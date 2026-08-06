"""Session-token primitives, and re-exports of the one password module.

Why the password functions are re-exports and not implementations
-----------------------------------------------------------------
There were two password implementations: this module hashed with bcrypt, and
nothing stopped a caller importing either it or something else. Two answers to
"is this the right password" is one more than a system can safely have — the
day they disagree, one of them is accepting what the other refuses, and which
one a call site got depended on which import it happened to write.

So there is now exactly one, in ``core/passwords``: Argon2id for new passwords,
bcrypt still accepted for existing ones and rehashed on login. The names below
are kept as re-exports so ``scripts/create_admin.py`` and anything else
importing from here keeps working *and* gets the authoritative behaviour —
rather than being quietly left on a second implementation nobody remembers.

Session tokens
--------------
Opaque, cryptographically random. Only the SHA-256 *hash* is persisted, so a
database disclosure does not yield usable session credentials. This replaced
the legacy ``token_{username}_{unix_seconds}`` scheme, which was forgeable by
anyone who could read a clock.

Tokens travel **only** in an HttpOnly cookie. Never in a URL, never in
``localStorage``, never readable by JavaScript.
"""

from __future__ import annotations

import hashlib
import secrets

# The authoritative password implementation. Re-exported, not reimplemented.
from nanobio_studio.app.core.passwords import (  # noqa: F401
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PasswordRejected,
    algorithm_of,
    check_password_policy,
    dummy_password_verify,
    hash_password,
    needs_rehash,
    tokens_equal,
    verify_password,
)

__all__ = [
    "hash_password", "verify_password", "needs_rehash", "algorithm_of",
    "check_password_policy", "PasswordRejected", "dummy_password_verify",
    "MIN_PASSWORD_LENGTH", "MAX_PASSWORD_LENGTH",
    "generate_session_token", "hash_session_token", "tokens_equal",
    "SESSION_TOKEN_BYTES",
]

#: Bytes of entropy in a session token before URL-safe encoding.
SESSION_TOKEN_BYTES = 32


def generate_session_token() -> str:
    """A new opaque session token. Never derived from user data."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """SHA-256 of a session token. Only this is stored server-side."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
