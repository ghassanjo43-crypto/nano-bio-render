"""SQLAlchemy models for authentication, sessions and the auth audit trail.

These are the **intended production models**, not a disposable local design. The
same declarative models run against SQLite locally and PostgreSQL in deployment;
only ``DATABASE_URL`` changes. Column types are chosen to be portable across
both.

Relationship to the legacy ``users.db``
---------------------------------------
This schema is *separate* and the legacy SQLite file is never read or written by
this code. Migrating legacy accounts is an explicit, manual, later step. The
legacy schema had a BLOB/TEXT conflict on ``password_hash`` and keyed its audit
log on ``username`` (so renaming a user orphaned the trail). Both are fixed here:
the hash is consistently TEXT and the audit log is keyed on ``user_id``.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nanobio_studio.app.db.base import Base


def utcnow() -> datetime:
    """Timezone-aware UTC. The legacy code mixed naive and aware datetimes."""
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    """Target roles for the platform.

    ``researcher`` is genuinely new (the legacy app had admin/student/viewer).
    Legacy ``student`` accounts are NOT auto-converted; that mapping is an
    explicit migration decision handled separately.
    """

    ADMIN = "admin"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


class AccountState(str, enum.Enum):
    """What can be done with this login account.

    Replaces a boolean that could not distinguish the five situations an
    administrator actually faces. ``is_active`` is kept and derived from this,
    so every existing check keeps working while the reason becomes visible.

    Two of these are *not* deletion, and the distinction is the point. Removing
    an organization membership takes somebody out of a workspace. Disabling an
    account stops them signing in. Neither erases the experiments they
    performed — scientific attribution and the audit trail outlive both, which
    is what makes a regulated record a record.
    """

    #: Created by an administrator, no password chosen yet. Cannot sign in.
    #: The account exists so it can hold memberships and appear in a roster
    #: before its owner has ever visited.
    PENDING_ACTIVATION = "pending_activation"

    ACTIVE = "active"

    #: Temporarily stopped, restorable. The row and its history stay.
    SUSPENDED = "suspended"

    #: Stopped by decision, not expected to return. Still not deleted.
    DISABLED = "disabled"

    #: Erasure requested. Sessions end immediately; identifying fields survive
    #: until it is carried out, so the decision is reversible and auditable.
    DELETION_PENDING = "deletion_pending"

    #: Identifying fields cleared. The row survives, because every experiment,
    #: review and approval references this id — and an approval whose approver
    #: cannot be named is not an approval.
    DELETED = "deleted"


#: The only state in which an account may open or keep a session.
SIGN_IN_STATES = frozenset({AccountState.ACTIVE})


class User(Base):
    __tablename__ = "auth_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False,
                                          index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True,
                                              nullable=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: bcrypt hash, always TEXT. Never plaintext, never returned by the API.
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=32),
        nullable=False,
        default=UserRole.VIEWER,
    )

    #: Kept, and derived from ``state``. Several hundred existing checks read
    #: it, and rewriting them all in the change that introduces the states
    #: would make both harder to review.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    state: Mapped[AccountState] = mapped_column(
        Enum(AccountState, native_enum=False, length=32),
        nullable=False, default=AccountState.ACTIVE,
        server_default="ACTIVE", index=True)
    state_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    state_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    #: Which algorithm produced ``password_hash``.
    #:
    #: Recorded rather than sniffed from the hash prefix, so a rehash-on-login
    #: migration can be reported on. "How many accounts are still on bcrypt" is
    #: a question an operator asks during a migration, and answering it should
    #: not require parsing every hash in the table.
    password_algorithm: Mapped[str | None] = mapped_column(
        String(32), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    #: The next sign-in must set a password. Never a password an administrator
    #: chose — see :class:`AccountToken`.
    must_set_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                           nullable=True)

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username} role={self.role.value}>"


class UserSession(Base):
    """A server-controlled session.

    The client holds an opaque token in an HttpOnly cookie; the server stores
    only its SHA-256 hash, so the table cannot be used to impersonate anyone.
    Sessions are revocable (logout deletes the row) and carry both an absolute
    expiry and an idle timeout.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True,
                                            nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                       nullable=False,
                                                       default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, index=True)

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    #: Why the session ended, when it did. Rows are deleted on logout, so this
    #: is set only where a session is retained for display — it exists so the
    #: "active sessions" screen can distinguish "still open" from "ended by a
    #: password change" without a second table.
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(64),
                                                       nullable=True)

    #: Short, non-secret prefix of the token hash. Lets a user recognise one of
    #: their own sessions in a list, and lets an audit line name a session,
    #: without either becoming a credential.
    handle: Mapped[str | None] = mapped_column(String(12), nullable=True,
                                               index=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class TokenPurpose(str, enum.Enum):
    """What a token may be redeemed for.

    Bound to the purpose, not merely to the account. A reset token that could
    also activate, or an activation token that could also reset, would let one
    workflow be driven through the other and skip its preconditions.
    """

    ACTIVATION = "activation"
    PASSWORD_RESET = "password_reset"


class TokenState(str, enum.Enum):
    PENDING = "pending"
    REDEEMED = "redeemed"
    REVOKED = "revoked"
    EXPIRED = "expired"


class AccountToken(Base):
    """A single-use, time-limited credential for setting a password.

    Stored as ``sha256(token)``. The raw value is returned exactly once — to
    the administrator who issued it, or in the email — and is unrecoverable
    afterwards. The same rule as an organization invitation, for the same
    reason: the token *is* the credential, and a database backup full of live
    ones is a permanent leak nobody would notice being used.

    **No administrator ever sees a password through this.** They cause a link
    to exist; the account holder chooses the password behind it. There is
    deliberately no code path anywhere that lets one person set, view or
    recover another person password.
    """

    __tablename__ = "auth_account_tokens"
    __table_args__ = (
        # One live token per purpose per account. Partial, so a spent token
        # does not block re-issue while two simultaneous live links cannot
        # exist — two links would mean revoking "the" link left one working.
        Index("uq_account_token_live", "user_id", "purpose", unique=True,
              sqlite_where=text("state = 'PENDING'"),
              postgresql_where=text("state = 'PENDING'")),
        Index("ix_account_token_state", "state", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False,
        index=True)

    purpose: Mapped[TokenPurpose] = mapped_column(
        Enum(TokenPurpose, native_enum=False, length=32), nullable=False)
    state: Mapped[TokenState] = mapped_column(
        Enum(TokenState, native_enum=False, length=16), nullable=False,
        default=TokenState.PENDING)

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False,
                                            unique=True, index=True)
    #: Non-secret. Far too short to redeem, long enough to name one token in an
    #: audit line without the line becoming a credential.
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)

    redeemed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                      nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    #: Optimistic-concurrency counter. Redemption claims the row with a
    #: conditional UPDATE, so two simultaneous redemptions of one link set one
    #: password and refuse the other rather than racing.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1,
                                          server_default="1")

    #: What the delivery provider reported. "recorded" means nothing was sent
    #: and an administrator hands the link over — an honest state, not a
    #: failure.
    delivery_provider: Mapped[str | None] = mapped_column(String(32),
                                                          nullable=True)
    delivery_status: Mapped[str | None] = mapped_column(String(32),
                                                        nullable=True)
    #: Never the token, the link or a credential.
    delivery_detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuthEvent(str, enum.Enum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"
    SESSION_EXPIRED = "session_expired"
    SESSION_REVOKED = "session_revoked"
    SESSION_ROTATED = "session_rotated"
    RATE_LIMITED = "rate_limited"
    ADMIN_CREATED = "admin_created"

    ACTIVATION_ISSUED = "activation_issued"
    ACTIVATION_COMPLETED = "activation_completed"
    ACTIVATION_REVOKED = "activation_revoked"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_REHASHED = "password_rehashed"

    ACCOUNT_STATE_CHANGED = "account_state_changed"
    ACCOUNT_SUSPENDED = "account_suspended"
    ACCOUNT_RESTORED = "account_restored"


class AuthAuditLog(Base):
    """Append-only auth audit trail.

    Keyed on ``user_id`` (nullable, because a failed login may not correspond to
    a real account) rather than on a username string, so renames cannot orphan
    history. ``username_attempted`` records what was typed, for investigation.
    """

    __tablename__ = "auth_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event: Mapped[AuthEvent] = mapped_column(
        Enum(AuthEvent, native_enum=False, length=32), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True, index=True)
    username_attempted: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow,
                                                 index=True)


Index("ix_auth_audit_event_time", AuthAuditLog.event, AuthAuditLog.created_at)
