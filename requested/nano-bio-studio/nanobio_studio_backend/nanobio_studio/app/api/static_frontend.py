"""Serve the built React SPA from the same origin as the API.

Why this exists
---------------
The session cookie is ``SameSite=Lax``. If the interface is served from a
different *site* than the API, the browser accepts the cookie on the login
response and then refuses to send it on every subsequent request — the user is
signed out the instant they sign in. That is a real defect this project hit:
the app served from ``localhost:5173`` calling the API at ``127.0.0.1:8000``,
which are different sites for cookie purposes.

Development solves it with the Vite proxy (``frontend/vite.config.ts``).
Production has no dev server, so the equivalent must exist here: one origin
answers both the SPA and the API, and the cookie keeps working unchanged with
the stronger ``Lax`` CSRF posture. CORS becomes irrelevant in this shape.

Ordering contract
-----------------
This is mounted **after** every API router. FastAPI matches routes in
registration order, so the API always wins and the SPA fallback only sees paths
no route claimed.

The one rule that must not be broken
------------------------------------
**An unknown API path must never return HTML.** The typed frontend client parses
every response as JSON and treats a non-JSON body as a failure. If the SPA
fallback swallowed ``/api/v1/nope`` and returned ``index.html``, every genuine
API error would degrade into "returned a response that was not JSON" and the
real cause would be lost. ``_is_api_path`` enforces this, and a test asserts it.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

__all__ = ["resolve_dist_path", "mount_frontend"]

#: Prefixes that belong to the API and must never fall through to the SPA.
_API_PREFIXES: tuple[str, ...] = (
    "/api/", "/health", "/ready", "/docs", "/redoc", "/openapi.json",
)

#: Repository root, used to resolve a relative `frontend_dist_path`.
_REPO_ROOT = Path(__file__).resolve().parents[4]


def resolve_dist_path(configured: str) -> Path:
    """Resolve the configured build directory against the repository root."""
    path = Path(configured)
    return path if path.is_absolute() else (_REPO_ROOT / path)


def _is_api_path(path: str) -> bool:
    """True when a path belongs to the API rather than to client-side routing."""
    normalised = path if path.startswith("/") else f"/{path}"
    return any(normalised == prefix.rstrip("/") or normalised.startswith(prefix)
               for prefix in _API_PREFIXES)


def mount_frontend(app: FastAPI, dist_path: Path) -> bool:
    """Attach SPA serving to ``app``. Returns False when the build is absent.

    Absence is not an error: the backend is perfectly usable API-only, and
    failing to boot because a frontend build is missing would be a poor
    trade. The caller logs the outcome.
    """
    index_file = dist_path / "index.html"
    if not index_file.is_file():
        return False

    assets_dir = dist_path / "assets"
    if assets_dir.is_dir():
        # Hashed filenames, so these are safe to serve directly and cache hard.
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str):
        """Return index.html so client-side routes deep-link correctly.

        `/demo`, `/history/7` and `/workflow/review` exist only in the React
        router; a page load or refresh on one of them reaches the server, which
        must hand back the SPA shell and let the client route.
        """
        if _is_api_path(request.url.path):
            # Never HTML. See the module docstring: the typed client depends on
            # API failures staying JSON.
            return JSONResponse(
                status_code=404,
                content={
                    "error": "not_found",
                    "message": f"No API route matches {request.url.path}.",
                    "detail": None,
                },
            )

        # A request for a real file that is not under /assets (favicon, robots).
        candidate = (dist_path / full_path).resolve()
        if full_path and candidate.is_file():
            try:
                candidate.relative_to(dist_path.resolve())
            except ValueError:
                # Path traversal attempt; fall through to the SPA shell rather
                # than serving anything outside the build directory.
                return FileResponse(index_file)
            return FileResponse(candidate)

        return FileResponse(index_file)

    return True
