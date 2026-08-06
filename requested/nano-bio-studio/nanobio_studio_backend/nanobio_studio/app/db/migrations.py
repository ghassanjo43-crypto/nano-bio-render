"""Additive schema migrations for existing development databases.

Why this exists
---------------
``Base.metadata.create_all`` creates missing *tables* but never alters an
existing one. A development database created before the study-pathway columns
existed would therefore keep working right up until the first query touched a
new column, and then fail with an opaque ``no such column`` error.

This module adds missing columns in place, idempotently, at startup. It is a
**deliberate interim measure**, not a replacement for Alembic:

* it only ever ADDS nullable or defaulted columns — it never drops, renames or
  retypes anything, so it cannot destroy data;
* it is idempotent, so running it repeatedly is safe;
* it records nothing and has no down-migration.

Proper Alembic migrations remain a prerequisite for production, and are tracked
as a known limitation in the workspace documentation. The honest reason this
exists is that the alternative — silently broken developer databases — is worse.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

__all__ = ["ADDITIVE_COLUMNS", "apply_additive_migrations"]


@dataclass(frozen=True)
class AddColumn:
    table: str
    column: str
    #: DDL type plus any default. Must be nullable or defaulted, so existing
    #: rows remain valid without a backfill.
    ddl: str
    #: Optional statement to give existing rows a sensible value.
    backfill: str | None = None


# SQLAlchemy's ``Enum(..., native_enum=False)`` persists the enum **member
# name**, not its value: a ``RecordOrigin.DEMO`` row holds the string 'DEMO',
# not 'demo'. Raw SQL written against the values therefore matches nothing and
# fails silently — which is exactly what an earlier version of this table did,
# leaving demonstration runs backfilled as research designs.
#
# So every literal below is a member NAME, and the origin comparison accepts
# both spellings in case a row was ever written by hand.
_IS_DEMO = "origin IN ('DEMO', 'demo')"

#: Every column added since the tables were first created.
ADDITIVE_COLUMNS: tuple[AddColumn, ...] = (
    AddColumn(
        table="workspace_runs", column="pathway",
        ddl="VARCHAR(32) NOT NULL DEFAULT 'RESEARCH_DESIGN'",
        # Runs stored before pathways existed: a demo-origin run was a
        # demonstration, everything else was a research design. That is what
        # they actually were, so this is a restatement rather than a guess.
        backfill=(
            "UPDATE workspace_runs SET pathway = "
            f"CASE WHEN {_IS_DEMO} THEN 'DEMO_SCENARIO' "
            "ELSE 'RESEARCH_DESIGN' END"
        ),
    ),
    AddColumn(table="workspace_runs", column="research_purpose",
              ddl="VARCHAR(80) NULL"),
    AddColumn(
        table="workspace_runs", column="inputs_are_synthetic",
        ddl="BOOLEAN NOT NULL DEFAULT 0",
        backfill=("UPDATE workspace_runs SET inputs_are_synthetic = 1 "
                  f"WHERE {_IS_DEMO}"),
    ),
    AddColumn(table="workspace_runs", column="report_assessment_id",
              ddl="INTEGER NULL"),
)

#: Repairs for rows an earlier, defective migration mislabelled.
#:
#: The first release of this module compared ``origin`` against the enum VALUE
#: ('demo') when the column holds the enum NAME ('DEMO'). The comparison matched
#: nothing, so demonstration runs were left marked as research designs. These
#: statements are idempotent and only ever move a row towards the truth: a run
#: whose origin says DEMO *is* a demonstration with synthetic inputs.
REPAIRS: tuple[tuple[str, str], ...] = (
    ("workspace_runs",
     f"UPDATE workspace_runs SET pathway = 'DEMO_SCENARIO' WHERE {_IS_DEMO} "
     "AND pathway <> 'DEMO_SCENARIO'"),
    ("workspace_runs",
     f"UPDATE workspace_runs SET inputs_are_synthetic = 1 WHERE {_IS_DEMO} "
     "AND inputs_are_synthetic = 0"),
)


async def _existing_columns(conn, table: str) -> set[str]:
    """Column names on ``table``, or an empty set when the table is absent."""
    dialect = conn.dialect.name
    if dialect == "sqlite":
        rows = await conn.execute(text(f"PRAGMA table_info({table})"))
        return {row[1] for row in rows}
    rows = await conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = :t"), {"t": table})
    return {row[0] for row in rows}


async def apply_additive_migrations(engine: AsyncEngine) -> list[str]:
    """Add any missing columns. Returns what it changed, for logging."""
    applied: list[str] = []

    async with engine.begin() as conn:
        for spec in ADDITIVE_COLUMNS:
            existing = await _existing_columns(conn, spec.table)
            if not existing:
                # Table absent: create_all will build it complete. Nothing to do.
                continue
            if spec.column in existing:
                continue

            await conn.execute(text(
                f"ALTER TABLE {spec.table} ADD COLUMN {spec.column} {spec.ddl}"))
            if spec.backfill:
                await conn.execute(text(spec.backfill))
            applied.append(f"{spec.table}.{spec.column}")

        # Repair rows the earlier, defective backfill mislabelled. Runs
        # unconditionally because a database migrated by that version has the
        # columns already and would otherwise never be corrected.
        for table, statement in REPAIRS:
            if not await _existing_columns(conn, table):
                continue
            result = await conn.execute(text(statement))
            if result.rowcount and result.rowcount > 0:
                applied.append(f"repaired {result.rowcount} row(s) in {table}")

    return applied
