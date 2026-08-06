"""Organization and study-team management over HTTP.

The question this suite exists to answer
----------------------------------------
The management API hands out access. If it can be persuaded to hand out
*scientific* authority, then every rule the registry enforces — independent
review, no self-approval, administrators cannot approve — becomes reachable by
anyone who can administer an organization.

So the centre of this file is escalation, not CRUD. The CRUD tests are here to
provide positive controls: a negative test proves nothing if the endpoint is
simply broken for everybody.

One finding is recorded directly as a test
------------------------------------------
``test_an_administrator_cannot_promote_themselves`` covers a hole that existed
in the implementation and was found by probing the service before this API was
written. An administrator could set their own organization role to APPROVER,
then assign themselves as study approver, then approve evidence — two requests,
no second person, and an audit trail showing a routine role change.
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

from nanobio_studio.app.api.deps_organization import (  # noqa: E402
    ORGANIZATION_HEADER,
)
from nanobio_studio.app.db.auth_models import UserRole  # noqa: E402
from nanobio_studio.app.organizations.vocabulary import (  # noqa: E402
    AccessScope, MembershipStatus, OrganizationRole, OrganizationStatus,
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

PASSWORD = "Fixture-Only-Passphrase-9f3a2b"


@pytest.fixture(scope="module")
def managed(tmp_path_factory):
    """Two organizations with a full cast, built through the models.

    Acme: owner, second_owner, admin, researcher, reviewer_person,
          approver_person, cro_person, auditor_person.
    Other: outsider_owner, with its own study.
    """
    from nanobio_studio.app.db.organization_models import (
        Organization, OrganizationMembership, StudyAssignment,
    )
    from nanobio_studio.app.db.workspace_models import (
        Project, RecordOrigin, RunStatus, StoredRun,
    )
    from nanobio_studio.app.organizations.vocabulary import StudyRole
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("org_mgmt")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {"acme": {}, "other": {}}

    CAST = {
        "owner": OrganizationRole.OWNER,
        "second_owner": OrganizationRole.OWNER,
        "admin": OrganizationRole.ADMINISTRATOR,
        "researcher": OrganizationRole.RESEARCHER,
        "reviewer_person": OrganizationRole.REVIEWER,
        "approver_person": OrganizationRole.APPROVER,
        "cro_person": OrganizationRole.LAB_CONTRIBUTOR,
        "auditor_person": OrganizationRole.AUDITOR,
    }

    async def seed():
        async with factory() as session:
            users = {}
            for name in list(CAST) + ["outsider_owner", "unaffiliated"]:
                role = (UserRole.ADMIN if name in ("owner", "admin",
                                                   "outsider_owner")
                        else UserRole.RESEARCHER)
                users[name] = await create_user(
                    session, username=name, password=PASSWORD, role=role)
            await session.flush()

            acme = Organization(slug="acme-bio", name="Acme Bio",
                                status=OrganizationStatus.ACTIVE)
            other = Organization(slug="other-labs", name="Other Labs",
                                 status=OrganizationStatus.ACTIVE)
            migrated = Organization(
                slug="migrated-org", name="Migrated Org",
                status=OrganizationStatus.PENDING_CONFIRMATION,
                is_legacy=True)
            session.add_all([acme, other, migrated])
            await session.flush()

            for name, role in CAST.items():
                session.add(OrganizationMembership(
                    organization_id=acme.id, user_id=users[name].id,
                    role=role,
                    scope=(AccessScope.ORGANIZATION
                           if role in (OrganizationRole.OWNER,
                                       OrganizationRole.ADMINISTRATOR,
                                       OrganizationRole.AUDITOR)
                           else AccessScope.ASSIGNED_STUDIES),
                    status=MembershipStatus.ACTIVE))

            session.add_all([
                OrganizationMembership(
                    organization_id=other.id,
                    user_id=users["outsider_owner"].id,
                    role=OrganizationRole.OWNER,
                    scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.ACTIVE),
                OrganizationMembership(
                    organization_id=migrated.id, user_id=users["owner"].id,
                    role=OrganizationRole.OWNER,
                    scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.ACTIVE),
            ])
            await session.flush()

            for label, organization, who in (
                    ("acme", acme, "researcher"),
                    ("other", other, "outsider_owner")):
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
                state[label]["organization_id"] = organization.id
                state[label]["study_id"] = study.id

            state["migrated_organization_id"] = migrated.id
            state["users"] = {k: v.id for k, v in users.items()}
            await session.commit()

            memberships = {}
            from sqlalchemy import select
            rows = (await session.execute(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == acme.id)
            )).scalars().all()
            for m in rows:
                for name, uid in state["users"].items():
                    if uid == m.user_id:
                        memberships[name] = m.id
            state["memberships"] = memberships

    with client:
        run_async(seed())
        yield app, client, state
    app.dependency_overrides.clear()


def _login(client, username: str) -> None:
    response = client.post("/api/v1/auth/login",
                           json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text


def _acme(state) -> int:
    return state["acme"]["organization_id"]


# ===========================================================================
# 1. Who may administer
# ===========================================================================

class TestAdministrativePermissions:

    def test_an_owner_can_list_members(self, managed):
        _app, client, state = managed
        _login(client, "owner")
        response = client.get(
            f"/api/v1/organizations/{_acme(state)}/members")
        assert response.status_code == 200, response.text
        names = {m["username"] for m in response.json()["members"]}
        assert "researcher" in names, "positive control"

    def test_an_administrator_can_list_members(self, managed):
        _app, client, state = managed
        _login(client, "admin")
        assert client.get(
            f"/api/v1/organizations/{_acme(state)}/members"
        ).status_code == 200

    def test_a_researcher_cannot_add_a_member(self, managed):
        _app, client, state = managed
        _login(client, "researcher")
        response = client.post(
            f"/api/v1/organizations/{_acme(state)}/members",
            json={"user_id": state["users"]["unaffiliated"],
                  "role": "researcher"})
        assert response.status_code == 403, response.text
        assert "administrator" in response.json()["message"].lower()

    def test_an_auditor_cannot_change_anything(self, managed):
        """Read-only is the entire content of the role."""
        _app, client, state = managed
        _login(client, "auditor_person")

        assert client.get(
            f"/api/v1/organizations/{_acme(state)}/members"
        ).status_code == 200, "positive control: an auditor reads"

        response = client.post(
            f"/api/v1/organizations/{_acme(state)}/members",
            json={"user_id": state["users"]["unaffiliated"],
                  "role": "researcher"})
        assert response.status_code == 403, response.text

    def test_administration_of_another_organization_is_404(self, managed):
        """Not 403 — the caller must not learn the organization exists."""
        _app, client, state = managed
        _login(client, "owner")

        foreign = state["other"]["organization_id"]
        assert client.get(
            f"/api/v1/organizations/{foreign}/members").status_code == 404
        assert client.get(
            f"/api/v1/organizations/{foreign}").status_code == 404
        assert client.get(
            f"/api/v1/organizations/{foreign}/audit").status_code == 404

    def test_a_foreign_organization_and_an_absent_one_look_the_same(
            self, managed):
        _app, client, state = managed
        _login(client, "owner")
        foreign = client.get(
            f"/api/v1/organizations/{state['other']['organization_id']}")
        absent = client.get("/api/v1/organizations/987654")
        assert foreign.status_code == absent.status_code == 404
        assert foreign.json() == absent.json()


# ===========================================================================
# 2. Escalation
# ===========================================================================

class TestEscalationIsImpossible:
    """The reason this API needed writing carefully."""

    def test_an_administrator_cannot_promote_themselves(self, managed):
        """The hole that existed, now closed.

        Two requests would otherwise have taken an administrator from
        "manages access" to "approves evidence" with nobody else involved.
        """
        _app, client, state = managed
        _login(client, "admin")

        response = client.patch(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['admin']}",
            json={"role": "approver"})
        assert response.status_code == 409, response.text
        assert "your own" in response.json()["message"].lower()

        # And they are still an administrator.
        _login(client, "owner")
        members = client.get(
            f"/api/v1/organizations/{_acme(state)}/members").json()["members"]
        admin = next(m for m in members if m["username"] == "admin")
        assert admin["role"] == "administrator"

    def test_an_owner_cannot_promote_themselves_either(self, managed):
        """The bar is not "administrators"; it is everybody."""
        _app, client, state = managed
        _login(client, "owner")
        response = client.patch(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['owner']}",
            json={"role": "approver"})
        assert response.status_code == 409, response.text

    def test_an_administrator_cannot_assign_themselves_as_approver(
            self, managed):
        """The second half of the two-act path, blocked independently."""
        _app, client, state = managed
        _login(client, "admin")

        response = client.post(
            f"/api/v1/organizations/{_acme(state)}"
            f"/studies/{state['acme']['study_id']}/team",
            json={"user_id": state["users"]["admin"], "role": "approver"})
        assert response.status_code == 409, response.text
        assert "cannot hold the study role" in response.json()["message"]

    def test_a_researcher_cannot_be_assigned_approver(self, managed):
        """Eligibility comes from the organization role, not the appointment."""
        _app, client, state = managed
        _login(client, "admin")
        response = client.post(
            f"/api/v1/organizations/{_acme(state)}"
            f"/studies/{state['acme']['study_id']}/team",
            json={"user_id": state["users"]["researcher"],
                  "role": "approver"})
        assert response.status_code == 409, response.text

    def test_an_approver_can_be_assigned_approver(self, managed):
        """Positive control: the legitimate path works.

        Without this, every test above would pass against an endpoint that
        simply refused all assignments.
        """
        _app, client, state = managed
        _login(client, "admin")
        response = client.post(
            f"/api/v1/organizations/{_acme(state)}"
            f"/studies/{state['acme']['study_id']}/team",
            json={"user_id": state["users"]["approver_person"],
                  "role": "approver"})
        assert response.status_code == 201, response.text
        assert response.json()["role"] == "approver"
        assert response.json()["is_active"] is True

    def test_assigning_into_another_organizations_study_is_404(self, managed):
        """Parent injection: own organization id, foreign study id."""
        _app, client, state = managed
        _login(client, "owner")
        response = client.post(
            f"/api/v1/organizations/{_acme(state)}"
            f"/studies/{state['other']['study_id']}/team",
            json={"user_id": state["users"]["researcher"],
                  "role": "contributor"})
        assert response.status_code == 404, response.text


# ===========================================================================
# 3. Last-owner protection
# ===========================================================================

class TestLastOwnerProtection:

    def test_an_owner_can_be_demoted_while_another_remains(self, managed):
        """Positive control for the protection tests below."""
        _app, client, state = managed
        _login(client, "owner")
        response = client.patch(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['second_owner']}",
            json={"role": "administrator"})
        assert response.status_code == 200, response.text
        assert response.json()["role"] == "administrator"

        # Restore, so ordering does not affect later tests.
        restored = client.patch(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['second_owner']}",
            json={"role": "owner"})
        assert restored.status_code == 200, restored.text

    def test_the_last_owner_cannot_be_demoted(self, managed):
        _app, client, state = managed
        _login(client, "owner")
        # Remove the spare owner first.
        assert client.patch(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['second_owner']}",
            json={"role": "administrator"}).status_code == 200

        _login(client, "second_owner")
        # 'owner' is now the only owner; an administrator tries to demote them.
        _login(client, "admin")
        response = client.patch(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['owner']}",
            json={"role": "researcher"})
        assert response.status_code == 409, response.text
        assert "only active owner" in response.json()["message"].lower()

        _login(client, "owner")
        client.patch(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['second_owner']}",
            json={"role": "owner"})

    def test_the_last_owner_cannot_be_revoked(self, managed):
        _app, client, state = managed
        _login(client, "owner")
        assert client.patch(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['second_owner']}",
            json={"role": "administrator"}).status_code == 200

        _login(client, "admin")
        response = client.delete(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['owner']}")
        assert response.status_code == 409, response.text
        assert "only active owner" in response.json()["message"].lower()

        _login(client, "owner")
        client.patch(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['second_owner']}",
            json={"role": "owner"})


# ===========================================================================
# 4. Membership changes take effect immediately
# ===========================================================================

class TestChangesTakeEffectImmediately:
    """Authorization is resolved per request, so there is no stale window."""

    def test_revocation_blocks_the_very_next_request(self, managed):
        _app, client, state = managed

        # Positive control: the CRO can read before revocation.
        _login(client, "cro_person")
        before = client.get("/api/v1/organizations")
        assert before.status_code == 200
        assert len(before.json()["organizations"]) == 1, before.text

        _login(client, "owner")
        revoked = client.request(
            "DELETE",
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['cro_person']}",
            json={"reason": "Contract ended"})
        assert revoked.status_code == 200, revoked.text

        _login(client, "cro_person")
        after = client.get("/api/v1/organizations")
        assert after.status_code == 200
        assert after.json()["organizations"] == [], (
            "revoked membership still granted access on the next request")
        assert client.get(
            f"/api/v1/organizations/{_acme(state)}/members"
        ).status_code == 404

    def test_suspension_blocks_and_reinstatement_restores(self, managed):
        _app, client, state = managed

        _login(client, "owner")
        suspended = client.post(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['auditor_person']}/status",
            json={"status": "suspended", "reason": "Under review"})
        assert suspended.status_code == 200, suspended.text
        assert suspended.json()["status"] == "suspended"

        _login(client, "auditor_person")
        assert client.get("/api/v1/organizations").json()[
            "organizations"] == []

        _login(client, "owner")
        restored = client.post(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['auditor_person']}/status",
            json={"status": "active"})
        assert restored.status_code == 200, restored.text

        _login(client, "auditor_person")
        assert len(client.get("/api/v1/organizations").json()[
            "organizations"]) == 1, "reinstatement did not restore access"

    def test_a_terminal_status_cannot_be_set_directly(self, managed):
        _app, client, state = managed
        _login(client, "owner")
        response = client.post(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['researcher']}/status",
            json={"status": "revoked"})
        assert response.status_code == 409, response.text


# ===========================================================================
# 5. Confirming a migrated organization
# ===========================================================================

class TestMigratedOrganizationConfirmation:

    def test_confirmation_lifts_the_hold_and_grants_no_science(self, managed):
        _app, client, state = managed
        migrated = state["migrated_organization_id"]

        _login(client, "owner")
        before = client.get(f"/api/v1/organizations/{migrated}")
        assert before.status_code == 200, before.text
        assert before.json()["awaiting_confirmation"] is True

        response = client.post(f"/api/v1/organizations/{migrated}/confirm")
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "active"
        assert response.json()["awaiting_confirmation"] is False
        assert "no reviewer or approver" in response.json()["notice"].lower()

        # Confirming created no assignment of any kind.
        team = client.get(
            f"/api/v1/organizations/{migrated}/members").json()["members"]
        assert all(m["role"] in ("owner",) for m in team), team

    def test_only_an_owner_can_confirm(self, managed):
        _app, client, state = managed
        _login(client, "admin")
        response = client.post(
            f"/api/v1/organizations/{_acme(state)}/confirm")
        assert response.status_code == 403, response.text
        assert "owner" in response.json()["message"].lower()


# ===========================================================================
# 6. External collaborators
# ===========================================================================

class TestExternalCollaborators:

    def test_a_time_limited_collaborator_expires_without_a_sweep(
            self, managed):
        _app, client, state = managed
        _login(client, "owner")

        # Positive control: an unexpired collaborator has access.
        live = client.post(
            f"/api/v1/organizations/{_acme(state)}/members",
            json={"user_id": state["users"]["unaffiliated"],
                  "role": "lab_contributor",
                  "external_organization": "Contract Labs Ltd",
                  "may_download_attachments": False,
                  "expires_at": (datetime.now(timezone.utc)
                                 + timedelta(days=30)).isoformat()})
        assert live.status_code == 201, live.text
        assert live.json()["is_external"] is True
        assert live.json()["may_download_attachments"] is False
        membership_id = live.json()["id"]

        _login(client, "unaffiliated")
        assert len(client.get("/api/v1/organizations").json()[
            "organizations"]) == 1, "positive control: collaborator has access"

        # Now move the expiry into the past and re-check without any sweep.
        _login(client, "owner")
        expired = client.post(
            f"/api/v1/organizations/{_acme(state)}/members",
            json={"user_id": state["users"]["unaffiliated"],
                  "role": "lab_contributor",
                  "external_organization": "Contract Labs Ltd",
                  "expires_at": (datetime.now(timezone.utc)
                                 - timedelta(days=1)).isoformat()})
        # Already an active member, so this is refused; revoke then re-add.
        assert expired.status_code == 409, expired.text
        client.delete(f"/api/v1/organizations/{_acme(state)}/members"
                      f"/{membership_id}")
        readded = client.post(
            f"/api/v1/organizations/{_acme(state)}/members",
            json={"user_id": state["users"]["unaffiliated"],
                  "role": "lab_contributor",
                  "external_organization": "Contract Labs Ltd",
                  "expires_at": (datetime.now(timezone.utc)
                                 - timedelta(days=1)).isoformat()})
        assert readded.status_code == 201, readded.text

        _login(client, "unaffiliated")
        assert client.get("/api/v1/organizations").json()[
            "organizations"] == [], (
            "an expired collaboration still granted access; expiry must be "
            "evaluated on read, not left to a sweep job")


# ===========================================================================
# 7. Audit completeness
# ===========================================================================

class TestAuditTrail:

    def test_every_membership_change_is_recorded(self, managed):
        _app, client, state = managed
        _login(client, "owner")

        before = len(client.get(
            f"/api/v1/organizations/{_acme(state)}/audit"
        ).json()["events"])

        client.patch(
            f"/api/v1/organizations/{_acme(state)}/members"
            f"/{state['memberships']['researcher']}",
            json={"scope": "organization"})

        events = client.get(
            f"/api/v1/organizations/{_acme(state)}/audit").json()["events"]
        assert len(events) > before, "a role change wrote no audit event"

        latest = events[0]
        assert latest["actor_username"] == "owner"
        assert latest["summary"]
        assert latest["created_at"]

    def test_audit_history_needs_administrative_authority(self, managed):
        _app, client, state = managed
        _login(client, "researcher")
        response = client.get(f"/api/v1/organizations/{_acme(state)}/audit")
        assert response.status_code == 403, response.text

    def test_the_audit_trail_never_contains_a_credential(self, managed):
        _app, client, state = managed
        _login(client, "owner")
        blob = client.get(
            f"/api/v1/organizations/{_acme(state)}/audit").text.lower()
        for forbidden in ("password", "password_hash", "token", "secret",
                          PASSWORD.lower()):
            assert forbidden not in blob, f"audit trail leaked {forbidden!r}"


# ===========================================================================
# 8. The switcher contract
# ===========================================================================

class TestOrganizationListingContract:

    def test_a_single_organization_member_needs_no_explicit_selection(
            self, managed):
        _app, client, _state = managed
        _login(client, "researcher")
        body = client.get("/api/v1/organizations").json()
        assert len(body["organizations"]) == 1
        assert body["requires_explicit_selection"] is False

    def test_a_multi_organization_member_must_choose(self, managed):
        _app, client, _state = managed
        _login(client, "owner")  # member of acme and the migrated org
        body = client.get("/api/v1/organizations").json()
        assert len(body["organizations"]) >= 2
        assert body["requires_explicit_selection"] is True, (
            "a multi-organization user must select explicitly; the backend "
            "must never guess")

    def test_a_user_with_no_membership_gets_an_empty_list_not_an_error(
            self, managed):
        _app, client, _state = managed
        _login(client, "unaffiliated")
        response = client.get("/api/v1/organizations")
        assert response.status_code == 200, response.text
        assert response.json()["organizations"] == []

    def test_the_switcher_listing_is_deliberately_not_narrowed(self, managed):
        """The one endpoint the header must not restrict.

        Everywhere else, selecting an organization narrows what the backend
        returns — that is the contract. This endpoint is the switcher's own
        source of truth: if it narrowed to the active organization, a user
        who selected one could never see the others and could never switch
        back. It reports the selection instead, in ``active_organization_id``.

        This is a genuine exception and worth stating, because "the header
        always narrows" is otherwise the rule the whole design rests on.
        """
        _app, client, state = managed
        _login(client, "owner")
        response = client.get("/api/v1/organizations", headers={
            ORGANIZATION_HEADER: str(_acme(state))})
        assert response.status_code == 200, response.text
        assert response.json()["active_organization_id"] == _acme(state)
        ids = [o["id"] for o in response.json()["organizations"]]
        assert _acme(state) in ids
        assert len(ids) >= 2, (
            "the switcher must keep listing every organization the user "
            "belongs to, or they could never switch away from the current one")

    def test_selection_still_narrows_every_other_endpoint(self, managed):
        """Positive control for the exception above: the rule still holds."""
        _app, client, state = managed
        _login(client, "owner")
        migrated = state["migrated_organization_id"]
        response = client.get(
            f"/api/v1/organizations/{migrated}/members",
            headers={ORGANIZATION_HEADER: str(_acme(state))})
        assert response.status_code == 404, (
            "selecting acme did not hide the other organization's members")
