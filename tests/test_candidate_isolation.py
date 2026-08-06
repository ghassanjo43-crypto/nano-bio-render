"""Cross-organization isolation for candidates and candidate versions, over HTTP.

This file began as a probe asserting a defect and is now the permanent guard
against its return. The defect was real and serious:

    `create_candidate_version` loaded its candidate with a bare `session.get()`
    — no organization predicate, no study scope, no policy call — and neither
    did its route. Any authenticated account that could name a candidate id
    could append a scientific version to it. It did not need to be in the
    owning organization. It did not need to be in ANY organization. A suspended
    member could do it.

Three things made it worse than one missing check:

  * the written row had `organization_id` NULL, because the creation service
    never set it — so it belonged to no tenant;
  * the candidate listing did not scope versions at all, so the foreign row
    appeared in the owning organization's history looking exactly like one they
    had written;
  * a candidate version is what an eligibility gate resolves by checksum, so
    the injected row was usable as the scientific basis for real experiments.

Every denial below has an authorized positive control beside it, so a route
that refused everybody could not pass.
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
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

PASSWORD = "a-genuinely-long-fixture-passphrase"

DESIGN = {"size_nm": 95.0, "charge_mv": -12.0, "encapsulation_percent": 82.0}


@pytest.fixture(scope="module")
def two_orgs(tmp_path_factory):
    """Alpha and Beta, each with a study and a candidate."""
    from nanobio_studio.app.db.organization_models import (
        Organization, OrganizationMembership,
    )
    from nanobio_studio.app.db.validation_models import Candidate
    from nanobio_studio.app.db.workspace_models import StoredRun
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("candidate_isolation")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    CAST = {
        "alpha_owner": ("alpha", OrganizationRole.OWNER,
                        AccessScope.ORGANIZATION, {}),
        "alpha_researcher": ("alpha", OrganizationRole.RESEARCHER,
                             AccessScope.ORGANIZATION, {}),
        "alpha_assigned": ("alpha", OrganizationRole.RESEARCHER,
                           AccessScope.ASSIGNED_STUDIES, {}),
        "alpha_suspended": ("alpha", OrganizationRole.RESEARCHER,
                            AccessScope.ORGANIZATION,
                            {"status": MembershipStatus.SUSPENDED}),
        "alpha_revoked": ("alpha", OrganizationRole.RESEARCHER,
                          AccessScope.ORGANIZATION,
                          {"status": MembershipStatus.REVOKED}),
        "beta_researcher": ("beta", OrganizationRole.RESEARCHER,
                            AccessScope.ORGANIZATION, {}),
        "beta_owner": ("beta", OrganizationRole.OWNER,
                       AccessScope.ORGANIZATION, {}),
    }

    async def seed():
        async with factory() as session:
            users = {}
            for name in (*CAST, "unaffiliated"):
                users[name] = await create_user(
                    session, username=name, password=PASSWORD,
                    role=UserRole.RESEARCHER, email=f"{name}@candidates.test")
            await session.flush()

            alpha = Organization(slug="alpha-lab", name="Alpha Lab",
                                 status=OrganizationStatus.ACTIVE)
            beta = Organization(slug="beta-lab", name="Beta Lab",
                                status=OrganizationStatus.ACTIVE)
            session.add_all([alpha, beta])
            await session.flush()
            orgs = {"alpha": alpha, "beta": beta}

            for name, (org, role, scope, extra) in CAST.items():
                session.add(OrganizationMembership(
                    organization_id=orgs[org].id, user_id=users[name].id,
                    role=role, scope=scope,
                    status=extra.get("status", MembershipStatus.ACTIVE)))
            await session.flush()

            for key, organization, owner in (
                    ("alpha", alpha, users["alpha_researcher"]),
                    ("beta", beta, users["beta_researcher"])):
                run = StoredRun(
                    organization_id=organization.id, owner_id=owner.id,
                    name=f"{key} study")
                session.add(run)
                await session.flush()

                candidate = Candidate(
                    organization_id=organization.id, study_id=run.id,
                    owner_id=owner.id, code=f"{key.upper()}-1",
                    name=f"{key} candidate")
                session.add(candidate)
                await session.flush()

                state[f"{key}_study_id"] = run.id
                state[f"{key}_candidate_id"] = candidate.id

            await session.commit()
            state["alpha_id"] = alpha.id
            state["beta_id"] = beta.id
            state["users"] = {k: v.id for k, v in users.items()}

    with client:
        run_async(seed())
        yield app, client, state
    app.dependency_overrides.clear()


def _sign_in(client, username: str) -> None:
    client.post("/api/v1/auth/logout")
    response = client.post("/api/v1/auth/login",
                           json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text


def _add_version(client, candidate_id: int, organization_id: int | None = None,
                 note: str = "probe"):
    headers = ({"X-Organization-Id": str(organization_id)}
               if organization_id is not None else {})
    return client.post(
        f"/api/v1/validation/candidates/{candidate_id}/versions",
        headers=headers,
        json={"design_inputs": DESIGN, "note": note})


# ===========================================================================
# 1. The write is refused
# ===========================================================================

class TestCrossOrganizationVersionWriteIsRefused:

    def test_a_foreign_member_cannot_append_a_version(self, two_orgs):
        """A Beta researcher writing into Alpha's scientific record.

        404, not 403: a candidate in another organization must be
        indistinguishable from one that never existed, or the identifier space
        becomes an oracle for what Alpha is working on.
        """
        _app, client, state = two_orgs
        _sign_in(client, "beta_researcher")

        response = _add_version(client, state["alpha_candidate_id"],
                                state["beta_id"], note="written from Beta")
        assert response.status_code == 404, response.text

    def test_a_foreign_owner_gets_no_more_than_a_foreign_researcher(
            self, two_orgs):
        """Authority inside Beta grants nothing at all inside Alpha."""
        _app, client, state = two_orgs
        _sign_in(client, "beta_owner")

        response = _add_version(client, state["alpha_candidate_id"],
                                state["beta_id"])
        assert response.status_code == 404, response.text

    def test_an_unaffiliated_account_cannot_append_a_version(self, two_orgs):
        _app, client, state = two_orgs
        _sign_in(client, "unaffiliated")

        response = _add_version(client, state["alpha_candidate_id"])
        assert response.status_code == 404, response.text

    def test_a_suspended_member_cannot_append_a_version(self, two_orgs):
        """Enforced on the next request, not at the next cache expiry."""
        _app, client, state = two_orgs
        _sign_in(client, "alpha_suspended")

        response = _add_version(client, state["alpha_candidate_id"],
                                state["alpha_id"])
        assert response.status_code == 404, response.text

    def test_a_revoked_member_cannot_append_a_version(self, two_orgs):
        _app, client, state = two_orgs
        _sign_in(client, "alpha_revoked")

        response = _add_version(client, state["alpha_candidate_id"],
                                state["alpha_id"])
        assert response.status_code == 404, response.text

    def test_an_absent_and_a_foreign_identifier_are_indistinguishable(
            self, two_orgs):
        """Guessing must disclose nothing — not even existence."""
        _app, client, state = two_orgs
        _sign_in(client, "beta_researcher")

        foreign = _add_version(client, state["alpha_candidate_id"],
                               state["beta_id"])
        absent = _add_version(client, 999_999, state["beta_id"])

        assert foreign.status_code == absent.status_code == 404
        assert foreign.json() == absent.json(), (
            "a foreign candidate answers differently from an absent one, so "
            "the identifier space reveals which ids are real")

    def test_the_authorized_member_can_append_a_version(self, two_orgs):
        """Positive control.

        Without it, a route that refused everybody would look identical to a
        route that refused the right people.
        """
        _app, client, state = two_orgs
        _sign_in(client, "alpha_researcher")

        response = _add_version(client, state["alpha_candidate_id"],
                                state["alpha_id"], note="legitimate")
        assert response.status_code == 200, response.text
        assert "id" in response.json()


# ===========================================================================
# 2. The written row belongs to a tenant
# ===========================================================================

class TestTheWrittenRowCarriesItsOrganization:

    def test_a_new_version_inherits_the_candidates_organization(self, two_orgs):
        """NULL here made the row belong to nobody.

        `scoped()` filters on `organization_id IN (...)` and NULL is never in
        anything, so an unowned row is invisible to every scoped read — while
        still being present, and still being what an eligibility gate resolves
        by checksum.
        """
        from sqlalchemy import select

        from nanobio_studio.app.db.auth_session import get_auth_session
        from nanobio_studio.app.db.validation_models import CandidateVersion

        app, client, state = two_orgs
        _sign_in(client, "alpha_researcher")
        created = _add_version(client, state["alpha_candidate_id"],
                               state["alpha_id"], note="owned")
        assert created.status_code == 200, created.text
        version_id = created.json()["id"]

        async def scenario():
            generator = app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                return (await session.execute(
                    select(CandidateVersion).where(
                        CandidateVersion.id == version_id))).scalars().first()
            finally:
                await generator.aclose()

        version = run_async(scenario())
        assert version is not None
        assert version.organization_id == state["alpha_id"], (
            "the version does not carry its candidate's organization")

    def test_the_version_listing_is_organization_scoped(self):
        """The read side of the same defect."""
        import inspect

        from nanobio_studio.app.api.routes import validation

        source = inspect.getsource(validation.list_candidates)
        assert ("scoped(select(CandidateVersion), CandidateVersion, ctx)"
                in source)

    def test_the_owner_sees_their_own_versions(self, two_orgs):
        """Positive control for the scoping above.

        A filter that matched nothing would also pass a test asserting that
        foreign rows are absent.
        """
        _app, client, state = two_orgs
        _sign_in(client, "alpha_researcher")

        response = client.get(
            f"/api/v1/validation/studies/{state['alpha_study_id']}/candidates",
            headers={"X-Organization-Id": str(state["alpha_id"])})
        assert response.status_code == 200, response.text

        target = [c for c in response.json()["candidates"]
                  if c["id"] == state["alpha_candidate_id"]]
        assert target, "the candidate itself is not visible"
        assert target[0]["versions"], (
            "the owner cannot see their own versions — the scoping is too "
            "tight, which is the failure a foreign-row test cannot catch")

    def test_no_foreign_note_survives_in_the_history(self, two_orgs):
        """End to end: nothing written from Beta is in Alpha."""
        _app, client, state = two_orgs
        _sign_in(client, "alpha_researcher")

        response = client.get(
            f"/api/v1/validation/studies/{state['alpha_study_id']}/candidates",
            headers={"X-Organization-Id": str(state["alpha_id"])})
        target = [c for c in response.json()["candidates"]
                  if c["id"] == state["alpha_candidate_id"]][0]

        notes = [v.get("note") for v in target["versions"]]
        assert "written from Beta" not in notes
        assert "written by nobody" not in notes


# ===========================================================================
# 3. Candidate creation authorizes through the organization, not ownership
# ===========================================================================

class TestCandidateCreationAuthorization:

    def test_the_ownership_shortcut_is_gone(self):
        """`run.owner_id != actor.user_id` was wrong in both directions.

        It refused a colleague legitimately assigned to the study, and accepted
        a former owner who had since been removed from the organization.
        """
        import inspect

        from nanobio_studio.app.services import validation_service

        source = inspect.getsource(validation_service.create_candidate)
        assert "run.owner_id != actor.user_id" not in source

    def test_a_new_candidate_carries_its_studys_organization(self):
        import inspect

        from nanobio_studio.app.services import validation_service

        source = inspect.getsource(validation_service.create_candidate)
        assert "organization_id=run.organization_id" in source
