"""An in-memory object store that behaves like an S3-compatible one.

Why this exists rather than a mock
----------------------------------
A ``unittest.mock`` standing in for the store passes whatever the test asserts,
including things the real store would refuse. This is a genuine implementation
of the interface — it validates keys, verifies checksums, distinguishes absent
from unreachable, and reports the same metadata — so a test that passes against
it is evidence about the *contract*, not about the mock.

It also makes the failure modes reachable, which is the point. A real object
store fails after the database has been written, or succeeds while the database
transaction is rolling back, or loses an object between two requests. Those are
the paths the lifecycle exists to survive and they are unreachable against a
filesystem that always works. So this store can be told to fail:

* ``fail_next_put`` / ``fail_next_get`` / ``fail_next_delete`` — one injected
  failure, consumed on use;
* ``vanish(key)`` — remove the object without touching the database, which is
  exactly what an operator's mistaken lifecycle rule looks like;
* ``corrupt(key)`` — replace the bytes, leaving the recorded checksum stale.

Not for production, and not registered as a selectable driver in configuration.
It is constructed only by tests and by the S3-compatible walkthrough harness.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from nanobio_studio.app.storage.keys import is_valid_key
from nanobio_studio.app.storage.objects import (
    DEFAULT_CHUNK_BYTES, ObjectMetadata, ObjectNotFound, ObjectStore,
    StorageError, StorageHealth,
)

__all__ = ["InMemoryObjectStore"]


@dataclass
class _Entry:
    content: bytes
    checksum_sha256: str
    last_modified: datetime
    content_type: str | None


class InMemoryObjectStore(ObjectStore):
    #: Reports itself as ``s3`` on purpose when asked to.
    #:
    #: The attachment row records which driver wrote it, and a test that wants
    #: to prove the *S3-compatible* path works needs the row to say so. The
    #: default is honest about what it is.
    driver = "memory"

    def __init__(self, *, bucket: str | None = "test-bucket",
                 driver: str = "memory") -> None:
        self._objects: dict[str, _Entry] = {}
        self.bucket = bucket
        self.driver = driver
        self.fail_next_put: str | None = None
        self.fail_next_get: str | None = None
        self.fail_next_delete: str | None = None
        self.fail_health = False
        #: Every operation, for tests that assert what the layer actually did.
        self.calls: list[tuple[str, str]] = []

    # -- test seams -------------------------------------------------------

    def vanish(self, key: str) -> None:
        """Lose an object without telling the database. A lifecycle mistake."""
        self._objects.pop(key, None)

    def corrupt(self, key: str, content: bytes = b"tampered") -> None:
        """Replace the bytes, leaving the recorded checksum stale."""
        entry = self._objects.get(key)
        if entry is not None:
            entry.content = content

    def _maybe_fail(self, attribute: str, operation: str) -> None:
        code = getattr(self, attribute)
        if code:
            setattr(self, attribute, None)
            raise StorageError(code, f"Injected {operation} failure.")

    # -- operations -------------------------------------------------------

    def put(self, key: str, content: bytes, *, checksum_sha256: str,
            content_type: str | None = None) -> ObjectMetadata:
        self.calls.append(("put", key))
        if not is_valid_key(key):
            raise StorageError("invalid_key", "The object key is not valid.")
        self._maybe_fail("fail_next_put", "upload")

        actual = hashlib.sha256(content).hexdigest()
        if actual != checksum_sha256:
            raise StorageError(
                "checksum_mismatch",
                "The content does not match its checksum. Nothing was written.")

        self._objects[key] = _Entry(
            content=content, checksum_sha256=actual,
            last_modified=datetime.now(timezone.utc),
            content_type=content_type)
        return ObjectMetadata(key=key, size_bytes=len(content),
                              checksum_sha256=actual,
                              last_modified=self._objects[key].last_modified,
                              bucket=self.bucket)

    def open_stream(self, key: str, *,
                    chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> Iterator[bytes]:
        self.calls.append(("get", key))
        if not is_valid_key(key):
            raise StorageError("invalid_key", "The object key is not valid.")
        self._maybe_fail("fail_next_get", "download")
        entry = self._objects.get(key)
        if entry is None:
            raise ObjectNotFound(key)
        content = entry.content

        def chunks() -> Iterator[bytes]:
            for start in range(0, len(content), chunk_bytes):
                yield content[start:start + chunk_bytes]

        return chunks()

    def head(self, key: str) -> ObjectMetadata:
        self.calls.append(("head", key))
        if not is_valid_key(key):
            raise StorageError("invalid_key", "The object key is not valid.")
        entry = self._objects.get(key)
        if entry is None:
            raise ObjectNotFound(key)
        return ObjectMetadata(key=key, size_bytes=len(entry.content),
                              checksum_sha256=entry.checksum_sha256,
                              last_modified=entry.last_modified,
                              bucket=self.bucket)

    def exists(self, key: str) -> bool:
        self.calls.append(("exists", key))
        return is_valid_key(key) and key in self._objects

    def copy(self, source_key: str, destination_key: str) -> ObjectMetadata:
        self.calls.append(("copy", source_key))
        entry = self._objects.get(source_key)
        if entry is None:
            raise ObjectNotFound(source_key)
        if not is_valid_key(destination_key):
            raise StorageError("invalid_key", "The object key is not valid.")
        self._objects[destination_key] = _Entry(
            content=entry.content, checksum_sha256=entry.checksum_sha256,
            last_modified=datetime.now(timezone.utc),
            content_type=entry.content_type)
        return self.head(destination_key)

    def delete(self, key: str) -> bool:
        self.calls.append(("delete", key))
        self._maybe_fail("fail_next_delete", "delete")
        return self._objects.pop(key, None) is not None

    def health(self) -> StorageHealth:
        if self.fail_health:
            return StorageHealth(healthy=False, driver=self.driver,
                                 bucket=self.bucket,
                                 detail="storage_unavailable")
        return StorageHealth(healthy=True, driver=self.driver,
                             bucket=self.bucket,
                             detail="in-memory test store", latency_ms=0.0)

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        for key in sorted(self._objects):
            if key.startswith(prefix):
                yield key
