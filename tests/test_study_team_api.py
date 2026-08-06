"""Study teams: appointment authority, time limits and CRO restriction.

The question behind every test here
-----------------------------------
A study assignment is the *only* source of scientific capability. Membership of
an organization grants none. So if an assignment can be created by the wrong
person, for the wrong role, on somebody else's study, or can outlive its
agreement, then independent review is decoration — the person who administers
access can arrange to approve their own evidence.

The appointment-authority rule under test is documented in
``docs/APPOINTMENT_AUTHORITY.md``:

    Administrative roles appoint. Scientific roles act. One membership carries
    exactly one role, and nobody may change their own.

Each clause has its own test, because the rule is only as strong as its weakest
one: with clause 3 removed, clauses 1 and 2 are satisfied by an administrator
who promotes themselves first.

Every negative case is paired with a positive control. A test proving an
administrator cannot appoint themselves approver proves nothing if appointment
is broken for everybody.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
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

PASSWORD = "Fixture-Only-Passphrase-9f3a2b"


@pytest.fixture(scope="module")
def teamed(tmp_path_factory):
    """One organization with the full cast, and a second holding a foreign study."""
    from nanobio_studio.app.db.organization_models import (
        Organization, OrganizationMembership, StudyAssignment,
    )
    from nanobio_studio.app.db.workspace_models import (
        Project, RecordOrigin, RunStatus, StoredRun,
    )
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("study_team")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    CAST = {
        "team_owner": OrganizationRole.OWNER,
        "team_owner_two": OrganizationRole.OWNER,
        "team_admin": OrganizationRole.ADMINISTRATOR,
        "team_researcher": OrganizationRole.RESEARCHER,
        "team_reviewer": OrganizationRole.REVIEWER,
        "team_approver": OrganizationRole.APPROVER,
        "team_cro": OrganizationRole.LAB_CONTRIBUTOR,
        "team_auditor": OrganizationRole.AUDITOR,
    }

    async def seed():
        from sqlalchemy import select

        async with factory() as session:
            users = {}
            for name in list(CAST) + ["team_foreign_owner"]:
                users[name] = await create_user(
                    session, username=name, password=PASSWORD,
                    role=UserRole.RESEARCHER, email=f"{name}@team.test")
            await session.flush()

            acme = Organization(slug="team-acme", name="Team Acme",
                                status=OrganizationStatus.ACTIVE)
            foreign = Organization(slug="team-foreign", name="Team Foreign",
                                   status=OrganizationStatus.ACTIVE)
            session.add_all([acme, foreign])
            await session.flush()

            for name, role in CAST.items():
                session.add(OrganizationMembership(
                    organization_id=acme.id, user_id=users[name].id, role=role,
                    scope=(AccessScope.ORGANIZATION
                           if role in (OrganizationRole.OWNER,
                                       OrganizationRole.ADMINISTRATOR,
                                       OrganizationRole.AUDITOR)
                           else AccessScope.ASSIGNED_STUDIES),
                    status=MembershipStatus.ACTIVE,
                    external_organization=("Contract Labs Ltd"
                                           if name == "team_cro" else None),
                    may_download_attachments=(name != "team_cro")))
            session.add(OrganizationMembership(
                organization_id=foreign.id,
                user_id=users["team_foreign_owner"].id,
                role=OrganizationRole.OWNER, scope=AccessScope.ORGANIZATION,
                status=MembershipStatus.ACTIVE))
            await session.flush()

            for label, organization, who in (
                    ("acme", acme, "team_researcher"),
                    ("foreign", foreign, "team_foreign_owner")):
                project = Project(name=f"{label} project",
                                  owner_id=users[who].id,
                                  organization_id=organization.id)
                session.add(project)
                await session.flush()
                study = StoredRun(
                    name=f"{label} study", project_id=project.id,
                    owner_id=users[who].id, origin=RecordOrigin.USER,
                    status=RunStatus.COMPLETE,
                    organization_id=organization.id)
                session.add(study)
                await session.flush()
                session.add(StudyAssignment(
                    organization_id=organization.id, study_id=study.id,
                    user_id=users[who].id, role=StudyRole.OWNER,
                    status=MembershipStatus.ACTIVE))
                state[f"{label}_organization_id"] = organization.id
                state[f"{label}_study_id"] = study.id

            state["users"] = {k: v.id for k, v in users.items()}
            await session.commit()

            rows = (await session.execute(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == acme.id)
            )).scalars().all()
            state["memberships"] = {
                name: m.id for m in rows
                for name, uid in state["users"].items() if uid == m.user_id
            }

    with client:
        run_async(seed())
        yield app, client, state
    app.dependency_overrides.clear()


def _login(client, username: str) -> None:
    response = client.post("/api/v1/auth/login",
                           json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text


def _team_url(state) -> str:
    return (f"/api/v1/organizations/{state['acme_organization_id']}"
            f"/studies/{state['acme_study_id']}/team")


def _assign(client, state, who: str, role: str, **extra):
    body = {"user_id": state["users"][who], "role": role}
    body.update(extra)
    return client.post(_team_url(state), json=body)


def _revoke_all(client, state, who: str) -> None:
    """Leave the study team as it was found, whatever the test did to it."""
    listing = client.get(_team_url(state))
    if listing.status_code != 200:
        return
    for assignment in listing.json()["assignments"]:
        if (assignment["user_id"] == state["users"][who]
                and assignment["is_active"]):
            client.request("DELETE",
                           f"{_team_url(state)}/{assignment['id']}",
                           json={"reason": "Test cleanup."})


# ===========================================================================
# 1. Clause 1 — appointment is an administrative act
# ===========================================================================

class TestAppointmentIsAdministrative:

    def test_an_owner_may_appoint(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        response = _assign(client, state, "team_researcher", "contributor")
        assert response.status_code == 201, response.text
        assert response.json()["role"] == "contributor", "positive control"
        _revoke_all(client, state, "team_researcher")

    def test_an_administrator_may_appoint(self, teamed):
        _app, client, state = teamed
        _login(client, "team_admin")
        response = _assign(client, state, "team_reviewer", "reviewer")
        assert response.status_code == 201, response.text
        _revoke_all(client, state, "team_reviewer")

    def test_a_researcher_may_not_appoint(self, teamed):
        _app, client, state = teamed
        _login(client, "team_researcher")
        response = _assign(client, state, "team_reviewer", "reviewer")
        assert response.status_code == 403, response.text

    def test_a_reviewer_may_not_appoint_another_reviewer(self, teamed):
        """Scientific authority does not confer the power to hand it out."""
        _app, client, state = teamed
        _login(client, "team_reviewer")
        response = _assign(client, state, "team_approver", "approver")
        assert response.status_code == 403, response.text

    def test_an_auditor_may_not_appoint(self, teamed):
        _app, client, state = teamed
        _login(client, "team_auditor")
        response = _assign(client, state, "team_reviewer", "reviewer")
        assert response.status_code == 403, response.text

    def test_a_member_who_can_see_the_study_may_read_the_team(self, teamed):
        """Positive control: reading is not the same as appointing.

        The researcher owns this study, so they can see it and therefore its
        team, without holding any administrative role.
        """
        _app, client, state = teamed
        _login(client, "team_researcher")
        response = client.get(_team_url(state))
        assert response.status_code == 200, response.text

    def test_a_member_who_cannot_see_the_study_gets_404_not_a_roster(
            self, teamed):
        """The leak the browser walkthrough found.

        A member with ``ASSIGNED_STUDIES`` scope and no assignment on this
        study could read the whole team: names, roles and dates for work they
        cannot otherwise reach. Organization membership was being treated as
        enough, and it is not.

        404 rather than 403, matching the study itself: a study outside the
        caller's reach is never selected by the workspace queries, so the team
        endpoint must not be the one place that confirms it exists.
        """
        _app, client, state = teamed
        # The CRO holds an assigned-studies membership and no assignment here.
        _login(client, "team_cro")

        study = client.get(
            f"/api/v1/runs/{state['acme_study_id']}",
            headers={"X-Organization-Id": str(state["acme_organization_id"])})
        assert study.status_code == 404, (
            "fixture: this account must not be able to see the study")

        response = client.get(_team_url(state))
        assert response.status_code == 404, response.text
        assert "username" not in response.text


# ===========================================================================
# 2. Clause 2 — eligibility comes from the organization role
# ===========================================================================

class TestEligibilityGate:

    def test_an_organization_approver_may_be_assigned_approver(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        response = _assign(client, state, "team_approver", "approver")
        assert response.status_code == 201, "positive control"
        _revoke_all(client, state, "team_approver")

    def test_a_researcher_may_not_be_assigned_approver(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        response = _assign(client, state, "team_researcher", "approver")
        assert response.status_code == 409, response.text
        assert "organization role first" in response.json()["message"]

    def test_a_laboratory_contributor_may_not_be_assigned_reviewer(
            self, teamed):
        """A contract laboratory enters data; it does not review it."""
        _app, client, state = teamed
        _login(client, "team_owner")
        response = _assign(client, state, "team_cro", "reviewer")
        assert response.status_code == 409, response.text

    def test_a_laboratory_contributor_may_be_assigned_its_own_role(
            self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        response = _assign(client, state, "team_cro", "lab_contributor")
        assert response.status_code == 201, "positive control"
        _revoke_all(client, state, "team_cro")

    def test_an_owner_may_be_assigned_only_as_auditor(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        permitted = _assign(client, state, "team_owner_two", "auditor")
        assert permitted.status_code == 201, "positive control"
        refused = _assign(client, state, "team_owner_two", "contributor")
        assert refused.status_code == 409, refused.text
        _revoke_all(client, state, "team_owner_two")

    def test_somebody_outside_the_organization_cannot_be_assigned(
            self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        response = _assign(client, state, "team_foreign_owner", "contributor")
        assert response.status_code == 409, response.text
        assert "not an active member" in response.json()["message"]


# ===========================================================================
# 3. Clause 3 — nobody changes their own role, so nobody escalates alone
# ===========================================================================

class TestSelfEscalationIsImpossible:

    def test_an_administrator_cannot_appoint_themselves_approver(self, teamed):
        _app, client, state = teamed
        _login(client, "team_admin")
        response = _assign(client, state, "team_admin", "approver")
        assert response.status_code == 409, response.text

    def test_an_administrator_cannot_appoint_themselves_reviewer(self, teamed):
        _app, client, state = teamed
        _login(client, "team_admin")
        response = _assign(client, state, "team_admin", "reviewer")
        assert response.status_code == 409, response.text

    def test_an_administrator_cannot_promote_themselves_to_become_eligible(
            self, teamed):
        """The two-step escalation, closed at the first step."""
        _app, client, state = teamed
        _login(client, "team_admin")
        response = client.patch(
            f"/api/v1/organizations/{state['acme_organization_id']}/members/"
            f"{state['memberships']['team_admin']}",
            json={"role": "approver"})
        assert response.status_code == 409, response.text
        assert "your own" in response.json()["message"].lower()

    def test_an_owner_cannot_promote_themselves_either(self, teamed):
        """The bar applies to everyone, or it is not a bar."""
        _app, client, state = teamed
        _login(client, "team_owner")
        response = client.patch(
            f"/api/v1/organizations/{state['acme_organization_id']}/members/"
            f"{state['memberships']['team_owner']}",
            json={"role": "approver"})
        assert response.status_code == 409, response.text

    def test_another_administrator_can_make_the_same_change(self, teamed):
        """Positive control: the bar is on self-change, not on the change."""
        _app, client, state = teamed
        _login(client, "team_owner")
        response = client.patch(
            f"/api/v1/organizations/{state['acme_organization_id']}/members/"
            f"{state['memberships']['team_admin']}",
            json={"role": "reviewer"})
        assert response.status_code == 200, response.text
        assert response.json()["role"] == "reviewer"

        restored = client.patch(
            f"/api/v1/organizations/{state['acme_organization_id']}/members/"
            f"{state['memberships']['team_admin']}",
            json={"role": "administrator"})
        assert restored.status_code == 200, restored.text

    def test_promotion_costs_the_administrator_their_administrative_role(
            self, teamed):
        """One membership, one role. The two ladders never overlap."""
        _app, client, state = teamed
        _login(client, "team_owner")
        promoted = client.patch(
            f"/api/v1/organizations/{state['acme_organization_id']}/members/"
            f"{state['memberships']['team_admin']}",
            json={"role": "approver"})
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["is_administrative"] is False

        _login(client, "team_admin")
        refused = _assign(client, state, "team_reviewer", "reviewer")
        assert refused.status_code == 403, (
            "an approver must not retain the power to appoint")

        _login(client, "team_owner")
        client.patch(
            f"/api/v1/organizations/{state['acme_organization_id']}/members/"
            f"{state['memberships']['team_admin']}",
            json={"role": "administrator"})


# ===========================================================================
# 4. Cross-organization injection
# ===========================================================================

class TestCrossOrganizationInjection:

    def test_a_foreign_study_id_under_your_own_organization_is_404(
            self, teamed):
        """Naming your organization does not make their study yours."""
        _app, client, state = teamed
        _login(client, "team_owner")
        response = client.post(
            f"/api/v1/organizations/{state['acme_organization_id']}"
            f"/studies/{state['foreign_study_id']}/team",
            json={"user_id": state["users"]["team_researcher"],
                  "role": "contributor"})
        assert response.status_code == 404, response.text

    def test_a_foreign_study_and_an_absent_one_are_indistinguishable(
            self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        foreign = client.get(
            f"/api/v1/organizations/{state['acme_organization_id']}"
            f"/studies/{state['foreign_study_id']}/team")
        absent = client.get(
            f"/api/v1/organizations/{state['acme_organization_id']}"
            f"/studies/99999999/team")
        assert foreign.status_code == absent.status_code == 404
        assert foreign.json() == absent.json()

    def test_your_own_study_is_reachable(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        response = client.get(_team_url(state))
        assert response.status_code == 200, "positive control"

    def test_a_foreign_assignment_id_cannot_be_revoked(self, teamed):
        from sqlalchemy import select

        from nanobio_studio.app.db.organization_models import StudyAssignment

        _app, client, state = teamed

        async def foreign_assignment_id():
            from nanobio_studio.app.db.auth_session import get_auth_session
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                return (await session.execute(
                    select(StudyAssignment.id).where(
                        StudyAssignment.study_id
                        == state["foreign_study_id"])
                )).scalars().first()
            finally:
                await generator.aclose()

        foreign = run_async(foreign_assignment_id())
        assert foreign is not None, "fixture"

        _login(client, "team_owner")
        response = client.request(
            "DELETE", f"{_team_url(state)}/{foreign}", json={})
        assert response.status_code == 404, response.text


# ===========================================================================
# 5. Time limits, suspension and revocation
# ===========================================================================

class TestAssignmentLifecycle:

    def _future(self, days: int) -> str:
        return (datetime.now(timezone.utc)
                + timedelta(days=days)).isoformat()

    def test_start_and_expiry_dates_are_recorded(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        response = _assign(client, state, "team_cro", "lab_contributor",
                           starts_at=self._future(1),
                           expires_at=self._future(30),
                           note="Contract CRO-2026-014.")
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["starts_at"] and body["expires_at"]
        assert body["note"] == "Contract CRO-2026-014."
        _revoke_all(client, state, "team_cro")

    def test_an_expiry_before_the_start_is_refused(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        response = _assign(client, state, "team_cro", "lab_contributor",
                           starts_at=self._future(30),
                           expires_at=self._future(1))
        assert response.status_code == 409, response.text
        assert "after the start date" in response.json()["message"]

    def test_a_duplicate_active_assignment_is_refused(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        first = _assign(client, state, "team_reviewer", "reviewer")
        assert first.status_code == 201, "positive control"
        second = _assign(client, state, "team_reviewer", "reviewer")
        assert second.status_code == 409, second.text
        assert "already exists" in second.json()["message"]
        _revoke_all(client, state, "team_reviewer")

    def test_an_assignment_can_be_amended_and_then_revoked(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        created = _assign(client, state, "team_reviewer", "reviewer",
                          expires_at=self._future(10))
        assignment_id = created.json()["id"]

        amended = client.patch(
            f"{_team_url(state)}/{assignment_id}",
            json={"expires_at": self._future(60),
                  "note": "Extended to cover the second batch.",
                  "expected_revision": created.json()["revision"]})
        assert amended.status_code == 200, amended.text
        assert amended.json()["note"] == "Extended to cover the second batch."

        revoked = client.request(
            "DELETE", f"{_team_url(state)}/{assignment_id}",
            json={"reason": "Study closed.",
                  "expected_revision": amended.json()["revision"]})
        assert revoked.status_code == 200, revoked.text
        assert revoked.json()["status"] == "revoked"
        assert "already happened" in revoked.json()["notice"]

    def test_amending_against_a_stale_revision_is_refused(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        created = _assign(client, state, "team_reviewer", "reviewer")
        assignment_id = created.json()["id"]
        stale = created.json()["revision"]

        first = client.patch(f"{_team_url(state)}/{assignment_id}",
                             json={"note": "First administrator.",
                                   "expected_revision": stale})
        assert first.status_code == 200, "positive control"

        second = client.patch(f"{_team_url(state)}/{assignment_id}",
                              json={"note": "Second administrator.",
                                    "expected_revision": stale})
        assert second.status_code == 409, second.text
        assert second.json()["error"] == "concurrent_modification"

        current = client.get(_team_url(state))
        row = [a for a in current.json()["assignments"]
               if a["id"] == assignment_id][0]
        assert row["note"] == "First administrator.", "no lost update"

        _revoke_all(client, state, "team_reviewer")

    def test_revocation_preserves_the_historical_record(self, teamed):
        """Access ends. Attribution does not."""
        _app, client, state = teamed
        _login(client, "team_owner")
        created = _assign(client, state, "team_reviewer", "reviewer",
                          note="Appointed for batch one.")
        assignment_id = created.json()["id"]
        client.request("DELETE", f"{_team_url(state)}/{assignment_id}",
                       json={"reason": "Rotation."})

        listing = client.get(_team_url(state))
        row = [a for a in listing.json()["assignments"]
               if a["id"] == assignment_id][0]
        assert row["status"] == "revoked"
        assert row["is_active"] is False
        assert row["note"] == "Appointed for batch one."
        assert row["end_reason"] == "Rotation."

    def test_revoked_access_stops_at_the_next_request(self, teamed):
        """The context is rebuilt per request, so there is no stale window."""
        _app, client, state = teamed
        _login(client, "team_owner")
        created = _assign(client, state, "team_reviewer", "contributor")
        assignment_id = created.json()["id"]

        _login(client, "team_reviewer")
        before = client.get(
            f"/api/v1/runs/{state['acme_study_id']}",
            headers={"X-Organization-Id": str(state["acme_organization_id"])})
        assert before.status_code == 200, "positive control: assigned"

        _login(client, "team_owner")
        client.request("DELETE", f"{_team_url(state)}/{assignment_id}",
                       json={"reason": "Immediate."})

        _login(client, "team_reviewer")
        after = client.get(
            f"/api/v1/runs/{state['acme_study_id']}",
            headers={"X-Organization-Id": str(state["acme_organization_id"])})
        assert after.status_code == 404, after.text


# ===========================================================================
# 6. External collaborator restriction
# ===========================================================================

class TestCollaboratorRestriction:

    def test_a_restricted_membership_cannot_download_attachments(self, teamed):
        from nanobio_studio.app.organizations.policy import (
            Action, RecordFacts, may, resolve_context,
        )

        _app, client, state = teamed

        async def decide(username: str):
            from sqlalchemy import select

            from nanobio_studio.app.db.auth_models import User
            from nanobio_studio.app.db.auth_session import get_auth_session
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                user = (await session.execute(
                    select(User).where(User.username == username)
                )).scalar_one()
                ctx = await resolve_context(session, user)
                return may(ctx, Action.DOWNLOAD_ATTACHMENT, RecordFacts(
                    organization_id=state["acme_organization_id"],
                    study_id=state["acme_study_id"]))
            finally:
                await generator.aclose()

        # The auditor holds organization-wide scope and an unrestricted
        # membership, so this is the "nothing is in the way" case.
        allowed, _reason = run_async(decide("team_auditor"))
        assert allowed is True, "positive control"

        refused, reason = run_async(decide("team_cro"))
        assert refused is False
        assert "downloading attachments" in reason

    def test_a_per_study_restriction_subtracts_from_a_permitted_membership(
            self, teamed):
        """One study's agreement may be narrower than the collaboration."""
        from nanobio_studio.app.organizations.policy import (
            Action, RecordFacts, may, resolve_context,
        )

        _app, client, state = teamed
        _login(client, "team_owner")
        created = _assign(client, state, "team_reviewer", "reviewer",
                          may_download_attachments=False)
        assert created.status_code == 201, created.text
        assert created.json()["may_download_attachments"] is False

        async def decide():
            from sqlalchemy import select

            from nanobio_studio.app.db.auth_models import User
            from nanobio_studio.app.db.auth_session import get_auth_session
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                user = (await session.execute(
                    select(User).where(User.username == "team_reviewer")
                )).scalar_one()
                ctx = await resolve_context(session, user)
                return may(ctx, Action.DOWNLOAD_ATTACHMENT, RecordFacts(
                    organization_id=state["acme_organization_id"],
                    study_id=state["acme_study_id"]))
            finally:
                await generator.aclose()

        allowed, reason = run_async(decide())
        assert allowed is False, reason
        assert "assignment on this study" in reason

        _revoke_all(client, state, "team_reviewer")

    def test_an_unrestricted_assignment_leaves_the_membership_alone(
            self, teamed):
        """Positive control: NULL defers, it does not deny."""
        from nanobio_studio.app.organizations.policy import (
            Action, RecordFacts, may, resolve_context,
        )

        _app, client, state = teamed
        _login(client, "team_owner")
        created = _assign(client, state, "team_reviewer", "reviewer")
        assert created.json()["may_download_attachments"] is None

        async def decide():
            from sqlalchemy import select

            from nanobio_studio.app.db.auth_models import User
            from nanobio_studio.app.db.auth_session import get_auth_session
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                user = (await session.execute(
                    select(User).where(User.username == "team_reviewer")
                )).scalar_one()
                ctx = await resolve_context(session, user)
                return may(ctx, Action.DOWNLOAD_ATTACHMENT, RecordFacts(
                    organization_id=state["acme_organization_id"],
                    study_id=state["acme_study_id"]))
            finally:
                await generator.aclose()

        allowed, _reason = run_async(decide())
        assert allowed is True
        _revoke_all(client, state, "team_reviewer")

    def test_a_collaborator_reaches_no_unrelated_study(self, teamed):
        _app, client, state = teamed
        _login(client, "team_cro")
        response = client.get(
            f"/api/v1/runs/{state['foreign_study_id']}",
            headers={"X-Organization-Id": str(state["acme_organization_id"])})
        assert response.status_code == 404, response.text

    def test_a_collaborator_sees_no_organization_wide_records(self, teamed):
        """Assigned-studies scope means what it says."""
        _app, client, state = teamed
        _login(client, "team_cro")
        response = client.get(
            "/api/v1/runs",
            headers={"X-Organization-Id": str(state["acme_organization_id"])})
        assert response.status_code == 200, response.text
        assert response.json()["runs"] == [], (
            "an unassigned collaborator must see nothing")


# ===========================================================================
# 7. Assignment history
# ===========================================================================

class TestAssignmentHistory:

    def test_the_history_records_appointment_amendment_and_revocation(
            self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        created = _assign(client, state, "team_approver", "approver",
                          note="Appointed to approve batch two.")
        assignment_id = created.json()["id"]
        client.patch(f"{_team_url(state)}/{assignment_id}",
                     json={"note": "Extended."})
        client.request("DELETE", f"{_team_url(state)}/{assignment_id}",
                       json={"reason": "Study closed."})

        history = client.get(f"{_team_url(state)}/history")
        assert history.status_code == 200, history.text
        events = [e["event"] for e in history.json()["events"]]
        assert "assignment_created" in events
        assert "assignment_amended" in events
        assert "assignment_revoked" in events
        assert all(e["actor_username"] == "team_owner"
                   for e in history.json()["events"]
                   if e["subject_id"] == assignment_id)

    def test_a_researcher_cannot_read_the_appointment_history(self, teamed):
        """Who appointed whom is access-control information."""
        _app, client, state = teamed
        _login(client, "team_researcher")
        response = client.get(f"{_team_url(state)}/history")
        assert response.status_code == 403, response.text

    def test_an_auditor_can_read_the_appointment_history(self, teamed):
        _app, client, state = teamed
        _login(client, "team_auditor")
        response = client.get(f"{_team_url(state)}/history")
        assert response.status_code == 200, "positive control"

    def test_the_history_of_a_foreign_study_is_404(self, teamed):
        _app, client, state = teamed
        _login(client, "team_owner")
        response = client.get(
            f"/api/v1/organizations/{state['acme_organization_id']}"
            f"/studies/{state['foreign_study_id']}/team/history")
        assert response.status_code == 404, response.text


# ===========================================================================
# 8. Confirmation of a migrated organization adds no scientific authority
# ===========================================================================

class TestAuditCompleteness:

    def test_every_management_action_writes_an_audit_row(self, teamed):
        """An access review reads the trail, not the current rows."""
        _app, client, state = teamed
        _login(client, "team_owner")
        organization_id = state["acme_organization_id"]

        created = _assign(client, state, "team_reviewer", "reviewer")
        client.patch(f"{_team_url(state)}/{created.json()['id']}",
                     json={"note": "Audited amendment."})
        client.request("DELETE", f"{_team_url(state)}/{created.json()['id']}",
                       json={"reason": "Audited revocation."})
        client.post(
            f"/api/v1/organizations/{organization_id}/members/"
            f"{state['memberships']['team_researcher']}/status",
            json={"status": "suspended", "reason": "Audited suspension."})
        client.post(
            f"/api/v1/organizations/{organization_id}/members/"
            f"{state['memberships']['team_researcher']}/status",
            json={"status": "active"})

        audit = client.get(
            f"/api/v1/organizations/{organization_id}/audit?limit=500")
        assert audit.status_code == 200, audit.text
        events = {e["event"] for e in audit.json()["events"]}
        for expected in ("assignment_created", "assignment_amended",
                         "assignment_revoked", "member_suspended",
                         "member_reinstated"):
            assert expected in events, expected

        # Every row names who did it and what happened, and none of them
        # carries a credential.
        for row in audit.json()["events"]:
            assert row["summary"]
            assert PASSWORD not in row["summary"]
