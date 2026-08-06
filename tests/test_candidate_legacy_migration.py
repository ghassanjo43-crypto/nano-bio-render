"""The legacy migration, on a fresh database and on an upgraded one.

What has to be true, and why each one is a separate test
--------------------------------------------------------
* **Every candidate ends up with a version.** That is the invariant the rest of
  the feature rests on: a dependent record cannot name an exact version if
  there is none to name.
* **Nothing is invented.** Where the formulation can be attributed — a study
  with exactly one candidate — the snapshot is a restatement of what the
  database already held. Where it cannot, the version is created with an
  **empty** snapshot and a note saying why, and the candidate appears in the
  ambiguity report. A snapshot copied from a study that had three candidates
  would be a fabricated attribution wearing a checksum, and a checksum is
  exactly what makes a fabrication hard to spot later.
* **Nothing is lost.** Row counts are read on both sides and every table except
  the versions table must be exactly the size it was.
* **Restart is safe.** A second run reports zero work and changes nothing.
* **Dry run changes nothing at all**, and reports the same plan the real run
  executes.
* **A fresh database is unaffected**, because there is nothing to migrate.

The upgraded-database cases are built by creating the schema and then removing
what an older release did not have, rather than by checking in an old SQLite
file. A fixture file would drift from the model silently; a database built from
the model and then aged is wrong in exactly the ways a real upgrade is.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Imported for their side effect: each registers its tables on the shared
# metadata, and `create_all` builds only what is registered. Without them the
# schema comes up missing `auth_users` and the seed fails with a message about
# a table rather than about the migration under test.
from nanobio_studio.app.db import auth_models  # noqa: F401,E402
from nanobio_studio.app.db import organization_models  # noqa: F401,E402
from nanobio_studio.app.db import validation_models  # noqa: F401,E402
from nanobio_studio.app.db import workspace_models  # noqa: F401,E402
from nanobio_studio.app.db.base import Base  # noqa: E402
from nanobio_studio.app.db.legacy_candidate_migration import (  # noqa: E402
    LEGACY_MIGRATION_NOTE, UNATTRIBUTABLE_NOTE, migrate_legacy_candidates,
    verify_candidate_version_bindings,
)

from tests.conftest import run_async  # noqa: E402

DESIGN = {"size_nm": 88.0, "charge_mv": -12.0, "coating": "PEG",
          "dose_mg_kg": 1.5}


async def _engine(tmp_path: Path, name: str):
    """A real file-backed database. Not in-memory.

    The migration opens more than one connection through ``engine.begin()`` and
    ``engine.connect()``; a ``:memory:`` database gives each connection its own
    empty schema, so a test against it would pass while proving nothing.
    """
    path = tmp_path / f"{name}.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path.as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def _seed_users_and_org(conn) -> None:
    await conn.execute(text(
        "INSERT INTO auth_users (id, username, email, password_hash, role, "
        "is_active, created_at) VALUES "
        "(1, 'author', 'a@x.invalid', 'x', 'RESEARCHER', 1, '2026-01-05')"))
    await conn.execute(text(
        "INSERT INTO organizations (id, slug, name, status, is_legacy, "
        "created_at) VALUES "
        "(1, 'legacy', 'Legacy workspace', 'ACTIVE', 1, '2026-01-05')"))


async def _seed_study(conn, study_id: int, design: dict | None,
                      *, name: str = "legacy study") -> None:
    await conn.execute(text(
        "INSERT INTO workspace_runs (id, organization_id, owner_id, name, "
        "origin, pathway, inputs_are_synthetic, status, design_inputs_json, "
        "engines_run, engines_not_run, created_at) VALUES "
        "(:id, 1, 1, :name, 'USER', 'RESEARCH_DESIGN', 0, 'COMPLETE', "
        ":design, '', '', '2026-01-06')"),
        {"id": study_id, "name": name,
         "design": json.dumps(design) if design is not None else None})


async def _seed_candidate(conn, candidate_id: int, study_id: int,
                          code: str) -> None:
    await conn.execute(text(
        "INSERT INTO validation_candidates (id, organization_id, study_id, "
        "owner_id, code, name, created_at, updated_at) VALUES "
        "(:id, 1, :study, 1, :code, :name, '2026-01-07', '2026-01-07')"),
        {"id": candidate_id, "study": study_id, "code": code,
         "name": f"Candidate {code}"})


async def _rows(engine, query: str) -> list:
    async with engine.connect() as conn:
        return (await conn.execute(text(query))).all()


async def _scalar(engine, query: str):
    async with engine.connect() as conn:
        return (await conn.execute(text(query))).scalar()


# ===========================================================================
# 1. A fresh database
# ===========================================================================

class TestFreshDatabase:

    def test_a_fresh_database_needs_no_migration(self, tmp_path):
        async def scenario():
            engine = await _engine(tmp_path, "fresh")
            try:
                report = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                return report
            finally:
                await engine.dispose()

        report = run_async(scenario())

        assert report.candidates_examined == 0
        assert report.candidates_migrated == 0
        assert report.versions_created == 0
        assert report.ambiguities == []
        assert report.failures == []
        assert report.counts_verified is True
        assert report.checksums_verified is True
        assert report.succeeded is True

    def test_a_fresh_database_reports_complete_bindings(self, tmp_path):
        async def scenario():
            engine = await _engine(tmp_path, "fresh_bindings")
            try:
                return await verify_candidate_version_bindings(engine)
            finally:
                await engine.dispose()

        result = run_async(scenario())
        assert result["complete"] is True
        assert result["versionless_candidates"] == 0


# ===========================================================================
# 2. An upgraded database: the attributable case
# ===========================================================================

class TestAttributableCandidate:
    """One study, one candidate, one set of design inputs.

    The only case in which the formulation can be attributed without guessing,
    and therefore the only one in which a snapshot is written.
    """

    async def _prepared(self, tmp_path, name="attributable"):
        engine = await _engine(tmp_path, name)
        async with engine.begin() as conn:
            await _seed_users_and_org(conn)
            await _seed_study(conn, 10, DESIGN)
            await _seed_candidate(conn, 100, 10, "CAND-A")
        return engine

    def test_the_dry_run_changes_nothing_and_states_the_plan(self, tmp_path):
        async def scenario():
            engine = await self._prepared(tmp_path, "attr_dry")
            try:
                report = await migrate_legacy_candidates(engine, dry_run=True)
                after = await _scalar(
                    engine,
                    "SELECT COUNT(*) FROM validation_candidate_versions")
                return report, after
            finally:
                await engine.dispose()

        report, after = run_async(scenario())

        assert report.dry_run is True
        assert report.candidates_examined == 1
        assert report.candidates_migrated == 1
        assert report.versions_created == 1
        assert report.versions_with_attributed_snapshot == 1
        assert report.versions_with_empty_snapshot == 0
        assert after == 0, "the dry run wrote a row"

    def test_the_real_run_creates_the_initial_version(self, tmp_path):
        async def scenario():
            engine = await self._prepared(tmp_path, "attr_real")
            try:
                report = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                rows = await _rows(engine, (
                    "SELECT candidate_id, version_number, revision_label, "
                    "status, results_state, design_snapshot_json, "
                    "snapshot_checksum, organization_id, note, created_at "
                    "FROM validation_candidate_versions"))
                return report, rows
            finally:
                await engine.dispose()

        report, rows = run_async(scenario())

        assert report.succeeded is True
        assert len(rows) == 1
        (candidate_id, number, label, status, results_state, snapshot,
         checksum, organization_id, note, created_at) = rows[0]

        assert candidate_id == 100
        assert number == 1
        assert label == "v1"
        # DRAFT: nothing has been shown to depend on it. The reliance boundary
        # locks it the first time something does.
        assert status == "DRAFT"
        # NONE, not CURRENT. No legacy row recorded whether its derived values
        # were computed for these inputs.
        assert results_state == "NONE"
        assert json.loads(snapshot) == DESIGN
        assert organization_id == 1, "the version did not inherit the org"
        assert note == LEGACY_MIGRATION_NOTE
        # The candidate's own creation time, not the migration's clock.
        assert str(created_at).startswith("2026-01-07")

        import hashlib
        assert checksum == hashlib.sha256(snapshot.encode()).hexdigest()

    def test_the_plan_and_the_run_agree(self, tmp_path):
        """A dry run that reported something different from what happened
        would be worse than no dry run at all."""
        async def scenario():
            engine = await self._prepared(tmp_path, "attr_agree")
            try:
                planned = await migrate_legacy_candidates(engine,
                                                          dry_run=True)
                applied = await migrate_legacy_candidates(engine,
                                                          dry_run=False)
                return planned, applied
            finally:
                await engine.dispose()

        planned, applied = run_async(scenario())

        for field in ("candidates_examined", "candidates_migrated",
                      "candidates_unchanged", "versions_created",
                      "versions_with_attributed_snapshot",
                      "versions_with_empty_snapshot"):
            assert getattr(planned, field) == getattr(applied, field), field
        assert ([a.kind for a in planned.ambiguities]
                == [a.kind for a in applied.ambiguities])

    def test_a_second_run_is_a_no_op(self, tmp_path):
        async def scenario():
            engine = await self._prepared(tmp_path, "attr_restart")
            try:
                first = await migrate_legacy_candidates(engine, dry_run=False)
                before = await _scalar(
                    engine,
                    "SELECT COUNT(*) FROM validation_candidate_versions")
                second = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                after = await _scalar(
                    engine,
                    "SELECT COUNT(*) FROM validation_candidate_versions")
                return first, second, before, after
            finally:
                await engine.dispose()

        first, second, before, after = run_async(scenario())

        assert first.versions_created == 1
        assert second.versions_created == 0
        assert second.candidates_migrated == 0
        assert second.candidates_unchanged == 1
        assert before == after == 1
        assert second.succeeded is True


# ===========================================================================
# 3. An upgraded database: the ambiguous cases
# ===========================================================================

class TestAmbiguityIsReportedNotGuessed:

    def test_a_study_with_several_candidates_is_reported(self, tmp_path):
        """One set of design inputs, three candidates. Nothing to attribute."""
        async def scenario():
            engine = await _engine(tmp_path, "ambiguous")
            async with engine.begin() as conn:
                await _seed_users_and_org(conn)
                await _seed_study(conn, 20, DESIGN)
                await _seed_candidate(conn, 200, 20, "CAND-A")
                await _seed_candidate(conn, 201, 20, "CAND-B")
                await _seed_candidate(conn, 202, 20, "CAND-C")
            try:
                report = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                rows = await _rows(engine, (
                    "SELECT candidate_id, design_snapshot_json, note "
                    "FROM validation_candidate_versions ORDER BY candidate_id"))
                return report, rows
            finally:
                await engine.dispose()

        report, rows = run_async(scenario())

        assert report.candidates_migrated == 3
        assert report.versions_with_attributed_snapshot == 0
        assert report.versions_with_empty_snapshot == 3
        assert len(report.ambiguities) == 3
        assert {a.kind for a in report.ambiguities} == {
            "study_has_several_candidates"}

        for ambiguity in report.ambiguities:
            assert "cannot be determined" in ambiguity.detail
            assert "Nothing was copied in" in ambiguity.resolution

        # Every candidate still got a version — the invariant holds — and not
        # one of them carries a formulation the migration could not attribute.
        assert len(rows) == 3
        for _candidate_id, snapshot, note in rows:
            assert json.loads(snapshot) == {}
            assert note == UNATTRIBUTABLE_NOTE

    def test_a_study_with_no_design_inputs_is_reported(self, tmp_path):
        async def scenario():
            engine = await _engine(tmp_path, "no_inputs")
            async with engine.begin() as conn:
                await _seed_users_and_org(conn)
                await _seed_study(conn, 30, None)
                await _seed_candidate(conn, 300, 30, "CAND-N")
            try:
                return await migrate_legacy_candidates(engine, dry_run=False)
            finally:
                await engine.dispose()

        report = run_async(scenario())

        assert report.versions_created == 1
        assert report.versions_with_empty_snapshot == 1
        assert [a.kind for a in report.ambiguities] == [
            "study_has_no_design_inputs"]

    def test_unreadable_design_inputs_are_reported_not_stored(self, tmp_path):
        async def scenario():
            engine = await _engine(tmp_path, "unreadable")
            async with engine.begin() as conn:
                await _seed_users_and_org(conn)
                await conn.execute(text(
                    "INSERT INTO workspace_runs (id, organization_id, "
                    "owner_id, name, origin, pathway, inputs_are_synthetic, "
                    "status, design_inputs_json, engines_run, "
                    "engines_not_run, created_at) VALUES "
                    "(40, 1, 1, 'broken', 'USER', 'RESEARCH_DESIGN', 0, "
                    "'COMPLETE', '{not json', '', '', '2026-01-06')"))
                await _seed_candidate(conn, 400, 40, "CAND-BROKEN")
            try:
                report = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                snapshot = await _scalar(engine, (
                    "SELECT design_snapshot_json FROM "
                    "validation_candidate_versions"))
                return report, snapshot
            finally:
                await engine.dispose()

        report, snapshot = run_async(scenario())

        assert [a.kind for a in report.ambiguities] == [
            "unreadable_study_inputs"]
        assert json.loads(snapshot) == {}, (
            "unparseable text reached a snapshot")

    def test_every_ambiguity_says_what_was_done(self, tmp_path):
        """A list of problems with no stated outcome is a list of things to
        worry about, not a record of what happened."""
        async def scenario():
            engine = await _engine(tmp_path, "ambiguity_shape")
            async with engine.begin() as conn:
                await _seed_users_and_org(conn)
                await _seed_study(conn, 50, DESIGN)
                await _seed_candidate(conn, 500, 50, "CAND-X")
                await _seed_candidate(conn, 501, 50, "CAND-Y")
            try:
                return await migrate_legacy_candidates(engine, dry_run=False)
            finally:
                await engine.dispose()

        report = run_async(scenario())
        assert report.ambiguities

        for ambiguity in report.ambiguities:
            assert ambiguity.kind and " " not in ambiguity.kind
            assert ambiguity.subject.strip()
            assert len(ambiguity.detail) > 30
            assert len(ambiguity.resolution) > 20
            assert set(ambiguity.as_dict()) == {
                "kind", "subject", "detail", "resolution"}


# ===========================================================================
# 4. Dependent records are bound deterministically
# ===========================================================================

class TestDependentRecordsAreBound:

    async def _with_experiment(self, tmp_path, name):
        engine = await _engine(tmp_path, name)
        async with engine.begin() as conn:
            await _seed_users_and_org(conn)
            await _seed_study(conn, 60, DESIGN)
            await _seed_candidate(conn, 600, 60, "CAND-E")
            snapshot = json.dumps(DESIGN, sort_keys=True,
                                  separators=(",", ":"))
            import hashlib
            await conn.execute(text(
                "INSERT INTO validation_candidate_versions "
                "(id, organization_id, candidate_id, version_number, "
                " revision_label, design_snapshot_json, snapshot_checksum, "
                " status, results_state, supersession_state, revision, "
                " created_at) VALUES "
                "(6000, 1, 600, 1, 'v1', :snap, :sum, 'DRAFT', 'NONE', "
                " 'NONE', 1, '2026-01-08')"),
                {"snap": snapshot,
                 "sum": hashlib.sha256(snapshot.encode()).hexdigest()})
            await conn.execute(text(
                "INSERT INTO validation_experiments (id, organization_id, "
                "code, candidate_id, study_id, owner_id, subtype, purpose, "
                "title, created_at, updated_at) VALUES "
                "(700, 1, 'EXP-1', 600, 60, 1, 'PARTICLE_SIZE_PDI', "
                "'STRUCTURAL_VISUALIZATION', 'Size', '2026-01-09', "
                "'2026-01-09')"))
            await conn.execute(text(
                "INSERT INTO validation_experiment_versions "
                "(id, organization_id, experiment_id, version_number, "
                " candidate_version_id, status, disclosures_confirmed, "
                " created_at, updated_at) VALUES "
                "(7000, 1, 700, 1, 6000, 'DRAFT', 0, '2026-01-09', "
                "'2026-01-09')"))
            # An attachment written before the binding column existed.
            await conn.execute(text(
                "INSERT INTO validation_attachments (id, organization_id, "
                "version_id, candidate_version_id, category, "
                "original_filename, mime_type, size_bytes, checksum_sha256, "
                "storage_key, state, delete_attempts, uploaded_at) VALUES "
                "(8000, 1, 7000, NULL, 'RAW_DATA', 'trace.csv', 'text/csv', "
                "64, :sum, 'k/8000', 'AVAILABLE', 0, '2026-01-10')"),
                {"sum": "0" * 64})
            # Audit rows: one naming a version, one naming an experiment.
            await conn.execute(text(
                "INSERT INTO validation_audit_log (id, organization_id, "
                "event, actor_id, experiment_id, experiment_version_id, "
                "candidate_version_id, candidate_id, summary, created_at) "
                "VALUES "
                "(9000, 1, 'VERSION_CREATED', 1, NULL, NULL, 6000, NULL, "
                " 'v1 created', '2026-01-08'), "
                "(9001, 1, 'CREATED', 1, 700, 7000, NULL, NULL, "
                " 'EXP-1 created', '2026-01-09')"))
        return engine

    def test_attachments_take_the_version_their_experiment_names(self,
                                                                 tmp_path):
        async def scenario():
            engine = await self._with_experiment(tmp_path, "bind_attach")
            try:
                report = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                bound = await _scalar(engine, (
                    "SELECT candidate_version_id FROM validation_attachments "
                    "WHERE id = 8000"))
                return report, bound
            finally:
                await engine.dispose()

        report, bound = run_async(scenario())

        assert bound == 6000
        assert report.dependent_records_bound["validation_attachments"] == 1
        assert report.ambiguities == []

    def test_audit_rows_take_the_candidate_they_can_reach(self, tmp_path):
        async def scenario():
            engine = await self._with_experiment(tmp_path, "bind_audit")
            try:
                report = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                rows = await _rows(engine, (
                    "SELECT id, candidate_id FROM validation_audit_log "
                    "ORDER BY id"))
                return report, rows
            finally:
                await engine.dispose()

        report, rows = run_async(scenario())

        assert dict(rows) == {9000: 600, 9001: 600}
        assert report.dependent_records_bound["validation_audit_log"] == 2

    def test_the_dry_run_binds_nothing(self, tmp_path):
        async def scenario():
            engine = await self._with_experiment(tmp_path, "bind_dry")
            try:
                report = await migrate_legacy_candidates(engine, dry_run=True)
                bound = await _scalar(engine, (
                    "SELECT candidate_version_id FROM validation_attachments "
                    "WHERE id = 8000"))
                return report, bound
            finally:
                await engine.dispose()

        report, bound = run_async(scenario())

        assert report.dependent_records_bound["validation_attachments"] == 1
        assert bound is None, "the dry run wrote a binding"

    def test_verification_reports_the_gap_before_and_closure_after(self,
                                                                   tmp_path):
        async def scenario():
            engine = await self._with_experiment(tmp_path, "bind_verify")
            try:
                before = await verify_candidate_version_bindings(engine)
                await migrate_legacy_candidates(engine, dry_run=False)
                after = await verify_candidate_version_bindings(engine)
                return before, after
            finally:
                await engine.dispose()

        before, after = run_async(scenario())

        assert before["complete"] is False
        assert before["unbound"]["validation_attachments"
                                 ".candidate_version_id"] == 1
        assert after["complete"] is True
        assert not any(after["unbound"].values())

    def test_a_conflicting_audit_row_is_reported_not_resolved(self, tmp_path):
        """Choosing a side would edit the trail, which is the one record that
        has to say what it said."""
        async def scenario():
            engine = await self._with_experiment(tmp_path, "bind_conflict")
            async with engine.begin() as conn:
                # A second candidate, and an audit row naming this version
                # alongside the other candidate's experiment.
                await _seed_candidate(conn, 601, 60, "CAND-F")
                await conn.execute(text(
                    "INSERT INTO validation_experiments (id, "
                    "organization_id, code, candidate_id, study_id, owner_id, "
                    "subtype, purpose, title, created_at, updated_at) VALUES "
                    "(701, 1, 'EXP-2', 601, 60, 1, 'ZETA_POTENTIAL', "
                    "'FORMULATION_ASSESSMENT', 'Zeta', '2026-01-09', "
                    "'2026-01-09')"))
                await conn.execute(text(
                    "INSERT INTO validation_audit_log (id, organization_id, "
                    "event, actor_id, experiment_id, candidate_version_id, "
                    "candidate_id, summary, created_at) VALUES "
                    "(9002, 1, 'ACCESSED', 1, 701, 6000, NULL, 'conflict', "
                    " '2026-01-11')"))
            try:
                report = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                conflicted = await _scalar(engine, (
                    "SELECT candidate_id FROM validation_audit_log "
                    "WHERE id = 9002"))
                return report, conflicted
            finally:
                await engine.dispose()

        report, conflicted = run_async(scenario())

        assert conflicted is None, "the migration picked a side"
        assert "audit_row_names_two_candidates" in {
            a.kind for a in report.ambiguities}


# ===========================================================================
# 5. Verification: counts and checksums
# ===========================================================================

class TestVerification:

    def test_row_counts_are_read_on_both_sides(self, tmp_path):
        async def scenario():
            engine = await _engine(tmp_path, "counts")
            async with engine.begin() as conn:
                await _seed_users_and_org(conn)
                await _seed_study(conn, 70, DESIGN)
                await _seed_candidate(conn, 700, 70, "CAND-C1")
            try:
                return await migrate_legacy_candidates(engine, dry_run=False)
            finally:
                await engine.dispose()

        report = run_async(scenario())

        assert report.source_counts["validation_candidates"] == 1
        assert report.source_counts["validation_candidate_versions"] == 0
        assert report.destination_counts["validation_candidate_versions"] == 1
        # Nothing else moved.
        for table, before in report.source_counts.items():
            if table == "validation_candidate_versions":
                continue
            assert report.destination_counts[table] == before, table
        assert report.counts_verified is True

    def test_a_preexisting_checksum_mismatch_is_a_finding_not_a_failure(
            self, tmp_path):
        """Aborting on pre-existing damage would make this migration unusable
        on exactly the databases that most need repairing."""
        async def scenario():
            engine = await _engine(tmp_path, "bad_checksum")
            async with engine.begin() as conn:
                await _seed_users_and_org(conn)
                await _seed_study(conn, 80, DESIGN)
                await _seed_candidate(conn, 800, 80, "CAND-BAD")
                await conn.execute(text(
                    "INSERT INTO validation_candidate_versions "
                    "(id, organization_id, candidate_id, version_number, "
                    " revision_label, design_snapshot_json, "
                    " snapshot_checksum, status, results_state, "
                    " supersession_state, revision, created_at) VALUES "
                    "(8000, 1, 800, 1, 'v1', :snap, "
                    " 'deadbeef', 'DRAFT', 'NONE', 'NONE', 1, '2026-01-08')"),
                    {"snap": '{"size_nm":88}'})
            try:
                return await migrate_legacy_candidates(engine, dry_run=False)
            finally:
                await engine.dispose()

        report = run_async(scenario())

        assert report.failures == []
        assert report.checksums_verified is True
        assert len(report.integrity_findings) == 1
        finding = report.integrity_findings[0]
        assert "did not write them" in finding
        assert "should be investigated" in finding

    def test_every_written_checksum_matches_its_snapshot(self, tmp_path):
        async def scenario():
            engine = await _engine(tmp_path, "written_checksums")
            async with engine.begin() as conn:
                await _seed_users_and_org(conn)
                for index in range(5):
                    await _seed_study(conn, 90 + index,
                                      {**DESIGN, "size_nm": 80 + index})
                    await _seed_candidate(conn, 900 + index, 90 + index,
                                          f"CAND-{index}")
            try:
                report = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                rows = await _rows(engine, (
                    "SELECT design_snapshot_json, snapshot_checksum "
                    "FROM validation_candidate_versions"))
                return report, rows
            finally:
                await engine.dispose()

        report, rows = run_async(scenario())

        import hashlib
        assert report.versions_created == 5
        assert report.checksums_verified is True
        for snapshot, checksum in rows:
            assert hashlib.sha256(snapshot.encode()).hexdigest() == checksum

    def test_the_report_serialises_every_count_the_brief_asks_for(self,
                                                                  tmp_path):
        async def scenario():
            engine = await _engine(tmp_path, "report_shape")
            async with engine.begin() as conn:
                await _seed_users_and_org(conn)
                await _seed_study(conn, 110, DESIGN)
                await _seed_candidate(conn, 1100, 110, "CAND-R1")
                await _seed_candidate(conn, 1101, 110, "CAND-R2")
            try:
                return await migrate_legacy_candidates(engine, dry_run=False)
            finally:
                await engine.dispose()

        report = run_async(scenario())
        payload = report.as_dict()

        for key in ("candidates_migrated", "dependent_records_bound_total",
                    "ambiguity_count", "failure_count",
                    "candidates_unchanged", "integrity_finding_count",
                    "source_counts", "destination_counts",
                    "counts_verified", "checksums_verified", "succeeded"):
            assert key in payload, key

        summary = report.summary()
        for phrase in ("candidate(s) examined", "migrated", "unchanged",
                       "dependent record(s) bound", "ambiguity(ies)",
                       "failure(s)"):
            assert phrase in summary, phrase


# ===========================================================================
# 6. An upgraded database missing the newer columns
# ===========================================================================

class TestUpgradedSchema:
    """A database built from an older release, aged by removing the columns
    that release did not have — then migrated forward the way a real upgrade
    does: additive columns first, then this migration.
    """

    async def _aged(self, tmp_path, name):
        engine = await _engine(tmp_path, name)
        async with engine.begin() as conn:
            await _seed_users_and_org(conn)
            await _seed_study(conn, 120, DESIGN)
            await _seed_candidate(conn, 1200, 120, "CAND-OLD")
            # Age the schema: remove the three binding columns this milestone
            # added.
            #
            # `validation_attachments.candidate_version_id` is a foreign key,
            # and SQLite refuses DROP COLUMN on one — so the table is rebuilt
            # by copy, which is what the old schema was anyway: an aged
            # database is precisely one with fewer columns and fewer
            # constraints. The audit-log columns carry no key and drop
            # directly.
            columns = [c[1] for c in (await conn.execute(text(
                "PRAGMA table_info(validation_attachments)"))).all()
                if c[1] != "candidate_version_id"]
            listed = ", ".join(columns)
            await conn.execute(text(
                f"CREATE TABLE validation_attachments__old AS "
                f"SELECT {listed} FROM validation_attachments"))
            await conn.execute(text("DROP TABLE validation_attachments"))
            await conn.execute(text(
                "ALTER TABLE validation_attachments__old "
                "RENAME TO validation_attachments"))

            # `candidate_id` is indexed, and SQLite refuses DROP COLUMN on an
            # indexed column too. Dropping the index first is exactly what an
            # older release would not have had.
            await conn.execute(text(
                "DROP INDEX IF EXISTS ix_validation_audit_log_candidate_id"))
            await conn.execute(text(
                "ALTER TABLE validation_audit_log DROP COLUMN candidate_id"))
            await conn.execute(text(
                "ALTER TABLE validation_audit_log DROP COLUMN reason"))
        return engine

    def test_the_migration_says_what_is_missing_rather_than_failing(self,
                                                                    tmp_path):
        async def scenario():
            engine = await self._aged(tmp_path, "aged_note")
            try:
                return await migrate_legacy_candidates(engine, dry_run=False)
            finally:
                await engine.dispose()

        report = run_async(scenario())

        assert report.failures == []
        notes = " ".join(report.verification_notes)
        assert "candidate_version_id is absent" in notes
        assert "run the additive migration first" in notes
        # The part it CAN do, it does.
        assert report.versions_created == 1

    def test_the_full_upgrade_path_ends_complete(self, tmp_path):
        """Additive columns, then this migration. The order a real startup
        uses, asserted rather than assumed."""
        from nanobio_studio.app.db.migrations import apply_additive_migrations

        async def scenario():
            engine = await self._aged(tmp_path, "aged_full")
            try:
                applied = await apply_additive_migrations(engine)
                report = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                bindings = await verify_candidate_version_bindings(engine)
                return applied, report, bindings
            finally:
                await engine.dispose()

        applied, report, bindings = run_async(scenario())

        assert "validation_attachments.candidate_version_id" in applied
        assert "validation_audit_log.candidate_id" in applied
        assert "validation_audit_log.reason" in applied
        assert report.succeeded is True
        assert bindings["complete"] is True

    def test_a_candidate_with_versions_already_is_left_alone(self, tmp_path):
        async def scenario():
            engine = await _engine(tmp_path, "already_versioned")
            import hashlib
            snapshot = json.dumps(DESIGN, sort_keys=True,
                                  separators=(",", ":"))
            async with engine.begin() as conn:
                await _seed_users_and_org(conn)
                await _seed_study(conn, 130, DESIGN)
                await _seed_candidate(conn, 1300, 130, "CAND-HAS")
                await conn.execute(text(
                    "INSERT INTO validation_candidate_versions "
                    "(id, organization_id, candidate_id, version_number, "
                    " revision_label, design_snapshot_json, "
                    " snapshot_checksum, status, results_state, "
                    " supersession_state, revision, created_at, note, "
                    " locked_at) VALUES "
                    "(13000, 1, 1300, 1, 'v1', :snap, :sum, 'APPROVED', "
                    " 'CURRENT', 'NONE', 3, '2026-01-08', 'original', "
                    " '2026-01-09')"),
                    {"snap": snapshot,
                     "sum": hashlib.sha256(snapshot.encode()).hexdigest()})
            try:
                report = await migrate_legacy_candidates(engine,
                                                         dry_run=False)
                row = (await _rows(engine, (
                    "SELECT status, results_state, revision, note "
                    "FROM validation_candidate_versions WHERE id = 13000")))[0]
                return report, row
            finally:
                await engine.dispose()

        report, row = run_async(scenario())

        assert report.candidates_migrated == 0
        assert report.candidates_unchanged == 1
        assert row == ("APPROVED", "CURRENT", 3, "original"), (
            "an existing version was modified")
