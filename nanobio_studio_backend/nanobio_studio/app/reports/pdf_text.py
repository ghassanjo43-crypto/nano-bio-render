"""PDF text extraction, and honest detection of scanned documents.

What this does
--------------
Reads the embedded text layer of a PDF, page by page, using ``pypdf``. Text-based
reports — the ordinary output of a hospital reporting system — extract cleanly.

What it deliberately does not do
--------------------------------
**OCR.** A scanned report is an image; recovering text from it needs an optical
character recognition engine, and none is available in this environment:

* ``pytesseract`` is not installed, and it is only a wrapper — the real work is
  done by the ``tesseract`` binary, which is not on PATH either;
* ``easyocr`` is not installed.

So a scanned PDF is **detected and reported**, never guessed at. Returning
plausible-looking text for a page nobody could read would be the worst possible
failure mode for a clinical document: it would be indistinguishable from a real
reading, and every downstream field would inherit the fabrication.

Detection heuristic, and its limits
-----------------------------------
A page with a very low character yield is treated as image-only. This is a
heuristic: a genuinely near-empty page (a divider, a signature sheet) also yields
little text, so it is reported as *probably* scanned rather than asserted. The
distinction is surfaced to the user rather than resolved silently.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Final

__all__ = [
    "PDF_READER_NAME",
    "PDF_READER_VERSION",
    "OCR_AVAILABLE",
    "OCR_UNAVAILABLE_REASON",
    "PdfPage",
    "PdfExtraction",
    "extract_pdf_text",
    "ocr_available",
]

#: A page yielding fewer than this many characters is treated as image-only.
#: Chosen well below any real report page and well above an empty one.
_MIN_CHARS_PER_PAGE: Final[int] = 40

PDF_READER_NAME: Final[str] = "pypdf"


def _reader_version() -> str:
    try:
        import pypdf
        return getattr(pypdf, "__version__", "unknown")
    except ImportError:      # pragma: no cover - pypdf is a hard dependency
        return "not-installed"


PDF_READER_VERSION: Final[str] = _reader_version()


def ocr_available() -> bool:
    """True only when a usable OCR engine is genuinely present.

    Checked at call time rather than import time so that installing an engine
    takes effect without a code change. Both the Python wrapper and the
    underlying binary must be present — a wrapper alone decodes nothing.
    """
    import importlib.util
    import shutil

    if importlib.util.find_spec("pytesseract") is not None:
        if shutil.which("tesseract"):
            return True
    if importlib.util.find_spec("easyocr") is not None:
        return True
    return False


OCR_AVAILABLE: Final[bool] = ocr_available()

OCR_UNAVAILABLE_REASON: Final[str] = (
    "This document appears to be scanned: its pages carry images rather than a "
    "text layer. No optical character recognition engine is installed "
    "(pytesseract with the tesseract binary, or easyocr), so its text cannot be "
    "read. Nothing has been guessed. Enter the clinical details manually, or "
    "supply a text-based PDF exported from the reporting system."
)


@dataclass(frozen=True)
class PdfPage:
    """One page's extracted text."""

    number: int          # 1-based, as a reader would cite it
    text: str
    char_count: int

    @property
    def looks_scanned(self) -> bool:
        return self.char_count < _MIN_CHARS_PER_PAGE


@dataclass(frozen=True)
class PdfExtraction:
    """The outcome of reading a PDF's text layer."""

    pages: tuple[PdfPage, ...]
    page_count: int
    #: Concatenated text, page-separated. Empty when nothing could be read.
    text: str
    #: True when no page yielded a usable text layer.
    is_scanned: bool
    #: 1-based numbers of pages that yielded almost nothing.
    scanned_pages: tuple[int, ...]
    reader_name: str
    reader_version: str
    #: Populated when the document could not be read at all.
    failure: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def readable(self) -> bool:
        return self.failure is None and not self.is_scanned and bool(self.text.strip())


def extract_pdf_text(content: bytes) -> PdfExtraction:
    """Read a PDF's embedded text layer.

    Never raises: a malformed document returns a failure result, because an
    upload endpoint must degrade to an honest message rather than a stack trace.
    """
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:      # pragma: no cover - hard dependency
        return _failed(f"No PDF reader is installed ({exc}).")

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        return _failed(f"The PDF could not be opened: {type(exc).__name__}.")

    if getattr(reader, "is_encrypted", False):
        # An empty-password decrypt is worth one attempt; anything else is a
        # document the user must unlock themselves.
        try:
            if reader.decrypt("") == 0:
                return _failed(
                    "The PDF is password-protected. Remove the protection and "
                    "upload it again; the platform will not attempt to bypass "
                    "it.")
        except Exception:
            return _failed("The PDF is encrypted and could not be opened.")

    pages: list[PdfPage] = []
    warnings: list[str] = []

    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            text = ""
            warnings.append(
                f"Page {index} could not be read ({type(exc).__name__}); it is "
                "treated as containing no text rather than partially guessed.")
        cleaned = text.strip()
        pages.append(PdfPage(number=index, text=cleaned,
                             char_count=len(cleaned)))

    if not pages:
        return _failed("The PDF contains no pages.")

    scanned = tuple(p.number for p in pages if p.looks_scanned)
    all_scanned = len(scanned) == len(pages)

    if all_scanned:
        warnings.append(OCR_UNAVAILABLE_REASON)
    elif scanned:
        warnings.append(
            f"Page(s) {', '.join(str(n) for n in scanned)} carry little or no "
            "text and may be scanned images. Any detail on those pages was not "
            "read and must be entered manually."
        )

    return PdfExtraction(
        pages=tuple(pages),
        page_count=len(pages),
        text="\n\n".join(p.text for p in pages if p.text),
        is_scanned=all_scanned,
        scanned_pages=scanned,
        reader_name=PDF_READER_NAME,
        reader_version=PDF_READER_VERSION,
        failure=None,
        warnings=tuple(warnings),
    )


def _failed(reason: str) -> PdfExtraction:
    return PdfExtraction(
        pages=(), page_count=0, text="", is_scanned=False, scanned_pages=(),
        reader_name=PDF_READER_NAME, reader_version=PDF_READER_VERSION,
        failure=reason, warnings=(reason,),
    )
