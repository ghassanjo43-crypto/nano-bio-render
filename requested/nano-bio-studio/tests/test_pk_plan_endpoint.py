"""HTTP contract for the pharmacokinetic model-plan endpoints.

The defect these exist for
--------------------------
Step 3 showed "Could not load the model plan / The service returned HTTP 404".
The routes were present in the source and registered in ``vertical_slice.py``,
but the **running** uvicorn process had been started before the module existed
and was launched without ``--reload``, so it never loaded them. Verifying the
routes with a fresh ``import app`` checked the source and said nothing about the
running service.

A unit test cannot catch a stale process — only hitting the live server can, and
``frontend/nav-walkthrough.mjs`` now does that. What these tests *can* pin is
everything that would make the path wrong on purpose: the exact paths the
frontend requests, the methods, the prefix, and the structured shape of the
blocked plan. If any of those drift, the 404 comes back for a reason a test can
see.

They also pin the safety property that matters most: **a failing or missing
planning service never yields a scientific result.**
"""

from __future__ import annotations

import re
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

from nanobio_studio.app.vertical_slice import app  # noqa: E402

#: The exact paths `frontend/src/api/client.ts` requests. Kept as literals so a
#: change on either side has to be made deliberately on both.
FRONTEND_PLAN_PATH = "/api/v1/pk/plan"
FRONTEND_ROUTES_PATH = "/api/v1/pk/administration-routes"
FRONTEND_SIMULATE_PATH = "/api/v1/pk/simulate-routed"

CLIENT_TS = REPO_ROOT / "frontend" / "src" / "api" / "client.ts"
PANEL_TSX = (REPO_ROOT / "frontend" / "src" / "pages" / "workflow"
             / "RoutedPKPanel.tsx")


def _registered() -> dict[str, set[str]]:
    """Path -> methods, as the FastAPI application actually registers them."""
    table: dict[str, set[str]] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            table.setdefault(path, set()).update(
                getattr(route, "methods", set()) or set())
    return table


# =========================================================================
class TestTheEndpointsExist:
    """Requirement 9.1 — the model-plan endpoint exists."""

    def test_plan_endpoint_is_registered(self):
        assert FRONTEND_PLAN_PATH in _registered()

    def test_plan_endpoint_accepts_GET(self):
        assert "GET" in _registered()[FRONTEND_PLAN_PATH]

    def test_administration_routes_endpoint_is_registered(self):
        assert "GET" in _registered()[FRONTEND_ROUTES_PATH]

    def test_routed_simulate_endpoint_is_registered(self):
        assert "POST" in _registered()[FRONTEND_SIMULATE_PATH]

    def test_the_legacy_depot_endpoint_is_untouched(self):
        # Adding the router must not have displaced the original endpoint.
        assert "POST" in _registered()["/api/v1/pk/simulate"]

    def test_the_router_is_included_not_merely_importable(self):
        """The failure mode was a router that existed but was not included.

        Importing the module proves nothing; being present in `app.routes` is
        the property that matters.
        """
        from nanobio_studio.app.api.routes import pk_routed

        declared = {r.path for r in pk_routed.router.routes}
        registered = set(_registered())
        assert declared, "pk_routed declares no routes"
        assert declared <= registered, (
            f"declared but not included in the app: {declared - registered}")


# =========================================================================
class TestFrontendAndBackendPathsMatch:
    """Requirement 9.2 — the frontend path matches the backend route."""

    def test_client_requests_exactly_the_registered_plan_path(self):
        source = CLIENT_TS.read_text(encoding="utf-8")
        # The client builds `/api/v1/pk/plan?...`; match the path portion.
        assert f"`{FRONTEND_PLAN_PATH}?" in source

    def test_client_requests_exactly_the_registered_routes_path(self):
        source = CLIENT_TS.read_text(encoding="utf-8")
        assert f"'{FRONTEND_ROUTES_PATH}'" in source

    def test_no_frontend_pk_path_is_unregistered(self):
        """Every /api/v1/pk/... literal in the client must be a real route."""
        source = CLIENT_TS.read_text(encoding="utf-8")
        found = set(re.findall(r"/api/v1/pk/[a-z0-9\-]+", source))
        registered = set(_registered())
        assert found, "no PK paths found in the client; the regex is stale"
        assert found <= registered, f"client calls unregistered: {found - registered}"

    def test_no_trailing_slash_variant_is_used(self):
        # FastAPI would 307-redirect a trailing slash; the client must not rely
        # on that, because a redirect drops credentials on some configurations.
        source = CLIENT_TS.read_text(encoding="utf-8")
        assert "/api/v1/pk/plan/" not in source
        assert "/api/v1/pk/administration-routes/" not in source

    def test_the_client_uses_a_relative_same_origin_path(self):
        """A cross-origin absolute URL would break the session cookie.

        The same-origin rule is already recorded in docs/VERTICAL_SLICE.md; this
        pins it for the PK endpoints specifically.
        """
        source = CLIENT_TS.read_text(encoding="utf-8")
        assert "http://127.0.0.1:8000/api/v1/pk" not in source
        assert "http://localhost:8000/api/v1/pk" not in source


# =========================================================================
class TestBlockedPlanShape:
    """Requirements 9.3-9.6 — IV trastuzumab returns a structured blocked plan."""

    @pytest.fixture
    def plan(self):
        from nanobio_studio.app.api.routes.pk_routed import _plan_to_dict
        from nanobio_studio.app.pk.administration import AdministrationRoute
        from nanobio_studio.app.pk.planning import build_plan

        return _plan_to_dict(build_plan(
            therapeutic="Trastuzumab (Herceptin)",
            route=AdministrationRoute.IV_INFUSION))

    def test_it_is_a_structured_plan_not_an_error(self, plan):
        # The endpoint answers 200 with a plan that says "blocked" — it does not
        # fail. A failure would be indistinguishable from the 404 being fixed.
        for key in ("runnable", "suitability", "missing_inputs",
                    "blocking_reasons", "not_applicable", "inputs"):
            assert key in plan

    def test_it_is_not_runnable(self, plan):
        assert plan["runnable"] is False

    def test_it_says_not_yet_operational(self, plan):
        assert "Not yet operational" in plan["suitability"]
        assert "Trastuzumab (Herceptin)" in plan["suitability"]
        assert "Intravenous infusion" in plan["suitability"]

    def test_it_names_the_missing_reviewed_parameters(self, plan):
        assert plan["missing_inputs"] == ["CL", "Vc", "Q", "Vp"]

    def test_it_explains_why_it_is_blocked(self, plan):
        joined = " ".join(plan["blocking_reasons"])
        assert "No reviewed pharmacokinetic parameter set" in joined

    def test_no_k_abs_is_requested_for_iv_infusion(self, plan):
        assert "k_abs" in plan["not_applicable"]
        assert not any(i["name"] == "k_abs" for i in plan["inputs"])

    def test_it_carries_no_parameter_set(self, plan):
        assert plan["parameter_set"] is None

    def test_it_offers_no_rate_constant_for_the_user_to_invent(self, plan):
        offered = {i["name"] for i in plan["inputs"]}
        for constant in ("k_abs", "k_el", "k_12", "k_21", "kabs", "kel"):
            assert constant not in offered

    def test_it_carries_no_scientific_result(self, plan):
        """A blocked plan must contain no calculated pharmacokinetic value."""
        import json

        blob = json.dumps(plan).lower()
        for forbidden in ("half_life", "auc", "c_max", "peak_concentration",
                          "concentration_time", "clearance_value"):
            assert forbidden not in blob

    def test_it_states_the_research_use_only_notice(self, plan):
        assert "Research Use Only" in plan["notice"]

    def test_bioavailability_is_not_attributed_to_a_citation(self, plan):
        """F = 1 for IV is a property of the route, not a cited parameter.

        It was originally labelled "From cited parameter set" — a citation that
        does not exist, for a combination that has no parameter set at all.
        """
        f = next(i for i in plan["inputs"] if i["name"] == "bioavailability")
        assert f["source"] == "route_definition"
        assert f["source_label"] == "Fixed by administration route"
        assert f["editable"] is False

    def test_no_input_claims_a_parameter_library_source_when_none_exists(
            self, plan):
        assert plan["parameter_set"] is None
        assert not [i for i in plan["inputs"]
                    if i["source"] == "parameter_library"]

    def test_no_fitted_parameter_is_offered(self, plan):
        offered = {i["name"] for i in plan["inputs"]}
        assert not offered & {"CL", "Vc", "Q", "Vp"}


# =========================================================================
class TestFailureNeverProducesResults:
    """Requirement 9.7 — 404s and service failures never yield science."""

    def test_an_unknown_route_is_a_structured_error_with_no_data(self):
        from fastapi.testclient import TestClient
        from nanobio_studio.app.api.deps_auth import get_current_user
        from nanobio_studio.app.db.auth_models import User, UserRole

        app.dependency_overrides[get_current_user] = lambda: User(
            id=1, username="t", password_hash="x", role=UserRole.RESEARCHER,
            is_active=True)
        try:
            with TestClient(app) as client:
                r = client.get(FRONTEND_PLAN_PATH,
                               params={"therapeutic": "X", "route": "teleport"})
            assert r.status_code == 400
            body = r.json()
            assert body["error"] == "unknown_route"
            assert body["data_available"] is False
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_simulate_refuses_without_provenance_confirmation(self):
        from fastapi.testclient import TestClient
        from nanobio_studio.app.api.deps_auth import get_current_user
        from nanobio_studio.app.db.auth_models import User, UserRole

        app.dependency_overrides[get_current_user] = lambda: User(
            id=1, username="t", password_hash="x", role=UserRole.RESEARCHER,
            is_active=True)
        try:
            with TestClient(app) as client:
                r = client.post(FRONTEND_SIMULATE_PATH, json={
                    "therapeutic": "Trastuzumab (Herceptin)",
                    "route": "iv_infusion", "dose_basis": "per_kg",
                    "dose_amount": 6.0, "body_weight_kg": 68.0,
                    "infusion_duration_h": 1.5,
                    "provenance_confirmed": False,
                })
            assert r.status_code == 400
            assert r.json()["error"] == "confirmation_required"
            assert r.json()["data_available"] is False
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_simulate_refuses_a_blocked_combination(self):
        from fastapi.testclient import TestClient
        from nanobio_studio.app.api.deps_auth import get_current_user
        from nanobio_studio.app.db.auth_models import User, UserRole

        app.dependency_overrides[get_current_user] = lambda: User(
            id=1, username="t", password_hash="x", role=UserRole.RESEARCHER,
            is_active=True)
        try:
            with TestClient(app) as client:
                r = client.post(FRONTEND_SIMULATE_PATH, json={
                    "therapeutic": "Trastuzumab (Herceptin)",
                    "route": "iv_infusion", "dose_basis": "per_kg",
                    "dose_amount": 6.0, "body_weight_kg": 68.0,
                    "infusion_duration_h": 1.5,
                    "provenance_confirmed": True,
                })
            assert r.status_code == 400
            body = r.json()
            assert body["error"] == "not_operational"
            assert body["data_available"] is False
            # No curve, no parameter, nothing that could be plotted.
            assert "concentration_time" not in body
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_both_endpoints_require_authentication(self):
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            for path in (FRONTEND_PLAN_PATH, FRONTEND_ROUTES_PATH):
                r = client.get(path, params={"therapeutic": "X",
                                             "route": "iv_bolus"})
                assert r.status_code == 401


# =========================================================================
class TestTheInterfaceCannotProceedWithoutAPlan:
    """Requirement: the frontend must not proceed to PK input on failure."""

    def test_the_panel_clears_the_plan_on_a_failed_request(self):
        source = PANEL_TSX.read_text(encoding="utf-8")
        # A failed plan request must null the plan, not leave a stale one.
        assert "setPlan(null);" in source
        assert "setServiceDown(true);" in source

    def test_the_panel_states_the_required_unavailable_message(self):
        source = PANEL_TSX.read_text(encoding="utf-8")
        assert "The PK planning service is unavailable" in source
        assert "No simulation has been run" in source
        assert "no parameters were inferred" in source

    def test_the_run_action_is_gated_on_a_runnable_plan(self):
        source = PANEL_TSX.read_text(encoding="utf-8")
        # Run only renders inside `plan?.runnable`, so a null plan cannot run.
        assert "{plan?.runnable && (" in source
