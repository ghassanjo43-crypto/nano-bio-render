"""Cross-organization isolation over HTTP.

Why this file exists separately from ``test_organization_isolation.py``
-----------------------------------------------------------------------
That file proves the policy and the scoped query layer behave. This one proves
the **routes actually call them** — which is a different claim, and the one
that matters to somebody holding a session cookie.

A control that exists only in a service is one a future route can forget to
call. So the central test here is not about any particular endpoint: it walks
every organization-scoped route in the application and fails if even one omits
the access-context dependency. A new route added next year without it breaks
this test on the first run, which is the only kind of guard that survives
people forgetting.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.api.deps_organization import (  # noqa: E402
    ORGANIZATION_HEADER, get_access_context,
)
from nanobio_studio.app.db.auth_models import UserRole  # noqa: E402
from nanobio_studio.app.organizations.vocabulary import (  # noqa: E402
    AccessScope, MembershipStatus, OrganizationRole, OrganizationStatus,
    StudyRole,
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402


# ===========================================================================
# 1. The guard that cannot be forgotten
# ===========================================================================

def _resolves_access_context(route) -> bool:
    """Does this route resolve an AccessContext, directly or via a dependency?"""
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return False
    calls = {d.call for d in dependant.dependencies}
    for dep in dependant.dependencies:
        calls |= {d.call for d in dep.dependencies}
    return get_access_context in calls


def _app_routes():
    """Every route on the real application, with its path and methods."""
    from nanobio_studio.app.vertical_slice import app

    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is None or not methods:
            continue
        # Static-file mounts and the SPA fallback serve no database record.
        if getattr(route, "dependant", None) is None:
            continue
        yield route, path, methods


class TestEveryScopedRouteIsGuarded:
    """The structural check. Fail-closed across the whole application.

    Extended past the registry: this now walks every route the application
    serves, not one router. The rule is inverted from a protected-list —
    everything is required to resolve an ``AccessContext`` unless
    ``route_classification.EXEMPT_ROUTES`` says otherwise, with a reason.
    """

    def test_every_route_resolves_an_access_context_unless_exempted(self):
        """The guard referenced in ``RegistryActor.access``.

        That field is optional so several hundred existing unit tests can
        construct a bare actor without building an organization first — which
        would be a silent bypass if nothing checked that the *routes* always
        populate it. This is what checks.
        """
        from nanobio_studio.app.api.route_classification import (
            EXEMPT_ROUTES, KNOWN_UNCONVERTED_ROUTES, classify,
        )

        unguarded = []
        for route, path, methods in _app_routes():
            if path in EXEMPT_ROUTES or path in KNOWN_UNCONVERTED_ROUTES:
                continue
            if not _resolves_access_context(route):
                unguarded.append(
                    f"[{classify(path)}] {sorted(methods)} {path}")

        assert not unguarded, (
            f"{len(unguarded)} route(s) do not resolve an AccessContext and "
            f"are therefore outside the organization boundary. Either add the "
            f"dependency, or add the path to EXEMPT_ROUTES with a written "
            f"reason:\n  " + "\n  ".join(sorted(unguarded)))

    def test_every_exemption_names_a_real_route(self):
        """A stale exemption is worse than none.

        It sits in the list looking deliberate, and the day somebody adds a
        scoped route at that exact path it is silently unprotected.
        """
        from nanobio_studio.app.api.route_classification import EXEMPT_ROUTES

        paths = {path for _r, path, _m in _app_routes()}
        stale = sorted(set(EXEMPT_ROUTES) - paths)
        assert not stale, (
            f"these paths are exempted but are not routes: {stale}. Remove "
            f"them rather than leaving an entry that could later match a new "
            f"scoped endpoint.")

    def test_there_are_no_unconverted_routes_left(self):
        """The tracked gap is closed, and closing it is a claim under test.

        ``KNOWN_UNCONVERTED_ROUTES`` held the medical report paths until the
        medical-report isolation pass. It is now empty, and this pins it empty:
        re-introducing a gap must mean adding an entry with a written reason
        AND changing this test, rather than quietly omitting a dependency and
        adding the path to a list nobody reads.
        """
        from nanobio_studio.app.api.route_classification import (
            KNOWN_UNCONVERTED_ROUTES,
        )

        assert KNOWN_UNCONVERTED_ROUTES == {}, (
            f"{sorted(KNOWN_UNCONVERTED_ROUTES)} are exempt from the "
            f"structural guard as tracked gaps. Every organization-bearing "
            f"route is converted; convert the new one too rather than "
            f"re-opening the list.")

    def test_every_medical_report_route_resolves_a_context(self):
        """Named explicitly, because these hold the most sensitive data.

        The general guard already covers them now that they are not exempt.
        This says so by name, so that deleting the reports router — which would
        make the general guard pass vacuously — fails here instead.
        """
        from nanobio_studio.app.api.route_classification import EXEMPT_ROUTES

        report_routes = [
            (sorted(methods), path)
            for route, path, methods in _app_routes()
            if path.startswith("/api/v1/reports")
            and not _resolves_access_context(route)
            and path not in EXEMPT_ROUTES
        ]
        assert not report_routes, (
            f"unprotected medical report routes: {report_routes}")

        total = sum(1 for _r, path, _m in _app_routes()
                    if path.startswith("/api/v1/reports"))
        assert total >= 11, (
            f"only {total} medical report routes found; the router is missing "
            f"or was renamed, which would make the check above pass without "
            f"checking anything.")

    def test_unconverted_routes_are_not_also_exempted(self):
        """The two lists mean opposite things and must not overlap."""
        from nanobio_studio.app.api.route_classification import (
            EXEMPT_ROUTES, KNOWN_UNCONVERTED_ROUTES,
        )

        overlap = set(EXEMPT_ROUTES) & set(KNOWN_UNCONVERTED_ROUTES)
        assert not overlap, (
            f"{sorted(overlap)} is both 'owns no organization data' and "
            f"'owns organization data, unprotected'. One of those is wrong.")

    def test_every_exemption_carries_a_reason(self):
        from nanobio_studio.app.api.route_classification import EXEMPT_ROUTES

        for path, reason in EXEMPT_ROUTES.items():
            assert reason and len(reason) > 20, (
                f"{path} is exempted without a meaningful reason")

    def test_all_four_converted_groups_have_guarded_routes(self):
        """Guards against the guard passing because a group vanished.

        If a router were removed or renamed, every "no unguarded routes"
        assertion would still pass — vacuously. This asserts each converted
        group is actually present and actually protected.
        """
        from nanobio_studio.app.api.route_classification import (
            EXEMPT_ROUTES, classify,
        )

        guarded: dict[str, int] = {}
        for route, path, _m in _app_routes():
            if path in EXEMPT_ROUTES:
                continue
            if _resolves_access_context(route):
                group = classify(path)
                guarded[group] = guarded.get(group, 0) + 1

        for group in ("Validation Registry", "Workspace / projects",
                      "Runs / studies", "Scientific Readiness",
                      "Organization management", "Reports"):
            assert guarded.get(group, 0) > 0, (
                f"no guarded routes found in group {group!r}; the group is "
                f"missing or was never converted. Counts: {guarded}")


# ===========================================================================
# 2. Two organizations over HTTP
# ===========================================================================

@pytest.fixture(scope="module")
def two_organizations(tmp_path_factory):
    """Two organizations, each with a researcher, a study and an experiment.

    Built through the models rather than the API because the organization
    management endpoints are not part of this slice yet; what is under test is
    whether the *registry* routes respect the boundary, not how it was created.
    """
    from sqlalchemy import text

    from nanobio_studio.app.db.organization_models import (
        Organization, OrganizationMembership, StudyAssignment,
    )
    from nanobio_studio.app.db.validation_models import (
        Candidate, CandidateVersion, ExperimentVersion,
        ValidationExperiment,
    )
    from nanobio_studio.app.db.workspace_models import (
        Project, RecordOrigin, RunStatus, StoredRun,
    )
    from nanobio_studio.app.science.statuses import ReadinessArea
    from nanobio_studio.app.services.auth_service import create_user
    from nanobio_studio.app.validation.vocabulary import ExperimentSubtype

    tmp_dir = tmp_path_factory.mktemp("org_routes")
    app, client, factory = make_isolated_auth_client(tmp_dir)

    state: dict = {}

    async def seed():
        async with factory() as session:
            people = {}
            for name in ("acme_sci", "other_sci"):
                people[name] = await create_user(
                    session, username=name,
                    password="Fixture-Only-Passphrase-9f3a2b",
                    role=UserRole.RESEARCHER)
            await session.commit()

            for label, slug, who in (("acme", "acme-bio", "acme_sci"),
                                     ("other", "other-labs", "other_sci")):
                organization = Organization(
                    slug=slug, name=slug.title(),
                    status=OrganizationStatus.ACTIVE)
                session.add(organization)
                await session.flush()

                session.add(OrganizationMembership(
                    organization_id=organization.id, user_id=people[who].id,
                    role=OrganizationRole.RESEARCHER,
                    scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.ACTIVE))

                project = Project(name=f"{label} project",
                                  owner_id=people[who].id,
                                  organization_id=organization.id)
                session.add(project)
                await session.flush()

                study = StoredRun(
                    name=f"{label} study", project_id=project.id,
                    owner_id=people[who].id, origin=RecordOrigin.USER,
                    status=RunStatus.COMPLETE,
                    organization_id=organization.id)
                session.add(study)
                await session.flush()

                session.add(StudyAssignment(
                    organization_id=organization.id, study_id=study.id,
                    user_id=people[who].id, role=StudyRole.OWNER,
                    status=MembershipStatus.ACTIVE))

                candidate = Candidate(
                    code=f"{label.upper()}-C1", name=f"{label} candidate",
                    study_id=study.id, project_id=project.id,
                    owner_id=people[who].id,
                    organization_id=organization.id)
                session.add(candidate)
                await session.flush()

                # A frozen candidate version, because an experiment always
                # points at the exact material that was tested.
                snapshot = '{"size_nm": 100}'
                candidate_version = CandidateVersion(
                    candidate_id=candidate.id, version_number=1,
                    design_snapshot_json=snapshot,
                    snapshot_checksum=hashlib.sha256(
                        snapshot.encode()).hexdigest(),
                    created_by=people[who].id,
                    organization_id=organization.id)
                session.add(candidate_version)
                await session.flush()

                experiment = ValidationExperiment(
                    code=f"{label.upper()}-E1",
                    title=f"{label} experiment",
                    candidate_id=candidate.id, study_id=study.id,
                    project_id=project.id, owner_id=people[who].id,
                    subtype=ExperimentSubtype.CYTOTOXICITY,
                    purpose=ReadinessArea.SAFETY_ASSESSMENT,
                    organization_id=organization.id)
                session.add(experiment)
                await session.flush()

                # The listing joins versions to experiments, so without one
                # every assertion below would pass against an empty registry
                # and prove nothing.
                session.add(ExperimentVersion(
                    experiment_id=experiment.id, version_number=1,
                    candidate_version_id=candidate_version.id,
                    organization_id=organization.id))
                await session.flush()

                state[label] = {
                    "organization_id": organization.id,
                    "user": who,
                    "project_id": project.id,
                    "study_id": study.id,
                    "candidate_id": candidate.id,
                    "experiment_id": experiment.id,
                }

            # Extra accounts for the access-lifecycle tests.
            extras = {}
            for name in ("stranger", "revoked_user", "expired_user",
                         "suspended_user", "multi_org_user"):
                extras[name] = await create_user(
                    session, username=name,
                    password="Fixture-Only-Passphrase-9f3a2b",
                    role=UserRole.RESEARCHER)
            await session.flush()

            acme_id = state["acme"]["organization_id"]
            other_id = state["other"]["organization_id"]

            # 'stranger' deliberately gets no membership at all.
            session.add_all([
                OrganizationMembership(
                    organization_id=acme_id,
                    user_id=extras["revoked_user"].id,
                    role=OrganizationRole.RESEARCHER,
                    scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.REVOKED),
                OrganizationMembership(
                    organization_id=acme_id,
                    user_id=extras["suspended_user"].id,
                    role=OrganizationRole.RESEARCHER,
                    scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.SUSPENDED),
                OrganizationMembership(
                    organization_id=acme_id,
                    user_id=extras["expired_user"].id,
                    role=OrganizationRole.RESEARCHER,
                    scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.ACTIVE,
                    expires_at=datetime.now(timezone.utc) - timedelta(days=1)),
                # A consultant genuinely in both organizations.
                OrganizationMembership(
                    organization_id=acme_id,
                    user_id=extras["multi_org_user"].id,
                    role=OrganizationRole.RESEARCHER,
                    scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.ACTIVE),
                OrganizationMembership(
                    organization_id=other_id,
                    user_id=extras["multi_org_user"].id,
                    role=OrganizationRole.RESEARCHER,
                    scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.ACTIVE),
            ])
            await session.commit()

    with client:
        run_async(seed())
        yield app, client, state
    app.dependency_overrides.clear()


def _login(client, username: str) -> None:
    response = client.post("/api/v1/auth/login", json={
        "username": username,
        "password": "Fixture-Only-Passphrase-9f3a2b",
    })
    assert response.status_code == 200, response.text


class TestRegistryRoutesRespectTheBoundary:

    def test_the_listing_shows_only_your_own_organization(self,
                                                          two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        response = client.get("/api/v1/validation/experiments")
        assert response.status_code == 200, response.text
        titles = {row["title"] for row in response.json()["experiments"]}

        assert "acme experiment" in titles
        assert "other experiment" not in titles, (
            "the registry listing leaked another organization's experiment")

    def test_filtering_by_another_organizations_study_returns_nothing(
            self, two_organizations):
        """A query parameter must not reach past the boundary.

        The organization predicate is applied before any user filter, so no
        combination of parameters can widen the result set.
        """
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        response = client.get("/api/v1/validation/experiments",
                              params={"study_id": state["other"]["study_id"]})
        assert response.status_code == 200, response.text
        assert response.json()["experiments"] == []

    def test_fetching_another_organizations_experiment_is_404(
            self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        foreign = state["other"]["experiment_id"]
        response = client.get(f"/api/v1/validation/experiments/{foreign}")
        assert response.status_code == 404, response.text
        body = response.json()
        # The body must not confirm the record exists, name its organization
        # or explain that access was refused.
        text = repr(body).lower()
        assert "other" not in text
        assert "forbidden" not in text
        assert "permission" not in text

    def test_a_real_foreign_id_and_an_absent_id_are_indistinguishable(
            self, two_organizations):
        """The oracle test. Same status, same body shape."""
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        real_foreign = client.get(
            f"/api/v1/validation/experiments/"
            f"{state['other']['experiment_id']}")
        never_issued = client.get("/api/v1/validation/experiments/987654")

        assert real_foreign.status_code == never_issued.status_code == 404
        assert (real_foreign.json().keys()
                == never_issued.json().keys())
        assert (real_foreign.json()["error"]
                == never_issued.json()["error"])

    def test_another_organizations_audit_history_is_404(self,
                                                        two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])
        response = client.get(
            f"/api/v1/validation/experiments/"
            f"{state['other']['experiment_id']}/audit")
        assert response.status_code == 404, response.text

    def test_another_organizations_candidates_are_404(self,
                                                      two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])
        response = client.get(
            f"/api/v1/validation/studies/"
            f"{state['other']['study_id']}/candidates")
        assert response.status_code == 404, response.text

    def test_another_organizations_readiness_evidence_is_404(
            self, two_organizations):
        """Evidence leakage is the subtlest one: it exposes conclusions."""
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])
        response = client.get(
            f"/api/v1/validation/studies/"
            f"{state['other']['study_id']}/evidence")
        assert response.status_code == 404, response.text

    def test_another_organizations_contradictions_are_404(
            self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])
        response = client.get(
            f"/api/v1/validation/studies/"
            f"{state['other']['study_id']}/contradictions")
        assert response.status_code == 404, response.text

    def test_the_dashboard_counts_only_your_own_organization(
            self, two_organizations):
        """A count is a leak too: it reveals how much work someone else has."""
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        response = client.get("/api/v1/validation/dashboard")
        assert response.status_code == 200, response.text
        body = response.json()
        total = sum(body["by_status"].values())
        assert total <= 1, (
            f"dashboard counted {total} versions; only this organization's "
            f"records should be included")

    def test_writing_to_another_organizations_study_is_404(
            self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        response = client.post("/api/v1/validation/candidates", json={
            "study_id": state["other"]["study_id"],
            "code": "INTRUDER-1",
            "name": "Should not be created",
        })
        assert response.status_code == 404, response.text

    def test_the_other_organization_still_sees_its_own_records(
            self, two_organizations):
        """Isolation must not be achieved by breaking everybody's access."""
        _app, client, state = two_organizations
        _login(client, state["other"]["user"])

        response = client.get("/api/v1/validation/experiments")
        assert response.status_code == 200, response.text
        titles = {row["title"] for row in response.json()["experiments"]}
        assert "other experiment" in titles
        assert "acme experiment" not in titles


class TestOrganizationHeader:

    def test_naming_an_organization_you_are_not_in_returns_nothing(
            self, two_organizations):
        """The switcher narrows; it can never widen."""
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        response = client.get(
            "/api/v1/validation/experiments",
            headers={ORGANIZATION_HEADER: str(
                state["other"]["organization_id"])})
        assert response.status_code == 200, response.text
        assert response.json()["experiments"] == []

    def test_naming_your_own_organization_still_works(self,
                                                      two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        response = client.get(
            "/api/v1/validation/experiments",
            headers={ORGANIZATION_HEADER: str(
                state["acme"]["organization_id"])})
        assert response.status_code == 200, response.text
        assert len(response.json()["experiments"]) == 1

    def test_a_malformed_header_is_rejected_rather_than_ignored(
            self, two_organizations):
        """Falling back to "all organizations" would turn a typo into a widening."""
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        response = client.get("/api/v1/validation/experiments",
                              headers={ORGANIZATION_HEADER: "not-a-number"})
        assert response.status_code == 400, response.text
        assert response.json()["detail"]["error"] == "invalid_organization"


class TestUnauthenticatedAccess:

    def test_registry_routes_still_require_a_session(self, two_organizations):
        _app, client, state = two_organizations
        client.post("/api/v1/auth/logout")

        for path in (
            "/api/v1/validation/experiments",
            "/api/v1/validation/dashboard",
            f"/api/v1/validation/experiments/{state['acme']['experiment_id']}",
        ):
            response = client.get(path)
            assert response.status_code == 401, f"{path}: {response.text}"


# ===========================================================================
# 3. Workspace, runs and readiness over HTTP
# ===========================================================================

class TestRunAndWorkspaceRoutesRespectTheBoundary:
    """The routes converted in this milestone, proven over HTTP.

    Every negative here is paired with a positive control. A negative test on
    its own proves nothing: an endpoint that returned 404 to everybody, or a
    list that was always empty, would satisfy all of them while the feature
    was simply broken. That is not hypothetical — it happened while this file
    was being written, and only the positive controls caught it.
    """

    def test_run_listing_shows_your_own_and_not_the_others(
            self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        response = client.get("/api/v1/runs")
        assert response.status_code == 200, response.text
        names = {r["name"] for r in response.json()["runs"]}

        assert "acme study" in names, "positive control: own study missing"
        assert "other study" not in names, "run listing leaked another org"

    def test_run_total_counts_only_your_own_organization(self,
                                                         two_organizations):
        """An aggregate is a leak too.

        A total that counted rows the list cannot show would disclose how
        much work another organization holds.
        """
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        body = client.get("/api/v1/runs").json()
        assert body["total"] == len(body["runs"]), (
            f"total {body['total']} disagrees with {len(body['runs'])} "
            f"visible runs; the count is scoped differently from the list")
        assert body["total"] == 1

    def test_run_detail_positive_then_negative(self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        own = client.get(f"/api/v1/runs/{state['acme']['study_id']}")
        assert own.status_code == 200, own.text

        foreign = client.get(f"/api/v1/runs/{state['other']['study_id']}")
        assert foreign.status_code == 404, foreign.text

    def test_a_foreign_run_id_matches_an_absent_one(self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        foreign = client.get(f"/api/v1/runs/{state['other']['study_id']}")
        absent = client.get("/api/v1/runs/987654")
        assert foreign.status_code == absent.status_code == 404
        assert foreign.json() == absent.json(), (
            "a foreign run and an absent one produce different bodies, which "
            "is enough to tell them apart")

    def test_project_listing_is_scoped_with_a_positive_control(
            self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        response = client.get("/api/v1/projects")
        assert response.status_code == 200, response.text
        names = {p["name"] for p in response.json()["projects"]}
        assert "acme project" in names, "positive control: own project missing"
        assert "other project" not in names

    def test_deleting_another_organizations_run_is_404_and_changes_nothing(
            self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        victim = state["other"]["study_id"]
        response = client.delete(f"/api/v1/runs/{victim}")
        assert response.status_code == 404, response.text

        # And it is still there for its owner.
        _login(client, state["other"]["user"])
        assert client.get(f"/api/v1/runs/{victim}").status_code == 200

    def test_filtering_runs_cannot_reach_across(self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        response = client.get(
            "/api/v1/runs",
            params={"project_id": state["other"]["project_id"]})
        assert response.status_code == 200, response.text
        assert response.json()["runs"] == []
        assert response.json()["total"] == 0

    def test_reparenting_a_run_into_a_foreign_project_is_refused(
            self, two_organizations):
        """Parent injection.

        A legitimate run of the caller own, paired with a project id from
        another organization, hoping the write lands with the foreign parent
        attached and drags the run across the boundary.
        """
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        own_run = state["acme"]["study_id"]
        foreign_project = state["other"]["project_id"]

        response = client.post(
            f"/api/v1/runs/{own_run}/project?project_id={foreign_project}")
        assert response.status_code == 404, response.text

        # Positive control: the same call with its own project works.
        own_project = state["acme"]["project_id"]
        ok = client.post(
            f"/api/v1/runs/{own_run}/project?project_id={own_project}")
        assert ok.status_code == 200, ok.text
        assert ok.json()["project_id"] == own_project


class TestReadinessRoutesRespectTheBoundary:

    def test_readiness_summary_positive_then_negative(self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        own = client.get(
            f"/api/v1/science/studies/{state['acme']['study_id']}/readiness")
        assert own.status_code == 200, own.text
        assert "areas" in own.json(), "positive control: no readiness payload"

        foreign = client.get(
            f"/api/v1/science/studies/{state['other']['study_id']}/readiness")
        assert foreign.status_code == 404, foreign.text

    def test_readiness_records_are_scoped(self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        own = client.get(
            f"/api/v1/science/studies/{state['acme']['study_id']}/records")
        assert own.status_code == 200, own.text

        foreign = client.get(
            f"/api/v1/science/studies/{state['other']['study_id']}/records")
        assert foreign.status_code == 404, foreign.text

    def test_writing_a_record_to_a_foreign_study_is_refused(
            self, two_organizations):
        """A write is the one that matters: a leak here corrupts, not just discloses."""
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        payload = {"status": "measured", "value": "100", "unit": "nm",
                   "measurement_method": "cryo-TEM",
                   "measured_on": "2026-05-13"}
        foreign = client.put(
            f"/api/v1/science/studies/{state['other']['study_id']}"
            f"/records/physical_diameter", json=payload)
        assert foreign.status_code == 404, foreign.text
        # The study check runs before the field check, so a foreign study with
        # a nonexistent field is still a plain 404 rather than an
        # "unknown_field" message that would confirm the study resolved.
        assert foreign.json()["error"] == "not_found", foreign.text

        own = client.put(
            f"/api/v1/science/studies/{state['acme']['study_id']}"
            f"/records/physical_diameter", json=payload)
        assert own.status_code in (200, 201), (
            f"positive control failed: {own.text}")

    def test_readiness_snapshots_are_scoped(self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        own = client.get(
            f"/api/v1/science/studies/{state['acme']['study_id']}"
            f"/readiness/snapshots")
        assert own.status_code == 200, own.text

        foreign = client.get(
            f"/api/v1/science/studies/{state['other']['study_id']}"
            f"/readiness/snapshots")
        assert foreign.status_code == 404, foreign.text


class TestAccessLifecycleOverHttp:
    """Membership states, end to end."""

    def test_a_user_with_no_membership_sees_nothing_anywhere(
            self, two_organizations):
        _app, client, _state = two_organizations
        _login(client, "stranger")

        # Keyed explicitly rather than with `or`: an empty list is falsy, so
        # chaining `.get()` calls would skip past the very result being
        # asserted and compare None instead.
        for path, key in (("/api/v1/runs", "runs"),
                          ("/api/v1/projects", "projects"),
                          ("/api/v1/validation/experiments", "experiments")):
            response = client.get(path)
            assert response.status_code == 200, f"{path}: {response.text}"
            assert response.json()[key] == [], (
                f"{path} returned {response.json()[key]}")

    @pytest.mark.parametrize("username", [
        "revoked_user", "suspended_user", "expired_user",
    ])
    def test_ended_memberships_grant_nothing(self, two_organizations,
                                             username):
        """Revoked, suspended and expired all block.

        Expiry matters most: it is evaluated on read rather than left to a
        sweep, so a failed housekeeping job cannot silently extend access.
        """
        _app, client, state = two_organizations
        _login(client, username)

        listing = client.get("/api/v1/runs")
        assert listing.status_code == 200, listing.text
        assert listing.json()["runs"] == [], username

        detail = client.get(f"/api/v1/runs/{state['acme']['study_id']}")
        assert detail.status_code == 404, username

    def test_a_multi_organization_user_sees_both_until_they_choose(
            self, two_organizations):
        _app, client, state = two_organizations
        _login(client, "multi_org_user")

        both = client.get("/api/v1/runs")
        assert both.status_code == 200, both.text
        assert {r["name"] for r in both.json()["runs"]} == {
            "acme study", "other study"}, "positive control"

        for label in ("acme", "other"):
            narrowed = client.get("/api/v1/runs", headers={
                ORGANIZATION_HEADER: str(state[label]["organization_id"])})
            assert narrowed.status_code == 200, narrowed.text
            names = {r["name"] for r in narrowed.json()["runs"]}
            assert names == {f"{label} study"}, (
                f"selecting {label} returned {names}")
            assert narrowed.json()["total"] == 1

    def test_switching_organization_also_narrows_detail_and_readiness(
            self, two_organizations):
        """Switching must narrow every surface, not just the list.

        A switcher that filtered only the listing would leave detail pages
        reachable by identifier from the previous organization — which is
        exactly the stale-context leak the header exists to prevent.
        """
        _app, client, state = two_organizations
        _login(client, "multi_org_user")

        acme_header = {ORGANIZATION_HEADER: str(
            state["acme"]["organization_id"])}

        own = client.get(f"/api/v1/runs/{state['acme']['study_id']}",
                         headers=acme_header)
        assert own.status_code == 200, own.text

        other_study = state["other"]["study_id"]
        assert client.get(f"/api/v1/runs/{other_study}",
                          headers=acme_header).status_code == 404
        assert client.get(
            f"/api/v1/science/studies/{other_study}/readiness",
            headers=acme_header).status_code == 404
        assert client.get(
            f"/api/v1/validation/studies/{other_study}/candidates",
            headers=acme_header).status_code == 404

        # Positive control: with the other organization selected, they work.
        other_header = {ORGANIZATION_HEADER: str(
            state["other"]["organization_id"])}
        assert client.get(f"/api/v1/runs/{other_study}",
                          headers=other_header).status_code == 200


class TestCandidateAccessThroughRuns:
    """A candidate hidden in the registry must not surface via a run."""

    def test_a_foreign_studys_candidates_are_unreachable_by_either_path(
            self, two_organizations):
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        foreign_study = state["other"]["study_id"]

        # Positive control first: the same two paths work for own study.
        own_study = state["acme"]["study_id"]
        assert client.get(f"/api/v1/runs/{own_study}").status_code == 200
        own_candidates = client.get(
            f"/api/v1/validation/studies/{own_study}/candidates")
        assert own_candidates.status_code == 200, own_candidates.text
        assert own_candidates.json()["candidates"], "positive control empty"

        # Neither path reaches the other organization.
        assert client.get(
            f"/api/v1/runs/{foreign_study}").status_code == 404
        assert client.get(
            f"/api/v1/validation/studies/{foreign_study}/candidates"
        ).status_code == 404

    def test_a_foreign_candidate_name_never_appears_in_any_listing(
            self, two_organizations):
        """Names leak too: a candidate code can carry a programme name."""
        _app, client, state = two_organizations
        _login(client, state["acme"]["user"])

        blob = "".join([
            client.get("/api/v1/runs").text,
            client.get("/api/v1/projects").text,
            client.get("/api/v1/validation/experiments").text,
            client.get("/api/v1/validation/dashboard").text,
        ])
        assert "other candidate" not in blob
        assert "OTHER-C1" not in blob
        assert "other experiment" not in blob
        # Positive control: our own names are present, so the search is real.
        assert "acme study" in blob
