"""Scientific Readiness Framework endpoints.

Transport only. Every scientific decision lives in ``app/science/``; this module
adds no rule, no threshold and no default.

Authorization follows the existing pattern: every route requires an
authenticated user, and every study access goes through
``readiness_service.get_owned_study``, which checks ownership before revealing
whether a study id exists.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.api.deps_auth import get_current_user
from nanobio_studio.app.api.deps_organization import get_access_context
from nanobio_studio.app.organizations.policy import AccessContext
from nanobio_studio.app.db.auth_models import User
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.db.workspace_models import RecordOrigin, StoredRun
from nanobio_studio.app.schemas.readiness import (
    ScienceRecordUpsertRequest,
    SnapshotCreateRequest,
)
from nanobio_studio.app.science.data_dictionary import (
    DATA_DICTIONARY,
    DICTIONARY_VERSION,
)
from nanobio_studio.app.science.statuses import (
    AREA_DESCRIPTION,
    AREA_LABEL,
    EVIDENCE_LABEL,
    EVIDENCE_LEVEL_REQUIREMENT,
    EXPERIMENTAL_VALIDATION_LEVELS,
    NOT_ACCREDITATION_NOTICE,
    READINESS_LABEL,
    RULES_ENGINE_VERSION,
    STATUS_DESCRIPTION,
    STATUS_LABEL,
    VALIDATION_KIND_LABEL,
    VALIDATION_KIND_LEVEL,
    VALIDATION_REGISTRY_AVAILABLE,
    VALIDATION_REGISTRY_NOTICE,
    EvidenceLevel,
    ReadinessArea,
    ReadinessStatus,
    ScientificStatus,
    ValidationKind,
    evidence_level_is_attainable,
    max_attainable_evidence_level,
)
from nanobio_studio.app.services import readiness_service as svc

router = APIRouter(prefix="/api/v1/science", tags=["scientific-readiness"])


def _error(code: str, message: str, http_status: int,
           detail: str | None = None) -> JSONResponse:
    """Structured failure. Never carries a readiness result."""
    return JSONResponse(
        status_code=http_status,
        content={"error": code, "message": message, "detail": detail,
                 "readiness_available": False},
    )


# ---------------------------------------------------------------------------
# Vocabulary and dictionary
# ---------------------------------------------------------------------------


@router.get("/vocabulary", summary="Statuses, areas and evidence levels")
async def vocabulary(_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "scientific_statuses": [
            {"id": s.value, "label": STATUS_LABEL[s],
             "description": STATUS_DESCRIPTION[s]}
            for s in ScientificStatus
        ],
        "readiness_statuses": [
            {"id": s.value, "label": READINESS_LABEL[s]}
            for s in ReadinessStatus
        ],
        # Each level carries what it *requires* and whether it can currently be
        # reached at all. A scale that shows E6 without saying it is
        # unreachable invites the reading that a study is merely some distance
        # from it, rather than that no study can get there.
        "evidence_levels": [
            {"id": e.value, "label": EVIDENCE_LABEL[e],
             "requirement": EVIDENCE_LEVEL_REQUIREMENT[e],
             "asserts_experimental_validation":
                 e in EXPERIMENTAL_VALIDATION_LEVELS,
             "attainable": evidence_level_is_attainable(e)}
            for e in EvidenceLevel
        ],
        "validation_kinds": [
            {"id": k.value, "label": VALIDATION_KIND_LABEL[k],
             "supports_level": VALIDATION_KIND_LEVEL[k].value}
            for k in ValidationKind
        ],
        "validation_registry_available": VALIDATION_REGISTRY_AVAILABLE,
        "max_attainable_evidence_level": max_attainable_evidence_level().value,
        "evidence_ceiling_notice": VALIDATION_REGISTRY_NOTICE,
        "areas": [
            {"id": a.value, "label": AREA_LABEL[a],
             "description": AREA_DESCRIPTION[a]}
            for a in ReadinessArea
        ],
        "rules_engine_version": RULES_ENGINE_VERSION,
        "dictionary_version": DICTIONARY_VERSION,
        "notice": NOT_ACCREDITATION_NOTICE,
    }


@router.get("/dictionary", summary="The scientific data dictionary")
async def dictionary(
    group: str | None = Query(None),
    _user: User = Depends(get_current_user),
ctx: AccessContext = Depends(get_access_context),
) -> dict[str, Any]:
    entries = [d for d in DATA_DICTIONARY.values()
               if group is None or d.group == group]
    return {
        "version": DICTIONARY_VERSION,
        "fields": [
            {
                "id": d.id, "label": d.label, "definition": d.definition,
                "group": d.group, "data_type": d.data_type,
                "accepted_units": list(d.accepted_units),
                "valid_range": (list(d.valid_range) if d.valid_range
                                and all(abs(v) != float("inf")
                                        for v in d.valid_range) else None),
                "choices": list(d.choices),
                "relevant_conditions": list(d.relevant_conditions),
                "supported_statuses": sorted(s.value
                                             for s in d.supported_statuses),
                "area_requirements": {a.value: r.value
                                      for a, r in d.area_requirements.items()},
                "condition": d.condition,
                "compatibility_rules": list(d.compatibility_rules),
                "researcher_note": d.researcher_note,
            }
            for d in entries
        ],
    }


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@router.get("/studies/{study_id}/records",
            summary="Scientific records for a study")
async def list_records(
    study_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        run = await svc.get_owned_study(session, access=ctx, owner_id=user.id,
                                        study_id=study_id)
    except svc.ReadinessError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)

    records = await svc.load_records(session, study_id=study_id)
    is_legacy = not records
    if is_legacy:
        records = svc.legacy_records_for_study(run)

    return {
        "study_id": study_id,
        "records": [r.to_dict() for r in records],
        "is_legacy_import": is_legacy,
        "legacy_notice": _legacy_notice(run) if is_legacy else None,
    }


def _legacy_notice(run: StoredRun) -> str:
    """Why a study with no records still shows values.

    The two cases are not the same and must not share wording. A legacy study's
    numbers were entered by a researcher and simply predate provenance
    recording. A demonstration study's numbers were never entered by anyone.
    """
    if run.origin is RecordOrigin.DEMO:
        return (
            "This is a demonstration study. Its values were chosen to exercise "
            "the interface, not measured or supplied by a researcher, and they "
            "describe no real material. They are shown as illustrative and "
            "contribute nothing to readiness."
        )
    return (
        "This study predates the Scientific Readiness Framework. Its design "
        "values are shown as user-supplied because no measurement method, "
        "source or conditions were recorded when it was saved."
    )


@router.put("/studies/{study_id}/records/{field_id}",
            summary="Create or replace one scientific record")
async def put_record(
    study_id: int, field_id: str, request: ScienceRecordUpsertRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        await svc.get_owned_study(session, owner_id=user.id,
                                  study_id=study_id, access=ctx)
    except svc.ReadinessError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)

    try:
        row, warnings = await svc.upsert_record(
            session, owner_id=user.id, study_id=study_id, field_id=field_id,
            payload=request.model_dump(exclude_none=False))
    except svc.ReadinessError as exc:
        http = (status.HTTP_404_NOT_FOUND if exc.code == "unknown_field"
                else status.HTTP_400_BAD_REQUEST)
        return _error(exc.code, exc.message, http, exc.detail)

    return {"study_id": study_id, "field_id": row.field_id,
            "status": row.status.value, "warnings": warnings}


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


@router.get("/studies/{study_id}/readiness",
            summary="Assess the six readiness areas")
async def get_readiness(
    study_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        report, records = await svc.assess_study(session, access=ctx,
                                                 owner_id=user.id,
                                                 study_id=study_id)
    except svc.ReadinessError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)

    payload = report.to_dict()
    payload["study_id"] = study_id
    payload["record_count"] = len(records)
    return payload


@router.post("/studies/{study_id}/readiness/snapshots",
             summary="Store an immutable readiness snapshot")
async def post_snapshot(
    study_id: int, request: SnapshotCreateRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        report, records = await svc.assess_study(session, access=ctx,
                                                 owner_id=user.id,
                                                 study_id=study_id)
        snapshot = await svc.create_snapshot(
            session, owner_id=user.id, study_id=study_id, report=report,
            records=records, trigger=request.trigger,
            model_version=request.model_version)
    except svc.ReadinessError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)

    return {
        "id": snapshot.id, "study_id": study_id,
        "rules_engine_version": snapshot.rules_engine_version,
        "dictionary_version": snapshot.dictionary_version,
        "model_version": snapshot.model_version,
        "trigger": snapshot.trigger,
        "created_at": snapshot.created_at.isoformat(),
    }


@router.get("/studies/{study_id}/readiness/snapshots",
            summary="Readiness history for a study")
async def get_snapshots(
    study_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        await svc.get_owned_study(session, owner_id=user.id,
                                  study_id=study_id, access=ctx)
    except svc.ReadinessError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)

    rows = await svc.list_snapshots(session, study_id=study_id)
    return {
        "study_id": study_id,
        "snapshots": [
            {
                "id": r.id,
                "rules_engine_version": r.rules_engine_version,
                "dictionary_version": r.dictionary_version,
                "model_version": r.model_version,
                "trigger": r.trigger,
                "created_at": r.created_at.isoformat(),
                # The stored report, verbatim. A historical snapshot is never
                # recomputed under current rules — that would defeat its point.
                "report": json.loads(r.report_json),
            }
            for r in rows
        ],
        "total": len(rows),
    }
