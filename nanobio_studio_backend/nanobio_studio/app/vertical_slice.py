"""FastAPI application for the Phase 2 vertical slice.

Why this is a separate entry point from ``app/main.py``
------------------------------------------------------
``app/main.py`` is the pre-existing LNP ingestion/ML backend. Its lifespan calls
``init_db()`` against PostgreSQL and it imports ``loguru``, so it cannot start
without a database and an extra dependency. This slice needs neither: it computes
a score from request inputs and stores nothing.

Rather than modify that application (which would expand scope and risk the
existing project), the slice gets its own ASGI app that reuses the same package,
settings module and health router. Consolidating the two entry points belongs to
Step 2, when the backend skeleton is properly established.

Run it with:

    uvicorn nanobio_studio.app.vertical_slice:app --reload --port 8000

Scientific positioning: every response is a computational research-planning
result. Nothing served here is experimentally or clinically validated.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from nanobio_studio.app.api.deps_organization import (
    policy_denied_handler, record_not_visible_handler,
)
from nanobio_studio.app.organizations.policy import (
    PolicyDenied, RecordNotVisible,
)
from nanobio_studio.app.api.routes import (
    auth, candidate_artifacts, design, health, organizations, pk, pk_routed,
    readiness, account, reports, validation, workspace,
)
from nanobio_studio.app.api.static_frontend import mount_frontend, resolve_dist_path
from nanobio_studio.app.core.config import settings
from nanobio_studio.app.api.security_middleware import (
    OriginCheckMiddleware, SecurityHeadersMiddleware,
)
from nanobio_studio.app.db.auth_session import close_auth_db, init_auth_db

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Explicit startup initialisation -- never an import side effect."""
    await init_auth_db()

    # Build the object store now, so an incomplete production configuration
    # fails here rather than at the first upload. The alternative — coming up,
    # serving traffic and quietly writing attachments to a container
    # filesystem that the next deploy discards — is the failure mode this
    # check exists to make impossible.
    #
    # Deliberately NOT a reachability check: a momentarily unreachable store
    # should not stop the application from starting and serving the routes
    # that do not need it. Reachability is the readiness probe's job, because
    # it is re-evaluated continuously; configuration is this one's, because it
    # will not fix itself.
    from nanobio_studio.app.storage import verify_configuration
    verify_configuration()

    # Same reasoning for the login limiter, one degree sharper. An object store
    # that is misconfigured fails loudly at the first upload; a rate limiter
    # that is misconfigured never fails at all — it just counts a fifth of what
    # it promises, reports itself healthy, and is noticed only as a successful
    # brute force nobody attributes to it. So a declared multi-instance
    # deployment with per-process counters stops here.
    from nanobio_studio.app.core.rate_limit import (
        build_backend, verify_rate_limit_configuration,
    )
    from nanobio_studio.app.services.auth_service import rate_limiter

    backend = build_backend(kind=settings.rate_limit_backend,
                            redis_url=settings.rate_limit_redis_url)
    description = verify_rate_limit_configuration(
        kind=settings.rate_limit_backend,
        instance_count=settings.app_instance_count,
        backend=backend)
    rate_limiter.use_backend(backend)
    logger.info("login rate limiting: %s", description)

    # A configured-but-broken breach corpus raises here. It must not degrade
    # quietly: a check that is switched on in configuration and does nothing at
    # runtime is worse than one that was never switched on, because somebody
    # has recorded it as a control.
    from nanobio_studio.app.core.breach_corpus import corpus_status, load_corpus
    load_corpus(settings.password_breach_corpus_path)
    logger.info("password breach corpus: %s", corpus_status())

    yield
    await close_auth_db()


app = FastAPI(
    title=f"{settings.api_title} (Vertical Slice)",
    version=settings.api_version,
    description=(
        "React + TypeScript -> FastAPI -> canonical scientific code. Two "
        "migrated calculations are served: the design impact score "
        "(core.scoring) and the two-compartment pharmacokinetic model "
        "(utils.pk_model). They are separate calculations with separate "
        "versions and must not be combined. Not the full platform."
    ),
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS -- environment-driven, no wildcard
# ---------------------------------------------------------------------------
# The stored default in core/config.py includes "*", which is both unsafe and
# invalid alongside allow_credentials=True. The slice uses the explicit,
# env-configurable dev origins instead. Override with NANOBIO_CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    # An explicit allow-list. Never "*": a wildcard with credentials is
    # rejected by browsers anyway, and writing one invites somebody to "fix"
    # it by echoing the request origin, which permits every site there is.
    allow_origins=[o for o in settings.slice_cors_origins if o != "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Organization-Id"],
)

# Order matters, and Starlette runs middleware in reverse registration order —
# so the origin check is registered AFTER CORS and therefore runs BEFORE the
# route. A refused request never reaches a service and never touches the
# database.
app.add_middleware(OriginCheckMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request,
                                       exc: RequestValidationError):
    """Return schema failures in the same structured shape as calculation failures.

    Critically, this carries no result field: a rejected request must never
    produce a number, favourable or otherwise. The "nothing was produced" flag
    is named for the calculation the route serves, so each endpoint's failure
    body matches its own success contract.
    """
    path = request.url.path
    if path.startswith("/api/v1/pk/"):
        availability_flag = "results_available"
    elif path.startswith("/api/v1/reports"):
        # A rejected report request must never look like it produced clinical
        # data, so the flag names what is absent here too.
        availability_flag = "data_available"
    elif path.startswith("/api/v1/validation/"):
        # A rejected registry request must not look like an empty registry.
        availability_flag = "registry_available"
    elif path.startswith("/api/v1/science/"):
        # Matches the readiness routes' own failure shape, so a rejected
        # request cannot be mistaken for an assessment that came back empty.
        availability_flag = "readiness_available"
    else:
        availability_flag = "score_available"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "The request did not match the expected schema.",
            "detail": "; ".join(
                f"{'.'.join(str(p) for p in e.get('loc', ()) if p != 'body')}: "
                f"{e.get('msg', '')}".strip(": ")
                for e in exc.errors()
            ) or None,
            availability_flag: False,
        },
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(design.router)
app.include_router(pk.router)
# Route-aware PK. Registered alongside the legacy depot endpoint,
# not in place of it, so stored runs stay reproducible.
app.include_router(pk_routed.router)
app.include_router(workspace.router)
app.include_router(account.router)
app.include_router(reports.router)
# Scientific Readiness Framework. Assesses six areas independently;
# adds no scientific calculation of its own.
app.include_router(readiness.router)
# Experimental Validation Registry (Phase 2, Milestone 1). Grants E3 only;
# every gate, permission and transition is enforced in the service beneath
# these routes, not by the routes themselves.
app.include_router(validation.router)
# Records that depend on an exact candidate version: simulations, evidence
# assessments, reports, exports, CRO packages and filed comparisons. Every
# route is addressed to a version and none of them resolves "latest" — the
# locking, the audit event and the dependent insert happen together inside
# services/candidate_dependencies.py.
app.include_router(candidate_artifacts.router)
# Organization and study-team management (Phase 2, Production
# Hardening). Administrative authority only: nothing here can grant
# scientific authority, and no route bypasses the policy.
app.include_router(organizations.router)

# Organization boundary (Phase 2, Production Hardening).
#
# Registered as handlers rather than caught per route so no route can get the
# mapping wrong. The distinction they preserve is the whole point of the
# boundary: a record outside the caller's organizations raises
# RecordNotVisible and becomes an ordinary 404, indistinguishable from an
# identifier that was never issued, while a record inside the organization
# that the caller may not act on raises PolicyDenied and becomes a 403 with a
# reason. Collapsing the two either leaks the existence of other tenants'
# records or leaves users unable to tell "not yours" from "not allowed".
app.add_exception_handler(RecordNotVisible, record_not_visible_handler)
app.add_exception_handler(PolicyDenied, policy_denied_handler)


def _service_descriptor() -> dict:
    return {
        "service": "NanoBio Studio Backend — Vertical Slice",
        "version": settings.api_version,
        "status": "running",
        "endpoints": [
            "/health", "/ready", "/docs",
            "/api/v1/auth/login", "/api/v1/auth/logout",
            "/api/v1/auth/me", "/api/v1/design/score",
            "/api/v1/pk/simulate",
            "/api/v1/demo/scenarios", "/api/v1/runs", "/api/v1/projects",
            "/api/v1/reports",
        ],
        "notice": (
            "Computational research use only. Results are not experimentally "
            "or clinically validated."
        ),
    }


@app.get("/api", tags=["meta"])
async def service_descriptor() -> dict:
    """The service descriptor, always reachable regardless of what serves `/`."""
    return _service_descriptor()


# ---------------------------------------------------------------------------
# Same-origin frontend serving
# ---------------------------------------------------------------------------
# Registered LAST so every API route above takes precedence. When enabled, `/`
# belongs to the interface and the descriptor lives at `/api`; when the backend
# runs API-only, `/` keeps returning the descriptor as before.
#
# See app/api/static_frontend.py for why same-origin serving is a correctness
# requirement rather than a packaging convenience.
_frontend_mounted = False

if settings.serve_frontend:
    _dist = resolve_dist_path(settings.frontend_dist_path)
    _frontend_mounted = mount_frontend(app, _dist)
    if not _frontend_mounted:
        # Not fatal: an API-only backend is perfectly usable, and refusing to
        # boot over a missing frontend build would be a poor trade.
        print(
            f"[nanobio] SERVE_FRONTEND is set but no build was found at "
            f"{_dist}. Serving API only. Run `npm run build` in frontend/."
        )

if not _frontend_mounted:
    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return _service_descriptor()
