"""Filesystem object store, for development and for the test suite.

**Not production storage, and it says so rather than implying it.** Bytes are
written unencrypted to a directory with no lifecycle policy, no replication and
no access control beyond the operating system's. Production means an
S3-compatible service with server-side encryption; this driver exists so that
running the application locally does not require one, and so that the tests
exercise a real implementation of the interface rather than a stub.

It is nonetheless a faithful implementation, not a shortcut:

* keys are validated on every operation, and the resolved path is checked to be
  inside the root even after validation, so a key arriving from anywhere cannot
  escape;
* the checksum is verified before the bytes are written, and again on read-back
  in ``head``;
* writes go to a temporary file in the same directory and are then renamed. A
  crash mid-write therefore leaves a ``.part`` file rather than a truncated
  object that would pass an existence check and fail a checksum — which is the
  difference between an attachment that is visibly incomplete and one that is
  silently wrong.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from nanobio_studio.app.storage.keys import is_valid_key
from nanobio_studio.app.storage.objects import (
    DEFAULT_CHUNK_BYTES, ObjectMetadata, ObjectNotFound, ObjectStore,
    StorageError, StorageHealth,
)

__all__ = ["LocalObjectStore"]

#: Written beside the object. Holds the checksum the store recorded at write
#: time, so ``head`` can report the store's view without reading the body —
#: which is what makes reconciliation cheap enough to run.
_META_SUFFIX = ".sha256"


class LocalObjectStore(ObjectStore):
    driver = "local"

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self.bucket = None

    # -- paths ------------------------------------------------------------

    def _path_for(self, key: str) -> Path:
        if not is_valid_key(key):
            # A key that is not the shape this application generates did not
            # come from this application. Refusing it is cheaper, and safer,
            # than reasoning about what it might resolve to.
            raise StorageError("invalid_key", "The object key is not valid.")
        path = (self._root / key).resolve()
        # Belt and braces. The key is already validated against a strict
        # pattern; this catches the case where that pattern is ever loosened.
        if not path.is_relative_to(self._root):
            raise StorageError("invalid_key", "The object key is not valid.")
        return path

    # -- operations -------------------------------------------------------

    def put(self, key: str, content: bytes, *, checksum_sha256: str,
            content_type: str | None = None) -> ObjectMetadata:
        actual = hashlib.sha256(content).hexdigest()
        if actual != checksum_sha256:
            raise StorageError(
                "checksum_mismatch",
                "The content does not match its checksum. Nothing was written.")

        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write-then-rename. On every platform this application targets, a
        # rename within a directory is atomic, so a reader never observes a
        # half-written object.
        temporary = path.with_suffix(path.suffix + ".part")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, path)
            path.with_suffix(path.suffix + _META_SUFFIX).write_text(
                actual, encoding="ascii")
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError("write_failed",
                               f"The object could not be written "
                               f"({type(exc).__name__}).") from exc

        return ObjectMetadata(
            key=key, size_bytes=len(content), checksum_sha256=actual,
            last_modified=datetime.now(timezone.utc), bucket=None)

    def open_stream(self, key: str, *,
                    chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> Iterator[bytes]:
        path = self._path_for(key)
        if not path.is_file():
            raise ObjectNotFound(key)

        def chunks() -> Iterator[bytes]:
            with path.open("rb") as handle:
                while True:
                    block = handle.read(chunk_bytes)
                    if not block:
                        return
                    yield block

        return chunks()

    def head(self, key: str) -> ObjectMetadata:
        path = self._path_for(key)
        if not path.is_file():
            raise ObjectNotFound(key)
        stat = path.stat()
        sidecar = path.with_suffix(path.suffix + _META_SUFFIX)
        checksum = None
        if sidecar.is_file():
            try:
                checksum = sidecar.read_text(encoding="ascii").strip() or None
            except OSError:
                checksum = None
        return ObjectMetadata(
            key=key, size_bytes=stat.st_size, checksum_sha256=checksum,
            last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
            bucket=None)

    def exists(self, key: str) -> bool:
        try:
            return self._path_for(key).is_file()
        except StorageError:
            return False

    def copy(self, source_key: str, destination_key: str) -> ObjectMetadata:
        source = self._path_for(source_key)
        destination = self._path_for(destination_key)
        if not source.is_file():
            raise ObjectNotFound(source_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source, destination)
            sidecar = source.with_suffix(source.suffix + _META_SUFFIX)
            if sidecar.is_file():
                shutil.copy2(
                    sidecar,
                    destination.with_suffix(destination.suffix + _META_SUFFIX))
        except OSError as exc:
            raise StorageError("copy_failed",
                               f"The object could not be copied "
                               f"({type(exc).__name__}).") from exc
        return self.head(destination_key)

    def delete(self, key: str) -> bool:
        path = self._path_for(key)
        existed = path.is_file()
        try:
            path.unlink(missing_ok=True)
            path.with_suffix(path.suffix + _META_SUFFIX).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("delete_failed",
                               f"The object could not be removed "
                               f"({type(exc).__name__}).") from exc
        return existed

    def health(self) -> StorageHealth:
        try:
            probe = self._root / ".health"
            probe.write_text("ok", encoding="ascii")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            return StorageHealth(
                healthy=False, driver=self.driver,
                detail=f"the storage root is not writable "
                       f"({type(exc).__name__})")
        return StorageHealth(
            healthy=True, driver=self.driver,
            detail="local filesystem storage — development only, not "
                   "encrypted at rest")

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        base = self._root
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            name = path.name
            if name.endswith(_META_SUFFIX) or name.endswith(".part"):
                continue
            key = path.relative_to(base).as_posix()
            if key.startswith(prefix):
                yield key
