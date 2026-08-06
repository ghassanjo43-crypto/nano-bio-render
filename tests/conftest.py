"""Shared pytest fixtures for NanoBio Studio.

Safety contract for this test suite
-----------------------------------
No test may read, write, create or delete a real application database.
The legacy code hard-codes relative SQLite paths (``users.db``,
``trial_registry.db``, ``nano_bio.db``, ...) resolved against the *current
working directory*, so an accidental import can silently create or mutate a real
database file. Three defences are applied here:

1. ``isolated_db_dir`` gives tests a throwaway directory.
2. ``patch_legacy_db_paths`` redirects every module-level DB path constant we
   know about at that directory.
3. ``repo_db_snapshot`` records the repository's real ``*.db`` files at session
   start so ``test_no_real_database_was_touched`` can prove nothing changed.

Modules with import-time database side effects -- DO NOT import these in tests
-----------------------------------------------------------------------------
Merely importing these creates or mutates a real database in the current working
directory, before any fixture gets the chance to redirect a path:

* ``auth.py``               -- ``init_db()`` at line 88 (and, before containment,
                               ``_reset_admin_session()`` at line 171)
* ``design_persistence.py`` -- ``init_design_db()`` at line 568, which creates
                               ``nano_bio.db`` (~36 KB) on a bare import

Monkeypatching cannot help, because the damage is done during the import
statement. The only safe approach is not to import them. Both are recorded as
DEFECT-D11 in the golden-vector baseline.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Every relative SQLite filename the legacy application can create.
LEGACY_DB_FILENAMES = (
    "users.db",
    "trial_registry.db",
    "nano_bio.db",
    "ml_module.db",
    "app.db",
    "nanobio_studio.db",
    "nanoparticles_disease_tagged.db",
)


def _snapshot_databases(root: Path) -> dict[str, str | None]:
    """Map db filename -> sha256 of contents, or None when absent."""
    snap: dict[str, str | None] = {}
    for name in LEGACY_DB_FILENAMES:
        p = root / name
        if p.exists():
            snap[name] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            snap[name] = None
    return snap


# Taken at conftest IMPORT time, not inside a fixture. A lazily-evaluated
# fixture is useless here: it would snapshot *after* a leak had already occurred
# and report a false pass. This module is imported before any test or plugin
# collects, so this is the earliest observation point available.
_DB_SNAPSHOT_AT_SESSION_START = _snapshot_databases(REPO_ROOT)


@pytest.fixture(scope="session")
def repo_db_snapshot() -> dict[str, str | None]:
    """Hashes of the real databases captured at conftest import time."""
    return dict(_DB_SNAPSHOT_AT_SESSION_START)


@pytest.fixture
def isolated_db_dir(tmp_path: Path) -> Path:
    """A throwaway directory for any test that needs a real SQLite file."""
    d = tmp_path / "isolated_dbs"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Isolated authentication backend
# ---------------------------------------------------------------------------


def make_isolated_auth_client(tmp_dir: Path):
    """Build a TestClient whose auth database is a throwaway SQLite file.

    Uses FastAPI ``dependency_overrides`` rather than reloading modules through
    ``sys.modules``. An earlier version did the latter and broke when two test
    modules ran in the same session: the re-imported engine pointed at a new
    database while already-cached route modules still held the previous session
    factory, producing ``no such table: auth_users``. Overriding the dependency
    is order-independent and leaves module state untouched.

    Returns ``(app, client, session_factory)``. The caller is responsible for
    closing the client (use it as a context manager).
    """
    import asyncio

    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                        create_async_engine)

    backend_root = REPO_ROOT / "nanobio_studio_backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from nanobio_studio.app.db.auth_session import get_auth_session
    from nanobio_studio.app.db.base import Base
    from nanobio_studio.app.vertical_slice import app

    db_path = tmp_dir / "isolated_auth.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}", future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession,
                                 expire_on_commit=False, autoflush=False)

    async def _create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_create_tables())
    finally:
        loop.close()

    async def _override():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_auth_session] = _override
    client = TestClient(app)
    return app, client, factory


def run_async(coro):
    """Run a coroutine on a fresh event loop (test helper)."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def patch_legacy_db_paths(isolated_db_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect known module-level DB path constants into a temp directory.

    Only patches modules that are safe to import, i.e. those without import-time
    database side effects. ``design_persistence`` is deliberately NOT imported
    here: its import creates ``nano_bio.db`` in the repository root before any
    patch can apply (DEFECT-D11). Redirecting it requires either refactoring the
    module or importing it under a changed working directory, which belongs to
    the migration phase, not to this harness.

    Returns the directory so a test can inspect what was created.
    """
    import modules.trial_registry as trial_registry

    monkeypatch.setattr(trial_registry, "DB_PATH",
                        isolated_db_dir / "trial_registry.db", raising=True)

    return isolated_db_dir


def ensure_default_organization(factory):
    """Enrol a test fixture's seeded users into the default organization.

    Production does this at startup: ``backfill_organizations`` runs from
    ``init_auth_db`` and enrols any account that belongs to no organization.
    Tests seed their users *after* the client is built, so they have to ask
    for it explicitly at the point their seeding finishes.

    Calling the real backfill rather than inserting memberships by hand is
    deliberate — a fixture that hand-rolled its own memberships could drift
    from what a real installation produces, and then the suite would be
    testing an arrangement no deployment has.
    """
    from nanobio_studio.app.db.organization_backfill import (
        backfill_organizations,
    )

    return run_async(backfill_organizations(factory.kw["bind"]))
