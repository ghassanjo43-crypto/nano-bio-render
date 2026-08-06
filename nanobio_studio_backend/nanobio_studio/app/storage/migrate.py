"""Moving existing attachments into object storage, without losing one.

The rule this module is built around
------------------------------------
**Upload and verify before changing where the row points, and never touch the
original.** A migration that flips the pointer first has a window in which the
row names an object that does not exist yet; a migration that deletes as it
goes has no way back when the third file turns out to be corrupt. So the order
is: read the local file, verify it against the recorded checksum, upload it,
read the uploaded object's metadata back, compare, and only then update the
row. The local file is left exactly where it was.

Deleting the originals is a **separate command**, run afterwards, requiring an
explicit path and confirmation. That is not caution for its own sake: the whole
value of a migration you can rerun is that the source is still there.

Resuming, and rerunning
-----------------------
Idempotent by looking at where each row actually points. A row whose
``storage_backend`` already matches the destination driver and whose object
verifies is skipped — so an interrupted run continues where it stopped, and a
completed run does nothing on a second invocation rather than uploading every
file again under new keys.

The manifest
------------
Identifiers, sizes, checksums and outcomes. No filename, no clinical content,
no organization name. A migration manifest is an operations artefact that ends
up in tickets and archives, and it must be safe to put there.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.validation_models import (
    AttachmentState, ExperimentAttachment,
)
from nanobio_studio.app.storage.keys import is_valid_key, new_attachment_key
from nanobio_studio.app.storage.objects import (
    ObjectNotFound, ObjectStore, StorageError,
)

__all__ = ["MigrationReport", "migrate_attachments", "cleanup_local_originals"]

log = logging.getLogger(__name__)


@dataclass
class MigrationReport:
    """Technical status only. Safe to paste into a ticket."""

    dry_run: bool = True
    verify_only: bool = False
    destination_driver: str = ""
    destination_bucket: str | None = None

    considered: int = 0
    already_migrated: int = 0
    migrated: int = 0
    verified: int = 0
    skipped_no_source: list[int] = field(default_factory=list)
    checksum_mismatch: list[int] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    entries: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed and not self.checksum_mismatch

    def summary(self) -> str:
        mode = ("verification only" if self.verify_only
                else "dry run" if self.dry_run else "applied")
        return (f"{mode}: considered {self.considered}, already migrated "
                f"{self.already_migrated}, migrated {self.migrated}, verified "
                f"{self.verified}, missing source "
                f"{len(self.skipped_no_source)}, checksum mismatch "
                f"{len(self.checksum_mismatch)}, failed {len(self.failed)}")

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "verify_only": self.verify_only,
            "destination": {"driver": self.destination_driver,
                            "bucket": self.destination_bucket},
            "considered": self.considered,
            "already_migrated": self.already_migrated,
            "migrated": self.migrated,
            "verified": self.verified,
            "skipped_no_source": self.skipped_no_source,
            "checksum_mismatch": self.checksum_mismatch,
            "failed": self.failed,
            "ok": self.ok,
            "notes": self.notes,
            "entries": self.entries,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True),
                          encoding="utf-8")
        return target


def _local_path(root: Path, storage_key: str) -> Path | None:
    """Where a pre-migration attachment's bytes live.

    Two layouts, because the key format changed with the object-storage work:
    the old flat 32-hex key sharded by its first two characters, and the new
    ``att/org/id/token`` key stored at that path. Both are looked for, so a
    deployment that half-migrated before this command existed still resolves.
    """
    candidates = []
    if is_valid_key(storage_key):
        candidates.append(root / storage_key)
    if len(storage_key) == 32 and all(c in "0123456789abcdef"
                                      for c in storage_key):
        candidates.append(root / storage_key[:2] / storage_key)
    candidates.append(root / storage_key)
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_relative_to(root.resolve()) and resolved.is_file():
            return resolved
    return None


async def migrate_attachments(
    session: AsyncSession, *, destination: ObjectStore, local_root: str | Path,
    dry_run: bool = True, verify_only: bool = False, limit: int | None = None,
) -> MigrationReport:
    """Copy local attachment files into object storage, verifying each one.

    Never deletes, never overwrites a verified object, and never changes a row
    until the uploaded object has been read back and compared.
    """
    root = Path(local_root).resolve()
    report = MigrationReport(dry_run=dry_run, verify_only=verify_only,
                             destination_driver=destination.driver,
                             destination_bucket=destination.bucket)

    rows = list((await session.execute(
        select(ExperimentAttachment)
        .where(ExperimentAttachment.state != AttachmentState.DELETED)
        .order_by(ExperimentAttachment.id)
    )).scalars().all())
    if limit is not None:
        rows = rows[:limit]

    for row in rows:
        report.considered += 1
        entry: dict[str, object] = {
            "attachment_id": row.id,
            "organization_id": row.organization_id,
            "size_bytes": row.size_bytes,
            "state": row.state.value,
        }

        # Already there? Verify rather than re-upload. This is what makes a
        # rerun a no-op instead of a second copy under a new key.
        if (row.storage_backend == destination.driver
                and (row.storage_bucket or None)
                == (destination.bucket or None)
                and row.storage_key):
            try:
                metadata = destination.head(row.storage_key)
            except ObjectNotFound:
                metadata = None
            except StorageError as exc:
                report.failed.append({"attachment_id": row.id,
                                      "code": exc.code, "stage": "head"})
                entry["outcome"] = "storage_error"
                report.entries.append(entry)
                continue
            if metadata is not None and metadata.size_bytes == row.size_bytes:
                report.already_migrated += 1
                report.verified += 1
                entry["outcome"] = "already_migrated"
                report.entries.append(entry)
                continue

        source = _local_path(root, row.storage_key)
        if source is None:
            report.skipped_no_source.append(row.id)
            entry["outcome"] = "no_local_source"
            report.entries.append(entry)
            continue

        content = source.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        entry["checksum_matches_row"] = digest == row.checksum_sha256

        if digest != row.checksum_sha256:
            # The local file does not match what the row says it is. Migrating
            # it would carry a corruption forward and stamp it as verified.
            report.checksum_mismatch.append(row.id)
            entry["outcome"] = "checksum_mismatch"
            report.entries.append(entry)
            continue

        if verify_only:
            report.verified += 1
            entry["outcome"] = "verified_source_only"
            report.entries.append(entry)
            continue

        if dry_run:
            entry["outcome"] = "would_migrate"
            report.entries.append(entry)
            continue

        key = new_attachment_key(
            organization_id=row.organization_id or 0, attachment_id=row.id)
        try:
            destination.put(key, content, checksum_sha256=digest,
                            content_type=row.mime_type)
        except StorageError as exc:
            report.failed.append({"attachment_id": row.id, "code": exc.code,
                                  "stage": "upload"})
            entry["outcome"] = "upload_failed"
            report.entries.append(entry)
            continue

        # Read back before believing it. An upload that reported success and
        # stored nothing is rare and catastrophic; one extra head request per
        # file is a cheap way never to find out the hard way.
        try:
            metadata = destination.head(key)
        except (ObjectNotFound, StorageError) as exc:
            report.failed.append({"attachment_id": row.id,
                                  "code": getattr(exc, "code", "verify_failed"),
                                  "stage": "verify"})
            entry["outcome"] = "verify_failed"
            report.entries.append(entry)
            continue

        if (metadata.size_bytes != row.size_bytes
                or (metadata.checksum_sha256 or digest) != digest):
            report.failed.append({"attachment_id": row.id,
                                  "code": "post_upload_mismatch",
                                  "stage": "verify"})
            entry["outcome"] = "post_upload_mismatch"
            report.entries.append(entry)
            continue

        # Only now does the row change. Everything else about it — id,
        # relationships, filename, MIME type, size, checksum, timestamps,
        # audit references, provenance — is untouched.
        previous_key = row.storage_key
        row.storage_key = key
        row.storage_backend = destination.driver
        row.storage_bucket = destination.bucket
        await session.flush()

        report.migrated += 1
        report.verified += 1
        entry["outcome"] = "migrated"
        entry["previous_key_retained_locally"] = bool(previous_key)
        report.entries.append(entry)

    if not dry_run and not verify_only:
        report.notes.append(
            "Local originals were NOT deleted. Run cleanup_local_originals "
            "with an explicit root and confirm=True once you have verified "
            "the destination.")
    return report


def cleanup_local_originals(
    *, local_root: str | Path, keys: list[str], confirm: bool = False,
) -> dict[str, object]:
    """Delete migrated local files. Explicit path, explicit confirmation.

    Separate from the migration on purpose. The value of a migration you can
    rerun is that the source is still there, so removing the source is a
    decision taken afterwards by somebody who has checked — not a step that
    happens automatically while nobody is watching.
    """
    root = Path(local_root).resolve()
    if not root.is_dir():
        return {"confirmed": False, "deleted": 0,
                "message": f"No such directory: {root}"}

    planned: list[str] = []
    for key in keys:
        path = _local_path(root, key)
        if path is not None:
            planned.append(key)

    if not confirm:
        return {"confirmed": False, "deleted": 0, "planned": len(planned),
                "root": str(root),
                "message": (f"Dry run. {len(planned)} local file(s) would be "
                            f"removed from {root}; nothing was touched.")}

    deleted = 0
    for key in planned:
        path = _local_path(root, key)
        if path is None:
            continue
        try:
            path.unlink()
            deleted += 1
        except OSError as exc:
            log.warning("could not remove a migrated local original (%s)",
                        type(exc).__name__)
    return {"confirmed": True, "deleted": deleted, "planned": len(planned),
            "root": str(root),
            "message": f"Removed {deleted} migrated local file(s)."}
