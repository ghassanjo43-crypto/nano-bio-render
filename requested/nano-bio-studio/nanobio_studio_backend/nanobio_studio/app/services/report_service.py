"""Medical report assessment service.

Responsibilities: validate, apply intake policy, run the extraction pipeline,
store, audit, confirm, map and delete. It performs **no clinical
interpretation**: the extractor reports what the document says, and a human
decides what that means.

Two rules this module exists to enforce
---------------------------------------
1. **A value never gains authority it did not have.** An inferred, ambiguous or
   conflicting field cannot become a confirmed workflow value without an
   explicit human decision; ``confirm_fields`` rejects the attempt.
2. **A report cannot reach a calculation.** Only three fields map onward
   (disease, subtype, drug) and they map into the *therapeutic context*, which
   the audit and the UI both state does not affect any calculated number. The
   design score consumes physicochemical parameters only; the PK model consumes
   a dose and four rate constants only.

Logging discipline: this module logs identifiers, counts and codes. It never
logs document bytes, filenames or clinical values.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.report_models import (
    DEFAULT_RETENTION,
    AssessmentStatus,
    ReportAssessment,
    ReportAuditEvent,
    ReportAuditLog,
    ReportDocument,
    utcnow,
)
from nanobio_studio.app.reports.extraction import (
    CLINICAL_FIELDS,
    FIELD_KEYS,
    FieldProvenance,
    extract_from_document,
)
from nanobio_studio.app.reports.policy import (
    DocumentClassification,
    PolicyRefusal,
    evaluate_intake,
)
from nanobio_studio.app.reports.validation import ValidationError, validate_upload

__all__ = [
    "ReportServiceError",
    "record_audit",
    "create_assessment",
    "list_assessments",
    "get_assessment",
    "load_document",
    "confirm_fields",
    "map_to_workflow",
    "delete_assessment",
    "purge_expired",
    "assessment_summary",
    "assessment_detail",
]

#: Provenance values a confirmed field may carry. `INFERRED`, `AMBIGUOUS` and
#: `CONFLICTING` are absent on purpose: each describes an unresolved reading, so
#: confirming one requires the user to either accept it (becoming
#: USER_CORRECTED) or type a value (becoming USER_ENTERED).
_CONFIRMABLE = {
    FieldProvenance.EXPLICITLY_STATED.value,
    FieldProvenance.USER_ENTERED.value,
    FieldProvenance.USER_CORRECTED.value,
    FieldProvenance.NOT_FOUND.value,
}


class ReportServiceError(RuntimeError):
    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


async def record_audit(session: AsyncSession, *, event: ReportAuditEvent,
                       user_id: int | None, assessment_id: int | None = None,
                       content_hash: str | None = None,
                       detail: str | None = None) -> None:
    """Append an audit entry.

    ``detail`` must carry only non-sensitive context — a refusal code, a count.
    It is truncated defensively so an oversized value cannot bloat the trail.
    """
    session.add(ReportAuditLog(
        event=event, user_id=user_id, assessment_id=assessment_id,
        content_hash=content_hash,
        detail=(detail[:500] if detail else None),
    ))


async def create_assessment(
    session: AsyncSession,
    *,
    owner_id: int,
    filename: str | None,
    content: bytes,
    classification: DocumentClassification,
    attested: bool,
    fixture_slug: str | None = None,
    retention_days: int | None = None,
) -> tuple[ReportAssessment, dict[str, Any]]:
    """Validate, apply policy, store and audit an uploaded document.

    Returns the assessment and the extraction result as a serialisable dict.
    """
    try:
        document = validate_upload(filename, content)
    except ValidationError as exc:
        await record_audit(session, event=ReportAuditEvent.REFUSED,
                           user_id=owner_id, detail=f"validation:{exc.code}")
        raise ReportServiceError(exc.code, exc.message, exc.detail) from exc

    try:
        decision = evaluate_intake(classification, attested, document.text)
    except PolicyRefusal as exc:
        await record_audit(session, event=ReportAuditEvent.REFUSED,
                           user_id=owner_id,
                           content_hash=document.content_hash,
                           detail=f"policy:{exc.code}")
        raise ReportServiceError(exc.code, exc.message, exc.detail) from exc

    # Run the real extraction pipeline. PDFs go through the text-layer reader;
    # decoded text formats are read directly. A scanned PDF is reported as
    # unreadable rather than guessed at.
    result = extract_from_document(
        content=content,
        text=document.text,
        is_pdf=document.format_key == "pdf",
    )

    retention = (timedelta(days=retention_days) if retention_days
                 else DEFAULT_RETENTION)

    assessment = ReportAssessment(
        owner_id=owner_id,
        display_name=document.display_name,
        content_hash=document.content_hash,
        format_key=document.format_key,
        media_type=document.media_type,
        size_bytes=document.size_bytes,
        classification=decision.classification.value,
        attested=attested,
        policy_version=decision.policy_version,
        fixture_slug=fixture_slug,
        status=AssessmentStatus.AWAITING_REVIEW,
        extraction_status=result.status.value,
        extraction_engine=result.engine_name,
        extraction_engine_version=result.engine_version,
        extraction_contract_version=result.contract_version,
        extraction_result_json=json.dumps(_result_to_dict(result)),
        retain_until=utcnow() + retention,
    )
    assessment.document = ReportDocument(
        content=content,
        # Store the text the EXTRACTION pipeline recovered, not just what
        # validation could decode: a PDF's text layer is only available after
        # the reader has run, and the review screen needs it on every later
        # visit, not merely on the upload response.
        text_content=result.document_text or document.text)

    session.add(assessment)
    await session.flush()

    await record_audit(
        session, event=ReportAuditEvent.UPLOADED, user_id=owner_id,
        assessment_id=assessment.id, content_hash=document.content_hash,
        detail=f"format={document.format_key} "
               f"classification={decision.classification.value} "
               f"bytes={document.size_bytes}")

    payload = _result_to_dict(result)
    payload["intake_warnings"] = list(decision.warnings)
    payload["document_readable"] = document.readable
    payload["unreadable_reason"] = document.unreadable_reason
    # Returned for review, but deliberately NOT part of `_result_to_dict`: the
    # text is already stored once on the document row, and duplicating it into
    # the extraction record would double the sensitive-data footprint for no
    # benefit. Without it, manual entry would have nothing to read from.
    # The extraction pipeline recovers PDF text that `validate_upload` could
    # not, so prefer its reading when present.
    payload["document_text"] = result.document_text or document.text
    return assessment, payload


def _result_to_dict(result) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "engine_name": result.engine_name,
        "engine_version": result.engine_version,
        "contract_version": result.contract_version,
        "reader_name": result.reader_name,
        "reader_version": result.reader_version,
        "message": result.message,
        "limitations": list(result.limitations),
        "warnings": list(result.warnings),
        "page_count": result.page_count,
        "fields": [
            {
                "key": f.key,
                "label": f.label,
                "value": f.value,
                "provenance": f.provenance.value,
                "supporting_text": f.supporting_text,
                "page": f.page,
                "confidence": f.confidence,
                "alternatives": list(f.alternatives),
                "supporting_excerpts": list(f.supporting_excerpts),
                "note": f.note,
                # Stated per field so a user is never left to assume a biomarker
                # influenced a calculated number. Nothing here is consumed.
                "consumed_by_engines": False,
            }
            for f in result.fields
        ],
    }


async def list_assessments(session: AsyncSession, *,
                           owner_id: int) -> list[ReportAssessment]:
    stmt = (select(ReportAssessment)
            .where(ReportAssessment.owner_id == owner_id)
            .order_by(ReportAssessment.created_at.desc()))
    return list((await session.execute(stmt)).scalars().all())


async def get_assessment(session: AsyncSession, *, owner_id: int,
                         assessment_id: int) -> ReportAssessment:
    row = await session.get(ReportAssessment, assessment_id)
    # Ownership is checked before existence is revealed, so ids cannot be probed.
    if row is None or row.owner_id != owner_id:
        raise ReportServiceError("assessment_not_found",
                                 "The requested assessment does not exist.")
    return row


async def load_document(session: AsyncSession, *, owner_id: int,
                        assessment_id: int) -> ReportDocument:
    """Fetch the document body. Separated so it is a deliberate, audited act."""
    assessment = await get_assessment(session, owner_id=owner_id,
                                      assessment_id=assessment_id)
    stmt = select(ReportDocument).where(
        ReportDocument.assessment_id == assessment.id)
    document = (await session.execute(stmt)).scalar_one_or_none()
    if document is None:
        raise ReportServiceError("document_missing",
                                 "The stored document is no longer available.")
    return document


async def confirm_fields(session: AsyncSession, *, owner_id: int,
                         assessment_id: int,
                         fields: Sequence[dict[str, Any]]) -> ReportAssessment:
    """Record the user's confirmed clinical fields.

    Rejects any field whose provenance would grant it authority the document did
    not give it. An inferred or ambiguous reading must be resolved by the user
    first — accepted (``user_corrected``) or replaced (``user_entered``).
    """
    assessment = await get_assessment(session, owner_id=owner_id,
                                      assessment_id=assessment_id)

    known = set(FIELD_KEYS)
    confirmed: list[dict[str, Any]] = []

    for entry in fields:
        key = entry.get("key")
        if key not in known:
            raise ReportServiceError(
                "unknown_field", f"Unknown clinical field {key!r}.",
                f"Accepted fields: {', '.join(sorted(known))}")

        provenance = entry.get("provenance")
        if provenance not in _CONFIRMABLE:
            raise ReportServiceError(
                "provenance_not_confirmable",
                f"The field '{key}' cannot be confirmed with provenance "
                f"'{provenance}'.",
                "An inferred or ambiguous reading is not a confirmed value. "
                "Accept it explicitly, which records it as a user correction, "
                "or enter the value yourself.")

        value = entry.get("value")
        if provenance == FieldProvenance.NOT_FOUND.value and value:
            raise ReportServiceError(
                "invalid_field_state",
                f"The field '{key}' is marked not found but carries a value.",
                "A field the document does not contain must be left empty.")

        confirmed.append({
            "key": key,
            "value": value or None,
            "provenance": provenance,
            "supporting_text": entry.get("supporting_text"),
            "page": entry.get("page"),
            "original_value": entry.get("original_value"),
            "note": entry.get("note"),
        })

    assessment.confirmed_fields_json = json.dumps(confirmed)
    assessment.status = AssessmentStatus.CONFIRMED
    await session.flush()

    entered = sum(1 for f in confirmed
                  if f["provenance"] == FieldProvenance.USER_ENTERED.value)
    await record_audit(
        session, event=ReportAuditEvent.CONFIRMED, user_id=owner_id,
        assessment_id=assessment.id, content_hash=assessment.content_hash,
        detail=f"fields={len(confirmed)} user_entered={entered}")

    return assessment


async def map_to_workflow(session: AsyncSession, *, owner_id: int,
                          assessment_id: int, disease: str, subtype: str,
                          drug: str) -> ReportAssessment:
    """Record the therapeutic context carried into a design session.

    The triple is validated by the caller against the curated mapping, so an
    invalid disease/subtype/drug combination cannot be stored.
    """
    assessment = await get_assessment(session, owner_id=owner_id,
                                      assessment_id=assessment_id)
    if assessment.status is AssessmentStatus.AWAITING_REVIEW:
        raise ReportServiceError(
            "not_confirmed",
            "Confirm the extracted information before carrying it into a "
            "design session.")

    assessment.mapped_disease = disease
    assessment.mapped_subtype = subtype
    assessment.mapped_drug = drug
    assessment.status = AssessmentStatus.MAPPED_TO_WORKFLOW
    await session.flush()

    await record_audit(
        session, event=ReportAuditEvent.MAPPED, user_id=owner_id,
        assessment_id=assessment.id, content_hash=assessment.content_hash,
        detail="therapeutic context only; affects no calculated value")

    return assessment


async def delete_assessment(session: AsyncSession, *, owner_id: int,
                            assessment_id: int) -> str:
    """Delete an assessment and its document. Real deletion, not a flag."""
    assessment = await get_assessment(session, owner_id=owner_id,
                                      assessment_id=assessment_id)
    content_hash = assessment.content_hash
    name = assessment.display_name

    await session.delete(assessment)      # cascades to the document row
    await session.flush()

    # Audited AFTER deletion, and the trail deliberately outlives the row.
    await record_audit(
        session, event=ReportAuditEvent.DELETED, user_id=owner_id,
        assessment_id=assessment_id, content_hash=content_hash,
        detail="assessment and document deleted")

    return name


async def purge_expired(session: AsyncSession, *,
                        confirm: bool = False) -> dict[str, Any]:
    """Dispose of assessments past their retention deadline.

    Reports scope without ``confirm``, mirroring the demo-reset command: a
    disposal job that cannot be dry-run is one nobody dares to schedule.
    """
    now = utcnow()
    stmt = select(ReportAssessment).where(ReportAssessment.retain_until <= now)
    expired = list((await session.execute(stmt)).scalars().all())

    total = int((await session.execute(
        select(func.count()).select_from(ReportAssessment))).scalar_one())

    if confirm:
        for assessment in expired:
            await record_audit(
                session, event=ReportAuditEvent.DELETED,
                user_id=assessment.owner_id, assessment_id=assessment.id,
                content_hash=assessment.content_hash,
                detail="retention expiry")
            await session.delete(assessment)
        await session.flush()

    return {
        "confirmed": confirm,
        "expired": len(expired),
        "retained": total - len(expired),
        "deleted": len(expired) if confirm else 0,
    }


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def assessment_summary(assessment: ReportAssessment) -> dict[str, Any]:
    return {
        "id": assessment.id,
        "display_name": assessment.display_name,
        "content_hash": assessment.content_hash,
        "format_key": assessment.format_key,
        "size_bytes": assessment.size_bytes,
        "classification": assessment.classification,
        "fixture_slug": assessment.fixture_slug,
        "status": assessment.status.value,
        "extraction_status": assessment.extraction_status,
        "extraction_engine": assessment.extraction_engine,
        "extraction_engine_version": assessment.extraction_engine_version,
        "mapped_disease": assessment.mapped_disease,
        "mapped_subtype": assessment.mapped_subtype,
        "mapped_drug": assessment.mapped_drug,
        "created_at": assessment.created_at,
        "retain_until": assessment.retain_until,
    }


def assessment_detail(assessment: ReportAssessment,
                      document_text: str | None) -> dict[str, Any]:
    extraction = (json.loads(assessment.extraction_result_json)
                  if assessment.extraction_result_json else None)
    confirmed = (json.loads(assessment.confirmed_fields_json)
                 if assessment.confirmed_fields_json else None)
    return {
        **assessment_summary(assessment),
        "extraction_contract_version": assessment.extraction_contract_version,
        "policy_version": assessment.policy_version,
        "attested": assessment.attested,
        "extraction": extraction,
        "confirmed_fields": confirmed,
        "document_text": document_text,
        "clinical_fields": [dict(f) for f in CLINICAL_FIELDS],
    }
