"""Async database engine and session factory for the authentication schema.

Temporary local arrangement (documented, not a second design)
------------------------------------------------------------
The intended production database is PostgreSQL. A PostgreSQL server is listening
locally on 5432 but no usable development credentials were available, so the
local default is a **SQLite file accessed through the same SQLAlchemy async
abstraction**. Nothing about the models, queries or session handling differs
between the two: only ``AUTH_DATABASE_URL`` changes.

    # local default (temporary)
    sqlite+aiosqlite:///./nanobio_auth_dev.db

    # production
    postgresql+asyncpg://user:password@host:5432/nanobio_studio

The legacy ``users.db`` is never opened by this module. It is a separate file and
migrating it is an explicit, manual, later step.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from nanobio_studio.app.db.base import Base

# Import the models so they are registered on Base.metadata before create_all.
# workspace_models declares foreign keys onto auth_users, so both must be
# registered before create_all runs or the FK targets are unresolved.
from nanobio_studio.app.db import auth_models  # noqa: F401
from nanobio_studio.app.db import workspace_models  # noqa: F401
from nanobio_studio.app.db import report_models  # noqa: F401

#: Repo root, used only to place the local development SQLite file.
_REPO_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_AUTH_DATABASE_URL = (
    f"sqlite+aiosqlite:///{(_REPO_ROOT / 'nanobio_auth_dev.db').as_posix()}"
)


def get_auth_database_url() -> str:
    """Resolve the auth database URL from the environment.

    Deliberately a separate setting from the LNP backend's ``database_url`` so
    that pointing one at PostgreSQL does not implicitly move the other.
    """
    return os.environ.get("AUTH_DATABASE_URL", DEFAULT_AUTH_DATABASE_URL)


def _make_engine(url: str):
    kwargs: dict = {"echo": False, "future": True}
    if not url.startswith("sqlite"):
        # Pooling options are meaningless (and rejected) for SQLite.
        kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=20)
    return create_async_engine(url, **kwargs)


engine = _make_engine(get_auth_database_url())

AuthSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


async def init_auth_db() -> None:
    """Create the auth tables if absent. Idempotent.

    Called explicitly from application startup -- never as an import side effect
    (see DEFECT-D11, where import-time database writes were removed from the
    legacy modules).

    For PostgreSQL this is a bootstrap convenience; Alembic migrations remain the
    intended mechanism for schema change and are a prerequisite for production.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # create_all builds missing TABLES but never alters an existing one, so a
    # database created before a column existed needs it added in place.
    # Additive only: nothing is dropped, renamed or retyped.
    from nanobio_studio.app.db.migrations import apply_additive_migrations

    applied = await apply_additive_migrations(engine)
    if applied:
        print(f"[nanobio] added missing columns: {', '.join(applied)}")


async def close_auth_db() -> None:
    await engine.dispose()


async def get_auth_session() -> AsyncSession:
    """FastAPI dependency yielding an auth database session."""
    async with AuthSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
