"""Give every pre-existing candidate an initial version, and bind what depends on it.

The state this exists to repair
-------------------------------
Before this milestone a candidate could exist with no version at all
(``create_candidate`` did not make one), and the formulation itself lived in
``workspace_runs.design_inputs_json`` — on the *study*, not the candidate. So an
upgraded database contains candidates that nothing can be attributed to, and
attachments and audit rows that reach their formulation only through a join
that a listing query has to remember to make.

What it does
------------
1. **One initial version per candidate that has none.** Numbered 1, labelled
   v1, carrying the candidate's own organization, study and timestamps.
2. **The snapshot, where it can be attributed.** A study with exactly one
   candidate had exactly one formulation, so its ``design_inputs_json`` is that
   candidate's — a restatement, not a guess. A study with several candidates
   and one set of design inputs cannot be resolved, and is reported instead.
3. **Dependent records bound to an exact version.** Attachments take the
   candidate version their experiment version already names. Audit rows take
   the candidate their version or experiment already names.
4. **Verification before it is believed.** Row counts on both sides, and every
   checksum recomputed from the stored snapshot.

The rule it follows when it cannot tell
---------------------------------------
**It reports, and does not guess.** An ambiguous candidate still gets an
initial version — dependent binding has to be deterministic, and leaving one
candidate versionless would mean the invariant "every candidate has a version"
holds for all but a few — but that version carries an **empty snapshot and a
note saying so**, and the candidate appears in the ambiguity report. An empty
snapshot that says it is empty is honest. A snapshot copied from a study that
had three candidates would be a fabricated attribution wearing a checksum.

Dry run and restart
-------------------
``dry_run=True`` is the default, as everywhere else in this codebase: the
person running a migration should see the plan before the plan runs. Restart is
safe because every step claims only rows that are still unclaimed — a candidate
with no version, an attachment with a NULL binding — so a second run reports
zero work and changes nothing. A run interrupted midway leaves a consistent
prefix, because the whole thing is one transaction.

What it never does
------------------
Deletes, overwrites or renumbers anything. No existing version, experiment,
review, approval, report, attachment, export or audit row is modified except to
*fill in* a binding column that was NULL. An approval granted before the
upgrade stays an approval of exactly the version it was granted on.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

__all__ = [
    "Ambiguity", "LegacyMigrationReport", "migrate_legacy_candidates",
    "verify_candidate_version_bindings", "LEGACY_MIGRATION_NOTE",
]

LEGACY_MIGRATION_NOTE = (
    "Initial version created by the legacy candidate migration. It records "
    "what the database already held; no scientific input was invented.")

UNATTRIBUTABLE_NOTE = (
    "Initial version created by the legacy candidate migration with an EMPTY "
    "formulation snapshot. The study this candidate belongs to holds one set "
    "of design inputs and more than one candidate, so which formulation "
    "belonged to this candidate could not be determined. Nothing was copied "
    "in: an attributed snapshot here would be a guess wearing a checksum.")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str)


def _checksum(snapshot: str) -> str:
    return hashlib.sha256(snapshot.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Ambiguity:
    """Something the migration could not resolve, and what it did instead.

    ``resolution`` is not optional. An ambiguity report that lists problems
    without saying what state the database was left in is a list of things to
    worry about rather than a record of what happened.
    """

    kind: str
    subject: str
    detail: str
    resolution: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "subject": self.subject,
                "detail": self.detail, "resolution": self.resolution}


@dataclass
class LegacyMigrationReport:
    """Exact counts. Every field is a number somebody can check against the database."""

    dry_run: bool = True
    ran_at: str = ""

    candidates_examined: int = 0
    candidates_migrated: int = 0
    candidates_unchanged: int = 0

    versions_created: int = 0
    versions_with_attributed_snapshot: int = 0
    versions_with_empty_snapshot: int = 0

    dependent_records_bound: dict[str, int] = field(default_factory=dict)
    dependent_records_unchanged: dict[str, int] = field(default_factory=dict)

    ambiguities: list[Ambiguity] = field(default_factory=list)

    #: Reasons this migration must not commit. Only ever things the migration
    #: itself got wrong — a lost row, a checksum on a version it just wrote.
    failures: list[str] = field(default_factory=list)

    #: Problems in data the migration did not create. Reported loudly and
    #: deliberately NOT fatal: a version whose checksum drifted before this
    #: ran is a real integrity finding, and refusing to start the application
    #: over it would take a system offline to protest about a row that was
    #: already there. The distinction matters — a migration that aborts on
    #: pre-existing damage can never be used to repair a damaged database.
    integrity_findings: list[str] = field(default_factory=list)

    counts_verified: bool = False
    checksums_verified: bool = False
    verification_notes: list[str] = field(default_factory=list)

    #: Row counts read before and after, so the report proves its own claims
    #: rather than asserting them.
    source_counts: dict[str, int] = field(default_factory=dict)
    destination_counts: dict[str, int] = field(default_factory=dict)

    @property
    def dependent_records_bound_total(self) -> int:
        return sum(self.dependent_records_bound.values())

    @property
    def succeeded(self) -> bool:
        return (not self.failures and self.counts_verified
                and self.checksums_verified)

    def summary(self) -> str:
        mode = "DRY RUN" if self.dry_run else "applied"
        return (
            f"legacy candidate migration ({mode}): "
            f"{self.candidates_examined} candidate(s) examined, "
            f"{self.candidates_migrated} migrated, "
            f"{self.candidates_unchanged} unchanged, "
            f"{self.versions_created} initial version(s) created "
            f"({self.versions_with_attributed_snapshot} with an attributed "
            f"snapshot, {self.versions_with_empty_snapshot} empty), "
            f"{self.dependent_records_bound_total} dependent record(s) bound, "
            f"{len(self.ambiguities)} ambiguity(ies), "
            f"{len(self.failures)} failure(s), "
            f"{len(self.integrity_findings)} pre-existing integrity finding(s)")

    def as_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "ran_at": self.ran_at,
            "candidates_examined": self.candidates_examined,
            "candidates_migrated": self.candidates_migrated,
            "candidates_unchanged": self.candidates_unchanged,
            "versions_created": self.versions_created,
            "versions_with_attributed_snapshot":
                self.versions_with_attributed_snapshot,
            "versions_with_empty_snapshot": self.versions_with_empty_snapshot,
            "dependent_records_bound": dict(self.dependent_records_bound),
            "dependent_records_bound_total": self.dependent_records_bound_total,
            "dependent_records_unchanged":
                dict(self.dependent_records_unchanged),
            "ambiguities": [a.as_dict() for a in self.ambiguities],
            "ambiguity_count": len(self.ambiguities),
            "failures": list(self.failures),
            "failure_count": len(self.failures),
            "integrity_findings": list(self.integrity_findings),
            "integrity_finding_count": len(self.integrity_findings),
            "counts_verified": self.counts_verified,
            "checksums_verified": self.checksums_verified,
            "verification_notes": list(self.verification_notes),
            "source_counts": dict(self.source_counts),
            "destination_counts": dict(self.destination_counts),
            "succeeded": self.succeeded,
            "summary": self.summary(),
        }


async def _table_exists(conn, table: str) -> bool:
    from nanobio_studio.app.db.migrations import _existing_columns

    return bool(await _existing_columns(conn, table))


async def _columns(conn, table: str) -> set[str]:
    from nanobio_studio.app.db.migrations import _existing_columns

    return await _existing_columns(conn, table)


async def _count(conn, table: str, where: str = "") -> int:
    clause = f" WHERE {where}" if where else ""
    return int((await conn.execute(
        text(f"SELECT COUNT(*) FROM {table}{clause}"))).scalar() or 0)


# ---------------------------------------------------------------------------
# The migration
# ---------------------------------------------------------------------------

async def migrate_legacy_candidates(engine: AsyncEngine, *,
                                    dry_run: bool = True
                                    ) -> LegacyMigrationReport:
    """Create initial versions and bind dependent records. Idempotent.

    One transaction. A failure anywhere leaves the database exactly as it was,
    which is what makes restarting safe rather than merely permitted.
    """
    report = LegacyMigrationReport(dry_run=dry_run,
                                   ran_at=_utcnow().isoformat())

    async with engine.begin() as conn:
        if not await _table_exists(conn, "validation_candidates"):
            report.verification_notes.append(
                "validation_candidates does not exist; nothing to migrate.")
            report.counts_verified = True
            report.checksums_verified = True
            return report

        await _read_source_counts(conn, report)
        written_ids = await _create_initial_versions(conn, report,
                                                     dry_run=dry_run)
        await _bind_attachments(conn, report, dry_run=dry_run)
        await _bind_audit_rows(conn, report, dry_run=dry_run)
        await _bind_contradiction_resolutions(conn, report, dry_run=dry_run)
        await _read_destination_counts(conn, report)
        await _verify(conn, report, dry_run=dry_run, written_ids=written_ids)

        if report.failures and not dry_run:
            # One transaction, so raising here rolls back everything above.
            # A migration that half-applied and reported failures would leave
            # somebody to work out which half.
            raise RuntimeError(
                "legacy candidate migration refused to commit: "
                + "; ".join(report.failures))

    return report


async def _read_source_counts(conn, report: LegacyMigrationReport) -> None:
    """What is there before anything is written."""
    for table in ("validation_candidates", "validation_candidate_versions",
                  "validation_experiments", "validation_experiment_versions",
                  "validation_measurements", "validation_attachments",
                  "validation_audit_log",
                  "validation_contradiction_resolutions"):
        if await _table_exists(conn, table):
            report.source_counts[table] = await _count(conn, table)

    report.candidates_examined = report.source_counts.get(
        "validation_candidates", 0)


async def _create_initial_versions(conn, report: LegacyMigrationReport, *,
                                   dry_run: bool) -> set[int]:
    """One version 1 per candidate that has none.

    Deliberately ordered by candidate id so a dry run and the real run visit
    the same candidates in the same order, and two runs of the report can be
    compared line by line.

    Returns the ids of the versions it wrote, so the checksum verification can
    tell a row this migration produced from one that was already there.
    """
    written: set[int] = set()
    candidates = (await conn.execute(text(
        "SELECT c.id, c.organization_id, c.study_id, c.owner_id, c.code, "
        "       c.name, c.created_at "
        "FROM validation_candidates c "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM validation_candidate_versions v "
        "  WHERE v.candidate_id = c.id) "
        "ORDER BY c.id"))).all()

    report.candidates_unchanged = (report.candidates_examined
                                   - len(candidates))

    if not candidates:
        return written

    # How many candidates each study has. A study with one candidate had one
    # formulation; a study with several cannot be resolved from one column.
    per_study = {
        row[0]: row[1] for row in (await conn.execute(text(
            "SELECT study_id, COUNT(*) FROM validation_candidates "
            "GROUP BY study_id"))).all()
    }

    has_runs = await _table_exists(conn, "workspace_runs")
    version_columns = await _columns(conn, "validation_candidate_versions")

    for (candidate_id, organization_id, study_id, _owner_id, code, _name,
         created_at) in candidates:
        design_inputs: dict | None = None
        siblings = int(per_study.get(study_id, 1) or 1)

        if has_runs:
            row = (await conn.execute(text(
                "SELECT design_inputs_json FROM workspace_runs WHERE id = :s"
            ), {"s": study_id})).first()
            raw = row[0] if row is not None else None
            if raw:
                try:
                    parsed = json.loads(raw)
                except (TypeError, ValueError):
                    parsed = None
                    report.ambiguities.append(Ambiguity(
                        kind="unreadable_study_inputs",
                        subject=f"candidate {candidate_id} ({code})",
                        detail=("The study's design_inputs_json is not valid "
                                "JSON, so no formulation could be read from "
                                "it."),
                        resolution=("An initial version was created with an "
                                    "empty snapshot and a note recording "
                                    "why.")))
                if isinstance(parsed, dict):
                    if siblings == 1:
                        design_inputs = parsed
                    else:
                        report.ambiguities.append(Ambiguity(
                            kind="study_has_several_candidates",
                            subject=f"candidate {candidate_id} ({code})",
                            detail=(f"Study {study_id} holds one set of design "
                                    f"inputs and {siblings} candidates, so "
                                    f"which formulation belonged to this one "
                                    f"cannot be determined."),
                            resolution=("An initial version was created with "
                                        "an empty snapshot and a note "
                                        "recording why. Nothing was copied "
                                        "in.")))
            elif has_runs:
                report.ambiguities.append(Ambiguity(
                    kind="study_has_no_design_inputs",
                    subject=f"candidate {candidate_id} ({code})",
                    detail=(f"Study {study_id} records no design inputs, so "
                            f"there is no formulation to attribute."),
                    resolution=("An initial version was created with an empty "
                                "snapshot and a note recording why.")))

        attributed = design_inputs is not None
        snapshot = _canonical(design_inputs if attributed else {})

        report.versions_created += 1
        if attributed:
            report.versions_with_attributed_snapshot += 1
        else:
            report.versions_with_empty_snapshot += 1
        report.candidates_migrated += 1

        if dry_run:
            continue

        values = {
            "organization_id": organization_id,
            "candidate_id": candidate_id,
            "version_number": 1,
            "design_snapshot_json": snapshot,
            "snapshot_checksum": _checksum(snapshot),
            # The candidate's own creation time, not now(). The version
            # records when the formulation existed, and stamping it with the
            # migration's clock would date every legacy candidate to the day
            # somebody ran an upgrade.
            "created_at": created_at,
            "note": (LEGACY_MIGRATION_NOTE if attributed
                     else UNATTRIBUTABLE_NOTE),
        }
        # Columns added by later migrations may or may not be present on the
        # database being upgraded. Only set the ones that exist, so this runs
        # against a schema at any point on the upgrade path.
        optional = {
            "revision_label": "v1",
            # DRAFT: nothing has been shown to depend on it yet. The reliance
            # boundary locks it the first time something does, and claiming
            # LOCKED here would freeze every legacy candidate on the strength
            # of no dependency at all.
            "status": "DRAFT",
            # NONE, not CURRENT. No legacy row recorded whether its derived
            # values were computed for these inputs, and claiming they were is
            # exactly the fabrication this migration refuses elsewhere.
            "results_state": "NONE",
            "supersession_state": "NONE",
            "revision": 1,
        }
        for column, value in optional.items():
            if column in version_columns:
                values[column] = value

        columns = ", ".join(values)
        placeholders = ", ".join(f":{k}" for k in values)
        await conn.execute(text(
            f"INSERT INTO validation_candidate_versions ({columns}) "
            f"VALUES ({placeholders})"), values)

        new_id = (await conn.execute(text(
            "SELECT id FROM validation_candidate_versions "
            "WHERE candidate_id = :c AND version_number = 1"),
            {"c": candidate_id})).scalar()
        if new_id is not None:
            written.add(int(new_id))

    return written


async def _bind_attachments(conn, report: LegacyMigrationReport, *,
                            dry_run: bool) -> None:
    """Give each attachment the candidate version its experiment already names.

    Deterministic and unambiguous: ``validation_experiment_versions
    .candidate_version_id`` is NOT NULL, so there is exactly one answer per
    attachment and nothing to choose between.
    """
    table = "validation_attachments"
    if not await _table_exists(conn, table):
        return
    if "candidate_version_id" not in await _columns(conn, table):
        report.verification_notes.append(
            f"{table}.candidate_version_id is absent; run the additive "
            f"migration first.")
        return

    unbound = await _count(conn, table, "candidate_version_id IS NULL")
    report.dependent_records_unchanged[table] = (
        await _count(conn, table, "candidate_version_id IS NOT NULL"))

    if not unbound:
        report.dependent_records_bound.setdefault(table, 0)
        return

    orphans = await _count(conn, table, (
        "candidate_version_id IS NULL AND NOT EXISTS ("
        "  SELECT 1 FROM validation_experiment_versions ev "
        f" WHERE ev.id = {table}.version_id)"))
    if orphans:
        report.ambiguities.append(Ambiguity(
            kind="attachment_without_experiment_version",
            subject=f"{orphans} attachment(s)",
            detail=("These attachments reference an experiment version that "
                    "does not exist, so no candidate version can be derived "
                    "from them."),
            resolution=("Left unbound. The rows are untouched and the "
                        "attachments remain readable through their own "
                        "identifiers.")))

    bindable = unbound - orphans
    report.dependent_records_bound[table] = bindable

    if dry_run or not bindable:
        return

    await conn.execute(text(
        f"UPDATE {table} SET candidate_version_id = ("
        "  SELECT ev.candidate_version_id FROM validation_experiment_versions ev"
        f" WHERE ev.id = {table}.version_id) "
        "WHERE candidate_version_id IS NULL "
        "  AND EXISTS (SELECT 1 FROM validation_experiment_versions ev2 "
        f"              WHERE ev2.id = {table}.version_id)"))


async def _bind_audit_rows(conn, report: LegacyMigrationReport, *,
                           dry_run: bool) -> None:
    """Fill in the candidate on audit rows that already name a version or experiment.

    Two sources, applied in order of directness: a row that names a candidate
    version is bound from that; a row that names only an experiment is bound
    from the experiment. A row that names both and *disagrees* is reported
    rather than resolved — the trail is the record of what happened, and
    picking a side would be editing it.
    """
    table = "validation_audit_log"
    if not await _table_exists(conn, table):
        return
    if "candidate_id" not in await _columns(conn, table):
        report.verification_notes.append(
            f"{table}.candidate_id is absent; run the additive migration "
            f"first.")
        return

    report.dependent_records_unchanged[table] = (
        await _count(conn, table, "candidate_id IS NOT NULL"))

    # Written without a NULL-safe comparison operator on purpose: SQLite
    # spells it `IS NOT` and PostgreSQL spells it `IS DISTINCT FROM`, and this
    # module runs against both. Handling the NULLs explicitly is longer and
    # portable, which is the right trade for a migration.
    _version_candidate = (
        "(SELECT v.candidate_id FROM validation_candidate_versions v "
        f" WHERE v.id = {table}.candidate_version_id)")
    _experiment_candidate = (
        "(SELECT e.candidate_id FROM validation_experiments e "
        f" WHERE e.id = {table}.experiment_id)")

    conflicting = await _count(conn, table, (
        "candidate_id IS NULL "
        "AND candidate_version_id IS NOT NULL AND experiment_id IS NOT NULL "
        f"AND {_version_candidate} IS NOT NULL "
        f"AND {_experiment_candidate} IS NOT NULL "
        f"AND {_version_candidate} <> {_experiment_candidate}"))
    if conflicting:
        report.ambiguities.append(Ambiguity(
            kind="audit_row_names_two_candidates",
            subject=f"{conflicting} audit row(s)",
            detail=("The candidate version and the experiment named by these "
                    "rows belong to different candidates."),
            resolution=("Left unbound. Choosing one would edit the trail, "
                        "which is the one record that must say what it said.")))

    from_version = await _count(conn, table, (
        "candidate_id IS NULL AND candidate_version_id IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM validation_candidate_versions v "
        f"           WHERE v.id = {table}.candidate_version_id)"))
    from_experiment = await _count(conn, table, (
        "candidate_id IS NULL AND candidate_version_id IS NULL "
        "AND experiment_id IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM validation_experiments e "
        f"           WHERE e.id = {table}.experiment_id)"))

    bindable = from_version + from_experiment - conflicting
    report.dependent_records_bound[table] = max(0, bindable)

    if dry_run or bindable <= 0:
        return

    await conn.execute(text(
        f"UPDATE {table} SET candidate_id = {_version_candidate} "
        "WHERE candidate_id IS NULL AND candidate_version_id IS NOT NULL "
        f"  AND {_version_candidate} IS NOT NULL "
        "  AND (experiment_id IS NULL "
        f"       OR {_experiment_candidate} IS NULL "
        f"       OR {_version_candidate} = {_experiment_candidate})"))

    await conn.execute(text(
        f"UPDATE {table} SET candidate_id = ("
        "  SELECT e.candidate_id FROM validation_experiments e "
        f" WHERE e.id = {table}.experiment_id) "
        "WHERE candidate_id IS NULL AND candidate_version_id IS NULL "
        "  AND experiment_id IS NOT NULL "
        "  AND EXISTS (SELECT 1 FROM validation_experiments e2 "
        f"              WHERE e2.id = {table}.experiment_id)"))


async def _bind_contradiction_resolutions(conn,
                                          report: LegacyMigrationReport, *,
                                          dry_run: bool) -> None:
    """Bind a resolution to an exact version where exactly one is possible.

    A resolution carries a study and a purpose but may carry no candidate
    version. Where the study has exactly one candidate with exactly one
    version, there is one answer and it is a restatement. Where it has more,
    it is reported.
    """
    table = "validation_contradiction_resolutions"
    if not await _table_exists(conn, table):
        return

    report.dependent_records_unchanged[table] = (
        await _count(conn, table, "candidate_version_id IS NOT NULL"))

    unbound = await _count(conn, table, "candidate_version_id IS NULL")
    if not unbound:
        report.dependent_records_bound.setdefault(table, 0)
        return

    resolvable = await _count(conn, table, (
        "candidate_version_id IS NULL AND ("
        "  SELECT COUNT(*) FROM validation_candidate_versions v "
        "  JOIN validation_candidates c ON c.id = v.candidate_id "
        f" WHERE c.study_id = {table}.study_id) = 1"))

    unresolvable = unbound - resolvable
    if unresolvable:
        report.ambiguities.append(Ambiguity(
            kind="resolution_study_has_several_versions",
            subject=f"{unresolvable} contradiction resolution(s)",
            detail=("These resolutions name a study whose candidates have "
                    "more than one version between them, so which version the "
                    "reviewer was reading cannot be determined."),
            resolution=("Left unbound. The resolution, its rationale and its "
                        "considered version ids are untouched.")))

    report.dependent_records_bound[table] = resolvable

    if dry_run or not resolvable:
        return

    await conn.execute(text(
        f"UPDATE {table} SET candidate_version_id = ("
        "  SELECT v.id FROM validation_candidate_versions v "
        "  JOIN validation_candidates c ON c.id = v.candidate_id "
        f" WHERE c.study_id = {table}.study_id) "
        "WHERE candidate_version_id IS NULL "
        "  AND (SELECT COUNT(*) FROM validation_candidate_versions v2 "
        "       JOIN validation_candidates c2 ON c2.id = v2.candidate_id "
        f"      WHERE c2.study_id = {table}.study_id) = 1"))


async def _read_destination_counts(conn,
                                   report: LegacyMigrationReport) -> None:
    for table in report.source_counts:
        report.destination_counts[table] = await _count(conn, table)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

async def _verify(conn, report: LegacyMigrationReport, *,
                  dry_run: bool, written_ids: set[int]) -> None:
    """Prove the claims above, or record why they could not be proved."""
    await _verify_counts(conn, report, dry_run=dry_run)
    await _verify_checksums(conn, report, written_ids=written_ids)


async def _verify_counts(conn, report: LegacyMigrationReport, *,
                         dry_run: bool) -> None:
    problems: list[str] = []

    # Nothing may be lost. Every table except the versions table must have
    # exactly the row count it started with — this migration adds versions and
    # fills in NULLs, and any other change is a defect.
    for table, before in report.source_counts.items():
        after = report.destination_counts.get(table, before)
        if table == "validation_candidate_versions":
            expected = before + (0 if dry_run else report.versions_created)
            if after != expected:
                problems.append(
                    f"{table}: expected {expected} rows after creating "
                    f"{report.versions_created} initial version(s) from "
                    f"{before}, found {after}")
            continue
        if after != before:
            problems.append(
                f"{table}: {before} rows before, {after} after. This "
                f"migration must not add or remove rows in this table.")

    if not dry_run:
        # The invariant the whole migration is for.
        versionless = await _count(conn, "validation_candidates", (
            "NOT EXISTS (SELECT 1 FROM validation_candidate_versions v "
            "            WHERE v.candidate_id = validation_candidates.id)"))
        if versionless:
            problems.append(
                f"{versionless} candidate(s) still have no version after the "
                f"migration ran.")

    report.counts_verified = not problems
    report.failures.extend(problems)
    if not problems:
        report.verification_notes.append(
            "Row counts verified on both sides: no table other than "
            "validation_candidate_versions changed size, and that one grew by "
            f"exactly {0 if dry_run else report.versions_created}.")


async def _verify_checksums(conn, report: LegacyMigrationReport, *,
                            written_ids: set[int]) -> None:
    """Recompute every stored checksum from its stored snapshot.

    Every version, not only the rows this migration wrote — a migration is the
    moment somebody is looking, and a drifted checksum is cheaper to find here
    than when a report cites the wrong formulation.

    But the two cases are handled differently, and the difference is the point:

    * a mismatch on a row **this migration wrote** is a failure, and rolls the
      whole thing back — it means the write itself is wrong;
    * a mismatch on a **pre-existing** row is an integrity *finding*. It is
      reported, and it does not block. Aborting on it would make this migration
      unusable on exactly the databases that most need repairing, and would
      take an application offline over a row that was already there before it
      started.
    """
    rows = (await conn.execute(text(
        "SELECT id, design_snapshot_json, snapshot_checksum "
        "FROM validation_candidate_versions ORDER BY id"))).all()

    written_mismatch: list[int] = []
    preexisting_mismatch: list[int] = []
    for version_id, snapshot, stored in rows:
        if _checksum(snapshot or "") == (stored or ""):
            continue
        (written_mismatch if version_id in written_ids
         else preexisting_mismatch).append(version_id)

    def _listing(ids: list[int]) -> str:
        shown = ", ".join(str(i) for i in ids[:20])
        more = "" if len(ids) <= 20 else f" (and {len(ids) - 20} more)"
        return shown + more

    if written_mismatch:
        report.failures.append(
            f"{len(written_mismatch)} initial version(s) this migration wrote "
            f"have a checksum that does not match their snapshot: "
            f"{_listing(written_mismatch)}")

    if preexisting_mismatch:
        report.integrity_findings.append(
            f"{len(preexisting_mismatch)} pre-existing candidate version(s) "
            f"have a checksum that does not match their stored snapshot: "
            f"{_listing(preexisting_mismatch)}. This migration did not write "
            f"them and has not changed them. Each one is a formulation whose "
            f"recorded identity cannot be confirmed, and should be "
            f"investigated before anything new is generated from it.")

    report.checksums_verified = not written_mismatch
    if report.checksums_verified:
        report.verification_notes.append(
            f"Recomputed {len(rows)} snapshot checksum(s). "
            f"{len(rows) - len(preexisting_mismatch)} matched"
            + (f"; {len(preexisting_mismatch)} pre-existing row(s) did not "
               f"and are reported as integrity findings."
               if preexisting_mismatch else "."))


async def verify_candidate_version_bindings(engine: AsyncEngine) -> dict:
    """Report what is still unbound. Creates and changes nothing.

    Separate from the migration so it can be run at any time — before, after,
    or on a database nobody intends to migrate — and so a test can prove the
    migration actually resolved what this reports.
    """
    result: dict = {"checked_at": _utcnow().isoformat(), "unbound": {},
                    "versionless_candidates": 0, "complete": True}

    async with engine.connect() as conn:
        if not await _table_exists(conn, "validation_candidates"):
            result["note"] = "validation_candidates does not exist."
            return result

        result["versionless_candidates"] = await _count(
            conn, "validation_candidates",
            "NOT EXISTS (SELECT 1 FROM validation_candidate_versions v "
            "            WHERE v.candidate_id = validation_candidates.id)")

        for table, column in (
            ("validation_attachments", "candidate_version_id"),
            ("validation_audit_log", "candidate_id"),
        ):
            if not await _table_exists(conn, table):
                continue
            if column not in await _columns(conn, table):
                continue
            result["unbound"][f"{table}.{column}"] = await _count(
                conn, table, f"{column} IS NULL")

    result["complete"] = (result["versionless_candidates"] == 0
                          and not any(result["unbound"].values()))
    result["note"] = (
        "Every candidate has a version and every dependent record names one."
        if result["complete"] else
        "Some records do not name an exact candidate version. Run "
        "migrate_legacy_candidates(dry_run=False), then read its ambiguity "
        "report for anything it declined to resolve.")
    return result
