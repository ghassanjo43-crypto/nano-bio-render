"""The unified study record: pathway, purpose and the additive migration.

What these tests protect
------------------------
1. A study records **how it began** and keeps saying so. The three pathways are
   distinguishable in storage, not inferred later from a route or a name.
2. ``origin`` keeps its old two-value meaning, because ``reset_demo_data``
   scopes its deletion on it. Adding ``pathway`` must not weaken that.
3. The additive migration is genuinely idempotent and genuinely additive: it
   adds missing columns, leaves existing rows intact, and running it twice
   changes nothing the second time.

Nothing here touches a scientific calculation. These are storage and
information-architecture tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
# Repo root first: the backend ships its own `tests` package which would
# otherwise shadow this suite's conftest.
for _p in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if _p in sys.path:
        sys.path.remove(_p)
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker,
    create_async_engine,
)

from tests.conftest import run_async  # noqa: E402

from nanobio_studio.app.db.base import Base  # noqa: E402
# Importing the model modules registers every table on Base.metadata.
# workspace_runs declares a foreign key onto auth_users, so both must be
# registered before create_all or the FK target is unresolvable.
from nanobio_studio.app.db import auth_models  # noqa: E402,F401
from nanobio_studio.app.db import report_models  # noqa: E402,F401
from nanobio_studio.app.db import workspace_models  # noqa: E402,F401
from nanobio_studio.app.db.migrations import (  # noqa: E402
    ADDITIVE_COLUMNS,
    REPAIRS,
    apply_additive_migrations,
)
from nanobio_studio.app.db.workspace_models import (  # noqa: E402
    RecordOrigin,
    RunStatus,
    StudyPathway,
)
from nanobio_studio.app.services import workspace_service as svc  # noqa: E402

DESIGN_INPUTS = {"size_nm": 100, "charge_mv": -5, "encapsulation_percent": 85}
DESIGN_RESULT = {"score_version": "design-impact-adapter-0.1.0",
                 "design_impact_score": {"delivery": 87.5}}


async def _fresh_db():
    """An in-memory database with the current schema and one owner row."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    session = maker()
    # A row must exist for the owner foreign key. Inserted directly rather than
    # through the auth API, which is not what these tests are about.
    await session.execute(text(
        "INSERT INTO auth_users (id, username, email, password_hash, "
        "role, is_active, created_at) VALUES "
        "(1, 'u', 'u@x.test', 'x', 'researcher', 1, '2026-08-01')"))
    await session.commit()
    return engine, session


async def _create(session, **kwargs):
    defaults = dict(
        owner_id=1, name="Study", disease=None, subtype=None, drug=None,
        design_inputs=DESIGN_INPUTS, pk_inputs=None,
        design_result=DESIGN_RESULT, pk_result=None,
        engines_not_run=[], project_id=None, is_demo=False,
        demo_scenario_slug=None, demo_fixture_version=None,
    )
    defaults.update(kwargs)
    run = await svc.create_run(session, **defaults)
    await session.commit()
    return run


# =========================================================================
class TestPathwayIsRecorded:

    def test_each_pathway_round_trips(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                for pathway in StudyPathway:
                    run = await _create(session, pathway=pathway,
                                        name=f"study-{pathway.value}")
                    assert run.pathway is pathway

                runs, total = await svc.list_runs(session, owner_id=1)
                assert total == 3
                assert {r.pathway for r in runs} == set(StudyPathway)
                # The summary the API returns carries it too, as a plain string.
                assert {svc.run_to_summary(r)["pathway"] for r in runs} == {
                    "patient_assessment", "research_design", "demo_scenario"}
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_defaults_to_research_design(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                # An unspecified pathway is a research design: that is what a
                # study with no report and no scenario actually is.
                run = await _create(session)
                assert run.pathway is StudyPathway.RESEARCH_DESIGN
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_research_purpose_is_stored_verbatim(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _create(session,
                                    pathway=StudyPathway.RESEARCH_DESIGN,
                                    research_purpose="targeting_ligand")
                assert run.research_purpose == "targeting_ligand"
                assert (svc.run_to_summary(run)["research_purpose"]
                        == "targeting_ligand")
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_report_link_is_an_opaque_id_only(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _create(session,
                                    pathway=StudyPathway.PATIENT_ASSESSMENT,
                                    report_assessment_id=42)
                assert run.report_assessment_id == 42
                summary = svc.run_to_summary(run)
                assert summary["report_assessment_id"] == 42
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_the_record_has_no_field_for_an_identifier(self):
        """A structural guarantee, not a runtime check.

        There is no column on the study that could hold a patient name, date of
        birth or medical record number, so no code path can put one there.
        """
        from nanobio_studio.app.db.workspace_models import StoredRun

        columns = {c.name for c in StoredRun.__table__.columns}
        for banned in ("patient_name", "patient_id", "date_of_birth", "dob",
                       "mrn", "medical_record_number", "nhs_number",
                       "report_text", "document_text"):
            assert banned not in columns


# =========================================================================
class TestOriginStillMeansWhatItMeant:
    """`reset_demo_data` scopes deletion on `origin`. That must keep working."""

    def test_demo_pathway_forces_demo_origin(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                # The caller claims it is not a demo; the pathway says it is.
                # The pathway wins, or a demonstration could escape the reset.
                run = await _create(session,
                                    pathway=StudyPathway.DEMO_SCENARIO,
                                    is_demo=False)
                assert run.origin is RecordOrigin.DEMO
                assert run.inputs_are_synthetic is True
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_user_pathways_are_user_origin(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                for pathway in (StudyPathway.PATIENT_ASSESSMENT,
                                StudyPathway.RESEARCH_DESIGN):
                    run = await _create(session, pathway=pathway,
                                        name=pathway.value)
                    assert run.origin is RecordOrigin.USER
                    assert run.inputs_are_synthetic is False
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_demo_origin_alone_still_marks_a_demo_run(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                # The old call shape, with no pathway. It must still produce a
                # demo record, or the reset command would stop finding these.
                run = await _create(session, is_demo=True,
                                    demo_scenario_slug="liver-hcc-galnac",
                                    demo_fixture_version="demo-scenarios-1.0.0")
                assert run.origin is RecordOrigin.DEMO
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())


# =========================================================================
class TestFiltering:

    def test_filters_by_pathway(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                await _create(session, pathway=StudyPathway.PATIENT_ASSESSMENT,
                              name="a")
                await _create(session, pathway=StudyPathway.RESEARCH_DESIGN,
                              name="b")
                await _create(session, pathway=StudyPathway.RESEARCH_DESIGN,
                              name="c")
                await _create(session, pathway=StudyPathway.DEMO_SCENARIO,
                              name="d")

                runs, total = await svc.list_runs(
                    session, owner_id=1, pathway=StudyPathway.RESEARCH_DESIGN)
                assert total == 2
                assert {r.name for r in runs} == {"b", "c"}

                _, all_total = await svc.list_runs(session, owner_id=1)
                assert all_total == 4
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_pathway_filter_respects_ownership(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                await _create(session, pathway=StudyPathway.RESEARCH_DESIGN,
                              name="mine")
                runs, total = await svc.list_runs(
                    session, owner_id=999,
                    pathway=StudyPathway.RESEARCH_DESIGN)
                assert total == 0
                assert runs == []
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())


# =========================================================================
class TestInvariantsSurvive:
    """The pathway columns must not weaken the existing storage invariants."""

    def test_result_without_inputs_is_still_refused(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                with pytest.raises(svc.WorkspaceError) as exc:
                    await _create(session,
                                  pathway=StudyPathway.PATIENT_ASSESSMENT,
                                  design_inputs=None,
                                  design_result=DESIGN_RESULT)
                assert exc.value.code == "inputs_required"
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_engines_run_is_still_derived_not_trusted(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _create(session,
                                    pathway=StudyPathway.PATIENT_ASSESSMENT,
                                    design_result=None, design_inputs=None)
                assert run.engines_run == ""
                assert run.status is RunStatus.BLOCKED
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())


# =========================================================================
class TestAdditiveMigration:

    def test_enum_storage_spelling_is_the_member_name(self):
        """The assumption the migration literals depend on.

        ``Enum(..., native_enum=False)`` persists the member NAME, not the
        value. An earlier migration compared against the value, matched nothing,
        and silently mislabelled every demonstration run. This test pins the
        actual storage format so that regression cannot recur unnoticed.
        """
        async def scenario():
            engine, session = await _fresh_db()
            try:
                await _create(session, pathway=StudyPathway.DEMO_SCENARIO)
                raw = (await session.execute(text(
                    "SELECT origin, pathway FROM workspace_runs"))).all()
                assert tuple(raw[0]) == ("DEMO", "DEMO_SCENARIO")
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_migration_literals_match_the_storage_spelling(self):
        """Every enum literal the migration writes must be a member NAME.

        The lowercase VALUES are what the defective version used. Their absence
        is the assertion that matters.
        """
        pathway_spec = next(c for c in ADDITIVE_COLUMNS if c.column == "pathway")
        assert "RESEARCH_DESIGN" in pathway_spec.ddl
        assert "DEMO_SCENARIO" in pathway_spec.backfill
        for value in (p.value for p in StudyPathway):
            assert f"'{value}'" not in pathway_spec.ddl
            assert f"'{value}'" not in pathway_spec.backfill

    def test_adds_missing_columns_to_a_legacy_table(self):
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                # Build the table WITHOUT the new columns, as an older database
                # has it — using the spelling SQLAlchemy genuinely writes, not
                # an assumed one.
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "CREATE TABLE workspace_runs ("
                        " id INTEGER PRIMARY KEY, owner_id INTEGER,"
                        " name VARCHAR(200), origin VARCHAR(16),"
                        " status VARCHAR(16))"))
                    await conn.execute(text(
                        "INSERT INTO workspace_runs"
                        " (id, owner_id, name, origin, status) VALUES"
                        " (1, 1, 'old user run', 'USER', 'COMPLETE'),"
                        " (2, 1, 'old demo run', 'DEMO', 'COMPLETE')"))

                applied = await apply_additive_migrations(engine)
                for column in ADDITIVE_COLUMNS:
                    assert f"workspace_runs.{column.column}" in applied

                async with engine.begin() as conn:
                    rows = (await conn.execute(text(
                        "SELECT name, origin, pathway, inputs_are_synthetic "
                        "FROM workspace_runs ORDER BY id"))).all()

                # Existing rows survive, backfilled with what they actually
                # were rather than with a guess.
                assert tuple(rows[0]) == ("old user run", "USER",
                                          "RESEARCH_DESIGN", 0)
                assert tuple(rows[1]) == ("old demo run", "DEMO",
                                          "DEMO_SCENARIO", 1)
            finally:
                await engine.dispose()

        run_async(scenario())

    def test_repairs_rows_the_defective_migration_mislabelled(self):
        """The exact damage the first version of this module caused."""
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                # A database already migrated by the DEFECTIVE version: the
                # columns exist, but the demo run was left as a research design.
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "CREATE TABLE workspace_runs ("
                        " id INTEGER PRIMARY KEY, owner_id INTEGER,"
                        " name VARCHAR(200), origin VARCHAR(16),"
                        " status VARCHAR(16), pathway VARCHAR(32),"
                        " research_purpose VARCHAR(80),"
                        " inputs_are_synthetic BOOLEAN,"
                        " report_assessment_id INTEGER)"))
                    await conn.execute(text(
                        "INSERT INTO workspace_runs (id, owner_id, name, origin,"
                        " status, pathway, inputs_are_synthetic) VALUES"
                        " (1, 1, 'demo run', 'DEMO', 'COMPLETE',"
                        "  'RESEARCH_DESIGN', 0),"
                        " (2, 1, 'my run', 'USER', 'COMPLETE',"
                        "  'RESEARCH_DESIGN', 0)"))

                applied = await apply_additive_migrations(engine)
                assert any("repaired" in a for a in applied)

                async with engine.begin() as conn:
                    rows = (await conn.execute(text(
                        "SELECT name, pathway, inputs_are_synthetic "
                        "FROM workspace_runs ORDER BY id"))).all()

                # The demonstration is relabelled; genuine user work is not.
                assert tuple(rows[0]) == ("demo run", "DEMO_SCENARIO", 1)
                assert tuple(rows[1]) == ("my run", "RESEARCH_DESIGN", 0)

                # And the repair is idempotent.
                assert not any("repaired" in a for a in
                               await apply_additive_migrations(engine))
            finally:
                await engine.dispose()

        run_async(scenario())

    def test_repairs_never_touch_user_work(self):
        # A structural assertion: every repair is scoped to demo-origin rows.
        for _table, statement in REPAIRS:
            assert "origin IN ('DEMO', 'demo')" in statement
            assert statement.strip().upper().startswith("UPDATE")

    def test_is_idempotent(self):
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "CREATE TABLE workspace_runs ("
                        " id INTEGER PRIMARY KEY, owner_id INTEGER,"
                        " name VARCHAR(200), origin VARCHAR(16),"
                        " status VARCHAR(16))"))

                first = await apply_additive_migrations(engine)
                second = await apply_additive_migrations(engine)
                third = await apply_additive_migrations(engine)

                assert first          # something was added
                assert second == []   # and nothing thereafter
                assert third == []
            finally:
                await engine.dispose()

        run_async(scenario())

    def test_does_nothing_when_the_table_is_absent(self):
        async def scenario():
            # create_all will build it complete; the migration must not try to
            # ALTER a table that does not exist.
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                assert await apply_additive_migrations(engine) == []
            finally:
                await engine.dispose()

        run_async(scenario())

    def test_current_schema_needs_no_migration(self):
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                assert await apply_additive_migrations(engine) == []
            finally:
                await engine.dispose()

        run_async(scenario())

    def test_never_drops_or_renames(self):
        # A structural assertion on the migration table itself: every entry is
        # an ADD. There is no mechanism here that can destroy data.
        for spec in ADDITIVE_COLUMNS:
            assert "DROP" not in spec.ddl.upper()
            assert "RENAME" not in spec.ddl.upper()
            if spec.backfill:
                assert spec.backfill.strip().upper().startswith("UPDATE")
