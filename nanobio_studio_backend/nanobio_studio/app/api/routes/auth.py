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
from nanobio_studio.app.core.config import settings
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
    """HTTPS-only cookie flag.

    Reads configuration first and the raw environment second, so a deployment
    that sets either gets the secure behaviour. False by default only so local
    http development works — anywhere reachable over HTTPS must set it.
    """
    if settings.session_cookie_secure:
        return True
    return os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in (
        "1", "true", "yes")


def cookie_policy() -> dict:
    """The attributes the session cookie is set with.

    One place, read by both the setter and the diagnostics endpoint, so what
    the server reports and what it actually sends cannot drift apart — a
    diagnostics endpoint that describes intended behaviour rather than real
    behaviour is worse than none.
    """
    return {
        "name": SESSION_COOKIE_NAME,
        "httponly": True,
        "secure": _cookie_secure(),
        "samesite": (settings.session_cookie_samesite or "lax").lower(),
        "path": settings.session_cookie_path or "/",
        # Empty means host-only. A parent domain would share the cookie with
        # every sibling host, which is how one compromised subdomain becomes
        # an authenticated session everywhere.
        "domain": settings.session_cookie_domain or None,
        "max_age_seconds": int(SESSION_IDLE_TIMEOUT.total_seconds()),
    }


def _set_session_cookie(response: Response, token: str, max_age: int) -> None:
    policy = cookie_policy()
    response.set_cookie(
        key=policy["name"],
        value=token,
        max_age=max_age,
        httponly=True,
        samesite=policy["samesite"],
        secure=policy["secure"],
        path=policy["path"],
        domain=policy["domain"],
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
            # Session fixation: whatever session the browser arrived with is
            # discarded before a new one is issued. Without passing this the
            # rotation is inert — an attacker who can plant a cookie waits for
            # the victim to sign in and then holds a session authenticated as
            # them.
            previous_token=request.cookies.get(SESSION_COOKIE_NAME),
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


@router.get("/cookie-policy",
            summary="How the session cookie is configured")
async def cookie_policy_route() -> dict:
    """What attributes this server sets on the session cookie.

    Unauthenticated on purpose: it is the deployment check that needs it, and
    it discloses nothing — the attributes are policy, not secrets, and knowing
    that a cookie is HttpOnly and Secure helps an attacker not at all.

    It exists because verifying cookie attributes any other way means either
    signing in (which needs an account a deployment check has no business
    creating) or reading the source (which describes intent, not the running
    configuration).
    """
    policy = cookie_policy()
    return {
        **policy,
        "notice": (
            "Secure must be true anywhere reachable over HTTPS. It is false "
            "by default only so local http development works."
            if not policy["secure"] else
            "Secure is set: the cookie will not be sent over plain HTTP."),
    }


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
