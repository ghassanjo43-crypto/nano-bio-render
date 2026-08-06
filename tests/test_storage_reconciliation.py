"""Reconciliation and migration: finding the divergence, and moving files safely.

Two tools, one property
-----------------------
Both exist because the database and the object store can drift apart, and both
are built around the same rule: **report by default, destroy only when asked
explicitly, twice.**

Reconciliation is the diagnosis. Migration is a move that can be interrupted,
rerun and audited without losing a file. Neither deletes anything unless a
caller has passed an explicit list *and* a confirmation flag, because the first
time an automatic cleaner runs against a half-migrated deployment it deletes
every object the migration had not yet recorded.

The tests below therefore spend as much effort on what these tools *decline* to
do as on what they find.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.db.validation_models import (  # noqa: E402
    AttachmentState, ExperimentAttachment,
)
from nanobio_studio.app.storage.keys import new_attachment_key  # noqa: E402
from nanobio_studio.app.storage.local import LocalObjectStore  # noqa: E402
from nanobio_studio.app.storage.memory import InMemoryObjectStore  # noqa: E402
from nanobio_studio.app.storage.migrate import (  # noqa: E402
    cleanup_local_originals, migrate_attachments,
)
from nanobio_studio.app.storage.reconcile import (  # noqa: E402
    STUCK_AFTER, cleanup_orphan_objects, reconcile,
)

from tests.conftest import run_async  # noqa: E402

PAYLOAD = b"time_s,signal\n0,1.0\n1,0.5\n"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


async def _fresh_session():
    """A throwaway in-memory database with the validation tables."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    import nanobio_studio.app.db.auth_models  # noqa: F401
    import nanobio_studio.app.db.organization_models  # noqa: F401
    import nanobio_studio.app.db.validation_models  # noqa: F401
    import nanobio_studio.app.db.workspace_models  # noqa: F401
    from nanobio_studio.app.db.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, AsyncSession(engine, expire_on_commit=False)


def _row(**overrides) -> ExperimentAttachment:
    defaults = dict(
        organization_id=1, version_id=1,
        category="raw_data", original_filename="run.csv",
        mime_type="text/csv", size_bytes=len(PAYLOAD),
        checksum_sha256=DIGEST, storage_key="",
        storage_backend="s3", storage_bucket="test-bucket",
        state=AttachmentState.AVAILABLE,
        uploaded_at=datetime.now(timezone.utc))
    defaults.update(overrides)
    from nanobio_studio.app.validation.vocabulary import AttachmentCategory
    defaults["category"] = AttachmentCategory.RAW_DATA
    return ExperimentAttachment(**defaults)


# ===========================================================================
# 1. Reconciliation finds each kind of divergence
# ===========================================================================

class TestReconciliation:

    def test_a_consistent_pair_is_reported_healthy(self):
        """The positive control every other test in this class rests on."""
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                store.put(key, PAYLOAD, checksum_sha256=DIGEST)
                session.add(_row(storage_key=key))
                await session.commit()

                report = await reconcile(session, store=store)
                assert report.healthy, report.to_dict()
                assert report.checked_rows == 1
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_row_without_an_object_is_found(self):
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                store.put(key, PAYLOAD, checksum_sha256=DIGEST)
                session.add(_row(storage_key=key))
                await session.commit()
                store.vanish(key)

                report = await reconcile(session, store=store)
                assert report.rows_without_objects, report.to_dict()
                assert not report.healthy
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_marking_missing_is_opt_in_and_never_deletes(self):
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                store.put(key, PAYLOAD, checksum_sha256=DIGEST)
                row = _row(storage_key=key)
                session.add(row)
                await session.commit()
                store.vanish(key)

                # Default: reports, changes nothing.
                await reconcile(session, store=store)
                await session.refresh(row)
                assert row.state is AttachmentState.AVAILABLE

                report = await reconcile(session, store=store,
                                         mark_missing=True)
                await session.commit()
                await session.refresh(row)
                assert row.state is AttachmentState.MISSING
                assert report.marked_missing == [row.id]
                # The row itself survives — the metadata and provenance are
                # what make the gap investigable.
                assert row.checksum_sha256 == DIGEST
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_an_object_without_a_row_is_found(self):
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                orphan = new_attachment_key(organization_id=1,
                                            attachment_id=999)
                store.put(orphan, PAYLOAD, checksum_sha256=DIGEST)

                report = await reconcile(session, store=store)
                assert report.objects_without_rows == [orphan]
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_an_object_we_did_not_write_is_reported_separately(self):
        """Something else sharing the bucket is not ours to clean up."""
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                store._objects["att/not-a-key"] = store._objects.get(
                    "att/not-a-key")
                # Insert directly: the store's own put would refuse this key,
                # which is the point — it can only arrive from outside.
                from nanobio_studio.app.storage.memory import _Entry
                store._objects["att/someone-elses-thing"] = _Entry(
                    content=b"x", checksum_sha256="0" * 64,
                    last_modified=datetime.now(timezone.utc),
                    content_type=None)
                store._objects.pop("att/not-a-key", None)

                report = await reconcile(session, store=store)
                assert "att/someone-elses-thing" in \
                    report.unattributable_objects
                assert "att/someone-elses-thing" not in \
                    report.objects_without_rows
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_size_mismatch_is_found(self):
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                store.put(key, PAYLOAD, checksum_sha256=DIGEST)
                session.add(_row(storage_key=key, size_bytes=999_999))
                await session.commit()

                report = await reconcile(session, store=store)
                assert report.size_mismatches
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_checksum_mismatch_is_found(self):
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                store.put(key, PAYLOAD, checksum_sha256=DIGEST)
                session.add(_row(storage_key=key, checksum_sha256="f" * 64))
                await session.commit()

                report = await reconcile(session, store=store)
                assert report.checksum_mismatches
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_deep_check_catches_tampering_the_metadata_hides(self):
        """The store's recorded digest can be stale. The bytes cannot lie."""
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                store.put(key, PAYLOAD, checksum_sha256=DIGEST)
                session.add(_row(storage_key=key))
                await session.commit()

                # Replace the bytes, leaving the recorded checksum alone.
                store.corrupt(key, b"tampered")

                shallow = await reconcile(session, store=store)
                assert not shallow.checksum_mismatches, (
                    "head reports the store's recorded digest, which is stale")
                assert shallow.size_mismatches, "the size does give it away"

                deep = await reconcile(session, store=store, deep=True)
                assert deep.checksum_mismatches
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_row_in_a_different_container_is_reported_not_checked(self):
        """A half-finished migration is a finding, not a corruption."""
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="new-bucket", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                session.add(_row(storage_key=key, storage_bucket="old-bucket"))
                await session.commit()

                report = await reconcile(session, store=store)
                assert report.wrong_container
                assert not report.rows_without_objects, (
                    "it must not be reported as missing from a store it was "
                    "never written to")
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_row_stuck_in_a_transitional_state_is_found(self):
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                stale = datetime.now(timezone.utc) - STUCK_AFTER - timedelta(
                    minutes=5)
                session.add(_row(state=AttachmentState.PENDING_UPLOAD,
                                 state_changed_at=stale))
                await session.commit()

                report = await reconcile(session, store=store)
                assert report.stuck_in_transition
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_recent_transitional_row_is_not_a_finding(self):
        """A slow upload is not a fault, and reporting it as one trains
        operators to ignore the report."""
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                session.add(_row(state=AttachmentState.PENDING_UPLOAD,
                                 state_changed_at=datetime.now(timezone.utc)))
                await session.commit()

                report = await reconcile(session, store=store)
                assert not report.stuck_in_transition
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_deliberately_deleted_row_is_not_a_finding(self):
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                session.add(_row(state=AttachmentState.DELETED,
                                 storage_key=new_attachment_key(
                                     organization_id=1, attachment_id=1)))
                await session.commit()

                report = await reconcile(session, store=store)
                assert report.healthy, report.to_dict()
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_the_report_carries_no_filename_or_clinical_content(self):
        """It ends up in tickets and chat. Identifiers are enough."""
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                session.add(_row(
                    original_filename="jane-doe-carcinoma-biopsy.csv",
                    storage_key=new_attachment_key(organization_id=1,
                                                   attachment_id=1)))
                await session.commit()

                report = await reconcile(session, store=store)
                serialised = json.dumps(report.to_dict())
                for leak in ("jane", "doe", "carcinoma", "biopsy"):
                    assert leak not in serialised.lower()
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())


# ===========================================================================
# 2. Cleanup refuses by default, and refuses what is not ours
# ===========================================================================

class TestOrphanCleanup:

    def test_without_confirmation_nothing_is_deleted(self):
        store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
        key = new_attachment_key(organization_id=1, attachment_id=1)
        store.put(key, PAYLOAD, checksum_sha256=DIGEST)

        result = cleanup_orphan_objects(store=store, keys=[key])
        assert result["confirmed"] is False
        assert result["deleted"] == 0
        assert store.exists(key), "a dry run must touch nothing"

    def test_with_confirmation_the_named_objects_go(self):
        store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
        key = new_attachment_key(organization_id=1, attachment_id=1)
        store.put(key, PAYLOAD, checksum_sha256=DIGEST)

        result = cleanup_orphan_objects(store=store, keys=[key], confirm=True)
        assert result["deleted"] == 1
        assert not store.exists(key)

    def test_an_object_we_did_not_write_is_refused(self):
        """If something else shares the bucket, its objects are not ours."""
        store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
        result = cleanup_orphan_objects(
            store=store, keys=["some/other/system/file.txt"], confirm=True)
        assert result["deleted"] == 0
        assert result["refused_not_ours"] == ["some/other/system/file.txt"]

    def test_there_is_no_way_to_ask_for_all_orphans(self):
        """The enumerating function does not delete; this one does not
        enumerate. That separation is the safety property."""
        import inspect

        signature = inspect.signature(cleanup_orphan_objects)
        assert "keys" in signature.parameters
        assert "prefix" not in signature.parameters
        assert "all" not in signature.parameters
        source = inspect.getsource(cleanup_orphan_objects)
        assert "list_keys" not in source


# ===========================================================================
# 3. Migration: verified before authoritative, and rerunnable
# ===========================================================================

class TestMigration:

    def _seed_local(self, root: Path, key: str) -> Path:
        path = root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PAYLOAD)
        return path

    def test_a_dry_run_changes_nothing(self, tmp_path):
        async def scenario():
            engine, session = await _fresh_session()
            destination = InMemoryObjectStore(bucket="new", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                self._seed_local(tmp_path, key)
                row = _row(storage_key=key, storage_backend="local",
                           storage_bucket=None)
                session.add(row)
                await session.commit()

                report = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path)
                assert report.dry_run is True
                assert report.migrated == 0
                assert not list(destination.list_keys())
                await session.refresh(row)
                assert row.storage_backend == "local"
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_applying_uploads_verifies_and_repoints(self, tmp_path):
        async def scenario():
            engine, session = await _fresh_session()
            destination = InMemoryObjectStore(bucket="new", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                source = self._seed_local(tmp_path, key)
                row = _row(storage_key=key, storage_backend="local",
                           storage_bucket=None)
                session.add(row)
                await session.commit()

                report = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path,
                    dry_run=False)
                await session.commit()

                assert report.migrated == 1, report.to_dict()
                assert report.ok
                await session.refresh(row)
                assert row.storage_backend == "s3"
                assert row.storage_bucket == "new"
                assert destination.get(row.storage_key) == PAYLOAD

                # Everything else about the row is untouched.
                assert row.original_filename == "run.csv"
                assert row.checksum_sha256 == DIGEST
                assert row.size_bytes == len(PAYLOAD)

                # And the original is still there.
                assert source.is_file(), (
                    "the value of a rerunnable migration is that the source "
                    "survives it")
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_rerunning_does_not_duplicate(self, tmp_path):
        async def scenario():
            engine, session = await _fresh_session()
            destination = InMemoryObjectStore(bucket="new", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                self._seed_local(tmp_path, key)
                session.add(_row(storage_key=key, storage_backend="local",
                                 storage_bucket=None))
                await session.commit()

                await migrate_attachments(session, destination=destination,
                                          local_root=tmp_path, dry_run=False)
                await session.commit()
                after_first = list(destination.list_keys())

                second = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path,
                    dry_run=False)
                await session.commit()

                assert second.migrated == 0
                assert second.already_migrated == 1
                assert list(destination.list_keys()) == after_first
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_an_interrupted_run_resumes(self, tmp_path):
        """The second row is migrated without touching the first."""
        async def scenario():
            engine, session = await _fresh_session()
            destination = InMemoryObjectStore(bucket="new", driver="s3")
            try:
                for attachment_id in (1, 2):
                    key = new_attachment_key(organization_id=1,
                                             attachment_id=attachment_id)
                    self._seed_local(tmp_path, key)
                    session.add(_row(storage_key=key, storage_backend="local",
                                     storage_bucket=None))
                await session.commit()

                # Interrupt: migrate only the first.
                first = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path,
                    dry_run=False, limit=1)
                await session.commit()
                assert first.migrated == 1

                resumed = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path,
                    dry_run=False)
                await session.commit()
                assert resumed.migrated == 1
                assert resumed.already_migrated == 1
                assert len(list(destination.list_keys())) == 2
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_corrupt_local_file_is_not_migrated(self, tmp_path):
        """Migrating it would carry the corruption forward as verified."""
        async def scenario():
            engine, session = await _fresh_session()
            destination = InMemoryObjectStore(bucket="new", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                path = self._seed_local(tmp_path, key)
                path.write_bytes(b"not what the row says")
                session.add(_row(storage_key=key, storage_backend="local",
                                 storage_bucket=None))
                await session.commit()

                report = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path,
                    dry_run=False)
                assert report.checksum_mismatch
                assert report.migrated == 0
                assert not report.ok
                assert not list(destination.list_keys())
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_an_upload_failure_leaves_the_row_pointing_at_the_original(
            self, tmp_path):
        async def scenario():
            engine, session = await _fresh_session()
            destination = InMemoryObjectStore(bucket="new", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                self._seed_local(tmp_path, key)
                row = _row(storage_key=key, storage_backend="local",
                           storage_bucket=None)
                session.add(row)
                await session.commit()

                destination.fail_next_put = "storage_unavailable"
                report = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path,
                    dry_run=False)

                assert report.failed and report.migrated == 0
                await session.refresh(row)
                assert row.storage_backend == "local"
                assert row.storage_key == key
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_verify_only_reads_and_writes_nothing(self, tmp_path):
        async def scenario():
            engine, session = await _fresh_session()
            destination = InMemoryObjectStore(bucket="new", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                self._seed_local(tmp_path, key)
                session.add(_row(storage_key=key, storage_backend="local",
                                 storage_bucket=None))
                await session.commit()

                report = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path,
                    dry_run=False, verify_only=True)
                assert report.verified == 1
                assert report.migrated == 0
                assert not list(destination.list_keys())
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_missing_local_file_is_reported_not_skipped_silently(
            self, tmp_path):
        async def scenario():
            engine, session = await _fresh_session()
            destination = InMemoryObjectStore(bucket="new", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                session.add(_row(storage_key=key, storage_backend="local",
                                 storage_bucket=None))
                await session.commit()

                report = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path,
                    dry_run=False)
                assert report.skipped_no_source
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_the_manifest_carries_no_filename_or_clinical_content(
            self, tmp_path):
        async def scenario():
            engine, session = await _fresh_session()
            destination = InMemoryObjectStore(bucket="new", driver="s3")
            try:
                key = new_attachment_key(organization_id=1, attachment_id=1)
                self._seed_local(tmp_path, key)
                session.add(_row(
                    storage_key=key, storage_backend="local",
                    storage_bucket=None,
                    original_filename="jane-doe-carcinoma.csv"))
                await session.commit()

                report = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path,
                    dry_run=False)
                await session.commit()

                manifest = tmp_path / "manifest.json"
                report.write(manifest)
                text = manifest.read_text(encoding="utf-8").lower()
                for leak in ("jane", "doe", "carcinoma"):
                    assert leak not in text
                # But it does carry what an operator needs.
                assert "attachment_id" in text
                assert "outcome" in text
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())


# ===========================================================================
# 4. Local originals are removed only on purpose
# ===========================================================================

class TestLocalCleanup:

    def test_without_confirmation_nothing_is_removed(self, tmp_path):
        key = new_attachment_key(organization_id=1, attachment_id=1)
        path = tmp_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PAYLOAD)

        result = cleanup_local_originals(local_root=tmp_path, keys=[key])
        assert result["confirmed"] is False
        assert path.is_file()

    def test_with_confirmation_the_named_originals_go(self, tmp_path):
        key = new_attachment_key(organization_id=1, attachment_id=1)
        path = tmp_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PAYLOAD)

        result = cleanup_local_originals(local_root=tmp_path, keys=[key],
                                         confirm=True)
        assert result["deleted"] == 1
        assert not path.exists()

    def test_a_path_outside_the_root_is_not_followed(self, tmp_path):
        outside = tmp_path.parent / "outside.txt"
        outside.write_bytes(b"do not touch")
        try:
            result = cleanup_local_originals(
                local_root=tmp_path, keys=["../outside.txt"], confirm=True)
            assert result["deleted"] == 0
            assert outside.is_file()
        finally:
            outside.unlink(missing_ok=True)

    def test_migration_never_calls_the_cleanup_itself(self):
        """Separate commands, so the source survives a bad migration.

        Checked against the parsed call graph rather than the source text: the
        migration's closing note *mentions* the cleanup command by name, which
        is exactly what an operator needs to read and exactly what a substring
        search would trip over.
        """
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(migrate_attachments))
        called = {
            node.func.id if isinstance(node.func, ast.Name)
            else getattr(node.func, "attr", "")
            for node in ast.walk(tree) if isinstance(node, ast.Call)
        }
        assert "cleanup_local_originals" not in called
        assert "unlink" not in called
        assert "rmtree" not in called
        assert "remove" not in called


class TestLegacyKeyFormat:
    """Rows written before the opaque-key format.

    Found by running the reconciliation command against a real installation:
    an old flat 32-hex key made ``head`` raise ``invalid_key``, which the
    report surfaced as "storage unavailable while checking row N". That reads
    like an incident. It is a migration backlog, and it now says so.
    """

    def test_a_legacy_key_is_reported_as_a_backlog_not_an_outage(self):
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                session.add(_row(storage_key="a" * 32))
                await session.commit()

                report = await reconcile(session, store=store)
                assert report.legacy_key_format, report.to_dict()
                assert not report.notes, (
                    "a pre-migration row must not be reported as a storage "
                    "outage")
                assert not report.rows_without_objects, (
                    "nor as a missing object — nobody has looked for it yet")
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_a_migration_backlog_does_not_make_the_report_unhealthy(self):
        """A report that is always red stops being read."""
        async def scenario():
            engine, session = await _fresh_session()
            store = InMemoryObjectStore(bucket="test-bucket", driver="s3")
            try:
                session.add(_row(storage_key="b" * 32))
                await session.commit()

                report = await reconcile(session, store=store)
                assert report.healthy
                assert "awaiting key migration" in report.summary()
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())

    def test_the_migration_command_resolves_a_legacy_key(self, tmp_path):
        """The backlog has a command, and it clears the finding."""
        async def scenario():
            engine, session = await _fresh_session()
            destination = InMemoryObjectStore(bucket="new", driver="s3")
            try:
                legacy = "c" * 32
                # The old sharded layout: first two characters as a directory.
                path = tmp_path / legacy[:2] / legacy
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(PAYLOAD)

                row = _row(storage_key=legacy, storage_backend="local",
                           storage_bucket=None)
                session.add(row)
                await session.commit()

                report = await migrate_attachments(
                    session, destination=destination, local_root=tmp_path,
                    dry_run=False)
                await session.commit()
                assert report.migrated == 1, report.to_dict()

                after = await reconcile(session, store=destination)
                assert not after.legacy_key_format
                assert after.healthy, after.to_dict()
            finally:
                await session.close()
                await engine.dispose()

        run_async(scenario())
