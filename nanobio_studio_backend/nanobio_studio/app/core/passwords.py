"""Password hashing, verification, and the policy a password must satisfy.

Argon2id, and why bcrypt accounts are not invalidated
-----------------------------------------------------
New passwords are hashed with **Argon2id**: memory-hard, so a GPU or ASIC
attacker gains far less against it than against bcrypt, and the current
recommendation for interactive login.

Existing accounts are on bcrypt. Invalidating them would be the security
equivalent of solving a leak by demolishing the house: every user locked out,
every one of them driven through a reset flow at once, and an operator strongly
tempted to hand out passwords to get people working again. So verification
accepts either scheme, and a successful bcrypt login **rehashes to Argon2id in
place** — the one moment the plaintext is legitimately available. The migration
completes as people sign in, and ``password_algorithm`` on the account row
makes "how many are left" answerable without parsing every hash.

The bcrypt 72-byte trap
-----------------------
bcrypt silently truncates at 72 bytes. A 200-character passphrase and its first
72 bytes are the *same password* to it — which turns a user carefully choosing
a long passphrase into a user with a shorter one than they think. Argon2 has no
such limit, but the maximum below is enforced regardless: it bounds the work an
unauthenticated caller can make the server do, and one password rule that means
the same thing under both algorithms is easier to reason about than two.

What is deliberately absent
---------------------------
**Composition rules.** No "one uppercase, one digit, one symbol". They add
almost nothing to entropy and reliably produce ``Password1!`` — the rule is
what makes the choice predictable. Length and a rejection list do more.

**Security questions.** A second, weaker password whose answer is often public.

Nothing here logs, returns or stores a plaintext password, and no function
takes one that is not immediately hashed or verified.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

import bcrypt

__all__ = [
    "hash_password", "verify_password", "needs_rehash", "algorithm_of",
    "PasswordRejected", "check_password_policy",
    "MIN_PASSWORD_LENGTH", "MAX_PASSWORD_LENGTH",
    "generate_account_token", "hash_account_token", "tokens_equal",
    "ARGON2ID", "BCRYPT",
]

ARGON2ID = "argon2id"
BCRYPT = "bcrypt"

#: 12 characters. Long enough that a rejection list plus rate limiting is a
#: meaningful defence; short enough that people do not write it down.
MIN_PASSWORD_LENGTH = 12

#: 1024 characters. Not a security rule about the password — a bound on the
#: work an unauthenticated caller can ask the server to do. Argon2 on a
#: megabyte of input, once per request, is a denial-of-service primitive.
MAX_PASSWORD_LENGTH = 1024

#: Legacy bcrypt truncation point. Passwords longer than this were silently
#: shortened by bcrypt; recorded so the migration can be reasoned about.
BCRYPT_TRUNCATION_BYTES = 72

BCRYPT_ROUNDS = 12

#: Argon2id parameters. 64 MiB and three passes is a common 2026 interactive
#: setting: comfortably under a second on server hardware, and expensive enough
#: that offline cracking of a stolen table is a serious undertaking.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_KIB = 64 * 1024
ARGON2_PARALLELISM = 2

#: Common *bases*, not complete passwords.
#:
#: Checking whole strings does not work: the list would need `password1`,
#: `password12`, `password123`, `password1234` and every other suffix a person
#: reaches for when a length rule rejects the word alone. Padding a common word
#: with digits is exactly the behaviour a length rule produces, so the check
#: normalises first — trailing digits and punctuation are stripped, leetspeak is
#: folded back — and compares the base.
#:
#: A small embedded list, not a breach corpus. Two honest reasons: shipping
#: hundreds of megabytes of hashes into this repository is not proportionate,
#: and a list that is *present* is worth more than a service integration that
#: is planned. Extending it to a k-anonymity range query against a breach
#: service is recorded as deferred rather than implied to be here.
_COMMON_BASES = frozenset({
    "password", "passwd", "pass", "secret", "letmein", "welcome", "iloveyou",
    "admin", "administrator", "root", "guest", "test", "user", "login",
    "qwerty", "qwertyuiop", "asdfgh", "zxcvbn", "abc", "abcd", "abcdef",
    "monkey", "dragon", "football", "baseball", "sunshine", "princess",
    "trustno", "changeme", "changemenow", "default", "temporary", "temp",
    "nanobio", "nanobiostudio", "nanobio-studio", "nanoparticle",
    "correcthorsebatterystaple",
})

#: Folded before comparison, so `p@ssw0rd` and `password` are the same guess.
_LEET = str.maketrans({"@": "a", "4": "a", "3": "e", "1": "l", "0": "o",
                       "5": "s", "7": "t", "$": "s", "!": "i"})


#: Characters people append to satisfy a length rule.
_PADDING = "0123456789!?.,-_*#+=@$ "


def _password_base(password: str) -> str:
    """Reduce a password to the word somebody actually thought of.

    Order matters, and getting it wrong is silent. Folding leetspeak first
    turns the ``1234`` in ``password1234`` into ``l2ea`` — letters, no longer
    strippable — so the base came out as ``passwordl2ea`` and matched nothing.
    The padding therefore comes off first, then the fold, then any padding the
    fold exposed.
    """
    folded = password.strip().lower().rstrip(_PADDING)
    folded = folded.translate(_LEET).rstrip(_PADDING)
    # A single repeated character is its own base ("aaaaaaaaaaaa").
    if folded and len(set(folded)) == 1:
        return folded[0] * 3
    return folded


def _is_sequential(folded: str) -> bool:
    """Whether the whole string is one ascending or descending run.

    Catches "123456789012" and "abcdefghijkl", which satisfy a length rule and
    are among the first few thousand guesses in any dictionary attack.
    """
    if len(folded) < MIN_PASSWORD_LENGTH:
        return False
    deltas = {ord(b) - ord(a) for a, b in zip(folded, folded[1:])}
    return deltas <= {1} or deltas <= {-1}


class PasswordRejected(ValueError):
    """A password the policy will not accept. Carries a code and a reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class _Argon2:
    """Lazily constructed, so the module imports without argon2 installed."""

    @staticmethod
    def hasher():
        from argon2 import PasswordHasher
        return PasswordHasher(
            time_cost=ARGON2_TIME_COST,
            memory_cost=ARGON2_MEMORY_KIB,
            parallelism=ARGON2_PARALLELISM,
        )


def algorithm_of(password_hash: str | bytes | None) -> str | None:
    """Which scheme produced this hash, read from its own prefix."""
    if not password_hash:
        return None
    if isinstance(password_hash, bytes):
        password_hash = password_hash.decode("utf-8", "replace")
    if password_hash.startswith("$argon2"):
        return ARGON2ID
    if password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        return BCRYPT
    return None


def check_password_policy(password: str, *,
                          confirmation: str | None = None,
                          username: str | None = None,
                          email: str | None = None) -> None:
    """Raise :class:`PasswordRejected` unless the password is acceptable.

    Every message names what to change. "Password does not meet requirements"
    sends the user round the loop guessing, and the guesses converge on
    ``Password1!``.
    """
    if not isinstance(password, str) or not password:
        raise PasswordRejected("password_required", "Enter a password.")

    if confirmation is not None and password != confirmation:
        raise PasswordRejected(
            "password_mismatch",
            "The two passwords do not match. Retype them.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordRejected(
            "password_too_short",
            f"Use at least {MIN_PASSWORD_LENGTH} characters. Length is what "
            f"makes a password hard to guess; a short one with a symbol in it "
            f"is not.")

    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordRejected(
            "password_too_long",
            f"Use at most {MAX_PASSWORD_LENGTH} characters.")

    folded = password.strip().lower()
    base = _password_base(password)
    # A repeated single character, whatever it is: "aaaaaaaaaaaa" passes a
    # length rule and has almost no entropy.
    repeated = len(set(folded)) <= 2 and len(folded) >= MIN_PASSWORD_LENGTH
    # A run of consecutive digits or letters: "123456789012", "abcdefghijkl".
    sequential = _is_sequential(folded)

    # An empty base means the whole password was padding — digits and
    # punctuation and nothing else. "123456789012" reduces to nothing, and a
    # digit string is the shortest search space there is.
    digits_only = base == ""

    if base in _COMMON_BASES or repeated or sequential or digits_only:
        raise PasswordRejected(
            "password_too_common",
            "That password is built from a word or pattern that appears on "
            "lists of commonly used passwords — adding digits to the end does "
            "not change that, because it is the first thing an attacker tries. "
            "Choose something unrelated.")

    # An optional local breach corpus, when one is configured. Checked after
    # the cheap rules so a password that fails on length never causes a file
    # seek, and last among the disqualifying checks because it is the only one
    # that touches the filesystem.
    #
    # Imported here rather than at module scope: this module is imported by
    # `core.security`, which the legacy-boundary test parses, and a top-level
    # import would make the corpus machinery load for every password hash even
    # where no corpus exists.
    from nanobio_studio.app.core.breach_corpus import active_corpus

    corpus = active_corpus()
    if corpus is not None:
        try:
            compromised, occurrences = corpus.is_compromised(password)
        except OSError:
            # A corpus that became unreadable after startup must not block
            # somebody from setting a password. It is verified at startup, so
            # this is a disk fault rather than a configuration error, and the
            # embedded list still applies.
            compromised, occurrences = False, 0
        if compromised:
            raise PasswordRejected(
                "password_compromised",
                f"That password appears in a public list of passwords exposed "
                f"in past data breaches (seen {occurrences:,} times), so it is "
                f"already in the dictionaries attackers try first. It may never "
                f"have been yours — but it has to be changed. Choose something "
                f"unrelated.")

    # A password containing the account name is the first guess after the
    # common list, and it is the one people reach for when hurried.
    for personal in (username, (email or "").split("@")[0] if email else None):
        if personal and len(personal) >= 4 and personal.lower() in folded:
            raise PasswordRejected(
                "password_contains_identity",
                "The password contains your username or email address, which "
                "makes it guessable by anyone who knows either.")


def hash_password(password: str) -> str:
    """Hash with Argon2id. Falls back to bcrypt only if argon2 is unavailable.

    The fallback exists so a deployment missing the dependency degrades to the
    previous scheme rather than refusing every password change — but it records
    which was used, so the gap is visible rather than silent.
    """
    if not isinstance(password, str) or not password:
        raise PasswordRejected("password_required", "Enter a password.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordRejected(
            "password_too_long",
            f"Use at most {MAX_PASSWORD_LENGTH} characters.")
    try:
        return _Argon2.hasher().hash(password)
    except ImportError:  # pragma: no cover - dependency present in this repo
        return bcrypt.hashpw(password.encode("utf-8"),
                             bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
                             ).decode("utf-8")


def verify_password(password: str, password_hash: str | bytes | None) -> bool:
    """Check a password against either scheme. Never raises.

    Returns False for any malformed input rather than propagating, so a corrupt
    stored hash can never produce an exception a caller might mistake for
    success. Both libraries compare in constant time internally; neither result
    is branched on before the comparison completes.
    """
    if not password or not password_hash:
        return False
    if isinstance(password_hash, bytes):
        password_hash = password_hash.decode("utf-8", "replace")

    algorithm = algorithm_of(password_hash)
    try:
        if algorithm == ARGON2ID:
            from argon2.exceptions import VerificationError, VerifyMismatchError
            try:
                return bool(_Argon2.hasher().verify(password_hash, password))
            except (VerifyMismatchError, VerificationError):
                return False
        if algorithm == BCRYPT:
            # bcrypt truncates at 72 bytes; passing more raises on some
            # versions. Truncating here reproduces exactly what the stored hash
            # was computed over, so an existing password keeps working.
            candidate = password.encode("utf-8")[:BCRYPT_TRUNCATION_BYTES]
            return bcrypt.checkpw(candidate, password_hash.encode("utf-8"))
    except (ValueError, TypeError, ImportError):
        return False
    return False


def needs_rehash(password_hash: str | bytes | None) -> bool:
    """Whether a verified password should be re-hashed on this sign-in.

    True for every bcrypt hash — the migration — and for an Argon2 hash whose
    parameters are weaker than the current settings, so raising the cost later
    is a configuration change that applies itself.
    """
    algorithm = algorithm_of(password_hash)
    if algorithm is None or algorithm == BCRYPT:
        return True
    if isinstance(password_hash, bytes):
        password_hash = password_hash.decode("utf-8", "replace")
    try:
        return bool(_Argon2.hasher().check_needs_rehash(password_hash))
    except Exception:  # noqa: BLE001 — a rehash decision must not break login
        return False


def dummy_password_verify() -> None:
    """Burn roughly one verification of time.

    Called when a username does not exist, so a missing account and a wrong
    password take comparable time. Without it, response timing reveals which
    usernames are registered — and an enumeration oracle that works by stopwatch
    is not closed by a generic error message.
    """
    verify_password(
        "timing-equalisation",
        "$2b$12$C6UzMDM.H6dfI/f/IKcEeO3Y.J1sHqE5oNQ5V0mFLtqUqxq0G0dGa",
    )


# ---------------------------------------------------------------------------
# Account tokens
# ---------------------------------------------------------------------------

#: 32 bytes — 256 bits before encoding. Guessing is not a strategy against it,
#: and it comes from `secrets`, not `random`, which is seeded predictably.
ACCOUNT_TOKEN_BYTES = 32


def generate_account_token() -> str:
    return secrets.token_urlsafe(ACCOUNT_TOKEN_BYTES)


def hash_account_token(token: str) -> str:
    """SHA-256, hex. Only this is stored.

    A fast hash rather than a password hash, deliberately: the token has 256
    bits of entropy from a CSPRNG, so there is nothing to brute-force and
    nothing a slow hash would buy. What matters is that the stored form cannot
    be replayed, and a digest achieves that.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    """Constant-time comparison for token digests."""
    return hmac.compare_digest(a or "", b or "")
