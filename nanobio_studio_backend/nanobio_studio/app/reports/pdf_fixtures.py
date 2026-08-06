"""Synthetic oncology report PDFs, generated at import time.

Why generated rather than checked in
------------------------------------
A binary fixture in source control cannot be reviewed in a diff. Building the
PDF from the text below means the clinical content is readable, reviewable and
obviously synthetic, while the artefact the pipeline receives is a genuine PDF
with a real text layer — the same thing a hospital system would emit.

The scanned fixture is a genuine image-only PDF: a rendered page with no text
layer at all. It is the honest way to exercise the scanned-document path, since
no OCR engine is installed and the pipeline must say so rather than guess.

WHAT THESE ARE NOT
------------------
Not real reports, not de-identified real reports, not derived from any real case
or publication. Every name, identifier, date, institution and finding is
invented. Any resemblance to a real person is coincidental.

THE RULE
--------
These are **documents**, never answers. No expected extraction result is stored
here. The values a test asserts are produced by running the real pipeline over
the real PDF — if the extractor stops finding them, the test fails, which is the
entire point.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache

__all__ = ["PDF_FIXTURE_VERSION", "SyntheticPdf", "SYNTHETIC_PDFS",
           "pdf_fixture_by_slug", "build_pdf"]

PDF_FIXTURE_VERSION = "synthetic-report-pdfs-1.0.0"

_BANNER = (
    "SYNTHETIC DEMONSTRATION DOCUMENT — NOT A REAL MEDICAL REPORT. "
    "This document is entirely fabricated for software testing. The patient "
    "does not exist. The identifiers, dates, institution and clinical findings "
    "are invented. It must not be used for any clinical purpose."
)


@dataclass(frozen=True)
class SyntheticPdf:
    slug: str
    title: str
    purpose: str
    demonstrates: str
    filename: str
    #: Lines of the document body. Rendered to a real PDF text layer.
    lines: tuple[str, ...]
    #: When True, produce an image-only PDF with no text layer.
    scanned: bool = False

    def as_bytes(self) -> bytes:
        return build_pdf(self.lines, scanned=self.scanned)


# ---------------------------------------------------------------------------
# 1. Breast pathology — the primary end-to-end fixture
# ---------------------------------------------------------------------------

_BREAST_LINES: tuple[str, ...] = (
    _BANNER,
    "",
    "FICTIONAL ONCOLOGY CENTRE — SURGICAL PATHOLOGY REPORT",
    "",
    "Patient name: JANE Q. EXAMPLE (FICTIONAL)",
    "Record number: SYN-0000001 (NOT A REAL MRN)",
    "Report date: 12 March 2026",
    "Document type: Surgical pathology report",
    "Specimen: Left breast, lumpectomy with sentinel node sampling",
    "Primary site: Left breast, upper outer quadrant",
    "",
    "DIAGNOSIS",
    "Invasive breast carcinoma of the left breast.",
    "",
    "MICROSCOPIC DESCRIPTION",
    "Sections show an invasive ductal carcinoma (NST) with moderate nuclear",
    "pleomorphism and a mitotic count of 14 per 10 high-power fields.",
    "",
    "Combined histologic grade: Grade 3 (poorly differentiated)",
    "Clinical stage: Stage IIB",
    "TNM: cT2 N1 M0",
    "",
    "No evidence of distant metastatic disease was identified on staging.",
    "",
    "IMMUNOHISTOCHEMISTRY",
    "ER: POSITIVE (95%, Allred score 8)",
    "PR: POSITIVE (80%, Allred score 7)",
    "HER2 IHC: EQUIVOCAL (2+)",
    "HER2 ISH: AMPLIFIED (HER2/CEP17 ratio 3.1)",
    "HER3: Not tested",
    "Ki-67: 45%",
    "PD-L1: Not tested",
    "",
    "MOLECULAR PATHOLOGY",
    "PIK3CA: p.H1047R mutation detected",
    "BRCA1/2: No pathogenic variant detected",
    "TP53: No pathogenic variant detected",
    "",
    "TREATMENT TO DATE",
    "No systemic therapy administered prior to surgery.",
    "",
    "LABORATORY FINDINGS",
    "Haemoglobin 11.8 g/dL; neutrophils 3.4 x10^9/L; platelets 245 x10^9/L.",
    "",
    "Reported by Dr A. Fictional, Consultant Histopathologist (FICTIONAL)",
)

# ---------------------------------------------------------------------------
# 2. Conflicting findings — exercises contradiction handling
# ---------------------------------------------------------------------------

_CONFLICT_LINES: tuple[str, ...] = (
    _BANNER,
    "",
    "FICTIONAL TEACHING HOSPITAL — MDT MEETING SUMMARY",
    "",
    "Report date: 28 January 2026",
    "Document type: MDT meeting summary",
    "Primary site: Sigmoid colon",
    "",
    "*** THIS DOCUMENT CONTAINS DELIBERATE CONTRADICTIONS FOR TESTING ***",
    "",
    "DIAGNOSIS",
    "Colorectal adenocarcinoma of the sigmoid colon.",
    "",
    "STAGING",
    "Histopathology section records: Stage II",
    "Radiology section records: Stage III",
    "These statements are not reconciled anywhere in this document.",
    "",
    "GRADE",
    "Grade 2 is recorded in one section.",
    "Grade 3 is recorded in another section.",
    "",
    "BIOMARKERS",
    "ER: Not tested",
    "PR: Not tested",
    "HER2 IHC: Not tested",
    "HER3: Not tested",
    "",
    "MOLECULAR",
    "KRAS: p.G12D mutation detected",
    "BRAF: No pathogenic variant detected",
    "",
    "TREATMENT",
    "No treatment has been recorded in this summary.",
)

# ---------------------------------------------------------------------------
# 3. Sparse report — most biomarkers genuinely absent
# ---------------------------------------------------------------------------

_SPARSE_LINES: tuple[str, ...] = (
    _BANNER,
    "",
    "FICTIONAL REGIONAL HOSPITAL — CLINIC LETTER",
    "",
    "Report date: 03 February 2026",
    "Document type: Clinic letter",
    "",
    "The patient has non-small cell lung cancer, adenocarcinoma of the right",
    "upper lobe. Metastatic deposits are present in the liver and bone.",
    "",
    "No receptor or biomarker testing has been undertaken to date.",
    "",
    "The patient commenced pembrolizumab monotherapy in January 2026 and has",
    "received two cycles.",
)


def _blank_line_count(lines: tuple[str, ...]) -> int:
    return sum(1 for line in lines if line)


SYNTHETIC_PDFS: tuple[SyntheticPdf, ...] = (
    SyntheticPdf(
        slug="synthetic-pdf-breast-oncology",
        title="Synthetic breast oncology pathology report (PDF)",
        purpose=(
            "A complete, internally consistent surgical pathology report in "
            "PDF form, covering indication, histology, grade, stage, the full "
            "receptor panel and molecular results."
        ),
        demonstrates=(
            "The primary end-to-end extraction path. Note that HER2 is "
            "reported as equivocal by immunohistochemistry and amplified by "
            "in-situ hybridisation — the overall status is therefore DERIVED, "
            "marked as inferred, and requires an explicit human decision."
        ),
        filename="synthetic-breast-oncology.pdf",
        lines=_BREAST_LINES,
    ),
    SyntheticPdf(
        slug="synthetic-pdf-conflicting",
        title="Synthetic report with conflicting findings (PDF)",
        purpose=(
            "An MDT summary that records two different stages and two "
            "different grades, and never reconciles them."
        ),
        demonstrates=(
            "Contradiction handling. A conflict is surfaced with both readings "
            "and both supporting excerpts; the platform does not choose."
        ),
        filename="synthetic-conflicting.pdf",
        lines=_CONFLICT_LINES,
    ),
    SyntheticPdf(
        slug="synthetic-pdf-sparse",
        title="Synthetic clinic letter with absent biomarkers (PDF)",
        purpose=(
            "A narrative letter that states an indication and metastatic sites "
            "but reports no receptor or biomarker testing at all."
        ),
        demonstrates=(
            "Honest absence. Untested biomarkers are reported as not found "
            "rather than filled with a default, and the manual-entry fallback "
            "carries the rest."
        ),
        filename="synthetic-sparse.pdf",
        lines=_SPARSE_LINES,
    ),
    SyntheticPdf(
        slug="synthetic-pdf-scanned",
        title="Synthetic scanned report, image only (PDF)",
        purpose=(
            "A genuine image-only PDF with no text layer, as a scanner would "
            "produce."
        ),
        demonstrates=(
            "Scanned-document detection. No OCR engine is installed, so the "
            "pipeline reports the document as unreadable rather than guessing "
            "at its contents."
        ),
        filename="synthetic-scanned.pdf",
        lines=_BREAST_LINES,
        scanned=True,
    ),
)


def pdf_fixture_by_slug(slug: str) -> SyntheticPdf | None:
    for pdf in SYNTHETIC_PDFS:
        if pdf.slug == slug:
            return pdf
    return None


@lru_cache(maxsize=8)
def _cached_pdf(lines: tuple[str, ...], scanned: bool) -> bytes:
    return _render_pdf(lines, scanned)


def build_pdf(lines: tuple[str, ...], *, scanned: bool = False) -> bytes:
    """Render lines to a real PDF. Cached, since fixtures are immutable."""
    return _cached_pdf(tuple(lines), scanned)


def _render_pdf(lines: tuple[str, ...], scanned: bool) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    if scanned:
        # An image-only page: the text is DRAWN as vector strokes, not placed as
        # selectable text, so the PDF genuinely carries no text layer. This is
        # what a scanner produces, and it is what the detector must catch.
        pdf.setFillGray(0.96)
        pdf.rect(0, 0, width, height, stroke=0, fill=1)
        pdf.setFillGray(0.35)
        y = height - inch
        for line in lines[:28]:
            if line:
                _draw_as_strokes(pdf, 0.9 * inch, y, line[:70])
            y -= 14
            if y < inch:
                break
        pdf.showPage()
        pdf.save()
        return buf.getvalue()

    pdf.setFont("Helvetica", 9)
    y = height - inch
    for line in lines:
        if y < inch:
            pdf.showPage()
            pdf.setFont("Helvetica", 9)
            y = height - inch
        if line:
            pdf.drawString(0.9 * inch, y, line[:110])
        y -= 12
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


def _draw_as_strokes(pdf, x: float, y: float, text: str) -> None:
    """Draw a line of text as meaningless rectangles.

    Produces the visual impression of text without any extractable characters —
    the defining property of a scanned page for this pipeline's purposes.
    """
    cursor = x
    for char in text:
        if char == " ":
            cursor += 3.2
            continue
        pdf.rect(cursor, y, 3.0, 6.0, stroke=0, fill=1)
        cursor += 4.2
