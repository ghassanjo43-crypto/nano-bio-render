"""The schema changes organization management needs, and what they must not do.

An upgrade that breaks an existing installation
-----------------------------------------------
is worse than a feature that never shipped, because the data was already there
and the operator has already run the upgrade. So the claim under test is not
"the new columns exist" — `create_all` would satisfy that on a clean database
while an upgraded one failed on the first query. It is:

* an existing database gains the new columns **in place**, and
* every row it already held remains valid, and
* nothing that already existed is dropped, renamed or retyped.

The invitations table is new, so an upgrade adds it whole and an installation
that never issues an invitation is untouched by all of this.

The `revision` default deserves its own test
--------------------------------------------
`revision` is `NOT NULL DEFAULT 1` rather than nullable, and that is not a
style choice. Concurrency detection issues
``UPDATE … WHERE id = ? AND revision = ?``, and `NULL <> NULL` in SQL — so a
nullable revision would make *every* update on a pre-existing row match no row
and be refused as a phantom conflict. The administration screens would appear
to work on new members and silently refuse every change to an old one.
"""

from __future__ import annotations

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

from nanobio_studio.app.db.migrations import (  # noqa: E402
    ADDITIVE_COLUMNS, EXPECTED_TABLES, apply_additive_migrations,
)

from tests.conftest import run_async  # noqa: E402

#: Columns this milestone adds, and the table each belongs to.
NEW_COLUMNS = {
    ("organization_memberships", "revision"),
    ("study_assignments", "revision"),
    ("study_assignments", "may_download_attachments"),
    ("study_assignments", "note"),
}


def _metadata_with_every_model():
    """The declarative Base, with every model module imported.

    Importing one model module alone leaves foreign keys dangling — the
    invitation table points at ``auth_users`` and the assignment table at
    ``workspace_runs`` — and ``create_all`` then fails resolving them rather
    than building anything. Loading the whole set is also the honest scenario:
    a real installation has all of them.
    """
    import nanobio_studio.app.db.auth_models  # noqa: F401
    import nanobio_studio.app.db.organization_models  # noqa: F401
    import nanobio_studio.app.db.workspace_models  # noqa: F401
    from nanobio_studio.app.db.base import Base

    return Base


async def _columns(conn, table: str) -> set[str]:
    rows = await conn.execute(text(f"PRAGMA table_info({table})"))
    return {row[1] for row in rows}


class TestTheNewTableIsDeclared:

    def test_the_invitations_table_is_expected(self):
        assert "organization_invitations" in EXPECTED_TABLES

    def test_a_clean_database_builds_it_complete(self):
        async def scenario():
            Base = _metadata_with_every_model()
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                    columns = await _columns(conn, "organization_invitations")
                for required in ("organization_id", "email", "role", "status",
                                 "token_hash", "token_prefix", "expires_at",
                                 "membership_expires_at", "revision",
                                 "may_download_attachments", "accepted_at",
                                 "ended_at", "end_reason"):
                    assert required in columns, required
            finally:
                await engine.dispose()

        run_async(scenario())

    def test_the_partial_uniqueness_index_exists(self):
        """Two live invitations to one address is the state it prevents.

        Partial — `PENDING` only — so an address can be re-invited after a
        withdrawal, which a plain unique index would forbid forever.
        """
        async def scenario():
            Base = _metadata_with_every_model()
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                    rows = (await conn.execute(text(
                        "SELECT sql FROM sqlite_master WHERE type='index' "
                        "AND name='uq_org_invitation_pending'"
                    ))).scalars().all()
                assert rows, "uq_org_invitation_pending was not created"
                sql = rows[0].upper()
                assert "UNIQUE" in sql
                assert "WHERE" in sql, (
                    "the index is not partial, so a withdrawn invitation "
                    "would block the address permanently")
            finally:
                await engine.dispose()

        run_async(scenario())


class TestTheAdditiveColumnsAreSafe:

    @pytest.mark.parametrize("table,column", sorted(NEW_COLUMNS))
    def test_each_new_column_is_declared_for_migration(self, table, column):
        """`create_all` never ALTERs, so an upgrade needs these listed."""
        declared = {(c.table, c.column) for c in ADDITIVE_COLUMNS}
        assert (table, column) in declared, (
            f"{table}.{column} exists on the model but is not in "
            f"ADDITIVE_COLUMNS, so an existing database would never gain it "
            f"and would fail on the first query that touched it.")

    def test_the_revision_columns_are_defaulted_not_nullable(self):
        """`NULL <> NULL`, so a nullable revision refuses every update."""
        for spec in ADDITIVE_COLUMNS:
            if spec.column != "revision":
                continue
            ddl = spec.ddl.upper()
            assert "NOT NULL" in ddl, spec.table
            assert "DEFAULT 1" in ddl, (
                f"{spec.table}.revision has no default, so existing rows "
                f"would be NULL and every conditional update on them would "
                f"match no row and be refused as a phantom conflict.")

    def test_the_assignment_columns_are_nullable(self):
        """An existing assignment must remain valid without a backfill."""
        for spec in ADDITIVE_COLUMNS:
            if (spec.table, spec.column) not in NEW_COLUMNS:
                continue
            if spec.column == "revision":
                continue
            assert "NOT NULL" not in spec.ddl.upper(), (
                f"{spec.table}.{spec.column} is NOT NULL, so adding it would "
                f"invalidate every existing row.")
            assert spec.backfill is None, (
                f"{spec.table}.{spec.column} carries a blanket UPDATE. NULL "
                f"already means the right thing here — 'defer to the "
                f"membership' — and writing a value would state a restriction "
                f"nobody chose.")


class TestAnExistingDatabaseIsUpgradedInPlace:

    def test_the_columns_are_added_and_the_rows_survive(self):
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                # The tables as an installation from the previous milestone
                # has them: no revision, no per-assignment restriction.
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "CREATE TABLE organization_memberships ("
                        " id INTEGER PRIMARY KEY, organization_id INTEGER,"
                        " user_id INTEGER, role VARCHAR(32),"
                        " scope VARCHAR(32), status VARCHAR(32))"))
                    await conn.execute(text(
                        "CREATE TABLE study_assignments ("
                        " id INTEGER PRIMARY KEY, organization_id INTEGER,"
                        " study_id INTEGER, user_id INTEGER,"
                        " role VARCHAR(32), status VARCHAR(32))"))
                    await conn.execute(text(
                        "INSERT INTO organization_memberships"
                        " (id, organization_id, user_id, role, scope, status)"
                        " VALUES (1, 1, 1, 'OWNER', 'ORGANIZATION', 'ACTIVE')"))
                    await conn.execute(text(
                        "INSERT INTO study_assignments"
                        " (id, organization_id, study_id, user_id, role,"
                        "  status)"
                        " VALUES (1, 1, 5, 1, 'APPROVER', 'ACTIVE')"))

                applied = await apply_additive_migrations(engine)

                for table, column in sorted(NEW_COLUMNS):
                    assert f"{table}.{column}" in applied, (
                        f"{table}.{column} was not added")

                async with engine.begin() as conn:
                    membership = (await conn.execute(text(
                        "SELECT role, status, revision FROM "
                        "organization_memberships WHERE id = 1"))).one()
                    assignment = (await conn.execute(text(
                        "SELECT role, status, revision, "
                        "may_download_attachments, note "
                        "FROM study_assignments WHERE id = 1"))).one()

                # The rows are exactly as they were, plus a usable revision.
                assert tuple(membership) == ("OWNER", "ACTIVE", 1)
                assert assignment[0] == "APPROVER"
                assert assignment[1] == "ACTIVE"
                assert assignment[2] == 1, (
                    "an existing assignment must get revision 1, not NULL")
                assert assignment[3] is None, (
                    "NULL means 'defer to the membership', which is what this "
                    "assignment did before the column existed")
                assert assignment[4] is None
            finally:
                await engine.dispose()

        run_async(scenario())

    def test_running_it_twice_changes_nothing_the_second_time(self):
        """Idempotent, or an operator who reruns an upgrade loses a database."""
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "CREATE TABLE organization_memberships ("
                        " id INTEGER PRIMARY KEY, organization_id INTEGER,"
                        " user_id INTEGER, role VARCHAR(32),"
                        " scope VARCHAR(32), status VARCHAR(32))"))
                    await conn.execute(text(
                        "INSERT INTO organization_memberships"
                        " (id, organization_id, user_id, role, scope, status)"
                        " VALUES (1, 1, 1, 'OWNER', 'ORGANIZATION', 'ACTIVE')"))

                first = await apply_additive_migrations(engine)
                assert "organization_memberships.revision" in first, (
                    "positive control: the first run did the work")

                second = await apply_additive_migrations(engine)
                assert "organization_memberships.revision" not in second

                async with engine.begin() as conn:
                    row = (await conn.execute(text(
                        "SELECT role, revision FROM organization_memberships "
                        "WHERE id = 1"))).one()
                assert tuple(row) == ("OWNER", 1)
            finally:
                await engine.dispose()

        run_async(scenario())

    def test_an_absent_table_is_skipped_rather_than_created_by_alter(self):
        """A brand-new database gets its tables from `create_all`, whole."""
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                applied = await apply_additive_migrations(engine)
                assert applied == []
            finally:
                await engine.dispose()

        run_async(scenario())
