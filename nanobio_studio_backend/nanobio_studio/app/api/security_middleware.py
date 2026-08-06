"""Browser-facing protections: security headers, and origin checking for CSRF.

Why origin checking rather than a synchroniser token
----------------------------------------------------
The session cookie is ``SameSite=Lax``, which already blocks the classic
cross-site form post. That is genuine protection and it is not sufficient on
its own: ``Lax`` still permits a top-level ``GET`` navigation to carry the
cookie, older browsers implement it inconsistently, and a same-site subdomain
is not cross-site at all.

So state-changing requests are additionally required to come from an approved
origin. Checking ``Origin`` — with ``Referer`` as a fallback for the few cases
that omit it — costs nothing per request, needs no token to be threaded through
every form, and cannot be got wrong by a page that forgot to include a hidden
field. A synchroniser token would add a second thing to keep in step for a
protection this already provides.

What an absent ``Origin`` means
------------------------------
It means the caller is not a browser. Every current browser attaches ``Origin``
to POST, PUT, PATCH and DELETE — same-origin included — and a page cannot
suppress it, which is exactly what makes the header usable as a CSRF signal.

So an unsafe request without one came from a script, a provisioning tool or a
test client, and those cannot be forged: forgery works by getting a *browser*
to attach the session cookie automatically, and a script that already has the
cookie does not need a victim. Refusing them would buy nothing and would break
every non-browser client, including the deployment scripts and the walkthrough
harness.

A request that *does* declare an origin and declares a foreign one is refused,
which is the case an attacker is actually in.

Cache headers on authenticated responses
----------------------------------------
Anything served to an authenticated caller is marked ``no-store``. A shared
proxy or a browser cache holding a patient assessment, a member list or a
session listing is a disclosure that outlives the session that fetched it, and
the back button after a shared-machine logout is exactly how it surfaces.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from nanobio_studio.app.core.config import settings

log = logging.getLogger(__name__)

__all__ = ["SecurityHeadersMiddleware", "OriginCheckMiddleware",
           "approved_origins"]

#: Methods that change something and therefore need an approved origin.
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Paths reached without a session, listed so the reasoning is written down
#: rather than inferred from the absence of a check.
#:
#: None of these can be forged cross-site: forgery works by borrowing an
#: existing session, and these are the routes a caller uses when they have
#: none. They are covered by the unauthenticated branch below; the list is
#: here so a reader can see they were considered.
UNAUTHENTICATED_STATE_CHANGING_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/account/activate",
    "/api/v1/account/reset",
    "/api/v1/account/forgot",
})


def approved_origins() -> set[str]:
    """Origins whose credentialed requests are accepted.

    The same list CORS uses, so there is one answer to "may this site talk to
    us" rather than two that can drift apart.
    """
    return {origin.rstrip("/") for origin in (settings.slice_cors_origins or [])
            if origin and origin != "*"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Headers every response carries, and why each one is there."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        headers = response.headers

        # Stops a browser deciding an octet-stream is really HTML and running
        # it. Cheap, and the failure it prevents is script execution in our
        # own origin.
        headers.setdefault("X-Content-Type-Options", "nosniff")

        # Clickjacking. `frame-ancestors` in the CSP is the modern control and
        # X-Frame-Options is the one older browsers honour; both are set
        # because the cost of the second is one header.
        headers.setdefault("X-Frame-Options", "DENY")

        # Referrer. `strict-origin-when-cross-origin` stops a study or
        # assessment identifier in a path leaking to a third-party host in a
        # Referer header — which is how internal identifiers end up in
        # somebody else's access log.
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # Turn off browser features this application never uses, so a
        # compromised script cannot reach them either.
        headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()")

        path = request.url.path
        if path.startswith("/api/"):
            # An API response is JSON and must never be framed, styled or
            # scripted. `default-src 'none'` is the strictest thing that can be
            # said about a document nobody should be rendering.
            headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        else:
            headers.setdefault("Content-Security-Policy", _spa_csp())

        # Nothing served to an authenticated caller may be cached. A shared
        # proxy or a browser cache holding a member list or a patient
        # assessment outlives the session that fetched it, and the back button
        # after a shared-machine logout is how it surfaces.
        if _is_authenticated_request(request) and path.startswith("/api/"):
            headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            headers["Pragma"] = "no-cache"

        return response


def _spa_csp() -> str:
    """The SPA policy, with `unsafe-inline` confined to development.

    What was wrong
    --------------
    This policy carried `style-src 'self' 'unsafe-inline'` unconditionally,
    with a comment explaining that Vite injects inline styles. The comment was
    true and the conclusion was not: Vite injects inline styles **in the dev
    server**, where it hot-reloads CSS by writing `<style>` elements. The
    production build does not. It emits one hashed stylesheet and an
    `index.html` containing no `<style>` element and no `style` attribute —
    verified against the actual build output, not assumed.

    So production was running a measurably weaker policy than it needed, for a
    reason that only applied to development. That is the quiet kind of
    weakening: a real constraint, correctly described, applied one environment
    too wide, and permanent because the comment explaining it reads as
    justification.

    React's `style={{...}}` props are unaffected either way — React assigns
    through CSSOM from an already-allowed script, which `style-src` does not
    govern.

    The dev allowance is keyed on `settings.environment`, so the strict policy
    is what any deployment gets unless it explicitly says it is development.
    """
    base = ("default-src 'self'; "
            "script-src 'self'; "
            "{style}"
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'")

    if settings.environment.strip().lower() == "development":
        # Vite's HMR client writes <style> elements as CSS changes.
        return base.format(style="style-src 'self' 'unsafe-inline'; ")
    return base.format(style="style-src 'self'; ")


def _is_authenticated_request(request: Request) -> bool:
    from nanobio_studio.app.services.auth_service import SESSION_COOKIE_NAME
    return SESSION_COOKIE_NAME in request.cookies


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Refuses a credentialed state-changing request from an unapproved origin.

    Runs before the route, so a refused request never reaches a service and
    never touches the database.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method not in _UNSAFE_METHODS:
            return await call_next(request)

        # A request with no session cookie cannot be a cross-site request
        # *forgery*: there is no authority to borrow. Login and activation are
        # in this class by construction.
        if not _is_authenticated_request(request):
            return await call_next(request)

        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        approved = approved_origins()

        candidate = origin
        if candidate is None and referer:
            parts = urlsplit(referer)
            if parts.scheme and parts.netloc:
                candidate = f"{parts.scheme}://{parts.netloc}"

        if candidate is None:
            # No Origin and no Referer at all.
            #
            # This is **not** a browser. Every current browser attaches
            # ``Origin`` to POST, PUT, PATCH and DELETE, same-origin included,
            # and a page cannot suppress it — that is the whole reason the
            # header is usable as a CSRF signal. So an unsafe request without
            # one came from a script, a provisioning tool or a test client.
            #
            # Those are not a CSRF risk, because cross-site request forgery
            # needs a *browser* to attach the session cookie automatically. A
            # script that wants to send the cookie has to have obtained it,
            # and if it has the cookie it does not need the victim.
            #
            # Refusing here would therefore buy nothing and would break every
            # non-browser client — including the deployment scripts and the
            # walkthrough harness — for a threat that cannot reach this path.
            # ``SameSite=Lax`` remains in force underneath for the browser case.
            return await call_next(request)

        candidate = candidate.rstrip("/")

        # Same-origin is always acceptable, and is the normal case: the SPA and
        # the API share an origin in the supported deployment.
        here = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")
        if candidate == here or candidate in approved:
            return await call_next(request)

        log.warning("refused a credentialed %s to %s from an unapproved origin",
                    request.method, request.url.path)
        return _refuse(
            "origin_not_allowed",
            "This request came from a site that is not permitted to act on "
            "your session.")


def _refuse(code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"error": code, "message": message, "detail": None,
                 "data_available": False},
    )
