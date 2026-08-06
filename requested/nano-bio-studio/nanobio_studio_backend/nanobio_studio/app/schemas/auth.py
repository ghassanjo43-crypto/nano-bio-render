"""Pydantic schemas for authentication.

Password fields are input-only. No schema here can serialise a password or a
password hash: the response models simply do not contain those fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)
    remember_me: bool = Field(
        False,
        description=(
            "Reserved. Not currently honoured: extending session lifetime "
            "requires a reviewed policy decision, so it has no effect."
        ),
    )


class UserProfile(BaseModel):
    """The authenticated user. Deliberately excludes password_hash."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Literal["admin", "researcher", "viewer"]
    is_active: bool
    last_login_at: Optional[datetime] = None


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: UserProfile
    session_expires_at: datetime
    idle_timeout_minutes: int


class LogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detail: str = "Signed out."


class AuthErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str
    message: str
    retry_after_seconds: Optional[int] = None
