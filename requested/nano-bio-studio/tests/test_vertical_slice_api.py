"""Tests for the Phase 2 vertical slice: POST /api/v1/design/score.

The most important tests here are the **equivalence tests**, which assert that
the API returns bit-identical numbers to the canonical
``core/scoring.py::compute_impact()`` for the same golden-vector inputs. If those
ever diverge, the API is no longer serving the canonical science.

Nothing here touches a database.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import os  # noqa: E402
import tempfile  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ENDPOINT = "/api/v1/design/score"

MINIMAL = {"size_nm": 100, "charge_mv": -5, "encapsulation_percent": 85}

# ---------------------------------------------------------------------------
# Authenticated client
# ---------------------------------------------------------------------------
# The scoring endpoint became authenticated in the application-shell slice. The
# assertions below are unchanged -- in particular the bit-exact equivalence
# checks against the canonical function -- but every request now carries a real
# session cookie. Authentication is transport, not science: adding it must not
# alter a single number, and `test_api_matches_canonical_function_exactly`
# continues to prove that.
#
# A throwaway SQLite auth database is used. The real development database and
# the legacy users.db are never touched.

TEST_USER = "slice_test_user"
TEST_PASSWORD = "SliceTestPassword-2026!"

#: Populated by the autouse fixture below; test bodies reference it as `client`.
client: TestClient


@pytest.fixture(scope="module", autouse=True)
def _authenticated_client(tmp_path_factory):
    global client

    from tests.conftest import make_isolated_auth_client, run_async

    tmp_dir = tmp_path_factory.mktemp("slice_auth")
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


# ===========================================================================
# Health
# ===========================================================================


class TestHealth:
    def test_health_endpoint(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_ready_endpoint(self):
        assert client.get("/ready").status_code == 200

    def test_root_declares_research_use_only(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "research use only" in r.json()["notice"].lower()

    def test_openapi_schema_is_served(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert ENDPOINT in r.json()["paths"]


# ===========================================================================
# Request-schema validation
# ===========================================================================


class TestRequestSchemaValidation:

    @pytest.mark.parametrize("missing", ["size_nm", "charge_mv",
                                         "encapsulation_percent"])
    def test_required_fields_are_required(self, missing):
        payload = {k: v for k, v in MINIMAL.items() if k != missing}
        r = client.post(ENDPOINT, json=payload)
        assert r.status_code == 422
        body = r.json()
        assert body["error"] == "validation_error"
        assert body["score_available"] is False

    def test_required_fields_are_never_defaulted(self):
        """A required input must never be silently substituted."""
        r = client.post(ENDPOINT, json={"charge_mv": -5,
                                        "encapsulation_percent": 85})
        assert r.status_code == 422
        assert "design_impact_score" not in r.json()

    @pytest.mark.parametrize(
        "field, value",
        [
            ("size_nm", 0),           # gt=0
            ("size_nm", -10),
            ("charge_mv", 500),       # le=200
            ("encapsulation_percent", 101),   # le=100
            ("encapsulation_percent", -1),
            ("pdi", 1.5),             # le=1
        ],
    )
    def test_out_of_range_values_rejected(self, field, value):
        payload = dict(MINIMAL)
        payload[field] = value
        r = client.post(ENDPOINT, json=payload)
        assert r.status_code == 422
        assert r.json()["score_available"] is False

    def test_unknown_fields_are_rejected_not_ignored(self):
        payload = dict(MINIMAL)
        payload["not_a_real_field"] = 1
        assert client.post(ENDPOINT, json=payload).status_code == 422

    def test_malformed_body_is_rejected(self):
        r = client.post(ENDPOINT, content="this is not json",
                        headers={"Content-Type": "application/json"})
        assert r.status_code == 422
        assert r.json()["score_available"] is False

    def test_wrong_type_is_rejected(self):
        payload = dict(MINIMAL)
        payload["size_nm"] = "not-a-number"
        assert client.post(ENDPOINT, json=payload).status_code == 422

    def test_blank_list_entries_rejected(self):
        payload = dict(MINIMAL)
        payload["surface_coating"] = ["PEG (Stealth)", "  "]
        assert client.post(ENDPOINT, json=payload).status_code == 422


# ===========================================================================
# Successful scoring
# ===========================================================================


class TestSuccessfulScoring:

    def test_minimal_request_succeeds(self):
        r = client.post(ENDPOINT, json=MINIMAL)
        assert r.status_code == 200

    def test_response_contains_every_required_field(self):
        body = client.post(ENDPOINT, json=MINIMAL).json()
        for field in ("design_impact_score", "score_version", "component_scores",
                      "normalized_inputs", "warnings", "prediction_basis",
                      "evidence_level", "validation_status", "limitations"):
            assert field in body, f"missing response field {field}"

    def test_design_impact_score_has_three_canonical_values(self):
        score = client.post(ENDPOINT, json=MINIMAL).json()["design_impact_score"]
        assert set(score) == {"delivery", "toxicity", "cost"}
        assert 0.0 <= score["delivery"] <= 100.0
        assert 0.0 <= score["toxicity"] <= 10.0
        assert 0.0 <= score["cost"] <= 100.0

    def test_component_scores_carry_scale_and_meaning(self):
        comps = client.post(ENDPOINT, json=MINIMAL).json()["component_scores"]
        assert set(comps) == {"delivery", "toxicity", "cost"}
        for name, c in comps.items():
            assert isinstance(c["value"], float)
            assert c["scale"] and c["meaning"]

    def test_component_scores_match_the_headline_values(self):
        body = client.post(ENDPOINT, json=MINIMAL).json()
        for key in ("delivery", "toxicity", "cost"):
            assert body["component_scores"][key]["value"] == (
                body["design_impact_score"][key])

    def test_normalized_inputs_are_reported(self):
        body = client.post(ENDPOINT, json=MINIMAL).json()
        norm = body["normalized_inputs"]
        assert norm["Size"] == 100
        assert norm["Charge"] == -5
        assert norm["Encapsulation"] == 85
        assert norm["PDI"] == 0.15           # canonical default applied
        assert norm["HydrodynamicSize"] == 120.0   # derived: Size * 1.2

    def test_provenance_fields_are_honest(self):
        body = client.post(ENDPOINT, json=MINIMAL).json()
        assert body["prediction_basis"] == "rule_based_physicochemical_heuristic"
        assert body["evidence_level"] == "literature_informed_unvalidated"
        assert body["validation_status"] == "not_experimentally_validated"
        assert body["scientific_source"] == "core.scoring.compute_impact"
        assert body["score_version"]

    def test_limitations_disclaim_validation(self):
        limits = " ".join(client.post(ENDPOINT, json=MINIMAL).json()["limitations"])
        low = limits.lower()
        assert "not experimentally validated" in low
        assert "not clinically validated" in low
        assert "not a regulatory approval prediction" in low

    def test_full_request_succeeds(self):
        payload = {
            **MINIMAL,
            "pdi": 0.12, "hydrodynamic_size_nm": 118, "stability_percent": 90,
            "surface_area_nm2": 260, "degradation_time_days": 28,
            "crystallinity_index": 72, "hydrophobicity_logp": 1.4,
            "coating_thickness_nm": 3.0, "ligand_density_percent": 60,
            "receptor_binding_kd_nm": 10, "release_predictability_percent": 88,
            "ligand": "GalNAc", "surface_coating": ["PEG (Stealth)"],
            "functional_groups": ["-COOH (Carboxyl)"],
        }
        assert client.post(ENDPOINT, json=payload).status_code == 200


# ===========================================================================
# Null / missing input handling (DEFECT-D9 contract)
# ===========================================================================


class TestNullAndMissingInputs:

    OPTIONAL_FIELDS = [
        "pdi", "stability_percent", "surface_area_nm2", "degradation_time_days",
        "crystallinity_index", "hydrophobicity_logp", "coating_thickness_nm",
        "ligand_density_percent", "receptor_binding_kd_nm",
        "release_predictability_percent", "ligand", "surface_coating",
        "functional_groups",
    ]

    @pytest.mark.parametrize("field", OPTIONAL_FIELDS)
    def test_explicit_null_equals_omitted(self, field):
        """The Step 1 D9 contract, enforced at the API boundary."""
        omitted = client.post(ENDPOINT, json=dict(MINIMAL))
        with_null = client.post(ENDPOINT, json={**MINIMAL, field: None})

        assert omitted.status_code == 200
        assert with_null.status_code == 200
        assert (with_null.json()["design_impact_score"]
                == omitted.json()["design_impact_score"]), (
            f"null {field} produced a different score than omitting it")

    def test_null_required_field_is_rejected_not_defaulted(self):
        r = client.post(ENDPOINT, json={**MINIMAL, "size_nm": None})
        assert r.status_code == 422
        assert "design_impact_score" not in r.json()

    def test_nulls_are_reported_in_warnings(self):
        body = client.post(ENDPOINT, json={**MINIMAL, "pdi": None}).json()
        assert any("null" in w.lower() for w in body["warnings"])


# ===========================================================================
# Failure never yields a favourable score
# ===========================================================================


class TestFailuresNeverProduceScores:

    def test_calculation_failure_returns_no_score(self, monkeypatch):
        """Force the canonical function to raise; assert no number comes back."""
        from nanobio_studio.app.services import design_scoring

        def _boom(*a, **k):
            raise RuntimeError("simulated calculation failure")

        monkeypatch.setattr(design_scoring, "compute_impact", _boom)

        r = client.post(ENDPOINT, json=MINIMAL)
        assert r.status_code == 500
        body = r.json()
        assert body["score_available"] is False
        assert body["error"] == "calculation_failed"
        assert "design_impact_score" not in body
        assert "component_scores" not in body

    def test_non_finite_result_is_a_failure_not_a_score(self, monkeypatch):
        from nanobio_studio.app.services import design_scoring

        monkeypatch.setattr(
            design_scoring, "compute_impact",
            lambda *a, **k: {"Delivery": float("nan"), "Toxicity": 1.0,
                             "Cost": 10.0})

        r = client.post(ENDPOINT, json=MINIMAL)
        assert r.status_code == 500
        assert r.json()["score_available"] is False

    @pytest.mark.parametrize("legacy_value", [92, 89, 82, 94.2, 91.5, 87.3])
    def test_deprecated_hardcoded_scores_never_appear(self, legacy_value,
                                                      monkeypatch):
        """No response path may emit the retired headline or mock values."""
        from nanobio_studio.app.services import design_scoring

        # success path
        ok = client.post(ENDPOINT, json=MINIMAL).json()
        assert ok["design_impact_score"] != {"delivery": legacy_value,
                                             "toxicity": legacy_value,
                                             "cost": legacy_value}

        # failure path must contain no numbers at all
        monkeypatch.setattr(design_scoring, "compute_impact",
                            lambda *a, **k: (_ for _ in ()).throw(
                                RuntimeError("fail")))
        err = client.post(ENDPOINT, json=MINIMAL).json()
        assert str(legacy_value) not in str(err.get("message", ""))
        assert err["score_available"] is False

    def test_error_body_shape_is_structured(self, monkeypatch):
        from nanobio_studio.app.services import design_scoring

        monkeypatch.setattr(design_scoring, "compute_impact",
                            lambda *a, **k: (_ for _ in ()).throw(
                                RuntimeError("fail")))
        body = client.post(ENDPOINT, json=MINIMAL).json()
        assert set(body) == {"error", "message", "detail", "score_available"}


# ===========================================================================
# EQUIVALENCE: API result == canonical legacy function
# ===========================================================================


class TestCanonicalEquivalence:
    """The API must return exactly what the legacy function returns."""

    @staticmethod
    def _api_to_canonical(design: dict) -> dict:
        """Map a canonical CapitalCase design to the API's snake_case body."""
        from nanobio_studio.app.schemas.design_score import DesignScoreRequest

        reverse = {v: k for k, v in DesignScoreRequest.FIELD_MAP.items()}
        body = {}
        for canonical, value in design.items():
            if canonical in reverse:
                body[reverse[canonical]] = value
        return body

    @pytest.mark.parametrize(
        "vector_name",
        [
            "app_default", "minimal_required_keys", "size_50_below_optimal",
            "size_80_lower_bound", "size_120_upper_bound", "size_200_oversized",
            "charge_zero", "charge_pos40_high", "encap_40_low", "encap_100_max",
            "pdi_zero", "pdi_045_high", "ligand_none_passive",
            "ligand_unknown_cost_default", "coating_all_four",
            "coating_empty_list", "hydrophobicity_5_toxic",
            "crystallinity_20_low", "functional_groups_all", "stability_low",
        ],
    )
    def test_api_matches_canonical_function_exactly(self, vector_name):
        from core.scoring import compute_impact
        from tests.golden_vectors.inputs import SCORING_DESIGNS

        design = SCORING_DESIGNS[vector_name]
        expected = compute_impact(dict(design))

        body = self._api_to_canonical(design)
        r = client.post(ENDPOINT, json=body)
        assert r.status_code == 200, f"{vector_name}: {r.json()}"
        got = r.json()["design_impact_score"]

        assert got["delivery"] == expected["Delivery"], (
            f"{vector_name}: delivery drifted "
            f"{expected['Delivery']!r} -> {got['delivery']!r}")
        assert got["toxicity"] == expected["Toxicity"]
        assert got["cost"] == expected["Cost"]

    def test_equivalence_is_bit_exact_not_approximate(self):
        """Guard against silent rounding in the transport layer."""
        from core.scoring import compute_impact
        from tests.golden_vectors.inputs import SCORING_DESIGNS

        design = SCORING_DESIGNS["app_default"]
        expected = compute_impact(dict(design))
        got = client.post(ENDPOINT,
                          json=self._api_to_canonical(design)).json()

        assert repr(got["design_impact_score"]["delivery"]) == repr(
            expected["Delivery"]), "value was rounded in transit"


# ===========================================================================
# Scientific restrictions
# ===========================================================================


class TestScientificRestrictions:

    def test_no_composite_overall_score_is_returned(self):
        """DECISION 2: the replacement Overall Score is NOT implemented."""
        body = client.post(ENDPOINT, json=MINIMAL).json()
        assert "overall_score" not in body
        assert "overall_score" not in body["design_impact_score"]
        assert set(body["design_impact_score"]) == {"delivery", "toxicity",
                                                    "cost"}

    def test_no_assessment_engine_output_is_mixed_in(self):
        """Design score must not be combined with the assessment engines."""
        body = client.post(ENDPOINT, json=MINIMAL).json()
        for forbidden in ("safety_risk_profile", "disease_fit",
                          "manufacturability", "regulatory_assessment",
                          "confidence"):
            assert forbidden not in body

    def test_score_is_not_named_overall_score(self):
        body = client.post(ENDPOINT, json=MINIMAL).json()
        assert "design_impact_score" in body
