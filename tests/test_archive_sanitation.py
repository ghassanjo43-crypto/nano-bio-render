"""Regression tests for archive sanitation.

**What went wrong.** A built archive shipped `users.json` (a SHA-256 password
hash and a real personal email address), `sessions.json` (live session token
keys with the usernames and activity times they belonged to), and
`.claude/settings.local.json` (this machine's absolute paths). Both copies of
the first two — the root one and the legacy `biotech-lab-main/` one — were
included. The builder scanned for *credentials* and found none, which was true
and beside the point: an account record is not a credential, and nothing was
looking for one.

**What these tests hold.** Three layers, because each fails differently:

1. **Denial** — the named files and machine-config directories are refused,
   wherever in the tree they sit.
2. **Detection** — the content scanner fires on a session token, a password
   hash, a personal mailbox and a home path pasted anywhere, including into a
   file with an innocent name. A denylist alone cannot catch a token in a
   README.
3. **Enforcement** — a build over a tree containing any of these *aborts and
   writes nothing*, and a tampered archive fails post-build verification and is
   deleted. Detection that does not stop the build is a log line nobody reads.

And one guard in the other direction: sanitation must not eat the science. The
golden vectors are full of 64-character hex strings under a `"sha256"` key, and
a naive "looks like a hash" rule would strip the scientific fixtures this
project's correctness rests on.

All fixture values here are invented. Nothing copied from a real account,
session or mailbox belongs in this file, and `test_fixtures_are_synthetic`
asserts the invented tokens appear nowhere else in the tree.
"""

from __future__ import annotations

import pathlib
import re
import sys
import zipfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import make_readiness_archive as builder  # noqa: E402

ARCHIVE = REPO_ROOT / builder.ARCHIVE_NAME

# --- invented fixtures, resembling what actually leaked -------------------
FAKE_SESSION_TOKEN = "token_fixtureuser_1234567890"
FAKE_SHA256 = "a" * 64
FAKE_PERSONAL_EMAIL = "not.a.real.person@gmail.com"
FAKE_HOME_PATH = r"C:\Users\fixtureoperator\Desktop\thing"

FAKE_USERS_JSON = (
    '{\n  "admin": {\n'
    f'    "password": "{FAKE_SHA256}",\n'
    '    "role": "admin",\n'
    f'    "email": "{FAKE_PERSONAL_EMAIL}"\n'
    '  }\n}\n'
)
FAKE_SESSIONS_JSON = (
    '{\n'
    f'  "{FAKE_SESSION_TOKEN}": {{\n'
    '    "username": "admin",\n'
    '    "roles": ["admin"],\n'
    '    "last_activity": "2026-03-19T16:22:48"\n'
    '  }\n}\n'
)


def scan(text: str, name: str = "probe.json") -> list[str]:
    """Run the content detectors over a string."""
    return builder.scan_text(text, f"some/dir/{name}", name, [])


def labels(findings: list[str]) -> set[str]:
    """The detector labels a finding list names."""
    found = set()
    for f in findings:
        for label, _ in builder.SECRET_PATTERNS:
            if f":  {label}" in f or f"  {label}:" in f:
                found.add(label)
    return found


# ===========================================================================
# 1. Denial -- the named files and directories are refused
# ===========================================================================


class TestSensitiveFilesAreDenied:

    @pytest.mark.parametrize("name", [
        "sessions.json", "users.json", "credentials.json", "secrets.json",
        "secrets.toml", "tokens.json", "settings.local.json", ".netrc",
        "id_rsa", "service-account.json", "authorized_keys", ".npmrc",
    ])
    def test_denied_by_name(self, name):
        assert builder.is_denied_file(name)
        assert builder.is_excluded_file(pathlib.Path("anywhere") / name)

    @pytest.mark.parametrize("name", ["SESSIONS.JSON", "Users.Json"])
    def test_denial_is_case_insensitive(self, name):
        """Windows is case-insensitive; the denylist must not be a way in."""
        assert builder.is_denied_file(name)

    @pytest.mark.parametrize("rel", [
        "sessions.json",
        "users.json",
        "biotech-lab-main/sessions.json",
        "biotech-lab-main/users.json",
        "some/deeply/nested/path/users.json",
    ])
    def test_denied_at_every_depth(self, rel):
        """The leak was two copies of each file, not one.

        A path-specific rule would have caught the root copy and shipped the
        legacy subtree's.
        """
        assert builder.denied_reason(rel) is not None

    @pytest.mark.parametrize("rel", [
        ".claude/settings.local.json",
        ".claude/anything.json",
        "nested/.aws/config",
        ".ssh/known_hosts",
        ".gnupg/secring.gpg",
    ])
    def test_machine_config_directories_are_denied(self, rel):
        assert builder.denied_reason(rel) is not None

    def test_the_directory_walk_never_descends_into_them(self):
        for name in builder.MACHINE_CONFIG_DIRS:
            assert builder.is_excluded_dir(name), name

    @pytest.mark.parametrize("rel", [
        "users.db", "nanobio_auth_dev.db", "data/x.sqlite3",
        ".env", "backend/.env", "server.key", "cert.pem",
    ])
    def test_databases_secrets_and_keys_stay_denied(self, rel):
        """The original guarantees must survive the new ones."""
        assert builder.denied_reason(rel) is not None

    @pytest.mark.parametrize("rel", [
        "var/attachments/ab/abcdef.bin",
        "uploads/plate-reads.csv",
        "instance/state.json",
        "nested/var/attachments/x",
    ])
    def test_uploaded_experimental_data_is_denied(self, rel):
        """A researcher's uploads are data, not source.

        The local attachment adapter writes raw data, instrument exports and
        laboratory reports under `var/`. Shipping those inside a source
        archive is the same category of mistake as shipping the user
        database.
        """
        assert builder.denied_reason(rel) is not None

    def test_the_runtime_directories_are_not_descended_into(self):
        for name in builder.RUNTIME_DATA_DIRS:
            assert builder.is_excluded_dir(name), name

    def test_an_upload_directory_is_dropped_from_a_build(self, tmp_path):
        _minimal_tree(tmp_path)
        uploads = tmp_path / "var" / "attachments" / "ab"
        uploads.mkdir(parents=True)
        (uploads / "abcdef0123456789.bin").write_bytes(b"raw instrument data")
        out = tmp_path / builder.ARCHIVE_NAME
        assert builder.main(root=tmp_path, out=out) == 0
        with zipfile.ZipFile(out) as z:
            assert not [n for n in z.namelist() if "attachments" in n]

    def test_denial_outranks_the_keep_anyway_allowance(self):
        """An allowance must never resurrect an account record."""
        assert ".env.example" in builder.KEEP_ANYWAY
        assert builder.denied_reason(".env.example") is None
        # But nothing on the denylist can be rescued the same way.
        for name in ("users.json", "sessions.json"):
            assert name not in builder.KEEP_ANYWAY
            assert builder.is_excluded_file(pathlib.Path(name))

    @pytest.mark.parametrize("rel", [
        "nanobio_studio_backend/nanobio_studio/app/science/rules.py",
        "docs/SCIENTIFIC_READINESS.md",
        "tests/golden_vectors/baseline.json",
        "frontend/.env.example",
        "package.json",
        "requirements.txt",
    ])
    def test_ordinary_project_files_are_not_denied(self, rel):
        """A denylist that refuses everything protects nothing."""
        assert builder.denied_reason(rel) is None


# ===========================================================================
# 2. Detection -- content, wherever it is pasted
# ===========================================================================


class TestSessionTokensAreDetected:

    def test_a_session_token_key_is_found(self):
        assert labels(scan(FAKE_SESSIONS_JSON)) & {"Session token key"}

    def test_it_is_found_in_a_file_with_an_innocent_name(self):
        """The case a denylist cannot reach."""
        findings = scan(f"Paste from the log: {FAKE_SESSION_TOKEN}\n",
                        "NOTES.md")
        assert labels(findings) & {"Session token key"}

    @pytest.mark.parametrize("assignment", [
        'session_token = "abcdef0123456789abcdef"',
        '"access_token": "abcdef0123456789abcdef"',
        "refresh_token: 'abcdef0123456789abcdef'",
    ])
    def test_an_assigned_token_is_found(self, assignment):
        assert labels(scan(assignment, "x.py")) & {"Assigned session token"}

    def test_the_finding_does_not_reprint_the_record(self):
        """Reporting must not copy the leak into the build log.

        The whole line of `sessions.json` carries the username and the activity
        timestamp beside the token. Printing it to abort the build would put
        the record in the console, and from there into whatever captured it.
        """
        findings = scan(FAKE_SESSIONS_JSON)
        blob = " ".join(findings)
        assert "last_activity" not in blob
        assert "2026-03-19T16:22:48" not in blob

    def test_the_word_token_alone_is_not_a_finding(self):
        """A detector that fires on prose is one people learn to ignore."""
        prose = ("The session token is set as an HttpOnly cookie. "
                 "See tokens.css for the design tokens.\n")
        assert not labels(scan(prose, "README.md")) & {"Session token key"}


class TestPasswordHashesAreDetected:

    def test_a_hash_in_a_password_field_is_found(self):
        assert labels(scan(FAKE_USERS_JSON)) & {"Password hash"}

    @pytest.mark.parametrize("line", [
        f'"password": "{FAKE_SHA256}"',
        f"password_hash = '{FAKE_SHA256}'",
        f'"hashed_password": "{"b" * 32}"',
    ])
    def test_password_field_variants(self, line):
        assert labels(scan(line, "x.py")) & {"Password hash"}

    @pytest.mark.parametrize("line", [
        "hash = '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$aBcDeFgHiJkLmNoP'",
        "h = 'pbkdf2_sha256$260000$abcdefghijklmnop$aBcDeFgHiJkLmNoPqRsTuV'",
    ])
    def test_self_identifying_kdf_formats(self, line):
        assert labels(scan(line, "x.py")) & {
            "Password hash (modern KDF)", "Password hash (Django/Werkzeug)"}

    def test_bcrypt_is_reported_once_not_twice(self):
        """bcrypt has a dedicated detector; the KDF pattern must not overlap.

        Two detectors for one hash means one exemption written in two places,
        and an exemption that is only half-applied reads as a live finding.
        """
        line = "h = '$2b$12$C6UzMDM.H6dfI/f/IKcEeO3Y.J1sHqE5oNQ5V0mFLtqUqxq0G0dGa'"
        found = labels(scan(line, "x.py"))
        assert "bcrypt hash" in found
        assert "Password hash (modern KDF)" not in found


class TestGoldenVectorChecksumsSurvive:
    """Sanitation must not eat the science."""

    def test_a_sha256_checksum_field_is_not_a_password_hash(self):
        vector = f'{{ "vector": "pk-b1", "sha256": "{FAKE_SHA256}" }}'
        assert not labels(scan(vector, "baseline.json")) & {
            "Password hash", "Password hash (modern KDF)"}

    def test_the_real_golden_vectors_scan_clean(self):
        """Run the detectors over the actual fixtures, not a stand-in."""
        vectors = sorted((REPO_ROOT / "tests" / "golden_vectors")
                         .glob("*.json"))
        assert vectors, "golden vectors are missing"
        for path in vectors:
            findings = builder.scan_for_secrets(
                path, f"tests/golden_vectors/{path.name}", [])
            assert findings == [], f"{path.name}: {findings[:3]}"

    def test_the_golden_vectors_are_still_in_the_archive(self):
        """The sanitation is not allowed to have quietly dropped them."""
        assert ARCHIVE.exists(), "build the archive first"
        with zipfile.ZipFile(ARCHIVE) as z:
            names = z.namelist()
        assert any(n.endswith("tests/golden_vectors/baseline.json")
                   for n in names)


class TestPlaintextPasswordsAreDetected:
    """Assigned readable passwords, and known defaults.

    The tree carried seven of these: three demo passwords printed on a login
    form, an admin password in two provisioning scripts, a one-word database
    default, and an instructor password displayed on the page it protected.
    None was a hash, so nothing was looking for them.
    """

    @pytest.mark.parametrize("line", [
        'password = "hunter2000"',
        '"password": "SomeValue!23"',
        "passwd: 'another-one-here'",
        'admin_password = "Provisioning@2024"',
        'DEMO_PASSWORD = "x9f2kd0s"',
    ])
    def test_an_assigned_plaintext_password_is_found(self, line):
        assert labels(scan(line, "x.py")) & {"Assigned plaintext password"}

    @pytest.mark.parametrize("line", [
        "user: admin\\npass: SomeSecret99",          # the login-form shape
        "Password: Provisioning@2024",               # the script-output shape
        "pwd = TrialValue77",
        "Enter correct password: `Teaching2024`",    # Markdown, backticked
        "2. Instructor Notes (password: `Teaching2024`)",
    ])
    def test_a_documented_credential_pair_is_found(self, line):
        assert labels(scan(line, "README.md")) & {"Documented credential pair"}

    def test_a_credential_behind_another_keyword_is_a_known_gap(self):
        """Recorded as a limitation rather than papered over.

        `Password protection (default: `value`)` puts the credential after
        `default:`, not after `password:`. Catching it would mean treating
        `default:` as a credential keyword, which matches every `default:
        enabled` in every YAML file in the tree.

        This shape is covered for *known* credentials by the hash detector —
        which is how the real instance was found — and is genuinely not covered
        for unknown ones. README-ARCHIVE.md says so.
        """
        line = "- Password protection (default: `Teaching2024`)"
        assert not labels(scan(line, "README.md")) & {
            "Documented credential pair"}

        known = "- Password protection (default: `" + "instructor2024" + "`)"
        assert builder.find_known_credentials(known), (
            "the hash detector must cover what the pair regex cannot")

    @pytest.mark.parametrize("line", [
        "password=payload.password,",            # a call argument
        "  password: string;",                   # a TypeScript type
        "        password=TEST_PASSWORD)",       # a constant reference
        "Run the tests and check they pass: pytest",   # prose
        "  const pass = process.env[PASS_VAR];",
        "await create_user(session, password=password)",
    ])
    def test_ordinary_password_references_are_not_flagged(self, line):
        """The regression that made a looser version of this unusable.

        Allowing a trailing `,` or `)` after the value matched hundreds of
        ordinary references — every call argument and type annotation naming a
        password parameter. A detector that fires on all of those is one whose
        output gets skimmed, which is worse than not having it.
        """
        assert not labels(scan(line, "x.ts")) & {"Documented credential pair"}

    def test_a_hash_is_not_double_reported_as_plaintext(self):
        """Long hex belongs to the password-hash detector, not this one."""
        found = labels(scan(f'"password": "{FAKE_SHA256}"', "x.json"))
        assert "Password hash" in found
        assert "Assigned plaintext password" not in found

    @pytest.mark.parametrize("line", [
        "password = st.text_input('Password', type='password')",
        'password = os.environ.get("NANOBIO_ADMIN_PASSWORD", "")',
        "password = os.getenv('NANOBIO_DEMO_ADMIN_PASSWORD')",
        "def check(self, password: str) -> bool:",
        "    :param password: the value to verify",
    ])
    def test_password_handling_code_is_not_flagged(self, line):
        """Reading a password is not disclosing one.

        This matters more than it looks: if the detector fired on the
        environment lookups that replaced the literals, the fix would have
        been unshippable and the literals would have stayed.
        """
        found = labels(scan(line, "x.py"))
        assert not found & {"Assigned plaintext password",
                            "Documented credential pair"}

    def test_a_docstring_parameter_does_not_span_lines(self):
        """The regression that made the first version of this unusable.

        With `\\s*` after the colon the pattern walked over the newline and
        matched every Sphinx docstring in the auth modules — the files most
        likely to mention passwords for entirely good reasons.
        """
        docstring = (
            'def verify(self, password):\n'
            '    """Check it.\n\n'
            '    :param password:\n'
            '        return True when it matches.\n'
            '    """\n'
            '    return True\n'
        )
        assert not labels(scan(docstring, "auth.py")) & {
            "Documented credential pair"}


class TestKnownDefaultCredentialsAreDetected:
    """Matched by hash, so the denylist need not contain the passwords."""

    def test_the_retired_demo_passwords_are_recognised(self):
        """The three this cleanup removed, reconstructed only in memory.

        Built from parts so the literals do not appear in this file either —
        the point of hashing them in the builder is that they stop existing in
        the source tree, and a test that pasted them back would undo it.
        """
        for stem in ("admin", "science", "view"):
            token = stem + "1" + "2" + "3"
            hits = builder.find_known_credentials(f'pw = "{token}"')
            assert hits, f"{stem}<digits> is not on the known-credential list"

    def test_the_finding_never_prints_the_credential(self):
        """A build log goes to a terminal, CI and often a ticket."""
        token = "admin" + "123"
        hits = builder.find_known_credentials(f'pw = "{token}"')
        assert hits
        _, redacted = hits[0]
        assert token not in redacted
        assert redacted.startswith("a*")
        assert "8 chars" in redacted

    def test_the_denylist_holds_hashes_not_passwords(self):
        """The property that lets the builder refuse what it cannot disclose."""
        for entry in builder.KNOWN_WEAK_CREDENTIAL_SHA256:
            assert re.fullmatch(r"[a-f0-9]{64}", entry), entry

    def test_the_two_provisioning_literals_are_recognised(self):
        """An instructor-area password and a provisioning password.

        Both were found only after the plaintext detectors existed: neither was
        a hash, so the first sanitation pass had nothing that could see them.
        Reconstructed from parts here for the same reason as above.
        """
        for token in ("instructor" + "2024", "Admin" + "@" + "2024"):
            assert builder.find_known_credentials(f'pw = "{token}"'), token

    def test_ordinary_words_are_not_flagged(self):
        prose = ("The readiness engine reports evidence level E2 for a "
                 "measured value. See baseline2026 for the vectors.\n")
        assert builder.find_known_credentials(prose) == []

    def test_it_fires_through_the_full_scanner(self):
        token = "science" + "123"
        assert labels(scan(f'demo_pw = "{token}"', "notes.md")) or True
        findings = scan(f'literal {token} here', "notes.md")
        assert any("Known default credential" in f for f in findings)


class TestPersonalDataIsDetected:

    def test_a_personal_mailbox_is_found(self):
        assert labels(scan(FAKE_USERS_JSON)) & {"Personal email address"}

    @pytest.mark.parametrize("addr", [
        "someone@gmail.com", "someone@outlook.com", "someone@yahoo.co.uk",
        "someone@proton.me", "someone@icloud.com", "someone@yandex.ru",
    ])
    def test_consumer_providers_are_flagged(self, addr):
        assert labels(scan(f"contact: {addr}", "x.md")) & {
            "Personal email address"}

    @pytest.mark.parametrize("addr", [
        "info@expertsgroup.me",         # published business contact
        "licensing@expertsgroup.ae",    # published business contact
        "admin@nanobio.local",          # fixture
        "u@x.invalid",                  # fixture
        "admin@nanobio.com",            # fictional demo account
    ])
    def test_business_and_fixture_addresses_are_not_flagged(self, addr):
        """The distinction that matters is whose mailbox it is.

        A company's published contact address and an invented test fixture are
        meant to be in the source. An individual's real mailbox is not. A rule
        that flagged every email would be turned off within a week.
        """
        assert not labels(scan(f"contact: {addr}", "x.md")) & {
            "Personal email address"}

    @pytest.mark.parametrize("path", [
        r"C:\Users\someone\Desktop\notes.txt",
        r"C:\\Users\\someone\\project\\file.py",
        "/home/someone/project/file.py",
        "/Users/someone/project/file.py",
    ])
    def test_home_directory_paths_are_flagged(self, path):
        assert labels(scan(f'p = "{path}"', "x.py")) & {"Home-directory path"}

    @pytest.mark.parametrize("path", [
        "D:/Nano_bio_Studio_30-7-2026/tests",
        "./frontend/src/api/client.ts",
        "/usr/local/bin/python",
        "/var/log/app.log",
    ])
    def test_project_and_system_paths_are_not_flagged(self, path):
        """Only the part that identifies a person is sensitive."""
        assert not labels(scan(f'p = "{path}"', "x.py")) & {
            "Home-directory path"}

    def test_identity_findings_are_not_suppressed_by_a_stray_bracket(self):
        """The general placeholder list is too loose for identity findings.

        It drops any line containing '<', 'sample' or 'config.' — reasonable
        for a key in a code snippet, and a hole a real token would fit through.
        """
        line = f'<p>sample config. token: {FAKE_SESSION_TOKEN}</p>'
        assert labels(scan(line, "page.html")) & {"Session token key"}


# ===========================================================================
# 3. Enforcement -- a finding stops the build
# ===========================================================================


def _minimal_tree(root: pathlib.Path) -> None:
    """A tiny but valid project tree, with nothing sensitive in it."""
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# probe\n", encoding="utf-8")
    (root / "docs" / "notes.md").write_text("Nothing here.\n",
                                            encoding="utf-8")


class TestABuildAborts:

    def test_a_clean_tree_builds(self, tmp_path):
        """The control. Without it, every abort test below proves nothing."""
        _minimal_tree(tmp_path)
        out = tmp_path / builder.ARCHIVE_NAME
        assert builder.main(root=tmp_path, out=out) == 0
        assert out.exists()

    @pytest.mark.parametrize("name, content", [
        ("sessions.json", FAKE_SESSIONS_JSON),
        ("users.json", FAKE_USERS_JSON),
    ])
    def test_an_account_or_session_record_is_excluded_and_reported(
            self, tmp_path, name, content):
        """Dropped, not fatal — but never dropped quietly.

        These files legitimately exist in a working checkout, so aborting on
        them would make the builder unrunnable. What must not happen is the
        build reporting "clean" while saying nothing about what it refused.
        """
        _minimal_tree(tmp_path)
        (tmp_path / name).write_text(content, encoding="utf-8")
        out = tmp_path / builder.ARCHIVE_NAME

        assert builder.main(root=tmp_path, out=out) == 0
        _, _, refused = builder.collect_files(tmp_path)
        assert any(name in r for r in refused), (
            f"{name} was excluded without being reported")

        with zipfile.ZipFile(out) as z:
            assert not [n for n in z.namelist() if name in n]
        assert builder.verify_archive(out) == []

    def test_a_record_in_a_legacy_subtree_is_excluded_too(self, tmp_path):
        """Both copies leaked; catching only the root one is not a fix."""
        _minimal_tree(tmp_path)
        legacy = tmp_path / "biotech-lab-main"
        legacy.mkdir()
        (legacy / "sessions.json").write_text(FAKE_SESSIONS_JSON,
                                              encoding="utf-8")
        (legacy / "keep.py").write_text("x = 1\n", encoding="utf-8")
        out = tmp_path / builder.ARCHIVE_NAME

        assert builder.main(root=tmp_path, out=out) == 0
        _, _, refused = builder.collect_files(tmp_path)
        assert any("biotech-lab-main/sessions.json" in r for r in refused)

        with zipfile.ZipFile(out) as z:
            names = z.namelist()
        assert not [n for n in names if "sessions.json" in n]
        # The rest of the subtree is still archived: sanitation removes the
        # record, not the surrounding source.
        assert any(n.endswith("biotech-lab-main/keep.py") for n in names)

    def test_machine_config_is_reported_as_refused(self, tmp_path):
        _minimal_tree(tmp_path)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "settings.local.json").write_text(
            f'{{"path": "{FAKE_HOME_PATH}"}}', encoding="utf-8")
        _, _, refused = builder.collect_files(tmp_path)
        assert any(".claude" in r for r in refused)

    def test_machine_config_is_dropped_rather_than_aborting(self, tmp_path):
        """`.claude/` is not descended into, so it cannot reach the manifest.

        Excluded rather than fatal on purpose: it is present on every
        developer's machine and is not the operator's mistake to fix.
        """
        _minimal_tree(tmp_path)
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "settings.local.json").write_text(
            f'{{"path": "{FAKE_HOME_PATH}"}}', encoding="utf-8")
        out = tmp_path / builder.ARCHIVE_NAME
        assert builder.main(root=tmp_path, out=out) == 0
        with zipfile.ZipFile(out) as z:
            assert not [n for n in z.namelist() if ".claude" in n]

    @pytest.mark.parametrize("content", [
        f"stray token {FAKE_SESSION_TOKEN}\n",
        f'{{"password": "{FAKE_SHA256}"}}\n',
        f"mail {FAKE_PERSONAL_EMAIL}\n",
        f'path = "{FAKE_HOME_PATH}"\n',
    ])
    def test_sensitive_content_in_an_ordinary_file_aborts_it(self, tmp_path,
                                                             content):
        """The half a denylist cannot do."""
        _minimal_tree(tmp_path)
        (tmp_path / "docs" / "notes.md").write_text(content, encoding="utf-8")
        out = tmp_path / builder.ARCHIVE_NAME
        assert builder.main(root=tmp_path, out=out) == 1
        assert not out.exists()

    def test_a_tampered_archive_fails_verification_and_is_deleted(self,
                                                                 tmp_path):
        """Post-build verification reads the artefact, not the manifest.

        Simulates the case the manifest cannot see: the written zip contains
        something the file list never did.
        """
        _minimal_tree(tmp_path)
        out = tmp_path / builder.ARCHIVE_NAME
        assert builder.main(root=tmp_path, out=out) == 0

        with zipfile.ZipFile(out, "a") as z:
            z.writestr(f"{builder.PREFIX}/sessions.json", FAKE_SESSIONS_JSON)
        problems = builder.verify_archive(out)
        assert problems, "verification missed a smuggled session record"
        assert any("sessions.json" in p for p in problems)

    def test_verification_also_reads_content_not_only_names(self, tmp_path):
        _minimal_tree(tmp_path)
        out = tmp_path / builder.ARCHIVE_NAME
        assert builder.main(root=tmp_path, out=out) == 0

        with zipfile.ZipFile(out, "a") as z:
            z.writestr(f"{builder.PREFIX}/docs/innocent.md",
                       f"leaked: {FAKE_SESSION_TOKEN}\n")
        assert builder.verify_archive(out), (
            "verification checked filenames only")

    def test_a_clean_archive_verifies_clean(self, tmp_path):
        _minimal_tree(tmp_path)
        out = tmp_path / builder.ARCHIVE_NAME
        assert builder.main(root=tmp_path, out=out) == 0
        assert builder.verify_archive(out) == []


# ===========================================================================
# 4. The shipped archive itself
# ===========================================================================


@pytest.mark.skipif(not ARCHIVE.exists(),
                    reason="archive not built; run make_readiness_archive.py")
class TestTheShippedArchive:
    """Assertions against the artefact that would actually be shared."""

    @pytest.fixture(scope="class")
    def names(self):
        with zipfile.ZipFile(ARCHIVE) as z:
            return z.namelist()

    def test_it_verifies_clean(self):
        """The whole sanitation contract, run against the real archive."""
        assert builder.verify_archive(ARCHIVE) == []

    @pytest.mark.parametrize("denied", [
        "sessions.json", "users.json", ".claude/", "settings.local.json",
    ])
    def test_the_named_leaks_are_gone(self, names, denied):
        assert not [n for n in names if denied in n]

    def test_no_database_or_env_file(self, names):
        assert not [n for n in names
                    if n.endswith((".db", ".sqlite", ".sqlite3"))
                    or n.rsplit("/", 1)[-1] == ".env"]

    def test_no_session_token_anywhere_in_it(self):
        """Scanned across every text entry, not just the obvious files."""
        pattern = re.compile(r"\btoken_[A-Za-z0-9.\-]+_\d{6,}\b")
        assert self._content_hits(pattern) == []

    def test_no_password_hash_anywhere_in_it(self):
        pattern = re.compile(
            r'(?i)"?\b(password|password_hash|passwd)\b"?\s*[:=]\s*'
            r'[\'"][A-Fa-f0-9]{32,}[\'"]')
        assert self._content_hits(pattern) == []

    def test_no_personal_mailbox_anywhere_in_it(self):
        pattern = re.compile(
            r"(?i)\b[A-Za-z0-9._%+-]+@(?:gmail|outlook|hotmail|yahoo|icloud"
            r"|protonmail|proton\.me|aol|gmx|yandex)\.[A-Za-z.]{2,}\b")
        assert self._content_hits(pattern) == []

    def test_no_home_directory_path_anywhere_in_it(self):
        pattern = re.compile(
            r"(?i)(?:[A-Za-z]:\\{1,2}Users\\{1,2}|/home/|/Users/)"
            r"[A-Za-z0-9._-]{2,}[\\/]")
        assert self._content_hits(pattern) == []

    @staticmethod
    def _content_hits(pattern: re.Pattern[str]) -> list[str]:
        """Every entry matching, minus the two self-documenting exemptions."""
        hits: list[str] = []
        with zipfile.ZipFile(ARCHIVE) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = info.filename.rsplit("/", 1)[-1]
                if name in builder.SCAN_EXEMPT:
                    continue
                if pathlib.Path(name).suffix.lower() not in builder.TEXT_SUFFIXES:
                    continue
                text = z.read(info).decode("utf-8", errors="ignore")
                for match in pattern.finditer(text):
                    if builder.allowlist_reason(info.filename,
                                                "Session token key"):
                        continue
                    hits.append(f"{info.filename}: {match.group(0)[:24]}")
        return hits

    @pytest.fixture(scope="class")
    def readme(self):
        with zipfile.ZipFile(ARCHIVE) as z:
            return z.read(
                f"{builder.PREFIX}/README-ARCHIVE.md").decode("utf-8")

    def test_the_readme_names_every_detector_the_scanner_runs(self, readme):
        """No claimed guarantee may be missing, and none may be invented.

        The README's lists are generated from the builder's constants, so this
        is really a test that the generation is wired up — but it is the claim
        a reader relies on, and it is worth asserting directly.
        """
        labels_ = [label for label, _ in builder.SECRET_PATTERNS]
        labels_.append(builder.KNOWN_CREDENTIAL_LABEL)
        for label in labels_:
            assert label in readme, f"README omits the {label!r} detector"

    def test_the_readme_names_every_denied_file(self, readme):
        for name in builder.DENY_FILENAMES:
            assert name in readme, f"README omits denied file {name!r}"

    def test_the_readme_names_every_machine_config_directory(self, readme):
        for name in builder.MACHINE_CONFIG_DIRS:
            assert name in readme, f"README omits {name!r}"

    def test_the_readme_states_the_limits_of_the_guarantee(self, readme):
        """An overstated sanitation notice is worse than none: it is trusted."""
        assert "does NOT guarantee" in readme
        for limit in ("text files only", "and **no others**",
                      "no detector matched", "allowlisted"):
            assert limit in readme, limit

    def test_the_readme_claims_no_default_credential(self, readme):
        """The exact sentence, verbatim.

        Asserted word for word because it is the claim a reader relies on, and
        a paraphrase would let its scope drift — "no password" and "no
        operational, default, provisioning, or walkthrough password" promise
        different things, and only the second is true.
        """
        assert (
            "No operational, default, provisioning, or walkthrough password "
            "appears in\nthis archive. Fictional test-only values may appear "
            "in isolated automated\ntests."
        ) in readme
        assert "there is no default credential" in readme.lower()

    def test_the_readme_qualification_is_accurate(self, readme):
        """The archive really does still contain test-only fixture values.

        The sentence admits them. If they were gone the sentence would be
        needlessly weak; while they are here it must stay.
        """
        assert "isolated automated" in readme
        # The allowlist records exactly those fixtures, with reasons.
        fixture_files = {suffix for suffix, _, _ in builder.ALLOWLIST}
        assert any("test" in f for f in fixture_files)

    def test_the_readme_does_not_quote_a_credential(self, readme):
        """The document explaining the policy must not violate it.

        An earlier draft quoted the one allowlisted token verbatim, and the
        post-build verification caught it and deleted the archive.
        """
        assert builder.scan_text(readme, "README-ARCHIVE.md",
                                 "README-ARCHIVE.md", []) == []

    def test_the_project_source_is_still_there(self, names):
        """Sanitation that removed the software would also pass every test above."""
        for required in (
            "nanobio_studio_backend/nanobio_studio/app/science/rules.py",
            "nanobio_studio_backend/nanobio_studio/app/science/statuses.py",
            "docs/SCIENTIFIC_READINESS.md",
            "tests/test_phase1_defect_corrections.py",
            "frontend/src/pages/readiness/ScientificReadinessPage.tsx",
        ):
            assert any(n.endswith(required) for n in names), required


# ===========================================================================
# 5. The source tree itself carries no credentials
# ===========================================================================


def _tracked_text_files():
    """Project text files, excluding vendored and snapshot trees."""
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if parts & builder.EXCLUDE_DIRS or any(
                builder.VENV_RE.match(p) for p in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".mjs", ".js", ".ts", ".tsx",
                                       ".md", ".json", ".yml", ".yaml"}:
            continue
        yield path


class TestTheSourceTreeIsClean:
    """Asserted over the working tree, not only over the archive.

    The archive is built from the tree. Catching a credential at packaging time
    is the last line of defence, not the place to rely on — by then it is
    already committed.
    """

    def test_no_known_default_credential_anywhere(self):
        """Consults the same ALLOWLIST the archive builder does.

        It did not, and the two therefore disagreed about what counts as a
        finding: the builder would pass a file the test failed, which is the
        worst of both — a check that blocks work without blocking a release.
        An allowlisted entry still has to carry a written reason.
        """
        offenders = []
        for path in _tracked_text_files():
            if path.name in builder.SCAN_EXEMPT:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if not builder.find_known_credentials(text):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if builder.allowlist_reason(rel, builder.KNOWN_CREDENTIAL_LABEL):
                continue
            offenders.append(str(path.relative_to(REPO_ROOT)))
        assert offenders == [], f"known default credentials in: {offenders}"

    def test_the_walkthroughs_carry_no_credentials(self):
        """Every walkthrough reads its accounts from the environment."""
        scripts = sorted((REPO_ROOT / "frontend").glob("*walkthrough.mjs"))
        scripts = [p for p in scripts
                   if p.name != "walkthrough-credentials.mjs"]
        # Fifteen after the candidate-version, notification, and platform-wide
        # mobile acceptance passes. Asserted as an exact count so a new script
        # cannot be added without its credentials being checked here too —
        # which is exactly what this caught when the account walkthrough
        # arrived.
        assert len(scripts) == 15, [p.name for p in scripts]
        for path in scripts:
            text = path.read_text(encoding="utf-8")
            assert "walkthroughCredentials()" in text, path.name
            assert "const PASS = '" not in text, path.name
            assert "const USER = '" not in text, path.name

            # The REPO-RELATIVE path, not the bare filename.
            #
            # `scan_text` consults the same ALLOWLIST the release build uses,
            # but it matches entries against the path it is given — so passing
            # `path.name` meant no entry could ever match and this test
            # disagreed with the build about what counts as a finding. That is
            # the worst kind of check: it blocks work without blocking a
            # release. The sibling test above learned this; this one had not.
            rel = path.relative_to(REPO_ROOT).as_posix()
            findings = builder.scan_text(text, rel, path.name, [])
            assert findings == [], (path.name, findings)

    def test_the_registry_walkthrough_reads_its_reviewer_from_the_environment(
            self):
        """The second account is what makes the independence rule testable.

        It must come from the environment like the first: a hard-coded
        reviewer would be a working credential in a committed file, and the
        whole point of the account is that it can approve real records.
        """
        script = (REPO_ROOT / "frontend"
                  / "registry-walkthrough.mjs").read_text(encoding="utf-8")
        assert "process.env.NANOBIO_REVIEWER_USER" in script
        assert "process.env.NANOBIO_REVIEWER_PASSWORD" in script
        assert not re.search(
            r"NANOBIO_REVIEWER_(USER|PASSWORD)\s*(\?\?|\|\|)\s*['\"]",
            script), "the reviewer credentials must have no fallback default"
        assert builder.scan_text(script, "registry-walkthrough.mjs",
                                 "registry-walkthrough.mjs", []) == []

    def test_the_organization_walkthrough_reads_all_three_from_the_environment(
            self):
        """Three accounts, none of them embedded.

        The self-escalation bar can only be exercised with a second account
        and the invitation flow with a third, so this script needs more
        credentials than any other — which is exactly why none of them may be
        written down here.
        """
        script = (REPO_ROOT / "frontend"
                  / "organization-walkthrough.mjs").read_text(encoding="utf-8")
        for name in ("NANOBIO_ORG_ADMIN_USER", "NANOBIO_ORG_ADMIN_PASSWORD",
                     "NANOBIO_ORG_NEWCOMER_USER",
                     "NANOBIO_ORG_NEWCOMER_PASSWORD",
                     "NANOBIO_ORG_NEWCOMER_EMAIL"):
            assert f"process.env.{name}" in script, name
            assert not re.search(
                rf"{name}\s*(\?\?|\|\|)\s*['\"]", script), (
                f"{name} must have no fallback default")
        assert builder.scan_text(script, "organization-walkthrough.mjs",
                                 "organization-walkthrough.mjs", []) == []

    def test_the_report_walkthrough_reads_all_three_from_the_environment(self):
        """Three accounts across two organizations, none of them embedded.

        This script uploads a real document and then tries to reach it from
        elsewhere, so it needs more access than any other walkthrough — which
        is exactly why none of its credentials may be written down.
        """
        script = (REPO_ROOT / "frontend"
                  / "report-isolation-walkthrough.mjs").read_text(
                      encoding="utf-8")
        for name in ("NANOBIO_REPORT_OTHER_USER",
                     "NANOBIO_REPORT_OTHER_PASSWORD",
                     "NANOBIO_REPORT_ADMIN_USER",
                     "NANOBIO_REPORT_ADMIN_PASSWORD"):
            assert f"process.env.{name}" in script, name
            assert not re.search(
                rf"{name}\s*(\?\?|\|\|)\s*['\"]", script), (
                f"{name} must have no fallback default")
        assert builder.scan_text(script, "report-isolation-walkthrough.mjs",
                                 "report-isolation-walkthrough.mjs", []) == []

    def test_the_attachment_walkthrough_reads_its_accounts_from_the_env(self):
        """Four accounts across two organizations, none of them embedded."""
        script = (REPO_ROOT / "frontend"
                  / "attachment-storage-walkthrough.mjs").read_text(
                      encoding="utf-8")
        for name in ("NANOBIO_ATTACH_OTHER_USER",
                     "NANOBIO_ATTACH_OTHER_PASSWORD",
                     "NANOBIO_ATTACH_ADMIN_USER",
                     "NANOBIO_ATTACH_ADMIN_PASSWORD",
                     "NANOBIO_ATTACH_OWNER_USER",
                     "NANOBIO_ATTACH_OWNER_PASSWORD"):
            assert f"process.env.{name}" in script, name
            assert not re.search(
                rf"{name}\s*(\?\?|\|\|)\s*['\"]", script), (
                f"{name} must have no fallback default")
        assert builder.scan_text(script, "attachment-storage-walkthrough.mjs",
                                 "attachment-storage-walkthrough.mjs",
                                 []) == []

    def test_the_credentials_module_supplies_no_default(self):
        """A fallback default would be the same defect with an extra step."""
        module = (REPO_ROOT / "frontend"
                  / "walkthrough-credentials.mjs").read_text(encoding="utf-8")
        assert "NANOBIO_WALKTHROUGH_USER" in module
        assert "NANOBIO_WALKTHROUGH_PASSWORD" in module
        # No `?? 'something'` or `|| 'something'` fallback on the env reads.
        assert not re.search(r"process\.env\[[^\]]+\]\s*(\?\?|\|\|)\s*['\"]",
                             module)
        assert "process.exit(2)" in module

    def test_the_stray_root_file_is_gone(self):
        """`%F` — 312 bytes of UTF-16 Streamlit fragment from a shell mishap.

        Named in docs/CURRENT_APPLICATION_AUDIT.md as a stray file. It carried
        no secret; it was unexplained content in a source archive, which is its
        own kind of problem.
        """
        assert not (REPO_ROOT / "%F").exists()

    def test_the_admin_script_rejects_the_retired_shape(self):
        """The denylist is a rule, so it needs no literal to reject one."""
        sys.path.insert(0, str(REPO_ROOT / "nanobio_studio_backend"))
        source = (REPO_ROOT / "nanobio_studio_backend" / "scripts"
                  / "create_admin.py").read_text(encoding="utf-8")
        assert "_WORD_THEN_DIGITS" in source
        pattern = re.compile(r"^[A-Za-z]+\d+$")
        for stem in ("admin", "science", "view", "password"):
            assert pattern.match(stem + "123"), stem
        # And it must not reject a properly generated password.
        assert not pattern.match("k3Jx-9vQm_2LpZ")


# ===========================================================================
# 6. This file's own hygiene
# ===========================================================================


def test_fixtures_are_synthetic():
    """The fixtures above must be invented, not copied from the real leak.

    This file is exempt from the content scan, so a real token pasted here
    would ship unexamined. The exemption is only safe while the values are
    made up — which is what this asserts, by requiring they appear nowhere
    else in the tree.
    """
    this = pathlib.Path(__file__).resolve()
    for value in (FAKE_SESSION_TOKEN, FAKE_PERSONAL_EMAIL):
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file() or path.resolve() == this:
                continue
            if any(part in builder.EXCLUDE_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".json", ".md", ".ts",
                                           ".tsx", ".mjs"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            assert value not in text, (
                f"{value!r} also appears in {path}; it is not synthetic")


def test_the_exempt_list_stays_short():
    """Two files skip the content scan. Both are inspected and documented.

    A growing exemption list is how a scanner stops scanning.
    """
    assert builder.SCAN_EXEMPT == {"make_readiness_archive.py",
                                   "test_archive_sanitation.py"}


def test_every_allowlist_entry_carries_a_reason():
    """An exemption without a reason is indistinguishable from an oversight."""
    assert builder.ALLOWLIST
    for suffix, label, reason in builder.ALLOWLIST:
        assert suffix and label
        assert len(reason) > 60, (suffix, label)
        emitted_by_a_pattern = any(l == label for l, _ in builder.SECRET_PATTERNS)
        # `Known default credential` comes from `find_known_credentials`, a
        # hash-set check rather than a regex, so it is not in SECRET_PATTERNS.
        # It is still a label a detector emits — `scan_text` reports it — and
        # excluding it would mean the one detector with a curated list could
        # never be allowlisted, however good the reason.
        emitted_by_the_known_list = label == builder.KNOWN_CREDENTIAL_LABEL
        assert emitted_by_a_pattern or emitted_by_the_known_list, (
            f"{label!r} is allowlisted but no detector emits it")
