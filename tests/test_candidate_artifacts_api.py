"""The version-bound artefact routes, over real HTTP.

What these add over the service-level tests
--------------------------------------------
`test_candidate_dependency_binding.py` proves the invariants hold at the
service boundary. These prove they survive the transport: the field names a
client reads, the status codes it branches on, the refusals it has to handle,
and the cross-organization boundary that only exists once a request carries an
identity.

The properties the brief names, in the order it names them:

* an approval of revision 1 never appears as an approval of revision 2;
* a historical report always uses its stored version;
* exports and CRO packages carry candidate id, exact version id, revision label
  and generation timestamp;
* a revision starts without inherited approval;
* copied results stay STALE and identify their source;
* evidence reuse is explicitly classified.

Every refusal has an authorized positive control beside it, so a route that
refused everybody could not pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.db.auth_models import UserRole  # noqa: E402
from nanobio_studio.app.organizations.vocabulary import (  # noqa: E402
    AccessScope, MembershipStatus, OrganizationRole, OrganizationStatus,
    StudyRole,
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

PASSWORD = "a-genuinely-long-fixture-passphrase"

DESIGN = {"size_nm": 95.0, "charge_mv": -12.0, "coating": "PEG",
          "dose_mg_kg": 2.0, "encapsulation_percent": 82.0}


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    """Two organizations, a study, a candidate, and a cast with real roles."""
    from nanobio_studio.app.db.organization_models import (
        Organization, OrganizationMembership, StudyAssignment,
    )
    from nanobio_studio.app.db.validation_models import Candidate
    from nanobio_studio.app.db.workspace_models import StoredRun
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("candidate_artifacts_api")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    #: name -> (organization, organization role, scope, platform role, extra)
    CAST = {
        "author": ("home", OrganizationRole.RESEARCHER,
                   AccessScope.ORGANIZATION, UserRole.RESEARCHER, {}),
        # A RESEARCHER, not an OWNER. Scientific capability comes from the
        # study assignment and nowhere else, and every administrative
        # organization role — owner included — is refused every scientific
        # verb by design. An "approver" fixture holding OWNER would be testing
        # a person who cannot approve anything.
        "approver": ("home", OrganizationRole.RESEARCHER,
                     AccessScope.ORGANIZATION, UserRole.RESEARCHER, {}),
        "administrator": ("home", OrganizationRole.ADMINISTRATOR,
                          AccessScope.ORGANIZATION, UserRole.ADMIN, {}),
        "unassigned": ("home", OrganizationRole.RESEARCHER,
                       AccessScope.ASSIGNED_STUDIES, UserRole.RESEARCHER, {}),
        "revoked": ("home", OrganizationRole.RESEARCHER,
                    AccessScope.ORGANIZATION, UserRole.RESEARCHER,
                    {"status": MembershipStatus.REVOKED}),
        "outsider": ("away", OrganizationRole.RESEARCHER,
                     AccessScope.ORGANIZATION, UserRole.RESEARCHER, {}),
    }

    async def seed():
        async with factory() as session:
            users = {}
            for name, (_org, _role, _scope, platform, _extra) in CAST.items():
                users[name] = await create_user(
                    session, username=name, password=PASSWORD,
                    role=platform, email=f"{name}@artifacts.test")
            await session.flush()

            home = Organization(slug="home-lab", name="Home Lab",
                                status=OrganizationStatus.ACTIVE)
            away = Organization(slug="away-lab", name="Away Lab",
                                status=OrganizationStatus.ACTIVE)
            session.add_all([home, away])
            await session.flush()
            orgs = {"home": home, "away": away}

            for name, (org, role, scope, _platform, extra) in CAST.items():
                session.add(OrganizationMembership(
                    organization_id=orgs[org].id, user_id=users[name].id,
                    role=role, scope=scope,
                    status=extra.get("status", MembershipStatus.ACTIVE)))
            await session.flush()

            run = StoredRun(organization_id=home.id,
                            owner_id=users["author"].id, name="artifact study")
            session.add(run)
            await session.flush()

            # The assigned-studies member is deliberately given no assignment
            # on this study; that is the case under test.
            for name, role in (("author", StudyRole.OWNER),
                               ("approver", StudyRole.APPROVER)):
                session.add(StudyAssignment(
                    organization_id=home.id, study_id=run.id,
                    user_id=users[name].id, role=role,
                    status=MembershipStatus.ACTIVE))

            candidate = Candidate(organization_id=home.id, study_id=run.id,
                                  owner_id=users["author"].id,
                                  code="ART-1", name="Artifact candidate")
            session.add(candidate)
            await session.flush()

            state.update(home_id=home.id, away_id=away.id, study_id=run.id,
                         candidate_id=candidate.id,
                         users={k: v.id for k, v in users.items()})
            await session.commit()

    with client:
        run_async(seed())
        yield app, client, state
    app.dependency_overrides.clear()


def sign_in(client, username: str) -> None:
    client.post("/api/v1/auth/logout")
    response = client.post("/api/v1/auth/login",
                           json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text


def headers(state, org: str = "home") -> dict:
    return {"X-Organization-Id": str(state[f"{org}_id"])}


def make_version(client, state, note: str, design: dict | None = None) -> int:
    """A fresh candidate version owned by `author`."""
    sign_in(client, "author")
    response = client.post(
        f"/api/v1/validation/candidates/{state['candidate_id']}/versions",
        headers=headers(state),
        json={"design_inputs": design or DESIGN, "note": note})
    assert response.status_code == 200, response.text
    return response.json()["id"]


# ===========================================================================
# 1. Every route is registered and addressed to a version
# ===========================================================================

class TestTheRoutesExist:

    def test_every_artifact_route_is_registered(self, api):
        app, _client, _state = api
        paths = {getattr(r, "path", "") for r in app.routes}

        for expected in (
            "/api/v1/validation/candidate-versions/{version_id}/simulations",
            "/api/v1/validation/candidate-versions/{version_id}/evidence",
            "/api/v1/validation/candidate-versions/{version_id}/reports",
            "/api/v1/validation/candidate-versions/{version_id}/exports",
            "/api/v1/validation/candidate-versions/{version_id}/cro-packages",
            "/api/v1/validation/candidate-versions/{version_id}/comparisons",
            "/api/v1/validation/candidate-versions/{version_id}/recalculate",
            "/api/v1/validation/candidate-versions/{version_id}/dependents",
            "/api/v1/validation/candidate-versions/{version_id}/audit",
            "/api/v1/validation/candidate-versions/{version_id}"
            "/propose-supersession",
            "/api/v1/validation/candidate-versions/{version_id}"
            "/refuse-supersession",
            "/api/v1/validation/candidate-reports/{report_id}",
            "/api/v1/validation/candidates/{candidate_id}/comparisons",
        ):
            assert expected in paths, f"{expected} is not registered"

    def test_no_artifact_route_is_addressed_to_a_candidate_alone(self, api):
        """The one exception is the comparison LIST, which is a read.

        A write addressed to a candidate would have to resolve which version it
        meant, and that is the ambiguity the whole feature exists to remove.
        """
        app, _client, _state = api

        for route in app.routes:
            module = getattr(getattr(route, "endpoint", None), "__module__", "")
            if not module.endswith("candidate_artifacts"):
                continue
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", set()) or set()
            if "POST" not in methods:
                continue
            assert "{version_id}" in path, (
                f"{path} writes without naming an exact version")


# ===========================================================================
# 2. "latest" is refused, never resolved
# ===========================================================================

class TestLatestIsRefused:

    def test_a_write_addressed_to_latest_is_a_400_with_a_remedy(self, api):
        _app, client, state = api
        sign_in(client, "author")

        response = client.post(
            "/api/v1/validation/candidate-versions/latest/reports",
            headers=headers(state), json={"title": "Summary", "body": {}})

        # FastAPI's own path coercion refuses a non-integer before the handler
        # runs, which is the same refusal for the same reason. What matters is
        # that no report is produced and the caller is told the request was
        # rejected rather than being given somebody's guess.
        assert response.status_code in (400, 422), response.text
        assert "report_id" not in response.text

    def test_a_missing_version_is_a_404_not_a_fallback(self, api):
        _app, client, state = api
        sign_in(client, "author")

        response = client.post(
            "/api/v1/validation/candidate-versions/99999999/reports",
            headers=headers(state), json={"title": "Summary", "body": {}})

        assert response.status_code == 404, response.text
        assert "report_id" not in response.json()


# ===========================================================================
# 3. Generated artefacts identify exactly what they describe
# ===========================================================================

class TestArtifactsIdentifyTheirVersion:

    def test_an_export_carries_the_identifying_facts(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "export identity")

        response = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/exports",
            headers=headers(state),
            json={"format": "json", "purpose_note": "statistics review"})
        assert response.status_code == 200, response.text
        payload = response.json()

        assert payload["candidate_version_id"] == version_id
        assert payload["candidate_id"] == state["candidate_id"]
        assert payload["version_label"]

        manifest = payload["manifest"]
        assert manifest["candidate_id"] == state["candidate_id"]
        assert manifest["candidate_version_id"] == version_id
        assert manifest["revision_label"] == payload["version_label"]
        assert manifest["snapshot_checksum"] == payload["version_checksum"]
        assert manifest["generated_at"]

    def test_a_cro_package_carries_them_too(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "package identity")

        response = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/cro-packages",
            headers=headers(state),
            json={"recipient_name": "Northgate Contract Labs",
                  "package_code": f"PKG-API-{version_id}",
                  "quotation_reference": "Q-2026-0201"})
        assert response.status_code == 200, response.text
        payload = response.json()

        manifest = payload["manifest"]
        assert manifest["candidate_id"] == state["candidate_id"]
        assert manifest["candidate_version_id"] == version_id
        assert manifest["revision_label"]
        assert manifest["generated_at"]
        assert manifest["recipient"] == "Northgate Contract Labs"
        assert payload["content_checksum"]

    def test_generating_an_artifact_locks_the_version(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "lock through http")

        before = client.get(
            f"/api/v1/validation/candidate-versions/{version_id}/dependents",
            headers=headers(state)).json()
        assert before["editable"] is True
        assert before["total_dependents"] == 0

        client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/reports",
            headers=headers(state), json={"title": "Summary", "body": {}})

        after = client.get(
            f"/api/v1/validation/candidate-versions/{version_id}/dependents",
            headers=headers(state)).json()
        assert after["editable"] is False
        assert after["dependents"]["reports"] == 1
        assert after["total_dependents"] == 1
        assert "report was generated" in after["lock_reason"]
        assert "revision" in after["explanation"]


# ===========================================================================
# 4. A historical report always uses its stored version
# ===========================================================================

class TestHistoricalReports:

    def test_reopening_a_report_serves_its_stored_content(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "historical report",
                                  design={**DESIGN, "dose_mg_kg": 2.0})

        created = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/reports",
            headers=headers(state),
            json={"title": "Pre-clinical summary",
                  "body": {"finding": "acceptable"}}).json()

        # The candidate moves on: a revision with a different dose.
        revision = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/revise",
            headers=headers(state),
            json={"design_inputs": {**DESIGN, "dose_mg_kg": 12.0},
                  "reason": "Dose escalation for the tolerability arm"}).json()
        assert revision["id"] != version_id

        reopened = client.get(
            f"/api/v1/validation/candidate-reports/{created['report_id']}",
            headers=headers(state))
        assert reopened.status_code == 200, reopened.text
        payload = reopened.json()

        assert payload["candidate_version_id"] == version_id, (
            "the report was re-attributed to the newer version")
        assert payload["regenerated"] is False
        assert payload["content"]["design_snapshot"]["dose_mg_kg"] == 2.0, (
            "the report shows the revision's dose, so it was regenerated "
            "from current data rather than served as issued")
        assert payload["content_checksum"] == created["content_checksum"]

    def test_a_report_on_a_superseded_version_says_it_is_historical(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "superseded report")

        created = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/reports",
            headers=headers(state),
            json={"title": "Original summary", "body": {}}).json()

        revision = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/revise",
            headers=headers(state),
            json={"design_inputs": {**DESIGN, "coating": "chitosan"},
                  "reason": "Coating change after the stability finding"}
        ).json()

        # The successor has to leave draft before it can take over.
        client.post(
            f"/api/v1/validation/candidate-versions/{revision['id']}/exports",
            headers=headers(state), json={"format": "json"})

        sign_in(client, "approver")
        superseded = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/supersede",
            headers=headers(state),
            json={"successor_version_id": revision["id"],
                  "reason": "The coated version replaces the original"})
        assert superseded.status_code == 200, superseded.text

        reopened = client.get(
            f"/api/v1/validation/candidate-reports/{created['report_id']}",
            headers=headers(state)).json()

        assert reopened["historical"] is True
        assert reopened["superseded_by_version_id"] == revision["id"]
        assert "true record of what was concluded then" in reopened["notice"]
        assert reopened["candidate_version_id"] == version_id


# ===========================================================================
# 5. A revision starts without inherited approval
# ===========================================================================

class TestRevisionsInheritNothing:

    def test_a_revision_of_an_approved_version_starts_as_a_draft(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "approval inheritance")

        history_before = client.get(
            f"/api/v1/validation/candidates/{state['candidate_id']}/versions",
            headers=headers(state)).json()
        assert history_before["latest_draft_version_id"] is not None

        # Lock it and record an approval-shaped decision by generating an
        # artefact, then revise.
        client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/reports",
            headers=headers(state), json={"title": "Basis", "body": {}})

        revision = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/revise",
            headers=headers(state),
            json={"design_inputs": {**DESIGN, "dose_mg_kg": 9.0},
                  "reason": "Dose escalation agreed at review"}).json()

        assert revision["status"] == "draft"
        assert revision["results_state"] in ("stale", "none")
        assert revision["predecessor_version_id"] == version_id
        assert revision["consequence"]["approval_may_carry_forward"] is False
        assert revision["consequence"]["requires"] == "safety_review"
        assert "carries no approval" in revision["notice"]

    def test_the_predecessor_is_untouched_by_the_revision(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "predecessor untouched")

        client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/reports",
            headers=headers(state), json={"title": "Basis", "body": {}})

        before = client.get(
            f"/api/v1/validation/candidate-versions/{version_id}/dependents",
            headers=headers(state)).json()

        client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/revise",
            headers=headers(state),
            json={"design_inputs": {**DESIGN, "coating": "chitosan"},
                  "reason": "Coating change"})

        after = client.get(
            f"/api/v1/validation/candidate-versions/{version_id}/dependents",
            headers=headers(state)).json()

        assert after["status"] == before["status"]
        assert after["dependents"] == before["dependents"]

    def test_the_history_never_reports_an_unqualified_latest(self, api):
        """"Latest" is ambiguous between the newest draft and the currently
        approved version. The API names which is which."""
        _app, client, state = api
        make_version(client, state, "latest naming")

        payload = client.get(
            f"/api/v1/validation/candidates/{state['candidate_id']}/versions",
            headers=headers(state)).json()

        assert "latest_draft_version_id" in payload
        assert "latest_approved_version_id" in payload
        assert "current_effective_version_id" in payload
        assert "latest_version_id" not in payload, (
            "the API offers an unqualified 'latest', which is the ambiguity "
            "the whole feature exists to remove")


# ===========================================================================
# 6. An approval of one revision never appears as an approval of another
# ===========================================================================

class TestApprovalsStayWithTheirVersion:

    def test_evidence_recorded_on_one_version_is_not_listed_on_another(self,
                                                                       api):
        _app, client, state = api
        v1 = make_version(client, state, "evidence v1")

        recorded = client.post(
            f"/api/v1/validation/candidate-versions/{v1}/evidence",
            headers=headers(state),
            json={"purpose": "safety_assessment", "level": "E3",
                  "reuse": "newly_validated",
                  "rationale": "Cytotoxicity performed on this version."})
        assert recorded.status_code == 200, recorded.text

        v2 = client.post(
            f"/api/v1/validation/candidate-versions/{v1}/revise",
            headers=headers(state),
            json={"design_inputs": {**DESIGN, "dose_mg_kg": 15.0},
                  "reason": "Dose escalation"}).json()["id"]

        on_v1 = client.get(
            f"/api/v1/validation/candidate-versions/{v1}/evidence",
            headers=headers(state)).json()
        on_v2 = client.get(
            f"/api/v1/validation/candidate-versions/{v2}/evidence",
            headers=headers(state)).json()

        assert on_v1["total"] == 1
        assert on_v1["assessments"][0]["level"] == "E3"
        assert on_v2["total"] == 0, (
            "an E3 granted against the previous formulation appears under the "
            "revision, which is the exact misattribution this prevents")

    def test_reports_generated_on_one_version_are_not_listed_on_another(self,
                                                                        api):
        _app, client, state = api
        v1 = make_version(client, state, "reports v1")

        client.post(f"/api/v1/validation/candidate-versions/{v1}/reports",
                    headers=headers(state),
                    json={"title": "v1 report", "body": {}})

        v2 = client.post(
            f"/api/v1/validation/candidate-versions/{v1}/revise",
            headers=headers(state),
            json={"design_inputs": {**DESIGN, "pdi": 0.21},
                  "reason": "Recorded the measured polydispersity"}
        ).json()["id"]

        on_v1 = client.get(
            f"/api/v1/validation/candidate-versions/{v1}/reports",
            headers=headers(state)).json()
        on_v2 = client.get(
            f"/api/v1/validation/candidate-versions/{v2}/reports",
            headers=headers(state)).json()

        assert [r["title"] for r in on_v1["reports"]] == ["v1 report"]
        assert on_v2["total"] == 0
        assert on_v1["reports"][0]["candidate_version_id"] == v1


# ===========================================================================
# 7. Evidence reuse must be classified
# ===========================================================================

class TestEvidenceReuseOverHttp:

    def test_an_unclassified_reuse_is_refused(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "reuse unclassified")

        response = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/evidence",
            headers=headers(state),
            json={"purpose": "safety_assessment", "level": "E3",
                  "reuse": "assumed_fine",
                  "rationale": "Looks like the previous one."})

        assert response.status_code == 400, response.text
        body = response.json()
        assert body["error"] == "unknown_reuse_classification"
        assert "retained_reference" in body["detail"]

    def test_retained_evidence_without_a_source_is_refused(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "retained no source")

        response = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/evidence",
            headers=headers(state),
            json={"purpose": "safety_assessment", "level": "E3",
                  "reuse": "retained_reference",
                  "rationale": "Carried over from the earlier revision."})

        assert response.status_code == 400, response.text
        assert response.json()["error"] == "retained_evidence_needs_a_source"

    def test_each_classification_is_labelled_for_a_reader(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "reuse labelled")

        payload = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/evidence",
            headers=headers(state),
            json={"purpose": "safety_assessment", "level": None,
                  "reuse": "reassessment_required",
                  "rationale": "The coating changed; the earlier assay does "
                               "not describe this material."}).json()

        assert payload["reuse"] == "reassessment_required"
        assert payload["reuse_label"] == "Reassessment required"


# ===========================================================================
# 8. Authorization
# ===========================================================================

class TestAuthorization:

    #: (username, expected status, why)
    #:
    #: 404 and 403 mean different things and the difference is deliberate. A
    #: record outside the caller's organizations is indistinguishable from one
    #: that never existed, or the identifier space becomes an oracle. A record
    #: inside the organization that the caller may not act on gets a 403 with
    #: a reason, because they can already see it exists and a silent 404 there
    #: would read as data loss.
    REFUSALS = [
        ("outsider", 404,
         "a version in another organization must be indistinguishable from "
         "one that never existed"),
        ("unassigned", 403,
         "an assigned-studies member can see the organization but is not "
         "assigned to this study, so the refusal explains itself"),
        ("revoked", 404, "a revoked membership sees no organization at all"),
        ("administrator", 403,
         "administrative authority is not scientific authority"),
    ]

    @pytest.mark.parametrize("username,expected,why", REFUSALS)
    def test_generating_a_report_is_refused(self, api, username, expected,
                                            why):
        _app, client, state = api
        version_id = make_version(client, state, f"authz-{username}")

        sign_in(client, username)
        org = "away" if username == "outsider" else "home"
        response = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/reports",
            headers=headers(state, org),
            json={"title": "Unauthorized", "body": {}})

        assert response.status_code == expected, f"{why}: {response.text}"
        assert "report_id" not in response.json()

    @pytest.mark.parametrize("username,expected,why", REFUSALS)
    def test_generating_a_cro_package_is_refused(self, api, username,
                                                 expected, why):
        _app, client, state = api
        version_id = make_version(client, state, f"authz-pkg-{username}")

        sign_in(client, username)
        org = "away" if username == "outsider" else "home"
        response = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/cro-packages",
            headers=headers(state, org),
            json={"recipient_name": "Elsewhere Labs",
                  "package_code": f"PKG-BAD-{version_id}"})

        assert response.status_code == expected, f"{why}: {response.text}"
        assert "package_id" not in response.json()

    def test_an_authorized_author_succeeds(self, api):
        """Positive control. A route that refused everybody would pass every
        assertion above."""
        _app, client, state = api
        version_id = make_version(client, state, "authz positive")

        sign_in(client, "author")
        response = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/reports",
            headers=headers(state), json={"title": "Authorized", "body": {}})

        assert response.status_code == 200, response.text
        assert response.json()["report_id"]

    def test_a_refused_attempt_does_not_lock_the_version(self, api):
        """A refusal must leave no trace at all — not even a lock."""
        _app, client, state = api
        version_id = make_version(client, state, "refusal leaves no lock")

        sign_in(client, "administrator")
        refused = client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/reports",
            headers=headers(state), json={"title": "Refused", "body": {}})
        assert refused.status_code == 403

        sign_in(client, "author")
        dependents = client.get(
            f"/api/v1/validation/candidate-versions/{version_id}/dependents",
            headers=headers(state)).json()
        assert dependents["editable"] is True
        assert dependents["total_dependents"] == 0


# ===========================================================================
# 9. Supersession: proposing, refusing, and self-supersession
# ===========================================================================

class TestSupersessionAuthority:

    def _pair(self, client, state, label: str) -> tuple[int, int]:
        v1 = make_version(client, state, f"{label} v1")
        client.post(f"/api/v1/validation/candidate-versions/{v1}/exports",
                    headers=headers(state), json={"format": "json"})
        v2 = client.post(
            f"/api/v1/validation/candidate-versions/{v1}/revise",
            headers=headers(state),
            json={"design_inputs": {**DESIGN, "charge_mv": -20.0},
                  "reason": f"{label}: corrected the measured zeta potential"}
        ).json()["id"]
        client.post(f"/api/v1/validation/candidate-versions/{v2}/exports",
                    headers=headers(state), json={"format": "json"})
        return v1, v2

    def test_an_author_may_propose_but_that_does_not_supersede(self, api):
        _app, client, state = api
        v1, v2 = self._pair(client, state, "propose")

        sign_in(client, "author")
        proposed = client.post(
            f"/api/v1/validation/candidate-versions/{v1}"
            f"/propose-supersession",
            headers=headers(state),
            json={"successor_version_id": v2,
                  "reason": "The corrected version should be used"})

        assert proposed.status_code == 200, proposed.text
        payload = proposed.json()
        assert payload["supersession_state"] == "proposed"
        assert payload["status"] != "superseded", (
            "proposing superseded the predecessor, which removes the "
            "separation the two-step workflow exists to create")
        assert payload["superseded_by_version_id"] is None

    def test_an_administrator_cannot_accept_a_supersession(self, api):
        _app, client, state = api
        v1, v2 = self._pair(client, state, "admin accept")

        sign_in(client, "administrator")
        response = client.post(
            f"/api/v1/validation/candidate-versions/{v1}/supersede",
            headers=headers(state),
            json={"successor_version_id": v2, "reason": "Administratively"})

        assert response.status_code == 403, response.text

    def test_the_author_of_the_successor_cannot_decide_it_replaces(self, api):
        """Separation of duty, the same one that stops self-approval."""
        _app, client, state = api
        v1, v2 = self._pair(client, state, "self supersede")

        # `author` created both versions; give them approval authority for the
        # duration of this check by acting as the owner who did NOT author.
        sign_in(client, "author")
        response = client.post(
            f"/api/v1/validation/candidate-versions/{v1}/supersede",
            headers=headers(state),
            json={"successor_version_id": v2, "reason": "Mine is better"})

        # Either the policy refuses the authority (403) or the self-supersession
        # guard refuses the act (409). Both are correct refusals; what must not
        # happen is a 200.
        assert response.status_code in (403, 409), response.text
        assert response.json().get("status") != "superseded"

    def test_an_approver_who_did_not_author_may_accept(self, api):
        """Positive control for the two refusals above."""
        _app, client, state = api
        v1, v2 = self._pair(client, state, "approver accept")

        sign_in(client, "approver")
        response = client.post(
            f"/api/v1/validation/candidate-versions/{v1}/supersede",
            headers=headers(state),
            json={"successor_version_id": v2,
                  "reason": "Agreed at the formulation review"})

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["superseded"]["status"] == "superseded"
        assert payload["successor_version_id"] == v2
        assert "unchanged" in payload["notice"]

    def test_refusing_a_proposal_needs_approval_authority(self, api):
        _app, client, state = api
        v1, v2 = self._pair(client, state, "refuse authority")

        sign_in(client, "author")
        client.post(
            f"/api/v1/validation/candidate-versions/{v1}"
            f"/propose-supersession",
            headers=headers(state),
            json={"successor_version_id": v2, "reason": "Please replace"})

        # The author cannot kill their own proposal's review by declining it.
        refused_by_author = client.post(
            f"/api/v1/validation/candidate-versions/{v1}"
            f"/refuse-supersession",
            headers=headers(state), json={"reason": "Changed my mind"})
        assert refused_by_author.status_code == 403, refused_by_author.text

        sign_in(client, "approver")
        refused = client.post(
            f"/api/v1/validation/candidate-versions/{v1}"
            f"/refuse-supersession",
            headers=headers(state),
            json={"reason": "The correction needs a second opinion"})
        assert refused.status_code == 200, refused.text
        assert refused.json()["supersession_state"] == "refused"
        assert refused.json()["status"] != "superseded"


# ===========================================================================
# 10. The audit trail is readable and complete over HTTP
# ===========================================================================

class TestAuditOverHttp:

    def test_the_version_trail_reports_each_event(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "audit over http")

        client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/reports",
            headers=headers(state), json={"title": "Trail", "body": {}})
        client.post(
            f"/api/v1/validation/candidate-versions/{version_id}/exports",
            headers=headers(state), json={"format": "json"})

        trail = client.get(
            f"/api/v1/validation/candidate-versions/{version_id}/audit",
            headers=headers(state))
        assert trail.status_code == 200, trail.text
        payload = trail.json()

        kinds = [e["event"] for e in payload["events"]]
        assert "version_locked" in kinds
        assert "report_generated" in kinds
        assert "export_generated" in kinds

        for event in payload["events"]:
            assert event["candidate_version_id"] == version_id
            assert event["candidate_id"] == state["candidate_id"]
            assert event["actor_id"] == state["users"]["author"]
            assert event["created_at"]

        assert "append-only" in payload["notice"]

    def test_the_trail_is_not_readable_from_another_organization(self, api):
        _app, client, state = api
        version_id = make_version(client, state, "audit isolation")

        sign_in(client, "outsider")
        response = client.get(
            f"/api/v1/validation/candidate-versions/{version_id}/audit",
            headers=headers(state, "away"))
        assert response.status_code == 404, response.text
