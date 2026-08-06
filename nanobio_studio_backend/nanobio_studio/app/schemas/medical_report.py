"""Pydantic schemas for the Medical Report Assessment pathway.

Contract note: no schema here can express a clinical *conclusion*. A field
carries a value plus the provenance of that value, and the provenance vocabulary
makes "the report says this" and "someone typed this" structurally different
things. There is no field for a recommendation, a prognosis or a suggested
treatment, because the platform produces none.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClinicalFieldPayload(BaseModel):
    """One clinical field as confirmed by the user."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: Optional[str] = Field(None, max_length=2000)
    provenance: str = Field(
        ...,
        description=(
            "One of: explicitly_stated, user_entered, user_corrected, "
            "not_found. Deliberately excludes 'inferred' and 'ambiguous' — an "
            "unresolved reading is not a confirmed value and must be resolved "
            "by the user first."
        ),
    )
    supporting_text: Optional[str] = Field(None, max_length=4000)
    page: Optional[int] = Field(None, ge=1)
    #: The engine's original value, retained when the user overrode it so the
    #: override stays visible as an override.
    original_value: Optional[str] = Field(None, max_length=2000)
    note: Optional[str] = Field(None, max_length=1000)


class ConfirmFieldsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: List[ClinicalFieldPayload]


class MapToWorkflowRequest(BaseModel):
    """Carry a confirmed therapeutic context into a design session.

    These three values populate Disease & Therapeutic Selection. They are
    recorded for traceability and **do not affect any calculated result**: the
    design score consumes physicochemical parameters only, and the PK model
    consumes a dose and four rate constants only.
    """

    model_config = ConfigDict(extra="forbid")

    disease: str = Field(..., max_length=120)
    subtype: str = Field(..., max_length=160)
    drug: str = Field(..., max_length=160)


class UploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: int
    display_name: str
    content_hash: str
    format_key: str
    size_bytes: int
    classification: str
    status: str
    #: The extraction outcome, including its honest status when no engine is
    #: connected. Never omitted.
    extraction: Dict[str, Any]
    intake_warnings: List[str]
    document_readable: bool
    unreadable_reason: Optional[str]
    document_text: Optional[str]
    retain_until: datetime


class AssessmentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    display_name: str
    content_hash: str
    format_key: str
    size_bytes: int
    classification: str
    fixture_slug: Optional[str]
    status: str
    extraction_status: str
    extraction_engine: str
    extraction_engine_version: str
    mapped_disease: Optional[str]
    mapped_subtype: Optional[str]
    mapped_drug: Optional[str]
    created_at: datetime
    retain_until: datetime


class AssessmentDetail(AssessmentSummary):
    model_config = ConfigDict(extra="forbid")

    extraction_contract_version: str
    policy_version: str
    attested: bool
    extraction: Optional[Dict[str, Any]]
    confirmed_fields: Optional[List[Dict[str, Any]]]
    document_text: Optional[str]
    clinical_fields: List[Dict[str, Any]]


class AssessmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessments: List[AssessmentSummary]
    total: int
    #: Counts by status, over the caller's visible assessments only.
    #:
    #: Computed from the same scoped query the list comes from, never over the
    #: whole table. A summary is a disclosure like any other: a total counted
    #: across organizations would tell a member of one exactly how many patient
    #: assessments another holds, without returning a single row.
    counts: Dict[str, int] = Field(default_factory=dict)
    #: Restated on every listing so the intake restriction travels with the data.
    policy_statement: str


class SyntheticReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    purpose: str
    demonstrates: str
    filename: str
    size_bytes: int
    #: Constant. Rendered as a badge wherever a fixture appears.
    data_classification: str = "Synthetic demonstration document"


class SyntheticReportListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports: List[SyntheticReportSummary]
    fixture_version: str
    notice: str


class DeidentifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    redactions: Dict[str, int]
    total_redactions: int
    version: str
    #: Always returned. This is an aid, never a guarantee.
    limitations: List[str]


class RetentionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool
    expired: int
    retained: int
    deleted: int
    message: str


class ReportErrorResponse(BaseModel):
    """Structured failure carrying no document or clinical data."""

    model_config = ConfigDict(extra="forbid")

    error: str
    message: str
    detail: Optional[str] = None
    data_available: bool = Field(False, description="Always false on failure.")
