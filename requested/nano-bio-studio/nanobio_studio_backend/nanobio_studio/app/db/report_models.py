"""Storage for medical report assessments.

Sensitivity
-----------
These rows hold uploaded documents and clinical fields. Even though intake is
restricted to synthetic and de-identified content (``app/reports/policy.py``),
the schema is built as if it held protected health information, so that
tightening the policy later is a configuration change rather than a rewrite:

* the document body is stored in its own table, so listing assessments never
  touches it;
* every access is attributable — owner, timestamp, action — via an append-only
  audit table keyed on ``user_id``;
* deletion is real and cascades to the document body, not a soft flag;
* a retention deadline is recorded on every assessment so an expiry job has
  something to act on.

**No column here is ever written to a log.** The application logs identifiers
and counts only.

Not yet implemented, and stated rather than implied
---------------------------------------------------
Encryption at rest. The document body is stored as bytes in the database file.
That is acceptable for synthetic content and is exactly why real patient data is
refused at intake.
"""

from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nanobio_studio.app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


#: Default retention for an assessment. Short by design: this is a working
#: artefact, not a record system. Extended only by explicit user action.
DEFAULT_RETENTION = timedelta(days=30)


class AssessmentStatus(str, enum.Enum):
    #: Uploaded and validated; fields not yet reviewed.
    AWAITING_REVIEW = "awaiting_review"
    #: The user has confirmed the clinical fields.
    CONFIRMED = "confirmed"
    #: Confirmed fields were carried into a design session.
    MAPPED_TO_WORKFLOW = "mapped_to_workflow"


class ReportAssessment(Base):
    """One uploaded report and the clinical fields confirmed from it."""

    __tablename__ = "report_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False,
        index=True)

    #: Neutralised display name. Never the raw client filename.
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    #: SHA-256 of the uploaded bytes; identifies the document without its name.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False,
                                              index=True)
    format_key: Mapped[str] = mapped_column(String(16), nullable=False)
    media_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    #: Declared classification, and the recorded attestation behind it.
    classification: Mapped[str] = mapped_column(String(32), nullable=False,
                                                index=True)
    attested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    policy_version: Mapped[str] = mapped_column(String(48), nullable=False)

    #: Slug when created from a synthetic fixture; null for a user upload.
    fixture_slug: Mapped[str | None] = mapped_column(String(80), nullable=True,
                                                      index=True)

    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus, native_enum=False, length=32),
        nullable=False, default=AssessmentStatus.AWAITING_REVIEW, index=True)

    # --- extraction provenance ---------------------------------------------
    # Recorded on every assessment so a stored record stays interpretable, and
    # so a record created while no engine existed can never later be mistaken
    # for engine output.
    extraction_status: Mapped[str] = mapped_column(String(48), nullable=False)
    extraction_engine: Mapped[str] = mapped_column(String(80), nullable=False)
    extraction_engine_version: Mapped[str] = mapped_column(String(48),
                                                            nullable=False)
    extraction_contract_version: Mapped[str] = mapped_column(String(48),
                                                              nullable=False)

    #: JSON array of confirmed fields, each with its own provenance.
    confirmed_fields_json: Mapped[str | None] = mapped_column(Text,
                                                               nullable=True)
    #: JSON of the extraction result as produced, kept alongside any user
    #: corrections so an override is always visible as an override.
    extraction_result_json: Mapped[str | None] = mapped_column(Text,
                                                                nullable=True)

    #: Set once confirmed fields are carried into a design session.
    mapped_disease: Mapped[str | None] = mapped_column(String(120),
                                                        nullable=True)
    mapped_subtype: Mapped[str | None] = mapped_column(String(160),
                                                        nullable=True)
    mapped_drug: Mapped[str | None] = mapped_column(String(160), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow,
                                                 index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow,
                                                 onupdate=utcnow)
    #: When this assessment becomes eligible for automatic disposal.
    retain_until: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                    nullable=False, index=True)

    document: Mapped["ReportDocument"] = relationship(
        back_populates="assessment", cascade="all, delete-orphan",
        uselist=False)


class ReportDocument(Base):
    """The uploaded bytes, in their own table.

    Separated so that listing assessments never loads document content, and so
    the sensitive column has exactly one access path.
    """

    __tablename__ = "report_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("report_assessments.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True)

    #: NOT ENCRYPTED AT REST. See the module docstring: this is why intake is
    #: restricted to synthetic and de-identified documents.
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    #: Decoded text when the format was readable; null for a PDF, which the
    #: platform cannot currently read.
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    assessment: Mapped[ReportAssessment] = relationship(
        back_populates="document")


class ReportAuditEvent(str, enum.Enum):
    UPLOADED = "uploaded"
    VIEWED = "viewed"
    DOWNLOADED = "downloaded"
    CONFIRMED = "confirmed"
    MAPPED = "mapped_to_workflow"
    DEIDENTIFIED = "deidentified"
    DELETED = "deleted"
    REFUSED = "refused"


class ReportAuditLog(Base):
    """Append-only access trail for report assessments.

    Keyed on ``user_id`` and ``assessment_id`` only. ``detail`` is for
    non-sensitive context — a refusal code, a field count — and **must never**
    carry document content, a filename or a clinical value.
    """

    __tablename__ = "report_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event: Mapped[ReportAuditEvent] = mapped_column(
        Enum(ReportAuditEvent, native_enum=False, length=32), nullable=False,
        index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True,
        index=True)
    #: Not a foreign key: the trail must outlive the assessment it describes,
    #: which is the entire point of auditing a deletion.
    assessment_id: Mapped[int | None] = mapped_column(Integer, nullable=True,
                                                       index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow,
                                                 index=True)


Index("ix_report_assessments_owner_created",
      ReportAssessment.owner_id, ReportAssessment.created_at)
Index("ix_report_audit_user_time", ReportAuditLog.user_id,
      ReportAuditLog.created_at)
