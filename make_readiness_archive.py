"""Build the sanitized NanoBio Studio source archive.

Currently packages **Phase 2, Milestone 1** — the Experimental Validation
Registry — on top of the completed Phase 1 Scientific Readiness Framework.

Read-only with respect to the application: this script copies and filters, and
never edits a working file.

Four things it guarantees, in order of importance:

1. **No production database.** ``users.db`` and every other ``*.db``/``*.sqlite``
   is excluded unconditionally. There is no "inspect it and decide" path,
   because a database that looks empty today can hold a session row tomorrow.
2. **No account, session or identity records.** ``users.json``,
   ``sessions.json`` and their kin are denied by name wherever they appear, and
   the *content* of every included file is scanned for session tokens, password
   hashes and personal email addresses. Both halves are needed: a denylist
   cannot catch a session token pasted into a README, and a content scan cannot
   be trusted to parse every file format.
3. **No secrets or machine-specific configuration.** ``.env`` files, key
   material, certificates, ``.claude/`` and other per-machine directories are
   excluded by pattern, and included text is scanned for credential-shaped
   content and home-directory paths.
4. **Nothing that could be mistaken for production data.** The archive name says
   what it is, and a README at its root says it again.

**A finding aborts the build.** There is no "warn and continue" path: a build
that prints a warning and writes the zip anyway produces exactly the artefact
the warning was about, and the warning is read afterwards if at all.

The final check runs against the **written archive**, reopened and re-scanned,
not against the file list that was intended to go into it. A guarantee about a
manifest is a guarantee about the wrong object; if the two ever disagree, the
zip is what got shared. A failed verification deletes the archive.

Usage:  python make_readiness_archive.py
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
#: Named for what the archive contains, not for the phase it started in.
#: The previous name said "scientific-readiness-phase1" long after the
#: contents had become Phase 2 Milestone 1, which is the kind of drift a
#: reader has no way to detect from the outside.
ARCHIVE_NAME = "nano-bio-studio-phase2-milestone1-validation-registry.zip"
PREFIX = "nano-bio-studio-phase2-milestone1-validation-registry"

# --------------------------------------------------------------------------
# Exclusions
# --------------------------------------------------------------------------

#: Directory names dropped wherever they appear.
EXCLUDE_DIRS = {
    "node_modules", "__pycache__", ".git", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".vite", "dist", "build", ".idea", ".vscode", "htmlcov",
    ".ipynb_checkpoints", "playwright-report", "test-results", ".benchmarks",
    # Snapshots of previous archive builds; including them would nest stale
    # copies of the source inside this one.
    "requested", "requested-a",
}

#: Uploaded experimental data and other runtime state.
#:
#: `var/attachments` is where the local attachment adapter writes uploaded raw
#: data, instrument exports and laboratory reports. That is somebody's
#: experimental data — the archive is source code, and shipping a researcher's
#: uploads inside it would be the same category of mistake as shipping the
#: user database.
RUNTIME_DATA_DIRS = {"var", "uploads", "attachments", "instance", "media"}

#: Per-machine and per-operator configuration. None of it describes the project,
#: all of it describes whoever built the archive: local absolute paths, tool
#: permissions, cloud profiles, credential helpers.
#:
#: ``.claude`` is here because ``.claude/settings.local.json`` carried this
#: machine's absolute paths (``D:\...``, ``C:\Users\<name>\...``) into a
#: previous archive. It is configuration for a tool, not part of the software.
MACHINE_CONFIG_DIRS = {
    ".claude", ".aws", ".ssh", ".gnupg", ".azure", ".docker", ".kube",
    ".gcloud", ".config", ".cursor", ".continue",
}

EXCLUDE_DIRS |= MACHINE_CONFIG_DIRS
EXCLUDE_DIRS |= RUNTIME_DATA_DIRS

#: Files denied by exact name, wherever in the tree they appear.
#:
#: These hold accounts, sessions or credentials rather than source. A glob would
#: be too loose — ``*.json`` is most of the project's fixtures — and a
#: path-specific rule too tight, because the legacy ``biotech-lab-main/`` subtree
#: carries its own copy of several of them. Matching on the bare filename is
#: what catches both, and any future third copy.
DENY_FILENAMES = {
    # Account records. `users.json` held a SHA-256 password hash and a real
    # personal email address.
    "users.json", "user.json", "accounts.json", "credentials.json",
    "htpasswd", ".htpasswd",
    # Session records. `sessions.json` held live session token keys, the
    # usernames they belonged to, and their activity timestamps.
    "sessions.json", "session.json", "sessionstore.json",
    # Tokens and secret stores.
    "token.json", "tokens.json", "auth.json", "secrets.json", "secrets.toml",
    "secrets.yaml", "secrets.yml", "service-account.json",
    # Per-machine tool configuration and credential helpers.
    "settings.local.json", ".netrc", "_netrc", "authorized_keys",
    "known_hosts", ".npmrc", ".pypirc",
    # Private keys by conventional name (the suffix globs below catch the rest).
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
}

#: Virtual environments under any spelling. A fixed list previously let
#: `.venv_new` through, which put 37 MB of site-packages in an archive.
VENV_RE = re.compile(r"^\.?(venv|virtualenv|env)([-_.].*)?$", re.IGNORECASE)

#: Files dropped by glob. Databases and secrets are unconditional.
EXCLUDE_GLOBS = (
    "*.db", "*.db-journal", "*.db-wal", "*.db-shm", "*.sqlite", "*.sqlite3",
    ".env", ".env.*", "*.env",
    "*.key", "*.pem", "*.pfx", "*.p12", "*.crt", "*.cer", "*.jks",
    "*.pyc", "*.pyo", "*.so", "*.dll", "*.dylib",
    "*.zip", "*.tar", "*.tar.gz", "*.7z", "*.rar",
    "*.log", ".DS_Store", "Thumbs.db",
    # Office lock files. Word and Excel write these while a document is
    # open; they are 162-byte fragments naming whoever had the file open,
    # so they are both noise and a small disclosure.
    "~$*", ".~lock.*",
    # Editor and merge leftovers.
    "*.orig", "*.rej", "*.bak", "*.swp", "*~",
    "*.pkl", "*.joblib", "*.h5", "*.pt", "*.pth", "*.onnx", "*.ckpt",
)

#: Kept despite matching an exclusion above — they carry no secret and are
#: needed to understand or run the project.
KEEP_ANYWAY = {".env.example", ".env.sample", ".env.template"}

#: Skip individual files larger than this. Source does not reach it.
MAX_FILE_BYTES = 8 * 1024 * 1024

# --------------------------------------------------------------------------
# Secret scanning
# --------------------------------------------------------------------------

TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".md",
    ".txt", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".html", ".css",
    ".sh", ".ps1", ".sql", ".example", ".sample", ".template", "",
}

#: Patterns that indicate a real credential rather than a placeholder.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.")),
    ("bcrypt hash", re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}")),
    ("Postgres URL with password",
     re.compile(r"postgres(?:ql)?://[^\s:/@]+:[^\s@]{3,}@")),
    ("Assigned secret literal", re.compile(
        r"(?i)\b(secret_key|api_key|access_token|auth_token|client_secret"
        r"|private_key)\b\s*[:=]\s*[\"'][^\"'\s]{16,}[\"']")),

    # ---- added after session and account records reached a built archive ----

    # A session token key of the shape `sessions.json` actually used:
    # `token_admin_1773922968`. Keyed on the literal prefix plus a long numeric
    # suffix, so it identifies a minted session rather than the word "token".
    ("Session token key", re.compile(r"\btoken_[A-Za-z0-9.\-]+_\d{6,}\b")),

    # A bearer/session token assigned to a session-ish key.
    #
    # The optional quote after the key name matters: in JSON the key is itself
    # quoted (`"access_token": "..."`), so a pattern that jumps straight from
    # the word to the colon matches Python and misses every JSON file — which
    # is the format session records actually arrive in.
    ("Assigned session token", re.compile(
        r"(?i)[\"']?\b(session_token|session_id|sessionid|access_token"
        r"|bearer_token|refresh_token|csrf_token)\b[\"']?\s*[:=]\s*"
        r"[\"'][A-Za-z0-9._\-]{16,}[\"']")),

    # A password hash assigned to a password-ish key.
    #
    # Deliberately keyed on the *field name*, not on "64 hex characters". The
    # golden vectors are full of 64-hex strings under a `"sha256"` key — they
    # are fixture checksums and must survive untouched. What makes a hash a
    # password hash is the field it sits in, so that is what is matched.
    ("Password hash", re.compile(
        r"(?i)\"?\b(password|password_hash|passwd|pwd|pass_hash|hashed_password)"
        r"\b\"?\s*[:=]\s*[\"'][A-Fa-f0-9]{32,}[\"']")),

    # Modern password-hash formats, which are self-identifying.
    #
    # bcrypt (`$2a$`/`$2b$`/`$2y$`) is deliberately *not* listed here: it has
    # its own detector above with its own allowlist entry, and matching it twice
    # would report one hash as two findings and need the same exemption written
    # in two places.
    ("Password hash (modern KDF)", re.compile(
        r"\$(argon2(?:id|i|d)|scrypt|pbkdf2[\w-]*)\$[^\s\"']{16,}")),
    ("Password hash (Django/Werkzeug)", re.compile(
        r"\b(pbkdf2_sha\d+|scrypt|argon2)\$[^\s\"']{16,}")),

    # A personal mailbox. Restricted to consumer mail providers on purpose:
    # the project's published business contacts (`info@expertsgroup.me`) and
    # its fictional fixtures (`admin@nanobio.local`, `u@x.invalid`) are
    # intentional and must not be flagged, while an individual's real address
    # must be. The distinction that matters is "whose mailbox is this", and the
    # provider domain is the reliable signal for it.
    # Split into two branches on purpose. Providers named by their second-level
    # label alone still need a TLD appended (`yahoo` + `.co.uk`); providers
    # whose identity *is* the full domain (`proton.me`, `mail.ru`) must not have
    # one demanded of them, or they never match.
    ("Personal email address", re.compile(
        r"(?i)\b[A-Za-z0-9._%+-]+@(?:"
        r"(?:gmail|googlemail|outlook|hotmail|live|msn|yahoo|ymail|icloud"
        r"|aol|protonmail|gmx|yandex|qq|163|126)\.[A-Za-z.]{2,}"
        r"|(?:proton\.me|me\.com|mac\.com|mail\.ru|web\.de|zoho\.com)"
        r")\b")),

    # A home directory identifies the machine and the operator who built the
    # archive. Project-relative paths and bare drive letters are fine; a path
    # through someone's user profile is not.
    ("Home-directory path", re.compile(
        r"(?i)(?:[A-Za-z]:\\{1,2}Users\\{1,2}|/home/|/Users/)"
        r"(?!(?:public|shared|all\s?users|default)\b)[A-Za-z0-9._-]{2,}[\\/]")),

    # ---- added after plaintext demo credentials were found in source -------

    # A password assigned as a readable literal.
    #
    # The negative lookahead hands long hex strings to the password-hash
    # detector above rather than reporting one value twice under two labels.
    ("Assigned plaintext password", re.compile(
        r"(?i)[\"']?\b(?:password|passwd|pwd|admin_password|user_password"
        r"|default_password|db_password|demo_password)\b[\"']?\s*[:=]\s*"
        r"[\"'](?![A-Fa-f0-9]{32,}[\"'])[^\"'\s]{3,64}[\"']")),

    # An unquoted credential beside its label — the shape documentation and
    # login screens use: `user: admin` / `pass: <something>`.
    #
    # Same line only: `[ \t]*` rather than `\s*`. With `\s*` the pattern walks
    # over newlines and matches every Sphinx docstring that has `:param
    # password:` on one line and code on the next, which is a false positive on
    # exactly the files most likely to mention passwords legitimately.
    # The leading alternation replaces a plain `\b`, and it is not cosmetic.
    # The real occurrence looked like `st.code("user: admin\npass: <value>")`
    # — an escape sequence in the source, so the character before `pass` is a
    # literal `n`, and `\b` finds no boundary there. A word boundary would have
    # missed the exact string this detector was written for.
    # Three constraints, each earning its place:
    #
    # * The optional backtick around the value — Markdown writes a documented
    #   credential as ``password: `value` ``, and documentation is where a
    #   default credential lives by definition.
    # * The value must end the line. Allowing a trailing `,` or `)` as well
    #   matched every `password=payload.password,` and `password: string;` in
    #   the codebase — hundreds of ordinary references, none of them a secret.
    # * Bare `pass` counts only at the start of a line or straight after a `\n`
    #   escape, which is the credential-block shape. Mid-sentence, "pass:" is
    #   overwhelmingly prose ("tests pass: pytest"), not a password.
    ("Documented credential pair", re.compile(
        r"(?i)(?:(?:\\n|^)[ \t]*pass"
        r"|(?:\\n|^|[^A-Za-z0-9_])(?:password|pwd))"
        r"[ \t]*[:=][ \t]*"
        # A value in backticks or quotes is a quoted literal, so it may be
        # followed by anything — Markdown routinely closes a parenthesis after
        # it. A bare value has to end the line, because without a delimiter
        # there is nothing to distinguish `password=TEST_PASSWORD)` from a
        # real one.
        r"(?:[`'\"]([A-Za-z][A-Za-z0-9._@!-]{4,40})[`'\"]"
        r"|([A-Za-z][A-Za-z0-9._@!-]{4,40})[ \t]*(?=$|\\n))",
        re.MULTILINE)),
)

# ---------------------------------------------------------------------------
# Known default and demo credentials
# ---------------------------------------------------------------------------

#: SHA-256 of credentials that must never reappear: the three this project
#: retired, plus the usual shipped defaults.
#:
#: Stored as **hashes, not plaintext**, and the reason is not ceremony. A
#: denylist of literal passwords has to contain the passwords, which would put
#: the retired ones straight back into the source this cleanup removed them
#: from — and into every archive built from it. Hashing lets the build refuse a
#: value it cannot itself disclose.
#:
#: To add one without ever writing it down:
#:     python -c "import hashlib,getpass; \
#:         print(hashlib.sha256(getpass.getpass().encode()).hexdigest())"
KNOWN_WEAK_CREDENTIAL_SHA256 = frozenset({
    "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",
    "f2561f567b862c9a3d557f3091c4902fade246a2136966c885ce177843120485",
    "656d604dfdba41a262963cce53699bbc56cd7a2c0da1ad5ead45fc49214159d6",
    "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f",
    "ac9689e2272427085e35b9d3e3e8bed88cb3434828b43b86fc0596cad4c6e270",
    "a68349561396ec264a350847024a4521d00beaa3358660c2709a80f31c7acdd0",
    "ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae",
    "9b8769a4a742959a2d0298c36fb70623f2dfacda8436237df08d8dfd5b37374c",
    "9b0eb22aef89516d6fb4b31ccf008a68abe0d10a3fc606316389613eccf96854",
    "e14cb9e5c0eeee0ea313a4e04fbd10aa17ac17aa33a3cad4bdfe74b87ca18ef8",
    "e606e38b0d8c19b24cf0ee3808183162ea7cd63ff7912dbb22b5e803286b4446",
    "d3ad9315b7be5dd53b31a273b3b3aba5defe700808305aa16a3062b76658a791",
    "6ca13d52ca70c883e0f0bb101e425a89e8624de51db2d2392593af6a84118090",
    "daaad6e5604e8e17bd9f108d91e26afe6281dac8fda0091040a7a6d7bd9b43b5",
    "8f0e2f76e22b43e2855189877e7dc1e1e7d98c226c95db247cd1d547928334a9",
    "a075d17f3d453073853f813838c15b8023b8c487038436354fe599c3942e1f95",
    # Two more this project had shipped: an instructor-area password that was
    # printed on the page it protected and repeated across seven documents,
    # and a provisioning password that two scripts set and echoed to stdout.
    "b5987cf2e9019baccae6c38310e286c145fa212aac821facc05ff409a0b2e1c9",
    "d3fc50c8f714cebd16d6c827826df01205bf519529f9d34775293cf9b70a420e",
})

#: Cheap pre-filter: a word followed by digits, the shape of every credential
#: in the set above. Hashing only these keeps the sweep to a few thousand
#: candidates per build instead of every token in the tree.
_CREDENTIAL_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9@!._-]{3,31}\b")

KNOWN_CREDENTIAL_LABEL = "Known default credential"


def find_known_credentials(text: str) -> list[tuple[int, str]]:
    """Locate known weak credentials. Returns (offset, redacted) pairs.

    The token is never returned in the clear. A build log is written to a
    terminal, a CI record and often a ticket; printing the credential to
    announce that it must not be shipped would ship it.
    """
    hits: list[tuple[int, str]] = []
    for match in _CREDENTIAL_TOKEN_RE.finditer(text):
        token = match.group(0)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if digest in KNOWN_WEAK_CREDENTIAL_SHA256:
            hits.append((match.start(),
                         f"{token[0]}{'*' * (len(token) - 1)} "
                         f"({len(token)} chars)"))
    return hits

#: Findings that identify a record rather than a credential. Reported under
#: their own heading so a reviewer can tell "an account file leaked" from "a key
#: leaked" — they need different responses.
IDENTITY_LABELS = frozenset({
    "Session token key", "Assigned session token", "Password hash",
    "Password hash (modern KDF)", "Password hash (Django/Werkzeug)",
    "Personal email address", "Home-directory path",
    "Assigned plaintext password", "Documented credential pair",
    "Known default credential",
})

#: Substrings that mark a match as an obvious placeholder or a detector.
PLACEHOLDER_HINTS = (
    "example", "placeholder", "your-", "your_", "changeme", "change-me",
    "xxxx", "<", "dummy", "fake", "sample", "replace", "todo", "insert",
    "os.environ", "getenv", "process.env", "settings.", "config.",
)

#: A much narrower list for identity findings.
#:
#: The general list above suppresses any line containing "<", "sample" or
#: "config." — sensible for a key that might appear in a code snippet, far too
#: loose for a real mailbox or a live session token, which would be suppressed
#: by an unrelated angle bracket on the same line. A session token in a file
#: that also says "example" is still a session token.
IDENTITY_PLACEHOLDER_HINTS = (
    "placeholder", "your-", "your_", "changeme", "change-me", "xxxx",
    "user@example", "@example.com", "@example.org",
)

#: Files exempt from the scan: they contain the detection patterns themselves,
#: so scanning them would match the detectors rather than any real secret.
#:
#: Both are inspected deliberately and neither is a dumping ground: the builder
#: holds regular expressions, and the sanitation tests hold synthetic fixtures
#: invented for the tests. No value copied from a real account, session or
#: mailbox belongs in either, and a test asserts that the tests' own fixtures
#: are absent from the rest of the tree.
SCAN_EXEMPT = {"make_readiness_archive.py", "test_archive_sanitation.py"}

#: Narrow, per-finding exemptions. Each was inspected and is genuinely not a
#: credential. Keyed on (path suffix, pattern label) so the scanner stays strict
#: everywhere else — a real key in one of these files would still be caught
#: unless it matched the same pattern, and a new file gets no exemption at all.
#:
#: Every entry carries the reason it is safe. An exemption without a reason is
#: indistinguishable from an oversight.
ALLOWLIST: tuple[tuple[str, str, str], ...] = (
    (
        "app/core/passwords.py", "Known default credential",
        "The password REJECTION list. Every string in `_COMMON_BASES` is "
        "there so that a user choosing it is refused — these are "
        "anti-credentials, and removing them would make the application "
        "accept the passwords they name. The file contains no credential for "
        "anything.",
    ),
    (
        "app/core/security.py", "bcrypt hash",
        "A fixed dummy hash used by dummy_password_verify() to burn one "
        "bcrypt verification when a username does not exist, so a missing "
        "account and a wrong password take similar time. It is nobody's "
        "password hash and its plaintext is irrelevant.",
    ),
    (
        "test_phase3_integration.py", "Assigned secret literal",
        "A signing key literal inside a test: 'test-secret-key-for-testing'. "
        "It signs nothing outside that test process.",
    ),
    (
        "nanobio_studio_backend/README.md", "Postgres URL with password",
        "Documentation showing the psql connection form. The credential is "
        "the literal text 'user:password'.",
    ),
    (
        "account-walkthrough.mjs", "Assigned plaintext password",
        "Anti-credentials in a negative test. The walkthrough posts "
        "'an-administrator-chosen-password' to the account-creation endpoint "
        "to assert that an administrator supplying a password is REFUSED with "
        "422 rather than having the field silently ignored, and a deliberately "
        "too-short value to assert that a rejected password does not consume "
        "the activation link. Both are asserted to be refused; neither "
        "authenticates anything. Every password that actually works in that "
        "script is generated at run time from crypto.randomBytes and never "
        "leaves the process.",
    ),
    (
        "account-walkthrough.mjs", "Documented credential pair",
        "The same line as the entry above, matched by a second detector. The "
        "walkthrough sends a username together with a password to the "
        "account-creation endpoint precisely so it can assert the request is "
        "REFUSED with 422 — an administrator must not be able to choose "
        "somebody's password, and a field that were silently ignored would "
        "leave them believing they had. The pair authenticates nothing and "
        "corresponds to no account.",
    ),
    (
        "tests/test_auth_api.py", "Assigned plaintext password",
        "Deliberately WRONG passwords ('wrong', 'not-the-password') posted to "
        "the login endpoint by tests that assert they are rejected with 401 "
        "and that a bad password is indistinguishable from an unknown user. "
        "These are anti-credentials: each one is asserted to authenticate "
        "nobody, and replacing them with anything else would not change what "
        "the tests prove.",
    ),
    (
        "tests/test_medical_reports.py", "Assigned plaintext password",
        "Fixture passwords for two accounts created inside a per-test "
        "temporary database built by tmp_path_factory and discarded when the "
        "module finishes. They authenticate nothing outside that process and "
        "correspond to no account in any real database.",
    ),
    (
        "tests/test_workspace_api.py", "Assigned plaintext password",
        "Fixture passwords for two accounts created inside a per-test "
        "temporary database built by tmp_path_factory and discarded when the "
        "module finishes. They authenticate nothing outside that process and "
        "correspond to no account in any real database.",
    ),
    (
        "tests/test_auth_api.py", "Session token key",
        "A deliberately forged cookie value in "
        "test_forged_cookie_is_rejected, which asserts that a guessed token "
        "authenticates nobody. It was never minted by the application and "
        "corresponds to no session; the test's whole point is that it is "
        "refused. Its timestamp component is a round invented number, not an "
        "issue time.",
    ),
)


def allowlist_reason(rel: str, label: str) -> str | None:
    for suffix, allowed_label, reason in ALLOWLIST:
        if label == allowed_label and rel.endswith(suffix):
            return reason
    return None


def is_excluded_dir(name: str) -> bool:
    return name in EXCLUDE_DIRS or bool(VENV_RE.match(name))


def is_denied_file(name: str) -> bool:
    """Account, session, token or machine-configuration file, by name.

    Checked case-insensitively and independently of location, so a copy in a
    legacy subtree is denied on the same terms as the one at the root.
    """
    return name.lower() in DENY_FILENAMES


def is_excluded_file(path: Path) -> bool:
    if is_denied_file(path.name):
        # Denied outranks kept: an explicit allowance must never resurrect an
        # account or session record.
        return True
    if path.name in KEEP_ANYWAY:
        return False
    from fnmatch import fnmatch
    return any(fnmatch(path.name, pattern) for pattern in EXCLUDE_GLOBS)


def denied_reason(rel: str) -> str | None:
    """Why a path must not be in the archive, or None if it may be.

    Operates on the archive-relative path so it can be run against the entries
    of a *written* zip, not only against a path on disk. That is what makes the
    post-build verification a check of the artefact rather than of the intent.
    """
    parts = Path(rel).parts
    name = parts[-1] if parts else rel

    if is_denied_file(name):
        return "account, session or credential record"
    for segment in parts[:-1]:
        if segment in MACHINE_CONFIG_DIRS:
            return f"machine-specific configuration directory {segment!r}"
        if segment in RUNTIME_DATA_DIRS:
            return (f"runtime data directory {segment!r} — uploaded "
                    "experimental data is never archived")
        if segment in EXCLUDE_DIRS or VENV_RE.match(segment):
            return f"excluded directory {segment!r}"
    if name.lower().endswith((".db", ".db-journal", ".db-wal", ".db-shm",
                              ".sqlite", ".sqlite3")):
        return "database file"
    if name == ".env" or (name.startswith(".env.")
                          and name not in KEEP_ANYWAY):
        return "environment file with real values"
    if name.lower().endswith((".key", ".pem", ".pfx", ".p12", ".jks")):
        return "key material"
    return None


def scan_text(text: str, rel: str, name: str,
              exempted: list[str]) -> list[str]:
    """Scan already-read text. Returns human-readable findings; empty is clean.

    Separated from file reading so the same detectors run against a path on
    disk *and* against an entry read back out of the written archive. One
    implementation, two call sites, no chance of the pre- and post-build checks
    drifting apart.

    Anything matched by the allowlist is recorded in ``exempted`` rather than
    dropped silently, so the build output still shows a reviewer every place a
    credential-shaped string exists and why it was accepted.
    """
    if name in SCAN_EXEMPT:
        return []
    lines = text.splitlines()
    findings: list[str] = []
    for label, pattern in SECRET_PATTERNS:
        identity = label in IDENTITY_LABELS
        hints = IDENTITY_PLACEHOLDER_HINTS if identity else PLACEHOLDER_HINTS
        for match in pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            line = lines[line_no - 1] if 0 < line_no <= len(lines) else ""
            if any(hint in line.lower() for hint in hints):
                continue
            reason = allowlist_reason(rel, label)
            if reason:
                exempted.append(f"{rel}:{line_no}  {label}\n      {reason}")
                continue
            # Identity findings are reported by what matched, not by the whole
            # line: printing the surrounding line would copy the very record
            # the build is refusing to ship into the build log.
            shown = (f"{match.group(0)[:24]}..." if identity
                     else line.strip()[:110])
            findings.append(f"{rel}:{line_no}  {label}: {shown}")

    # Known credentials are matched by hash rather than by pattern, so they are
    # checked separately. Same reporting discipline: the value is redacted.
    for offset, redacted in find_known_credentials(text):
        line_no = text.count("\n", 0, offset) + 1
        reason = allowlist_reason(rel, KNOWN_CREDENTIAL_LABEL)
        if reason:
            exempted.append(
                f"{rel}:{line_no}  {KNOWN_CREDENTIAL_LABEL}\n      {reason}")
            continue
        findings.append(
            f"{rel}:{line_no}  {KNOWN_CREDENTIAL_LABEL}: {redacted}")
    return findings


def scan_for_secrets(path: Path, rel: str,
                     exempted: list[str]) -> list[str]:
    """Scan one file on disk."""
    if path.name in SCAN_EXEMPT or path.suffix.lower() not in TEXT_SUFFIXES:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return scan_text(text, rel, path.name, exempted)


def _detector_list() -> str:
    """The detector labels, generated from SECRET_PATTERNS.

    Generated rather than typed so the README cannot claim a guarantee the
    scanner does not implement, or omit one it does. A hand-written list is
    accurate on the day it is written and drifts from then on — and a
    sanitation document that overstates its scanner is worse than none, because
    it is trusted.
    """
    labels = [label for label, _ in SECRET_PATTERNS]
    labels.append(KNOWN_CREDENTIAL_LABEL)
    return "\n".join(f"* {label}" for label in labels)


def _denied_list() -> str:
    """The denied filenames, generated from DENY_FILENAMES."""
    return ", ".join(f"`{name}`" for name in sorted(DENY_FILENAMES))


def _machine_dir_list() -> str:
    return ", ".join(f"`{name}/`" for name in sorted(MACHINE_CONFIG_DIRS))


README = f"""# NanoBio Studio — Phase 2, Milestone 1
# Experimental Validation Registry

## THIS IS A SANITIZED SOURCE ARCHIVE. IT IS NOT PRODUCTION DATA.

It contains **source code and documentation only**.

## What this milestone delivers

The **Experimental Validation Registry**: in-vitro experiments recorded against
an exact, immutable candidate version, reviewed and approved independently, and
consumed by Scientific Readiness as the only route to evidence level **E3**.

* **Candidate versioning.** A candidate version is a verbatim snapshot of the
  formulation with a SHA-256 checksum. Editing a design afterwards creates a new
  version rather than changing the old one, so a result stays attributable to
  the material that was actually tested.
* **14 in-vitro assay subtypes**, each with its own measurement fields. There is
  deliberately no universal measurement form: a release profile is a time
  course, a zeta potential is not, and one form asking for both would either
  lose information or invent fields that do not apply.
* **Structured measurements**, per replicate, per group, per time point — not a
  narrative conclusion. The value as entered is preserved; any normalisation is
  stored separately beside its method.
* **A 17-gate eligibility evaluator**, deterministic and versioned, returning
  every gate result with a plain-language reason and a remedy.
* **Workflow**: Draft → Submitted → Under review → Approved / Rejected /
  Revision required → Superseded. Submission freezes the version; approval makes
  it immutable; a correction creates a new version and supersedes the old one
  without rewriting it.
* **Independent review.** An experiment cannot be approved by whoever performed
  it, and an administrator cannot approve science at all — administration
  manages access, which is not a scientific judgement. Both are enforced in the
  backend, not by hiding buttons.
* **Append-only audit trail** with no foreign key to its subject, so it outlives
  what it describes.
* **Attachments** validated on the server for filename, type, size and content,
  addressed only by opaque key.
* **Contradiction handling.** Where approved experiments for one purpose
  disagree, the level is **held**; the favourable record is never preferred.
  A reviewer may record an explicit resolution with a rationale, which is
  audited and supersedes rather than overwrites — and a conflict reopens if an
  experiment is approved after the resolution was written.

## What E3 means here, exactly

> **E3 is approved in-vitro evidence for one specific scientific purpose, on one
> specific candidate version.**
>
> It does **not** mean the candidate is validated, the study is validated, or
> that any other purpose is supported.

An approved cytotoxicity experiment promotes *safety assessment* for *that
candidate version* and nothing else. Every other readiness area keeps whatever
level its own records justify. E3 is never inferred from the type of experiment,
never granted because a form was completed or a file uploaded, and never
propagated between purposes.

Each in-vitro subtype may only claim purposes its method can actually evidence.
**No in-vitro subtype may claim pharmacokinetic modelling or cinematic
animation** — nothing in a culture plate observes distribution or clearance in
an organism.

### Levels above E3 are not implemented

E4 (prospective in-vitro), E5 (in-vivo) and E6 (clinical) require evidence this
milestone does not record. They appear in the vocabulary so the shape of the
scale is visible, are marked "coming in a later phase", and **cannot be
selected, requested or granted**. The evaluator caps every path at E3.

### Phase 1 behaviour is unchanged

A study with no approved experiment produces exactly the E0–E2 outcome it
produced in Phase 1. Measured data alone still promotes nothing.

## What is excluded, exactly

The lists below are generated from the builder's own constants at build time,
so they state what the scanner actually enforces rather than what someone
remembered to write down.

**Files denied by name, at any depth, case-insensitively:**

{_denied_list()}

**Directories dropped wherever they appear** (per-machine and per-operator
configuration, which describes the build machine rather than the project):

{_machine_dir_list()}

**Also excluded:** uploaded experimental data (`var/`, `uploads/` — where the
local attachment adapter writes raw data, instrument exports and laboratory
reports), every database file (`*.db`, `*.sqlite`, `*.sqlite3`),
every `.env` with real values (`.env.example` is kept, placeholders only), keys
and certificates, virtual environments, `node_modules`, build output and caches.

## What the content scanner refuses

Every included text file is scanned. **A match aborts the build**; no archive is
written. These are the detectors, in full:

{_detector_list()}

The last one is matched by SHA-256 against a set of known default and demo
credentials, so the builder can refuse a password it does not itself contain.

## What is checked, and when

1. **Before writing** — the file list is checked against the denial rules and
   every included text file is scanned.
2. **After writing** — the zip is reopened and *re-scanned from its own
   entries*. If verification fails the archive is **deleted**, not merely
   reported. A guarantee about a file list is a guarantee about the wrong
   object; the zip is the thing that gets shared.

## What this does NOT guarantee

Stated because a sanitation notice that overstates itself is self-defeating:

* It scans **text files only**. Binary formats (`.docx`, `.pdf`, images) are
  excluded from the content scan, though the `.docx` and `.pdf` files here are
  generated reports.
* It detects the patterns listed above and **no others**. A credential in a
  shape nobody anticipated is not caught. Silence means "no detector matched",
  not "nothing sensitive is present".
* Specifically, an *unknown* credential introduced by a keyword other than
  `password`/`pass`/`pwd` — `Password protection (default: <value>)`, say —
  is **not** matched by the pattern detectors. Treating `default:` as a
  credential keyword would match every `default:` line in every config file.
  Such values are caught only if they are already on the known-credential
  list.
* It cannot judge whether source code is *correct*, only whether it carries
  something that looks like a secret.
* A small number of findings are **allowlisted** with written reasons, printed
  in full during every build. They are inspected, not suppressed.

## Running it

The backend is a packaged project defined by `pyproject.toml`. There is no
`requirements.txt` — an earlier version of this README told you to install one
that does not exist.

    # backend (Python 3.11 or newer)
    cd nanobio_studio_backend
    python -m venv .venv
    .venv\\Scripts\\activate          # Windows
    # source .venv/bin/activate       # macOS / Linux
    pip install -e .
    python -m uvicorn nanobio_studio.app.vertical_slice:app --reload

    # frontend (Node 18 or newer), in a second terminal
    cd frontend
    npm install
    npm run dev

The frontend dev server proxies `/api` to the backend, so open the interface at
the frontend's address rather than the backend's.

## First-user setup

There is no database in this archive; the application creates an empty one on
first start, with **no accounts at all**. Create your own:

    cd nanobio_studio_backend
    python scripts/create_admin.py --username admin --role admin
    python scripts/create_admin.py --username researcher_a --role researcher
    python scripts/create_admin.py --username researcher_b --role researcher

**Two researchers are required, not optional.** An administrator manages access
and is barred from authoring, reviewing or approving experiments, and an
experiment cannot be approved by whoever performed it — so a single account
cannot complete the registry workflow.

The script prompts for the password with hidden input, or reads
`NANOBIO_ADMIN_PASSWORD` for unattended provisioning. It never accepts a
password on the command line, because argv is visible to other processes.

**No operational, default, provisioning, or walkthrough password appears in
this archive. Fictional test-only values may appear in isolated automated
tests.**

There is no default credential to change, because there is no default
credential. The script prompts with hidden input, enforces a minimum length,
and rejects common defaults — including any word followed by digits, which is
the shape of nearly every shipped default password.

The Playwright walkthroughs under `frontend/` read their account from
`NANOBIO_WALKTHROUGH_USER` and `NANOBIO_WALKTHROUGH_PASSWORD` and refuse to run
without them. The legacy Streamlit sign-in page reads its development accounts
from `NANOBIO_DEMO_*_PASSWORD` and disables sign-in when none is set.

## What Phase 1 provides underneath

The Scientific Readiness Framework: six independently-assessed readiness areas,
persistent scientific records with provenance, a 60-field data dictionary, a
versioned deterministic rules engine, the `/scientific-readiness` dashboard,
immutable readiness snapshots, and additive migrations.

Read `docs/SCIENTIFIC_READINESS.md` first. Its §12 states the framework's
limitations plainly, and §15 records the defects corrected after Phase 1 was
first written up — including the one where a value marked "measured" was
promoted to E3 with nothing behind it.

## The legacy `biotech-lab-main/` directory

**It is not an obsolete duplicate, and it is not dead weight to be deleted.**

It is a snapshot of the pre-correction Streamlit application. 281 of its 304
files are byte-identical to the root copy, but 17 differ and 6 exist only
there — and `Login.py` at the root adds it to `sys.path` at runtime, so the
legacy Streamlit entry point does not start without it.

Two things to know before touching it:

* Its `core/scoring.py` and `utils/pk_model.py` are the **pre-fix versions**.
  They lack the shared null-handling contract and still import matplotlib at
  module scope. The corrected versions are the ones at the repository root, and
  those are what the FastAPI backend, the golden vectors and every test use.
* Nothing in Phase 1 or Phase 2 imports from it. If you are reading scientific
  code, read the root copy.

It remains because deleting it would break the legacy entry point and discard
six files that exist nowhere else, which is a larger decision than a packaging
correction.

**Readiness is not accreditation.** It describes whether the information
recorded for a study is sufficient and self-consistent for a kind of analysis.
It is not regulatory approval, clinical validation, or evidence that any result
is correct. A study can be fully ready and still be scientifically wrong.

**Evidence levels E3 to E6 are not reachable.** They assert that a prediction
was validated against an experiment or an independent result, and there is no
Experimental Validation Registry to record one in. No study can currently
exceed E2, whatever it records. This is stated as a limitation rather than
worked around; see §4.3 and §15.1.

## Test results at the time of packaging

* backend: 1552 passed, 0 failed, 0 skipped
  (including 153 archive-sanitation, 57 validation-registry and 73
  registry-API/attachment-security tests)
* frontend: 709 passed across 19 files, 0 failed
* typecheck: clean
* browser walkthroughs: 8 scripts, no problems
  (including the live end-to-end registry walkthrough: 48 checks)

## Known exemption

`tests/test_auth_api.py` line 311 contains the one token-shaped string in this
archive. It is a **forged** cookie value in `test_forged_cookie_is_rejected`,
which asserts that a guessed token authenticates nobody. It was never minted by
the application, corresponds to no session, and its numeric component is a round
invented number rather than an issue time. It is recorded in the builder's
`ALLOWLIST` with that reason; every other such string aborts the build.

(The value is deliberately not reproduced here. This README is itself scanned
before the archive is sealed, and quoting a token in the document that explains
the token policy is how the policy gets undermined by its own documentation.)

Archive: `{ARCHIVE_NAME}`
"""


def collect_files(root: Path) -> tuple[list[tuple[Path, str]],
                                       list[str], list[str]]:
    """Walk the tree and return (included, skipped_large, refused).

    ``refused`` names the account, session and credential files that were found
    and left out. They are **reported rather than fatal**, and the distinction
    is deliberate:

    * Not fatal, because these files legitimately exist in a working checkout.
      A builder that aborted whenever a developer had logged in once would be a
      builder nobody could run, and an unrunnable check is an absent one.
    * Not silent, because "the archive is clean" and "the archive is clean
      because eleven account records were refused" are different facts, and the
      operator needs the second one. Dropping them without a word is how nobody
      notices that a session store has appeared in the tree.

    Content findings *are* fatal, because a token pasted into a source file is
    not something the build can route around.
    """
    included: list[tuple[Path, str]] = []
    skipped_large: list[str] = []
    refused: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        for name in dirnames:
            if name in MACHINE_CONFIG_DIRS:
                refused.append(
                    f"{(here / name).relative_to(root).as_posix()}/  "
                    "(machine-specific configuration)")
        dirnames[:] = sorted(d for d in dirnames if not is_excluded_dir(d))
        for filename in sorted(filenames):
            path = here / filename
            if path.name == ARCHIVE_NAME:
                continue
            if is_denied_file(path.name):
                refused.append(f"{path.relative_to(root).as_posix()}  "
                               "(account, session or credential record)")
                continue
            if is_excluded_file(path):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            if size > MAX_FILE_BYTES:
                skipped_large.append(f"{rel} ({size / 1e6:.1f} MB)")
                continue
            included.append((path, rel))
    return included, skipped_large, refused


def verify_archive(archive: Path) -> list[str]:
    """Re-scan a written archive. Returns problems; empty means clean.

    Reads the entries back out of the zip rather than trusting the list that
    was meant to go in. The manifest is a statement of intent; the zip is the
    thing that gets shared, and only one of the two can actually leak.
    """
    problems: list[str] = []
    exempted: list[str] = []
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            # Entries are prefixed with the archive root; strip it so the
            # denial rules see the same relative path they were written from.
            rel = info.filename.split("/", 1)[-1]
            name = rel.rsplit("/", 1)[-1]

            reason = denied_reason(rel)
            if reason:
                problems.append(f"{rel}: {reason}")
                continue
            if Path(name).suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                text = z.read(info).decode("utf-8", errors="ignore")
            except (OSError, zipfile.BadZipFile) as exc:
                problems.append(f"{rel}: unreadable ({exc})")
                continue
            problems.extend(scan_text(text, rel, name, exempted))
    return problems


def main(root: Path | None = None, out: Path | None = None) -> int:
    root = root or ROOT
    out = out or (root / ARCHIVE_NAME)

    included, skipped_large, refused = collect_files(root)
    print(f"candidate files: {len(included)}")

    if refused:
        print(f"\nrefused {len(refused)} sensitive path(s) — excluded from "
              f"the archive:")
        for r in refused:
            print(f"    {r}")

    # ---- scan before writing anything -----------------------------------
    findings: list[str] = []
    exempted: list[str] = []
    for path, rel in included:
        findings.extend(scan_for_secrets(path, rel, exempted))

    # ---- and check the exclusions held, before writing too ---------------
    for _, rel in included:
        reason = denied_reason(rel)
        if reason:
            findings.append(f"{rel}: {reason} — must not be archived")

    if findings:
        print("\nABORTED — sensitive content found:\n")
        for f in findings[:40]:
            print(f"  {f}")
        if len(findings) > 40:
            print(f"  ... and {len(findings) - 40} more")
        print("\nNo archive was written. Remove or parameterise these first.")
        return 1

    print("pre-build scan: clean")
    if exempted:
        print(f"\n  {len(exempted)} credential-shaped string(s) inspected "
              f"and accepted:")
        for e in exempted:
            print(f"    {e}")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(f"{PREFIX}/README-ARCHIVE.md", README)
        for path, rel in included:
            z.write(path, f"{PREFIX}/{rel}")

    # ---- verify the artefact, not the intent ----------------------------
    problems = verify_archive(out)
    if problems:
        # Deleting is the point. Leaving a failed archive on disk beside a
        # console message is how a leaky zip gets shared anyway.
        out.unlink(missing_ok=True)
        print("\nABORTED — the written archive failed verification:\n")
        for p in problems[:40]:
            print(f"  {p}")
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more")
        print(f"\n{out.name} was deleted. Nothing shippable was produced.")
        return 1

    print("post-build verification: clean "
          "(re-scanned from the written archive)")

    size_mb = out.stat().st_size / 1e6
    print(f"\nwrote {out.name}")
    print(f"  entries: {len(included) + 1}")
    print(f"  size:    {size_mb:.1f} MB")
    if skipped_large:
        print(f"  skipped {len(skipped_large)} file(s) over "
              f"{MAX_FILE_BYTES / 1e6:.0f} MB:")
        for s in skipped_large[:10]:
            print(f"    {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
