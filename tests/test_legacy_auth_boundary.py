"""The legacy Streamlit authentication system, and the wall between it and this one.

Why this file exists in *this* milestone
----------------------------------------
The legacy application (``auth.py``, ``streamlit_auth.py``, ``users.db``) is not
being migrated or deleted here — that is its own milestone. What cannot wait is
the *boundary*: two authentication systems in one repository, sharing a machine
and possibly a reverse proxy, is exactly the arrangement in which one of them
quietly becomes a way into the other.

So this asserts the wall, and nothing about the legacy system's own quality.
Three claims, each of which would be a serious finding if false:

1. **A legacy cookie or token is not accepted by the main application.** The
   legacy scheme issued ``token_{username}_{unix_seconds}`` — forgeable by
   anyone who can read a clock — so a main-application route that honoured one
   would be authenticating on a guessable string.

2. **The main application never reads ``users.db``.** A shared password
   database means a change on one side silently changes the other, and the
   legacy schema is the one with the BLOB/TEXT hash conflict.

3. **There is no shared secret and no fallback path.** Nothing in the main
   application falls back to legacy verification when its own lookup fails,
   which is the shape a "temporary compatibility" branch usually takes.

The inventory below is deliberately recorded as data, so the later migration
milestone starts from a list rather than a search.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.services.auth_service import (  # noqa: E402
    SESSION_COOKIE_NAME,
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

#: The legacy authentication surface, recorded for the later milestone.
LEGACY_FILES = (
    "auth.py",
    "streamlit_auth.py",
    "users.db",
    "sessions.json",
)

#: Everything the main application is allowed to open. `users.db` is not here.
MAIN_APPLICATION_DATABASES = ("nanobio_auth_dev.db",)


@pytest.fixture(scope="module")
def isolated(tmp_path_factory):
    app, client, factory = make_isolated_auth_client(
        tmp_path_factory.mktemp("legacy_boundary"))
    with client:
        yield app, client
    app.dependency_overrides.clear()


# ===========================================================================
# 1. Inventory
# ===========================================================================

class TestLegacyInventory:

    def test_the_legacy_surface_is_recorded_not_searched_for(self):
        """A later milestone should start from a list, not a grep."""
        present = [name for name in LEGACY_FILES if (REPO_ROOT / name).exists()]
        assert present, (
            "none of the recorded legacy files exist. If they were removed, "
            "this list and the legacy-boundary milestone should be closed "
            "deliberately rather than left asserting nothing.")

    def test_the_legacy_user_database_is_readable_and_separate(self):
        """Confirms it is a real, separate store — not that it is any good."""
        legacy = REPO_ROOT / "users.db"
        if not legacy.exists():
            pytest.skip("users.db is not present in this checkout")

        connection = sqlite3.connect(f"file:{legacy}?mode=ro", uri=True)
        try:
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            connection.close()

        # The main application's tables must NOT be in here, and vice versa.
        assert "auth_users" not in tables, (
            "the legacy database contains the main application's user table, "
            "which would mean the two systems are sharing accounts")
        assert "auth_sessions" not in tables
        assert "auth_account_tokens" not in tables


# ===========================================================================
# 2. The main application does not accept legacy credentials
# ===========================================================================

class TestLegacyTokensAreNotAccepted:

    @pytest.mark.parametrize("legacy_token", [
        # The legacy scheme, exactly: token_{username}_{unix_seconds}.
        "token_admin_1785000000",
        "token_rpt_admin_1785000000",
        "token_researcher_1",
        # And the shapes around it.
        "admin", "1785000000", "token__",
    ])
    def test_a_forged_legacy_token_is_not_a_session(self, isolated,
                                                    legacy_token):
        """The legacy token was guessable. Honouring one would be catastrophic.

        Anybody who knew a username and could read a clock could construct a
        valid legacy token. If the main application accepted one, its entire
        session model would reduce to that.
        """
        _app, client = isolated
        client.cookies.clear()
        client.cookies.set(SESSION_COOKIE_NAME, legacy_token)

        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401, response.text
        assert response.json()["detail"]["error"] == "not_authenticated"

    def test_a_legacy_cookie_name_carries_no_authority(self, isolated):
        """Even a legitimate-looking legacy cookie under its own name."""
        _app, client = isolated
        client.cookies.clear()
        for name in ("session", "streamlit_session", "auth_token",
                     "nanobio_user", "user_token"):
            client.cookies.set(name, "token_admin_1785000000")

        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401, response.text
        client.cookies.clear()

    def test_a_real_session_still_works(self, isolated):
        """Positive control: the refusals above are about the token, not the
        endpoint being broken."""
        from nanobio_studio.app.db.auth_models import UserRole
        from nanobio_studio.app.services.auth_service import create_user

        _app, client = isolated

        async def seed():
            from nanobio_studio.app.db.auth_session import get_auth_session
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                await create_user(session, username="boundary_user",
                                  password="a-genuine-long-passphrase",
                                  role=UserRole.RESEARCHER)
                await session.commit()
            finally:
                await generator.aclose()

        run_async(seed())

        client.cookies.clear()
        assert client.post("/api/v1/auth/login", json={
            "username": "boundary_user",
            "password": "a-genuine-long-passphrase"}).status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 200


# ===========================================================================
# 3. No shared database, secret or fallback
# ===========================================================================

class TestNoSharedPathBetweenTheSystems:

    def test_the_main_application_never_opens_the_legacy_database(self):
        """Checked against the parsed source, not against the file text.

        A substring search over the raw text fails on the two modules whose
        *docstrings* explain that the legacy store is deliberately never
        opened — prose asserting the separation, flagged as if it were the
        breach. Parsing and looking only at executable string literals and
        imports asks the question that was meant: does any code path name it?
        """
        import ast

        offenders = []
        needles = ("users.db", "sessions.json", "streamlit_auth")

        for path in (BACKEND_ROOT / "nanobio_studio").rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8",
                                                errors="ignore"))
            except SyntaxError:  # pragma: no cover
                continue

            # Docstrings are the module, class and function bodies' first
            # statement. Collect them so they can be excluded by identity.
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef,
                                     ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = getattr(node, "body", None)
                    if (body and isinstance(body[0], ast.Expr)
                            and isinstance(body[0].value, ast.Constant)
                            and isinstance(body[0].value.value, str)):
                        docstrings.add(id(body[0].value))

            for node in ast.walk(tree):
                if (isinstance(node, ast.Constant)
                        and isinstance(node.value, str)
                        and id(node) not in docstrings):
                    for needle in needles:
                        if needle in node.value:
                            offenders.append(f"{path.name}: {needle}")
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = getattr(node, "module", "") or ""
                    names = " ".join(a.name for a in node.names)
                    for needle in needles:
                        if needle in module or needle in names:
                            offenders.append(f"{path.name}: import {needle}")

        assert offenders == [], (
            f"the main application references the legacy authentication "
            f"store in executable code: {offenders}. The two systems must not "
            f"share accounts, sessions or secrets.")

    def test_the_separation_is_stated_in_the_modules_that_matter(self):
        """Positive control for the check above, and a claim in its own right.

        The two auth modules explain in prose that the legacy store is never
        opened. That prose is what the previous version of the test tripped
        over — so this asserts it is still there, which is what makes the
        parsed check meaningful rather than vacuous.
        """
        for name in ("db/auth_models.py", "db/auth_session.py"):
            text = (BACKEND_ROOT / "nanobio_studio" / "app" / name).read_text(
                encoding="utf-8")
            assert "users.db" in text, (
                f"{name} no longer explains its relationship to the legacy "
                f"store; the boundary should be documented where somebody "
                f"editing the schema will read it")

    def test_no_legacy_fallback_branch_exists_in_authentication(self):
        """The shape a "temporary compatibility" branch takes.

        A fallback that verifies against the legacy store when the main lookup
        fails would make every legacy account a live account here, with the
        legacy hashing and the legacy password policy.
        """
        for name in ("services/auth_service.py", "services/account_service.py",
                     "api/deps_auth.py", "core/passwords.py",
                     "core/security.py"):
            text = (BACKEND_ROOT / "nanobio_studio" / "app" / name).read_text(
                encoding="utf-8")
            lowered = text.lower()
            for needle in ("legacy_verify", "legacy_password", "legacy_token",
                           "fallback_auth", "users.db"):
                assert needle not in lowered, f"{name} contains {needle!r}"

    def test_the_session_cookie_name_is_not_a_legacy_one(self):
        """So a legacy cookie cannot be presented to this application by
        accident, and neither can the reverse."""
        assert SESSION_COOKIE_NAME == "nanobio_session"
        legacy_names = {"session", "session_id", "streamlit_session",
                        "auth_token", "user_token"}
        assert SESSION_COOKIE_NAME not in legacy_names

    def test_the_two_systems_share_no_signing_secret(self):
        """The main application signs nothing with a shared key.

        Its sessions are opaque random tokens compared against a stored digest
        — there is no signature to share. This asserts that, rather than
        asserting the keys differ, because "no shared secret" is a stronger
        property than "different secrets".
        """
        from nanobio_studio.app.core import security

        assert hasattr(security, "generate_session_token")
        source = (BACKEND_ROOT / "nanobio_studio" / "app" / "core"
                  / "security.py").read_text(encoding="utf-8")
        for needle in ("hmac.new", "jwt", "itsdangerous", "SECRET_KEY",
                       "secret_key"):
            assert needle not in source, (
                f"core/security.py references {needle!r}; a signed token would "
                f"introduce a key that could be shared with the legacy system")
