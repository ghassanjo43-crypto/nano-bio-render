"""Tests for the PK migration slice: POST /api/v1/pk/simulate.

The most important tests here are the **legacy-equivalence tests**, which assert
that the migrated path returns bit-identical numbers to a direct call of
``utils/pk_model.py`` for the same golden-vector inputs. If those ever diverge,
the API is no longer serving the legacy pharmacokinetic model.

The second most important group is the honesty set: a failed or rejected
calculation must produce no curve, no half-life and no AUC, and the API must
never report a quantity the migrated model does not produce (notably clearance).

Nothing here touches a database.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import subprocess  # noqa: E402
import textwrap  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ENDPOINT = "/api/v1/pk/simulate"

#: A complete, in-bounds request. Every scientifically required field present.
VALID = {
    "dose_mg_kg": 3.0,
    "kabs_per_h": 0.5,
    "kel_per_h": 0.1,
    "k12_per_h": 0.2,
    "k21_per_h": 0.05,
}

REQUIRED_FIELDS = ("dose_mg_kg", "kabs_per_h", "kel_per_h", "k12_per_h",
                   "k21_per_h")

#: Golden vectors whose values fall inside the legacy Streamlit widget ranges
#: that the request schema reproduces, so they are reachable over HTTP.
API_REACHABLE_VECTORS = (
    "nominal_48h",
    "fast_elimination",
    "slow_absorption",
    "high_peripheral_partition",
)

#: Golden vectors that the legacy UI itself could not produce, because a value
#: sits outside the widget range. They are exercised against the service, and
#: asserted to be *rejected* over HTTP.
API_UNREACHABLE_VECTORS = (
    "short_duration_6h",     # duration 6 h, below the legacy minimum of 12
    "zero_dose_edge",        # dose 0, below the legacy minimum of 0.1
    "no_elimination_edge",   # k_el 0, below the legacy minimum of 0.001
)

TEST_USER = "pk_slice_test_user"
TEST_PASSWORD = "PkSliceTestPassword-2026!"

#: Populated by the autouse fixture below; test bodies reference it as `client`.
client: TestClient


@pytest.fixture(scope="module", autouse=True)
def _authenticated_client(tmp_path_factory):
    global client

    from tests.conftest import make_isolated_auth_client, run_async

    tmp_dir = tmp_path_factory.mktemp("pk_slice_auth")
    app, test_client, factory = make_isolated_auth_client(tmp_dir)

    from nanobio_studio.app.db.auth_models import UserRole
    from nanobio_studio.app.services.auth_service import create_user

    async def _seed():
        async with factory() as session:
            try:
                await create_user(session, username=TEST_USER,
                                  password=TEST_PASSWORD,
                                  role=UserRole.RESEARCHER)
            except ValueError:
                pass
            await session.commit()

    run_async(_seed())

    with test_client:
        login = test_client.post("/api/v1/auth/login",
                                 json={"username": TEST_USER,
                                       "password": TEST_PASSWORD})
        assert login.status_code == 200, f"test login failed: {login.text}"
        client = test_client
        yield test_client

    app.dependency_overrides.clear()


def _legacy_run(params: dict):
    """Call the legacy implementation directly, exactly as Streamlit did."""
    from utils.pk_model import calculate_pk_parameters, two_compartment_model

    time, c_plasma, c_tissue = two_compartment_model(**params)
    return time, c_plasma, c_tissue, calculate_pk_parameters(
        time, c_plasma, c_tissue)


def _to_api_body(params: dict) -> dict:
    """Map legacy keyword names onto the API's snake_case field names."""
    from nanobio_studio.app.schemas.pk_simulation import PKSimulationRequest

    reverse = {v: k for k, v in PKSimulationRequest.FIELD_MAP.items()}
    return {reverse[k]: v for k, v in params.items() if k in reverse}


# ===========================================================================
# Registration
# ===========================================================================


class TestEndpointRegistration:

    def test_endpoint_is_in_the_openapi_document(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert ENDPOINT in r.json()["paths"]

    def test_endpoint_is_versioned_under_api_v1(self):
        assert ENDPOINT.startswith("/api/v1/")

    def test_root_lists_the_pk_endpoint(self):
        assert ENDPOINT in client.get("/").json()["endpoints"]

    def test_design_scoring_endpoint_still_works(self):
        """The PK slice must not disturb the already-migrated calculation."""
        r = client.post("/api/v1/design/score",
                        json={"size_nm": 100, "charge_mv": -5,
                              "encapsulation_percent": 85})
        assert r.status_code == 200
        assert r.json()["design_impact_score"]["delivery"] == 87.52475247524752


# ===========================================================================
# Required inputs — no calculation without them
# ===========================================================================


class TestRequiredInputs:

    @pytest.mark.parametrize("missing", REQUIRED_FIELDS)
    def test_every_scientific_input_is_required(self, missing):
        body = {k: v for k, v in VALID.items() if k != missing}
        r = client.post(ENDPOINT, json=body)
        assert r.status_code == 422
        assert r.json()["error"] == "validation_error"

    @pytest.mark.parametrize("missing", REQUIRED_FIELDS)
    def test_missing_input_produces_no_numbers(self, missing):
        body = {k: v for k, v in VALID.items() if k != missing}
        payload = r"" + client.post(ENDPOINT, json=body).text
        assert "concentration_time" not in payload
        assert "pk_parameters" not in payload
        assert "half_life" not in payload

    @pytest.mark.parametrize("missing", REQUIRED_FIELDS)
    def test_missing_input_flags_results_unavailable(self, missing):
        body = {k: v for k, v in VALID.items() if k != missing}
        assert client.post(ENDPOINT, json=body).json()["results_available"] is False

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_explicit_null_is_not_treated_as_a_default(self, field):
        """Unlike the optional window settings, a null scientific input fails.

        Substituting a value here would invent the pharmacokinetics being
        reported, so null is rejected rather than defaulted.
        """
        body = dict(VALID)
        body[field] = None
        assert client.post(ENDPOINT, json=body).status_code == 422

    def test_empty_body_is_rejected(self):
        r = client.post(ENDPOINT, json={})
        assert r.status_code == 422
        assert r.json()["results_available"] is False

    def test_service_rejects_missing_input_without_defaulting(self):
        from nanobio_studio.app.services.pk_simulation import (
            PKSimulationFailure, simulate_pk)

        with pytest.raises(PKSimulationFailure) as exc:
            simulate_pk({"dose": 3.0, "kabs": 0.5, "kel": 0.1, "k12": 0.2})
        assert exc.value.code == "missing_required_input"
        assert "k21" in exc.value.message


# ===========================================================================
# Invalid inputs
# ===========================================================================


class TestInvalidInputs:

    @pytest.mark.parametrize("field,value", [
        ("dose_mg_kg", 0.0),        # below legacy minimum 0.1
        ("dose_mg_kg", 1000.0),     # above legacy maximum 100
        ("kabs_per_h", 0.0),        # below legacy minimum 0.01
        ("kabs_per_h", 50.0),       # above legacy maximum 5.0
        ("kel_per_h", 0.0),         # below legacy minimum 0.001
        ("kel_per_h", 10.0),        # above legacy maximum 2.0
        ("k12_per_h", -0.5),        # negative rate constant
        ("k21_per_h", -1.0),        # negative rate constant
        ("duration_h", 0),          # below legacy minimum 12
        ("duration_h", 10_000),     # above legacy maximum 168
    ])
    def test_out_of_range_values_are_rejected(self, field, value):
        body = dict(VALID)
        body[field] = value
        r = client.post(ENDPOINT, json=body)
        assert r.status_code == 422, r.text
        assert r.json()["results_available"] is False

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_non_numeric_values_are_rejected(self, field):
        body = dict(VALID)
        body[field] = "not-a-number"
        assert client.post(ENDPOINT, json=body).status_code == 422

    @pytest.mark.parametrize("bad_step", [0.0, -0.1, 0.07, 2.0, 3.5])
    def test_time_step_must_be_a_legacy_choice(self, bad_step):
        """The step size is part of the model's numerical identity."""
        body = dict(VALID)
        body["time_step_h"] = bad_step
        r = client.post(ENDPOINT, json=body)
        assert r.status_code == 422, r.text
        assert r.json()["results_available"] is False

    @pytest.mark.parametrize("good_step", [0.05, 0.1, 0.25, 0.5, 1.0])
    def test_legacy_time_steps_are_accepted(self, good_step):
        body = dict(VALID)
        body["time_step_h"] = good_step
        assert client.post(ENDPOINT, json=body).status_code == 200

    def test_unknown_fields_are_rejected_not_ignored(self):
        body = dict(VALID)
        body["disease"] = "Liver Cancer (HCC)"
        r = client.post(ENDPOINT, json=body)
        assert r.status_code == 422, (
            "The model takes no disease input; silently ignoring one would "
            "imply the selection influences the result.")

    def test_rejected_request_returns_no_partial_profile(self):
        body = dict(VALID)
        body["kel_per_h"] = 99.0
        payload = client.post(ENDPOINT, json=body).text
        for forbidden in ("time_h", "central_plasma", "auc_central",
                          "peak_concentration_central"):
            assert forbidden not in payload

    def test_service_rejects_a_non_finite_input(self):
        from nanobio_studio.app.services.pk_simulation import (
            PKSimulationFailure, simulate_pk)

        with pytest.raises(PKSimulationFailure) as exc:
            simulate_pk({"dose": float("nan"), "kabs": 0.5, "kel": 0.1,
                         "k12": 0.2, "k21": 0.05})
        assert exc.value.code == "invalid_input_value"

    @pytest.mark.parametrize("window", [
        {"dt": 0.0}, {"dt": -1.0}, {"duration": 0.0}, {"duration": -5.0},
        {"duration": 1.0, "dt": 10.0},
    ])
    def test_service_rejects_an_unusable_integration_window(self, window):
        from nanobio_studio.app.services.pk_simulation import (
            PKSimulationFailure, simulate_pk)

        with pytest.raises(PKSimulationFailure) as exc:
            simulate_pk({**{"dose": 3.0, "kabs": 0.5, "kel": 0.1,
                            "k12": 0.2, "k21": 0.05}, **window})
        assert exc.value.code == "invalid_input_value"


# ===========================================================================
# Successful calculation
# ===========================================================================


class TestSuccessfulSimulation:

    def test_returns_200_for_a_complete_request(self):
        assert client.post(ENDPOINT, json=VALID).status_code == 200

    def test_response_carries_a_concentration_time_profile(self):
        body = client.post(ENDPOINT, json=VALID).json()
        series = body["concentration_time"]
        assert series["point_count"] == len(series["time_h"]) == 481
        assert len(series["central_plasma"]) == series["point_count"]
        assert len(series["peripheral_tissue"]) == series["point_count"]

    def test_all_three_series_have_equal_length(self):
        s = client.post(ENDPOINT, json=VALID).json()["concentration_time"]
        assert len({len(s["time_h"]), len(s["central_plasma"]),
                    len(s["peripheral_tissue"])}) == 1

    def test_response_carries_every_parameter_the_model_produces(self):
        params = client.post(ENDPOINT, json=VALID).json()["pk_parameters"]
        assert set(params) == {
            "peak_concentration_central", "peak_concentration_peripheral",
            "time_to_peak_central_h", "time_to_peak_peripheral_h",
            "auc_central", "auc_peripheral", "half_life_central_h",
            "tissue_accumulation_ratio", "vss_ratio",
        }

    def test_response_carries_a_calculation_version(self):
        body = client.post(ENDPOINT, json=VALID).json()
        assert body["calculation_version"]
        assert body["model_name"] == "two_compartment_depot_forward_euler"

    def test_response_reports_normalized_inputs(self):
        norm = client.post(ENDPOINT, json=VALID).json()["normalized_inputs"]
        assert norm == {"dose": 3.0, "kabs": 0.5, "kel": 0.1, "k12": 0.2,
                        "k21": 0.05, "duration": 48.0, "dt": 0.1}

    def test_response_carries_assumptions_warnings_and_limitations(self):
        body = client.post(ENDPOINT, json=VALID).json()
        assert body["assumptions"]
        assert body["limitations"]
        assert isinstance(body["warnings"], list)

    def test_response_carries_a_validation_status(self):
        body = client.post(ENDPOINT, json=VALID).json()
        assert body["validation_status"] == "not_experimentally_validated"
        assert body["scientific_source"].startswith("utils.pk_model")

    def test_defaulted_window_is_reported_as_a_warning(self):
        warnings = " ".join(client.post(ENDPOINT, json=VALID).json()["warnings"])
        assert "default" in warnings.lower()
        assert "48" in warnings and "0.1" in warnings

    def test_supplied_window_is_used_verbatim(self):
        body = dict(VALID)
        body["duration_h"] = 24
        body["time_step_h"] = 0.5
        result = client.post(ENDPOINT, json=body).json()
        assert result["normalized_inputs"]["duration"] == 24
        assert result["normalized_inputs"]["dt"] == 0.5
        assert result["concentration_time"]["point_count"] == 49

    def test_non_default_step_is_flagged_as_not_interchangeable(self):
        body = dict(VALID)
        body["time_step_h"] = 1.0
        warnings = " ".join(client.post(ENDPOINT, json=body).json()["warnings"])
        assert "not interchangeable" in warnings

    def test_concentration_unit_is_not_claimed_to_be_mass_per_volume(self):
        series = client.post(ENDPOINT, json=VALID).json()["concentration_time"]
        assert "arbitrary" in series["concentration_unit"].lower()
        assert "ng/ml" not in series["concentration_unit"].lower()


# ===========================================================================
# Legacy equivalence — the point of the whole slice
# ===========================================================================


class TestLegacyEquivalence:
    """The migrated path must return exactly what the legacy code returns."""

    @pytest.mark.parametrize("vector_name", API_REACHABLE_VECTORS)
    def test_api_matches_legacy_parameters_exactly(self, vector_name):
        from tests.golden_vectors.inputs import PK_PARAM_SETS

        params = PK_PARAM_SETS[vector_name]
        _, _, _, legacy = _legacy_run(dict(params))

        r = client.post(ENDPOINT, json=_to_api_body(params))
        assert r.status_code == 200, f"{vector_name}: {r.text}"
        got = r.json()["pk_parameters"]

        pairs = [
            ("peak_concentration_central", "C_max_plasma"),
            ("peak_concentration_peripheral", "C_max_tissue"),
            ("time_to_peak_central_h", "T_max_plasma"),
            ("time_to_peak_peripheral_h", "T_max_tissue"),
            ("auc_central", "AUC_plasma"),
            ("auc_peripheral", "AUC_tissue"),
            ("half_life_central_h", "t_half_plasma"),
            ("tissue_accumulation_ratio", "tissue_accumulation_ratio"),
            ("vss_ratio", "Vss_ratio"),
        ]
        for api_key, legacy_key in pairs:
            expected = legacy[legacy_key]
            expected = None if expected is None else float(expected)
            assert got[api_key] == expected, (
                f"{vector_name}: {api_key} drifted "
                f"{expected!r} -> {got[api_key]!r}")

    @pytest.mark.parametrize("vector_name", API_REACHABLE_VECTORS)
    def test_api_matches_the_legacy_curve_point_for_point(self, vector_name):
        from tests.golden_vectors.inputs import PK_PARAM_SETS

        params = PK_PARAM_SETS[vector_name]
        time, c_plasma, c_tissue, _ = _legacy_run(dict(params))

        series = client.post(ENDPOINT,
                             json=_to_api_body(params)).json()["concentration_time"]
        assert series["time_h"] == [float(v) for v in time]
        assert series["central_plasma"] == [float(v) for v in c_plasma]
        assert series["peripheral_tissue"] == [float(v) for v in c_tissue]

    @pytest.mark.parametrize("vector_name", API_REACHABLE_VECTORS)
    def test_equivalence_is_bit_exact_not_approximate(self, vector_name):
        """Guard against silent rounding or resampling in the transport layer."""
        from tests.golden_vectors.inputs import PK_PARAM_SETS

        params = PK_PARAM_SETS[vector_name]
        _, c_plasma, _, legacy = _legacy_run(dict(params))

        body = client.post(ENDPOINT, json=_to_api_body(params)).json()
        assert repr(body["pk_parameters"]["auc_central"]) == repr(
            float(legacy["AUC_plasma"])), "AUC was rounded in transit"
        assert repr(body["concentration_time"]["central_plasma"][17]) == repr(
            float(c_plasma[17])), "a curve point was rounded in transit"

    @pytest.mark.parametrize(
        "vector_name",
        list(API_REACHABLE_VECTORS) + list(API_UNREACHABLE_VECTORS))
    def test_service_matches_legacy_for_every_golden_vector(self, vector_name):
        """Service-level equivalence, including the two numerical edge cases.

        ``zero_dose_edge`` and ``no_elimination_edge`` sit outside the legacy
        widget ranges the request schema reproduces, so they are unreachable
        over HTTP. They are still exercised here, against the same code path
        the endpoint uses.
        """
        from nanobio_studio.app.services.pk_simulation import simulate_pk
        from tests.golden_vectors.inputs import PK_PARAM_SETS

        params = dict(PK_PARAM_SETS[vector_name])
        time, c_plasma, c_tissue, legacy = _legacy_run(dict(params))

        result = simulate_pk(params)
        series = result["concentration_time"]
        assert series["time_h"] == [float(v) for v in time]
        assert series["central_plasma"] == [float(v) for v in c_plasma]
        assert series["peripheral_tissue"] == [float(v) for v in c_tissue]

        got = result["pk_parameters"]
        assert got["peak_concentration_central"] == float(legacy["C_max_plasma"])
        assert got["auc_central"] == float(legacy["AUC_plasma"])
        assert got["auc_peripheral"] == float(legacy["AUC_tissue"])
        assert got["vss_ratio"] == float(legacy["Vss_ratio"])
        expected_half = legacy["t_half_plasma"]
        assert got["half_life_central_h"] == (
            None if expected_half is None else float(expected_half))

    @pytest.mark.parametrize("vector_name", API_UNREACHABLE_VECTORS)
    def test_out_of_legacy_range_vectors_are_rejected_not_clamped(
            self, vector_name):
        """A value the legacy UI could not produce is refused, never clamped."""
        from tests.golden_vectors.inputs import PK_PARAM_SETS

        params = PK_PARAM_SETS[vector_name]
        r = client.post(ENDPOINT, json=_to_api_body(params))
        assert r.status_code == 422, r.text
        assert r.json()["results_available"] is False
        assert "pk_parameters" not in r.text

    def test_authentication_did_not_change_a_single_number(self):
        """Auth is transport, not science."""
        from nanobio_studio.app.services.pk_simulation import simulate_pk
        from tests.golden_vectors.inputs import PK_PARAM_SETS

        params = dict(PK_PARAM_SETS["nominal_48h"])
        direct = simulate_pk(dict(params))
        over_http = client.post(ENDPOINT, json=_to_api_body(params)).json()
        assert over_http["pk_parameters"] == direct["pk_parameters"]

    def test_repeated_requests_are_deterministic(self):
        first = client.post(ENDPOINT, json=VALID).json()
        second = client.post(ENDPOINT, json=VALID).json()
        assert first == second


# ===========================================================================
# The nullable half-life contract
# ===========================================================================


class TestNullableHalfLife:
    """The legacy model reports an unknown half-life as None. So must the API."""

    def test_half_life_is_null_when_the_curve_never_halves(self):
        """A very slow elimination over a short window never halves."""
        body = {"dose_mg_kg": 3.0, "kabs_per_h": 0.5, "kel_per_h": 0.001,
                "k12_per_h": 0.01, "k21_per_h": 0.01, "duration_h": 12}
        r = client.post(ENDPOINT, json=body)
        assert r.status_code == 200, r.text
        result = r.json()

        _, _, _, legacy = _legacy_run({
            "dose": 3.0, "kabs": 0.5, "kel": 0.001, "k12": 0.01, "k21": 0.01,
            "duration": 12, "dt": 0.1})
        assert legacy["t_half_plasma"] is None, (
            "test fixture no longer exercises the null branch")
        assert result["pk_parameters"]["half_life_central_h"] is None

    def test_null_half_life_is_explained_rather_than_estimated(self):
        body = {"dose_mg_kg": 3.0, "kabs_per_h": 0.5, "kel_per_h": 0.001,
                "k12_per_h": 0.01, "k21_per_h": 0.01, "duration_h": 12}
        warnings = " ".join(client.post(ENDPOINT, json=body).json()["warnings"])
        assert "half-life" in warnings.lower()
        assert "null" in warnings.lower()

    def test_null_half_life_does_not_suppress_the_rest_of_the_result(self):
        body = {"dose_mg_kg": 3.0, "kabs_per_h": 0.5, "kel_per_h": 0.001,
                "k12_per_h": 0.01, "k21_per_h": 0.01, "duration_h": 12}
        params = client.post(ENDPOINT, json=body).json()["pk_parameters"]
        assert params["auc_central"] > 0
        assert params["peak_concentration_central"] > 0


# ===========================================================================
# Calculation failure — never a favourable fallback
# ===========================================================================


class TestCalculationFailure:

    def test_non_finite_curve_is_a_failure_not_a_profile(self, monkeypatch):
        import numpy as np

        from nanobio_studio.app.services import pk_simulation

        def _diverged(**_kwargs):
            time = np.arange(0, 1.0, 0.1)
            bad = np.full(time.shape, np.inf)
            return time, bad, bad

        monkeypatch.setattr(pk_simulation, "two_compartment_model", _diverged)

        with pytest.raises(pk_simulation.PKSimulationFailure) as exc:
            pk_simulation.simulate_pk(
                {"dose": 3.0, "kabs": 0.5, "kel": 0.1, "k12": 0.2, "k21": 0.05})
        assert exc.value.code == "calculation_failed"

    def test_model_exception_becomes_a_structured_error(self, monkeypatch):
        from nanobio_studio.app.services import pk_simulation

        def _boom(**_kwargs):
            raise RuntimeError("solver exploded")

        monkeypatch.setattr(pk_simulation, "two_compartment_model", _boom)

        with pytest.raises(pk_simulation.PKSimulationFailure) as exc:
            pk_simulation.simulate_pk(
                {"dose": 3.0, "kabs": 0.5, "kel": 0.1, "k12": 0.2, "k21": 0.05})
        assert exc.value.code == "calculation_failed"
        assert "solver exploded" in (exc.value.detail or "")

    def test_parameter_derivation_failure_is_structured(self, monkeypatch):
        from nanobio_studio.app.services import pk_simulation

        def _boom(*_args, **_kwargs):
            raise ValueError("bad parameters")

        monkeypatch.setattr(pk_simulation, "calculate_pk_parameters", _boom)

        with pytest.raises(pk_simulation.PKSimulationFailure) as exc:
            pk_simulation.simulate_pk(
                {"dose": 3.0, "kabs": 0.5, "kel": 0.1, "k12": 0.2, "k21": 0.05})
        assert exc.value.code == "calculation_failed"

    def test_route_returns_500_and_no_numbers_on_failure(self, monkeypatch):
        from nanobio_studio.app.api.routes import pk as pk_route
        from nanobio_studio.app.services.pk_simulation import PKSimulationFailure

        def _fail(_payload):
            raise PKSimulationFailure(
                code="calculation_failed",
                message="The pharmacokinetic profile could not be calculated.",
                detail="synthetic failure")

        monkeypatch.setattr(pk_route, "simulate_pk", _fail)

        r = client.post(ENDPOINT, json=VALID)
        assert r.status_code == 500
        body = r.json()
        assert body["error"] == "calculation_failed"
        assert body["results_available"] is False
        assert "pk_parameters" not in body
        assert "concentration_time" not in body

    def test_input_failure_returns_400_not_a_default_profile(self, monkeypatch):
        from nanobio_studio.app.api.routes import pk as pk_route
        from nanobio_studio.app.services.pk_simulation import PKSimulationFailure

        def _fail(_payload):
            raise PKSimulationFailure(
                code="invalid_input_value",
                message="A pharmacokinetic input was rejected by the model.")

        monkeypatch.setattr(pk_route, "simulate_pk", _fail)

        r = client.post(ENDPOINT, json=VALID)
        assert r.status_code == 400
        assert r.json()["results_available"] is False

    def test_failure_body_has_no_numeric_field_at_all(self, monkeypatch):
        from nanobio_studio.app.api.routes import pk as pk_route
        from nanobio_studio.app.services.pk_simulation import PKSimulationFailure

        def _fail(_payload):
            raise PKSimulationFailure(code="calculation_failed",
                                      message="failed")

        monkeypatch.setattr(pk_route, "simulate_pk", _fail)

        body = client.post(ENDPOINT, json=VALID).json()
        assert not any(isinstance(v, (int, float)) and not isinstance(v, bool)
                       for v in body.values())


# ===========================================================================
# Scientific honesty
# ===========================================================================


class TestScientificHonesty:

    def test_clearance_is_not_returned(self):
        """The migrated model has no volume term, so it produces no clearance."""
        body = client.post(ENDPOINT, json=VALID).json()
        assert "clearance" not in body["pk_parameters"]
        assert not any("clearance" in k for k in body["pk_parameters"])

    def test_absence_of_clearance_is_stated_explicitly(self):
        body = client.post(ENDPOINT, json=VALID).json()
        listed = {q["quantity"] for q in body["quantities_not_produced"]}
        assert "clearance" in listed
        reason = next(q["reason"] for q in body["quantities_not_produced"]
                      if q["quantity"] == "clearance")
        assert "volume" in reason.lower()

    def test_other_underived_quantities_are_declared(self):
        listed = {q["quantity"] for q in
                  client.post(ENDPOINT, json=VALID).json()["quantities_not_produced"]}
        assert {"volume_of_distribution", "bioavailability",
                "auc_extrapolated_to_infinity"} <= listed

    def test_result_is_not_claimed_to_be_validated(self):
        body = client.post(ENDPOINT, json=VALID).json()
        assert body["validation_status"] == "not_experimentally_validated"
        text = " ".join(body["limitations"]).lower()
        assert "not experimentally" in text
        assert "not clinically validated" in text

    def test_no_clinical_interpretation_is_returned(self):
        """The legacy Streamlit page emitted clinical prose. This does not."""
        payload = client.post(ENDPOINT, json=VALID).text.lower()
        for phrase in ("excellent targeting", "favorable tissue targeting",
                       "may need pegylation", "consider dose adjustment",
                       "suitable for most therapeutic applications",
                       "optimal dosing regimen"):
            assert phrase not in payload

    def test_no_design_impact_score_is_mixed_in(self):
        body = client.post(ENDPOINT, json=VALID).json()
        for forbidden in ("design_impact_score", "delivery", "toxicity",
                          "cost", "score_version", "overall_score"):
            assert forbidden not in body

    def test_pk_version_is_distinct_from_the_score_version(self):
        from nanobio_studio.app.services.design_scoring import SCORE_VERSION
        from nanobio_studio.app.services.pk_simulation import (
            PK_CALCULATION_VERSION)

        assert PK_CALCULATION_VERSION != SCORE_VERSION

    def test_no_disease_or_therapeutic_context_reaches_the_calculation(self):
        """The disease selection is not an input and is not echoed as data.

        Prose that *disclaims* disease dependence is expected and is checked
        separately; this test looks only at the data-bearing fields.
        """
        body = client.post(ENDPOINT, json=VALID).json()
        assert set(body["normalized_inputs"]) == {
            "dose", "kabs", "kel", "k12", "k21", "duration", "dt"}
        data_fields = {
            "normalized_inputs": body["normalized_inputs"],
            "pk_parameters": body["pk_parameters"],
            "concentration_time": {
                k: v for k, v in body["concentration_time"].items()
                if not isinstance(v, list)},
        }
        rendered = repr(data_fields).lower()
        for term in ("disease", "indication", "subtype", "sorafenib", "hcc",
                     "therapeutic"):
            assert term not in rendered

    def test_limitations_state_that_rate_constants_are_inputs(self):
        text = " ".join(client.post(ENDPOINT, json=VALID).json()["limitations"])
        assert "rate constants are inputs, not predictions" in text.lower()

    def test_limitations_state_the_disease_independence(self):
        text = " ".join(
            client.post(ENDPOINT, json=VALID).json()["limitations"]).lower()
        assert "not inputs to this model" in text

    def test_assumptions_record_the_euler_numerical_identity(self):
        text = " ".join(
            client.post(ENDPOINT, json=VALID).json()["assumptions"]).lower()
        assert "forward-euler" in text
        assert "adaptive solver" in text

    def test_auc_is_not_claimed_to_be_extrapolated_to_infinity(self):
        text = " ".join(
            client.post(ENDPOINT, json=VALID).json()["limitations"]).lower()
        assert "auc(0-inf)" in text or "not auc(0-inf)" in text


# ===========================================================================
# Authentication
# ===========================================================================


class TestAuthentication:

    def test_simulation_requires_authentication(self):
        from nanobio_studio.app.vertical_slice import app

        with TestClient(app) as anonymous:
            r = anonymous.post(ENDPOINT, json=VALID)
        assert r.status_code == 401

    def test_unauthenticated_request_returns_no_numbers(self):
        from nanobio_studio.app.vertical_slice import app

        with TestClient(app) as anonymous:
            payload = anonymous.post(ENDPOINT, json=VALID).text
        assert "pk_parameters" not in payload
        assert "central_plasma" not in payload


# ===========================================================================
# Streamlit decoupling
# ===========================================================================


class TestStreamlitDecoupling:
    """The migrated calculation must not drag the Streamlit stack into the API.

    Run in a subprocess: a same-process check would be meaningless once any
    other test in the session has imported these modules for its own reasons.
    """

    def test_pk_service_imports_without_streamlit_or_matplotlib(self):
        script = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(REPO_ROOT)!r})
            sys.path.insert(0, {str(BACKEND_ROOT)!r})
            from nanobio_studio.app.services import pk_simulation
            pk_simulation.simulate_pk(
                {{"dose": 3.0, "kabs": 0.5, "kel": 0.1,
                  "k12": 0.2, "k21": 0.05}})
            leaked = [m for m in ("streamlit", "matplotlib")
                      if m in sys.modules]
            print("LEAKED:" + ",".join(leaked))
        """)
        proc = subprocess.run([sys.executable, "-c", script],
                              capture_output=True, text=True, cwd=str(REPO_ROOT))
        assert proc.returncode == 0, proc.stderr
        assert "LEAKED:\n" in proc.stdout or proc.stdout.strip() == "LEAKED:", (
            f"the PK service pulled in a UI dependency: {proc.stdout}")

    def test_legacy_pk_module_has_no_module_level_ui_import(self):
        import inspect

        from utils import pk_model

        source = inspect.getsource(pk_model)
        module_level = [line for line in source.splitlines()
                        if line.startswith(("import ", "from "))]
        joined = " ".join(module_level)
        assert "streamlit" not in joined
        assert "matplotlib" not in joined

    def test_the_solver_source_is_unchanged_by_the_decoupling(self):
        """Moving an import must not have touched the equations."""
        import inspect

        from utils import pk_model

        src = inspect.getsource(pk_model.two_compartment_model)
        assert "kabs * C_depot[i]" in src
        assert "- kel * C_plasma[i]" in src
        assert "- k12 * C_plasma[i]" in src
        assert "+ k21 * C_tissue[i]" in src
        assert "scipy" not in src
        sig = inspect.signature(pk_model.two_compartment_model)
        assert sig.parameters["dt"].default == 0.1
        assert sig.parameters["duration"].default == 48.0

    def test_plotting_still_works_for_the_legacy_page(self):
        """The lazy import must not have broken the Streamlit consumer."""
        import matplotlib
        matplotlib.use("Agg")

        from utils.pk_model import create_pk_plot

        time, c_plasma, c_tissue, params = _legacy_run(
            {"dose": 3.0, "kabs": 0.5, "kel": 0.1, "k12": 0.2, "k21": 0.05})
        fig = create_pk_plot(time, c_plasma, c_tissue, params,
                             {"Material": "Lipid NP", "Target": "Liver Cells"})
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)
