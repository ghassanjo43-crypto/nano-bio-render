"""The scientific data record: a value plus everything needed to trust it.

A bare number is not a scientific datum. ``100 nm`` means different things
depending on whether it came from TEM or DLS, in water or in serum, on this
batch or a comparable one from a paper. This module carries the value together
with the context that makes it interpretable, and refuses to let that context be
silently dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from datetime import date as date_type
from typing import Any

from .data_dictionary import FieldDefinition, field_definition, method_class
from .statuses import (
    EVIDENCE_BEARING_STATUSES,
    NON_CONTRIBUTING_STATUSES,
    SUPPORTING_STATUSES,
    ScientificStatus,
)

__all__ = [
    "MeasurementConditions",
    "ScientificRecord",
    "ValidationIssue",
    "InvalidMeasurementDate",
    "ISO_DATE_FORMAT",
    "parse_iso_date",
    "parse_stored_date",
    "validate_record",
    "record_from_dict",
]

# ---------------------------------------------------------------------------
# Measurement dates
# ---------------------------------------------------------------------------

ISO_DATE_FORMAT = "YYYY-MM-DD"

#: Only the extended calendar form is accepted.
#:
#: ``date.fromisoformat`` alone is too permissive for a stored field: it accepts
#: the basic form ``20260801`` and ISO week dates such as ``2026-W01-1``, which
#: silently resolves to 2025-12-29. A reader seeing "2026-W01-1" would not
#: expect a date in the previous year, so the form is rejected rather than
#: reinterpreted. One unambiguous shape in, one unambiguous shape out.
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class InvalidMeasurementDate(ValueError):
    """A measurement date that is not a genuine ISO calendar date."""


def _date_rejection_message(raw: str) -> str:
    return (
        f"{raw!r} is not a valid ISO date. Record the measurement date as "
        f"{ISO_DATE_FORMAT} — for example 2026-08-01. The date is stored "
        "verbatim and compared against other records, so a form that could be "
        "read as either day-month or month-day is not accepted, and neither is "
        "a calendar date that does not exist.")


def parse_iso_date(value: Any) -> date_type | None:
    """Parse a measurement date strictly. Raises on anything malformed.

    Used on the way *in*. A date that cannot be parsed is refused at the point
    of entry, where the person who typed it can still correct it, rather than
    being stored and becoming somebody else's crash later.

    ``None`` and the empty string mean "not recorded", which is legitimate.
    """
    if value is None:
        return None
    if isinstance(value, date_type):
        return value
    if not isinstance(value, str):
        raise InvalidMeasurementDate(_date_rejection_message(str(value)))
    raw = value.strip()
    if not raw:
        return None
    if not _ISO_DATE_RE.match(raw):
        raise InvalidMeasurementDate(_date_rejection_message(raw))
    try:
        return date_type.fromisoformat(raw)
    except ValueError as exc:
        raise InvalidMeasurementDate(_date_rejection_message(raw)) from exc


def parse_stored_date(value: Any) -> tuple[date_type | None, str | None]:
    """Parse a date already in storage. Never raises.

    Returns ``(date, unparsable_text)``: exactly one is non-None when something
    is stored. Used on the way *out*, and the reason is availability. Rows
    written before this field was validated may hold anything at all, and a
    study must remain loadable, viewable and assessable whatever one of its
    sixty dates says. A single malformed legacy value must not make a study
    impossible to open — the framework's whole purpose is to *show* what is
    wrong with recorded data, which it cannot do from a stack trace.

    The bad text is returned rather than discarded, so the report can show the
    user what is actually stored and they can correct it.
    """
    if value in (None, ""):
        return None, None
    try:
        return parse_iso_date(value), None
    except InvalidMeasurementDate:
        return None, str(value)


@dataclass(frozen=True)
class MeasurementConditions:
    """Conditions under which a measurement was taken.

    Two values of the same field measured under different conditions are
    different measurements. Storing the conditions is what makes that
    detectable.
    """

    medium: str | None = None
    ph: float | None = None
    temperature_c: float | None = None
    ionic_strength_mm: float | None = None
    #: Anything the fixed fields do not capture.
    other: dict[str, str] = dc_field(default_factory=dict)

    def is_empty(self) -> bool:
        return not any([self.medium, self.ph, self.temperature_c,
                        self.ionic_strength_mm, self.other])

    def describe(self) -> str:
        parts = []
        if self.medium:
            parts.append(f"medium {self.medium}")
        if self.ph is not None:
            parts.append(f"pH {self.ph}")
        if self.temperature_c is not None:
            parts.append(f"{self.temperature_c} °C")
        if self.ionic_strength_mm is not None:
            parts.append(f"{self.ionic_strength_mm} mM ionic strength")
        parts.extend(f"{k} {v}" for k, v in sorted(self.other.items()))
        return ", ".join(parts) if parts else "conditions not recorded"

    def conflicts_with(self, other: "MeasurementConditions") -> list[str]:
        """Differences that make two measurements non-comparable."""
        issues: list[str] = []
        if self.medium and other.medium and self.medium != other.medium:
            issues.append(f"different media ({self.medium} vs {other.medium})")
        if (self.ph is not None and other.ph is not None
                and abs(self.ph - other.ph) > 0.5):
            issues.append(f"different pH ({self.ph} vs {other.ph})")
        if (self.temperature_c is not None and other.temperature_c is not None
                and abs(self.temperature_c - other.temperature_c) > 5):
            issues.append(
                f"different temperature ({self.temperature_c} vs "
                f"{other.temperature_c} °C)")
        if (self.ionic_strength_mm is not None
                and other.ionic_strength_mm is not None
                and self.ionic_strength_mm != other.ionic_strength_mm):
            issues.append("different ionic strength")
        return issues


@dataclass
class ScientificRecord:
    """One recorded scientific value with its full provenance."""

    field_id: str
    status: ScientificStatus

    value: Any = None
    unit: str | None = None
    measurement_method: str | None = None
    conditions: MeasurementConditions = dc_field(
        default_factory=MeasurementConditions)
    source_citation: str | None = None
    batch_identifier: str | None = None
    measured_on: date_type | None = None
    #: What was stored for ``measured_on`` when it could not be parsed as an ISO
    #: date. Kept so a malformed legacy value is reported rather than silently
    #: becoming "no date recorded", which would look like an absence of data
    #: instead of a correctable error.
    measured_on_raw: str | None = None
    laboratory: str | None = None
    #: Uncertainty in the same unit as `value`, or a free-text range.
    uncertainty: str | None = None
    #: Whether a second person or method confirmed it.
    verification_status: str | None = None
    notes: str | None = None
    #: Reference into the existing report-document storage, when attached.
    evidence_attachment_id: int | None = None

    @property
    def definition(self) -> FieldDefinition:
        return field_definition(self.field_id)

    @property
    def is_present(self) -> bool:
        """Whether anything is recorded at all."""
        return (self.status not in {ScientificStatus.MISSING}
                and self.value not in (None, ""))

    @property
    def is_evidence(self) -> bool:
        """Whether this constitutes evidence about *this* material."""
        return self.status in EVIDENCE_BEARING_STATUSES and self.is_present

    @property
    def is_supporting(self) -> bool:
        return self.status in SUPPORTING_STATUSES and self.is_present

    @property
    def contributes_to_readiness(self) -> bool:
        """Assumed, illustrative and missing values never raise readiness."""
        return self.is_present and self.status not in NON_CONTRIBUTING_STATUSES

    @property
    def method_family(self) -> str | None:
        return method_class(self.measurement_method)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "measurement_method": self.measurement_method,
            "conditions": {
                "medium": self.conditions.medium,
                "ph": self.conditions.ph,
                "temperature_c": self.conditions.temperature_c,
                "ionic_strength_mm": self.conditions.ionic_strength_mm,
                "other": dict(self.conditions.other),
            },
            "source_citation": self.source_citation,
            "batch_identifier": self.batch_identifier,
            "measured_on": self.measured_on.isoformat()
                           if self.measured_on else None,
            "measured_on_unparsable": self.measured_on_raw,
            "laboratory": self.laboratory,
            "uncertainty": self.uncertainty,
            "verification_status": self.verification_status,
            "notes": self.notes,
            "evidence_attachment_id": self.evidence_attachment_id,
        }


@dataclass(frozen=True)
class ValidationIssue:
    field_id: str
    code: str
    message: str
    severity: str = "error"     # "error" | "warning"


def validate_record(record: ScientificRecord) -> list[ValidationIssue]:
    """Check a record against its dictionary definition.

    Validates type, unit, declared provenance and any defensible range. It does
    **not** invent a plausibility range: for most nanomaterial properties no
    universal range exists, and rejecting a genuine value would be worse than
    accepting an unusual one.
    """
    issues: list[ValidationIssue] = []
    try:
        spec = record.definition
    except KeyError as exc:
        return [ValidationIssue(record.field_id, "unknown_field", str(exc))]

    # --- provenance --------------------------------------------------------
    if record.status not in spec.supported_statuses:
        issues.append(ValidationIssue(
            spec.id, "unsupported_status",
            f"{record.status.value!r} is not a provenance type this field "
            f"supports. Accepted: "
            f"{', '.join(sorted(s.value for s in spec.supported_statuses))}."))

    if not record.is_present:
        # Nothing further to check; absence is legitimate.
        return issues

    # --- type --------------------------------------------------------------
    if spec.data_type == "number":
        try:
            numeric = float(record.value)
        except (TypeError, ValueError):
            issues.append(ValidationIssue(
                spec.id, "not_a_number",
                f"{spec.label} must be a number; got {record.value!r}."))
            return issues
        if spec.valid_range is not None:
            low, high = spec.valid_range
            if not (low <= numeric <= high):
                issues.append(ValidationIssue(
                    spec.id, "out_of_range",
                    f"{spec.label} = {numeric} lies outside the defensible "
                    f"range {low}–{high} {record.unit or ''}. This bound is "
                    "definitional, not a typical-value range."))
    elif spec.data_type == "enum" and spec.choices:
        if str(record.value) not in spec.choices:
            issues.append(ValidationIssue(
                spec.id, "invalid_choice",
                f"{spec.label} must be one of: {', '.join(spec.choices)}."))

    # --- unit --------------------------------------------------------------
    if spec.accepted_units:
        if record.unit is None or record.unit == "":
            if "" not in spec.accepted_units:
                issues.append(ValidationIssue(
                    spec.id, "missing_unit",
                    f"{spec.label} requires a unit. Accepted: "
                    f"{', '.join(u for u in spec.accepted_units if u)}."))
        elif record.unit not in spec.accepted_units:
            issues.append(ValidationIssue(
                spec.id, "invalid_unit",
                f"{record.unit!r} is not an accepted unit for {spec.label}. "
                f"Accepted: {', '.join(u for u in spec.accepted_units if u)}."))

    # --- method, for values that claim to be measured ----------------------
    if (record.status in EVIDENCE_BEARING_STATUSES
            and not record.measurement_method):
        issues.append(ValidationIssue(
            spec.id, "method_not_recorded",
            f"{spec.label} is recorded as {record.status.value} but no "
            "measurement method is stated. A measurement without its method "
            "cannot be compared with any other.", severity="warning"))

    # --- conditions, where they materially change the value ----------------
    if spec.relevant_conditions and record.conditions.is_empty():
        issues.append(ValidationIssue(
            spec.id, "conditions_not_recorded",
            f"{spec.label} depends on {', '.join(spec.relevant_conditions)}, "
            "none of which is recorded. The value cannot be compared with "
            "another measurement.", severity="warning"))

    # --- a stored date that could not be read ------------------------------
    # A warning, not an error: the value the record carries is still usable and
    # refusing the whole record over its date would lose more than it protects.
    if record.measured_on_raw:
        issues.append(ValidationIssue(
            spec.id, "measured_on_unparsable",
            f"The stored measurement date for {spec.label} is "
            f"{record.measured_on_raw!r}, which is not a valid ISO date. It is "
            f"shown as recorded and treated as no date. Correct it to "
            f"{ISO_DATE_FORMAT}.", severity="warning"))

    # --- literature values need a citation ---------------------------------
    if (record.status is ScientificStatus.LITERATURE_DERIVED
            and not record.source_citation):
        issues.append(ValidationIssue(
            spec.id, "citation_missing",
            f"{spec.label} is literature-derived but no source is recorded. "
            "An uncited literature value cannot be checked."))

    return issues


def record_from_dict(data: dict[str, Any]) -> ScientificRecord:
    """Rebuild a record from its stored dictionary form.

    Tolerant about the date, deliberately. This reads snapshots and other
    already-written data, including snapshots taken before the date was
    validated, and re-reading history must not be able to fail.
    """
    cond = data.get("conditions") or {}
    measured, unparsable = parse_stored_date(
        data.get("measured_on") if data.get("measured_on") not in (None, "")
        else data.get("measured_on_unparsable"))
    return ScientificRecord(
        field_id=data["field_id"],
        status=ScientificStatus(data.get("status", "missing")),
        value=data.get("value"),
        unit=data.get("unit"),
        measurement_method=data.get("measurement_method"),
        conditions=MeasurementConditions(
            medium=cond.get("medium"),
            ph=cond.get("ph"),
            temperature_c=cond.get("temperature_c"),
            ionic_strength_mm=cond.get("ionic_strength_mm"),
            other=dict(cond.get("other") or {}),
        ),
        source_citation=data.get("source_citation"),
        batch_identifier=data.get("batch_identifier"),
        measured_on=measured,
        measured_on_raw=unparsable,
        laboratory=data.get("laboratory"),
        uncertainty=data.get("uncertainty"),
        verification_status=data.get("verification_status"),
        notes=data.get("notes"),
        evidence_attachment_id=data.get("evidence_attachment_id"),
    )
