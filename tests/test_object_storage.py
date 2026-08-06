"""The object-storage layer, its lifecycle, and the ways it can go wrong.

What this file is really testing
--------------------------------
Not "can we write a file and read it back". That works in every implementation
anybody ever ships. What breaks in production is the seam between two systems:
the object store succeeds and the database rolls back; the database commits and
the object store was never reached; a lifecycle rule eats an object nobody
notices for a month; a retried upload overwrites a finalised one; a delete
reports success while the bytes remain.

Every one of those is unreachable against a filesystem that always works, which
is why ``InMemoryObjectStore`` can be told to fail. It is a real implementation
of the interface — it validates keys, verifies checksums, distinguishes absent
from unreachable — with injectable faults, so a test that passes against it is
evidence about the *contract* rather than about a mock.

The suite runs against both drivers
-----------------------------------
``local`` and the S3-compatible in-memory store, parametrised, because a
contract only one implementation satisfies is not a contract. No live cloud
credentials are needed or accepted: a test that requires an AWS account is a
test that stops being run.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.storage.keys import (  # noqa: E402
    InvalidObjectKey, is_valid_key, new_attachment_key, parse_key,
)
from nanobio_studio.app.storage.local import LocalObjectStore  # noqa: E402
from nanobio_studio.app.storage.memory import InMemoryObjectStore  # noqa: E402
from nanobio_studio.app.storage.objects import (  # noqa: E402
    ObjectMetadata, ObjectNotFound, ObjectStore, StorageError,
    StorageNotConfigured,
)

PAYLOAD = b"time_s,signal\n0,1.0\n1,0.5\n"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()

KEY = "att/3/17/" + "a" * 32
OTHER_KEY = "att/3/18/" + "b" * 32


@pytest.fixture(params=["local", "s3-compatible"])
def store(request, tmp_path) -> ObjectStore:
    """Both drivers, same assertions.

    A contract that only one implementation satisfies is not a contract, and
    the local driver is the one nobody will run in production.
    """
    if request.param == "local":
        return LocalObjectStore(tmp_path)
    return InMemoryObjectStore(bucket="test-bucket", driver="s3")


# ===========================================================================
# 1. Keys carry nothing
# ===========================================================================

class TestObjectKeys:

    def test_a_key_is_built_from_integers_and_random_bytes(self):
        key = new_attachment_key(organization_id=12, attachment_id=345)
        assert key.startswith("att/12/345/")
        token = key.rsplit("/", 1)[-1]
        assert len(token) == 32 and all(c in "0123456789abcdef" for c in token)

    @pytest.mark.parametrize("sensitive", [
        "Jane Doe", "jane@example.test", "invasive ductal carcinoma",
        "results-2026.csv", "Acme Clinical Research", "CAND-014",
        "NHS1234567890",
    ])
    def test_no_sensitive_string_can_reach_a_key(self, sensitive):
        """The signature is the enforcement: it takes integers only."""
        key = new_attachment_key(organization_id=1, attachment_id=1)
        assert sensitive.lower() not in key.lower()
        # And there is no parameter through which one could be passed.
        with pytest.raises(TypeError):
            new_attachment_key(organization_id=1, attachment_id=1,
                               filename=sensitive)

    def test_two_keys_for_the_same_record_differ(self):
        """What makes a retried upload safe rather than an overwrite."""
        first = new_attachment_key(organization_id=1, attachment_id=1)
        second = new_attachment_key(organization_id=1, attachment_id=1)
        assert first != second

    @pytest.mark.parametrize("bad", [
        "", "../../etc/passwd", "att/1/1", "att/1/1/short",
        "att/1/1/" + "Z" * 32, "xxx/1/1/" + "a" * 32,
        "/att/1/1/" + "a" * 32, "att/1/1/" + "a" * 33,
        "att/x/1/" + "a" * 32,
    ])
    def test_a_key_this_application_did_not_generate_is_refused(self, bad):
        assert not is_valid_key(bad)
        with pytest.raises(InvalidObjectKey):
            parse_key(bad)

    def test_a_key_is_traceable_back_to_its_row(self):
        """The operational reason the identifiers are in there at all."""
        parsed = parse_key(new_attachment_key(organization_id=9,
                                              attachment_id=41))
        assert parsed.organization_id == 9
        assert parsed.record_id == 41


# ===========================================================================
# 2. The contract, on both drivers
# ===========================================================================

class TestTheObjectStoreContract:

    def test_put_then_get_round_trips(self, store):
        metadata = store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        assert metadata.size_bytes == len(PAYLOAD)
        assert metadata.checksum_sha256 == DIGEST
        assert store.get(KEY) == PAYLOAD

    def test_streaming_yields_the_same_bytes_in_chunks(self, store):
        store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        chunks = list(store.open_stream(KEY, chunk_bytes=4))
        assert len(chunks) > 1, "the point of streaming is more than one chunk"
        assert b"".join(chunks) == PAYLOAD

    def test_head_reports_metadata_without_the_body(self, store):
        store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        metadata = store.head(KEY)
        assert isinstance(metadata, ObjectMetadata)
        assert metadata.size_bytes == len(PAYLOAD)
        assert metadata.checksum_sha256 == DIGEST

    def test_exists_is_a_boolean_and_never_raises_for_absence(self, store):
        assert store.exists(KEY) is False
        store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        assert store.exists(KEY) is True

    def test_copy_duplicates_without_touching_the_source(self, store):
        store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        metadata = store.copy(KEY, OTHER_KEY)
        assert metadata.size_bytes == len(PAYLOAD)
        assert store.get(OTHER_KEY) == PAYLOAD
        assert store.get(KEY) == PAYLOAD, "the source must survive a copy"

    def test_delete_reports_whether_it_was_there_and_is_idempotent(self, store):
        store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        assert store.delete(KEY) is True
        assert store.delete(KEY) is False
        with pytest.raises(ObjectNotFound):
            store.get(KEY)

    def test_a_missing_object_raises_object_not_found(self, store):
        with pytest.raises(ObjectNotFound):
            store.head(KEY)
        with pytest.raises(ObjectNotFound):
            list(store.open_stream(KEY))

    def test_a_checksum_mismatch_writes_nothing(self, store):
        with pytest.raises(StorageError) as exc:
            store.put(KEY, PAYLOAD, checksum_sha256="0" * 64)
        assert exc.value.code == "checksum_mismatch"
        assert store.exists(KEY) is False

    def test_an_invalid_key_is_refused_by_every_operation(self, store):
        for operation in (lambda: store.put("../x", PAYLOAD,
                                            checksum_sha256=DIGEST),
                          lambda: store.head("../x"),
                          lambda: list(store.open_stream("../x"))):
            with pytest.raises(StorageError) as exc:
                operation()
            assert exc.value.code == "invalid_key"

    def test_health_reports_without_raising(self, store):
        health = store.health()
        assert health.healthy is True
        assert health.driver in {"local", "s3"}

    def test_an_empty_object_round_trips(self, store):
        """Zero bytes is a legitimate object at this layer.

        Refusing empty *uploads* is the validator's job, one layer up, where
        there is a user to tell. A store that could not represent an empty
        object would be a store with a hole in it.
        """
        empty_digest = hashlib.sha256(b"").hexdigest()
        store.put(KEY, b"", checksum_sha256=empty_digest)
        assert store.get(KEY) == b""
        assert store.head(KEY).size_bytes == 0

    def test_a_large_object_within_the_limit_round_trips(self, store):
        payload = b"x" * (2 * 1024 * 1024)
        digest = hashlib.sha256(payload).hexdigest()
        store.put(KEY, payload, checksum_sha256=digest)
        assert store.head(KEY).size_bytes == len(payload)
        assert sum(len(c) for c in store.open_stream(KEY)) == len(payload)

    def test_no_provider_object_escapes_the_layer(self, store):
        """The claim that keeps the backing store swappable."""
        metadata = store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        for value in (metadata.key, metadata.checksum_sha256):
            assert isinstance(value, (str, type(None)))
        module = type(metadata).__module__
        assert module.startswith("nanobio_studio."), module
        # No filesystem location in anything a caller can see.
        assert "\\" not in metadata.key
        assert not metadata.key.startswith("/")


# ===========================================================================
# 3. The failure modes that only exist between two systems
# ===========================================================================

class TestInjectedFailures:

    def test_an_upload_failure_leaves_nothing_behind(self):
        store = InMemoryObjectStore()
        store.fail_next_put = "storage_unavailable"
        with pytest.raises(StorageError) as exc:
            store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        assert exc.value.code == "storage_unavailable"
        assert store.exists(KEY) is False

        # Positive control: the very next attempt succeeds, so the injected
        # failure was the cause rather than the store being broken.
        store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        assert store.exists(KEY) is True

    def test_a_download_failure_is_distinguishable_from_absence(self):
        """An outage is not a missing object, and must not read as one."""
        store = InMemoryObjectStore()
        store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        store.fail_next_get = "storage_unavailable"

        with pytest.raises(StorageError):
            list(store.open_stream(KEY))
        # Not ObjectNotFound — the object is still there.
        assert store.exists(KEY) is True

    def test_a_delete_failure_leaves_the_object_in_place(self):
        store = InMemoryObjectStore()
        store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        store.fail_next_delete = "storage_delete_failed"
        with pytest.raises(StorageError):
            store.delete(KEY)
        assert store.exists(KEY) is True, (
            "a failed delete must not look like a successful one")

    def test_an_object_can_vanish_without_the_database_knowing(self):
        """A lifecycle rule, a console mistake, a bucket policy."""
        store = InMemoryObjectStore()
        store.put(KEY, PAYLOAD, checksum_sha256=DIGEST)
        store.vanish(KEY)
        assert store.exists(KEY) is False


# ===========================================================================
# 4. Configuration
# ===========================================================================

class TestConfiguration:

    def test_the_default_driver_is_local(self):
        from nanobio_studio.app.core.config import settings
        assert settings.storage_driver == "local"

    def test_s3_without_a_bucket_refuses_to_start(self):
        """Loudly, at startup, naming what is missing.

        The alternative is the failure this check exists to prevent: the
        application comes up, accepts uploads, and writes them to a container
        filesystem that the next deploy discards.
        """
        from nanobio_studio.app.core.config import settings
        from nanobio_studio.app.storage import factory

        original = (settings.storage_driver, settings.storage_bucket)
        try:
            settings.storage_driver = "s3"
            settings.storage_bucket = ""
            factory.reset_object_store()
            with pytest.raises(StorageNotConfigured) as exc:
                factory.object_store()
        finally:
            settings.storage_driver, settings.storage_bucket = original
            factory.reset_object_store()
        assert "STORAGE_BUCKET" in str(exc.value)

    def test_an_unknown_driver_is_refused_rather_than_defaulted(self):
        from nanobio_studio.app.core.config import settings
        from nanobio_studio.app.storage import factory

        original = settings.storage_driver
        try:
            settings.storage_driver = "gdrive"
            factory.reset_object_store()
            with pytest.raises(StorageNotConfigured) as exc:
                factory.object_store()
        finally:
            settings.storage_driver = original
            factory.reset_object_store()
        assert "local, s3" in str(exc.value)

    def test_the_description_carries_no_credential_or_endpoint(self):
        """A diagnostics payload is read by more people than a secret store."""
        from nanobio_studio.app.core.config import settings
        from nanobio_studio.app.storage import describe_storage

        original = (settings.storage_endpoint_url,
                    settings.storage_access_key_id,
                    settings.storage_secret_access_key)
        try:
            settings.storage_endpoint_url = "https://secret.example.internal"
            settings.storage_access_key_id = "AKIAEXAMPLEKEYID"
            settings.storage_secret_access_key = "super-secret-value"
            described = repr(describe_storage())
        finally:
            (settings.storage_endpoint_url, settings.storage_access_key_id,
             settings.storage_secret_access_key) = original

        assert "secret.example.internal" not in described
        assert "AKIAEXAMPLEKEYID" not in described
        assert "super-secret-value" not in described

    def test_malware_scanning_is_reported_as_off_rather_than_implied_on(self):
        from nanobio_studio.app.storage import describe_storage

        scanning = describe_storage()["malware_scanning"]
        assert scanning["enabled"] is False
        assert "not scanned for malware" in scanning["notice"]

    def test_no_presigned_url_is_issued(self):
        """Stated in the diagnostics, so nobody has to read the code."""
        from nanobio_studio.app.storage import describe_storage

        presigned = describe_storage()["presigned_urls"]
        assert presigned["issued"] is False
        assert "bearer credential" in presigned["notice"]

    def test_the_env_example_carries_no_real_endpoint_or_secret(self):
        text = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("STORAGE_SECRET_ACCESS_KEY="):
                assert line.strip() == "STORAGE_SECRET_ACCESS_KEY="
            if line.startswith("STORAGE_ACCESS_KEY_ID="):
                assert line.strip() == "STORAGE_ACCESS_KEY_ID="
            if line.startswith("STORAGE_ENDPOINT_URL="):
                assert line.strip() == "STORAGE_ENDPOINT_URL="
        # Placeholder, not a real bucket somebody owns.
        assert "STORAGE_BUCKET=your-bucket-name" in text

    def test_the_s3_driver_is_importable_without_boto3_installed(self):
        """The package must import on a machine that has never seen boto3.

        The import is inside the constructor for exactly this reason: a test
        suite that cannot be collected without a cloud SDK is a test suite that
        stops being run.
        """
        import importlib
        module = importlib.import_module("nanobio_studio.app.storage.s3")
        assert hasattr(module, "S3ObjectStore")
