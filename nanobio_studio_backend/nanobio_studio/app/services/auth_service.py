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

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.core.rate_limit import MemoryRateLimitBackend
from nanobio_studio.app.core.passwords import (
    algorithm_of,
    check_password_policy,
    dummy_password_verify,
    hash_password,
    needs_rehash,
    verify_password,
)
from nanobio_studio.app.core.security import (
    generate_session_token,
    hash_session_token,
)
from nanobio_studio.app.db.auth_models import (
    SIGN_IN_STATES,
    AccountState,
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


class LoginRateLimiter:
    """Login lockout policy, on top of a pluggable counter store.

    The *policy* lives here — threshold, window, lockout length, and the key it
    counts against. Where the counters are kept lives in ``core.rate_limit``,
    because that is the part that has to change for a multi-instance
    deployment and the part that was previously an undocumented dictionary.

    The key is ``(account, address)``, deliberately. Keying on the account
    alone would let anybody who knows a username lock its owner out from
    anywhere — turning a brute-force control into a denial-of-service tool
    aimed at a named person. Keying on the address alone would let one office
    behind a NAT lock out its own colleagues. The pair costs an attacker a new
    address per five attempts and costs a legitimate user nothing.
    """

    def __init__(self, backend=None) -> None:
        self._backend = backend or MemoryRateLimitBackend()

    @property
    def backend(self):
        return self._backend

    def use_backend(self, backend) -> None:
        """Swap the store. Called once at startup, and by tests."""
        self._backend = backend

    @staticmethod
    def _key(username: str, ip: str | None) -> str:
        return f"{(username or '').strip().lower()}|{ip or '-'}"

    def check(self, username: str, ip: str | None) -> None:
        """Raise AuthError if currently locked out."""
        remaining = self._backend.locked_for(self._key(username, ip))
        if remaining > 0:
            raise AuthError(
                code="rate_limited",
                message=(
                    "Too many failed sign-in attempts. Try again in "
                    f"{max(1, int(remaining) // 60)} minute(s)."
                ),
                status_code=429,
                retry_after=max(1, int(remaining)),
            )

    def record_failure(self, username: str, ip: str | None) -> bool:
        """Record a failure. Returns True if this triggered a lockout."""
        return self._backend.record_failure(
            self._key(username, ip),
            window_s=ATTEMPT_WINDOW.total_seconds(),
            threshold=MAX_FAILED_ATTEMPTS,
            lockout_s=LOCKOUT_WINDOW.total_seconds())

    def reset(self, username: str, ip: str | None) -> None:
        self._backend.reset(self._key(username, ip))

    def clear(self) -> None:
        """Test helper."""
        self._backend.clear()

    def health(self) -> dict:
        return self._backend.health()


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
    password: str | None = None,
    role: UserRole,
    email: str | None = None,
    full_name: str | None = None,
) -> User:
    """Create a user.

    ``password`` is now **optional**, and that is the point of the change.

    An administrator creating an account for somebody else must not choose that
    person password — so they call this without one, and the account is created
    in ``PENDING_ACTIVATION`` with an unusable hash. It can hold memberships and
    appear in a roster; it cannot sign in until its owner sets a password
    through an activation link.

    The unusable hash is a fixed sentinel rather than a random password. A
    random one would be a real credential that briefly existed, and something
    would eventually log it. A sentinel that no input can hash to cannot be
    guessed, because there is nothing to guess.
    """
    username = (username or "").strip()
    if len(username) < 3:
        raise ValueError("username must be at least 3 characters")
    if await get_user_by_username(session, username):
        raise ValueError(f"user {username!r} already exists")

    if password is None:
        state = AccountState.PENDING_ACTIVATION
        # Not a valid hash for any algorithm, so `verify_password` returns
        # False for every input without needing a special case at the call
        # site. There is no plaintext that produces it.
        password_hash = "!no-password-set"
        algorithm = None
    else:
        check_password_policy(password, username=username, email=email)
        state = AccountState.ACTIVE
        password_hash = hash_password(password)
        algorithm = algorithm_of(password_hash)

    user = User(
        username=username,
        email=(email or None),
        full_name=(full_name or None),
        password_hash=password_hash,
        password_algorithm=algorithm,
        password_changed_at=utcnow() if password is not None else None,
        role=role,
        state=state,
        is_active=state is AccountState.ACTIVE,
        must_set_password=password is None,
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
    previous_token: str | None = None,
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

    signed_in_state = getattr(user, "state", None)
    state_ok = (signed_in_state in SIGN_IN_STATES
                if signed_in_state is not None else user.is_active)

    if not verify_password(password, user.password_hash) or not state_ok:
        locked = rate_limiter.record_failure(username, ip_address)
        await record_audit(
            session, AuthEvent.LOGIN_FAILURE, user_id=user.id,
            username_attempted=username, ip_address=ip_address,
            user_agent=user_agent,
            # The detail is for an investigator reading the trail; the caller
            # gets the same generic message either way.
            detail=("bad password" if state_ok
                    else f"account state {getattr(signed_in_state, 'value', 'inactive')}"))
        if locked:
            await record_audit(session, AuthEvent.RATE_LIMITED, user_id=user.id,
                               username_attempted=username, ip_address=ip_address,
                               user_agent=user_agent)
        # Same message for a wrong password and a disabled account.
        raise AuthError("invalid_credentials", GENERIC_LOGIN_FAILURE)

    rate_limiter.reset(username, ip_address)

    now = utcnow()

    # Rehash on login, while the plaintext is legitimately in hand.
    #
    # This is the whole bcrypt -> Argon2id migration: it completes as people
    # sign in, nobody is locked out, and no operator is tempted to hand out
    # passwords to get everyone working again. Deliberately after the password
    # has been verified, so a wrong guess never causes a write.
    if needs_rehash(user.password_hash):
        previous = algorithm_of(user.password_hash) or "unknown"
        user.password_hash = hash_password(password)
        user.password_algorithm = algorithm_of(user.password_hash)
        await record_audit(session, AuthEvent.PASSWORD_REHASHED,
                           user_id=user.id, ip_address=ip_address,
                           detail=f"{previous} -> {user.password_algorithm}")

    # Session fixation: any session presented WITH the login request is
    # discarded before a new one is issued.
    #
    # Without this, an attacker who can set a cookie in the victim's browser
    # (a shared machine, a subdomain, a network position) waits for them to
    # sign in and then holds a session that is now authenticated as them. The
    # defence is that the identifier the browser arrives with is never the
    # identifier it leaves with.
    rotated = 0
    if previous_token:
        rotated = await _discard_session(session, previous_token)
        if rotated:
            await record_audit(session, AuthEvent.SESSION_ROTATED,
                               user_id=user.id, ip_address=ip_address,
                               detail="session identifier rotated at sign-in")

    token = generate_session_token()
    token_hash = hash_session_token(token)
    expires_at = now + SESSION_ABSOLUTE_LIFETIME
    session.add(UserSession(
        token_hash=token_hash,
        # Non-secret, so a screen can name a session and an audit line can
        # reference one without either holding a credential.
        handle=token_hash[:12],
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


async def _discard_session(session: AsyncSession, token: str) -> int:
    """Remove a session by its raw token. Used for rotation at sign-in."""
    row = (await session.execute(
        select(UserSession).where(
            UserSession.token_hash == hash_session_token(token))
    )).scalar_one_or_none()
    if row is None:
        return 0
    await session.delete(row)
    await session.flush()
    return 1


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
    # The account state is re-read here, on every request, rather than trusted
    # from anything cached with the session. A suspension, a disablement or a
    # deletion must be refused on the NEXT request, not when a cache happens to
    # expire.
    state = getattr(user, "state", None)
    usable = (state in SIGN_IN_STATES if state is not None
              else bool(user and user.is_active))
    if user is None or not usable:
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
