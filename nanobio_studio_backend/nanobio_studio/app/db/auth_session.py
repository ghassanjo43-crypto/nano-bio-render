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
from nanobio_studio.app.db import science_models  # noqa: F401
# Phase 2 registry. Registered here for the same reason as the others: its
# foreign keys target workspace_runs and auth_users, which must already be on
# the metadata when create_all resolves them.
from nanobio_studio.app.db import validation_models  # noqa: F401
# Records that depend on an exact candidate version — simulations, evidence
# assessments, reports, exports, CRO packages and filed comparisons. Every one
# of them carries a NOT NULL foreign key onto validation_candidate_versions,
# so that table has to be on the metadata before create_all resolves them.
from nanobio_studio.app.db import candidate_dependency_models  # noqa: F401

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
    from nanobio_studio.app.db.migrations import (
        apply_additive_migrations, tables_awaiting_creation,
    )

    # Asked BEFORE create_all, because create_all is what creates them. An
    # existing database gaining a new table is an upgrade worth showing in the
    # log rather than a silent schema change.
    pending = await tables_awaiting_creation(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if pending:
        print(f"[nanobio] created new tables: {', '.join(pending)}")

    # create_all builds missing TABLES but never alters an existing one, so a
    # database created before a column existed needs it added in place.
    # Additive only: nothing is dropped, renamed or retyped.
    applied = await apply_additive_migrations(engine)
    if applied:
        print(f"[nanobio] added missing columns: {', '.join(applied)}")

    # Indexes for the organization predicate that every scoped query now
    # carries. create_all only indexes tables it creates itself, so an
    # upgraded database would otherwise get the columns without them.
    from nanobio_studio.app.db.migrations import (
        check_organization_consistency, create_organization_indexes,
    )
    await create_organization_indexes(engine)

    # Claim pre-multi-tenancy rows for the legacy organization. A no-op once
    # there is nothing left unassigned, so this is safe on every startup.
    from nanobio_studio.app.db.organization_backfill import (
        backfill_organizations,
    )
    report = await backfill_organizations(engine)
    if not report.skipped:
        print(f"[nanobio] {report.summary()}")
        for note in report.notes:
            print(f"[nanobio] NOTE: {note}")
        print("[nanobio] The legacy organization is awaiting administrator "
              "confirmation. Scientific changes are blocked until its "
              "memberships are confirmed.")

    # Give every pre-existing candidate an initial version and bind the
    # records that depend on one. Additive and idempotent: it creates only
    # versions for candidates that have none and fills only columns that are
    # NULL, so a second startup reports zero work.
    #
    # Run here rather than left as a command because the invariant the rest of
    # the application relies on — every dependent record names an exact
    # version — is not true of an upgraded database until it has run, and a
    # migration somebody has to remember is one that gets forgotten.
    from nanobio_studio.app.db.legacy_candidate_migration import (
        migrate_legacy_candidates,
    )
    candidate_migration = await migrate_legacy_candidates(engine,
                                                          dry_run=False)
    if (candidate_migration.versions_created
            or candidate_migration.dependent_records_bound_total
            or candidate_migration.ambiguities
            or candidate_migration.integrity_findings):
        print(f"[nanobio] {candidate_migration.summary()}")
        for ambiguity in candidate_migration.ambiguities:
            print(f"[nanobio] AMBIGUITY {ambiguity.kind} "
                  f"({ambiguity.subject}): {ambiguity.detail} "
                  f"-> {ambiguity.resolution}")
        for finding in candidate_migration.integrity_findings:
            print(f"[nanobio] WARNING candidate integrity: {finding}")

    # Denormalising organization_id onto every table means it *can* disagree
    # with the record's parent. Say so at startup rather than discovering it
    # when a record turns up in the wrong workspace.
    problems = await check_organization_consistency(engine)
    if problems:
        detail = ", ".join(f"{k}={v}" for k, v in sorted(problems.items()))
        print(f"[nanobio] WARNING organization consistency: {detail}")


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
