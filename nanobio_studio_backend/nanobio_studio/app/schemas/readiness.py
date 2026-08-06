"""Schemas for the Scientific Readiness endpoints.

Bounds here are structural. No field carries a scientific default: a default
would silently manufacture provenance the study does not have.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from nanobio_studio.app.science.records import (
    ISO_DATE_FORMAT,
    InvalidMeasurementDate,
    parse_iso_date,
)


class ConditionsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medium: Optional[str] = Field(None, max_length=160)
    ph: Optional[float] = Field(None, ge=0, le=14)
    temperature_c: Optional[float] = Field(None, ge=-273.15, le=1000)
    ionic_strength_mm: Optional[float] = Field(None, ge=0)
    other: Dict[str, str] = Field(default_factory=dict)


class ScienceRecordUpsertRequest(BaseModel):
    """One scientific value with its provenance."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(..., description="A ScientificStatus value.")
    value: Optional[Any] = None
    unit: Optional[str] = Field(None, max_length=32)
    measurement_method: Optional[str] = Field(None, max_length=160)
    conditions: Optional[ConditionsPayload] = None
    source_citation: Optional[str] = Field(None, max_length=2000)
    batch_identifier: Optional[str] = Field(None, max_length=120)
    measured_on: Optional[str] = Field(
        None, max_length=32,
        description=f"Calendar date of the measurement, as {ISO_DATE_FORMAT}. "
                    "Rejected if it is not a real date.",
        json_schema_extra={"examples": ["2026-08-01"]})
    laboratory: Optional[str] = Field(None, max_length=200)
    uncertainty: Optional[str] = Field(None, max_length=120)
    verification_status: Optional[str] = Field(None, max_length=64)
    notes: Optional[str] = Field(None, max_length=4000)
    evidence_attachment_id: Optional[int] = None

    @field_validator("measured_on")
    @classmethod
    def _measured_on_is_a_real_date(cls, value: Optional[str]) -> Optional[str]:
        """Refuse a measurement date that is not a genuine ISO calendar date.

        Rejecting at the schema means the request fails with a 422 that names
        the field, before anything is written. The alternative — storing free
        text and hoping — is what let ``13/05/2026`` and ``2026-02-30`` into the
        column, where they are neither comparable nor, until now, loadable.

        Returns the normalised date so storage never holds surrounding
        whitespace, and an empty string becomes a genuine absence.
        """
        if value is None:
            return None
        try:
            parsed = parse_iso_date(value)
        except InvalidMeasurementDate as exc:
            raise ValueError(str(exc)) from exc
        return parsed.isoformat() if parsed is not None else None


class SnapshotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger: str = Field("manual", max_length=64)
    model_version: Optional[str] = Field(None, max_length=64)
