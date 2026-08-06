"""Detecting where the database and the object store disagree.

Why this is a separate tool and not a background job
----------------------------------------------------
The database and the object store are two systems. The attachment lifecycle
(``AttachmentState``) exists so that every way they can disagree has a name,
and so that a disagreement is recorded rather than discovered by the next
person who asks for a file. This module is what goes looking.

Five findings, each with a different remedy:

* **row without object** — the row says ``AVAILABLE``, the store has nothing.
  Either an object was deleted out of band or a lifecycle rule ate it. The
  remedy is investigation, and the row is marked ``MISSING`` so the next
  reader gets an honest error instead of a 500.
* **object without row** — bytes nobody references. Almost always an upload
  that failed after step 3, or a rerun of a migration. The remedy is cleanup,
  and it is the one finding that must never be acted on automatically.
* **size or checksum mismatch** — the bytes are not the bytes. This is the
  most serious finding in the file: every result attributed to that attachment
  is unsupported until somebody looks.
* **wrong bucket or prefix** — a row written by a different driver or against
  a different container, usually a half-finished migration.
* **stuck in a transitional state** — ``PENDING_UPLOAD`` for an hour is an
  upload that died; ``DELETE_PENDING`` is a deletion that needs retrying.

Nothing is deleted unless asked, twice
--------------------------------------
``reconcile()`` reports. ``cleanup_orphan_objects()`` is a separate function
that requires ``confirm=True`` *and* an explicit list of keys produced by a
prior report. An automatic reconciler that deletes unmatched objects will, the
first time it runs against a half-migrated deployment, delete every object the
migration had not yet recorded. So it cannot: the deleting function does not
enumerate, and the enumerating function does not delete.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.validation_models import (
    AttachmentState, ExperimentAttachment, TRANSITIONAL_ATTACHMENT_STATES,
)
from nanobio_studio.app.storage.keys import (
    InvalidObjectKey, is_valid_key, parse_key,
)
from nanobio_studio.app.storage.objects import (
    ObjectNotFound, ObjectStore, StorageError,
)

__all__ = ["ReconciliationReport", "reconcile", "cleanup_orphan_objects",
           "STUCK_AFTER"]

log = logging.getLogger(__name__)

#: How long a transitional state has to persist before it is a finding.
#: Generous: a slow upload of a 25 MB file over a poor connection is not a
#: fault, and reporting it as one trains operators to ignore the report.
STUCK_AFTER = timedelta(hours=1)


@dataclass
class ReconciliationReport:
    """What was found. Identifiers and technical status only.

    Deliberately carries no filename, no clinical content and no organization
    *name* — a reconciliation report is an operations artefact that gets pasted
    into tickets and chat. Numeric identifiers are enough to find the row.
    """

    checked_rows: int = 0
    checked_objects: int = 0

    rows_without_objects: list[int] = field(default_factory=list)
    objects_without_rows: list[str] = field(default_factory=list)
    size_mismatches: list[int] = field(default_factory=list)
    checksum_mismatches: list[int] = field(default_factory=list)
    wrong_container: list[int] = field(default_factory=list)
    stuck_in_transition: list[int] = field(default_factory=list)
    unattributable_objects: list[str] = field(default_factory=list)
    #: Rows whose key predates the opaque-key format. Not a fault and not an
    #: outage: a migration backlog, with its own command.
    legacy_key_format: list[int] = field(default_factory=list)

    marked_missing: list[int] = field(default_factory=list)
    #: Set when the store cannot enumerate, so "no orphan objects" is never
    #: reported as a finding when it is really an absence of evidence.
    object_scan_available: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        """Whether anything is *wrong*.

        ``legacy_key_format`` is deliberately excluded. A row awaiting key
        migration is an expected state during an upgrade, and folding it in
        would make the report red on every installation that has not finished
        migrating — which is how a report stops being read. It is counted,
        listed and named in the summary regardless.
        """
        return not (self.rows_without_objects or self.objects_without_rows
                    or self.size_mismatches or self.checksum_mismatches
                    or self.wrong_container or self.stuck_in_transition)

    def summary(self) -> str:
        return (
            f"checked {self.checked_rows} row(s) and {self.checked_objects} "
            f"object(s); {len(self.rows_without_objects)} row(s) without "
            f"objects, {len(self.objects_without_rows)} object(s) without "
            f"rows, {len(self.checksum_mismatches)} checksum mismatch(es), "
            f"{len(self.size_mismatches)} size mismatch(es), "
            f"{len(self.wrong_container)} in the wrong container, "
            f"{len(self.stuck_in_transition)} stuck in transition, "
            f"{len(self.legacy_key_format)} awaiting key migration")

    def to_dict(self) -> dict:
        return {
            "checked_rows": self.checked_rows,
            "checked_objects": self.checked_objects,
            "rows_without_objects": self.rows_without_objects,
            "objects_without_rows": self.objects_without_rows,
            "size_mismatches": self.size_mismatches,
            "checksum_mismatches": self.checksum_mismatches,
            "wrong_container": self.wrong_container,
            "stuck_in_transition": self.stuck_in_transition,
            "unattributable_objects": self.unattributable_objects,
            "legacy_key_format": self.legacy_key_format,
            "marked_missing": self.marked_missing,
            "object_scan_available": self.object_scan_available,
            "healthy": self.healthy,
            "notes": self.notes,
        }


async def reconcile(
    session: AsyncSession, *, store: ObjectStore,
    mark_missing: bool = False, deep: bool = False,
    now: datetime | None = None,
) -> ReconciliationReport:
    """Compare every attachment row against the store. Deletes nothing.

    ``deep`` downloads each object to re-verify its checksum. Off by default:
    ``head`` gives the size and the store's recorded digest for a fraction of
    the cost, and a check nobody can afford to run is a check nobody runs.

    ``mark_missing`` is the one mutation offered, and it only ever moves a row
    to ``MISSING`` — a state that makes the next read fail honestly instead of
    with a 500. It never removes a row and never touches an object.
    """
    report = ReconciliationReport()
    moment = now or datetime.now(timezone.utc)

    rows = list((await session.execute(
        select(ExperimentAttachment).order_by(ExperimentAttachment.id)
    )).scalars().all())
    report.checked_rows = len(rows)

    known_keys: set[str] = set()

    for row in rows:
        # A row whose content was deliberately disposed of is not a finding.
        if row.state in {AttachmentState.DELETED}:
            continue

        if row.state in TRANSITIONAL_ATTACHMENT_STATES:
            changed = row.state_changed_at or row.uploaded_at
            if changed is not None and changed.tzinfo is None:
                changed = changed.replace(tzinfo=timezone.utc)
            if changed is not None and moment - changed > STUCK_AFTER:
                report.stuck_in_transition.append(row.id)
            # A pending upload has no object to compare against yet.
            if row.state is AttachmentState.PENDING_UPLOAD:
                continue

        if not row.storage_key:
            report.rows_without_objects.append(row.id)
            continue

        known_keys.add(row.storage_key)

        # A key written before the opaque-key format is not something the
        # store can be asked about — `head` refuses it as invalid, which
        # surfaced as "storage unavailable while checking row N" and read like
        # an incident. It is neither a fault nor an outage: it is a row the
        # migration command has not reached yet, and it gets its own finding
        # so an operator sees a backlog rather than an alarm.
        #
        # Found by running the tool against a real installation.
        if not is_valid_key(row.storage_key):
            report.legacy_key_format.append(row.id)
            continue

        # A row written against a different container than the one configured
        # now is not necessarily broken — it is usually a half-finished
        # migration — but it is not verifiable here either, so it is reported
        # rather than checked against the wrong store.
        if (row.storage_bucket or None) != (store.bucket or None) \
                or (row.storage_backend or store.driver) != store.driver:
            report.wrong_container.append(row.id)
            continue

        try:
            metadata = store.head(row.storage_key)
        except ObjectNotFound:
            report.rows_without_objects.append(row.id)
            if mark_missing and row.state is AttachmentState.AVAILABLE:
                row.state = AttachmentState.MISSING
                row.state_changed_at = moment
                row.last_error_code = "object_missing"
                report.marked_missing.append(row.id)
            continue
        except StorageError as exc:
            # Unreachable is not absent. Reporting it as a missing object
            # would turn a storage outage into a data-integrity alarm.
            report.notes.append(
                f"storage unavailable while checking row {row.id}: {exc.code}")
            continue

        report.checked_objects += 1

        if metadata.size_bytes != row.size_bytes:
            report.size_mismatches.append(row.id)

        recorded = metadata.checksum_sha256
        if recorded is not None and recorded != row.checksum_sha256:
            report.checksum_mismatches.append(row.id)
        elif deep:
            import hashlib
            digest = hashlib.sha256()
            try:
                for chunk in store.open_stream(row.storage_key):
                    digest.update(chunk)
            except (ObjectNotFound, StorageError):
                report.rows_without_objects.append(row.id)
                continue
            if digest.hexdigest() != row.checksum_sha256:
                report.checksum_mismatches.append(row.id)

    if mark_missing and report.marked_missing:
        await session.flush()

    # --- objects with no row -------------------------------------------
    try:
        for key in store.list_keys("att/"):
            report.checked_objects += 0  # counted above for compared objects
            if key in known_keys:
                continue
            try:
                parse_key(key)
            except InvalidObjectKey:
                # Not a key this application generates. Reported separately,
                # because deleting something we did not write is exactly the
                # mistake the cleanup gate exists to prevent.
                report.unattributable_objects.append(key)
                continue
            report.objects_without_rows.append(key)
    except StorageError as exc:
        report.object_scan_available = False
        report.notes.append(
            f"objects-without-rows not checked: {exc.code}. This is an "
            f"absence of evidence, not evidence of absence.")

    return report


def cleanup_orphan_objects(
    *, store: ObjectStore, keys: list[str], confirm: bool = False,
) -> dict[str, object]:
    """Delete named orphan objects. Requires an explicit list AND confirmation.

    Two gates, and both are load-bearing:

    * it takes a **list of keys**, not a prefix or a report. The caller has to
      have looked at a reconciliation report and chosen. There is no way to
      say "delete all orphans", because the first time that ran against a
      half-migrated deployment it would delete every object the migration had
      not yet recorded.
    * ``confirm`` defaults to false, so the default outcome of calling this
      function by accident is a dry run.

    Keys that this application did not generate are refused outright. If
    something else is sharing the bucket, its objects are not ours to remove.
    """
    planned: list[str] = []
    refused: list[str] = []
    for key in keys:
        try:
            parse_key(key)
        except InvalidObjectKey:
            refused.append(key)
            continue
        planned.append(key)

    if not confirm:
        return {"confirmed": False, "deleted": 0, "planned": planned,
                "refused_not_ours": refused,
                "message": (f"Dry run. {len(planned)} object(s) would be "
                            f"deleted; nothing was touched.")}

    deleted, failed = 0, []
    for key in planned:
        try:
            if store.delete(key):
                deleted += 1
        except StorageError as exc:
            failed.append({"key": key, "code": exc.code})

    return {"confirmed": True, "deleted": deleted, "planned": planned,
            "failed": failed, "refused_not_ours": refused,
            "message": f"Deleted {deleted} orphan object(s)."}
