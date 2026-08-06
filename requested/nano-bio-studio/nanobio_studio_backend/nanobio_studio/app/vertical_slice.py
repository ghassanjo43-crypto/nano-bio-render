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

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from nanobio_studio.app.api.routes import (
    auth, design, health, pk, pk_routed, reports, workspace,
)
from nanobio_studio.app.api.static_frontend import mount_frontend, resolve_dist_path
from nanobio_studio.app.core.config import settings
from nanobio_studio.app.db.auth_session import close_auth_db, init_auth_db

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Explicit startup initialisation -- never an import side effect."""
    await init_auth_db()
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
    allow_origins=settings.slice_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


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
app.include_router(reports.router)


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
