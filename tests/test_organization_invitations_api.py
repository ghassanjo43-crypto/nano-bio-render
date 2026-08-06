"""Invitations, external collaborators and concurrent management, over HTTP.

What this suite is actually testing
----------------------------------
An invitation is a credential for an account that does not exist yet. Nobody is
watching it. If it can be replayed, guessed, redeemed by the wrong person,
recovered from a list endpoint or used to work out who has an account here, the
failure is silent — the legitimate recipient still gets in, and the illegitimate
one leaves no trace that anybody looks at.

So the centre of this file is what an invitation *cannot* do, and every negative
case is paired with a positive control proving the endpoint works at all. A test
that "an outsider cannot accept" passes trivially against an endpoint that is
broken for everyone.

Enumeration deserves its own note. Several tests assert that two responses are
*identical* — same status, same keys, same body. That is a stronger claim than
"both are refused", and it is the claim that matters: a difference of any kind
between "this address has an account" and "this address does not" turns an
administrative endpoint into a directory of the installation's users.
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
    AccessScope, InvitationStatus, MembershipStatus, OrganizationRole,
    OrganizationStatus, StudyRole,
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

PASSWORD = "Fixture-Only-Passphrase-9f3a2b"


@pytest.fixture(scope="module")
def invited(tmp_path_factory):
    """Two organizations, each with an owner, an administrator and a study.

    Acme also carries a researcher (who may not administer) and a laboratory
    contributor standing in for an external CRO.
    """
    from nanobio_studio.app.db.organization_models import (
        Organization, OrganizationMembership, StudyAssignment,
    )
    from nanobio_studio.app.db.workspace_models import (
        Project, RecordOrigin, RunStatus, StoredRun,
    )
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("org_invitations")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    CAST = {
        "inv_owner": (OrganizationRole.OWNER, "inv_owner@acme.test"),
        "inv_admin": (OrganizationRole.ADMINISTRATOR, "inv_admin@acme.test"),
        "inv_researcher": (OrganizationRole.RESEARCHER,
                           "inv_researcher@acme.test"),
        "inv_cro": (OrganizationRole.LAB_CONTRIBUTOR, "inv_cro@contract.test"),
    }

    async def seed():
        from sqlalchemy import select

        async with factory() as session:
            users = {}
            for name, (_role, email) in CAST.items():
                users[name] = await create_user(
                    session, username=name, password=PASSWORD,
                    role=UserRole.RESEARCHER, email=email)
            # Somebody with an account and no membership anywhere. Used as the
            # legitimate recipient of an invitation, and as the "existing
            # account" half of the enumeration comparison.
            users["inv_newcomer"] = await create_user(
                session, username="inv_newcomer", password=PASSWORD,
                role=UserRole.RESEARCHER, email="inv_newcomer@acme.test")
            users["inv_other_owner"] = await create_user(
                session, username="inv_other_owner", password=PASSWORD,
                role=UserRole.RESEARCHER, email="inv_other_owner@other.test")
            await session.flush()

            acme = Organization(slug="inv-acme", name="Invitation Acme",
                                status=OrganizationStatus.ACTIVE)
            other = Organization(slug="inv-other", name="Invitation Other",
                                 status=OrganizationStatus.ACTIVE)
            session.add_all([acme, other])
            await session.flush()

            for name, (role, _email) in CAST.items():
                session.add(OrganizationMembership(
                    organization_id=acme.id, user_id=users[name].id, role=role,
                    scope=(AccessScope.ORGANIZATION
                           if role in (OrganizationRole.OWNER,
                                       OrganizationRole.ADMINISTRATOR)
                           else AccessScope.ASSIGNED_STUDIES),
                    status=MembershipStatus.ACTIVE,
                    external_organization=("Contract Labs Ltd"
                                           if name == "inv_cro" else None)))
            session.add(OrganizationMembership(
                organization_id=other.id, user_id=users["inv_other_owner"].id,
                role=OrganizationRole.OWNER, scope=AccessScope.ORGANIZATION,
                status=MembershipStatus.ACTIVE))
            await session.flush()

            for label, organization, who in (
                    ("acme", acme, "inv_researcher"),
                    ("other", other, "inv_other_owner")):
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


def _acme(state) -> int:
    return state["acme_organization_id"]


def _invite(client, organization_id: int, **overrides):
    body = {"email": "someone@example.test", "role": "researcher"}
    body.update(overrides)
    return client.post(f"/api/v1/organizations/{organization_id}/invitations",
                       json=body)


def _tidy(client, state, email: str) -> None:
    """Withdraw any outstanding invitation to ``email``.

    The module-scoped fixture means one test's outstanding invitation would
    otherwise make the next test's identical invitation a duplicate — a failure
    caused by ordering rather than by the behaviour under test.
    """
    listing = client.get(
        f"/api/v1/organizations/{_acme(state)}/invitations")
    if listing.status_code != 200:
        return
    for invitation in listing.json()["invitations"]:
        if invitation["email"] == email.lower():
            client.delete(
                f"/api/v1/organizations/{_acme(state)}/invitations/"
                f"{invitation['id']}")


# ===========================================================================
# 1. Who may invite
# ===========================================================================

class TestInvitationAuthority:

    def test_an_owner_can_invite(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        response = _invite(client, _acme(state), email="owner-invite@a.test")
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "pending", "positive control"
        _tidy(client, state, "owner-invite@a.test")

    def test_an_administrator_can_invite(self, invited):
        _app, client, state = invited
        _login(client, "inv_admin")
        response = _invite(client, _acme(state), email="admin-invite@a.test")
        assert response.status_code == 201, response.text
        _tidy(client, state, "admin-invite@a.test")

    def test_a_researcher_cannot_invite(self, invited):
        _app, client, state = invited
        _login(client, "inv_researcher")
        response = _invite(client, _acme(state), email="nope@a.test")
        assert response.status_code == 403, response.text

    def test_an_outsider_cannot_invite_and_gets_404_not_403(self, invited):
        """404, because 403 would confirm the organization exists."""
        _app, client, state = invited
        _login(client, "inv_other_owner")
        response = _invite(client, _acme(state), email="nope@a.test")
        assert response.status_code == 404, response.text
        assert "organization" not in response.text.lower() or \
            response.json()["message"] == "No such record."

    def test_a_researcher_cannot_list_invitations(self, invited):
        _app, client, state = invited
        _login(client, "inv_researcher")
        response = client.get(
            f"/api/v1/organizations/{_acme(state)}/invitations")
        assert response.status_code == 403, response.text

    def test_an_owner_can_list_invitations(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        response = client.get(
            f"/api/v1/organizations/{_acme(state)}/invitations")
        assert response.status_code == 200, "positive control"
        assert "invitations" in response.json()


# ===========================================================================
# 2. The token is a credential and is treated as one
# ===========================================================================

class TestTokenHandling:

    def test_the_link_is_returned_once_and_never_again(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        created = _invite(client, _acme(state), email="once@a.test")
        assert created.status_code == 201, created.text
        body = created.json()
        assert "invitation_link" in body, "positive control"
        assert body["link_shown_once"] is True

        listing = client.get(
            f"/api/v1/organizations/{_acme(state)}/invitations")
        for invitation in listing.json()["invitations"]:
            assert "invitation_link" not in invitation
            assert "token" not in invitation

        _tidy(client, state, "once@a.test")

    def test_the_raw_token_is_not_stored(self, invited):
        """The row holds a hash. A database dump is not a set of live links."""
        from sqlalchemy import select

        from nanobio_studio.app.db.organization_models import (
            OrganizationInvitation,
        )

        _app, client, state = invited
        _login(client, "inv_owner")
        created = _invite(client, _acme(state), email="hashed@a.test")
        token = created.json()["invitation_link"].split("token=")[1]

        app = _app
        override = app.dependency_overrides
        assert override, "fixture wiring"

        async def read():
            from nanobio_studio.app.db.auth_session import get_auth_session
            generator = override[get_auth_session]()
            session = await generator.__anext__()
            try:
                return (await session.execute(
                    select(OrganizationInvitation).where(
                        OrganizationInvitation.email == "hashed@a.test")
                )).scalars().all()
            finally:
                await generator.aclose()

        rows = run_async(read())
        assert rows, "positive control: the invitation exists"
        for row in rows:
            assert row.token_hash != token
            assert len(row.token_hash) == 64
            assert token not in (row.token_hash, row.token_prefix)
            assert row.token_prefix and len(row.token_prefix) <= 12

        _tidy(client, state, "hashed@a.test")

    def test_the_audit_trail_does_not_carry_the_token(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        created = _invite(client, _acme(state), email="audited@a.test")
        token = created.json()["invitation_link"].split("token=")[1]

        audit = client.get(
            f"/api/v1/organizations/{_acme(state)}/audit?subject_type=invitation")
        assert audit.status_code == 200, audit.text
        assert any(e["event"] == "member_invited"
                   for e in audit.json()["events"]), "positive control"
        assert token not in audit.text

        _tidy(client, state, "audited@a.test")

    def test_the_link_takes_no_destination_from_the_caller(self, invited):
        """There is no field through which a link can be aimed elsewhere."""
        _app, client, state = invited
        _login(client, "inv_owner")
        response = _invite(
            client, _acme(state), email="redirect@a.test",
            next="https://evil.example/steal",
            redirect_uri="https://evil.example/steal",
            invitation_link="https://evil.example/steal")
        assert response.status_code == 201, response.text
        link = response.json()["invitation_link"]
        assert "evil.example" not in link
        assert link.startswith("/invitations/accept?token=")
        _tidy(client, state, "redirect@a.test")

    @pytest.mark.parametrize("base", [
        "//evil.example/accept",
        "javascript:alert(1)",
        "https://",
        "/accept/../../evil",
    ])
    def test_an_unsafe_configured_base_falls_back_to_the_relative_default(
            self, base):
        """Configuration is not user input, but it is edited under pressure."""
        from nanobio_studio.app.core.config import settings
        from nanobio_studio.app.services.invitation_delivery import (
            build_invitation_link,
        )

        original = settings.invitation_link_base
        try:
            settings.invitation_link_base = base
            link = build_invitation_link("placeholder-token")
        finally:
            settings.invitation_link_base = original
        assert link == "/invitations/accept?token=placeholder-token"

    def test_a_safe_absolute_base_is_kept(self):
        """Positive control: the guard refuses the unsafe, not the unusual."""
        from nanobio_studio.app.core.config import settings
        from nanobio_studio.app.services.invitation_delivery import (
            build_invitation_link,
        )

        original = settings.invitation_link_base
        try:
            settings.invitation_link_base = "https://studio.example/join"
            link = build_invitation_link("placeholder-token")
        finally:
            settings.invitation_link_base = original
        assert link == "https://studio.example/join?token=placeholder-token"


# ===========================================================================
# 3. Redemption
# ===========================================================================

class TestRedemption:

    def _issue(self, client, state, email: str, **overrides) -> str:
        _login(client, "inv_owner")
        response = _invite(client, _acme(state), email=email, **overrides)
        assert response.status_code == 201, response.text
        return response.json()["invitation_link"].split("token=")[1]

    def test_the_invited_account_can_accept(self, invited):
        _app, client, state = invited
        token = self._issue(client, state, "inv_newcomer@acme.test")

        _login(client, "inv_newcomer")
        response = client.post("/api/v1/organizations/invitations/accept",
                               json={"token": token})
        assert response.status_code == 200, response.text
        assert response.json()["role"] == "researcher", "positive control"

        listing = client.get("/api/v1/organizations")
        assert any(o["id"] == _acme(state)
                   for o in listing.json()["organizations"])

    def test_a_token_cannot_be_used_twice(self, invited):
        _app, client, state = invited
        token = self._issue(client, state, "twice@a.test")

        _login(client, "inv_newcomer")
        first = client.post("/api/v1/organizations/invitations/accept",
                            json={"token": token})
        # The newcomer's address does not match, so this is refused — which is
        # itself the point of the next test. Use the matching account instead.
        assert first.status_code == 404

        _login(client, "inv_owner")
        second = _invite(client, _acme(state), email="inv_newcomer@acme.test")
        assert second.status_code == 201, second.text
        fresh = second.json()["invitation_link"].split("token=")[1]

        _login(client, "inv_newcomer")
        used = client.post("/api/v1/organizations/invitations/accept",
                           json={"token": fresh})
        assert used.status_code == 200, "positive control"
        replayed = client.post("/api/v1/organizations/invitations/accept",
                               json={"token": fresh})
        assert replayed.status_code == 404, replayed.text

        _login(client, "inv_owner")
        _tidy(client, state, "twice@a.test")

    def test_a_different_account_cannot_redeem_a_forwarded_link(self, invited):
        _app, client, state = invited
        token = self._issue(client, state, "stranger@nowhere.test")

        _login(client, "inv_researcher")
        response = client.post("/api/v1/organizations/invitations/accept",
                               json={"token": token})
        assert response.status_code == 404, response.text

        _login(client, "inv_owner")
        _tidy(client, state, "stranger@nowhere.test")

    def test_a_revoked_invitation_cannot_be_redeemed(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        created = _invite(client, _acme(state), email="inv_cro@contract.test")
        assert created.status_code == 201, created.text
        token = created.json()["invitation_link"].split("token=")[1]

        withdrawn = client.request(
            "DELETE",
            f"/api/v1/organizations/{_acme(state)}/invitations/"
            f"{created.json()['id']}", json={"reason": "Changed our minds."})
        assert withdrawn.status_code == 200, withdrawn.text
        assert withdrawn.json()["status"] == "revoked"

        _login(client, "inv_cro")
        response = client.post("/api/v1/organizations/invitations/accept",
                               json={"token": token})
        assert response.status_code == 404, response.text

    def test_re_issuing_stops_the_previous_link_working(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        created = _invite(client, _acme(state), email="inv_cro@contract.test")
        first_token = created.json()["invitation_link"].split("token=")[1]

        resent = client.post(
            f"/api/v1/organizations/{_acme(state)}/invitations/"
            f"{created.json()['id']}/resend")
        assert resent.status_code == 200, resent.text
        second_token = resent.json()["invitation_link"].split("token=")[1]
        assert second_token != first_token

        _login(client, "inv_cro")
        stale = client.post("/api/v1/organizations/invitations/accept",
                            json={"token": first_token})
        assert stale.status_code == 404, stale.text
        fresh = client.post("/api/v1/organizations/invitations/accept",
                            json={"token": second_token})
        assert fresh.status_code == 200, "positive control"

    def test_an_expired_invitation_cannot_be_redeemed(self, invited):
        """Expiry is evaluated on redemption, not by a sweep having run."""
        from sqlalchemy import update

        from nanobio_studio.app.db.organization_models import (
            OrganizationInvitation,
        )

        _app, client, state = invited
        _login(client, "inv_owner")
        created = _invite(client, _acme(state), email="expiring@a.test")
        token = created.json()["invitation_link"].split("token=")[1]
        invitation_id = created.json()["id"]

        async def age():
            from nanobio_studio.app.db.auth_session import get_auth_session
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                await session.execute(
                    update(OrganizationInvitation)
                    .where(OrganizationInvitation.id == invitation_id)
                    .values(expires_at=datetime.now(timezone.utc)
                            - timedelta(hours=1)))
                await session.commit()
            finally:
                await generator.aclose()

        run_async(age())

        _login(client, "inv_researcher")
        response = client.post("/api/v1/organizations/invitations/accept",
                               json={"token": token})
        assert response.status_code == 404, response.text

        # The stored status still says PENDING — that is exactly the point.
        _login(client, "inv_owner")
        listing = client.get(
            f"/api/v1/organizations/{_acme(state)}/invitations")
        outstanding = [i for i in listing.json()["invitations"]
                       if i["id"] == invitation_id]
        assert outstanding and outstanding[0]["status"] == "pending"
        _tidy(client, state, "expiring@a.test")

    def test_every_bad_token_returns_the_same_body(self, invited):
        """Unknown, malformed and revoked must be indistinguishable."""
        _app, client, state = invited
        _login(client, "inv_owner")
        created = _invite(client, _acme(state), email="oracle@a.test")
        real = created.json()["invitation_link"].split("token=")[1]
        client.delete(f"/api/v1/organizations/{_acme(state)}/invitations/"
                      f"{created.json()['id']}")

        _login(client, "inv_researcher")
        revoked = client.post("/api/v1/organizations/invitations/accept",
                              json={"token": real})
        unknown = client.post("/api/v1/organizations/invitations/accept",
                              json={"token": "x" * 43})

        assert revoked.status_code == unknown.status_code == 404
        assert revoked.json() == unknown.json()

    def test_accepting_grants_no_scientific_authority(self, invited):
        """Membership is not assignment. Joining approves nothing."""
        _app, client, state = invited
        _login(client, "inv_owner")
        created = _invite(client, _acme(state), email="inv_cro@contract.test",
                          role="approver")
        token = created.json()["invitation_link"].split("token=")[1]

        _login(client, "inv_cro")
        accepted = client.post("/api/v1/organizations/invitations/accept",
                               json={"token": token})
        assert accepted.status_code == 200, "positive control"
        assert accepted.json()["is_administrative"] is False
        assert "no scientific authority" in accepted.json()["notice"].lower()

        # Joining as an organization APPROVER does not even make the study
        # visible, let alone approvable: the membership carries
        # assigned-studies scope and there is no assignment.
        team = client.get(
            f"/api/v1/organizations/{_acme(state)}/studies/"
            f"{state['acme_study_id']}/team")
        assert team.status_code == 404, team.text

        # And from a vantage point that *can* see the study, no assignment
        # was created for them. The positive control for the 404 above: the
        # study and its team genuinely exist.
        _login(client, "inv_owner")
        visible = client.get(
            f"/api/v1/organizations/{_acme(state)}/studies/"
            f"{state['acme_study_id']}/team")
        assert visible.status_code == 200, visible.text
        assert not [a for a in visible.json()["assignments"]
                    if a["user_id"] == state["users"]["inv_cro"]
                    and a["is_active"]]

        # Restore the fixture's laboratory-contributor role for later tests.
        _login(client, "inv_owner")
        client.patch(
            f"/api/v1/organizations/{_acme(state)}/members/"
            f"{state['memberships']['inv_cro']}",
            json={"role": "lab_contributor"})


# ===========================================================================
# 4. Enumeration
# ===========================================================================

class TestEnumeration:

    def test_inviting_a_known_and_an_unknown_address_are_indistinguishable(
            self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")

        known = _invite(client, _acme(state), email="inv_newcomer@acme.test")
        unknown = _invite(client, _acme(state), email="nobody-here@a.test")

        assert known.status_code == unknown.status_code == 201
        assert set(known.json()) == set(unknown.json())
        # Only the identifiers and the address itself may differ.
        volatile = {"id", "email", "token_prefix", "invitation_link",
                    "created_at", "expires_at"}
        for key in set(known.json()) - volatile:
            assert known.json()[key] == unknown.json()[key], key

        _tidy(client, state, "inv_newcomer@acme.test")
        _tidy(client, state, "nobody-here@a.test")

    def test_a_foreign_invitation_id_and_an_absent_one_are_indistinguishable(
            self, invited):
        """Cross-organization parent injection returns nothing useful."""
        _app, client, state = invited
        _login(client, "inv_other_owner")
        theirs = _invite(client, state["other_organization_id"],
                         email="theirs@other.test")
        assert theirs.status_code == 201, "positive control"
        foreign_id = theirs.json()["id"]

        _login(client, "inv_owner")
        real = client.delete(
            f"/api/v1/organizations/{_acme(state)}/invitations/{foreign_id}")
        absent = client.delete(
            f"/api/v1/organizations/{_acme(state)}/invitations/99999999")

        assert real.status_code == absent.status_code == 404
        assert real.json() == absent.json()

    def test_a_malformed_address_is_refused_without_confirming_anything(
            self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        response = _invite(client, _acme(state), email="not-an-address")
        assert response.status_code == 409, response.text
        assert "@" not in response.json()["message"] or \
            "email address" in response.json()["message"]


# ===========================================================================
# 5. One live invitation per address
# ===========================================================================

class TestNoDuplicateInvitations:

    def test_a_second_outstanding_invitation_is_refused(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        first = _invite(client, _acme(state), email="dup@a.test")
        assert first.status_code == 201, "positive control"
        second = _invite(client, _acme(state), email="dup@a.test")
        assert second.status_code == 409, second.text
        assert "outstanding" in second.json()["message"].lower()
        _tidy(client, state, "dup@a.test")

    def test_the_address_is_compared_case_insensitively(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        first = _invite(client, _acme(state), email="Case@a.test")
        assert first.status_code == 201, "positive control"
        assert first.json()["email"] == "case@a.test"
        second = _invite(client, _acme(state), email="CASE@A.TEST")
        assert second.status_code == 409, second.text
        _tidy(client, state, "case@a.test")

    def test_re_inviting_after_withdrawal_is_permitted(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        first = _invite(client, _acme(state), email="again@a.test")
        client.delete(f"/api/v1/organizations/{_acme(state)}/invitations/"
                      f"{first.json()['id']}")
        second = _invite(client, _acme(state), email="again@a.test")
        assert second.status_code == 201, second.text
        _tidy(client, state, "again@a.test")


# ===========================================================================
# 6. Concurrency
# ===========================================================================

class TestConcurrentModification:

    def test_a_stale_revision_is_refused_rather_than_applied(self, invited):
        """Two administrators, one members screen each. Nobody loses a change."""
        _app, client, state = invited
        _login(client, "inv_owner")
        membership_id = state["memberships"]["inv_researcher"]

        before = client.get(
            f"/api/v1/organizations/{_acme(state)}/members/{membership_id}")
        assert before.status_code == 200, before.text
        stale_revision = before.json()["revision"]

        first = client.post(
            f"/api/v1/organizations/{_acme(state)}/members/{membership_id}"
            f"/status",
            json={"status": "suspended", "reason": "First administrator.",
                  "expected_revision": stale_revision})
        assert first.status_code == 200, "positive control"

        second = client.patch(
            f"/api/v1/organizations/{_acme(state)}/members/{membership_id}",
            json={"role": "reviewer", "expected_revision": stale_revision})
        assert second.status_code == 409, second.text
        assert second.json()["error"] == "concurrent_modification"

        # And the first administrator's change survived intact.
        after = client.get(
            f"/api/v1/organizations/{_acme(state)}/members/{membership_id}")
        assert after.json()["status"] == "suspended"
        assert after.json()["role"] == "researcher"

        client.post(
            f"/api/v1/organizations/{_acme(state)}/members/{membership_id}"
            f"/status", json={"status": "active"})

    def test_a_current_revision_is_accepted(self, invited):
        """Positive control: the check refuses the stale, not the ordinary."""
        _app, client, state = invited
        _login(client, "inv_owner")
        membership_id = state["memberships"]["inv_researcher"]
        current = client.get(
            f"/api/v1/organizations/{_acme(state)}/members/{membership_id}"
        ).json()["revision"]

        response = client.post(
            f"/api/v1/organizations/{_acme(state)}/members/{membership_id}"
            f"/status",
            json={"status": "suspended", "expected_revision": current})
        assert response.status_code == 200, response.text
        assert response.json()["revision"] == current + 1

        client.post(
            f"/api/v1/organizations/{_acme(state)}/members/{membership_id}"
            f"/status", json={"status": "active"})


# ===========================================================================
# 7. Membership detail and collaborators
# ===========================================================================

class TestMembershipDetailScoping:

    def test_a_membership_from_another_organization_is_not_reachable(
            self, invited):
        """The organization in the path is checked, not decorative."""
        from sqlalchemy import select

        from nanobio_studio.app.db.organization_models import (
            OrganizationMembership,
        )

        _app, client, state = invited

        async def foreign_membership_id():
            from nanobio_studio.app.db.auth_session import get_auth_session
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                return (await session.execute(
                    select(OrganizationMembership.id).where(
                        OrganizationMembership.organization_id
                        == state["other_organization_id"])
                )).scalars().first()
            finally:
                await generator.aclose()

        foreign = run_async(foreign_membership_id())
        assert foreign is not None, "fixture"

        _login(client, "inv_owner")
        mine = client.get(
            f"/api/v1/organizations/{_acme(state)}/members/"
            f"{state['memberships']['inv_admin']}")
        assert mine.status_code == 200, "positive control"

        theirs = client.get(
            f"/api/v1/organizations/{_acme(state)}/members/{foreign}")
        assert theirs.status_code == 404, theirs.text

    def test_the_collaborator_list_holds_only_external_memberships(
            self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        response = client.get(
            f"/api/v1/organizations/{_acme(state)}/collaborators")
        assert response.status_code == 200, response.text
        names = {c["username"] for c in response.json()["collaborators"]}
        assert "inv_cro" in names, "positive control"
        assert "inv_owner" not in names
        assert all(c["is_external"] for c in response.json()["collaborators"])

    def test_a_researcher_cannot_read_the_audit_trail(self, invited):
        _app, client, state = invited
        _login(client, "inv_researcher")
        response = client.get(f"/api/v1/organizations/{_acme(state)}/audit")
        assert response.status_code == 403, response.text

    def test_an_owner_can_read_the_audit_trail(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        response = client.get(f"/api/v1/organizations/{_acme(state)}/audit")
        assert response.status_code == 200, "positive control"
        assert response.json()["append_only"] is True


# ===========================================================================
# 8. Delivery is provider-neutral and carries no credential
# ===========================================================================

class TestDelivery:

    def test_the_default_provider_sends_nothing_and_says_so(self, invited):
        _app, client, state = invited
        _login(client, "inv_owner")
        response = _invite(client, _acme(state), email="delivery@a.test")
        body = response.json()
        assert body["delivery_provider"] == "recorded"
        assert body["delivery_status"] == "recorded"
        assert "administrator" in body["delivery_detail"].lower()
        _tidy(client, state, "delivery@a.test")

    def test_a_provider_receives_no_password_and_no_scientific_content(
            self, invited):
        from nanobio_studio.app.services import invitation_delivery

        captured: list = []

        class Capturing:
            name = "capturing"

            def send(self, message):
                captured.append(message)
                return invitation_delivery.DeliveryResult(
                    provider=self.name, status="sent", delivered=True,
                    detail="Captured by a test double.")

        _app, client, state = invited
        _login(client, "inv_owner")
        invitation_delivery.set_provider_for_tests(Capturing())
        try:
            response = _invite(client, _acme(state), email="probe@a.test")
            assert response.status_code == 201, response.text
        finally:
            invitation_delivery.set_provider_for_tests(None)

        assert captured, "positive control: the provider was called"
        message = captured[0]
        assert message.recipient_email == "probe@a.test"
        assert PASSWORD not in repr(message)
        assert "study" not in message.organization_name.lower()
        assert set(vars(message)) == {
            "recipient_email", "organization_name", "role", "invited_by",
            "expires_at", "link"}

        _tidy(client, state, "probe@a.test")

    def test_smtp_refuses_to_construct_without_configuration(self):
        """No embedded host, sender or credential to fall back on."""
        from nanobio_studio.app.core.config import settings
        from nanobio_studio.app.services.invitation_delivery import (
            DeliveryNotConfigured, SmtpDelivery,
        )

        original = (settings.smtp_host, settings.smtp_from_address)
        try:
            settings.smtp_host = ""
            settings.smtp_from_address = ""
            with pytest.raises(DeliveryNotConfigured) as excinfo:
                SmtpDelivery()
        finally:
            settings.smtp_host, settings.smtp_from_address = original
        assert "SMTP_HOST" in str(excinfo.value)

    def test_an_unknown_provider_falls_back_rather_than_failing(self):
        from nanobio_studio.app.core.config import settings
        from nanobio_studio.app.services.invitation_delivery import (
            get_provider,
        )

        original = settings.invitation_delivery
        try:
            settings.invitation_delivery = "carrier-pigeon"
            assert get_provider().name == "recorded"
            settings.invitation_delivery = "console"
            assert get_provider().name == "console", "positive control"
        finally:
            settings.invitation_delivery = original


# ===========================================================================
# 9. Expiry housekeeping
# ===========================================================================

class TestExpirySweep:

    def test_the_sweep_marks_a_lapsed_invitation_expired(self, invited):
        from sqlalchemy import update

        from nanobio_studio.app.db.organization_models import (
            OrganizationInvitation,
        )

        _app, client, state = invited
        _login(client, "inv_owner")
        created = _invite(client, _acme(state), email="sweep@a.test")
        invitation_id = created.json()["id"]

        async def age():
            from nanobio_studio.app.db.auth_session import get_auth_session
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                await session.execute(
                    update(OrganizationInvitation)
                    .where(OrganizationInvitation.id == invitation_id)
                    .values(expires_at=datetime.now(timezone.utc)
                            - timedelta(hours=1)))
                await session.commit()
            finally:
                await generator.aclose()

        run_async(age())

        response = client.post(
            f"/api/v1/organizations/{_acme(state)}/maintenance/expire")
        assert response.status_code == 200, response.text
        assert response.json()["expired"]["invitations"] >= 1

        listing = client.get(
            f"/api/v1/organizations/{_acme(state)}/invitations"
            f"?include_closed=true")
        row = [i for i in listing.json()["invitations"]
               if i["id"] == invitation_id]
        assert row and row[0]["status"] == InvitationStatus.EXPIRED.value

    def test_a_researcher_cannot_run_the_sweep(self, invited):
        _app, client, state = invited
        _login(client, "inv_researcher")
        response = client.post(
            f"/api/v1/organizations/{_acme(state)}/maintenance/expire")
        assert response.status_code == 403, response.text
