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
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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

    user: Mapped[User] = relationship(back_populates="sessions")


class AuthEvent(str, enum.Enum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_EXPIRED = "session_expired"
    RATE_LIMITED = "rate_limited"
    ADMIN_CREATED = "admin_created"


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
