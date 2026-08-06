"""Clinical field extraction — contract, provenance model, and the live engine.

WHAT IS CONNECTED
-----------------
A **rule-based oncology reader** (``clinical_extractor.py``) operating on text
recovered from the document (``pdf_text.py`` for PDFs, direct decode for plain
text). Every field it returns carries the verbatim excerpt and page that
produced it, so a reviewer can check the claim against the document.

HONEST STANDING OF ITS OUTPUT
-----------------------------
It is **not** a trained model and has **not** been calibrated or validated
against annotated reports. Its accuracy on real-world documents is **unmeasured**.
The ``confidence`` figure is a heuristic pattern-strength score, **not** a
probability: 0.9 means "matched an explicitly labelled field", not "90% likely
correct".

That is why every clinically material field still requires human confirmation,
and why an inferred or ambiguous reading can never be promoted automatically.
The reader is an assistant that shows its working, not an authority.

WHAT REMAINS UNAVAILABLE
------------------------
**OCR.** A scanned report is detected and reported as unreadable; no OCR engine
is installed (see ``pdf_text.OCR_UNAVAILABLE_REASON``). Nothing is guessed.

HISTORY
-------
An audit (2026-08-02) found no report-processing capability anywhere in the
legacy Streamlit application — no PDF reader, no OCR, no clinical NLP — so
nothing was migrated. This engine was written for this platform, which is
precisely why its evidence standing is stated so plainly above.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Sequence

from nanobio_studio.app.reports.clinical_extractor import (
    EXTRACTOR_NAME,
    EXTRACTOR_VERSION,
    extract_clinical_fields,
)
from nanobio_studio.app.reports.pdf_text import (
    OCR_UNAVAILABLE_REASON,
    PDF_READER_NAME,
    PDF_READER_VERSION,
    extract_pdf_text,
    ocr_available,
)

__all__ = [
    "EXTRACTION_CONTRACT_VERSION",
    "ENGINE_NAME",
    "ENGINE_VERSION",
    "EngineStatus",
    "FieldProvenance",
    "ExtractedField",
    "ExtractionResult",
    "CLINICAL_FIELDS",
    "FIELD_KEYS",
    "extract",
    "extract_from_document",
    "engine_is_connected",
]

#: Version of the *contract* — the shape of a result. Bumped when the field set
#: or provenance model changes. Distinct from the engine version, so a stored
#: assessment stays interpretable when either moves independently.
EXTRACTION_CONTRACT_VERSION = "extraction-contract-2.0.0"

ENGINE_NAME = EXTRACTOR_NAME
ENGINE_VERSION = EXTRACTOR_VERSION


class EngineStatus(str, enum.Enum):
    """Outcome of an extraction attempt."""

    COMPLETED = "completed"
    #: The document could not be read: a scanned PDF with no OCR available, or
    #: an unreadable file. No field is guessed.
    DOCUMENT_UNREADABLE = "document_unreadable"
    #: The engine ran and failed. No partial result is offered.
    FAILED = "failed"
    #: Retained so assessments stored before the engine existed still parse.
    NO_ENGINE_CONNECTED = "no_engine_connected"


class FieldProvenance(str, enum.Enum):
    """Where a field's value came from.

    The report-derived values are required by the review workflow to be visibly
    distinct: a reader must always be able to tell a quotation from a deduction.
    ``INFERRED``, ``AMBIGUOUS`` and ``CONFLICTING`` are **never** auto-promoted
    to a confirmed value; each requires an explicit human decision.
    """

    #: The report states this in so many words. Carries a supporting excerpt.
    EXPLICITLY_STATED = "explicitly_stated"
    #: Derived by combining other findings. Requires human confirmation.
    INFERRED = "inferred"
    #: The document supports more than one reading.
    AMBIGUOUS = "ambiguous"
    #: The document states two different values and does not reconcile them.
    CONFLICTING = "conflicting"
    #: The document does not contain it. Not an error, never a blank guess.
    NOT_FOUND = "not_found"
    #: A human typed it.
    USER_ENTERED = "user_entered"
    #: A human overrode an engine value. The original is retained alongside.
    USER_CORRECTED = "user_corrected"


#: The clinical fields the review workflow understands.
#:
#: `maps_to_workflow` marks the three that can flow into Disease & Therapeutic
#: Selection. `consumed_by_engines` is False for every field, because that is
#: the truth: the design score takes physicochemical parameters only and the PK
#: model takes a dose and four rate constants only. The interface renders this,
#: so a user is never left to assume a biomarker changed a number.
CLINICAL_FIELDS: tuple[dict[str, Any], ...] = (
    {"key": "cancer_indication", "label": "Cancer indication",
     "maps_to_workflow": "disease", "material": True},
    {"key": "histological_subtype", "label": "Histological subtype",
     "maps_to_workflow": "subtype", "material": True},
    {"key": "tumor_site", "label": "Tumour site", "maps_to_workflow": None,
     "material": True},
    {"key": "stage", "label": "Stage", "maps_to_workflow": None,
     "material": True},
    {"key": "tnm_classification", "label": "TNM classification",
     "maps_to_workflow": None, "material": False},
    {"key": "grade", "label": "Grade", "maps_to_workflow": None,
     "material": True},
    {"key": "metastatic_sites", "label": "Metastatic sites",
     "maps_to_workflow": None, "material": True},
    {"key": "er_status", "label": "ER (oestrogen receptor)",
     "maps_to_workflow": None, "material": True},
    {"key": "pr_status", "label": "PR (progesterone receptor)",
     "maps_to_workflow": None, "material": True},
    {"key": "her2_ihc", "label": "HER2 — immunohistochemistry",
     "maps_to_workflow": None, "material": True},
    {"key": "her2_ish", "label": "HER2 — in-situ hybridisation",
     "maps_to_workflow": None, "material": True},
    {"key": "her2_status", "label": "HER2 — overall status",
     "maps_to_workflow": None, "material": True},
    {"key": "her3_status", "label": "HER3", "maps_to_workflow": None,
     "material": False},
    {"key": "ki67", "label": "Ki-67 proliferation index",
     "maps_to_workflow": None, "material": False},
    {"key": "pdl1", "label": "PD-L1", "maps_to_workflow": None,
     "material": True},
    {"key": "genomic_alterations", "label": "Genomic alterations",
     "maps_to_workflow": None, "material": True},
    {"key": "pathology_findings", "label": "Pathology findings",
     "maps_to_workflow": None, "material": False},
    {"key": "current_treatment", "label": "Current or previous treatment",
     "maps_to_workflow": "drug", "material": True},
    {"key": "therapeutic_context", "label": "Therapeutic context",
     "maps_to_workflow": None, "material": False},
    {"key": "laboratory_findings", "label": "Relevant laboratory findings",
     "maps_to_workflow": None, "material": False},
    {"key": "report_date", "label": "Report date", "maps_to_workflow": None,
     "material": False},
    {"key": "document_type", "label": "Document type",
     "maps_to_workflow": None, "material": False},
)

FIELD_KEYS: tuple[str, ...] = tuple(f["key"] for f in CLINICAL_FIELDS)

_LABELS: dict[str, str] = {f["key"]: f["label"] for f in CLINICAL_FIELDS}


@dataclass(frozen=True)
class ExtractedField:
    """One clinical field, with the evidence for it."""

    key: str
    label: str
    value: str | None
    provenance: FieldProvenance
    supporting_text: str | None = None
    page: int | None = None
    #: Heuristic pattern-strength, 0.0-1.0. NOT a probability.
    confidence: float = 0.0
    #: Competing readings when the document conflicts with itself.
    alternatives: tuple[str, ...] = ()
    #: Every excerpt that supports the reading, including each side of a conflict.
    supporting_excerpts: tuple[str, ...] = ()
    note: str | None = None

    @property
    def needs_human_decision(self) -> bool:
        """Values that must not be auto-promoted into the workflow."""
        return self.provenance in (FieldProvenance.INFERRED,
                                   FieldProvenance.AMBIGUOUS,
                                   FieldProvenance.CONFLICTING)


@dataclass(frozen=True)
class ExtractionResult:
    """The outcome of attempting to extract clinical fields from a document."""

    status: EngineStatus
    engine_name: str
    engine_version: str
    contract_version: str
    fields: tuple[ExtractedField, ...]
    message: str
    limitations: tuple[str, ...] = ()
    document_text: str | None = None
    page_count: int | None = None
    #: Reader provenance, so a stored result records how the text was obtained.
    reader_name: str | None = None
    reader_version: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        """Reject a result that violates the provenance contract."""
        for f in self.fields:
            if f.provenance is FieldProvenance.NOT_FOUND and f.value:
                raise ValueError(
                    f"{f.key}: NOT_FOUND cannot carry a value ({f.value!r})")
            if (f.provenance is FieldProvenance.EXPLICITLY_STATED
                    and not f.supporting_text):
                raise ValueError(
                    f"{f.key}: EXPLICITLY_STATED requires a supporting text "
                    "span, otherwise the claim cannot be checked")
            if f.provenance is FieldProvenance.CONFLICTING and not f.alternatives:
                raise ValueError(
                    f"{f.key}: CONFLICTING requires the competing reading(s)")


def engine_is_connected() -> bool:
    """True: a rule-based extraction engine is wired in."""
    return True


_BASE_LIMITATIONS: tuple[str, ...] = (
    "Extraction is performed by a rule-based reader. It is NOT a trained model, "
    "has NOT been calibrated or validated against annotated reports, and its "
    "accuracy on real-world documents is unmeasured.",
    "The confidence figure is a heuristic pattern-strength score, not a "
    "probability. 0.9 means the value came from an explicitly labelled field, "
    "not that it is 90% likely to be correct.",
    "Check every value against the supporting excerpt before confirming it. "
    "An inferred, ambiguous or conflicting reading is never confirmed "
    "automatically.",
    "No value taken from a report changes any calculated result. The design "
    "impact score consumes physicochemical parameters only, and the "
    "pharmacokinetic model consumes a dose and four rate constants only.",
    "This pathway provides no clinical interpretation, no diagnosis, no "
    "prognosis and no treatment recommendation.",
)


def _limitations(extra: Sequence[str] = ()) -> tuple[str, ...]:
    return _BASE_LIMITATIONS + tuple(extra)


def _field_from(key: str, data: dict) -> ExtractedField:
    return ExtractedField(
        key=key,
        label=_LABELS.get(key, key),
        value=data.get("value"),
        provenance=FieldProvenance(data.get("status", "not_found")),
        supporting_text=data.get("excerpt"),
        page=data.get("page"),
        confidence=float(data.get("confidence") or 0.0),
        alternatives=tuple(data.get("alternatives") or ()),
        supporting_excerpts=tuple(data.get("supporting_excerpts") or ()),
        note=data.get("note"),
    )


def _all_not_found(note: str) -> tuple[ExtractedField, ...]:
    return tuple(
        ExtractedField(key=spec["key"], label=spec["label"], value=None,
                       provenance=FieldProvenance.NOT_FOUND, note=note)
        for spec in CLINICAL_FIELDS
    )


def extract_from_document(*, content: bytes | None, text: str | None,
                          is_pdf: bool) -> ExtractionResult:
    """Run the pipeline over an uploaded document.

    ``text`` is supplied for formats decoded upstream (plain text, Markdown);
    ``content`` is the raw bytes, used for PDFs.
    """
    pages: list[tuple[int, str]]
    reader_name: str | None = None
    reader_version: str | None = None
    warnings: list[str] = []
    page_count: int | None = None
    document_text: str | None = None

    if is_pdf:
        if content is None:      # pragma: no cover - defensive
            return _unreadable("No document content was supplied.")
        pdf = extract_pdf_text(content)
        reader_name, reader_version = pdf.reader_name, pdf.reader_version
        warnings.extend(pdf.warnings)
        page_count = pdf.page_count

        if pdf.failure:
            return _unreadable(pdf.failure, reader_name, reader_version,
                               tuple(warnings))
        if pdf.is_scanned:
            return _unreadable(
                OCR_UNAVAILABLE_REASON, reader_name, reader_version,
                tuple(warnings), page_count=page_count,
                extra_limitations=(
                    "Optical character recognition is not installed, so a "
                    "scanned document cannot be read at all. Its contents were "
                    "not guessed.",
                ))
        pages = [(p.number, p.text) for p in pdf.pages]
        document_text = pdf.text
    else:
        if not (text or "").strip():
            return _unreadable("The document contained no readable text.")
        pages = [(1, text or "")]
        document_text = text
        page_count = 1
        reader_name, reader_version = "utf-8-decode", "builtin"

    try:
        extracted = extract_clinical_fields(pages)
    except Exception as exc:
        # A failed extraction offers no partial result: a half-read clinical
        # document is more dangerous than an unread one.
        return ExtractionResult(
            status=EngineStatus.FAILED,
            engine_name=ENGINE_NAME, engine_version=ENGINE_VERSION,
            contract_version=EXTRACTION_CONTRACT_VERSION,
            fields=_all_not_found(
                "Extraction failed; this field was not read from the document."),
            message=(
                "Automatic extraction failed. No field was read from the "
                "document, and nothing has been guessed. Enter the clinical "
                "details manually."),
            limitations=_limitations((
                f"The extraction engine raised {type(exc).__name__}.",)),
            document_text=document_text, page_count=page_count,
            reader_name=reader_name, reader_version=reader_version,
            warnings=tuple(warnings),
        )

    fields = tuple(_field_from(spec["key"], extracted.get(spec["key"], {}))
                   for spec in CLINICAL_FIELDS)

    found = sum(1 for f in fields
                if f.provenance is not FieldProvenance.NOT_FOUND)
    needs = sum(1 for f in fields if f.needs_human_decision)

    result = ExtractionResult(
        status=EngineStatus.COMPLETED,
        engine_name=ENGINE_NAME, engine_version=ENGINE_VERSION,
        contract_version=EXTRACTION_CONTRACT_VERSION,
        fields=fields,
        message=(
            f"Read {found} of {len(fields)} fields from the document"
            + (f"; {needs} "
               + ("needs" if needs == 1 else "need")
               + " an explicit decision because "
               + ("it was" if needs == 1 else "they were")
               + " inferred, ambiguous or contradictory" if needs else "")
            + ". Check each value against its supporting excerpt before "
              "confirming."),
        limitations=_limitations(),
        document_text=document_text, page_count=page_count,
        reader_name=reader_name, reader_version=reader_version,
        warnings=tuple(warnings),
    )
    result.validate()
    return result


def _unreadable(reason: str, reader_name: str | None = None,
                reader_version: str | None = None,
                warnings: tuple[str, ...] = (),
                page_count: int | None = None,
                extra_limitations: Sequence[str] = ()) -> ExtractionResult:
    return ExtractionResult(
        status=EngineStatus.DOCUMENT_UNREADABLE,
        engine_name=ENGINE_NAME, engine_version=ENGINE_VERSION,
        contract_version=EXTRACTION_CONTRACT_VERSION,
        fields=_all_not_found(
            "The document could not be read, so this field was not extracted."),
        message=reason,
        limitations=_limitations(extra_limitations),
        document_text=None, page_count=page_count,
        reader_name=reader_name, reader_version=reader_version,
        warnings=warnings or (reason,),
    )


def extract(document_text: str | None = None,
            page_count: int | None = None) -> ExtractionResult:
    """Backwards-compatible entry point for already-decoded text."""
    return extract_from_document(content=None, text=document_text, is_pdf=False)


#: Re-exported so callers can report OCR availability without importing deeper.
OCR_IS_AVAILABLE = ocr_available
PDF_READER = (PDF_READER_NAME, PDF_READER_VERSION)
