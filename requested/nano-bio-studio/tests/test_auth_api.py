"""Backend authentication tests.

Every test runs against an **isolated temporary SQLite database**. The real
development auth database and the legacy ``users.db`` are never opened.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Isolated database
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def auth_env(tmp_path_factory):
    """App + client + session factory bound to a throwaway database."""
    from tests.conftest import make_isolated_auth_client

    tmp_dir = tmp_path_factory.mktemp("auth_api")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    with client:
        yield app, client, factory, tmp_dir
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def app_and_client(auth_env):
    app, client, _factory, _tmp = auth_env
    return app, client


@pytest.fixture(scope="module")
def session_factory(auth_env):
    return auth_env[2]


@pytest.fixture(scope="module")
def auth_db_path(auth_env):
    return auth_env[3] / "isolated_auth.db"


@pytest.fixture(scope="module")
def seeded_users(session_factory):
    """Create one user per role directly in the isolated database."""
    from tests.conftest import run_async

    from nanobio_studio.app.db.auth_models import UserRole
    from nanobio_studio.app.services.auth_service import create_user

    creds = {
        "admin": ("admin_test", "AdminPassword-2026!", UserRole.ADMIN),
        "researcher": ("res_test", "ResearchPassword-2026!", UserRole.RESEARCHER),
        "viewer": ("view_test", "ViewerPassword-2026!", UserRole.VIEWER),
    }

    async def _seed():
        async with session_factory() as session:
            for username, password, role in creds.values():
                try:
                    await create_user(session, username=username,
                                      password=password, role=role,
                                      email=f"{username}@test.local")
                except ValueError:
                    pass  # already seeded
            await session.commit()

    run_async(_seed())
    return creds


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    from nanobio_studio.app.services.auth_service import rate_limiter
    rate_limiter.clear()
    yield
    rate_limiter.clear()


LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"
SCORE = "/api/v1/design/score"
DESIGN = {"size_nm": 100, "charge_mv": -5, "encapsulation_percent": 85}


# ===========================================================================
# Login
# ===========================================================================


class TestLogin:

    def test_successful_login(self, app_and_client, seeded_users):
        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        r = client.post(LOGIN, json={"username": u, "password": p})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["username"] == u
        assert body["user"]["role"] == "admin"
        client.post(LOGOUT)

    def test_session_cookie_is_httponly_and_samesite(self, app_and_client,
                                                     seeded_users):
        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        r = client.post(LOGIN, json={"username": u, "password": p})
        cookie_header = r.headers.get("set-cookie", "").lower()
        assert "httponly" in cookie_header
        assert "samesite=lax" in cookie_header
        assert "path=/" in cookie_header
        client.post(LOGOUT)

    def test_response_never_contains_the_token_or_hash(self, app_and_client,
                                                       seeded_users):
        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        r = client.post(LOGIN, json={"username": u, "password": p})
        assert "password_hash" not in r.text
        assert "token" not in r.json()
        client.post(LOGOUT)

    def test_wrong_password_is_rejected(self, app_and_client, seeded_users):
        _, client = app_and_client
        u, _, _ = seeded_users["admin"]
        r = client.post(LOGIN, json={"username": u, "password": "not-the-password"})
        assert r.status_code == 401
        assert r.json()["error"] == "invalid_credentials"

    def test_unknown_user_and_wrong_password_are_indistinguishable(
            self, app_and_client, seeded_users):
        """Must not reveal whether an account exists."""
        _, client = app_and_client
        u, _, _ = seeded_users["admin"]
        bad_pw = client.post(LOGIN, json={"username": u, "password": "wrong"})
        unknown = client.post(LOGIN, json={"username": "does_not_exist",
                                           "password": "wrong"})
        assert bad_pw.status_code == unknown.status_code == 401
        assert bad_pw.json()["message"] == unknown.json()["message"]

    def test_empty_credentials_rejected(self, app_and_client):
        _, client = app_and_client
        assert client.post(LOGIN, json={"username": "", "password": ""}
                           ).status_code == 422

    def test_unknown_fields_rejected(self, app_and_client, seeded_users):
        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        r = client.post(LOGIN, json={"username": u, "password": p, "role": "admin"})
        assert r.status_code == 422


# ===========================================================================
# Rate limiting
# ===========================================================================


class TestRateLimiting:

    def test_repeated_failures_trigger_lockout(self, app_and_client, seeded_users):
        _, client = app_and_client
        u, _, _ = seeded_users["viewer"]

        statuses = [
            client.post(LOGIN, json={"username": u, "password": "wrong"}).status_code
            for _ in range(6)
        ]
        assert 429 in statuses, f"no lockout occurred: {statuses}"

    def test_lockout_response_is_structured(self, app_and_client, seeded_users):
        _, client = app_and_client
        u, _, _ = seeded_users["viewer"]
        last = None
        for _ in range(7):
            last = client.post(LOGIN, json={"username": u, "password": "wrong"})
        assert last.status_code == 429
        body = last.json()
        assert body["error"] == "rate_limited"
        assert body["retry_after_seconds"] > 0
        assert "Retry-After" in last.headers

    def test_correct_password_blocked_while_locked_out(self, app_and_client,
                                                       seeded_users):
        """Lockout must not be bypassable by then supplying the right password."""
        _, client = app_and_client
        u, p, _ = seeded_users["viewer"]
        for _ in range(6):
            client.post(LOGIN, json={"username": u, "password": "wrong"})
        r = client.post(LOGIN, json={"username": u, "password": p})
        assert r.status_code == 429

    def test_successful_login_resets_the_counter(self, app_and_client,
                                                 seeded_users):
        _, client = app_and_client
        u, p, _ = seeded_users["researcher"]
        for _ in range(3):
            client.post(LOGIN, json={"username": u, "password": "wrong"})
        assert client.post(LOGIN, json={"username": u, "password": p}
                           ).status_code == 200
        client.post(LOGOUT)
        for _ in range(3):
            client.post(LOGIN, json={"username": u, "password": "wrong"})
        # Still under the threshold because the counter was reset.
        assert client.post(LOGIN, json={"username": u, "password": p}
                           ).status_code == 200
        client.post(LOGOUT)


# ===========================================================================
# Profile / protected routes
# ===========================================================================


class TestProfileAndProtectedRoutes:

    def test_me_requires_authentication(self, app_and_client):
        _, client = app_and_client
        assert client.get(ME).status_code == 401

    def test_me_returns_the_profile_without_secrets(self, app_and_client,
                                                    seeded_users):
        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        client.post(LOGIN, json={"username": u, "password": p})
        r = client.get(ME)
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == u
        assert "password_hash" not in body
        assert "password" not in body
        client.post(LOGOUT)

    def test_scoring_requires_authentication(self, app_and_client):
        _, client = app_and_client
        r = client.post(SCORE, json=DESIGN)
        assert r.status_code == 401

    def test_scoring_works_when_authenticated(self, app_and_client, seeded_users):
        _, client = app_and_client
        u, p, _ = seeded_users["researcher"]
        client.post(LOGIN, json={"username": u, "password": p})
        r = client.post(SCORE, json=DESIGN)
        assert r.status_code == 200
        assert r.json()["design_impact_score"]["delivery"] == 87.52475247524752
        client.post(LOGOUT)

    def test_scoring_numerics_unchanged_by_authentication(self, app_and_client,
                                                          seeded_users):
        """Adding auth must not alter the scientific result."""
        from core.scoring import compute_impact

        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        client.post(LOGIN, json={"username": u, "password": p})
        api = client.post(SCORE, json=DESIGN).json()["design_impact_score"]
        legacy = compute_impact({"Size": 100, "Charge": -5, "Encapsulation": 85})
        assert api["delivery"] == legacy["Delivery"]
        assert api["toxicity"] == legacy["Toxicity"]
        assert api["cost"] == legacy["Cost"]
        client.post(LOGOUT)

    def test_health_stays_public(self, app_and_client):
        _, client = app_and_client
        assert client.get("/health").status_code == 200


# ===========================================================================
# Logout / session lifecycle
# ===========================================================================


class TestLogout:

    def test_logout_revokes_the_session(self, app_and_client, seeded_users):
        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        client.post(LOGIN, json={"username": u, "password": p})
        assert client.get(ME).status_code == 200
        assert client.post(LOGOUT).status_code == 200
        assert client.get(ME).status_code == 401

    def test_logout_clears_the_cookie(self, app_and_client, seeded_users):
        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        client.post(LOGIN, json={"username": u, "password": p})
        r = client.post(LOGOUT)
        assert 'nanobio_session=""' in r.headers.get("set-cookie", "") or \
               "nanobio_session=;" in r.headers.get("set-cookie", "")

    def test_logout_without_a_session_is_safe(self, app_and_client):
        _, client = app_and_client
        assert client.post(LOGOUT).status_code == 200

    def test_forged_cookie_is_rejected(self, app_and_client):
        """A guessed token must not authenticate anyone."""
        _, client = app_and_client
        client.cookies.set("nanobio_session", "token_admin_1785000000")
        assert client.get(ME).status_code == 401
        client.cookies.clear()


class TestSessionExpiry:

    def test_expired_session_is_rejected_and_removed(self, app_and_client,
                                                     seeded_users,
                                                     session_factory):
        """Force an absolute expiry in the past and confirm rejection."""
        from datetime import timedelta

        from sqlalchemy import select

        from tests.conftest import run_async

        from nanobio_studio.app.db.auth_models import UserSession, utcnow

        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        client.post(LOGIN, json={"username": u, "password": p})
        assert client.get(ME).status_code == 200

        async def _expire():
            async with session_factory() as s:
                rows = (await s.execute(select(UserSession))).scalars().all()
                for row in rows:
                    row.expires_at = utcnow() - timedelta(minutes=1)
                await s.commit()

        run_async(_expire())

        assert client.get(ME).status_code == 401
        client.cookies.clear()


# ===========================================================================
# Role-based access control
# ===========================================================================


class TestRoleBasedAccess:

    def test_roles_are_reported_correctly(self, app_and_client, seeded_users):
        _, client = app_and_client
        for expected, (u, p, _) in seeded_users.items():
            client.post(LOGIN, json={"username": u, "password": p})
            assert client.get(ME).json()["role"] == expected
            client.post(LOGOUT)

    def test_require_role_dependency_blocks_wrong_role(self, app_and_client,
                                                       seeded_users):
        """Mount a temporary admin-only route and check enforcement."""
        from fastapi import Depends

        from nanobio_studio.app.api.deps_auth import require_admin
        from nanobio_studio.app.db.auth_models import User

        app, client = app_and_client

        @app.get("/api/v1/_test/admin-only")
        async def _admin_only(user: User = Depends(require_admin)):
            return {"ok": True, "user": user.username}

        u, p, _ = seeded_users["researcher"]
        client.post(LOGIN, json={"username": u, "password": p})
        assert client.get("/api/v1/_test/admin-only").status_code == 403
        client.post(LOGOUT)

        u, p, _ = seeded_users["admin"]
        client.post(LOGIN, json={"username": u, "password": p})
        assert client.get("/api/v1/_test/admin-only").status_code == 200
        client.post(LOGOUT)

    def test_admin_only_route_requires_authentication(self, app_and_client):
        _, client = app_and_client
        assert client.get("/api/v1/_test/admin-only").status_code == 401


# ===========================================================================
# Audit logging
# ===========================================================================


class TestAuditLogging:

    @staticmethod
    def _events(factory):
        from sqlalchemy import select

        from tests.conftest import run_async

        from nanobio_studio.app.db.auth_models import AuthAuditLog

        async def _read():
            async with factory() as s:
                rows = (await s.execute(select(AuthAuditLog))).scalars().all()
                return [r.event.value for r in rows]

        return run_async(_read())

    def test_login_logout_and_failure_are_audited(self, app_and_client,
                                                  seeded_users,
                                                  session_factory):
        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        client.post(LOGIN, json={"username": u, "password": "wrong"})
        client.post(LOGIN, json={"username": u, "password": p})
        client.post(LOGOUT)

        events = self._events(session_factory)
        assert "login_failure" in events
        assert "login_success" in events
        assert "logout" in events

    def test_audit_never_records_a_password(self, app_and_client, seeded_users,
                                            session_factory):
        from sqlalchemy import select

        from tests.conftest import run_async

        from nanobio_studio.app.db.auth_models import AuthAuditLog

        _, client = app_and_client
        u, p, _ = seeded_users["admin"]
        client.post(LOGIN, json={"username": u, "password": p})
        client.post(LOGOUT)

        async def _read():
            async with session_factory() as s:
                rows = (await s.execute(select(AuthAuditLog))).scalars().all()
                return " ".join(f"{r.detail or ''} {r.username_attempted or ''}"
                                for r in rows)

        blob = run_async(_read())
        assert p not in blob


# ===========================================================================
# Password hashing
# ===========================================================================


class TestPasswordHashing:

    def test_hash_is_not_the_plaintext(self):
        from nanobio_studio.app.core.security import hash_password, verify_password

        h = hash_password("a-strong-password-2026")
        assert h != "a-strong-password-2026"
        assert h.startswith("$2")
        assert verify_password("a-strong-password-2026", h)
        assert not verify_password("wrong", h)

    def test_hashes_are_salted(self):
        from nanobio_studio.app.core.security import hash_password

        assert hash_password("same-password-1234") != hash_password("same-password-1234")

    def test_verify_never_raises_on_malformed_input(self):
        from nanobio_studio.app.core.security import verify_password

        for bad in (None, "", "not-a-hash", b"\x00\x01"):
            assert verify_password("x", bad) is False

    def test_session_tokens_are_random_and_hashed(self):
        from nanobio_studio.app.core.security import (
            generate_session_token,
            hash_session_token,
        )

        a, b = generate_session_token(), generate_session_token()
        assert a != b
        assert len(a) > 30
        assert hash_session_token(a) != a
        assert len(hash_session_token(a)) == 64

    def test_token_is_not_derived_from_the_username(self):
        """The legacy scheme was token_{username}_{timestamp}."""
        from nanobio_studio.app.core.security import generate_session_token

        assert "admin" not in generate_session_token()


# ===========================================================================
# Legacy database isolation
# ===========================================================================


class TestLegacyDatabaseIsolation:

    def test_legacy_users_db_is_never_referenced(self):
        """No auth module may point at the legacy SQLite file.

        Checks executable code only. Comments and docstrings are stripped first:
        several of these modules deliberately *document* that they never touch
        ``users.db``, and that documentation must not trip the assertion.
        """
        import ast

        backend = REPO_ROOT / "nanobio_studio_backend" / "nanobio_studio" / "app"
        for rel in ("db/auth_session.py", "db/auth_models.py",
                    "services/auth_service.py", "api/routes/auth.py"):
            source = (backend / rel).read_text(encoding="utf-8")
            tree = ast.parse(source)

            # Collect every string constant that is NOT a docstring.
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef)):
                    doc = ast.get_docstring(node, clean=False)
                    if doc is not None:
                        docstrings.add(doc)

            literals = [
                n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and n.value not in docstrings
            ]
            offenders = [s for s in literals if "users.db" in s]
            assert not offenders, (
                f"{rel} references the legacy database in code: {offenders}")

    def test_auth_db_is_separate_from_legacy(self, auth_db_path):
        assert auth_db_path.name != "users.db"
        assert (REPO_ROOT / "users.db").exists(), "legacy db should still exist"
