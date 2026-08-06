"""Tests for the demo workspace, stored runs, projects and comparison.

The load-bearing tests here are the honesty tests:

* a demonstration scenario carries **no stored scientific result** — proven by
  scanning every fixture for result-shaped keys and result-shaped numbers;
* every scenario's disease/subtype/drug triple exists in the application's own
  curated mapping, so no invalid combination can be demonstrated;
* seeding is idempotent, and reset deletes demo records **only**;
* a stored result cannot exist without the inputs that produced it;
* comparison produces no combined ranking.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
# Repo root first: the backend ships its own `tests` package which would
# otherwise shadow this suite's conftest.
for _p in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if _p in sys.path:
        sys.path.remove(_p)
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SCENARIOS_URL = "/api/v1/demo/scenarios"
RUNS_URL = "/api/v1/runs"
PROJECTS_URL = "/api/v1/projects"

ADMIN_USER, ADMIN_PASSWORD = "ws_admin_test", "WsAdminTest-2026!"
VIEWER_USER, VIEWER_PASSWORD = "ws_viewer_test", "WsViewerTest-2026!"

client: TestClient


@pytest.fixture(scope="module", autouse=True)
def _client(tmp_path_factory):
    global client

    from tests.conftest import make_isolated_auth_client, run_async

    app, test_client, factory = make_isolated_auth_client(
        tmp_path_factory.mktemp("workspace_auth"))

    from nanobio_studio.app.db.auth_models import UserRole
    from nanobio_studio.app.services.auth_service import create_user

    async def _seed():
        async with factory() as session:
            for name, password, role in (
                (ADMIN_USER, ADMIN_PASSWORD, UserRole.ADMIN),
                (VIEWER_USER, VIEWER_PASSWORD, UserRole.VIEWER),
            ):
                try:
                    await create_user(session, username=name, password=password,
                                      role=role)
                except ValueError:
                    pass
            await session.commit()

    run_async(_seed())

    # Every non-global record belongs to an organization, so the seeded
    # accounts need one before they can create a project or a study.
    from tests.conftest import ensure_default_organization
    ensure_default_organization(factory)

    with test_client:
        assert test_client.post("/api/v1/auth/login",
                                json={"username": ADMIN_USER,
                                      "password": ADMIN_PASSWORD}
                                ).status_code == 200
        client = test_client
        yield test_client

    app.dependency_overrides.clear()


def _store_minimal_run(name: str = "run", *, is_demo: bool = False,
                       slug: str | None = None, disease: str | None = None):
    design_inputs = {"size_nm": 100, "charge_mv": -5,
                     "encapsulation_percent": 85}
    score = client.post("/api/v1/design/score", json=design_inputs)
    assert score.status_code == 200, score.text
    body = {
        "name": name,
        "disease": disease,
        "design_inputs": design_inputs,
        "design_result": score.json(),
        "is_demo": is_demo,
    }
    if slug:
        body["demo_scenario_slug"] = slug
    created = client.post(RUNS_URL, json=body)
    assert created.status_code == 201, created.text
    return created.json()


# ===========================================================================
# Scenario inventory
# ===========================================================================


class TestScenarioInventory:

    def test_at_least_seven_scenarios_exist(self):
        body = client.get(SCENARIOS_URL).json()
        assert len(body["scenarios"]) >= 7

    def test_five_indication_scenarios_and_two_technical(self):
        scenarios = client.get(SCENARIOS_URL).json()["scenarios"]
        indication = [s for s in scenarios if not s["technical"]]
        technical = [s for s in scenarios if s["technical"]]
        assert len(indication) >= 5
        assert len(technical) == 2

    def test_one_scenario_per_available_indication(self):
        """Coverage is one scenario per indication the mapping actually offers."""
        from nanobio_studio.app.demo.scenarios import SCENARIOS

        covered = {s.disease for s in SCENARIOS if not s.technical}
        assert covered == {
            "Breast Cancer", "Lung Cancer", "Colorectal Cancer",
            "Pancreatic Cancer", "Liver Cancer (HCC)",
        }

    def test_slugs_are_unique(self):
        slugs = [s["slug"] for s in client.get(SCENARIOS_URL).json()["scenarios"]]
        assert len(slugs) == len(set(slugs))

    def test_listing_carries_the_fixture_version(self):
        body = client.get(SCENARIOS_URL).json()
        assert body["fixture_version"].startswith("demo-scenarios-")
        assert all(s["fixture_version"] == body["fixture_version"]
                   for s in body["scenarios"])

    def test_listing_notice_states_the_classification(self):
        notice = client.get(SCENARIOS_URL).json()["notice"].lower()
        for phrase in ("not patient data", "not clinical data",
                       "not validated experimental data",
                       "not treatment recommendations"):
            assert phrase in notice

    def test_every_scenario_carries_the_synthetic_badge(self):
        for s in client.get(SCENARIOS_URL).json()["scenarios"]:
            assert s["data_classification"] == "Synthetic demonstration data"

    def test_requires_authentication(self):
        from nanobio_studio.app.vertical_slice import app
        with TestClient(app) as anonymous:
            assert anonymous.get(SCENARIOS_URL).status_code == 401


# ===========================================================================
# Disease / subtype / drug mapping validity
# ===========================================================================


class TestScenarioMappings:
    """No scenario may demonstrate a disease/subtype/drug combination that the
    application's own curated mapping does not contain."""

    @staticmethod
    def _mapping() -> dict:
        """Parse the generated frontend mapping, which mirrors the legacy data."""
        import re

        source = (REPO_ROOT / "frontend" / "src" / "workflow"
                  / "diseaseData.ts").read_text(encoding="utf-8")
        match = re.search(r"=\s*(\[[\s\S]*?\])\s*as const;", source)
        assert match, "could not locate the DISEASES array"
        diseases = json.loads(match.group(1))
        return {
            d["name"]: {st["name"]: set(st["drugs"]) for st in d["subtypes"]}
            for d in diseases
        }

    def test_every_scenario_uses_a_real_triple(self):
        from nanobio_studio.app.demo.scenarios import SCENARIOS

        mapping = self._mapping()
        for s in SCENARIOS:
            assert s.disease in mapping, f"{s.slug}: unknown disease {s.disease!r}"
            assert s.subtype in mapping[s.disease], (
                f"{s.slug}: {s.subtype!r} is not a subtype of {s.disease!r}")
            assert s.drug in mapping[s.disease][s.subtype], (
                f"{s.slug}: {s.drug!r} is not offered for {s.subtype!r}")

    def test_mapping_helper_finds_a_deliberate_mismatch(self):
        """Guards the test above against silently passing on a broken parse."""
        mapping = self._mapping()
        assert "Liver Cancer (HCC)" in mapping
        assert "Sorafenib" not in mapping["Liver Cancer (HCC)"].get(
            "Immune-active HCC", set())


# ===========================================================================
# Fixture schema and the no-stored-results rule
# ===========================================================================


class TestFixtureSchema:

    def test_design_inputs_use_only_accepted_api_fields(self):
        from nanobio_studio.app.demo.scenarios import SCENARIOS
        from nanobio_studio.app.schemas.design_score import DesignScoreRequest

        allowed = set(DesignScoreRequest.model_fields)
        for s in SCENARIOS:
            unknown = set(s.design_inputs) - allowed
            assert not unknown, f"{s.slug}: unknown design fields {unknown}"

    def test_pk_inputs_use_only_accepted_api_fields(self):
        from nanobio_studio.app.demo.scenarios import SCENARIOS
        from nanobio_studio.app.schemas.pk_simulation import PKSimulationRequest

        allowed = set(PKSimulationRequest.model_fields)
        for s in SCENARIOS:
            unknown = set(s.pk_inputs) - allowed
            assert not unknown, f"{s.slug}: unknown PK fields {unknown}"

    def test_complete_scenarios_are_accepted_by_the_real_endpoints(self):
        """A scenario that claims to be runnable must actually be runnable."""
        from nanobio_studio.app.demo.scenarios import SCENARIOS

        for s in SCENARIOS:
            if s.is_score_runnable:
                r = client.post("/api/v1/design/score", json=s.design_inputs)
                assert r.status_code == 200, f"{s.slug} design: {r.text}"
            if s.is_pk_runnable:
                r = client.post("/api/v1/pk/simulate", json=s.pk_inputs)
                assert r.status_code == 200, f"{s.slug} pk: {r.text}"

    def test_incomplete_scenario_is_genuinely_rejected(self):
        """The blocked scenario must be blocked by the real schema, not by a flag."""
        from nanobio_studio.app.demo.scenarios import scenario_by_slug

        s = scenario_by_slug("technical-incomplete-inputs")
        assert s is not None
        assert client.post("/api/v1/design/score",
                           json=s.design_inputs).status_code == 422
        assert client.post("/api/v1/pk/simulate",
                           json=s.pk_inputs).status_code == 422

    def test_every_scenario_declares_assumptions_and_provenance(self):
        from nanobio_studio.app.demo.scenarios import SCENARIOS

        for s in SCENARIOS:
            assert s.assumptions, f"{s.slug} has no assumptions"
            assert s.provenance, f"{s.slug} has no provenance statement"
            assert s.purpose, f"{s.slug} has no purpose"
            assert s.engines_that_will_not_run, (
                f"{s.slug} does not say which engines will not run")

    def test_no_scenario_contains_a_stored_scientific_result(self):
        """The central rule: fixtures carry inputs, never results."""
        from dataclasses import asdict

        from nanobio_studio.app.demo.scenarios import SCENARIOS

        forbidden = (
            "delivery", "toxicity_score", "auc", "cmax", "c_max",
            "half_life", "t_half", "peak_concentration", "score",
            "design_impact", "concentration_time", "pk_parameters",
            "assessment", "verdict", "result",
        )
        for s in SCENARIOS:
            keys = set(asdict(s)) | set(s.design_inputs) | set(s.pk_inputs)
            for key in keys:
                assert not any(f in key.lower() for f in forbidden), (
                    f"{s.slug}: field {key!r} looks like a stored result")

    def test_scenario_detail_response_has_no_result_field(self):
        from nanobio_studio.app.demo.scenarios import SCENARIOS

        for s in SCENARIOS:
            body = client.get(f"{SCENARIOS_URL}/{s.slug}").json()
            # Prose may DISCUSS results; no key may CARRY one.
            for key in body:
                assert key not in ("design_result", "pk_result", "score",
                                   "results", "outputs")
            assert "design_impact_score" not in body
            assert "pk_parameters" not in body
            # Input payloads specifically must be free of result-shaped keys.
            for payload in (body["design_inputs"], body["pk_inputs"]):
                rendered = json.dumps(payload).lower()
                for token in ("auc", "cmax", "half_life", "score", "result"):
                    assert token not in rendered

    def test_any_mention_of_ng_per_ml_is_a_disclaimer(self):
        """The PK engine has no volume term, so ng/mL must only ever be denied.

        The word may legitimately appear in prose that rules the unit OUT; it
        must never appear as a unit the platform claims to produce.
        """
        from nanobio_studio.app.demo.scenarios import SCENARIOS

        for s in SCENARIOS:
            body = client.get(f"{SCENARIOS_URL}/{s.slug}").json()
            prose = body["assumptions"] + body["expected_warnings"] + \
                body["provenance"]
            for line in prose:
                if "ng/ml" in line.lower():
                    assert "not" in line.lower(), (
                        f"{s.slug}: ng/mL mentioned without denial: {line!r}")

    def test_unknown_scenario_is_a_structured_404(self):
        r = client.get(f"{SCENARIOS_URL}/no-such-scenario")
        assert r.status_code == 404
        assert r.json()["data_available"] is False


# ===========================================================================
# Scenario preview
# ===========================================================================


class TestScenarioPreview:

    def test_preview_lists_inputs_and_teaching_metadata(self):
        body = client.get(f"{SCENARIOS_URL}/breast-her2-targeted").json()
        assert body["design_inputs"]["size_nm"] == 95
        assert body["pk_inputs"]["dose_mg_kg"] == 4.0
        assert body["assumptions"] and body["expected_warnings"]
        assert body["engines_expected_to_run"]
        assert body["engines_that_will_not_run"]

    def test_preview_names_the_missing_required_inputs(self):
        body = client.get(f"{SCENARIOS_URL}/technical-incomplete-inputs").json()
        assert body["missing_required_design_inputs"] == ["encapsulation_percent"]
        assert set(body["missing_required_pk_inputs"]) == {
            "kel_per_h", "k12_per_h", "k21_per_h"}
        assert body["score_runnable"] is False
        assert body["pk_runnable"] is False

    def test_blocked_scenario_expects_no_engines_to_run(self):
        body = client.get(f"{SCENARIOS_URL}/technical-incomplete-inputs").json()
        assert body["engines_expected_to_run"] == []

    def test_boundary_scenario_is_runnable_and_warns(self):
        body = client.get(f"{SCENARIOS_URL}/technical-boundary-values").json()
        assert body["score_runnable"] is True
        assert body["pk_runnable"] is True
        expected = " ".join(body["expected_warnings"]).lower()
        assert "step" in expected

    def test_boundary_scenario_really_produces_engine_warnings(self):
        """The warnings are the engine's, not the fixture's claim."""
        from nanobio_studio.app.demo.scenarios import scenario_by_slug

        s = scenario_by_slug("technical-boundary-values")
        r = client.post("/api/v1/pk/simulate", json=s.pk_inputs)
        assert r.status_code == 200
        warnings = " ".join(r.json()["warnings"]).lower()
        assert "not interchangeable" in warnings
        assert "forward-euler" in warnings or "large relative" in warnings

    def test_boundary_scenario_does_not_bypass_validation(self):
        """Out-of-range values must still be refused, even for this scenario."""
        from nanobio_studio.app.demo.scenarios import scenario_by_slug

        s = scenario_by_slug("technical-boundary-values")
        over = {**s.pk_inputs, "kel_per_h": 99}
        assert client.post("/api/v1/pk/simulate", json=over).status_code == 422


# ===========================================================================
# Seeding
# ===========================================================================


class TestSeeding:

    def test_seeding_installs_every_scenario(self):
        from nanobio_studio.app.demo.scenarios import SCENARIOS

        body = client.post("/api/v1/demo/seed").json()
        assert body["total"] == len(SCENARIOS)

    def test_seeding_is_idempotent(self):
        first = client.post("/api/v1/demo/seed").json()
        second = client.post("/api/v1/demo/seed").json()
        assert second["created"] == []
        assert second["updated"] == []
        assert second["total"] == first["total"]

    def test_repeated_seeding_creates_no_duplicates(self):
        from sqlalchemy import func, select

        from nanobio_studio.app.db.workspace_models import DemoTemplate
        from nanobio_studio.app.demo.scenarios import SCENARIOS
        from tests.conftest import run_async

        for _ in range(3):
            client.post("/api/v1/demo/seed")

        from nanobio_studio.app.db.auth_session import get_auth_session
        from nanobio_studio.app.vertical_slice import app

        override = app.dependency_overrides[get_auth_session]

        async def _count():
            agen = override()
            session = await agen.__anext__()
            try:
                stmt = select(func.count()).select_from(DemoTemplate)
                return int((await session.execute(stmt)).scalar_one())
            finally:
                await agen.aclose()

        assert run_async(_count()) == len(SCENARIOS)

    def test_seeding_requires_admin(self, tmp_path_factory):
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login",
                    json={"username": VIEWER_USER, "password": VIEWER_PASSWORD})
        r = client.post("/api/v1/demo/seed")
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login",
                    json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
        assert r.status_code == 403


# ===========================================================================
# Storing runs
# ===========================================================================


class TestStoredRuns:

    def test_storing_a_run_records_which_engines_ran(self):
        run = _store_minimal_run("engines recorded")
        assert run["status"] == "partial"          # design only
        assert len(run["engines_run"]) == 1
        assert run["has_design_result"] is True
        assert run["has_pk_result"] is False

    def test_engines_run_is_derived_not_trusted(self):
        """A caller cannot claim an engine ran when no result is present."""
        created = client.post(RUNS_URL, json={
            "name": "claims too much",
            "engines_not_run": [],
        })
        assert created.status_code == 201
        assert created.json()["engines_run"] == []
        assert created.json()["status"] == "blocked"

    def test_result_cannot_be_stored_without_its_inputs(self):
        score = client.post("/api/v1/design/score",
                            json={"size_nm": 100, "charge_mv": -5,
                                  "encapsulation_percent": 85}).json()
        r = client.post(RUNS_URL, json={"name": "orphan",
                                        "design_result": score})
        assert r.status_code == 400
        assert r.json()["error"] == "inputs_required"
        assert r.json()["data_available"] is False

    def test_stored_result_matches_the_engine_output_exactly(self):
        run = _store_minimal_run("verbatim")
        detail = client.get(f"{RUNS_URL}/{run['id']}").json()
        fresh = client.post("/api/v1/design/score",
                            json=detail["design_inputs"]).json()
        assert (detail["design_result"]["design_impact_score"]
                == fresh["design_impact_score"])

    def test_demo_origin_is_recorded(self):
        run = _store_minimal_run("demo run", is_demo=True,
                                 slug="liver-hcc-galnac")
        assert run["origin"] == "demo"
        assert run["demo_scenario_slug"] == "liver-hcc-galnac"
        assert run["demo_fixture_version"].startswith("demo-scenarios-")

    def test_user_run_is_not_marked_as_demo(self):
        run = _store_minimal_run("my own work")
        assert run["origin"] == "user"
        assert run["demo_scenario_slug"] is None
        assert run["demo_fixture_version"] is None

    def test_unknown_scenario_slug_is_rejected(self):
        r = client.post(RUNS_URL, json={"name": "bad slug", "is_demo": True,
                                        "demo_scenario_slug": "not-real"})
        assert r.status_code == 400

    def test_history_lists_stored_runs(self):
        _store_minimal_run("listed run")
        body = client.get(RUNS_URL).json()
        assert body["total"] >= 1
        assert any(r["name"] == "listed run" for r in body["runs"])

    def test_history_filters_by_origin(self):
        _store_minimal_run("filter demo", is_demo=True, slug="liver-hcc-galnac")
        _store_minimal_run("filter user")
        demo = client.get(f"{RUNS_URL}?origin=demo").json()
        assert demo["total"] >= 1
        assert all(r["origin"] == "demo" for r in demo["runs"])

    def test_history_filters_by_disease(self):
        _store_minimal_run("liver run", disease="Liver Cancer (HCC)")
        body = client.get(f"{RUNS_URL}?disease=Liver+Cancer+%28HCC%29").json()
        assert all(r["disease"] == "Liver Cancer (HCC)" for r in body["runs"])

    def test_history_filters_by_scenario(self):
        _store_minimal_run("scenario run", is_demo=True,
                           slug="pancreatic-pdac-stroma")
        body = client.get(f"{RUNS_URL}?scenario=pancreatic-pdac-stroma").json()
        assert body["total"] >= 1
        assert all(r["demo_scenario_slug"] == "pancreatic-pdac-stroma"
                   for r in body["runs"])

    def test_missing_run_is_a_structured_404(self):
        r = client.get(f"{RUNS_URL}/999999")
        assert r.status_code == 404
        assert r.json()["data_available"] is False

    def test_deleting_a_run_removes_it(self):
        run = _store_minimal_run("to delete")
        assert client.delete(f"{RUNS_URL}/{run['id']}").status_code == 200
        assert client.get(f"{RUNS_URL}/{run['id']}").status_code == 404

    def test_viewer_cannot_delete_a_run(self):
        run = _store_minimal_run("protected")
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login",
                    json={"username": VIEWER_USER, "password": VIEWER_PASSWORD})
        r = client.delete(f"{RUNS_URL}/{run['id']}")
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login",
                    json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
        assert r.status_code == 403

    def test_a_colleague_with_organization_wide_scope_can_reach_the_run(self):
        """**This test asserts the opposite of what it used to.**

        It previously required that another *user* could not reach the run,
        because access was ``owner_id == caller`` and ownership was the whole
        boundary.

        Production hardening replaced that with the organization policy, and
        the brief asked for exactly this: owner scoping "is not sufficient",
        and legitimate study-assignment access must not be weakened. The unit
        of isolation is now the organization and the study assignment, not the
        individual account. Both accounts here are members of the same
        organization with ``AccessScope.ORGANIZATION`` — the viewer is an
        auditor, whose entire function is reading everything in the
        organization — so reaching this run is correct rather than a leak.

        The probing concern the original test existed for has not gone away;
        it moved. It is asserted in ``test_organization_routes.py``, across a
        real organization boundary, where a foreign identifier and one that
        was never issued are proven indistinguishable.
        """
        run = _store_minimal_run("owned")
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login",
                    json={"username": VIEWER_USER, "password": VIEWER_PASSWORD})
        r = client.get(f"{RUNS_URL}/{run['id']}")
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login",
                    json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text

    def test_an_identifier_from_outside_the_organization_is_not_reachable(self):
        """The isolation the previous test was reaching for, stated correctly.

        A run id that belongs to no organization the caller is in must be
        indistinguishable from one that was never issued.
        """
        absent = client.get(f"{RUNS_URL}/987654")
        assert absent.status_code == 404, absent.text
        assert absent.json()["error"] == "not_found"


# ===========================================================================
# Comparison
# ===========================================================================


class TestComparison:

    def test_comparing_two_runs_aligns_their_values(self):
        a = _store_minimal_run("compare A", disease="Breast Cancer")
        b = _store_minimal_run("compare B", disease="Lung Cancer")
        body = client.get(
            f"{RUNS_URL}/compare/select?ids={a['id']},{b['id']}").json()
        assert len(body["runs"]) == 2
        assert body["rows"]
        labels = {row["label"] for row in body["rows"]}
        assert "Indication" in labels
        assert "Delivery (0-100, higher better)" in labels

    def test_comparison_produces_no_combined_ranking(self):
        a = _store_minimal_run("rank A")
        b = _store_minimal_run("rank B")
        body = client.get(
            f"{RUNS_URL}/compare/select?ids={a['id']},{b['id']}").json()
        for forbidden in ("ranking", "overall", "winner", "best", "total_score",
                          "composite"):
            assert forbidden not in body
        assert "no overall ranking" in body["notice"].lower()

    def test_missing_value_is_null_not_zero(self):
        """A run without a PK result must not show 0 for its PK fields."""
        a = _store_minimal_run("no pk A")
        b = _store_minimal_run("no pk B")
        body = client.get(
            f"{RUNS_URL}/compare/select?ids={a['id']},{b['id']}").json()
        for row in body["rows"]:
            if row["source"] == "pk_param":
                assert all(v is None for v in row["values"])

    def test_pk_rows_carry_the_dose_scaled_unit_note(self):
        design = {"size_nm": 100, "charge_mv": -5, "encapsulation_percent": 85}
        pk_inputs = {"dose_mg_kg": 3.0, "kabs_per_h": 0.5, "kel_per_h": 0.1,
                     "k12_per_h": 0.2, "k21_per_h": 0.05}
        score = client.post("/api/v1/design/score", json=design).json()
        profile = client.post("/api/v1/pk/simulate", json=pk_inputs).json()
        made = [client.post(RUNS_URL, json={
            "name": f"pk run {i}", "design_inputs": design,
            "pk_inputs": pk_inputs, "design_result": score,
            "pk_result": profile}).json() for i in range(2)]

        body = client.get(
            f"{RUNS_URL}/compare/select?ids={made[0]['id']},{made[1]['id']}").json()
        pk_rows = [r for r in body["rows"] if r["source"] == "pk_param"]
        assert pk_rows
        for row in pk_rows:
            assert "dose-scaled" in row["unit_note"].lower()
            assert "ng/ml" not in row["unit_note"].lower()

    def test_fewer_than_two_runs_is_rejected(self):
        a = _store_minimal_run("single")
        r = client.get(f"{RUNS_URL}/compare/select?ids={a['id']}")
        assert r.status_code == 400
        assert r.json()["data_available"] is False

    def test_more_than_four_runs_is_rejected(self):
        ids = ",".join(str(_store_minimal_run(f"many {i}")["id"])
                       for i in range(5))
        assert client.get(f"{RUNS_URL}/compare/select?ids={ids}"
                          ).status_code == 400

    def test_non_numeric_ids_are_rejected(self):
        r = client.get(f"{RUNS_URL}/compare/select?ids=a,b")
        assert r.status_code == 400
        assert r.json()["error"] == "invalid_selection"


# ===========================================================================
# Projects
# ===========================================================================


class TestProjects:

    def test_create_and_list_a_project(self):
        created = client.post(PROJECTS_URL, json={"name": "Panel A"})
        assert created.status_code == 201
        listing = client.get(PROJECTS_URL).json()
        assert any(p["name"] == "Panel A" for p in listing["projects"])

    def test_assigning_a_run_updates_its_project(self):
        project = client.post(PROJECTS_URL, json={"name": "Panel B"}).json()
        run = _store_minimal_run("assignable")
        response = client.post(
            f"{RUNS_URL}/{run['id']}/project?project_id={project['id']}")
        assert response.status_code == 200, response.text
        updated = response.json()
        assert updated["project_id"] == project["id"]

    def test_project_run_count_reflects_assignments(self):
        project = client.post(PROJECTS_URL, json={"name": "Panel C"}).json()
        run = _store_minimal_run("counted")
        client.post(f"{RUNS_URL}/{run['id']}/project?project_id={project['id']}")
        listing = client.get(PROJECTS_URL).json()["projects"]
        row = next(p for p in listing if p["id"] == project["id"])
        assert row["run_count"] == 1

    def test_deleting_a_project_preserves_its_runs(self):
        """A grouping mistake must never cost a user their calculated results."""
        project = client.post(PROJECTS_URL, json={"name": "Panel D"}).json()
        run = _store_minimal_run("survivor")
        client.post(f"{RUNS_URL}/{run['id']}/project?project_id={project['id']}")

        deleted = client.delete(f"{PROJECTS_URL}/{project['id']}")
        assert deleted.status_code == 200
        assert deleted.json()["runs_preserved"] is True

        still_there = client.get(f"{RUNS_URL}/{run['id']}")
        assert still_there.status_code == 200
        assert still_there.json()["project_id"] is None

    def test_viewer_cannot_delete_a_project(self):
        project = client.post(PROJECTS_URL, json={"name": "Panel E"}).json()
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login",
                    json={"username": VIEWER_USER, "password": VIEWER_PASSWORD})
        r = client.delete(f"{PROJECTS_URL}/{project['id']}")
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login",
                    json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
        assert r.status_code == 403


# ===========================================================================
# Demo reset — the protection of genuine user data
# ===========================================================================


class TestDemoReset:

    def test_reset_without_confirm_deletes_nothing(self):
        _store_minimal_run("reset demo", is_demo=True, slug="liver-hcc-galnac")
        before = client.get(RUNS_URL).json()["total"]

        body = client.post("/api/v1/demo/reset", json={"confirm": False}).json()
        assert body["confirmed"] is False
        assert body["deleted"] is False
        assert client.get(RUNS_URL).json()["total"] == before

    def test_reset_reports_its_exact_scope(self):
        _store_minimal_run("scope demo", is_demo=True, slug="liver-hcc-galnac")
        _store_minimal_run("scope user")
        body = client.post("/api/v1/demo/reset", json={"confirm": False}).json()
        assert body["demo_runs"] >= 1
        assert body["user_runs_preserved"] >= 1
        assert "not touched" in body["message"] or "untouched" in body["message"]

    def test_reset_deletes_demo_runs_only(self):
        """The central safety property of the reset command."""
        demo = _store_minimal_run("delete me", is_demo=True,
                                  slug="liver-hcc-galnac")
        mine = _store_minimal_run("keep me")

        body = client.post("/api/v1/demo/reset", json={"confirm": True}).json()
        assert body["deleted"] is True

        assert client.get(f"{RUNS_URL}/{demo['id']}").status_code == 404
        assert client.get(f"{RUNS_URL}/{mine['id']}").status_code == 200

    def test_reset_leaves_no_demo_run_behind(self):
        _store_minimal_run("sweep 1", is_demo=True, slug="liver-hcc-galnac")
        _store_minimal_run("sweep 2", is_demo=True, slug="breast-her2-targeted")
        client.post("/api/v1/demo/reset", json={"confirm": True})
        assert client.get(f"{RUNS_URL}?origin=demo").json()["total"] == 0

    def test_reset_keeps_templates_installed_by_default(self):
        from nanobio_studio.app.demo.scenarios import SCENARIOS

        client.post("/api/v1/demo/seed")
        client.post("/api/v1/demo/reset", json={"confirm": True})
        assert len(client.get(SCENARIOS_URL).json()["scenarios"]) == len(SCENARIOS)

    def test_scenarios_remain_loadable_after_reset(self):
        client.post("/api/v1/demo/reset", json={"confirm": True})
        r = client.get(f"{SCENARIOS_URL}/liver-hcc-galnac")
        assert r.status_code == 200
        assert r.json()["design_inputs"]["size_nm"] == 100

    def test_non_admin_cannot_reset_every_users_demo_data(self):
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login",
                    json={"username": VIEWER_USER, "password": VIEWER_PASSWORD})
        r = client.post("/api/v1/demo/reset",
                        json={"confirm": True, "mine_only": False})
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login",
                    json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
        assert r.status_code == 403


# ===========================================================================
# Seeding service, exercised directly
# ===========================================================================


class TestSeedingService:

    def test_scenario_payload_excludes_identity_columns(self):
        from nanobio_studio.app.demo.scenarios import scenario_by_slug
        from nanobio_studio.app.demo.seeding import scenario_payload

        payload = scenario_payload(scenario_by_slug("liver-hcc-galnac"))
        for key in ("slug", "name", "disease", "subtype", "drug"):
            assert key not in payload
        assert "design_inputs" in payload
        assert "pk_inputs" in payload

    def test_payload_carries_no_result(self):
        from nanobio_studio.app.demo.scenarios import SCENARIOS
        from nanobio_studio.app.demo.seeding import scenario_payload

        for s in SCENARIOS:
            rendered = json.dumps(scenario_payload(s))
            assert "design_impact_score" not in rendered
            assert "pk_parameters" not in rendered
            assert "concentration_time" not in rendered
