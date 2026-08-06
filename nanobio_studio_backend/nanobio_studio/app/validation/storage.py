"""Attachment validation and storage.

The threat model, stated plainly
--------------------------------
An attachment is a file whose name and contents come from a user. Three things
follow, and each is handled here rather than at the call site:

1. **The filename is hostile until proven otherwise.** ``../../etc/passwd``,
   ``C:\\Windows\\system32\\x``, a NUL byte, a name that is 4000 characters
   long, a Windows reserved device name like ``CON``. None of these ever
   becomes part of a path: the stored name is a generated opaque key, and the
   original is kept as *data* for display only.

2. **The declared type is a claim, not a fact.** A browser's Content-Type is
   supplied by the client. It is checked against an allow-list *and* against
   the file's own magic bytes where the format has a recognisable signature,
   so a ``.csv`` that is actually a Windows executable is refused.

3. **Bytes are only as trustworthy as their checksum.** The SHA-256 is computed
   here, on the bytes actually received, never taken from the client. Storing a
   client-supplied digest would make the integrity check assert exactly what an
   attacker wanted it to.

Why an interface with a local adapter
-------------------------------------
Production wants object storage with server-side encryption, lifecycle policy
and its own access control. That is not buildable in this milestone, and a
half-built S3 client would be worse than none. So the *interface* is complete
and the local adapter is a genuine implementation of it — files land under a
configured root, addressed only by opaque key. Swapping in an object-storage
adapter changes this file and nothing else.

**The local adapter is for development.** It writes unencrypted bytes to a
local directory. That is documented on the class, in the archive README, and in
the known limitations — not left for somebody to discover.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import unicodedata
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path

from nanobio_studio.app.validation.vocabulary import AttachmentCategory

__all__ = [
    "AttachmentRejected",
    "MAX_ATTACHMENT_BYTES",
    "ALLOWED_MIME_TYPES",
    "safe_display_name",
    "validate_attachment",
    "AttachmentStore",
    "ObjectBackedAttachmentStore",
    "LocalAttachmentStore",
    "StoredBlob",
    "download_headers",
    "served_media_type",
]

if TYPE_CHECKING:  # pragma: no cover - typing only
    from nanobio_studio.app.storage.objects import ObjectStore


class AttachmentRejected(ValueError):
    """Refused before anything was written."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


#: 25 MB. Large enough for an instrument export, small enough that a single
#: upload cannot exhaust the request handler.
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024

#: Declared type -> permitted extensions.
#:
#: An allow-list, not a deny-list: a deny-list is a promise to have thought of
#: every dangerous format, which nobody can keep. Executables, archives and
#: scripts are absent because no scientific attachment needs to be one.
ALLOWED_MIME_TYPES: dict[str, tuple[str, ...]] = {
    "text/csv": (".csv",),
    "text/plain": (".txt", ".dat", ".asc"),
    "text/tab-separated-values": (".tsv",),
    "application/json": (".json",),
    "application/pdf": (".pdf",),
    "image/png": (".png",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/tiff": (".tif", ".tiff"),
    "application/vnd.ms-excel": (".xls",),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        (".xlsx",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        (".docx",),
    "application/xml": (".xml",),
    "text/xml": (".xml",),
}

#: Magic-byte signatures for the formats that have one.
#:
#: Only checked where a signature exists — a CSV has no header, and inventing a
#: rule for it would reject valid files. Absence of a signature is not treated
#: as a pass for formats that should have one.
_MAGIC: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/tiff": (b"II*\x00", b"MM\x00*"),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        (b"PK\x03\x04",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        (b"PK\x03\x04",),
    "application/vnd.ms-excel": (b"\xd0\xcf\x11\xe0",),
}

#: Signatures that must never appear, whatever the declared type.
#:
#: A file claiming to be a CSV whose first bytes are ``MZ`` is a Windows
#: executable. There is no benign reading of that.
_FORBIDDEN_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "Windows executable"),
    (b"\x7fELF", "ELF executable"),
    (b"\xca\xfe\xba\xbe", "Mach-O or Java class"),
    (b"#!", "script with a shebang"),
)

#: Windows reserved device names. Creating a file called ``CON`` or ``LPT1``
#: has surprising effects on Windows even inside an unrelated directory.
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_UNSAFE_CHARS = re.compile(r"[\x00-\x1f\x7f<>:\"/\\|?*]")


def safe_display_name(filename: str) -> str:
    """Reduce a user-supplied filename to something safe to store and show.

    The result is **never** used to build a path — the storage key is generated
    independently. This exists so the name can be rendered in the interface and
    written to the database without carrying control characters, directory
    separators or a traversal sequence into either.
    """
    if not filename or not filename.strip():
        raise AttachmentRejected("empty_filename",
                                 "The file has no name.")

    # Normalise first: a decomposed or full-width character can otherwise slip
    # a separator past a naive check.
    name = unicodedata.normalize("NFKC", filename).strip()

    # Take the last component under either separator convention. A browser on
    # Windows may send a full path; only the leaf is ever meaningful.
    name = name.replace("\\", "/").split("/")[-1]

    # Strip anything that could act as a separator, a control character or a
    # shell metacharacter.
    name = _UNSAFE_CHARS.sub("_", name)

    # A name of dots only is a traversal attempt with the separators removed.
    if set(name) <= {".", "_", " "} or not name.strip(". _"):
        raise AttachmentRejected(
            "unsafe_filename",
            "The filename contains no usable characters.")

    # Leading dots hide the file on POSIX; trailing dots and spaces are
    # silently stripped by Windows, which makes two names collide.
    name = name.lstrip(".").rstrip(". ")

    stem, dot, ext = name.rpartition(".")
    if dot and stem.upper() in _WINDOWS_RESERVED:
        name = f"file_{name}"
    elif not dot and name.upper() in _WINDOWS_RESERVED:
        name = f"file_{name}"

    if len(name) > 180:
        stem, dot, ext = name.rpartition(".")
        keep = 180 - (len(ext) + 1 if dot else 0)
        name = f"{stem[:keep]}.{ext}" if dot else name[:180]

    if not name:
        raise AttachmentRejected("unsafe_filename",
                                 "The filename could not be made safe.")
    return name


@dataclass(frozen=True)
class ValidatedAttachment:
    display_name: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    category: AttachmentCategory


def validate_attachment(*, filename: str, declared_mime: str, content: bytes,
                        category: AttachmentCategory) -> ValidatedAttachment:
    """Check a candidate attachment. Raises rather than returning a flag.

    Every check runs against the bytes actually received. The size is measured,
    not read from a header; the checksum is computed, not accepted.
    """
    display_name = safe_display_name(filename)

    size = len(content)
    if size == 0:
        raise AttachmentRejected("empty_file", "The file is empty.")
    if size > MAX_ATTACHMENT_BYTES:
        raise AttachmentRejected(
            "file_too_large",
            f"The file is {size / 1e6:.1f} MB. The limit is "
            f"{MAX_ATTACHMENT_BYTES / 1e6:.0f} MB.")

    mime = (declared_mime or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME_TYPES:
        raise AttachmentRejected(
            "unsupported_type",
            f"{mime or 'an unspecified type'} is not an accepted attachment "
            f"type. Accepted: {', '.join(sorted(ALLOWED_MIME_TYPES))}.")

    extension = Path(display_name).suffix.lower()
    if extension not in ALLOWED_MIME_TYPES[mime]:
        raise AttachmentRejected(
            "type_extension_mismatch",
            f"A {mime} file must have one of these extensions: "
            f"{', '.join(ALLOWED_MIME_TYPES[mime])}; this one is "
            f"{extension or 'absent'}.")

    head = content[:16]
    for signature, description in _FORBIDDEN_MAGIC:
        if head.startswith(signature):
            raise AttachmentRejected(
                "executable_content",
                f"The file's contents are a {description}, whatever its name "
                "and declared type say. It has not been stored.")

    expected = _MAGIC.get(mime)
    if expected and not any(head.startswith(sig) for sig in expected):
        raise AttachmentRejected(
            "content_type_mismatch",
            f"The file does not begin like a {mime} file. Its declared type "
            "and its contents disagree.")

    return ValidatedAttachment(
        display_name=display_name,
        mime_type=mime,
        size_bytes=size,
        # Computed here, from these bytes. Never supplied by the caller.
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        category=category,
    )


@dataclass(frozen=True)
class StoredBlob:
    storage_key: str
    size_bytes: int
    checksum_sha256: str
    #: Which driver wrote it, and into which container. Recorded on the row so
    #: a later reconciliation knows where to look for the object, rather than
    #: assuming the driver configured today wrote everything ever stored.
    backend: str = "local"
    bucket: str | None = None


class AttachmentStore(ABC):
    """The storage contract, in the registry's own terms.

    Callers see opaque keys only. No method accepts or returns a filesystem
    path or a provider object, which is what keeps the backing store swappable
    and stops either reaching a response body.

    Deliberately narrower than ``storage.ObjectStore``: the registry needs put,
    get, delete and verify, and giving it server-side copy and bucket listing
    would invite a service to reach past the lifecycle this file exists to
    enforce.
    """

    @abstractmethod
    def put(self, content: bytes, *, checksum_sha256: str,
            organization_id: int | None = None,
            attachment_id: int | None = None) -> StoredBlob:
        """Store bytes under a key derived from immutable identifiers.

        The identifiers are parameters rather than something this layer
        invents, because the key must be traceable back to its row — see
        ``storage/keys.py``. They are integers, so no filename, display name or
        clinical string can reach a key through this signature.
        """

    @abstractmethod
    def get(self, storage_key: str) -> bytes:
        """Retrieve bytes by key. Raises KeyError when absent."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Remove bytes by key. Idempotent."""

    @abstractmethod
    def verify(self, storage_key: str, *, checksum_sha256: str) -> bool:
        """Whether the stored bytes still hash to the recorded checksum."""


class ObjectBackedAttachmentStore(AttachmentStore):
    """The registry's view of the provider-neutral object store.

    One adapter, every provider. Which one is behind it is decided by
    configuration in ``storage/factory.py``; this class never learns, and does
    not want to know.
    """

    def __init__(self, store: "ObjectStore | None" = None) -> None:
        self._store = store

    @property
    def store(self) -> "ObjectStore":
        from nanobio_studio.app.storage import object_store
        return self._store if self._store is not None else object_store()

    def put(self, content: bytes, *, checksum_sha256: str,
            organization_id: int | None = None,
            attachment_id: int | None = None) -> StoredBlob:
        from nanobio_studio.app.storage.keys import new_attachment_key

        if attachment_id is None:
            raise AttachmentRejected(
                "missing_attachment_id",
                "An object key is built from the attachment's own identifier, "
                "so the row has to exist before the bytes are written.")

        key = new_attachment_key(
            organization_id=organization_id if organization_id is not None else 0,
            attachment_id=attachment_id)
        store = self.store
        metadata = store.put(key, content, checksum_sha256=checksum_sha256)
        return StoredBlob(
            storage_key=metadata.key,
            size_bytes=metadata.size_bytes,
            checksum_sha256=metadata.checksum_sha256 or checksum_sha256,
            backend=store.driver,
            bucket=store.bucket)

    def get(self, storage_key: str) -> bytes:
        from nanobio_studio.app.storage.objects import ObjectNotFound
        try:
            return self.store.get(storage_key)
        except ObjectNotFound as exc:
            # Re-raised as KeyError so the service layer keeps one meaning for
            # "absent" regardless of which driver reported it.
            raise KeyError(storage_key) from exc

    def delete(self, storage_key: str) -> None:
        self.store.delete(storage_key)

    def verify(self, storage_key: str, *, checksum_sha256: str) -> bool:
        try:
            content = self.get(storage_key)
        except (KeyError, AttachmentRejected):
            return False
        return hashlib.sha256(content).hexdigest() == checksum_sha256


class LocalAttachmentStore(ObjectBackedAttachmentStore):
    """A store rooted at a directory. Development and tests.

    **Not production storage.** Bytes are written unencrypted to a local
    directory with no lifecycle policy, no replication and no access control
    beyond the operating system's.

    Kept as a named class because tests construct it with an explicit root, and
    because "give me a store under this path" is a genuinely useful thing to
    ask for. It is now a thin subclass over the object-storage layer rather
    than its own filesystem implementation, so there is exactly one place where
    a key becomes a path.
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        from nanobio_studio.app.storage.local import LocalObjectStore
        super().__init__(LocalObjectStore(root))


_default_store: AttachmentStore | None = None


def default_store() -> AttachmentStore:
    """The process-wide store, over whichever object-storage driver is configured.

    No longer hard-wired to the filesystem: ``STORAGE_DRIVER`` selects local or
    S3-compatible storage, and this returns the same adapter either way.
    """
    global _default_store
    if _default_store is None:
        _default_store = ObjectBackedAttachmentStore()
    return _default_store


def set_default_store(store: AttachmentStore | None) -> None:
    """Replace the store. Used by tests to keep bytes out of the working tree."""
    global _default_store
    _default_store = store


# ---------------------------------------------------------------------------
# Serving a stored file safely
# ---------------------------------------------------------------------------

#: Types a browser will execute, script, or treat as same-origin markup.
#:
#: None of these is in ``ALLOWED_MIME_TYPES``, so nothing should ever be stored
#: with one. This exists anyway, because "the allow-list already prevents it"
#: is a claim about a list somebody may widen later — and the day an SVG becomes
#: an acceptable figure format is the day an uploaded file starts executing in
#: the application's origin. Neutralising on the way *out* survives that change.
_ACTIVE_CONTENT_TYPES = frozenset({
    "text/html", "application/xhtml+xml", "image/svg+xml",
    "application/xml", "text/xml", "application/xslt+xml",
    "application/javascript", "text/javascript", "application/ecmascript",
})

#: What an active type is served as instead. A browser downloads this and
#: renders nothing.
_NEUTRAL_MEDIA_TYPE = "application/octet-stream"


def served_media_type(stored_mime: str) -> str:
    """The Content-Type to serve a stored file with.

    Returns the stored type for anything inert, and
    ``application/octet-stream`` for anything a browser would execute or treat
    as markup. Combined with ``Content-Disposition: attachment`` and the
    sandbox CSP below, an uploaded file cannot become script in the
    application's origin even if it reaches the store.
    """
    mime = (stored_mime or "").split(";")[0].strip().lower()
    if mime in _ACTIVE_CONTENT_TYPES:
        return _NEUTRAL_MEDIA_TYPE
    return mime or _NEUTRAL_MEDIA_TYPE


def download_headers(original_filename: str) -> dict[str, str]:
    """Response headers for serving a stored file. Five, each doing a job.

    * ``Content-Disposition: attachment`` with a **re-sanitised** filename —
      re-sanitised rather than trusted, because the row was written by an
      earlier version of the validator and a quote or a newline in it would
      let a stored name inject a header.
    * ``X-Content-Type-Options: nosniff`` — stops a browser deciding for itself
      that an octet-stream is really HTML.
    * ``Content-Security-Policy: default-src 'none'; sandbox`` — if a file is
      opened in a tab anyway, it can load nothing and run nothing.
    * ``Cache-Control: no-store`` with ``Pragma`` — so a deleted attachment
      cannot be re-served from a browser or proxy cache, and so switching
      organization cannot resurrect the previous organization's file from
      local cache. A revoked download that a cache still answers is a
      revocation that did not happen.
    """
    try:
        safe = safe_display_name(original_filename)
    except AttachmentRejected:
        # A name that cannot be made safe is replaced rather than refused: the
        # bytes are still the user's file, and failing the download over a bad
        # stored name would be losing data to protect a header.
        safe = "attachment"
    # Belt and braces on top of `safe_display_name`, which already strips
    # quotes and control characters.
    safe = safe.replace('"', "").replace("\r", "").replace("\n", "")
    return {
        "Content-Disposition": f'attachment; filename="{safe}"',
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
        "Pragma": "no-cache",
    }
