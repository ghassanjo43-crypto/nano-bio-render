"""Per-request access context, and the exception handlers that keep 404 a 404.

One resolution per request
--------------------------
:func:`get_access_context` runs two queries and hands the result to everything
downstream. Services must not re-derive it. If they did, a membership revoked
midway through a request could be in force for one check and not the next, and
the answer to "may they" would depend on which line of code asked.

Choosing the active organization
--------------------------------
The client names one with the ``X-Organization-Id`` header. Naming an
organization *narrows* what the backend will return; it can never widen it,
because :func:`visible_organization_ids` intersects the request with actual
memberships. So a stale or forged header is inert — the worst it achieves is
showing the caller less than they are entitled to.

That is what makes the organization switcher trustworthy. If switching were a
frontend filter, a cached component or a replayed request could still surface
the previous organization's rows; here the rows are never selected.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.api.deps_auth import get_current_user
from nanobio_studio.app.db.auth_models import User
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.organizations.policy import (
    AccessContext, PolicyDenied, RecordNotVisible, resolve_context,
)

__all__ = [
    "ORGANIZATION_HEADER",
    "get_access_context",
    "policy_denied_handler",
    "record_not_visible_handler",
]

ORGANIZATION_HEADER = "X-Organization-Id"


async def get_access_context(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_auth_session),
) -> AccessContext:
    """Resolve every access fact for this caller, once."""
    raw = request.headers.get(ORGANIZATION_HEADER)
    active: int | None = None
    if raw:
        try:
            active = int(raw)
        except ValueError:
            # A malformed header is a client bug, not an attack, and it must
            # not silently fall back to "all organizations" — that would turn
            # a typo into a widening of scope.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_organization",
                    "message": (f"{ORGANIZATION_HEADER} must be an integer "
                                f"organization id."),
                },
            )
    return await resolve_context(session, user, active_organization_id=active)


#: Which "nothing was produced" flag each route family carries on a failure.
#:
#: Mirrors ``vertical_slice.validation_exception_handler``. A refused request
#: has to fail in the *same shape* the route succeeds in, or a client cannot
#: tell "you may not see this" from "the field is missing" — and, worse, a 404
#: whose body differs by route family becomes a way to work out which family a
#: foreign identifier belongs to.
_AVAILABILITY_FLAG: tuple[tuple[str, str], ...] = (
    ("/api/v1/pk/", "results_available"),
    ("/api/v1/reports", "data_available"),
    ("/api/v1/validation/", "registry_available"),
    ("/api/v1/science/", "readiness_available"),
    ("/api/v1/runs", "data_available"),
    ("/api/v1/projects", "data_available"),
)


def _availability_flag(path: str) -> str:
    for prefix, flag in _AVAILABILITY_FLAG:
        if path.startswith(prefix):
            return flag
    return "data_available"


async def record_not_visible_handler(
    request: Request, exc: RecordNotVisible,
):
    """404 — and deliberately indistinguishable from a genuine absence.

    The body names no organization, no owner and no reason beyond "not found",
    because every one of those would confirm that the identifier belongs to
    something real somewhere else.
    """
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "not_found",
            "message": f"No such {exc.record_type}.",
            "detail": None,
            _availability_flag(request.url.path): False,
        },
    )


async def policy_denied_handler(_request: Request, exc: PolicyDenied):
    """403 — reached only once membership is already established.

    Safe to explain here: the caller is inside the organization, so telling
    them *why* they cannot do this reveals nothing they could not already see,
    and a denial nobody understands becomes a support ticket or a workaround.
    """
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "not_permitted",
            "action": exc.action.value,
            "message": exc.reason,
        },
    )
