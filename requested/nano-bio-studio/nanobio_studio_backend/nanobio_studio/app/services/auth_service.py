"""Authentication business logic: login, logout, sessions, rate limiting, audit.

Kept out of the route layer so it is independently testable.

Security properties implemented here
------------------------------------
* Opaque, random session tokens; only the SHA-256 hash is stored.
* Absolute session expiry **and** idle timeout.
* Generic failure message -- never reveals whether a username exists.
* Timing equalisation on unknown usernames.
* Per-username and per-IP login rate limiting with lockout.
* Audit entries for success, failure, logout, expiry and rate limiting.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.core.security import (
    dummy_password_verify,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from nanobio_studio.app.db.auth_models import (
    AuthAuditLog,
    AuthEvent,
    User,
    UserRole,
    UserSession,
    utcnow,
)

# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

#: Absolute lifetime of a session, regardless of activity.
SESSION_ABSOLUTE_LIFETIME = timedelta(hours=8)

#: Idle timeout. Matches the legacy application's 30-minute policy.
SESSION_IDLE_TIMEOUT = timedelta(minutes=30)

#: Failed attempts allowed per (username, ip) before lockout.
MAX_FAILED_ATTEMPTS = 5

#: Lockout duration once the threshold is exceeded.
LOCKOUT_WINDOW = timedelta(minutes=15)

#: Rolling window in which failures accumulate.
ATTEMPT_WINDOW = timedelta(minutes=15)

#: Deliberately generic. Must not reveal whether the account exists.
GENERIC_LOGIN_FAILURE = "Invalid username or password."

SESSION_COOKIE_NAME = "nanobio_session"


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 401,
                 retry_after: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


@dataclass
class _Attempts:
    failures: list[float]
    locked_until: float | None = None


class LoginRateLimiter:
    """In-process login rate limiter.

    LIMITATION (documented): this is per-process memory. It resets on restart and
    is not shared across workers, so it is not sufficient for a multi-instance
    production deployment -- that needs Redis or a database-backed counter. It is
    nonetheless a real control for single-instance use and closes the legacy
    application's complete absence of any limit.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, _Attempts] = {}

    @staticmethod
    def _key(username: str, ip: str | None) -> str:
        return f"{(username or '').strip().lower()}|{ip or '-'}"

    def check(self, username: str, ip: str | None) -> None:
        """Raise AuthError if currently locked out."""
        bucket = self._buckets.get(self._key(username, ip))
        if bucket and bucket.locked_until and time.monotonic() < bucket.locked_until:
            remaining = int(bucket.locked_until - time.monotonic())
            raise AuthError(
                code="rate_limited",
                message=(
                    "Too many failed sign-in attempts. Try again in "
                    f"{max(1, remaining // 60)} minute(s)."
                ),
                status_code=429,
                retry_after=max(1, remaining),
            )

    def record_failure(self, username: str, ip: str | None) -> bool:
        """Record a failure. Returns True if this triggered a lockout."""
        key = self._key(username, ip)
        now = time.monotonic()
        bucket = self._buckets.setdefault(key, _Attempts(failures=[]))
        window = ATTEMPT_WINDOW.total_seconds()
        bucket.failures = [t for t in bucket.failures if now - t < window]
        bucket.failures.append(now)
        if len(bucket.failures) >= MAX_FAILED_ATTEMPTS:
            bucket.locked_until = now + LOCKOUT_WINDOW.total_seconds()
            bucket.failures.clear()
            return True
        return False

    def reset(self, username: str, ip: str | None) -> None:
        self._buckets.pop(self._key(username, ip), None)

    def clear(self) -> None:
        """Test helper."""
        self._buckets.clear()


rate_limiter = LoginRateLimiter()


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


async def record_audit(
    session: AsyncSession,
    event: AuthEvent,
    *,
    user_id: int | None = None,
    username_attempted: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    detail: str | None = None,
) -> None:
    session.add(AuthAuditLog(
        event=event,
        user_id=user_id,
        username_attempted=username_attempted,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
        detail=detail,
    ))
    await session.flush()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(
        select(User).where(User.username == (username or "").strip()))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    role: UserRole,
    email: str | None = None,
    full_name: str | None = None,
) -> User:
    """Create a user. The caller supplies the password; it is hashed immediately."""
    username = (username or "").strip()
    if len(username) < 3:
        raise ValueError("username must be at least 3 characters")
    if len(password or "") < 12:
        # Stronger than the legacy 6-character policy.
        raise ValueError("password must be at least 12 characters")
    if await get_user_by_username(session, username):
        raise ValueError(f"user {username!r} already exists")

    user = User(
        username=username,
        email=(email or None),
        full_name=(full_name or None),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------


async def authenticate(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, str, datetime]:
    """Verify credentials and open a session.

    Returns ``(user, raw_token, expires_at)``. The expiry is returned
    explicitly rather than read back off ``user.sessions``: traversing that
    relationship in async context triggers a lazy load outside the greenlet
    and raises MissingGreenlet.

    Raises AuthError with a generic message on any failure.
    """
    rate_limiter.check(username, ip_address)

    user = await get_user_by_username(session, username)

    if user is None:
        dummy_password_verify()  # equalise timing for unknown usernames
        locked = rate_limiter.record_failure(username, ip_address)
        await record_audit(
            session, AuthEvent.LOGIN_FAILURE,
            username_attempted=username, ip_address=ip_address,
            user_agent=user_agent, detail="unknown username")
        if locked:
            await record_audit(session, AuthEvent.RATE_LIMITED,
                               username_attempted=username, ip_address=ip_address,
                               user_agent=user_agent)
        raise AuthError("invalid_credentials", GENERIC_LOGIN_FAILURE)

    if not verify_password(password, user.password_hash) or not user.is_active:
        locked = rate_limiter.record_failure(username, ip_address)
        await record_audit(
            session, AuthEvent.LOGIN_FAILURE, user_id=user.id,
            username_attempted=username, ip_address=ip_address,
            user_agent=user_agent,
            detail="bad password" if user.is_active else "inactive account")
        if locked:
            await record_audit(session, AuthEvent.RATE_LIMITED, user_id=user.id,
                               username_attempted=username, ip_address=ip_address,
                               user_agent=user_agent)
        # Same message for a wrong password and a disabled account.
        raise AuthError("invalid_credentials", GENERIC_LOGIN_FAILURE)

    rate_limiter.reset(username, ip_address)

    token = generate_session_token()
    now = utcnow()
    expires_at = now + SESSION_ABSOLUTE_LIFETIME
    session.add(UserSession(
        token_hash=hash_session_token(token),
        user_id=user.id,
        created_at=now,
        last_activity_at=now,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
    ))
    user.last_login_at = now

    await record_audit(session, AuthEvent.LOGIN_SUCCESS, user_id=user.id,
                       username_attempted=username, ip_address=ip_address,
                       user_agent=user_agent)
    await session.flush()
    return user, token, expires_at


async def resolve_session(session: AsyncSession, token: str | None
                          ) -> tuple[User, UserSession] | None:
    """Validate a session token. Returns None when absent, invalid or expired.

    Enforces both absolute expiry and idle timeout, and refreshes activity on
    every successful resolution (a sliding window within the absolute lifetime).
    """
    if not token:
        return None

    result = await session.execute(
        select(UserSession).where(
            UserSession.token_hash == hash_session_token(token)))
    user_session = result.scalar_one_or_none()
    if user_session is None:
        return None

    now = utcnow()

    def _aware(dt: datetime) -> datetime:
        # SQLite round-trips naive datetimes; normalise before comparing.
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    expired = _aware(user_session.expires_at) <= now
    idle = (now - _aware(user_session.last_activity_at)) > SESSION_IDLE_TIMEOUT

    if expired or idle:
        user_id = user_session.user_id
        await session.delete(user_session)
        await record_audit(session, AuthEvent.SESSION_EXPIRED, user_id=user_id,
                           detail="absolute expiry" if expired else "idle timeout")
        await session.flush()
        return None

    user = await session.get(User, user_session.user_id)
    if user is None or not user.is_active:
        await session.delete(user_session)
        await session.flush()
        return None

    user_session.last_activity_at = now
    await session.flush()
    return user, user_session


async def logout(session: AsyncSession, token: str | None, *,
                 ip_address: str | None = None,
                 user_agent: str | None = None) -> bool:
    """Revoke a session server-side. Idempotent."""
    if not token:
        return False
    result = await session.execute(
        select(UserSession).where(
            UserSession.token_hash == hash_session_token(token)))
    user_session = result.scalar_one_or_none()
    if user_session is None:
        return False

    user_id = user_session.user_id
    await session.delete(user_session)
    await record_audit(session, AuthEvent.LOGOUT, user_id=user_id,
                       ip_address=ip_address, user_agent=user_agent)
    await session.flush()
    return True


async def purge_expired_sessions(session: AsyncSession) -> int:
    """Housekeeping: drop sessions past their absolute expiry."""
    result = await session.execute(
        delete(UserSession).where(UserSession.expires_at <= utcnow()))
    return result.rowcount or 0
