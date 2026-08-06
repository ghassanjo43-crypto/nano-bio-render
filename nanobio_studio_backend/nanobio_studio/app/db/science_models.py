"""Persistence for the Scientific Readiness Framework.

Three tables, added alongside the existing schema rather than altering it:

* ``science_data_records`` — one row per scientific field per study, carrying
  the value and its full provenance.
* ``science_readiness_snapshots`` — an immutable record of an assessment, so a
  historical result stays interpretable after the data or the rules change.

Both hang off ``workspace_runs.id`` by an indexed integer, and both carry the
owner so the existing ownership checks apply unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from nanobio_studio.app.db.base import Base

# Registers the ``organizations`` table in the shared metadata. Needed because
# the ``organization_id`` foreign key below resolves by table name, and a test
# that imports only this module would otherwise fail at mapper configuration
# with "could not find table 'organizations'".
from nanobio_studio.app.db import organization_models  # noqa: F401,E402
from nanobio_studio.app.science.statuses import ScientificStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScienceDataRecord(Base):
    """One scientific value with its provenance, for one study.

    ``value_text`` stores every value as text on purpose: the dictionary owns
    the type, and a per-type column set would duplicate that knowledge and
    guarantee drift. Validation happens in ``science/records.py``.
    """

    __tablename__ = "science_data_records"
    __table_args__ = (
        UniqueConstraint("study_id", "field_id", name="uq_science_field"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Owning organization. Denormalised onto every record rather than derived
    #: through the study, so the boundary can be a single indexed predicate in
    #: the same WHERE clause that finds the row. See
    #: ``db/organization_models.py`` for why.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    study_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_runs.id", ondelete="CASCADE"),
        nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False, index=True)

    #: Stable identifier from the data dictionary.
    field_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    status: Mapped[ScientificStatus] = mapped_column(
        Enum(ScientificStatus, native_enum=False, length=32),
        nullable=False, default=ScientificStatus.MISSING, index=True)

    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    measurement_method: Mapped[str | None] = mapped_column(String(160),
                                                            nullable=True)
    #: JSON: medium, pH, temperature, ionic strength, other.
    conditions_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    batch_identifier: Mapped[str | None] = mapped_column(String(120),
                                                          nullable=True)
    measured_on: Mapped[str | None] = mapped_column(String(32), nullable=True)
    laboratory: Mapped[str | None] = mapped_column(String(200), nullable=True)
    uncertainty: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(64),
                                                             nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Points at report_documents.id when evidence is attached. Deliberately
    #: not a foreign key: deleting an attachment must not delete the record of
    #: what was measured.
    evidence_attachment_id: Mapped[int | None] = mapped_column(Integer,
                                                                nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  nullable=False,
                                                  default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  nullable=False,
                                                  default=utcnow,
                                                  onupdate=utcnow)


class ReadinessSnapshot(Base):
    """An immutable assessment, kept so history stays interpretable.

    Records the rules-engine and dictionary versions alongside the result. When
    a rule changes later, an old snapshot still says which rules produced it.
    """

    __tablename__ = "science_readiness_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Owning organization. Denormalised onto every record rather than derived
    #: through the study, so the boundary can be a single indexed predicate in
    #: the same WHERE clause that finds the row. See
    #: ``db/organization_models.py`` for why.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    study_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_runs.id", ondelete="CASCADE"),
        nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False, index=True)

    rules_engine_version: Mapped[str] = mapped_column(String(64),
                                                       nullable=False)
    dictionary_version: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Engine version of any scientific model involved, when applicable.
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: The full assessment, verbatim.
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    #: The records the assessment was computed from, so it can be re-checked.
    input_records_json: Mapped[str] = mapped_column(Text, nullable=False)

    #: Why the snapshot was taken.
    trigger: Mapped[str] = mapped_column(String(64), nullable=False,
                                         default="manual")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  nullable=False,
                                                  default=utcnow, index=True)


Index("ix_science_records_study_field",
      ScienceDataRecord.study_id, ScienceDataRecord.field_id)
Index("ix_readiness_snapshots_study_created",
      ReadinessSnapshot.study_id, ReadinessSnapshot.created_at)
