"""Authentication routes: login, logout, profile.

Cookie policy
-------------
The session token is set as an **HttpOnly** cookie:

* ``httponly=True``  -- unreadable by JavaScript, so XSS cannot exfiltrate it
* ``samesite="lax"`` -- blocks cross-site POST CSRF while allowing normal navigation
* ``secure``         -- driven by ``SESSION_COOKIE_SECURE``; must be True over HTTPS
* ``path="/"``

The token is never placed in a URL, a response body, ``localStorage`` or a
JavaScript-readable cookie. This deliberately replaces the legacy scheme, which
put a forgeable token in the query string.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.api.deps_auth import client_ip, get_current_user
from nanobio_studio.app.db.auth_models import User
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.schemas.auth import (
    AuthErrorResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    UserProfile,
)
from nanobio_studio.app.services.auth_service import (
    SESSION_COOKIE_NAME,
    SESSION_IDLE_TIMEOUT,
    AuthError,
    authenticate,
    logout,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _cookie_secure() -> bool:
    """HTTPS-only cookie flag. False for local http development."""
    return os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in (
        "1", "true", "yes")


def _set_session_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        path="/",
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": AuthErrorResponse},
        429: {"model": AuthErrorResponse},
    },
    summary="Sign in and open a session",
)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_auth_session),
):
    ip = client_ip(request)
    agent = request.headers.get("user-agent")

    try:
        user, token, expires_at = await authenticate(
            session,
            username=payload.username,
            password=payload.password,
            ip_address=ip,
            user_agent=agent,
        )
    except AuthError as exc:
        headers = {}
        if exc.retry_after:
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            headers=headers,
            content=AuthErrorResponse(
                error=exc.code,
                message=exc.message,
                retry_after_seconds=exc.retry_after,
            ).model_dump(),
        )

    # `expires_at` comes back from authenticate() directly. Reading it off
    # `user.sessions` would trigger a lazy relationship load outside the
    # greenlet and raise MissingGreenlet under async SQLAlchemy.
    body = LoginResponse(
        user=UserProfile.model_validate(_profile_dict(user)),
        session_expires_at=expires_at,
        idle_timeout_minutes=int(SESSION_IDLE_TIMEOUT.total_seconds() // 60),
    )
    response = JSONResponse(status_code=status.HTTP_200_OK,
                            content=body.model_dump(mode="json"))
    # Cookie max-age tracks the IDLE timeout, so a browser-side cookie does not
    # outlive the server-side idle policy.
    _set_session_cookie(response, token,
                        int(SESSION_IDLE_TIMEOUT.total_seconds()))
    return response


@router.post("/logout", response_model=LogoutResponse,
             summary="Sign out and revoke the session")
async def logout_route(
    request: Request,
    session: AsyncSession = Depends(get_auth_session),
):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    await logout(session, token, ip_address=client_ip(request),
                 user_agent=request.headers.get("user-agent"))

    response = JSONResponse(status_code=status.HTTP_200_OK,
                            content=LogoutResponse().model_dump())
    # Always clear the cookie, even if no server-side session existed.
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/me", response_model=UserProfile,
            responses={401: {"model": AuthErrorResponse}},
            summary="The currently authenticated user")
async def me(user: User = Depends(get_current_user)) -> UserProfile:
    return UserProfile.model_validate(_profile_dict(user))


def _profile_dict(user: User) -> dict:
    """Explicit projection. Guarantees password_hash can never be serialised."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "last_login_at": user.last_login_at,
    }
