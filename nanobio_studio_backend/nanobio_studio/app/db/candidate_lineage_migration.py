"""Bring an upgraded database's candidate-version constraints up to the model.

The problem this exists for
---------------------------
`ADDITIVE_COLUMNS` can add a column to an existing table. It cannot add a CHECK
constraint, because SQLite has no `ALTER TABLE ... ADD CONSTRAINT` — and adding
one is not something the additive migration was ever designed to do.

The effect is quiet and bad. A database created fresh from the model gets every
lineage constraint. A database *upgraded* from an earlier release gets the new
columns and **none of the constraints**. Both then report the same schema
version and the same column list, and only one of them actually refuses a
version that is its own predecessor, or a row claiming SUPERSEDED with no
successor.

That is exactly the situation the brief rules out: relying on application code
for lineage integrity. The service does check these things, but the service is
one writer among several — a repair script, an import, a future migration — and
the constraint is what makes the guarantee hold for all of them.

What this does
--------------
`verify_lineage_constraints` reports which constraints the live table actually
has, so the gap is visible rather than assumed.

`rebuild_candidate_versions` performs the standard SQLite table rebuild —
create-with-constraints, copy, drop, rename — inside one transaction with
foreign keys deferred. It is idempotent: a table that already carries the
constraints is left alone.

Why a rebuild is safe *here* specifically
-----------------------------------------
Rebuilding a table is normally something to avoid, and the reasons it is
acceptable for this one are worth stating rather than assuming:

* the copy is a pure `INSERT ... SELECT` of the same columns — no
  transformation, so there is nothing to get wrong per row;
* the data is verified **before** the old table is dropped, and the whole thing
  runs in one transaction, so a failure leaves the original in place;
* the row count and every checksum are compared afterwards, so a silent
  truncation fails loudly instead of being discovered later.

Rollback limitation, stated plainly: once the rebuilt table carries the
constraints, a database that has since written rows relying on them cannot be
downgraded to the old schema without those rows being re-validated by hand. The
rebuild is reversible in structure and not in guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

__all__ = [
    "REQUIRED_CONSTRAINTS", "LineageConstraintReport",
    "verify_lineage_constraints", "rebuild_candidate_versions",
]

TABLE = "validation_candidate_versions"

#: The constraints the model declares, by name. Read from the model rather than
#: restated here would be better — but the model's names are what end up in the
#: DDL, and this list is what the *live table* is checked against, so keeping it
#: explicit makes a mismatch visible instead of tautological.
REQUIRED_CONSTRAINTS = (
    "ck_candidate_version_not_own_predecessor",
    "ck_candidate_version_not_own_successor",
    "ck_candidate_version_number_positive",
    "ck_candidate_version_supersession_complete",
    "ck_candidate_version_locked_has_timestamp",
)


@dataclass(frozen=True)
class LineageConstraintReport:
    present: tuple[str, ...]
    missing: tuple[str, ...]
    table_exists: bool
    dialect: str

    @property
    def complete(self) -> bool:
        return self.table_exists and not self.missing

    def as_dict(self) -> dict:
        return {
            "table": TABLE,
            "dialect": self.dialect,
            "table_exists": self.table_exists,
            "constraints_present": list(self.present),
            "constraints_missing": list(self.missing),
            "complete": self.complete,
            "note": (
                "Lineage integrity is enforced by the database."
                if self.complete else
                "Lineage integrity is currently enforced by application code "
                "only. A writer that bypasses the service — a repair script, "
                "an import, a future migration — could create a self-"
                "referencing or half-superseded version. Run "
                "rebuild_candidate_versions() to close the gap."),
        }


async def verify_lineage_constraints(engine: AsyncEngine
                                     ) -> LineageConstraintReport:
    """Report which lineage constraints the live table actually carries."""
    dialect = engine.dialect.name

    async with engine.connect() as conn:
        if dialect == "sqlite":
            row = (await conn.execute(text(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"
            ), {"n": TABLE})).first()
            if row is None or not row[0]:
                return LineageConstraintReport((), REQUIRED_CONSTRAINTS,
                                               False, dialect)
            ddl = row[0]
            present = tuple(name for name in REQUIRED_CONSTRAINTS
                            if name in ddl)
        else:
            rows = (await conn.execute(text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = :n"), {"n": TABLE})).all()
            found = {r[0] for r in rows}
            if not found:
                return LineageConstraintReport((), REQUIRED_CONSTRAINTS,
                                               False, dialect)
            present = tuple(name for name in REQUIRED_CONSTRAINTS
                            if name in found)

    missing = tuple(name for name in REQUIRED_CONSTRAINTS
                    if name not in present)
    return LineageConstraintReport(present, missing, True, dialect)


async def rebuild_candidate_versions(engine: AsyncEngine, *,
                                     dry_run: bool = True) -> dict:
    """Rebuild the table so it carries the lineage constraints.

    Idempotent, and a no-op on any dialect that supports adding constraints
    directly — the rebuild is a SQLite workaround, not a general strategy.

    Defaults to ``dry_run=True``. Every destructive tool in this codebase does,
    for the same reason: the person running it should see the plan before the
    plan runs.
    """
    report = await verify_lineage_constraints(engine)

    if not report.table_exists:
        return {"rebuilt": False, "reason": "table does not exist",
                **report.as_dict()}
    if report.complete:
        return {"rebuilt": False, "reason": "constraints already present",
                **report.as_dict()}
    if report.dialect != "sqlite":
        return {
            "rebuilt": False,
            "reason": ("this dialect supports ALTER TABLE ADD CONSTRAINT; add "
                       "the constraints directly rather than rebuilding"),
            **report.as_dict()}

    # Every table this one points at must be in the metadata, or compiling
    # its DDL raises NoReferencedTableError on the first foreign key. Importing
    # the modules is what registers them; naming them here rather than relying
    # on import order elsewhere keeps the rebuild self-contained.
    from nanobio_studio.app.db import auth_models  # noqa: F401
    from nanobio_studio.app.db import organization_models  # noqa: F401
    from nanobio_studio.app.db.validation_models import CandidateVersion

    columns = [c.name for c in CandidateVersion.__table__.columns]
    column_list = ", ".join(f'"{c}"' for c in columns)

    async with engine.begin() as conn:
        before = (await conn.execute(
            text(f"SELECT COUNT(*) FROM {TABLE}"))).scalar_one()

        if dry_run:
            return {
                "rebuilt": False, "dry_run": True, "rows": before,
                "would_add": list(report.missing),
                "plan": [
                    f"CREATE TABLE {TABLE}__rebuilt (… with constraints)",
                    f"INSERT INTO {TABLE}__rebuilt SELECT {column_list} "
                    f"FROM {TABLE}",
                    "verify row count and checksums",
                    f"DROP TABLE {TABLE}",
                    f"ALTER TABLE {TABLE}__rebuilt RENAME TO {TABLE}",
                    "recreate indexes",
                ],
                **report.as_dict()}

        # Foreign keys are deferred for the swap: the table references itself
        # (predecessor and successor), so dropping it with FKs enforced would
        # fail on its own rows.
        await conn.execute(text("PRAGMA defer_foreign_keys = ON"))

        staging = f"{TABLE}__rebuilt"
        await conn.execute(text(f"DROP TABLE IF EXISTS {staging}"))

        create_sql = _create_table_sql(
            CandidateVersion.__table__, staging, engine.dialect)
        await conn.execute(text(create_sql))

        await conn.execute(text(
            f"INSERT INTO {staging} ({column_list}) "
            f"SELECT {column_list} FROM {TABLE}"))

        # Verify BEFORE dropping. A truncated copy that is discovered after the
        # original is gone is not a migration, it is data loss with a log line.
        after = (await conn.execute(
            text(f"SELECT COUNT(*) FROM {staging}"))).scalar_one()
        if after != before:
            raise RuntimeError(
                f"refusing to swap: {before} rows in {TABLE} but {after} in "
                f"the rebuilt copy. The original is untouched.")

        original_sum = (await conn.execute(text(
            f"SELECT group_concat(snapshot_checksum) FROM "
            f"(SELECT snapshot_checksum FROM {TABLE} ORDER BY id)"))).scalar()
        copied_sum = (await conn.execute(text(
            f"SELECT group_concat(snapshot_checksum) FROM "
            f"(SELECT snapshot_checksum FROM {staging} ORDER BY id)"))).scalar()
        if original_sum != copied_sum:
            raise RuntimeError(
                "refusing to swap: the copied snapshots do not match the "
                "originals. The original is untouched.")

        await conn.execute(text(f"DROP TABLE {TABLE}"))
        await conn.execute(text(f"ALTER TABLE {staging} RENAME TO {TABLE}"))

        for index in CandidateVersion.__table__.indexes:
            cols = ", ".join(f'"{c.name}"' for c in index.columns)
            unique = "UNIQUE " if index.unique else ""
            await conn.execute(text(
                f"CREATE {unique}INDEX IF NOT EXISTS {index.name} "
                f"ON {TABLE} ({cols})"))

    final = await verify_lineage_constraints(engine)
    return {"rebuilt": True, "dry_run": False, "rows": before,
            "added": list(report.missing), **final.as_dict()}


def _create_table_sql(table, name: str, dialect) -> str:
    """Render the model's CREATE TABLE, under a staging name.

    Compiled from the declarative metadata rather than written out here, so the
    rebuilt table is by construction the one the model describes — including
    every constraint. Hand-written DDL would be one edit away from a rebuilt
    table that silently differs from the model it is supposed to restore.
    """
    from sqlalchemy.schema import CreateTable

    statement = str(CreateTable(table).compile(dialect=dialect))
    return statement.replace(f"CREATE TABLE {table.name}",
                             f"CREATE TABLE {name}", 1)
