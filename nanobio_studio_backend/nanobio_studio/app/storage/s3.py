"""S3 and S3-compatible object storage.

One driver, several providers
-----------------------------
AWS S3, Cloudflare R2, MinIO, Backblaze B2 and most government and university
object stores speak the same API. What differs between them is three settings,
not three code paths:

* ``endpoint_url`` — absent for AWS, present for everything else;
* ``region`` — meaningful for AWS, often ``auto`` for R2, ignored by MinIO;
* ``path_style`` — MinIO and many self-hosted gateways need
  ``bucket/key`` rather than ``bucket.host/key``, because virtual-host
  addressing needs wildcard DNS that a private deployment rarely has.

So there is no ``R2ObjectStore``. Writing one would mean three near-identical
classes drifting apart, and a provider nobody had written a class for yet would
be unsupported for no reason.

Nothing provider-shaped escapes
-------------------------------
``boto3`` and ``botocore`` are imported inside ``__init__`` rather than at
module scope, so the package remains importable — and the whole test suite
remains runnable — on a machine that has never installed them. Every
``ClientError`` is caught and re-raised as ``ObjectNotFound`` or
``StorageError`` with a short code. A botocore message contains the bucket
name, the request id and occasionally a signed query parameter; none of that
belongs in a log, an audit row or a response.

Credentials
-----------
Read from configuration, which reads from the environment. There is no default
endpoint, no default bucket and no embedded key anywhere in this repository,
and the constructor refuses to build rather than falling back to something that
would either fail obscurely or write into somebody else's bucket.

Encryption
----------
Server-side by default: ``AES256`` unless a KMS key is configured, in which
case ``aws:kms`` with that key. Deliberately not hard-coded to one cloud's
key-management product — the setting is a key *identifier*, which R2 and MinIO
ignore and AWS and compatible gateways honour.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Iterator

from nanobio_studio.app.storage.keys import is_valid_key
from nanobio_studio.app.storage.objects import (
    DEFAULT_CHUNK_BYTES, ObjectMetadata, ObjectNotFound, ObjectStore,
    StorageError, StorageHealth, StorageNotConfigured,
)

__all__ = ["S3ObjectStore"]

#: Where the store records the checksum it computed at write time. A custom
#: metadata header rather than the object's ETag: an ETag is MD5 only for
#: single-part uploads, so trusting it would silently start disagreeing with
#: the database the first time a file crossed the multipart threshold.
_CHECKSUM_METADATA = "sha256"

#: Absence codes, across providers. R2 and MinIO do not all use the same one.
_NOT_FOUND_CODES = {"404", "NoSuchKey", "NotFound", "NoSuchBucket"}


class S3ObjectStore(ObjectStore):
    driver = "s3"

    def __init__(self, *, bucket: str, endpoint_url: str | None = None,
                 region: str | None = None,
                 access_key_id: str | None = None,
                 secret_access_key: str | None = None,
                 path_style: bool = False,
                 prefix: str = "",
                 sse: str | None = "AES256",
                 sse_kms_key_id: str | None = None) -> None:
        missing = [name for name, value in (("STORAGE_BUCKET", bucket),) if not value]
        if missing:
            raise StorageNotConfigured(
                "storage_incomplete",
                "S3 storage is selected but " + ", ".join(missing)
                + " is not set. There is no default, deliberately: a default "
                  "bucket is how an application writes into somebody else's.")

        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise StorageNotConfigured(
                "boto3_missing",
                "S3 storage is selected but boto3 is not installed. Install "
                "it, or select the local driver for development."
            ) from exc

        self.bucket = bucket
        self._prefix = prefix.strip("/")
        self._sse = sse or None
        self._sse_kms_key_id = sse_kms_key_id or None

        config = Config(
            s3={"addressing_style": "path" if path_style else "auto"},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=10, read_timeout=60,
        )
        # Credentials are passed only when supplied. Omitting them lets boto3
        # use the instance role or the ambient credential chain, which is the
        # right thing in a managed deployment and avoids putting a long-lived
        # key in the environment at all.
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region or None,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
            config=config,
        )

        from botocore.exceptions import BotoCoreError, ClientError
        self._ClientError = ClientError
        self._BotoCoreError = BotoCoreError

    # -- helpers ----------------------------------------------------------

    def _object_key(self, key: str) -> str:
        if not is_valid_key(key):
            raise StorageError("invalid_key", "The object key is not valid.")
        return f"{self._prefix}/{key}" if self._prefix else key

    def _encryption_args(self) -> dict[str, Any]:
        if self._sse_kms_key_id:
            return {"ServerSideEncryption": "aws:kms",
                    "SSEKMSKeyId": self._sse_kms_key_id}
        if self._sse:
            return {"ServerSideEncryption": self._sse}
        return {}

    def _translate(self, exc: Exception, key: str, operation: str):
        """Provider exception in, ours out. The message never travels."""
        if isinstance(exc, self._ClientError):
            code = str(
                exc.response.get("Error", {}).get("Code", ""))  # type: ignore[attr-defined]
            status = str(
                exc.response.get("ResponseMetadata", {})  # type: ignore[attr-defined]
                .get("HTTPStatusCode", ""))
            if code in _NOT_FOUND_CODES or status == "404":
                return ObjectNotFound(key)
            if code in {"AccessDenied", "403"} or status == "403":
                return StorageError(
                    "storage_access_denied",
                    "The object store refused the request. This is a storage "
                    "credential or bucket-policy problem, not a user "
                    "permission problem.")
            return StorageError(
                f"storage_{operation}_failed",
                f"The object store could not complete the {operation} "
                f"(provider code {code or 'unknown'}).")
        return StorageError(
            f"storage_{operation}_failed",
            f"The object store is unreachable ({type(exc).__name__}).")

    # -- operations -------------------------------------------------------

    def put(self, key: str, content: bytes, *, checksum_sha256: str,
            content_type: str | None = None) -> ObjectMetadata:
        actual = hashlib.sha256(content).hexdigest()
        if actual != checksum_sha256:
            raise StorageError(
                "checksum_mismatch",
                "The content does not match its checksum. Nothing was written.")
        try:
            self._client.put_object(
                Bucket=self.bucket, Key=self._object_key(key), Body=content,
                ContentType=content_type or "application/octet-stream",
                # Recorded as metadata so `head` can report the store's own
                # view of the checksum without transferring the body.
                Metadata={_CHECKSUM_METADATA: actual},
                **self._encryption_args(),
            )
        except (self._ClientError, self._BotoCoreError) as exc:
            raise self._translate(exc, key, "upload") from exc
        return ObjectMetadata(key=key, size_bytes=len(content),
                              checksum_sha256=actual,
                              last_modified=datetime.now(timezone.utc),
                              bucket=self.bucket)

    def open_stream(self, key: str, *,
                    chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> Iterator[bytes]:
        try:
            response = self._client.get_object(Bucket=self.bucket,
                                               Key=self._object_key(key))
        except (self._ClientError, self._BotoCoreError) as exc:
            raise self._translate(exc, key, "download") from exc

        body = response["Body"]

        def chunks() -> Iterator[bytes]:
            try:
                while True:
                    block = body.read(chunk_bytes)
                    if not block:
                        return
                    yield block
            finally:
                body.close()

        return chunks()

    def head(self, key: str) -> ObjectMetadata:
        try:
            response = self._client.head_object(Bucket=self.bucket,
                                                Key=self._object_key(key))
        except (self._ClientError, self._BotoCoreError) as exc:
            raise self._translate(exc, key, "head") from exc
        metadata = {k.lower(): v
                    for k, v in (response.get("Metadata") or {}).items()}
        last_modified = response.get("LastModified")
        return ObjectMetadata(
            key=key,
            size_bytes=int(response.get("ContentLength", 0)),
            checksum_sha256=metadata.get(_CHECKSUM_METADATA),
            last_modified=last_modified,
            bucket=self.bucket)

    def exists(self, key: str) -> bool:
        try:
            self.head(key)
            return True
        except ObjectNotFound:
            return False
        except StorageError:
            # Unreachable is not absent. Reporting "no" here would let a
            # transient outage look like a missing object, and reconciliation
            # would then report every attachment as an orphan.
            raise

    def copy(self, source_key: str, destination_key: str) -> ObjectMetadata:
        try:
            self._client.copy_object(
                Bucket=self.bucket,
                # Server-side: the bytes never travel through this process.
                CopySource={"Bucket": self.bucket,
                            "Key": self._object_key(source_key)},
                Key=self._object_key(destination_key),
                MetadataDirective="COPY",
                **self._encryption_args(),
            )
        except (self._ClientError, self._BotoCoreError) as exc:
            raise self._translate(exc, source_key, "copy") from exc
        return self.head(destination_key)

    def delete(self, key: str) -> bool:
        existed = True
        try:
            self.head(key)
        except ObjectNotFound:
            existed = False
        except StorageError:
            raise
        try:
            self._client.delete_object(Bucket=self.bucket,
                                       Key=self._object_key(key))
        except (self._ClientError, self._BotoCoreError) as exc:
            raise self._translate(exc, key, "delete") from exc
        return existed

    def health(self) -> StorageHealth:
        started = time.monotonic()
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except Exception as exc:  # noqa: BLE001 — health must never raise
            translated = self._translate(exc, "", "health")
            return StorageHealth(
                healthy=False, driver=self.driver, bucket=self.bucket,
                # The code, not the provider's message: an endpoint or a
                # signed parameter must not reach a readiness body.
                detail=getattr(translated, "code", "storage_unavailable"),
                latency_ms=(time.monotonic() - started) * 1000)
        return StorageHealth(
            healthy=True, driver=self.driver, bucket=self.bucket,
            detail="object storage reachable",
            latency_ms=(time.monotonic() - started) * 1000)

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        full_prefix = f"{self._prefix}/{prefix}" if self._prefix else prefix
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket,
                                           Prefix=full_prefix):
                for item in page.get("Contents", []):
                    key = item["Key"]
                    if self._prefix and key.startswith(f"{self._prefix}/"):
                        key = key[len(self._prefix) + 1:]
                    yield key
        except (self._ClientError, self._BotoCoreError) as exc:
            raise self._translate(exc, "", "list") from exc
