"""FastAPI dependencies for authentication and role-based access control."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.auth_models import User, UserRole
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.services.auth_service import (
    SESSION_COOKIE_NAME,
    resolve_session,
)


def client_ip(request: Request) -> str | None:
    """Best-effort client IP.

    NOTE: X-Forwarded-For is intentionally NOT trusted here. Behind a proxy this
    must be wired to a validated forwarded header, otherwise a client could spoof
    its IP and evade per-IP rate limiting.
    """
    return request.client.host if request.client else None


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_auth_session),
) -> User:
    """Require an authenticated session. 401 otherwise."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    resolved = await resolve_session(session, token)
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "not_authenticated",
                "message": "Sign in to continue.",
            },
        )
    user, _ = resolved
    return user


async def get_optional_user(
    request: Request,
    session: AsyncSession = Depends(get_auth_session),
) -> User | None:
    """Resolve a session if present, without requiring one."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    resolved = await resolve_session(session, token)
    return resolved[0] if resolved else None


def require_role(*roles: UserRole) -> Callable:
    """Dependency factory restricting a route to the given roles."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_role",
                    "message": (
                        "Your account does not have access to this resource."
                    ),
                    "required_roles": [r.value for r in roles],
                },
            )
        return user

    return _guard


require_admin = require_role(UserRole.ADMIN)
require_researcher = require_role(UserRole.ADMIN, UserRole.RESEARCHER)
