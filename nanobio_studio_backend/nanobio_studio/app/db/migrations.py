"""Additive schema migrations for existing development databases.

Why this exists
---------------
``Base.metadata.create_all`` creates missing *tables* but never alters an
existing one. A development database created before the study-pathway columns
existed would therefore keep working right up until the first query touched a
new column, and then fail with an opaque ``no such column`` error.

This module adds missing columns in place, idempotently, at startup. It is a
**deliberate interim measure**, not a replacement for Alembic:

* it only ever ADDS nullable or defaulted columns â€” it never drops, renames or
  retypes anything, so it cannot destroy data;
* it is idempotent, so running it repeatedly is safe;
* it records nothing and has no down-migration.

Proper Alembic migrations remain a prerequisite for production, and are tracked
as a known limitation in the workspace documentation. The honest reason this
exists is that the alternative â€” silently broken developer databases â€” is worse.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

__all__ = ["ADDITIVE_COLUMNS", "EXPECTED_TABLES", "REPAIRS",
           "ORGANIZATION_SCOPED_TABLES", "apply_additive_migrations",
           "check_organization_consistency", "create_organization_indexes",
           "tables_awaiting_creation"]

#: Tables introduced after the first release. `create_all` builds any missing
#: table, so these need no ALTER â€” they are listed so startup can report which
#: ones an upgrade is about to add, and so a test can assert they exist.
EXPECTED_TABLES: tuple[str, ...] = (
    "science_data_records",
    "science_readiness_snapshots",
    # Phase 2, Milestone 1 â€” the Experimental Validation Registry.
    #
    # All new tables, no ALTER on any Phase 1 table: an upgraded installation
    # keeps every project, study, candidate and account exactly as it was, and
    # a Phase 1 rollback simply ignores these.
    "validation_candidates",
    "validation_candidate_versions",
    "validation_experiments",
    "validation_experiment_versions",
    "validation_measurements",
    "validation_attachments",
    "validation_audit_log",
    "validation_contradiction_resolutions",
    # Phase 2, Production Hardening â€” organizations and workspace isolation.
    #
    # Again all new tables. The ALTERs that accompany them are in
    # ORGANIZATION_COLUMNS below and add one nullable column per table, so an
    # existing installation keeps every row it had.
    "organizations",
    "organization_memberships",
    "study_assignments",
    "organization_audit_log",
    "notifications",
    "notification_audit_log",
    # Phase 2, Production Hardening â€” organization management.
    #
    # Invitations are a new table rather than a new membership status, so an
    # installation that never issues one is completely unaffected: no existing
    # row changes, and no access query reads it.
    "organization_invitations",
    # Phase 2, Production Hardening â€” account and session hardening.
    #
    # A new table for activation and reset tokens. Nothing existing changes
    # shape; an installation that never issues one is unaffected.
    "auth_account_tokens",
    # Phase 2, Candidate Revision and Supersession â€” records that depend on an
    # exact candidate version.
    #
    # All new tables again. Each carries a NOT NULL candidate_version_id, which
    # is why they are new tables rather than columns on existing ones: SQLite
    # cannot add a NOT NULL column without a default to a populated table, and
    # no default is correct for "which formulation was this about".
    "validation_candidate_simulations",
    "validation_candidate_evidence_assessments",
    "validation_candidate_reports",
    "validation_candidate_exports",
    "validation_cro_packages",
    "validation_version_comparisons",
)

#: Every table that acquires an ``organization_id``. Also the list
#: :func:`check_organization_consistency` walks, and the list the backfill
#: fills, so the three cannot drift apart.
#:
#: Ordered parent-first. The backfill relies on it: a child is only ever
#: assigned an organization that its parent already has.
ORGANIZATION_SCOPED_TABLES: tuple[str, ...] = (
    "workspace_projects",
    "workspace_runs",
    "science_data_records",
    "science_readiness_snapshots",
    "validation_candidates",
    "validation_candidate_versions",
    "validation_experiments",
    "validation_experiment_versions",
    "validation_measurements",
    "validation_attachments",
    "validation_contradiction_resolutions",
    "validation_audit_log",
    # Dependent records. Listed after validation_candidate_versions because
    # the backfill is ordered parent-first and each of these hangs off it.
    "validation_candidate_simulations",
    "validation_candidate_evidence_assessments",
    "validation_candidate_reports",
    "validation_candidate_exports",
    "validation_cro_packages",
    "validation_version_comparisons",
    "report_assessments",
    "report_documents",
    "report_audit_log",
)


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
# fails silently â€” which is exactly what an earlier version of this table did,
# leaving demonstration runs backfilled as research designs.
#
# So every literal below is a member NAME, and the origin comparison accepts
# both spellings in case a row was ever written by hand.
_IS_DEMO = "origin IN ('DEMO', 'demo')"

#: Every column added since the tables were first created.
ADDITIVE_COLUMNS: tuple[AddColumn, ...] = (
    AddColumn(table="notifications", column="idempotency_key",
              ddl="VARCHAR(160) NULL"),
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
        ddl="BOOLEAN NOT NULL DEFAULT FALSE",
        backfill=("UPDATE workspace_runs SET inputs_are_synthetic = TRUE "
                  f"WHERE {_IS_DEMO}"),
    ),
    AddColumn(table="workspace_runs", column="report_assessment_id",
              ddl="INTEGER NULL"),
    #: One nullable ``organization_id`` per scoped table.
    #:
    #: Nullable, and without a foreign key in the DDL, on purpose. SQLite
    #: cannot add a NOT NULL column to a populated table without a default,
    #: and no default is correct here â€” the right organization is whichever
    #: one the backfill works out from the record's parent. So the column
    #: arrives empty, ``backfill_organizations()`` fills it, and
    #: ``check_organization_consistency()` verifies the result. A row that
    #: somehow ends up NULL is invisible to every scoped query rather than
    #: visible to everyone, which is the safe direction to fail.
    *(AddColumn(table=_t, column="organization_id", ddl="INTEGER NULL")
      for _t in ORGANIZATION_SCOPED_TABLES),

    # --- organization management ------------------------------------------
    #
    # Optimistic-concurrency counters. Defaulted to 1 rather than left NULL:
    # the conditional UPDATE that detects a collision compares on this column,
    # and NULL <> NULL in SQL, so a NULL revision would make every update on a
    # pre-existing row fail as a phantom conflict.
    AddColumn(table="organization_memberships", column="revision",
              ddl="INTEGER NOT NULL DEFAULT 1"),
    AddColumn(table="study_assignments", column="revision",
              ddl="INTEGER NOT NULL DEFAULT 1"),
    # Per-assignment attachment restriction. NULL means "defer to the
    # membership", which is exactly what every pre-existing assignment did.
    AddColumn(table="study_assignments", column="may_download_attachments",
              ddl="BOOLEAN NULL"),
    AddColumn(table="study_assignments", column="note", ddl="TEXT NULL"),

    # --- object storage ---------------------------------------------------
    #
    # Every existing attachment was written by the local driver, into no
    # bucket, and is available. Defaulting the state to AVAILABLE is therefore
    # a restatement of what those rows already were, not a guess: before this
    # column existed, a row's presence *was* the claim that the object was
    # there. The backfill for `storage_backend` says 'local' for the same
    # reason â€” it is the only driver that could have written them.
    AddColumn(
        table="validation_attachments", column="state",
        ddl="VARCHAR(24) NOT NULL DEFAULT 'AVAILABLE'"),
    AddColumn(
        table="validation_attachments", column="storage_backend",
        ddl="VARCHAR(32) NULL",
        backfill=("UPDATE validation_attachments SET storage_backend = 'local' "
                  "WHERE storage_backend IS NULL")),
    AddColumn(table="validation_attachments", column="storage_bucket",
              ddl="VARCHAR(120) NULL"),
    AddColumn(table="validation_attachments", column="state_changed_at",
              ddl="TIMESTAMP NULL"),
    AddColumn(table="validation_attachments", column="delete_attempts",
              ddl="INTEGER NOT NULL DEFAULT 0"),
    AddColumn(table="validation_attachments", column="last_error_code",
              ddl="VARCHAR(64) NULL"),
    AddColumn(table="validation_attachments", column="content_removed_at",
              ddl="TIMESTAMP NULL"),

    # --- account and session hardening ------------------------------------
    #
    # Every existing account was usable and had a password, so ACTIVE is a
    # restatement of what those rows already were, not a guess. Defaulting to
    # PENDING_ACTIVATION would lock out every existing user on upgrade â€” the
    # exact outcome the rehash-on-login migration exists to avoid.
    AddColumn(table="auth_users", column="state",
              ddl="VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'",
              # An account already disabled stays disabled. Reading the old
              # boolean is the only honest source for this.
              backfill=("UPDATE auth_users SET state = 'DISABLED' "
                        "WHERE is_active IS FALSE")),
    AddColumn(table="auth_users", column="state_changed_at",
              ddl="TIMESTAMP NULL"),
    AddColumn(table="auth_users", column="state_reason",
              ddl="VARCHAR(500) NULL"),
    # Left NULL rather than guessed at. Every existing hash is bcrypt, but
    # `needs_rehash` reads the hash prefix, so it does not need this to be
    # right â€” and writing 'bcrypt' onto a row whose hash somebody had already
    # migrated by hand would be asserting something the migration cannot know.
    AddColumn(table="auth_users", column="password_algorithm",
              ddl="VARCHAR(32) NULL"),
    AddColumn(table="auth_users", column="password_changed_at",
              ddl="TIMESTAMP NULL"),
    AddColumn(table="auth_users", column="must_set_password",
              ddl="BOOLEAN NOT NULL DEFAULT FALSE"),

    # Session columns. All nullable: an existing session keeps working and
    # simply has no handle until it is replaced, which happens within the
    # 8-hour absolute lifetime anyway.
    AddColumn(table="auth_sessions", column="revoked_at", ddl="TIMESTAMP NULL"),
    AddColumn(table="auth_sessions", column="revoked_reason",
              ddl="VARCHAR(64) NULL"),
    AddColumn(table="auth_sessions", column="handle", ddl="VARCHAR(12) NULL"),

    # ------------------------------------------------------------------
    # Candidate revision and supersession.
    #
    # Every column is nullable or carries a default, so an existing version
    # row remains valid the moment the column appears. The backfills below
    # state what an existing row ALREADY WAS rather than guessing at
    # something new:
    #
    #   * every existing version is its candidate's history, so it becomes
    #     DRAFT only if nothing depends on it â€” that decision needs a join
    #     and is made by the dedicated migration in `candidate_versioning.py`,
    #     not by a blanket UPDATE here;
    #   * `revision_label` is a restatement of `version_number`;
    #   * `results_state` starts at NONE because no existing row recorded
    #     whether its derived values were current, and claiming CURRENT for
    #     data whose provenance was never captured would be a fabrication.
    # ------------------------------------------------------------------
    AddColumn(table="validation_candidate_versions",
              column="predecessor_version_id", ddl="INTEGER NULL"),
    AddColumn(table="validation_candidate_versions",
              column="revision_reason", ddl="TEXT NULL"),
    AddColumn(table="validation_candidate_versions",
              column="revision_label", ddl="VARCHAR(32) NULL",
              backfill=("UPDATE validation_candidate_versions "
                        "SET revision_label = 'v' || version_number "
                        "WHERE revision_label IS NULL")),
    AddColumn(table="validation_candidate_versions", column="status",
              ddl="VARCHAR(16) NOT NULL DEFAULT 'DRAFT'"),
    AddColumn(table="validation_candidate_versions", column="locked_at",
              ddl="TIMESTAMP NULL"),
    AddColumn(table="validation_candidate_versions", column="lock_reason",
              ddl="VARCHAR(200) NULL"),
    AddColumn(table="validation_candidate_versions", column="results_state",
              ddl="VARCHAR(16) NOT NULL DEFAULT 'NONE'"),
    AddColumn(table="validation_candidate_versions",
              column="results_inherited_from_id", ddl="INTEGER NULL"),
    AddColumn(table="validation_candidate_versions", column="model_version",
              ddl="VARCHAR(64) NULL"),
    AddColumn(table="validation_candidate_versions", column="ruleset_version",
              ddl="VARCHAR(64) NULL"),
    AddColumn(table="validation_candidate_versions",
              column="reference_data_version", ddl="VARCHAR(64) NULL"),
    AddColumn(table="validation_candidate_versions",
              column="algorithm_selection", ddl="VARCHAR(120) NULL"),
    AddColumn(table="validation_candidate_versions",
              column="supersession_state",
              ddl="VARCHAR(16) NOT NULL DEFAULT 'NONE'"),
    AddColumn(table="validation_candidate_versions",
              column="superseded_by_version_id", ddl="INTEGER NULL"),
    AddColumn(table="validation_candidate_versions", column="superseded_at",
              ddl="TIMESTAMP NULL"),
    AddColumn(table="validation_candidate_versions",
              column="superseded_by_user_id", ddl="INTEGER NULL"),
    AddColumn(table="validation_candidate_versions",
              column="supersession_reason", ddl="TEXT NULL"),
    AddColumn(table="validation_candidate_versions",
              column="supersession_decision_id", ddl="INTEGER NULL"),
    AddColumn(table="validation_candidate_versions", column="revision",
              ddl="INTEGER NOT NULL DEFAULT 1"),

    # ------------------------------------------------------------------
    # Exact-version binding for records that already existed.
    #
    # `validation_attachments.candidate_version_id` arrives NULL rather than
    # backfilled here. The value is reachable â€” every attachment hangs off an
    # experiment version which names its candidate version â€” but a two-table
    # UPDATE that silently guesses on a mismatch is exactly what the legacy
    # migration exists to avoid doing. `legacy_candidate_migration` binds them,
    # reports the count, and refuses rather than guessing where the join is
    # ambiguous.
    # ------------------------------------------------------------------
    AddColumn(table="validation_attachments", column="candidate_version_id",
              ddl="INTEGER NULL"),

    # The audit trail gains the candidate alongside the version, and a
    # separate column for the actor's stated reason. Both nullable: a row
    # written before they existed genuinely has neither, and inventing one
    # would put words in an actor's mouth.
    AddColumn(table="validation_audit_log", column="candidate_id",
              ddl="INTEGER NULL"),
    AddColumn(table="validation_audit_log", column="reason",
              ddl="VARCHAR(500) NULL"),
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
     f"UPDATE workspace_runs SET inputs_are_synthetic = TRUE WHERE {_IS_DEMO} "
     "AND inputs_are_synthetic IS FALSE"),
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


#: child table -> (parent table, child FK column) for the consistency check.
#:
#: The FK column names are read from the declarative metadata rather than
#: written out here. Restating them by hand is how this check silently stopped
#: checking anything: an earlier draft guessed ``experiment_version_id`` where
#: the column is actually ``version_id``, and a mistyped column in a
#: consistency query fails loudly only if something runs it â€” otherwise it sits
#: there asserting nothing.
_PARENT_OF: dict[str, str] = {
    "workspace_runs": "workspace_projects",
    "validation_candidates": "workspace_runs",
    "validation_candidate_versions": "validation_candidates",
    "validation_experiments": "validation_candidates",
    "validation_experiment_versions": "validation_experiments",
    "validation_measurements": "validation_experiment_versions",
    "validation_attachments": "validation_experiment_versions",
    # Every dependent record must agree with the version it depends on about
    # which organization owns it. A disagreement here would mean a report
    # about one tenant's formulation is listed under another's.
    "validation_candidate_simulations": "validation_candidate_versions",
    "validation_candidate_evidence_assessments": "validation_candidate_versions",
    "validation_candidate_reports": "validation_candidate_versions",
    "validation_candidate_exports": "validation_candidate_versions",
    "validation_cro_packages": "validation_candidate_versions",
    # `validation_version_comparisons` is deliberately absent: it has two
    # version foreign keys and `_parent_join` resolves the first it finds,
    # which would check one side and silently ignore the other. Its
    # organization is taken from the left version at write time, and both
    # sides are required to share a candidate â€” which shares an organization.
    # A report document must never disagree with its assessment about which
    # organization owns it: the document is the patient's file, and the
    # assessment is what every scoped query resolves first.
    "report_documents": "report_assessments",
    # ``report_audit_log`` is deliberately absent. Its ``assessment_id`` is not
    # a foreign key â€” the trail has to outlive the assessment it describes,
    # which is the entire point of auditing a deletion â€” so there is no join to
    # verify. Its organization is captured from the assessment at write time,
    # including in ``delete_assessment``, which reads it before the row goes.
}


def _parent_join(child: str) -> tuple[str, str] | None:
    """``(parent table, child FK column)``, resolved from the metadata."""
    parent = _PARENT_OF.get(child)
    if parent is None:
        return None

    from nanobio_studio.app.db.base import Base

    table = Base.metadata.tables.get(child)
    if table is None:
        return None
    for column in table.columns:
        for fk in column.foreign_keys:
            if fk.column.table.name == parent:
                return parent, column.name
    return None


async def create_organization_indexes(engine: AsyncEngine) -> list[str]:
    """Index every ``organization_id``, idempotently.

    ``create_all`` adds indexes only alongside the tables it creates, so an
    upgraded database would get the columns without them â€” and every list,
    filter and dashboard query is about to acquire an organization predicate.
    An unindexed predicate on a table of any size turns each of those into a
    full scan, which is how an authorization change becomes a performance
    regression nobody connects back to it.
    """
    created: list[str] = []
    async with engine.begin() as conn:
        for table in ORGANIZATION_SCOPED_TABLES:
            columns = await _existing_columns(conn, table)
            if "organization_id" not in columns:
                continue
            index = f"ix_{table}_organization_id"
            await conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS {index} "
                f"ON {table} (organization_id)"))
            created.append(index)
        notification_columns = await _existing_columns(conn, "notifications")
        if "idempotency_key" in notification_columns:
            index = "uq_notification_recipient_idempotency"
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS " + index
                + " ON notifications (recipient_id, idempotency_key)"))
            created.append(index)
    return created


async def check_organization_consistency(
    engine: AsyncEngine,
) -> dict[str, int]:
    """Count rows whose organization is absent or disagrees with their parent.

    The price of denormalising ``organization_id`` onto every table is that it
    *can* disagree with the record's parent. The service layer is what stops
    that happening; this is what proves it did. Returns a table â†’ count map,
    empty when everything is consistent.
    """
    problems: dict[str, int] = {}

    async with engine.begin() as conn:
        for table in ORGANIZATION_SCOPED_TABLES:
            columns = await _existing_columns(conn, table)
            if "organization_id" not in columns:
                continue

            orphans = await conn.execute(text(
                f"SELECT COUNT(*) FROM {table} WHERE organization_id IS NULL"))
            count = orphans.scalar() or 0
            if count:
                problems[f"{table}: unassigned"] = count

            join = _parent_join(table)
            if join is None:
                continue
            parent, fk = join
            if "organization_id" not in await _existing_columns(conn, parent):
                continue
            mismatched = await conn.execute(text(
                f"SELECT COUNT(*) FROM {table} c "
                f"JOIN {parent} p ON c.{fk} = p.id "
                f"WHERE c.organization_id IS NOT NULL "
                f"  AND p.organization_id IS NOT NULL "
                f"  AND c.organization_id <> p.organization_id"))
            count = mismatched.scalar() or 0
            if count:
                problems[f"{table}: differs from {parent}"] = count

    return problems


async def tables_awaiting_creation(engine: AsyncEngine) -> list[str]:
    """Which newer tables are missing from an *existing* database.

    Purely an observation â€” it creates nothing. ``create_all`` does that, so
    this must be called before it if the answer is to be meaningful.

    Separate from :func:`apply_additive_migrations` on purpose. That function
    returns the changes it actually made and must return an empty list once
    there is nothing left to do; reporting a table it does not create would both
    misstate what happened and never stop repeating, because nothing it does
    resolves the condition.

    Returns nothing for a brand-new database. There, every table is absent and
    ``create_all`` builds the whole schema, so naming each one is noise rather
    than news. It is only an upgrade worth reporting when the older schema is
    already present and these tables are not.
    """
    async with engine.begin() as conn:
        if not await _existing_columns(conn, "workspace_runs"):
            return []
        return [t for t in EXPECTED_TABLES
                if not await _existing_columns(conn, t)]

