"""Storage and assessment for the Scientific Readiness Framework.

Follows the existing workspace-service conventions: ownership is checked before
existence is revealed, so these endpoints cannot be used to probe for study ids
belonging to another account.

This module performs no scientific judgement of its own. It loads records, hands
them to the rules engine, and stores what comes back.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.science_models import (
    ReadinessSnapshot,
    ScienceDataRecord,
)
from nanobio_studio.app.db.workspace_models import RecordOrigin, StoredRun
from nanobio_studio.app.organizations.policy import (
    AccessContext, RecordNotVisible,
)
from nanobio_studio.app.organizations.scoping import scoped_runs
from nanobio_studio.app.science.data_dictionary import (
    DATA_DICTIONARY,
    DICTIONARY_VERSION,
)
from nanobio_studio.app.science.records import (
    InvalidMeasurementDate,
    MeasurementConditions,
    ScientificRecord,
    parse_iso_date,
    parse_stored_date,
    validate_record,
)
from nanobio_studio.app.science.rules import ReadinessReport, evaluate_study
from nanobio_studio.app.science.statuses import (
    RULES_ENGINE_VERSION,
    ScientificStatus,
)

__all__ = [
    "ReadinessError",
    "get_owned_study",
    "load_records",
    "upsert_record",
    "assess_study",
    "create_snapshot",
    "list_snapshots",
    "legacy_records_for_study",
]


class ReadinessError(RuntimeError):
    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


async def get_owned_study(session: AsyncSession, *, owner_id: int,
                          study_id: int,
                          access: "AccessContext | None" = None) -> StoredRun:
    """Resolve a study for readiness, or refuse without revealing existence.

    Every readiness route passes through here — summaries, purpose-level
    evidence, supporting experiment references, missing-requirement detail,
    snapshots and the records themselves. That is why the conversion is one
    function: a single scoped predicate here protects the whole readiness
    surface, and there is no second path into a study's evidence that could
    be left behind.

    Ownership alone is no longer the test. It hid a study from a reviewer
    explicitly assigned to it, and kept showing it to a former owner who had
    since left the organization. ``scoped_runs`` folds ownership, assignment
    and organization-wide scope into one predicate applied in SQL.
    """
    if access is not None:
        query = await scoped_runs(session, access)
        run = (await session.execute(
            query.where(StoredRun.id == study_id).limit(1))).scalars().first()
        if run is None:
            # RecordNotVisible rather than ReadinessError: a study outside the
            # caller's organizations must produce the same 404 as one that
            # does not exist, and the readiness error shape names the study.
            raise RecordNotVisible("study")
        return run

    run = await session.get(StoredRun, study_id)
    if run is None or run.owner_id != owner_id:
        raise ReadinessError("study_not_found",
                             "The requested study does not exist.")
    return run


def _to_domain(row: ScienceDataRecord) -> ScientificRecord:
    """Rebuild a domain record from a stored row.

    Every field here is read defensively, because the row may predate the
    validation that now guards it. Loading a study must not be able to fail on
    the content of one column: a study that cannot be opened cannot be
    corrected either.
    """
    try:
        conditions = json.loads(row.conditions_json) if row.conditions_json else {}
    except (json.JSONDecodeError, TypeError):
        conditions = {}
    if not isinstance(conditions, dict):
        conditions = {}
    measured_on, measured_on_raw = parse_stored_date(row.measured_on)
    return ScientificRecord(
        field_id=row.field_id,
        status=row.status,
        value=row.value_text,
        unit=row.unit,
        measurement_method=row.measurement_method,
        conditions=MeasurementConditions(
            medium=conditions.get("medium"),
            ph=conditions.get("ph"),
            temperature_c=conditions.get("temperature_c"),
            ionic_strength_mm=conditions.get("ionic_strength_mm"),
            other=dict(conditions.get("other") or {}),
        ),
        source_citation=row.source_citation,
        batch_identifier=row.batch_identifier,
        measured_on=measured_on,
        measured_on_raw=measured_on_raw,
        laboratory=row.laboratory,
        uncertainty=row.uncertainty,
        verification_status=row.verification_status,
        notes=row.notes,
        evidence_attachment_id=row.evidence_attachment_id,
    )


async def load_records(session: AsyncSession, *,
                       study_id: int) -> list[ScientificRecord]:
    rows = (await session.execute(
        select(ScienceDataRecord).where(
            ScienceDataRecord.study_id == study_id))).scalars().all()
    return [_to_domain(r) for r in rows]


#: Legacy design keys mapped to dictionary field ids, with their units.
_LEGACY_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    "size_nm": ("physical_diameter", "nm"),
    "hydrodynamic_size_nm": ("hydrodynamic_diameter", "nm"),
    "charge_mv": ("zeta_potential", "mV"),
    "encapsulation_percent": ("encapsulation_efficiency", "%"),
    "pdi": ("pdi", ""),
    "coating_thickness_nm": ("coating_thickness", "nm"),
    "surface_area_nm2": ("surface_area", "nm2"),
    "ligand": ("ligand_identity", None),
    "ligand_density_percent": ("ligand_density_value", "%"),
}

_LEGACY_NOTE = (
    "Imported from a study saved before the Scientific Readiness Framework "
    "existed. No measurement method, source or conditions were recorded at "
    "the time, so the value carries no evidence of how it was obtained."
)

_DEMO_NOTE = (
    "A demonstration value. It was chosen to exercise the interface, not "
    "measured, derived or supplied by a researcher, and it describes no real "
    "material. It contributes nothing to readiness."
)


def legacy_records_for_study(run: StoredRun) -> list[ScientificRecord]:
    """Derive records from a study saved before the framework existed.

    Legacy studies carry design inputs as bare numbers with no provenance. They
    surface as ``USER_SUPPLIED``: the value is real and a person entered it, but
    no method, source or conditions were ever recorded, so it carries no
    evidence and cannot satisfy a blocking requirement.

    Demonstration runs surface as ``ILLUSTRATIVE`` instead. Nobody supplied
    those numbers and they describe no real material, so they must not be
    allowed to raise a readiness percentage.

    This is what keeps old studies loading safely while staying honest about
    what is and is not known about them.
    """
    # A demonstration run's values were never supplied by anyone — they are
    # fixture values chosen to exercise the interface. Calling them
    # USER_SUPPLIED would credit a person who does not exist and imply the
    # number describes some real material. ILLUSTRATIVE is non-contributing, so
    # a seeded study reads as 0% and E0: exactly what it is.
    is_demo = run.origin is RecordOrigin.DEMO
    status = (ScientificStatus.ILLUSTRATIVE if is_demo
              else ScientificStatus.USER_SUPPLIED)
    note = _DEMO_NOTE if is_demo else _LEGACY_NOTE

    if not run.design_inputs_json:
        return []
    try:
        inputs = json.loads(run.design_inputs_json)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(inputs, dict):
        return []

    records: list[ScientificRecord] = []
    for key, (field_id, unit) in _LEGACY_FIELD_MAP.items():
        raw = inputs.get(key)
        if raw in (None, ""):
            continue
        records.append(ScientificRecord(
            field_id=field_id,
            status=status,
            value=str(raw),
            unit=unit,
            notes=note,
        ))

    # A legacy percentage ligand density has no recorded denominator. Marking
    # it ambiguous is what stops it being treated as a usable density.
    if any(r.field_id == "ligand_density_value" for r in records):
        records.append(ScientificRecord(
            field_id="ligand_density_unit",
            status=status,
            value="ambiguous_percent",
            notes=("Legacy studies recorded ligand density as a bare "
                   "percentage with no denominator."),
        ))
    return records


async def upsert_record(
    session: AsyncSession, *, owner_id: int, study_id: int,
    field_id: str, payload: dict[str, Any],
) -> tuple[ScienceDataRecord, list[dict[str, str]]]:
    """Create or replace one scientific record, after validating it."""
    if field_id not in DATA_DICTIONARY:
        raise ReadinessError(
            "unknown_field",
            f"{field_id!r} is not in the scientific data dictionary.",
            "Fields must be defined in the dictionary before they can be "
            "recorded, so their units and provenance rules are known.")

    try:
        status = ScientificStatus(payload.get("status", "missing"))
    except ValueError as exc:
        raise ReadinessError(
            "invalid_status",
            f"{payload.get('status')!r} is not a recognised scientific status.",
            "Accepted: " + ", ".join(s.value for s in ScientificStatus),
        ) from exc

    # Validated at the schema too, so an HTTP client gets a 422 naming the
    # field. Repeated here because this function is also called directly — by
    # scripts, by seeding, by tests — and a bad date must never reach the
    # column by a route that happens to bypass the schema.
    try:
        measured_on = parse_iso_date(payload.get("measured_on"))
    except InvalidMeasurementDate as exc:
        raise ReadinessError(
            "invalid_measured_on", str(exc),
            "The value was not stored. A measurement date that cannot be read "
            "is worse than no date: it cannot be compared, and it looks like "
            "provenance the record does not have.") from exc

    conditions = payload.get("conditions") or {}
    domain = ScientificRecord(
        field_id=field_id, status=status,
        value=payload.get("value"), unit=payload.get("unit"),
        measurement_method=payload.get("measurement_method"),
        conditions=MeasurementConditions(
            medium=conditions.get("medium"),
            ph=conditions.get("ph"),
            temperature_c=conditions.get("temperature_c"),
            ionic_strength_mm=conditions.get("ionic_strength_mm"),
            other=dict(conditions.get("other") or {}),
        ),
        source_citation=payload.get("source_citation"),
        batch_identifier=payload.get("batch_identifier"),
        measured_on=measured_on,
        laboratory=payload.get("laboratory"),
        uncertainty=payload.get("uncertainty"),
        verification_status=payload.get("verification_status"),
        notes=payload.get("notes"),
        evidence_attachment_id=payload.get("evidence_attachment_id"),
    )

    issues = validate_record(domain)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        raise ReadinessError(
            "validation_failed",
            "; ".join(i.message for i in errors),
            "The value was not stored. Correcting it is preferable to storing "
            "something the framework cannot interpret.")

    existing = (await session.execute(
        select(ScienceDataRecord).where(
            ScienceDataRecord.study_id == study_id,
            ScienceDataRecord.field_id == field_id))).scalar_one_or_none()

    row = existing or ScienceDataRecord(study_id=study_id, owner_id=owner_id,
                                        field_id=field_id)
    # The record inherits the study's organization rather than the
    # caller's, so a record can never end up filed under a different
    # organization from the study it describes.
    if row.organization_id is None:
        parent = await session.get(StoredRun, study_id)
        row.organization_id = parent.organization_id if parent else None
    row.status = status
    row.value_text = None if domain.value is None else str(domain.value)
    row.unit = domain.unit
    row.measurement_method = domain.measurement_method
    row.conditions_json = json.dumps({
        "medium": domain.conditions.medium,
        "ph": domain.conditions.ph,
        "temperature_c": domain.conditions.temperature_c,
        "ionic_strength_mm": domain.conditions.ionic_strength_mm,
        "other": domain.conditions.other,
    })
    row.source_citation = domain.source_citation
    row.batch_identifier = domain.batch_identifier
    # Stored normalised, so the column holds one unambiguous shape.
    row.measured_on = measured_on.isoformat() if measured_on else None
    row.laboratory = domain.laboratory
    row.uncertainty = domain.uncertainty
    row.verification_status = domain.verification_status
    row.notes = domain.notes
    row.evidence_attachment_id = domain.evidence_attachment_id

    if existing is None:
        session.add(row)
    await session.flush()

    warnings = [{"code": i.code, "message": i.message}
                for i in issues if i.severity == "warning"]
    return row, warnings


async def assess_study(session: AsyncSession, *, owner_id: int,
                       access: "AccessContext | None" = None,
                       study_id: int) -> tuple[ReadinessReport,
                                               list[ScientificRecord]]:
    """Assess a study, falling back to legacy import when it has no records.

    Approved registry evidence is fetched and handed to the engine, which is
    the only route by which E3 can be reached. When a study has no approved
    experiment the mapping is empty and every E0-E2 outcome is exactly what it
    was in Phase 1 -- the engine takes the same path it always did.
    """
    run = await get_owned_study(session, owner_id=owner_id,
                                study_id=study_id, access=access)
    records = await load_records(session, study_id=study_id)
    if not records:
        records = legacy_records_for_study(run)

    # Imported here rather than at module scope: the readiness service is
    # imported by the science tests, and a top-level import would drag the
    # whole registry into a suite that has nothing to do with it.
    from nanobio_studio.app.services.validation_service import (
        approved_evidence_for_study,
    )
    approved = await approved_evidence_for_study(session, study_id=study_id)

    return evaluate_study(records, approved), records


async def create_snapshot(
    session: AsyncSession, *, owner_id: int, study_id: int,
    report: ReadinessReport, records: Sequence[ScientificRecord],
    trigger: str = "manual", model_version: str | None = None,
) -> ReadinessSnapshot:
    """Store an immutable assessment.

    Keeps the inputs alongside the result, so a historical snapshot can be
    re-checked against the rules that produced it even after both change.
    """
    parent = await session.get(StoredRun, study_id)
    snapshot = ReadinessSnapshot(
        study_id=study_id, owner_id=owner_id,
        organization_id=parent.organization_id if parent else None,
        rules_engine_version=RULES_ENGINE_VERSION,
        dictionary_version=DICTIONARY_VERSION,
        model_version=model_version,
        report_json=json.dumps(report.to_dict()),
        input_records_json=json.dumps([r.to_dict() for r in records]),
        trigger=trigger,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def list_snapshots(session: AsyncSession, *, study_id: int,
                         limit: int = 50) -> list[ReadinessSnapshot]:
    rows = (await session.execute(
        select(ReadinessSnapshot)
        .where(ReadinessSnapshot.study_id == study_id)
        .order_by(ReadinessSnapshot.created_at.desc())
        .limit(limit))).scalars().all()
    return list(rows)
