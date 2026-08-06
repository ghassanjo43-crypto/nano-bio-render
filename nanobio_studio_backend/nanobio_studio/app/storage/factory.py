"""Choosing the object store, once, from configuration.

The one place a driver name becomes an object. Everything else in the
application asks for ``object_store()`` and gets something implementing
``ObjectStore``; nothing else imports ``s3.py`` or ``local.py``, which is what
keeps the provider swappable.

Failing loudly, and where
-------------------------
An incomplete production configuration must fail at **startup**, naming what is
missing. The alternative — falling back to local storage because the bucket
setting was empty — is the worst possible behaviour: the application comes up,
serves traffic, accepts uploads, and writes patient-adjacent files to a
container filesystem that will be discarded on the next deploy. Nobody notices
until somebody asks for a file back.

So ``object_store()`` raises ``StorageNotConfigured`` for a production driver
with missing settings, and ``verify_configuration()`` is called during
application startup so the failure happens before the first request rather than
during it.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from nanobio_studio.app.core.config import settings
from nanobio_studio.app.storage.objects import (
    ObjectStore, StorageHealth, StorageNotConfigured,
)

__all__ = [
    "object_store",
    "set_object_store_for_tests",
    "reset_object_store",
    "verify_configuration",
    "storage_health",
    "describe_storage",
]

log = logging.getLogger(__name__)

_store: ObjectStore | None = None
_override: ObjectStore | None = None

#: Settings a production driver cannot start without. Reported by name, so an
#: operator reads which variable to set rather than "storage misconfigured".
_REQUIRED_FOR_S3 = ("STORAGE_BUCKET",)


def _build() -> ObjectStore:
    driver = (settings.storage_driver or "local").strip().lower()

    if driver == "local":
        root = settings.storage_local_root or "var/attachments"
        # Relative paths resolve against the working directory, which is the
        # repository root in development and the container root in a
        # deployment. Absolute paths are used as given.
        from nanobio_studio.app.storage.local import LocalObjectStore
        return LocalObjectStore(Path(root).expanduser())

    if driver == "s3":
        missing = [name for name, value in (
            ("STORAGE_BUCKET", settings.storage_bucket),
        ) if not value]
        if missing:
            raise StorageNotConfigured(
                "storage_incomplete",
                "STORAGE_DRIVER is 's3' but " + ", ".join(missing)
                + " is not set. Set it, or select the local driver for "
                  "development. There is deliberately no fallback: silently "
                  "writing to a local directory when object storage was asked "
                  "for is how files are lost on the next deploy.")
        from nanobio_studio.app.storage.s3 import S3ObjectStore
        return S3ObjectStore(
            bucket=settings.storage_bucket,
            endpoint_url=settings.storage_endpoint_url or None,
            region=settings.storage_region or None,
            access_key_id=settings.storage_access_key_id or None,
            secret_access_key=settings.storage_secret_access_key or None,
            path_style=settings.storage_path_style,
            prefix=settings.storage_prefix or "",
            sse=settings.storage_sse or None,
            sse_kms_key_id=settings.storage_sse_kms_key_id or None,
        )

    raise StorageNotConfigured(
        "unknown_storage_driver",
        f"STORAGE_DRIVER is {driver!r}, which is not a driver. Valid drivers: "
        f"local, s3. Refused rather than defaulted, because defaulting a "
        f"typo'd driver name to local storage would put production files on a "
        f"container filesystem.")


def object_store() -> ObjectStore:
    """The process-wide store, built once."""
    global _store
    if _override is not None:
        return _override
    if _store is None:
        _store = _build()
    return _store


def set_object_store_for_tests(store: ObjectStore | None) -> None:
    """Test seam. ``None`` restores configuration-driven selection."""
    global _override
    _override = store


def reset_object_store() -> None:
    """Forget the cached store, so a settings change takes effect."""
    global _store
    _store = None


def verify_configuration() -> None:
    """Build the store, so a bad configuration fails at startup.

    Called from the application's startup path. Deliberately does *not* call
    ``health()``: an object store that is momentarily unreachable should not
    stop the application from starting and then serving the routes that do not
    need it. Reachability belongs in the readiness probe, which is re-evaluated
    continuously; configuration belongs here, because it will not fix itself.
    """
    store = object_store()
    log.info("Object storage: driver=%s bucket=%s",
             store.driver, store.bucket or "(none)")
    if store.driver == "local":
        log.warning(
            "Object storage is the local filesystem driver. Bytes are stored "
            "unencrypted with no lifecycle policy — development only.")


def storage_health() -> StorageHealth:
    """For the readiness probe. Never raises."""
    try:
        return object_store().health()
    except StorageNotConfigured as exc:
        return StorageHealth(healthy=False, driver="unconfigured",
                             detail=exc.code)
    except Exception:  # noqa: BLE001 — a probe that raises is a probe that lies
        return StorageHealth(healthy=False, driver="unknown",
                             detail="storage_unavailable")


def describe_storage() -> dict[str, object]:
    """What may safely be reported about the storage configuration.

    Names the driver, the bucket and whether encryption and scanning are on.
    Never the endpoint, the region, an access key, a secret or a signed
    parameter — a diagnostics endpoint is read by more people than a
    credential store is.
    """
    try:
        store = object_store()
        driver, bucket = store.driver, store.bucket
    except StorageNotConfigured as exc:
        driver, bucket = "unconfigured", None
        return {"driver": driver, "bucket": bucket, "error": exc.code}
    return {
        "driver": driver,
        "bucket": bucket,
        "server_side_encryption": bool(settings.storage_sse
                                       or settings.storage_sse_kms_key_id),
        "customer_managed_key": bool(settings.storage_sse_kms_key_id),
        "max_upload_bytes": settings.storage_max_upload_bytes,
        # Reported as it is, not as anybody would like it to be.
        "malware_scanning": {
            "enabled": settings.storage_malware_scanning_enabled,
            "provider": settings.storage_malware_scanner or None,
            "notice": (
                "No malware scanner is connected. Uploaded files are checked "
                "for type, size and executable signatures only; they are not "
                "scanned for malware."
                if not settings.storage_malware_scanning_enabled else
                "A scanner is connected. Files are held in PENDING_SCAN until "
                "it reports."),
        },
        "presigned_urls": {
            "issued": False,
            "ttl_seconds": settings.storage_presigned_ttl_seconds,
            "notice": (
                "Nothing issues a presigned URL. Attachments and medical "
                "report documents are streamed through the authenticated API, "
                "because a presigned URL is a bearer credential that outlives "
                "the authorization that produced it."),
        },
    }
