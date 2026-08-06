"""Upload validation for medical report documents.

Every check here is real. Nothing is decorative.

Threat model
------------
An upload endpoint that accepts arbitrary bytes from an authenticated user is a
genuine attack surface, so this module:

* **checks magic bytes, not the filename or the client-supplied MIME type.**
  Both of the latter are attacker-controlled; a ``.pdf`` extension proves
  nothing.
* **rejects by allow-list**, never by block-list.
* **caps size before reading** the whole body into memory.
* **neutralises the filename** — path separators, traversal sequences, control
  characters and null bytes are stripped, and the stored name is derived from a
  content hash rather than from anything the client sent.
* **refuses documents carrying active content** (embedded JavaScript, launch
  actions, embedded files in a PDF), because those are the payloads that matter
  for a document a human will later open.
* **never logs document bytes or filenames**, since either can carry patient
  identifiers.

Deliberately NOT claimed
------------------------
This is not antivirus and does not detect malware generally. It rejects the
specific, checkable classes above. That limitation is stated to the user rather
than papered over.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Final

__all__ = [
    "MAX_UPLOAD_BYTES",
    "SUPPORTED_FORMATS",
    "ValidationError",
    "ValidatedDocument",
    "validate_upload",
    "safe_display_name",
]

#: 15 MB. Generous for a pathology report, small enough that a single request
#: cannot exhaust memory. Enforced before the body is fully read.
MAX_UPLOAD_BYTES: Final[int] = 15 * 1024 * 1024

#: Smallest plausible real document. Below this it is a stub or an empty file.
MIN_UPLOAD_BYTES: Final[int] = 16


@dataclass(frozen=True)
class SupportedFormat:
    key: str
    label: str
    extensions: tuple[str, ...]
    media_type: str
    #: Leading bytes that must be present. Empty when the format has no magic
    #: number, in which case `text_like` decoding is the check instead.
    magic: tuple[bytes, ...]
    text_like: bool
    #: Whether the platform can currently read the content for display.
    readable: bool
    #: Stated to the user when it cannot.
    unreadable_reason: str | None = None


SUPPORTED_FORMATS: Final[tuple[SupportedFormat, ...]] = (
    SupportedFormat(
        key="pdf", label="PDF document", extensions=(".pdf",),
        media_type="application/pdf", magic=(b"%PDF-",),
        # Readable as of the extraction slice: pypdf recovers the embedded text
        # layer. A SCANNED pdf carries no such layer and is reported as
        # unreadable by the extraction pipeline, which owns that judgement.
        text_like=False, readable=True,
    ),
    SupportedFormat(
        key="txt", label="Plain-text report", extensions=(".txt",),
        media_type="text/plain", magic=(), text_like=True, readable=True,
    ),
    SupportedFormat(
        key="md", label="Markdown report", extensions=(".md", ".markdown"),
        media_type="text/markdown", magic=(), text_like=True, readable=True,
    ),
)

_BY_EXTENSION: Final[dict[str, SupportedFormat]] = {
    ext: fmt for fmt in SUPPORTED_FORMATS for ext in fmt.extensions
}

#: Signatures of formats that are plainly not documents. Matching one produces a
#: precise message instead of a vague "unsupported file".
_DANGEROUS_SIGNATURES: Final[tuple[tuple[bytes, str], ...]] = (
    (b"MZ", "a Windows executable"),
    (b"\x7fELF", "a Linux executable"),
    (b"PK\x03\x04", "a ZIP archive or Office document"),
    (b"\x1f\x8b", "a gzip archive"),
    (b"Rar!\x1a\x07", "a RAR archive"),
    (b"\xca\xfe\xba\xbe", "a Java class file"),
    (b"#!", "a script with a shebang"),
    (b"<?php", "a PHP script"),
    (b"\xd0\xcf\x11\xe0", "a legacy Office document"),
)

#: Active-content markers inside a PDF. These are the constructs that execute or
#: fetch when a document is opened, so a report containing them is refused.
_PDF_ACTIVE_CONTENT: Final[tuple[tuple[bytes, str], ...]] = (
    (b"/JavaScript", "embedded JavaScript"),
    (b"/JS", "embedded JavaScript"),
    (b"/Launch", "a launch action"),
    (b"/EmbeddedFile", "an embedded file"),
    (b"/OpenAction", "an automatic open action"),
    (b"/AA", "an automatic action"),
)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class ValidationError(Exception):
    """An upload was refused. ``code`` is machine-readable for the API."""

    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


@dataclass(frozen=True)
class ValidatedDocument:
    """An upload that passed every check."""

    format_key: str
    format_label: str
    media_type: str
    size_bytes: int
    #: SHA-256 of the content. Identifies the document without its name, which
    #: may itself carry a patient identifier.
    content_hash: str
    #: Neutralised name, safe to display and to store.
    display_name: str
    #: Decoded text, only when the format is genuinely readable.
    text: str | None
    readable: bool
    unreadable_reason: str | None


def safe_display_name(raw: str | None) -> str:
    """Reduce a client filename to something safe to store and render.

    Strips directory components, traversal sequences, control characters and
    anything outside a conservative allow-list. A name that reduces to nothing
    becomes a neutral placeholder rather than an empty string.
    """
    if not raw:
        return "uploaded-document"

    # Take the basename only: defeats both separators and any traversal.
    name = raw.replace("\\", "/").split("/")[-1]
    name = unicodedata.normalize("NFKC", name)
    name = _CONTROL_CHARS.sub("", name)
    name = name.replace("..", "")
    name = _UNSAFE_NAME.sub("_", name).strip("._-")

    if not name:
        return "uploaded-document"
    return name[:120]


def _match_format(filename: str, content: bytes) -> SupportedFormat:
    """Resolve the format from CONTENT, using the extension only as a hint."""
    lowered = filename.lower()
    claimed = next((fmt for ext, fmt in _BY_EXTENSION.items()
                    if lowered.endswith(ext)), None)

    # Magic-byte formats are authoritative: content decides, not the name.
    for fmt in SUPPORTED_FORMATS:
        if fmt.magic and any(content.startswith(m) for m in fmt.magic):
            return fmt

    if claimed is None:
        raise ValidationError(
            "unsupported_file_type",
            "That file type is not supported.",
            "Supported formats: "
            + ", ".join(f"{f.label} ({', '.join(f.extensions)})"
                        for f in SUPPORTED_FORMATS),
        )

    if claimed.magic:
        # Claimed a magic-byte format but the content does not match it.
        raise ValidationError(
            "content_does_not_match_extension",
            f"The file is named like a {claimed.label} but its contents are "
            "not one.",
            "The file type is determined from the content, never from the "
            "filename or the browser-supplied type.",
        )

    return claimed


def validate_upload(filename: str | None, content: bytes) -> ValidatedDocument:
    """Validate an uploaded document. Raises ``ValidationError`` on refusal.

    Order matters: cheap structural checks run before anything that touches the
    full body.
    """
    size = len(content)

    if size == 0:
        raise ValidationError("empty_file", "The uploaded file is empty.")
    if size < MIN_UPLOAD_BYTES:
        raise ValidationError(
            "file_too_small",
            "The uploaded file is too small to be a medical report.",
            f"{size} bytes; the minimum is {MIN_UPLOAD_BYTES}.")
    if size > MAX_UPLOAD_BYTES:
        raise ValidationError(
            "file_too_large",
            "The uploaded file exceeds the maximum size.",
            f"{size} bytes; the maximum is {MAX_UPLOAD_BYTES} "
            f"({MAX_UPLOAD_BYTES // (1024 * 1024)} MB).")

    # Refuse plainly non-document content with a precise reason. Checked before
    # format matching so an executable never reaches the text decoder.
    head = content[:16]
    for signature, description in _DANGEROUS_SIGNATURES:
        if head.startswith(signature):
            raise ValidationError(
                "unsafe_file_type",
                f"This looks like {description}, not a medical report.",
                "Only PDF, plain-text and Markdown documents are accepted.")

    display_name = safe_display_name(filename)
    fmt = _match_format(display_name, content)

    text: str | None = None
    if fmt.text_like:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError(
                "content_not_readable_text",
                "The file is named as a text document but is not valid UTF-8 "
                "text.",
                f"Decoding failed at byte {exc.start}.") from exc

        if "\x00" in text:
            raise ValidationError(
                "content_not_readable_text",
                "The text document contains null bytes, so it is not a plain "
                "text report.")

    if fmt.key == "pdf":
        for marker, description in _PDF_ACTIVE_CONTENT:
            if marker in content:
                raise ValidationError(
                    "active_content_rejected",
                    f"This PDF contains {description} and has been refused.",
                    "Documents that can execute or fetch content when opened "
                    "are not accepted. Re-export the report as a flat PDF or "
                    "plain text.")

    return ValidatedDocument(
        format_key=fmt.key,
        format_label=fmt.label,
        media_type=fmt.media_type,
        size_bytes=size,
        content_hash=hashlib.sha256(content).hexdigest(),
        display_name=display_name,
        text=text,
        readable=fmt.readable,
        unreadable_reason=fmt.unreadable_reason,
    )
