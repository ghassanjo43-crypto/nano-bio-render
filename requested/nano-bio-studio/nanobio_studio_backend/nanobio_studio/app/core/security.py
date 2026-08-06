"""Password hashing and session-token primitives.

Design notes
------------
* **Passwords** are hashed with bcrypt (already a declared project dependency).
  Plaintext is never stored, logged, or returned.
* **Session tokens** are opaque, cryptographically random values. Only the
  SHA-256 *hash* is persisted, so a database disclosure does not yield usable
  session credentials. This deliberately replaces the legacy
  ``token_{username}_{unix_seconds}`` scheme, which was forgeable.
* Tokens travel **only** in an HttpOnly cookie. Never in a URL, never in
  ``localStorage``, never readable by JavaScript.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt

#: Cost factor for bcrypt. 12 is a reasonable 2026 default for interactive login.
BCRYPT_ROUNDS = 12

#: Bytes of entropy in a session token before URL-safe encoding.
SESSION_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    """Hash a plaintext password. Returns a UTF-8 string safe for a TEXT column.

    Note the legacy application stored bcrypt output as BLOB in one place and
    TEXT in another (audit DEFECT: schema conflict). This layer commits to
    **TEXT** consistently and decodes on the way in.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    digest = bcrypt.hashpw(password.encode("utf-8"),
                           bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return digest.decode("utf-8")


def verify_password(password: str, password_hash: str | bytes | None) -> bool:
    """Constant-time-ish password check that never raises.

    Returns False for any malformed input rather than propagating, so a corrupt
    hash can never produce an exception that a caller might mistake for success.
    """
    if not password or not password_hash:
        return False
    try:
        if isinstance(password_hash, str):
            password_hash = password_hash.encode("utf-8")
        return bcrypt.checkpw(password.encode("utf-8"), password_hash)
    except (ValueError, TypeError):
        return False


def generate_session_token() -> str:
    """A new opaque session token. Never derived from user data."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """SHA-256 of a session token. Only this is stored server-side."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    """Constant-time comparison for token hashes."""
    return hmac.compare_digest(a, b)


def dummy_password_verify() -> None:
    """Burn roughly one bcrypt verification of time.

    Called when a username does not exist, so that a missing account and a wrong
    password take similar time. Without this, response timing reveals which
    usernames are registered.
    """
    verify_password(
        "timing-equalisation",
        "$2b$12$C6UzMDM.H6dfI/f/IKcEeO3Y.J1sHqE5oNQ5V0mFLtqUqxq0G0dGa",
    )
