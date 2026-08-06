"""Medical Report Assessment routes.

Transport and authorisation only. Validation, intake policy, storage and
auditing live in the service and ``app/reports/`` packages.

Authorisation model
-------------------
Every route requires an authenticated session. Viewers may read their own
assessments but may not upload, confirm or delete — reading a document is a
different act from creating or destroying one. Ownership is always checked
before existence is revealed, so assessment ids cannot be probed.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.api.deps_auth import get_current_user
from nanobio_studio.app.db.auth_models import User, UserRole
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.db.report_models import ReportAuditEvent
from nanobio_studio.app.reports.deidentify import deidentify_text
from nanobio_studio.app.reports.fixtures import (
    REPORT_FIXTURE_VERSION,
    SYNTHETIC_REPORTS,
    fixture_by_slug,
)
from nanobio_studio.app.reports.pdf_fixtures import (
    SYNTHETIC_PDFS,
    pdf_fixture_by_slug,
)
from nanobio_studio.app.reports.policy import (
    POLICY_STATEMENT,
    DocumentClassification,
)
from nanobio_studio.app.reports.validation import MAX_UPLOAD_BYTES
from nanobio_studio.app.schemas.medical_report import (
    AssessmentDetail,
    AssessmentListResponse,
    AssessmentSummary,
    ConfirmFieldsRequest,
    DeidentifyResponse,
    MapToWorkflowRequest,
    ReportErrorResponse,
    RetentionResponse,
    SyntheticReportListResponse,
    UploadResponse,
)
from nanobio_studio.app.services import report_service as svc

router = APIRouter(prefix="/api/v1/reports", tags=["medical-reports"])

SYNTHETIC_NOTICE = (
    "These documents are entirely fabricated for software testing. The patients "
    "do not exist; the identifiers, dates, institutions and clinical findings "
    "are invented. They are not real patient data, not de-identified real data, "
    "and not derived from any real case. Loading one runs the same upload, "
    "validation and extraction path as your own file — no result is "
    "pre-supplied."
)


def _error(code: str, message: str, http: int,
           detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=http,
        content=ReportErrorResponse(error=code, message=message, detail=detail,
                                    data_available=False).model_dump(),
    )


def _require_writer(user: User) -> JSONResponse | None:
    if user.role is UserRole.VIEWER:
        return _error("forbidden",
                      "Your role can read assessments but cannot create, "
                      "modify or delete them.",
                      status.HTTP_403_FORBIDDEN)
    return None


# ===========================================================================
# Synthetic fixtures
# ===========================================================================


@router.get("/synthetic", response_model=SyntheticReportListResponse,
            summary="List the synthetic demonstration reports")
async def list_synthetic(_user: User = Depends(get_current_user)):
    return {
        "reports": [
            {
                "slug": r.slug, "title": r.title, "purpose": r.purpose,
                "demonstrates": r.demonstrates, "filename": r.filename,
                "size_bytes": len(r.as_bytes()),
            }
            # PDFs first: they exercise the extraction pipeline end to end,
            # which the plain-text fixtures deliberately do not.
            for r in (*SYNTHETIC_PDFS, *SYNTHETIC_REPORTS)
        ],
        "fixture_version": REPORT_FIXTURE_VERSION,
        "notice": SYNTHETIC_NOTICE,
    }


@router.post("/synthetic/{slug}", response_model=UploadResponse,
             status_code=status.HTTP_201_CREATED,
             responses={404: {"model": ReportErrorResponse},
                        403: {"model": ReportErrorResponse}},
             summary="Load a synthetic report through the real upload pipeline")
async def load_synthetic(slug: str,
                         user: User = Depends(get_current_user),
                         session: AsyncSession = Depends(get_auth_session)):
    """Runs the identical path a user upload takes — nothing is short-circuited."""
    if (refusal := _require_writer(user)) is not None:
        return refusal

    fixture = pdf_fixture_by_slug(slug) or fixture_by_slug(slug)
    if fixture is None:
        return _error("fixture_not_found",
                      f"No synthetic report named {slug!r}.",
                      status.HTTP_404_NOT_FOUND)

    try:
        assessment, payload = await svc.create_assessment(
            session, owner_id=user.id, filename=fixture.filename,
            content=fixture.as_bytes(),
            classification=DocumentClassification.SYNTHETIC,
            attested=True,          # fabricated content; attestation is factual
            fixture_slug=fixture.slug,
        )
    except svc.ReportServiceError as exc:
        return _error(exc.code, exc.message, status.HTTP_400_BAD_REQUEST,
                      exc.detail)

    return _upload_response(assessment, payload)


# ===========================================================================
# Upload
# ===========================================================================


def _upload_response(assessment, payload: dict) -> dict:
    return {
        "assessment_id": assessment.id,
        "display_name": assessment.display_name,
        "content_hash": assessment.content_hash,
        "format_key": assessment.format_key,
        "size_bytes": assessment.size_bytes,
        "classification": assessment.classification,
        "status": assessment.status.value,
        "extraction": {k: v for k, v in payload.items()
                       if k not in ("intake_warnings", "document_readable",
                                    "unreadable_reason", "document_text")},
        "intake_warnings": payload.get("intake_warnings", []),
        "document_readable": payload.get("document_readable", False),
        "unreadable_reason": payload.get("unreadable_reason"),
        "document_text": payload.get("document_text"),
        "retain_until": assessment.retain_until,
    }


@router.post("", response_model=UploadResponse,
             status_code=status.HTTP_201_CREATED,
             responses={400: {"model": ReportErrorResponse},
                        403: {"model": ReportErrorResponse},
                        413: {"model": ReportErrorResponse}},
             summary="Upload a medical report document",
             description=(
                 "Accepts **synthetic and de-identified documents only**. Real "
                 "patient reports are refused: this deployment has no "
                 "encryption at rest, no enforced retention schedule and no "
                 "recorded legal basis for processing patient data.\n\n"
                 "The file type is determined from its **content**, never from "
                 "the filename or the browser-supplied type.\n\n"
                 "**Extraction is rule-based and unvalidated.** Every field "
                 "carries the verbatim excerpt and page that produced it, plus "
                 "a heuristic confidence score that is NOT a probability. "
                 "Inferred, ambiguous and conflicting readings must be resolved "
                 "by a human and are never confirmed automatically.\n\n"
                 "A **scanned** PDF carries no text layer. No OCR engine is "
                 "installed, so it is reported as unreadable rather than "
                 "guessed at."
             ))
async def upload_report(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_auth_session),
    file: UploadFile = File(...),
    classification: str = Form(...),
    attested: bool = Form(False),
    retention_days: Optional[int] = Form(None),
):
    if (refusal := _require_writer(user)) is not None:
        return refusal

    try:
        declared = DocumentClassification(classification)
    except ValueError:
        return _error(
            "unsupported_classification",
            "The document classification is not recognised.",
            status.HTTP_400_BAD_REQUEST,
            "Accepted: "
            + ", ".join(c.value for c in DocumentClassification))

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        await svc.record_audit(session, event=ReportAuditEvent.REFUSED,
                               user_id=user.id, detail="validation:file_too_large")
        return _error(
            "file_too_large", "The uploaded file exceeds the maximum size.",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"The maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    try:
        assessment, payload = await svc.create_assessment(
            session, owner_id=user.id, filename=file.filename, content=content,
            classification=declared, attested=attested,
            retention_days=retention_days)
    except svc.ReportServiceError as exc:
        return _error(exc.code, exc.message, status.HTTP_400_BAD_REQUEST,
                      exc.detail)

    return _upload_response(assessment, payload)


# ===========================================================================
# Read
# ===========================================================================


@router.get("", response_model=AssessmentListResponse,
            summary="List your report assessments")
async def list_assessments(user: User = Depends(get_current_user),
                           session: AsyncSession = Depends(get_auth_session)):
    rows = await svc.list_assessments(session, owner_id=user.id)
    return {
        "assessments": [svc.assessment_summary(r) for r in rows],
        "total": len(rows),
        "policy_statement": POLICY_STATEMENT,
    }


@router.get("/{assessment_id}", response_model=AssessmentDetail,
            responses={404: {"model": ReportErrorResponse}},
            summary="Open one assessment, with its document text for review")
async def get_assessment(assessment_id: int,
                         user: User = Depends(get_current_user),
                         session: AsyncSession = Depends(get_auth_session)):
    try:
        assessment = await svc.get_assessment(session, owner_id=user.id,
                                              assessment_id=assessment_id)
        document = await svc.load_document(session, owner_id=user.id,
                                           assessment_id=assessment_id)
    except svc.ReportServiceError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)

    await svc.record_audit(session, event=ReportAuditEvent.VIEWED,
                           user_id=user.id, assessment_id=assessment.id,
                           content_hash=assessment.content_hash)

    return svc.assessment_detail(assessment, document.text_content)


@router.get("/{assessment_id}/document",
            responses={404: {"model": ReportErrorResponse}},
            summary="Download the original document")
async def download_document(assessment_id: int,
                            user: User = Depends(get_current_user),
                            session: AsyncSession = Depends(get_auth_session)):
    try:
        assessment = await svc.get_assessment(session, owner_id=user.id,
                                              assessment_id=assessment_id)
        document = await svc.load_document(session, owner_id=user.id,
                                           assessment_id=assessment_id)
    except svc.ReportServiceError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)

    await svc.record_audit(session, event=ReportAuditEvent.DOWNLOADED,
                           user_id=user.id, assessment_id=assessment.id,
                           content_hash=assessment.content_hash)

    return Response(
        content=document.content,
        media_type=assessment.media_type,
        headers={
            # `attachment` so a document never renders inline in the browser.
            "Content-Disposition":
                f'attachment; filename="{assessment.display_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.post("/{assessment_id}/deidentify", response_model=DeidentifyResponse,
             responses={404: {"model": ReportErrorResponse},
                        400: {"model": ReportErrorResponse}},
             summary="Produce a redacted copy of the document text",
             description=(
                 "Pattern-based redaction of recognisable direct identifiers. "
                 "**Not** HIPAA Safe Harbor de-identification and not "
                 "certified; it cannot detect an identifier written into "
                 "ordinary prose. The limitations are returned with every "
                 "response."
             ))
async def deidentify(assessment_id: int,
                     user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(get_auth_session)):
    if (refusal := _require_writer(user)) is not None:
        return refusal
    try:
        assessment = await svc.get_assessment(session, owner_id=user.id,
                                              assessment_id=assessment_id)
        document = await svc.load_document(session, owner_id=user.id,
                                           assessment_id=assessment_id)
    except svc.ReportServiceError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)

    if document.text_content is None:
        return _error(
            "document_not_readable",
            "This document's text cannot be read, so it cannot be redacted.",
            status.HTTP_400_BAD_REQUEST,
            "No PDF reader is installed. Redact the source document before "
            "uploading it.")

    report = deidentify_text(document.text_content)
    await svc.record_audit(
        session, event=ReportAuditEvent.DEIDENTIFIED, user_id=user.id,
        assessment_id=assessment.id, content_hash=assessment.content_hash,
        detail=f"redactions={report.total_redactions}")

    return {
        "text": report.text,
        "redactions": report.counts,
        "total_redactions": report.total_redactions,
        "version": report.version,
        "limitations": list(report.limitations),
    }


# ===========================================================================
# Confirm and map
# ===========================================================================


@router.post("/{assessment_id}/confirm", response_model=AssessmentDetail,
             responses={400: {"model": ReportErrorResponse},
                        403: {"model": ReportErrorResponse},
                        404: {"model": ReportErrorResponse}},
             summary="Confirm the clinical fields for this assessment",
             description=(
                 "An inferred or ambiguous reading cannot be confirmed "
                 "directly. Accept it explicitly (recorded as a user "
                 "correction) or enter the value yourself (recorded as user "
                 "entered). Nothing is promoted automatically."
             ))
async def confirm(assessment_id: int, request: ConfirmFieldsRequest,
                  user: User = Depends(get_current_user),
                  session: AsyncSession = Depends(get_auth_session)):
    if (refusal := _require_writer(user)) is not None:
        return refusal
    try:
        assessment = await svc.confirm_fields(
            session, owner_id=user.id, assessment_id=assessment_id,
            fields=[f.model_dump() for f in request.fields])
        document = await svc.load_document(session, owner_id=user.id,
                                           assessment_id=assessment_id)
    except svc.ReportServiceError as exc:
        http = (status.HTTP_404_NOT_FOUND if exc.code == "assessment_not_found"
                else status.HTTP_400_BAD_REQUEST)
        return _error(exc.code, exc.message, http, exc.detail)

    return svc.assessment_detail(assessment, document.text_content)


@router.post("/{assessment_id}/map", response_model=AssessmentDetail,
             responses={400: {"model": ReportErrorResponse},
                        403: {"model": ReportErrorResponse},
                        404: {"model": ReportErrorResponse}},
             summary="Carry the confirmed therapeutic context into a session",
             description=(
                 "The disease, subtype and therapeutic agent must form a valid "
                 "combination in the platform's curated mapping. They populate "
                 "Disease & Therapeutic Selection for traceability and **do "
                 "not affect any calculated result**."
             ))
async def map_to_workflow(assessment_id: int, request: MapToWorkflowRequest,
                          user: User = Depends(get_current_user),
                          session: AsyncSession = Depends(get_auth_session)):
    if (refusal := _require_writer(user)) is not None:
        return refusal

    if not _is_valid_triple(request.disease, request.subtype, request.drug):
        return _error(
            "invalid_therapeutic_context",
            "That disease, subtype and therapeutic agent are not a valid "
            "combination.",
            status.HTTP_400_BAD_REQUEST,
            "The combination must exist in the platform's curated mapping. An "
            "invalid combination is refused rather than stored.")

    try:
        assessment = await svc.map_to_workflow(
            session, owner_id=user.id, assessment_id=assessment_id,
            disease=request.disease, subtype=request.subtype,
            drug=request.drug)
        document = await svc.load_document(session, owner_id=user.id,
                                           assessment_id=assessment_id)
    except svc.ReportServiceError as exc:
        http = (status.HTTP_404_NOT_FOUND if exc.code == "assessment_not_found"
                else status.HTTP_400_BAD_REQUEST)
        return _error(exc.code, exc.message, http, exc.detail)

    return svc.assessment_detail(assessment, document.text_content)


def _is_valid_triple(disease: str, subtype: str, drug: str) -> bool:
    """Validate against the curated disease/subtype/drug mapping."""
    from nanobio_studio.app.reports.disease_mapping import is_valid_triple

    return is_valid_triple(disease, subtype, drug)


# ===========================================================================
# Delete and retention
# ===========================================================================


@router.delete("/{assessment_id}",
               responses={403: {"model": ReportErrorResponse},
                          404: {"model": ReportErrorResponse}},
               summary="Delete an assessment and its document")
async def delete_assessment(assessment_id: int,
                            user: User = Depends(get_current_user),
                            session: AsyncSession = Depends(get_auth_session)):
    if (refusal := _require_writer(user)) is not None:
        return refusal
    try:
        name = await svc.delete_assessment(session, owner_id=user.id,
                                           assessment_id=assessment_id)
    except svc.ReportServiceError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)

    return {"deleted": True, "id": assessment_id, "display_name": name,
            "note": "The document was removed. The audit entry is retained."}


@router.post("/retention/purge", response_model=RetentionResponse,
             responses={403: {"model": ReportErrorResponse}},
             summary="Dispose of assessments past their retention deadline",
             description="Without `confirm`, reports scope and deletes nothing.")
async def purge(confirm: bool = False,
                user: User = Depends(get_current_user),
                session: AsyncSession = Depends(get_auth_session)):
    if user.role is not UserRole.ADMIN:
        return _error("forbidden",
                      "Running the retention purge requires an administrator "
                      "account.", status.HTTP_403_FORBIDDEN)

    scope = await svc.purge_expired(session, confirm=confirm)
    scope["message"] = (
        f"Deleted {scope['deleted']} expired assessment(s); "
        f"{scope['retained']} retained."
        if scope["confirmed"] else
        f"Nothing was deleted. {scope['expired']} assessment(s) are past their "
        f"retention deadline; {scope['retained']} are within it."
    )
    return scope
