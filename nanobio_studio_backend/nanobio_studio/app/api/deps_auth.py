"""FastAPI dependencies for authentication and role-based access control."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.core.config import settings
from nanobio_studio.app.db.auth_models import User, UserRole
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.services.auth_service import (
    SESSION_COOKIE_NAME,
    resolve_session,
)


def client_ip(request: Request) -> str | None:
    """The client address, trusting a forwarded header only from a known proxy.

    An unfiltered ``X-Forwarded-For`` is client-controlled. Honouring it lets an
    attacker present a different address on every request and walk straight
    past per-address rate limiting — so the header is read **only** when the
    immediate peer is one of the addresses configured in ``TRUSTED_PROXY_IPS``,
    and the default is to trust none.

    When it is trusted, the *rightmost* entry the proxy appended is taken
    rather than the leftmost. The leftmost is whatever the client sent and can
    be anything; the rightmost is what our own proxy observed.
    """
    peer = request.client.host if request.client else None
    trusted = {ip.strip() for ip in (settings.trusted_proxy_ips or [])
               if ip and ip.strip()}
    if not trusted or peer not in trusted:
        return peer

    forwarded = request.headers.get("x-forwarded-for") or ""
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    # Walk from the right past our own proxies to the first address none of
    # them is, which is the closest thing to a real client we can attest to.
    for candidate in reversed(hops):
        if candidate not in trusted:
            return candidate
    return peer


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
