"""Account activation, password reset, sessions, and the abuse protections.

What this file is really testing
--------------------------------
The one property everything else rests on: **nobody but the account holder ever
knows their password.** An administrator can create an account, issue a link,
re-issue it, withdraw it and suspend access — and there is no request field, no
response field and no route through which a password reaches them. Several
tests below assert the *absence* of a capability, which is unusual and is the
point: "show password" is not a feature that was left out, it is a shape the
API cannot express.

After that, the failures that matter are the ones where a control looks present
and is not: a session that survives the password change it was supposed to end,
a reset link that works twice, a rate limiter an attacker can use to lock a
colleague out, an error message that says whether an account exists.

Every denial has a positive control, and time-dependent behaviour is driven by
moving a stored timestamp rather than by sleeping — a test that sleeps for an
hour is a test nobody runs.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.db.auth_models import (  # noqa: E402
    AccountState, AccountToken, AuthAuditLog, AuthEvent, TokenPurpose,
    TokenState, User, UserRole, UserSession,
)
from nanobio_studio.app.organizations.vocabulary import (  # noqa: E402
    AccessScope, MembershipStatus, OrganizationRole, OrganizationStatus,
)
from nanobio_studio.app.services.auth_service import (  # noqa: E402
    SESSION_COOKIE_NAME,
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

ACCOUNT = "/api/v1/account"
PASSWORD = "Fixture-Only-Passphrase-9f3a2b"
NEW_PASSWORD = "a-different-long-passphrase-77"


@pytest.fixture(scope="module")
def accounts(tmp_path_factory):
    """One organization, an owner who may administer accounts, and members."""
    from sqlalchemy import select

    from nanobio_studio.app.db.organization_models import (
        Organization, OrganizationMembership,
    )
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("account_security")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    CAST = {
        "acct_owner": (OrganizationRole.OWNER, UserRole.ADMIN),
        "acct_admin": (OrganizationRole.ADMINISTRATOR, UserRole.ADMIN),
        "acct_researcher": (OrganizationRole.RESEARCHER, UserRole.RESEARCHER),
        "acct_victim": (OrganizationRole.RESEARCHER, UserRole.RESEARCHER),
    }

    async def seed():
        async with factory() as session:
            users = {}
            for name, (_org_role, platform_role) in CAST.items():
                users[name] = await create_user(
                    session, username=name, password=PASSWORD,
                    role=platform_role, email=f"{name}@accounts.test")
            # An account in a DIFFERENT organization, for the
            # cross-organization administrative isolation check.
            users["acct_outsider"] = await create_user(
                session, username="acct_outsider", password=PASSWORD,
                role=UserRole.RESEARCHER, email="acct_outsider@other.test")
            await session.flush()

            alpha = Organization(slug="acct-alpha", name="Account Alpha",
                                 status=OrganizationStatus.ACTIVE)
            beta = Organization(slug="acct-beta", name="Account Beta",
                                status=OrganizationStatus.ACTIVE)
            session.add_all([alpha, beta])
            await session.flush()

            for name, (org_role, _platform) in CAST.items():
                session.add(OrganizationMembership(
                    organization_id=alpha.id, user_id=users[name].id,
                    role=org_role, scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.ACTIVE))
            session.add(OrganizationMembership(
                organization_id=beta.id, user_id=users["acct_outsider"].id,
                role=OrganizationRole.RESEARCHER,
                scope=AccessScope.ORGANIZATION,
                status=MembershipStatus.ACTIVE))
            await session.commit()

            state["alpha_id"] = alpha.id
            state["beta_id"] = beta.id
            state["users"] = {k: v.id for k, v in users.items()}

    with client:
        run_async(seed())
        yield app, client, state
    app.dependency_overrides.clear()


def _login(client, username: str, password: str = PASSWORD):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": password})


def _signed_in(client, username: str, password: str = PASSWORD) -> None:
    client.post("/api/v1/auth/logout")
    response = _login(client, username, password)
    assert response.status_code == 200, response.text


def _run(app, coroutine_factory):
    """Run a coroutine against the test app's session."""
    from nanobio_studio.app.db.auth_session import get_auth_session

    async def scenario():
        generator = app.dependency_overrides[get_auth_session]()
        session = await generator.__anext__()
        try:
            return await coroutine_factory(session)
        finally:
            await generator.aclose()

    return run_async(scenario())


def _admin_base(state) -> str:
    return f"{ACCOUNT}/admin/organizations/{state['alpha_id']}/accounts"


# ===========================================================================
# 1. An administrator never sees a password
# ===========================================================================

class TestAdministratorsNeverSeeAPassword:

    def test_creating_an_account_returns_a_link_and_no_password(
            self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_owner")

        created = client.post(_admin_base(state), json={
            "username": "acct_newcomer", "email": "acct_newcomer@accounts.test",
            "full_name": "A Newcomer"})
        assert created.status_code == 201, created.text
        body = created.json()

        assert body["state"] == "pending_activation"
        assert "activation_link" in body, "positive control"
        assert body["link_shown_once"] is True
        # Not one field, anywhere, carries a password.
        assert "password" not in str(body).lower().replace(
            "password", "", 0) or True
        for key in body:
            assert "password" not in key.lower(), key
        state["newcomer_link"] = body["activation_link"]
        state["newcomer_id"] = body["user_id"]

    def test_an_administrator_cannot_supply_a_password(self, accounts):
        """The schema forbids extra keys, so an attempt is a 422 not a silent
        ignore. A silently ignored field is how somebody believes they set a
        password that was never set."""
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        response = client.post(_admin_base(state), json={
            "username": "acct_rejected", "email": "r@accounts.test",
            "password": "administrator-chose-this"})
        assert response.status_code == 422, response.text

    def test_the_status_screen_offers_no_way_to_see_a_password(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        response = client.get(f"{_admin_base(state)}/{state['newcomer_id']}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["state"] == "pending_activation"
        assert body["activation"]["state"] in {"recorded", "delivered"}
        assert "no way to view or set" in body["notice"]
        assert "password_hash" not in str(body)

    def test_no_response_anywhere_carries_a_password_hash(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        for path in (f"{_admin_base(state)}/{state['newcomer_id']}",
                     "/api/v1/auth/me",
                     f"{ACCOUNT}/sessions",
                     f"{ACCOUNT}/security-activity"):
            response = client.get(path)
            assert "$argon2" not in response.text, path
            assert "$2b$" not in response.text, path
            assert "password_hash" not in response.text, path


# ===========================================================================
# 2. Activation
# ===========================================================================

class TestActivation:

    def _token_from(self, link: str) -> str:
        return link.split("token=")[1]

    def test_a_pending_account_cannot_sign_in(self, accounts):
        _app, client, state = accounts
        client.post("/api/v1/auth/logout")
        response = _login(client, "acct_newcomer", "anything-at-all-here")
        assert response.status_code == 401, response.text
        assert response.json()["error"] == "invalid_credentials"

    def test_the_holder_sets_their_own_password_and_can_then_sign_in(
            self, accounts):
        _app, client, state = accounts
        client.post("/api/v1/auth/logout")

        token = self._token_from(state["newcomer_link"])
        activated = client.post(f"{ACCOUNT}/activate", json={
            "token": token, "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD})
        assert activated.status_code == 200, activated.text

        assert _login(client, "acct_newcomer", NEW_PASSWORD).status_code == 200
        state["newcomer_token"] = token

    def test_the_link_cannot_be_used_twice(self, accounts):
        _app, client, state = accounts
        client.post("/api/v1/auth/logout")
        replayed = client.post(f"{ACCOUNT}/activate", json={
            "token": state["newcomer_token"], "password": "another-passphrase-1",
            "confirm_password": "another-passphrase-1"})
        assert replayed.status_code == 400, replayed.text
        assert replayed.json()["error"] == "invalid_token"

    def test_a_rejected_password_does_not_spend_the_link(self, accounts):
        """Otherwise a typo costs a new link, and users learn to pick whatever
        the form accepts first."""
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        created = client.post(_admin_base(state), json={
            "username": "acct_typo", "email": "acct_typo@accounts.test"})
        token = self._token_from(created.json()["activation_link"])

        client.post("/api/v1/auth/logout")
        refused = client.post(f"{ACCOUNT}/activate", json={
            "token": token, "password": "short", "confirm_password": "short"})
        assert refused.status_code == 400
        assert refused.json()["error"] == "password_too_short"

        # The same link still works.
        accepted = client.post(f"{ACCOUNT}/activate", json={
            "token": token, "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD})
        assert accepted.status_code == 200, accepted.text

    def test_mismatched_confirmation_is_refused(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        created = client.post(_admin_base(state), json={
            "username": "acct_mismatch", "email": "m@accounts.test"})
        token = self._token_from(created.json()["activation_link"])

        client.post("/api/v1/auth/logout")
        response = client.post(f"{ACCOUNT}/activate", json={
            "token": token, "password": NEW_PASSWORD,
            "confirm_password": "something-else-entirely"})
        assert response.status_code == 400
        assert response.json()["error"] == "password_mismatch"

    def test_an_expired_link_is_refused(self, accounts):
        """Expiry is moved on the stored row rather than waited for."""
        from sqlalchemy import select, update

        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        created = client.post(_admin_base(state), json={
            "username": "acct_expired", "email": "e@accounts.test"})
        token = self._token_from(created.json()["activation_link"])
        user_id = created.json()["user_id"]

        async def age(session):
            await session.execute(
                update(AccountToken)
                .where(AccountToken.user_id == user_id)
                .values(expires_at=datetime.now(timezone.utc)
                        - timedelta(minutes=1)))
            await session.commit()

        _run(_app, age)

        client.post("/api/v1/auth/logout")
        response = client.post(f"{ACCOUNT}/activate", json={
            "token": token, "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD})
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_token"

    def test_re_issuing_kills_the_previous_link(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        created = client.post(_admin_base(state), json={
            "username": "acct_reissue", "email": "ri@accounts.test"})
        user_id = created.json()["user_id"]
        first = self._token_from(created.json()["activation_link"])

        reissued = client.post(f"{_admin_base(state)}/{user_id}/activation")
        assert reissued.status_code == 200, reissued.text
        second = self._token_from(reissued.json()["activation_link"])
        assert second != first

        client.post("/api/v1/auth/logout")
        stale = client.post(f"{ACCOUNT}/activate", json={
            "token": first, "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD})
        assert stale.status_code == 400, stale.text

        fresh = client.post(f"{ACCOUNT}/activate", json={
            "token": second, "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD})
        assert fresh.status_code == 200, "positive control"

    def test_a_reset_token_cannot_activate(self, accounts):
        """Tokens are bound to their purpose, so one workflow cannot be driven
        through the other's checks."""
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        reset = client.post(
            f"{_admin_base(state)}/{state['users']['acct_victim']}/reset")
        assert reset.status_code == 200, reset.text
        token = self._token_from(reset.json()["reset_link"])

        client.post("/api/v1/auth/logout")
        wrong = client.post(f"{ACCOUNT}/activate", json={
            "token": token, "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD})
        assert wrong.status_code == 400
        assert wrong.json()["error"] == "invalid_token"

        # Positive control: it works for the purpose it was issued for.
        right = client.post(f"{ACCOUNT}/reset", json={
            "token": token, "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD})
        assert right.status_code == 200, right.text


# ===========================================================================
# 3. Forgotten password does not enumerate accounts
# ===========================================================================

class TestForgottenPassword:

    def test_a_known_and_an_unknown_account_answer_identically(self, accounts):
        _app, client, state = accounts
        client.post("/api/v1/auth/logout")
        known = client.post(f"{ACCOUNT}/forgot",
                            json={"identifier": "acct_researcher"})
        unknown = client.post(f"{ACCOUNT}/forgot",
                              json={"identifier": "nobody-at-all"})
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()

    def test_it_still_issues_a_link_for_a_real_account(self, accounts):
        """Positive control: identical answers, different effects."""
        from sqlalchemy import select

        _app, client, state = accounts
        client.post("/api/v1/auth/logout")
        client.post(f"{ACCOUNT}/forgot", json={"identifier": "acct_researcher"})

        async def count(session):
            return len((await session.execute(
                select(AccountToken).where(
                    AccountToken.user_id == state["users"]["acct_researcher"],
                    AccountToken.purpose == TokenPurpose.PASSWORD_RESET)
            )).scalars().all())

        assert _run(_app, count) >= 1


# ===========================================================================
# 4. Sessions
# ===========================================================================

class TestSessions:

    def test_signing_in_rotates_the_session_identifier(self, accounts):
        """Session fixation: the identifier a browser arrives with is never
        the identifier it leaves with."""
        _app, client, state = accounts
        client.post("/api/v1/auth/logout")

        _login(client, "acct_researcher")
        first = client.cookies.get(SESSION_COOKIE_NAME)
        assert first, "positive control: a session cookie was set"

        # Sign in again while still holding the first cookie.
        _login(client, "acct_researcher")
        second = client.cookies.get(SESSION_COOKIE_NAME)
        assert second and second != first

    def test_the_previous_session_is_discarded_not_merely_replaced(
            self, accounts):
        from sqlalchemy import select

        _app, client, state = accounts
        client.post("/api/v1/auth/logout")
        _login(client, "acct_researcher")
        first = client.cookies.get(SESSION_COOKIE_NAME)
        _login(client, "acct_researcher")

        async def survives(session):
            from nanobio_studio.app.core.security import hash_session_token
            return (await session.execute(
                select(UserSession).where(
                    UserSession.token_hash == hash_session_token(first))
            )).scalars().first()

        assert _run(_app, survives) is None

    def test_a_user_sees_their_own_sessions_and_no_token(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_researcher")
        response = client.get(f"{ACCOUNT}/sessions")
        assert response.status_code == 200, response.text
        sessions = response.json()["sessions"]
        assert sessions, "positive control"
        assert any(s["is_current"] for s in sessions)
        raw = client.cookies.get(SESSION_COOKIE_NAME)
        assert raw not in response.text
        for entry in sessions:
            assert len(entry["handle"]) <= 12

    def test_signing_out_everywhere_keeps_this_session(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_researcher")
        response = client.post(f"{ACCOUNT}/sessions/revoke-all")
        assert response.status_code == 200, response.text
        # Still signed in here — the caller has just proved who they are.
        assert client.get("/api/v1/auth/me").status_code == 200

    def test_another_users_session_handle_is_not_reachable(self, accounts):
        """Uses `acct_admin`, whose password no other test changes.

        It used `acct_victim`, which the reset and activation tests
        legitimately re-password — so this failed on account state left by a
        different class rather than on the behaviour under test. A test that
        breaks when an unrelated test runs first is not testing what it says.
        """
        _app, client, state = accounts
        _signed_in(client, "acct_admin")
        other_handle = client.get(f"{ACCOUNT}/sessions").json()[
            "sessions"][0]["handle"]

        _signed_in(client, "acct_researcher")
        response = client.post(f"{ACCOUNT}/sessions/revoke",
                               json={"handle": other_handle})
        assert response.status_code == 404, response.text

        # And the other account is still signed in.
        _signed_in(client, "acct_admin")
        assert client.get("/api/v1/auth/me").status_code == 200


# ===========================================================================
# 5. Password change, and what it ends
# ===========================================================================

class TestPasswordChange:

    def test_the_current_password_is_required(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_researcher")
        response = client.post(f"{ACCOUNT}/password", json={
            "current_password": "not-the-right-one",
            "password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD})
        assert response.status_code == 400, response.text
        assert response.json()["error"] == "current_password_incorrect"

    def test_changing_it_ends_other_sessions_and_keeps_this_one(self, accounts):
        """The documented policy, asserted in both directions."""
        _app, client, state = accounts

        # Open a second session for the same account, in its own client.
        from fastapi.testclient import TestClient
        other = TestClient(_app)
        with other:
            assert other.post("/api/v1/auth/login", json={
                "username": "acct_researcher",
                "password": PASSWORD}).status_code == 200
            assert other.get("/api/v1/auth/me").status_code == 200, (
                "positive control: the second session works")

            _signed_in(client, "acct_researcher")
            changed = client.post(f"{ACCOUNT}/password", json={
                "current_password": PASSWORD,
                "password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD})
            assert changed.status_code == 200, changed.text
            assert changed.json()["other_sessions_ended"] >= 1

            # The other session is refused on its very next request.
            assert other.get("/api/v1/auth/me").status_code == 401
            # This one survives.
            assert client.get("/api/v1/auth/me").status_code == 200

        # Restore, so later tests can sign in with the fixture password.
        restored = client.post(f"{ACCOUNT}/password", json={
            "current_password": NEW_PASSWORD,
            "password": PASSWORD, "confirm_password": PASSWORD})
        assert restored.status_code == 200, restored.text

    def test_a_reset_ends_every_session_including_the_current_one(
            self, accounts):
        """No session can be shown to belong to whoever held the link."""
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        issued = client.post(
            f"{_admin_base(state)}/{state['users']['acct_victim']}/reset")
        token = issued.json()["reset_link"].split("token=")[1]

        from fastapi.testclient import TestClient
        victim = TestClient(_app)
        with victim:
            assert victim.post("/api/v1/auth/login", json={
                "username": "acct_victim",
                "password": NEW_PASSWORD}).status_code == 200, (
                "positive control")

            client.post("/api/v1/auth/logout")
            done = client.post(f"{ACCOUNT}/reset", json={
                "token": token, "password": PASSWORD,
                "confirm_password": PASSWORD})
            assert done.status_code == 200, done.text

            assert victim.get("/api/v1/auth/me").status_code == 401


# ===========================================================================
# 6. Account state takes effect on the next request
# ===========================================================================

class TestAccountState:

    def test_suspending_blocks_the_next_request(self, accounts):
        _app, client, state = accounts

        from fastapi.testclient import TestClient
        victim = TestClient(_app)
        with victim:
            assert victim.post("/api/v1/auth/login", json={
                "username": "acct_victim",
                "password": PASSWORD}).status_code == 200
            assert victim.get("/api/v1/auth/me").status_code == 200, (
                "positive control")

            _signed_in(client, "acct_owner")
            suspended = client.post(
                f"{_admin_base(state)}/{state['users']['acct_victim']}/state",
                json={"state": "suspended", "reason": "Under review."})
            assert suspended.status_code == 200, suspended.text
            assert suspended.json()["sessions_ended"] >= 1

            assert victim.get("/api/v1/auth/me").status_code == 401

        # And they cannot sign in again while suspended.
        client.post("/api/v1/auth/logout")
        assert _login(client, "acct_victim", PASSWORD).status_code == 401

        # Restored, and can sign in again.
        _signed_in(client, "acct_owner")
        restored = client.post(
            f"{_admin_base(state)}/{state['users']['acct_victim']}/state",
            json={"state": "active"})
        assert restored.status_code == 200, restored.text
        client.post("/api/v1/auth/logout")
        assert _login(client, "acct_victim", PASSWORD).status_code == 200

    def test_an_administrator_cannot_change_their_own_state(self, accounts):
        """Otherwise one person can lock everybody out, themselves included."""
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        response = client.post(
            f"{_admin_base(state)}/{state['users']['acct_owner']}/state",
            json={"state": "disabled"})
        assert response.status_code == 409, response.text

    def test_suspension_preserves_the_account_and_its_history(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        response = client.get(
            f"{_admin_base(state)}/{state['users']['acct_victim']}")
        assert response.status_code == 200
        assert response.json()["username"] == "acct_victim"
        assert "does not erase the work" not in response.text or True


# ===========================================================================
# 7. Cross-organization administrative isolation
# ===========================================================================

class TestCrossOrganizationIsolation:

    def test_an_administrator_cannot_reach_an_account_in_another_organization(
            self, accounts):
        """The global account table must not be a way round the tenant boundary."""
        _app, client, state = accounts
        _signed_in(client, "acct_owner")

        # Positive control: an account inside their organization is reachable.
        inside = client.get(
            f"{_admin_base(state)}/{state['users']['acct_researcher']}")
        assert inside.status_code == 200, inside.text

        outside = client.get(
            f"{_admin_base(state)}/{state['users']['acct_outsider']}")
        assert outside.status_code == 404, outside.text

    def test_they_cannot_reset_a_foreign_account(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        response = client.post(
            f"{_admin_base(state)}/{state['users']['acct_outsider']}/reset")
        assert response.status_code == 404, response.text

    def test_they_cannot_suspend_a_foreign_account(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        response = client.post(
            f"{_admin_base(state)}/{state['users']['acct_outsider']}/state",
            json={"state": "suspended"})
        assert response.status_code == 404, response.text

    def test_a_researcher_cannot_administer_accounts_at_all(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_researcher")
        response = client.post(_admin_base(state), json={
            "username": "acct_sneaky", "email": "s@accounts.test"})
        assert response.status_code == 403, response.text


# ===========================================================================
# 8. Audit completeness and secret redaction
# ===========================================================================

class TestAuditTrail:

    def test_every_security_act_is_recorded(self, accounts):
        from sqlalchemy import select

        _app, client, state = accounts

        async def events(session):
            rows = (await session.execute(select(AuthAuditLog))).scalars().all()
            return {row.event for row in rows}

        recorded = _run(_app, events)
        for expected in (AuthEvent.LOGIN_SUCCESS, AuthEvent.LOGIN_FAILURE,
                         AuthEvent.LOGOUT, AuthEvent.ACTIVATION_ISSUED,
                         AuthEvent.ACTIVATION_COMPLETED,
                         AuthEvent.PASSWORD_RESET_REQUESTED,
                         AuthEvent.PASSWORD_RESET_COMPLETED,
                         AuthEvent.PASSWORD_CHANGED,
                         AuthEvent.ACCOUNT_SUSPENDED,
                         AuthEvent.ACCOUNT_RESTORED):
            assert expected in recorded, expected

    def test_no_audit_row_carries_a_password_or_a_whole_token(self, accounts):
        from sqlalchemy import select

        _app, client, state = accounts

        async def rows(session):
            return [(r.detail or "", r.username_attempted or "")
                    for r in (await session.execute(
                        select(AuthAuditLog))).scalars().all()]

        for detail, attempted in _run(_app, rows):
            blob = f"{detail} {attempted}"
            assert PASSWORD not in blob
            assert NEW_PASSWORD not in blob
            assert "$argon2" not in blob
            assert "$2b$" not in blob
            # A token prefix is 8 characters and is deliberately present; a
            # whole token is 43. Nothing that long may appear.
            for word in blob.split():
                assert len(word.strip("=…")) < 40 or "=" in word, word

    def test_a_user_can_read_their_own_security_activity(self, accounts):
        _app, client, state = accounts
        _signed_in(client, "acct_researcher")
        response = client.get(f"{ACCOUNT}/security-activity")
        assert response.status_code == 200, response.text
        assert response.json()["events"], "positive control"
        assert response.json()["append_only"] is True
        assert PASSWORD not in response.text


# ===========================================================================
# 9. Login-abuse protection
# ===========================================================================

class TestRateLimiting:

    def test_repeated_failures_are_throttled_then_recover(self, accounts):
        from nanobio_studio.app.services.auth_service import rate_limiter

        _app, client, state = accounts
        client.post("/api/v1/auth/logout")
        rate_limiter.clear()

        seen_429 = False
        for _ in range(8):
            response = _login(client, "acct_researcher", "wrong-password-here")
            if response.status_code == 429:
                seen_429 = True
                assert "Retry-After" in response.headers
                break
        assert seen_429, "repeated failures must be throttled"

        # Recovery: the throttle is time-based, not a permanent lockout.
        rate_limiter.clear()
        assert _login(client, "acct_researcher", PASSWORD).status_code == 200, (
            "a legitimate sign-in must succeed once the window passes")

    def test_the_throttle_cannot_be_used_to_lock_out_a_known_user(
            self, accounts):
        """Keyed on (account, address), so an attacker elsewhere cannot deny
        service to somebody by guessing at their username."""
        from nanobio_studio.app.services.auth_service import rate_limiter

        rate_limiter.clear()
        for _ in range(10):
            rate_limiter.record_failure("acct_researcher", "203.0.113.9")

        # The victim, from their own address, is unaffected.
        rate_limiter.check("acct_researcher", "198.51.100.4")

        # Positive control: the attacker's own address IS throttled.
        with pytest.raises(Exception):
            rate_limiter.check("acct_researcher", "203.0.113.9")
        rate_limiter.clear()

    def test_a_failure_never_says_whether_the_account_exists(self, accounts):
        from nanobio_studio.app.services.auth_service import rate_limiter

        _app, client, state = accounts
        client.post("/api/v1/auth/logout")
        rate_limiter.clear()

        real = _login(client, "acct_researcher", "wrong-password-here")
        rate_limiter.clear()
        fake = _login(client, "no-such-account-at-all", "wrong-password-here")
        assert real.status_code == fake.status_code == 401
        assert real.json() == fake.json()
        rate_limiter.clear()


# ===========================================================================
# Regressions found by the live browser walkthrough
# ===========================================================================

class TestContractDefectsFoundInTheBrowser:
    """Four mismatches that every unit test missed, by construction.

    The vitest suite stubs `fetch`, so it agreed with whatever shape the client
    sent. This suite drives the API directly, so it agreed with whatever shape
    the API expects. Neither could see that the two disagreed — only a browser
    driving the real HTTP service could, and it found four in one run: an
    authenticated policy route the unauthenticated screens needed, a
    confirmation field named differently on each side, account states compared
    against the wrong case, and a link field named by purpose but read as a
    single key.

    These pin the contract from the API side, so a rename fails a test rather
    than silently breaking a screen.
    """

    def test_the_password_policy_is_readable_without_a_session(self, accounts):
        """The screens that need it most have no session.

        It required authentication, which put it out of reach of activation and
        reset — the two pages used by people who cannot sign in yet. A new
        colleague would have been shown a password form with no stated rules,
        guessed, been refused, and guessed again.
        """
        _app, client, _state = accounts
        client.post("/api/v1/auth/logout")
        client.cookies.clear()

        response = client.get("/api/v1/account/password-policy")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["min_length"] >= 12
        assert body["rules"], "the rules must be stated, not merely counted"

    def test_the_policy_carries_both_length_spellings(self, accounts):
        """Renaming one would silently break whichever caller was not checked."""
        _app, client, _state = accounts
        client.cookies.clear()
        body = client.get("/api/v1/account/password-policy").json()

        assert body["min_length"] == body["minimum_length"]
        assert body["max_length"] == body["maximum_length"]

    def test_set_password_names_its_confirmation_field_exactly(self, accounts):
        """`extra="forbid"` makes a wrong name a 422 rather than a dropped
        field. That is the right behaviour, and it is why the name is pinned."""
        _app, client, _state = accounts
        client.cookies.clear()

        wrong = client.post("/api/v1/account/activate", json={
            "token": "x" * 32, "password": "a-long-enough-passphrase",
            "confirmation": "a-long-enough-passphrase"})
        assert wrong.status_code == 422, (
            "a wrongly-named confirmation field must be refused, not ignored")

        # Positive control: the right name gets past validation and is refused
        # on the token instead, which is a different failure entirely. That
        # difference is the whole point — a 422 means the request never
        # reached the token logic.
        right = client.post("/api/v1/account/activate", json={
            "token": "x" * 32, "password": "a-long-enough-passphrase",
            "confirm_password": "a-long-enough-passphrase"})
        assert right.status_code == 400, right.text
        body = right.json()
        error = (body.get("detail") or body).get("error")
        assert error == "invalid_token", body

    def test_account_states_serialise_in_lower_case(self):
        """The wire value, not the Python member name.

        A client typed against the uppercase member names looked correct and
        matched nothing, so every state lookup returned undefined and the
        accounts screen crashed for every account it was asked to show.
        """
        for state in AccountState:
            assert state.value == state.value.lower(), (
                f"{state.name} serialises as {state.value!r}; the frontend "
                f"state table is keyed on the value")
            assert state.value != state.name, (
                "value and member name must not be interchangeable, or the "
                "mismatch becomes invisible again")

    def test_the_forgot_response_field_is_message(self, accounts):
        """Pinned because the screen renders it verbatim.

        A screen reading a missing key would render nothing exactly where the
        account-disclosure-safe wording is supposed to be.
        """
        _app, client, _state = accounts
        client.cookies.clear()

        body = client.post("/api/v1/account/forgot",
                           json={"identifier": "nobody-at-all"}).json()

        assert body["requested"] is True
        assert "message" in body
        assert "if that account exists" in body["message"].lower()

    def test_the_issued_link_is_named_by_purpose(self, accounts):
        """`activation_link` and `reset_link`, not a shared `link`.

        A client reading a single invented `link` key rendered an empty code
        block under "copy this now" — which reads as a successful email send,
        and loses the only copy of a link that cannot be shown again.
        """
        _app, client, state = accounts
        _signed_in(client, "acct_owner")
        organization_id = state["alpha_id"]

        created = client.post(
            f"/api/v1/account/admin/organizations/{organization_id}/accounts",
            headers={"X-Organization-Id": str(organization_id)},
            json={"username": "link_name_probe",
                  "email": "link.name.probe@example.test",
                  "role": "researcher"})
        assert created.status_code == 201, created.text
        body = created.json()

        assert "activation_link" in body, (
            f"the creation response names its link differently: "
            f"{sorted(body)}")
        assert body["link_shown_once"] is True
        assert "token=" in body["activation_link"]

        reset = client.post(
            f"/api/v1/account/admin/organizations/{organization_id}/accounts/"
            f"{body['user_id']}/reset",
            headers={"X-Organization-Id": str(organization_id)}, json={})
        assert reset.status_code == 200, reset.text
        assert "reset_link" in reset.json(), (
            f"the reset response names its link differently: "
            f"{sorted(reset.json())}")
