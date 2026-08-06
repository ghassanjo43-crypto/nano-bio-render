"""Tests for same-origin SPA serving.

Why this matters
----------------
The session cookie is ``SameSite=Lax``. Serving the interface from a different
site than the API means the browser accepts the cookie on login and then refuses
to send it on anything else — the user is signed out the instant they sign in.
That defect was hit in development (`localhost:5173` calling `127.0.0.1:8000`)
and would recur in production without same-origin serving.

The load-bearing test here is
``test_unknown_api_path_returns_json_not_html``: the typed frontend client
parses every response as JSON, so an SPA fallback that swallowed an unknown API
path would turn every genuine API error into "returned a response that was not
JSON" and hide the real cause.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if _p in sys.path:
        sys.path.remove(_p)
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

INDEX_MARKER = "<!-- spa-shell -->"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    """A minimal stand-in for the Vite build output."""
    build = tmp_path / "dist"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text(
        f"<!doctype html><html><body>{INDEX_MARKER}</body></html>",
        encoding="utf-8")
    (build / "assets" / "index-abc123.js").write_text(
        "console.log('bundle');", encoding="utf-8")
    (build / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    return build


@pytest.fixture
def app_with_spa(dist: Path) -> FastAPI:
    """An app shaped like the real one: API routes first, SPA fallback last."""
    from nanobio_studio.app.api.static_frontend import mount_frontend

    app = FastAPI()

    @app.get("/api/v1/design/score")
    async def _score():
        return {"design_impact_score": {"delivery": 1.0}}

    @app.get("/health")
    async def _health():
        return {"status": "healthy"}

    assert mount_frontend(app, dist) is True
    return app


# ===========================================================================
# The rule that protects the client's error handling
# ===========================================================================


class TestApiPathsNeverReturnHtml:

    @pytest.mark.parametrize("path", [
        "/api/v1/nope",
        "/api/v1/design/nonexistent",
        "/api/",
        "/api",
    ])
    def test_unknown_api_path_returns_json_not_html(self, app_with_spa, path):
        with TestClient(app_with_spa) as client:
            r = client.get(path)

        assert r.status_code == 404, path
        assert "application/json" in r.headers["content-type"], path
        assert INDEX_MARKER not in r.text, (
            f"{path} fell through to the SPA shell; the typed client would see "
            "HTML where it expects JSON and every API error would degrade.")
        assert r.json()["error"] == "not_found"

    @pytest.mark.parametrize("path", ["/health", "/ready", "/openapi.json",
                                      "/docs"])
    def test_reserved_api_prefixes_never_serve_the_shell(self, app_with_spa,
                                                          path):
        with TestClient(app_with_spa) as client:
            r = client.get(path)
        assert INDEX_MARKER not in r.text, f"{path} served the SPA shell"

    def test_the_json_404_matches_the_client_error_shape(self, app_with_spa):
        """The client reads `error`/`message`; a mismatch degrades messaging."""
        with TestClient(app_with_spa) as client:
            body = client.get("/api/v1/nope").json()
        assert set(body) >= {"error", "message"}
        assert isinstance(body["message"], str)
        # `detail` must be a string or null, never an object -- rendering an
        # object as a React child crashes the page.
        assert body["detail"] is None or isinstance(body["detail"], str)


# ===========================================================================
# SPA routing
# ===========================================================================


class TestSpaRouting:

    def test_root_serves_the_interface(self, app_with_spa):
        with TestClient(app_with_spa) as client:
            r = client.get("/")
        assert r.status_code == 200
        assert INDEX_MARKER in r.text

    @pytest.mark.parametrize("route", [
        "/demo", "/history", "/history/7", "/compare", "/projects",
        "/workflow/review", "/start",
    ])
    def test_client_side_routes_deep_link(self, app_with_spa, route):
        """A refresh on a React-router path must return the shell, not a 404."""
        with TestClient(app_with_spa) as client:
            r = client.get(route)
        assert r.status_code == 200, route
        assert INDEX_MARKER in r.text, route

    def test_hashed_assets_are_served(self, app_with_spa):
        with TestClient(app_with_spa) as client:
            r = client.get("/assets/index-abc123.js")
        assert r.status_code == 200
        assert "console.log" in r.text

    def test_real_files_outside_assets_are_served(self, app_with_spa):
        with TestClient(app_with_spa) as client:
            r = client.get("/favicon.svg")
        assert r.status_code == 200
        assert "<svg" in r.text

    def test_api_routes_still_win_over_the_fallback(self, app_with_spa):
        with TestClient(app_with_spa) as client:
            r = client.get("/api/v1/design/score")
        assert r.status_code == 200
        assert r.json()["design_impact_score"]["delivery"] == 1.0

    def test_path_traversal_cannot_escape_the_build_directory(self,
                                                              app_with_spa):
        with TestClient(app_with_spa) as client:
            r = client.get("/../../nanobio_auth_dev.db")
        # Either refused by the client/server or handed the SPA shell; never the
        # file itself.
        assert "SQLite" not in r.text


# ===========================================================================
# Enablement
# ===========================================================================


class TestEnablement:

    def test_mounting_reports_false_when_no_build_exists(self, tmp_path):
        from nanobio_studio.app.api.static_frontend import mount_frontend

        app = FastAPI()
        assert mount_frontend(app, tmp_path / "absent") is False

    def test_missing_build_is_not_fatal(self, tmp_path):
        """An API-only backend must still boot and serve."""
        from nanobio_studio.app.api.static_frontend import mount_frontend

        app = FastAPI()

        @app.get("/health")
        async def _health():
            return {"status": "healthy"}

        mount_frontend(app, tmp_path / "absent")
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200

    def test_serving_is_off_by_default(self):
        from nanobio_studio.app.core.config import Settings

        assert Settings().serve_frontend is False

    def test_default_dist_path_points_at_the_vite_build(self):
        from nanobio_studio.app.core.config import Settings

        assert Settings().frontend_dist_path == "frontend/dist"

    def test_relative_dist_path_resolves_against_the_repo_root(self):
        from nanobio_studio.app.api.static_frontend import resolve_dist_path

        resolved = resolve_dist_path("frontend/dist")
        assert resolved.is_absolute()
        assert resolved.parts[-2:] == ("frontend", "dist")

    def test_absolute_dist_path_is_left_alone(self, tmp_path):
        from nanobio_studio.app.api.static_frontend import resolve_dist_path

        assert resolve_dist_path(str(tmp_path)) == tmp_path


# ===========================================================================
# The live application, which defaults to API-only
# ===========================================================================


class TestLiveAppDefaults:

    def test_root_still_returns_the_service_descriptor(self):
        from nanobio_studio.app.vertical_slice import app

        with TestClient(app) as client:
            body = client.get("/").json()
        assert body["status"] == "running"
        assert "research use only" in body["notice"].lower()

    def test_descriptor_is_also_reachable_at_api(self):
        """So it survives `/` being taken over by the interface."""
        from nanobio_studio.app.vertical_slice import app

        with TestClient(app) as client:
            body = client.get("/api").json()
        assert body["status"] == "running"
        assert "/api/v1/design/score" in body["endpoints"]
