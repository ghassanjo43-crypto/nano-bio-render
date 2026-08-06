"""The object-storage contract, and nothing provider-specific.

What this interface is for
--------------------------
Attachment bytes used to be written to a directory by a class that knew it was
writing to a directory. Production wants S3 — or Cloudflare R2, or MinIO, or a
government cloud's S3-compatible service — with server-side encryption, a
lifecycle policy and its own access control. Making that a configuration change
rather than a rewrite requires one thing above all: **no caller outside this
package may ever hold a provider object.**

So nothing here returns a ``boto3`` client, a ``Bucket``, a botocore exception
or a filesystem ``Path``. Callers see opaque string keys, byte streams, a
metadata dataclass and two exception types. A route that caught
``ClientError`` would be a route that could only ever run against AWS, and it
would leak the provider's error text — which contains bucket names, request ids
and sometimes signed parameters — into a response body.

The operation set, and why each is separate
-------------------------------------------
* ``put`` — store bytes under a key the *caller* generated, and verify the
  checksum on the way in. Not "upload and tell me the key": the key is derived
  from immutable database identifiers (see ``keys.py``), so the caller has to
  own it.
* ``open_stream`` — an iterator of chunks. Distinct from a bytes-returning read
  because a 25 MB instrument export held entirely in memory, per concurrent
  download, is how a server falls over under perfectly ordinary use.
* ``head`` — size, checksum and modification time without transferring the
  body. Reconciliation reads thousands of these; downloading each one to learn
  its size would make the check unrunnable, and therefore unrun.
* ``exists`` — a boolean, for the common case where the metadata is not wanted.
* ``copy`` — server-side where the provider supports it. Superseding an
  attachment must not round-trip the bytes through the application.
* ``delete`` — idempotent, and reports whether the object was there. The caller
  needs to distinguish "removed" from "already gone" to decide whether a
  tombstone can be retired.
* ``health`` — a cheap liveness check for the readiness probe. A deployment
  whose object store is unreachable is not ready, and finding that out on the
  first upload is finding out too late.

Errors
------
Two, deliberately. ``ObjectNotFound`` is a fact about a key. ``StorageError``
is everything else — unreachable, refused, misconfigured — and carries a short
code rather than the provider's message, so nothing provider-shaped escapes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

__all__ = [
    "ObjectStore",
    "ObjectMetadata",
    "ObjectNotFound",
    "StorageError",
    "StorageNotConfigured",
    "StorageHealth",
    "DEFAULT_CHUNK_BYTES",
]

#: 64 KiB. Big enough that syscall overhead is irrelevant, small enough that a
#: hundred concurrent downloads do not add up to a memory problem.
DEFAULT_CHUNK_BYTES = 64 * 1024


class ObjectNotFound(KeyError):
    """No object at that key. A fact, not a failure."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


class StorageError(RuntimeError):
    """The store could not serve the request.

    Carries a short stable ``code`` rather than the provider's message. A
    botocore error string contains the bucket name, the request id and
    occasionally a signed query parameter; none of that belongs in a log line,
    an audit row or a response body.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class StorageNotConfigured(StorageError):
    """A production driver was selected without the settings it needs.

    Raised at construction, so a misconfigured deployment fails at startup with
    the missing variable named — rather than at the first upload, hours later,
    in front of a user holding a file.
    """


@dataclass(frozen=True)
class ObjectMetadata:
    """What is known about a stored object without reading it.

    ``checksum_sha256`` is what the *store* recorded at write time, which is not
    necessarily what the database believes. Reconciliation exists precisely to
    compare the two, so this must report the store's view rather than helpfully
    substituting the caller's.
    """

    key: str
    size_bytes: int
    checksum_sha256: str | None
    last_modified: datetime | None
    #: Provider-neutral container name. ``None`` for stores without one.
    bucket: str | None = None


@dataclass(frozen=True)
class StorageHealth:
    healthy: bool
    driver: str
    #: Safe for a readiness body: names the driver and the failure class, never
    #: an endpoint, a bucket or a credential.
    detail: str
    bucket: str | None = None
    latency_ms: float | None = None


class ObjectStore(ABC):
    """Provider-neutral object storage.

    Implementations must not leak provider types through any signature,
    exception or attribute reachable from outside this package.
    """

    #: Short stable identifier, e.g. ``local``, ``s3``, ``memory``. Recorded on
    #: the attachment row so a later reconciliation knows which store wrote it.
    driver: str = "abstract"

    #: Container name where the concept applies, otherwise ``None``.
    bucket: str | None = None

    @abstractmethod
    def put(self, key: str, content: bytes, *, checksum_sha256: str,
            content_type: str | None = None) -> ObjectMetadata:
        """Store bytes under ``key``, verifying the checksum first.

        Idempotent by construction: writing the same key with the same content
        twice is indistinguishable from writing it once, which is what makes a
        retried upload safe.
        """

    @abstractmethod
    def open_stream(self, key: str, *,
                    chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> Iterator[bytes]:
        """Yield the object's bytes in chunks. Raises ``ObjectNotFound``."""

    @abstractmethod
    def head(self, key: str) -> ObjectMetadata:
        """Metadata without the body. Raises ``ObjectNotFound``."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Whether an object is present. Never raises for absence."""

    @abstractmethod
    def copy(self, source_key: str, destination_key: str) -> ObjectMetadata:
        """Copy within the store, server-side where the provider supports it."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove the object. Returns whether it was there. Idempotent."""

    @abstractmethod
    def health(self) -> StorageHealth:
        """Cheap liveness check. Must not raise."""

    # -- convenience, implemented once ------------------------------------

    def get(self, key: str) -> bytes:
        """Whole object as bytes.

        Present because several call sites genuinely need the whole thing —
        checksum verification, for one. Streaming remains the default for
        anything that goes to a response.
        """
        return b"".join(self.open_stream(key))

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        """Every key under a prefix.

        Optional: a store that cannot enumerate raises ``StorageError`` and
        reconciliation reports the orphan-object check as unavailable rather
        than claiming there are none.
        """
        raise StorageError(
            "listing_unsupported",
            f"The {self.driver} store cannot enumerate keys, so "
            f"objects-without-rows cannot be detected against it.")
