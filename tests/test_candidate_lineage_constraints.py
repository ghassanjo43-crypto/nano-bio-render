"""The lineage constraints must exist on an UPGRADED database, not just a new one.

The gap this closes
-------------------
`ADDITIVE_COLUMNS` adds columns. It cannot add a CHECK constraint, because
SQLite has no `ALTER TABLE ... ADD CONSTRAINT`. So a database created fresh from
the model carried all five lineage constraints and a database upgraded from an
earlier release carried none — while reporting the same column list.

That is the failure mode the brief names directly: lineage integrity resting on
application code. The service checks these things, but the service is one
writer among several, and the constraint is what makes the guarantee hold for
the repair script nobody has written yet.

These tests use a real upgraded SQLite file rather than the model's metadata,
because the model always looks correct — it is the thing the constraints are
declared on. Only the live table can answer whether they arrived.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.db.candidate_lineage_migration import (  # noqa: E402
    REQUIRED_CONSTRAINTS, rebuild_candidate_versions,
    verify_lineage_constraints,
)

from tests.conftest import run_async  # noqa: E402


#: The table as an earlier release created it: the original nine columns, the
#: twenty added by ADDITIVE_COLUMNS, and no CHECK constraint anywhere. This is
#: what a real upgraded database looks like, which is the whole point.
LEGACY_TABLE = """
CREATE TABLE validation_candidate_versions (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER,
    candidate_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    design_snapshot_json TEXT NOT NULL,
    snapshot_checksum VARCHAR(64) NOT NULL,
    note TEXT,
    created_by INTEGER,
    created_at TIMESTAMP NOT NULL,
    predecessor_version_id INTEGER,
    revision_reason TEXT,
    revision_label VARCHAR(32),
    status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
    locked_at TIMESTAMP,
    lock_reason VARCHAR(200),
    results_state VARCHAR(16) NOT NULL DEFAULT 'NONE',
    results_inherited_from_id INTEGER,
    model_version VARCHAR(64),
    ruleset_version VARCHAR(64),
    reference_data_version VARCHAR(64),
    algorithm_selection VARCHAR(120),
    supersession_state VARCHAR(16) NOT NULL DEFAULT 'NONE',
    superseded_by_version_id INTEGER,
    superseded_at TIMESTAMP,
    superseded_by_user_id INTEGER,
    supersession_reason TEXT,
    supersession_decision_id INTEGER,
    revision INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT uq_candidate_version UNIQUE (candidate_id, version_number)
)
"""


async def _seed(engine, rows: int = 3) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(LEGACY_TABLE))
        for index in range(1, rows + 1):
            await conn.execute(text(
                "INSERT INTO validation_candidate_versions "
                "(id, organization_id, candidate_id, version_number, "
                " design_snapshot_json, snapshot_checksum, created_at, status,"
                " results_state, supersession_state, revision) "
                "VALUES (:id, 1, 1, :n, :snap, :sum, '2026-08-01 09:00:00', "
                "'DRAFT', 'NONE', 'NONE', 1)"),
                {"id": index, "n": index,
                 "snap": f'{{"size_nm":{90 + index}}}',
                 "sum": f"checksum-{index:04d}"})


@pytest.fixture
def upgraded(tmp_path):
    """A database that has been upgraded, not created fresh."""
    path = tmp_path / "upgraded.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    run_async(_seed(engine))
    yield engine
    run_async(engine.dispose())


# ===========================================================================
# 1. The gap is detectable
# ===========================================================================

class TestTheGapIsVisible:

    def test_an_upgraded_table_is_reported_as_missing_every_constraint(
            self, upgraded):
        report = run_async(verify_lineage_constraints(upgraded))

        assert report.table_exists is True
        assert report.complete is False
        assert set(report.missing) == set(REQUIRED_CONSTRAINTS)

    def test_the_report_says_what_the_consequence_is(self, upgraded):
        """A report that only lists names leaves the reader to work out
        whether it matters."""
        detail = run_async(verify_lineage_constraints(upgraded)).as_dict()

        assert detail["complete"] is False
        assert "application code" in detail["note"]
        assert "rebuild_candidate_versions" in detail["note"]

    def test_an_upgraded_table_really_does_accept_a_self_predecessor(
            self, upgraded):
        """The concrete harm, demonstrated rather than asserted.

        Without the constraint the database will happily store a version whose
        predecessor is itself — which makes any lineage walk non-terminating
        and any provenance claim circular.
        """
        async def insert_bad():
            async with upgraded.begin() as conn:
                await conn.execute(text(
                    "UPDATE validation_candidate_versions "
                    "SET predecessor_version_id = id WHERE id = 1"))
                return (await conn.execute(text(
                    "SELECT predecessor_version_id FROM "
                    "validation_candidate_versions WHERE id = 1"))).scalar()

        assert run_async(insert_bad()) == 1, (
            "the upgraded table refused a self-predecessor, so the gap this "
            "file exists for is already closed")


# ===========================================================================
# 2. The rebuild closes it
# ===========================================================================

class TestTheRebuild:

    def test_a_dry_run_changes_nothing_and_shows_the_plan(self, upgraded):
        """Default-dry-run, like every other destructive tool here."""
        result = run_async(rebuild_candidate_versions(upgraded))

        assert result["rebuilt"] is False
        assert result["dry_run"] is True
        assert result["rows"] == 3
        assert set(result["would_add"]) == set(REQUIRED_CONSTRAINTS)
        assert any("CREATE TABLE" in step for step in result["plan"])

        still_missing = run_async(verify_lineage_constraints(upgraded))
        assert still_missing.complete is False

    def test_the_rebuild_adds_every_constraint(self, upgraded):
        result = run_async(rebuild_candidate_versions(upgraded, dry_run=False))

        assert result["rebuilt"] is True
        assert result["complete"] is True
        assert result["constraints_missing"] == []

    def test_the_rebuild_preserves_every_row_and_checksum(self, upgraded):
        """The assertion that makes the rebuild trustworthy.

        A migration that adds constraints and loses a row has not improved
        anything.
        """
        async def read():
            async with upgraded.connect() as conn:
                rows = (await conn.execute(text(
                    "SELECT id, version_number, snapshot_checksum, "
                    "design_snapshot_json FROM validation_candidate_versions "
                    "ORDER BY id"))).all()
                return [tuple(r) for r in rows]

        before = run_async(read())
        run_async(rebuild_candidate_versions(upgraded, dry_run=False))
        after = run_async(read())

        assert before == after, "the rebuild altered the data it copied"
        assert len(after) == 3

    def test_the_rebuilt_table_actually_refuses_a_self_predecessor(self,
                                                                   upgraded):
        """The point of the whole exercise, proved against the live table."""
        run_async(rebuild_candidate_versions(upgraded, dry_run=False))

        async def insert_bad():
            async with upgraded.begin() as conn:
                await conn.execute(text(
                    "UPDATE validation_candidate_versions "
                    "SET predecessor_version_id = id WHERE id = 1"))

        with pytest.raises(IntegrityError):
            run_async(insert_bad())

    def test_the_rebuilt_table_refuses_a_half_written_supersession(self,
                                                                   upgraded):
        """A row claiming SUPERSEDED with no successor is a half-made decision
        about which version to use, which is worse than no decision."""
        run_async(rebuild_candidate_versions(upgraded, dry_run=False))

        async def insert_bad():
            async with upgraded.begin() as conn:
                await conn.execute(text(
                    "UPDATE validation_candidate_versions "
                    "SET status = 'SUPERSEDED' WHERE id = 1"))

        with pytest.raises(IntegrityError):
            run_async(insert_bad())

    def test_the_rebuilt_table_refuses_a_zero_version_number(self, upgraded):
        run_async(rebuild_candidate_versions(upgraded, dry_run=False))

        async def insert_bad():
            async with upgraded.begin() as conn:
                await conn.execute(text(
                    "UPDATE validation_candidate_versions "
                    "SET version_number = 0 WHERE id = 1"))

        with pytest.raises(IntegrityError):
            run_async(insert_bad())

    def test_the_rebuilt_table_still_accepts_legitimate_writes(self, upgraded):
        """Positive control.

        A rebuild that produced a table refusing everything would pass every
        assertion above.
        """
        run_async(rebuild_candidate_versions(upgraded, dry_run=False))

        async def insert_good():
            async with upgraded.begin() as conn:
                await conn.execute(text(
                    "UPDATE validation_candidate_versions "
                    "SET predecessor_version_id = 1 WHERE id = 2"))
                await conn.execute(text(
                    "INSERT INTO validation_candidate_versions "
                    "(organization_id, candidate_id, version_number, "
                    " design_snapshot_json, snapshot_checksum, created_at, "
                    " status, results_state, supersession_state, revision, "
                    " predecessor_version_id) "
                    "VALUES (1, 1, 4, '{}', 'checksum-0004', "
                    "'2026-08-02 09:00:00', 'DRAFT', 'NONE', 'NONE', 1, 3)"))
                return (await conn.execute(text(
                    "SELECT COUNT(*) FROM validation_candidate_versions"
                ))).scalar()

        assert run_async(insert_good()) == 4

    def test_the_rebuild_is_idempotent(self, upgraded):
        run_async(rebuild_candidate_versions(upgraded, dry_run=False))
        second = run_async(rebuild_candidate_versions(upgraded, dry_run=False))

        assert second["rebuilt"] is False
        assert second["reason"] == "constraints already present"

    def test_the_rebuild_recreates_the_indexes(self, upgraded):
        """Dropping and renaming a table takes its indexes with it.

        A rebuilt table that is correct and unindexed is a correctness fix that
        ships a performance regression.
        """
        run_async(rebuild_candidate_versions(upgraded, dry_run=False))

        async def read_indexes():
            async with upgraded.connect() as conn:
                rows = (await conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='validation_candidate_versions'"))).all()
                return {r[0] for r in rows}

        indexes = run_async(read_indexes())
        assert "ix_candidate_version_predecessor" in indexes
        assert "ix_candidate_version_status" in indexes

    def test_the_unique_constraint_survives_the_rebuild(self, upgraded):
        run_async(rebuild_candidate_versions(upgraded, dry_run=False))

        async def insert_duplicate():
            async with upgraded.begin() as conn:
                await conn.execute(text(
                    "INSERT INTO validation_candidate_versions "
                    "(organization_id, candidate_id, version_number, "
                    " design_snapshot_json, snapshot_checksum, created_at, "
                    " status, results_state, supersession_state, revision) "
                    "VALUES (1, 1, 1, '{}', 'dupe', '2026-08-02 09:00:00', "
                    "'DRAFT', 'NONE', 'NONE', 1)"))

        with pytest.raises(IntegrityError):
            run_async(insert_duplicate())


# ===========================================================================
# 3. A fresh database already has them
# ===========================================================================

class TestAFreshDatabase:

    def test_the_model_declares_every_required_constraint(self):
        """So the two halves cannot drift: what the rebuild installs is what
        the model says, by construction."""
        from nanobio_studio.app.db.validation_models import CandidateVersion

        declared = {c.name for c in CandidateVersion.__table__.constraints
                    if c.name}
        for name in REQUIRED_CONSTRAINTS:
            assert name in declared, (
                f"{name} is required by the migration but not declared on the "
                f"model, so a fresh database would not have it")
