"""Experimental Validation Registry endpoints.

Transport only. Every scientific decision lives in ``app/validation/``; this
module adds no gate, no threshold and no permission rule of its own.

Authorization is the service's, not the router's
------------------------------------------------
Each route resolves the caller into a ``RegistryActor`` and hands it to the
service, which calls ``permissions.require`` before mutating anything. The
router never decides who may do what — a control implemented at the edge is one
that a second caller, a script or a future route can walk around.

``PermissionDenied`` becomes 403 and ``ValidationError`` becomes 400 or 404,
each carrying the reason. A refusal that says only "forbidden" leaves the user
unable to tell a missing capability from a missing record.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.api.deps_auth import get_current_user
from nanobio_studio.app.api.deps_organization import get_access_context
from nanobio_studio.app.organizations.policy import (
    AccessContext, Action, RecordFacts, RecordNotVisible, require,
    require as require_policy,
)
from nanobio_studio.app.organizations.scoping import (
    require_scoped, scoped, scoped_study_ids,
)
from nanobio_studio.app.api.routes.candidate_scope import (
    resolve_candidate, resolve_candidate_version,
)
from nanobio_studio.app.api.serializers.validation_serializers import (
    serialize_attachment, serialize_candidate_version, serialize_measurement,
    serialize_version,
)
from nanobio_studio.app.db.auth_models import User
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.db.validation_models import (
    Candidate, CandidateVersion, ExperimentAttachment, ExperimentVersion,
    Measurement, ValidationExperiment,
)
from nanobio_studio.app.schemas.validation import (
    CandidateCreateRequest, CandidateRevisionRequest,
    CandidateVersionCreateRequest, SupersessionRequest,
    VersionWithdrawRequest,
    ContradictionResolutionRequest, DraftUpdateRequest,
    ExperimentCreateRequest, MeasurementBatchRequest, ReviewDecisionRequest,
    RevisionRequest,
)
from nanobio_studio.app.science.statuses import (
    EVIDENCE_LABEL, EvidenceLevel, ReadinessArea,
)
from nanobio_studio.app.services import validation_service as svc
from nanobio_studio.app.validation.permissions import (
    PermissionDenied, RegistryActor, capabilities_for, ExperimentContext,
)
from nanobio_studio.app.validation.storage import (
    ALLOWED_MIME_TYPES, MAX_ATTACHMENT_BYTES, AttachmentRejected,
)
from nanobio_studio.app.validation.vocabulary import (
    FUTURE_LEVELS, GRANTABLE_LEVELS, PURPOSE_LABEL, REGISTRY_VERSION,
    STATUS_LABEL, SUBTYPE_LABEL, SUBTYPE_PERMITTED_PURPOSES,
    AttachmentCategory, ExperimentStatus, ExperimentSubtype, ReviewDecision,
)

router = APIRouter(prefix="/api/v1/validation", tags=["validation-registry"])


def _error(code: str, message: str, http_status: int,
           detail: str | None = None) -> JSONResponse:
    """Structured failure. Never carries a partial registry result."""
    return JSONResponse(
        status_code=http_status,
        content={"error": code, "message": message, "detail": detail,
                 "registry_available": False},
    )


def _actor(user: User, ctx: AccessContext) -> RegistryActor:
    """The registry actor, carrying this request's access facts.

    The context is resolved once per request by the dependency and passed
    down; nothing below re-derives it. A membership revoked midway through
    a request must not be in force for one check and absent from the next.
    """
    return RegistryActor(user_id=user.id, role=user.role, access=ctx)


async def _scoped_experiment(session: AsyncSession, ctx: AccessContext,
                             experiment_id: int) -> ValidationExperiment:
    """Resolve an experiment the caller may reach, or raise the 404.

    The organization predicate is part of the same WHERE clause that finds the
    row, so an experiment belonging to another organization is never loaded.
    A caller walking the identifier space learns nothing: a real record they
    cannot see and an identifier that was never issued give the same answer.
    """
    return await require_scoped(
        session,
        scoped(select(ValidationExperiment), ValidationExperiment, ctx)
        .where(ValidationExperiment.id == experiment_id),
        "experiment")


async def _scoped_version(session: AsyncSession, ctx: AccessContext,
                          version_id: int) -> ExperimentVersion:
    """Resolve an experiment version the caller may reach, or raise the 404.

    Called at the top of every version route *before* delegating to the
    service. The service then loads the same row by identifier, which is safe
    because reachability has already been established here — this is the one
    choke point, rather than a check repeated in twenty service functions and
    forgotten in the twenty-first.
    """
    return await require_scoped(
        session,
        scoped(select(ExperimentVersion), ExperimentVersion, ctx)
        .where(ExperimentVersion.id == version_id),
        "experiment version")


async def _scoped_candidate(session: AsyncSession, ctx: AccessContext,
                            candidate_id: int) -> Candidate:
    """Resolve a candidate the caller may reach, or raise the 404.

    Delegates to ``routes/candidate_scope.py``, which is the single definition
    shared with the version-bound artefact router. The name is kept here
    because it is the one this module's routes and its tests use, and because
    the reasoning recorded around it belongs to this file's history.
    """
    return await resolve_candidate(session, ctx, candidate_id)


async def _scoped_candidate_version(session: AsyncSession, ctx: AccessContext,
                                    version_id: int) -> CandidateVersion:
    """Resolve a candidate version the caller may reach, or raise the 404."""
    return await resolve_candidate_version(session, ctx, version_id)


async def _scoped_study(session: AsyncSession, ctx: AccessContext,
                        study_id: int):
    """Resolve a study the caller may reach, or raise the 404."""
    from nanobio_studio.app.db.workspace_models import StoredRun

    return await require_scoped(
        session,
        scoped(select(StoredRun), StoredRun, ctx).where(
            StoredRun.id == study_id),
        "study")


async def _scoped_attachment(session: AsyncSession, ctx: AccessContext,
                             attachment_id: int) -> ExperimentAttachment:
    """Resolve an attachment the caller may reach, or raise the 404.

    Attachments are addressed by their own identifier rather than through the
    experiment, so they need the predicate applied directly. Without it, an
    attachment is the softest target in the registry: one integer away from a
    raw instrument file belonging to another organization.

    The organization predicate is not sufficient on its own
    -------------------------------------------------------
    It was, until the attachment-storage walkthrough drove a real upload
    through a real browser: an external contract laboratory with
    ``ASSIGNED_STUDIES`` scope and no assignment on the study downloaded the
    file, because organization membership was the whole test. Scope is now
    applied here too, through the same ``visible_study_ids`` the rest of the
    application uses — a member restricted to assigned studies reaches
    attachments on those studies and no others.
    """
    return await require_scoped(
        session,
        scoped(
            (select(ExperimentAttachment)
             .join(ExperimentVersion,
                   ExperimentVersion.id == ExperimentAttachment.version_id)
             .join(ValidationExperiment,
                   ValidationExperiment.id == ExperimentVersion.experiment_id)),
            ExperimentAttachment, ctx,
            study_column=ValidationExperiment.study_id,
            study_ids=await scoped_study_ids(session, ctx),
        ).where(ExperimentAttachment.id == attachment_id),
        "attachment")


async def _require_download_permission(
    session: AsyncSession, ctx: AccessContext,
    attachment: ExperimentAttachment,
) -> None:
    """The collaboration's attachment restriction, applied to the bytes.

    Reading an experiment's *results* on screen and taking a copy of the raw
    instrument file away are different acts, and a CRO agreement routinely
    permits the first while forbidding the second. The registry's own
    capability model has no concept of that — it predates organizations — so
    the organization policy is consulted here, where the bytes are about to be
    served.

    Found by the attachment-storage walkthrough: an external collaborator whose
    membership carried ``may_download_attachments = false`` was served the file
    with HTTP 200, because nothing on this path had ever asked.

    403 rather than 404: the caller can already see the attachment exists —
    they can list it — so explaining the refusal discloses nothing they did not
    have, and a silent 404 here would look like data loss.
    """
    version = await session.get(ExperimentVersion, attachment.version_id)
    experiment = (await session.get(ValidationExperiment, version.experiment_id)
                  if version is not None else None)
    require(ctx, Action.DOWNLOAD_ATTACHMENT, RecordFacts(
        organization_id=attachment.organization_id,
        study_id=experiment.study_id if experiment is not None else None,
        owner_id=attachment.uploaded_by))




def _handle(exc: Exception) -> JSONResponse:
    if isinstance(exc, PermissionDenied):
        return _error("permission_denied", exc.reason,
                      status.HTTP_403_FORBIDDEN,
                      f"capability: {exc.capability.value}")
    if isinstance(exc, AttachmentRejected):
        return _error(exc.code, exc.message, status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, svc.ValidationError):
        http = (status.HTTP_404_NOT_FOUND
                if exc.code.endswith("_not_found")
                else status.HTTP_400_BAD_REQUEST)
        return _error(exc.code, exc.message, http, exc.detail)
    raise exc


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


@router.get("/vocabulary", summary="Subtypes, purposes, statuses and levels")
async def vocabulary(_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "registry_version": REGISTRY_VERSION,
        "subtypes": [
            {"id": s.value, "label": SUBTYPE_LABEL[s],
             "permitted_purposes": sorted(
                 p.value for p in SUBTYPE_PERMITTED_PURPOSES.get(s, ()))}
            for s in ExperimentSubtype
        ],
        "purposes": [{"id": p.value, "label": PURPOSE_LABEL[p]}
                     for p in ReadinessArea],
        "statuses": [{"id": s.value, "label": STATUS_LABEL[s]}
                     for s in ExperimentStatus],
        "attachment_categories": [c.value for c in AttachmentCategory],
        # Grantable and future are separate lists on purpose: the interface
        # shows the shape of the scale without offering a level it cannot
        # substantiate.
        "grantable_levels": [
            {"id": lvl.value, "label": EVIDENCE_LABEL[lvl]}
            for lvl in sorted(GRANTABLE_LEVELS, key=lambda x: x.value)
        ],
        "future_levels": [
            {"id": lvl.value, "label": EVIDENCE_LABEL[lvl], "note": note,
             "selectable": False}
            for lvl, note in FUTURE_LEVELS.items()
        ],
        "attachment_limits": {
            "max_bytes": MAX_ATTACHMENT_BYTES,
            "accepted_mime_types": sorted(ALLOWED_MIME_TYPES),
        },
    }


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


@router.post("/candidates", summary="Create a candidate under a study")
async def create_candidate(request: CandidateCreateRequest,
                           user: User = Depends(get_current_user),
                           ctx: AccessContext = Depends(get_access_context),
                           session: AsyncSession = Depends(get_auth_session)):
    # Reachability first, and it must be here rather than in the service.
    #
    # The service used to authorize with `run.owner_id != actor.user_id`,
    # which was wrong in both directions but was — accidentally — the only
    # thing preventing cross-organization candidate creation, because this
    # route never resolved the study through the scope. Removing the ownership
    # test without adding this made writing into another organization's study
    # succeed, and the organization-routes suite caught it.
    study = await _scoped_study(session, ctx, request.study_id)
    try:
        candidate = await svc.create_candidate(
            session, actor=_actor(user, ctx), study_id=study.id,
            code=request.code, name=request.name,
            description=request.description)
        await session.commit()
    except Exception as exc:  # noqa: BLE001 - narrowed by _handle
        await session.rollback()
        return _handle(exc)
    return {"id": candidate.id, "code": candidate.code, "name": candidate.name,
            "study_id": candidate.study_id}


@router.get("/studies/{study_id}/candidates", summary="Candidates for a study")
async def list_candidates(study_id: int,
                          user: User = Depends(get_current_user),
                          ctx: AccessContext = Depends(get_access_context),
                          session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_study(session, ctx, study_id)
    rows = (await session.execute(
        scoped(select(Candidate), Candidate, ctx)
        .where(Candidate.study_id == study_id)
        .order_by(Candidate.created_at.desc()))).scalars().all()
    out = []
    for candidate in rows:
        # Scoped, not merely filtered by candidate. The previous version
        # gated on the candidate being reachable and then listed its versions
        # unconditionally — which, combined with the unauthorized write above,
        # meant a version written from another organization appeared here as a
        # legitimate part of this candidate's history.
        versions = (await session.execute(
            scoped(select(CandidateVersion), CandidateVersion, ctx)
            .where(CandidateVersion.candidate_id == candidate.id)
            .order_by(CandidateVersion.version_number.desc()))).scalars().all()
        out.append({
            "id": candidate.id, "code": candidate.code, "name": candidate.name,
            "description": candidate.description,
            "versions": [
                {"id": v.id, "version_number": v.version_number,
                 "checksum": v.snapshot_checksum, "note": v.note,
                 "created_at": v.created_at.isoformat()}
                for v in versions
            ],
        })
    return {"study_id": study_id, "candidates": out, "total": len(out)}


@router.post("/candidates/{candidate_id}/versions",
             summary="Freeze the current formulation as a new version")
async def create_candidate_version(
    candidate_id: int, request: CandidateVersionCreateRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    # Reachability BEFORE anything touches the record, so a candidate in
    # another organization is indistinguishable from one that never existed.
    candidate = await _scoped_candidate(session, ctx, candidate_id)
    try:
        version = await svc.create_candidate_version(
            session, actor=_actor(user, ctx), candidate_id=candidate.id,
            design_inputs=request.design_inputs, note=request.note)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    return {"id": version.id, "version_number": version.version_number,
            "checksum": version.snapshot_checksum}


# ---------------------------------------------------------------------------
# Registry listing and dashboard
# ---------------------------------------------------------------------------


def _version_summary(version: ExperimentVersion,
                     experiment: ValidationExperiment) -> dict[str, Any]:
    return {
        "experiment_id": experiment.id,
        "code": experiment.code,
        "title": experiment.title,
        "subtype": experiment.subtype.value,
        "subtype_label": SUBTYPE_LABEL[experiment.subtype],
        "purpose": experiment.purpose.value,
        "purpose_label": PURPOSE_LABEL[experiment.purpose],
        "study_id": experiment.study_id,
        "project_id": experiment.project_id,
        "candidate_id": experiment.candidate_id,
        "version_id": version.id,
        "version_number": version.version_number,
        "candidate_version_id": version.candidate_version_id,
        "status": version.status.value,
        "status_label": STATUS_LABEL[version.status],
        "approved_level": (version.approved_level.value
                           if version.approved_level else None),
        "laboratory_name": version.laboratory_name,
        "investigator_name": version.investigator_name,
        "reviewer_id": version.reviewer_id,
        "created_at": version.created_at.isoformat(),
        "decision_at": (version.decision_at.isoformat()
                        if version.decision_at else None),
        "e3_eligible": version.approved_level == EvidenceLevel.E3,
    }


@router.get("/experiments", summary="Registry listing with filters")
async def list_experiments(
    study_id: int | None = Query(None),
    project_id: int | None = Query(None),
    candidate_id: int | None = Query(None),
    subtype: str | None = Query(None),
    purpose: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    laboratory: str | None = Query(None),
    investigator: str | None = Query(None),
    reviewer_id: int | None = Query(None),
    e3_eligible: bool | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Every filter in the brief, applied in the database.

    Filtering in SQL rather than in the page keeps a large registry usable and
    means the counts the dashboard shows are the counts the list contains.
    """
    # The organization predicate goes on before any user filter, so no
    # combination of query parameters can produce a listing that reaches
    # outside the caller's organizations.
    query = scoped(
        (select(ExperimentVersion, ValidationExperiment)
         .join(ValidationExperiment,
               ValidationExperiment.id == ExperimentVersion.experiment_id)),
        ValidationExperiment, ctx,
        study_column=ValidationExperiment.study_id,
        study_ids=await scoped_study_ids(session, ctx))

    if study_id is not None:
        query = query.where(ValidationExperiment.study_id == study_id)
    if project_id is not None:
        query = query.where(ValidationExperiment.project_id == project_id)
    if candidate_id is not None:
        query = query.where(ValidationExperiment.candidate_id == candidate_id)
    if subtype:
        try:
            query = query.where(
                ValidationExperiment.subtype == ExperimentSubtype(subtype))
        except ValueError:
            return _error("unknown_subtype", f"{subtype!r} is not a subtype.",
                          status.HTTP_400_BAD_REQUEST)
    if purpose:
        try:
            query = query.where(
                ValidationExperiment.purpose == ReadinessArea(purpose))
        except ValueError:
            return _error("unknown_purpose", f"{purpose!r} is not a purpose.",
                          status.HTTP_400_BAD_REQUEST)
    if status_filter:
        try:
            query = query.where(
                ExperimentVersion.status == ExperimentStatus(status_filter))
        except ValueError:
            return _error("unknown_status", f"{status_filter!r} is not a status.",
                          status.HTTP_400_BAD_REQUEST)
    if laboratory:
        query = query.where(
            ExperimentVersion.laboratory_name.ilike(f"%{laboratory}%"))
    if investigator:
        query = query.where(
            ExperimentVersion.investigator_name.ilike(f"%{investigator}%"))
    if reviewer_id is not None:
        query = query.where(ExperimentVersion.reviewer_id == reviewer_id)
    if e3_eligible is True:
        query = query.where(ExperimentVersion.approved_level == EvidenceLevel.E3)
    elif e3_eligible is False:
        query = query.where(ExperimentVersion.approved_level.is_(None))

    rows = (await session.execute(
        query.order_by(ExperimentVersion.created_at.desc()).limit(limit))).all()
    return {
        "experiments": [_version_summary(v, e) for v, e in rows],
        "total": len(rows),
    }


@router.get("/dashboard", summary="Registry summary counts")
async def dashboard(study_id: int | None = Query(None),
                    user: User = Depends(get_current_user),
                    ctx: AccessContext = Depends(get_access_context),
                    session: AsyncSession = Depends(get_auth_session)):
    # The organization predicate goes on before any user filter, so no
    # combination of query parameters can produce a listing that reaches
    # outside the caller's organizations.
    query = scoped(
        (select(ExperimentVersion, ValidationExperiment)
         .join(ValidationExperiment,
               ValidationExperiment.id == ExperimentVersion.experiment_id)),
        ValidationExperiment, ctx,
        study_column=ValidationExperiment.study_id,
        study_ids=await scoped_study_ids(session, ctx))
    if study_id is not None:
        query = query.where(ValidationExperiment.study_id == study_id)
    rows = (await session.execute(query)).all()

    by_status: dict[str, int] = {s.value: 0 for s in ExperimentStatus}
    by_purpose: dict[str, int] = {}
    approved_by_purpose: dict[str, int] = {}
    for version, experiment in rows:
        by_status[version.status.value] += 1
        by_purpose[experiment.purpose.value] = (
            by_purpose.get(experiment.purpose.value, 0) + 1)
        if version.approved_level == EvidenceLevel.E3:
            approved_by_purpose[experiment.purpose.value] = (
                approved_by_purpose.get(experiment.purpose.value, 0) + 1)

    evidence: dict[str, Any] = {}
    if study_id is not None:
        evidence = await svc.approved_evidence_for_study(session,
                                                          study_id=study_id)
    return {
        "study_id": study_id,
        "total_experiments": len(rows),
        "by_status": by_status,
        "by_purpose": by_purpose,
        "approved_by_purpose": approved_by_purpose,
        "purposes_with_e3": sorted(
            k for k, v in evidence.items() if v.get("level") == "E3"),
        "purposes_with_contradiction": sorted(
            k for k, v in evidence.items() if v.get("contradiction")),
        "registry_version": REGISTRY_VERSION,
    }


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------


@router.post("/experiments", summary="Create an experiment and its first draft")
async def create_experiment(request: ExperimentCreateRequest,
                            user: User = Depends(get_current_user),
                            ctx: AccessContext = Depends(get_access_context),
                            session: AsyncSession = Depends(get_auth_session)):
    try:
        subtype = ExperimentSubtype(request.subtype)
        purpose = ReadinessArea(request.purpose)
    except ValueError:
        return _error("unknown_vocabulary",
                      "The subtype or purpose is not recognised.",
                      status.HTTP_400_BAD_REQUEST)

    code = request.code or f"EXP-{int(__import__('time').time())}"
    try:
        experiment, version = await svc.create_experiment(
            session, actor=_actor(user, ctx),
            candidate_version_id=request.candidate_version_id,
            subtype=subtype, purpose=purpose, title=request.title, code=code,
            performed_by=request.performed_by)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    return {"experiment_id": experiment.id, "code": experiment.code,
            "version_id": version.id, "version_number": version.version_number}


@router.get("/experiments/{experiment_id}", summary="Experiment detail")
async def get_experiment(experiment_id: int,
                         user: User = Depends(get_current_user),
                         ctx: AccessContext = Depends(get_access_context),
                         session: AsyncSession = Depends(get_auth_session)):
    experiment = await _scoped_experiment(session, ctx, experiment_id)

    versions = (await session.execute(
        select(ExperimentVersion)
        .where(ExperimentVersion.experiment_id == experiment_id)
        .order_by(ExperimentVersion.version_number.desc()))).scalars().all()
    current = versions[0] if versions else None

    payload: dict[str, Any] = {
        "experiment": {
            "id": experiment.id, "code": experiment.code,
            "title": experiment.title,
            "subtype": experiment.subtype.value,
            "subtype_label": SUBTYPE_LABEL[experiment.subtype],
            "purpose": experiment.purpose.value,
            "purpose_label": PURPOSE_LABEL[experiment.purpose],
            "study_id": experiment.study_id,
            "candidate_id": experiment.candidate_id,
            "project_id": experiment.project_id,
        },
        "versions": [
            {"id": v.id, "version_number": v.version_number,
             "status": v.status.value, "status_label": STATUS_LABEL[v.status],
             "approved_level": (v.approved_level.value
                                if v.approved_level else None),
             "created_at": v.created_at.isoformat(),
             "superseded_by_version_id": v.superseded_by_version_id}
            for v in versions
        ],
    }
    if current is not None:
        payload["current_version"] = await _version_detail(session, current)
        payload["capabilities"] = sorted(
            c.value for c in capabilities_for(
                _actor(user, ctx),
                ExperimentContext(owner_id=experiment.owner_id,
                                  status=current.status,
                                  performed_by=current.performed_by)))
    return payload


async def _version_detail(session: AsyncSession,
                          version: ExperimentVersion) -> dict[str, Any]:
    measurements = (await session.execute(
        select(Measurement).where(
            Measurement.version_id == version.id))).scalars().all()
    attachments = (await session.execute(
        select(ExperimentAttachment).where(
            ExperimentAttachment.version_id == version.id))).scalars().all()

    # Explicit allow-lists, never reflection over the model. A column added to
    # the schema stays invisible to clients until somebody names it in
    # validation_serializers, which is a decision with a diff rather than an
    # accident of ORM introspection.
    return {
        **serialize_version(version),
        "measurements": [serialize_measurement(m) for m in measurements],
        "attachments": [serialize_attachment(a) for a in attachments],
    }


@router.get("/versions/{version_id}", summary="One experiment version")
async def get_version(version_id: int,
                      user: User = Depends(get_current_user),
                      ctx: AccessContext = Depends(get_access_context),
                      session: AsyncSession = Depends(get_auth_session)):
    version = await _scoped_version(session, ctx, version_id)
    return await _version_detail(session, version)


@router.patch("/versions/{version_id}", summary="Edit a draft version")
async def update_draft(version_id: int, request: DraftUpdateRequest,
                       user: User = Depends(get_current_user),
                       ctx: AccessContext = Depends(get_access_context),
                       session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_version(session, ctx, version_id)
    fields = {k: v for k, v in request.model_dump(exclude_unset=True).items()}
    if "requested_level" in fields and fields["requested_level"]:
        try:
            fields["requested_level"] = EvidenceLevel(fields["requested_level"])
        except ValueError:
            return _error("unknown_level",
                          f"{fields['requested_level']!r} is not a level.",
                          status.HTTP_400_BAD_REQUEST)
    for date_field in ("start_date", "completion_date"):
        if fields.get(date_field):
            from datetime import date as _date
            try:
                fields[date_field] = _date.fromisoformat(fields[date_field])
            except ValueError:
                return _error(
                    "invalid_date",
                    f"{date_field} must be an ISO date (YYYY-MM-DD).",
                    status.HTTP_400_BAD_REQUEST)
    try:
        await svc.update_draft(session, actor=_actor(user, ctx),
                               version_id=version_id, fields=fields)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    return {"version_id": version_id, "updated": sorted(fields)}


@router.post("/versions/{version_id}/measurements",
             summary="Record structured measurements")
async def add_measurements(version_id: int, request: MeasurementBatchRequest,
                           user: User = Depends(get_current_user),
                           ctx: AccessContext = Depends(get_access_context),
                           session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_version(session, ctx, version_id)
    try:
        created = await svc.add_measurements(
            session, actor=_actor(user, ctx), version_id=version_id,
            rows=[r.model_dump() for r in request.rows])
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    return {"version_id": version_id, "recorded": len(created)}


# ---------------------------------------------------------------------------
# Workflow transitions
# ---------------------------------------------------------------------------


@router.post("/versions/{version_id}/submit", summary="Submit for review")
async def submit(version_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
                 session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_version(session, ctx, version_id)
    try:
        version = await svc.submit_version(session, actor=_actor(user, ctx),
                                           version_id=version_id)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    return {"version_id": version.id, "status": version.status.value}


@router.post("/versions/{version_id}/review", summary="Begin scientific review")
async def start_review(version_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
                       session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_version(session, ctx, version_id)
    try:
        version = await svc.start_review(session, actor=_actor(user, ctx),
                                         version_id=version_id)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    return {"version_id": version.id, "status": version.status.value,
            "reviewer_id": version.reviewer_id}


@router.post("/versions/{version_id}/decision",
             summary="Approve, reject or request revision")
async def record_decision(version_id: int, request: ReviewDecisionRequest,
                          user: User = Depends(get_current_user),
                          ctx: AccessContext = Depends(get_access_context),
                          session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_version(session, ctx, version_id)
    try:
        decision = ReviewDecision(request.decision)
    except ValueError:
        return _error("unknown_decision",
                      f"{request.decision!r} is not a review decision.",
                      status.HTTP_400_BAD_REQUEST)
    try:
        version, verdict = await svc.record_decision(
            session, actor=_actor(user, ctx), version_id=version_id,
            decision=decision, comments=request.comments)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    return {
        "version_id": version.id,
        "status": version.status.value,
        "approved_level": (version.approved_level.value
                           if version.approved_level else None),
        "eligibility": verdict.to_dict() if verdict else None,
    }


@router.post("/versions/{version_id}/revision",
             summary="Create a new version, superseding this one")
async def create_revision(version_id: int, request: RevisionRequest,
                          user: User = Depends(get_current_user),
                          ctx: AccessContext = Depends(get_access_context),
                          session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_version(session, ctx, version_id)
    try:
        fresh = await svc.create_revision(
            session, actor=_actor(user, ctx), version_id=version_id,
            candidate_version_id=request.candidate_version_id)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    return {"version_id": fresh.id, "version_number": fresh.version_number,
            "status": fresh.status.value}


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


@router.get("/versions/{version_id}/eligibility",
            summary="Evaluate E3 eligibility")
async def eligibility(version_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
                      session: AsyncSession = Depends(get_auth_session)):
    """The full verdict, gates and all.

    Returned for a draft as readily as for an approved record: an investigator
    needs to see which gates are outstanding *while* there is still time to
    address them, not only at the point of refusal.
    """
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_version(session, ctx, version_id)
    try:
        verdict = await svc.evaluate_version(session, version_id=version_id)
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)
    return verdict.to_dict()


@router.get("/studies/{study_id}/evidence",
            summary="Approved E3 evidence for a study, by purpose")
async def study_evidence(study_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
                         session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_study(session, ctx, study_id)
    evidence = await svc.approved_evidence_for_study(session,
                                                      study_id=study_id)
    return {"study_id": study_id, "by_purpose": evidence,
            "registry_version": REGISTRY_VERSION}


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------


@router.post("/versions/{version_id}/attachments", summary="Upload a file")
async def upload_attachment(version_id: int, category: str = Query(...),
                            file: UploadFile = None,  # type: ignore[assignment]
                            user: User = Depends(get_current_user),
                            ctx: AccessContext = Depends(get_access_context),
                            session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_version(session, ctx, version_id)
    if file is None:
        return _error("no_file", "No file was supplied.",
                      status.HTTP_400_BAD_REQUEST)
    try:
        cat = AttachmentCategory(category)
    except ValueError:
        return _error("unknown_category",
                      f"{category!r} is not an attachment category.",
                      status.HTTP_400_BAD_REQUEST)

    # Read with a hard ceiling so an oversized upload cannot be streamed into
    # memory before the size check runs.
    content = await file.read(MAX_ATTACHMENT_BYTES + 1)
    if len(content) > MAX_ATTACHMENT_BYTES:
        return _error("file_too_large",
                      f"The file exceeds the "
                      f"{MAX_ATTACHMENT_BYTES / 1e6:.0f} MB limit.",
                      status.HTTP_400_BAD_REQUEST)

    try:
        attachment = await svc.upload_attachment(
            session, actor=_actor(user, ctx), version_id=version_id, category=cat,
            filename=file.filename or "", declared_mime=file.content_type or "",
            content=content)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    return {
        "id": attachment.id, "category": attachment.category.value,
        "original_filename": attachment.original_filename,
        "mime_type": attachment.mime_type, "size_bytes": attachment.size_bytes,
        "checksum_sha256": attachment.checksum_sha256,
    }


@router.get("/attachments/{attachment_id}", summary="Download an attachment")
async def download_attachment(attachment_id: int,
                              user: User = Depends(get_current_user),
                              ctx: AccessContext = Depends(get_access_context),
                              session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    scoped_row = await _scoped_attachment(session, ctx, attachment_id)
    # The collaboration's attachment restriction, checked before the store is
    # touched. See `_require_download_permission`.
    await _require_download_permission(session, ctx, scoped_row)
    try:
        attachment, content = await svc.read_attachment(
            session, actor=_actor(user, ctx), attachment_id=attachment_id)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    from nanobio_studio.app.validation.storage import download_headers, \
        served_media_type

    # Never rendered inline in the application's origin. See
    # `download_headers` for what each header is stopping.
    return Response(
        content=content,
        media_type=served_media_type(attachment.mime_type),
        headers=download_headers(attachment.original_filename),
    )


@router.delete("/attachments/{attachment_id}",
               summary="Remove an attachment from a draft")
async def delete_attachment(attachment_id: int,
                            user: User = Depends(get_current_user),
                            ctx: AccessContext = Depends(get_access_context),
                            session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_attachment(session, ctx, attachment_id)
    try:
        await svc.remove_attachment(session, actor=_actor(user, ctx),
                                    attachment_id=attachment_id)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)
    return {"removed": attachment_id}


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@router.get("/experiments/{experiment_id}/audit", summary="Audit history")
async def audit_history(experiment_id: int,
                        user: User = Depends(get_current_user),
                        ctx: AccessContext = Depends(get_access_context),
                        session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_experiment(session, ctx, experiment_id)
    rows = await svc.audit_trail(session, experiment_id=experiment_id)
    return {
        "experiment_id": experiment_id,
        "events": [
            {"id": e.id, "event": e.event.value, "actor_id": e.actor_id,
             "version_id": e.experiment_version_id, "summary": e.summary,
             "created_at": e.created_at.isoformat()}
            for e in rows
        ],
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# Contradiction resolution
# ---------------------------------------------------------------------------


@router.post("/studies/{study_id}/contradictions",
             summary="Record how conflicting approved evidence should be read")
async def resolve_contradiction(study_id: int,
                                request: ContradictionResolutionRequest,
                                user: User = Depends(get_current_user),
                                ctx: AccessContext = Depends(get_access_context),
                                session: AsyncSession = Depends(get_auth_session)):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_study(session, ctx, study_id)
    try:
        purpose = ReadinessArea(request.purpose)
    except ValueError:
        return _error("unknown_purpose", f"{request.purpose!r} is not a purpose.",
                      status.HTTP_400_BAD_REQUEST)

    level: EvidenceLevel | None = None
    if request.resolved_level:
        try:
            level = EvidenceLevel(request.resolved_level)
        except ValueError:
            return _error("unknown_level",
                          f"{request.resolved_level!r} is not a level.",
                          status.HTTP_400_BAD_REQUEST)

    try:
        resolution = await svc.resolve_contradiction(
            session, actor=_actor(user, ctx), study_id=study_id, purpose=purpose,
            rationale=request.rationale, resolved_level=level,
            candidate_version_id=request.candidate_version_id)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)

    return {
        "id": resolution.id,
        "purpose": resolution.purpose.value,
        "resolved_level": (resolution.resolved_level.value
                           if resolution.resolved_level else None),
        "rationale": resolution.rationale,
        "resolved_by": resolution.resolved_by,
        "resolved_at": resolution.resolved_at.isoformat(),
        "considered_version_ids": resolution.considered_version_ids,
    }


@router.get("/studies/{study_id}/contradictions",
            summary="Recorded contradiction resolutions, newest first")
async def list_contradiction_resolutions(
    study_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    # Reachability first: an identifier outside the caller's
    # organizations must be indistinguishable from one that does not
    # exist, so this resolves before anything else touches the record.
    await _scoped_study(session, ctx, study_id)
    rows = await svc.list_resolutions(session, study_id=study_id)
    return {
        "study_id": study_id,
        "resolutions": [
            {"id": r.id, "purpose": r.purpose.value,
             "resolved_level": (r.resolved_level.value
                                if r.resolved_level else None),
             "rationale": r.rationale, "resolved_by": r.resolved_by,
             "resolved_at": r.resolved_at.isoformat(),
             "considered_version_ids": r.considered_version_ids,
             "superseded_by_id": r.superseded_by_id}
            for r in rows
        ],
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# Candidate revision and supersession
# ---------------------------------------------------------------------------
#
# The rule these routes exist to enforce: once a candidate version has been
# relied upon, its scientific inputs cannot change. Revising means creating a
# new version that records what it came from and why — the original stays
# exactly as it was, and every decision made about it stays true.


@router.get("/candidates/{candidate_id}/versions",
            summary="Version history, with lineage and status")
async def candidate_version_history(
    candidate_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """The full history, with each version's standing stated explicitly.

    `current_effective_version` is reported as its own field rather than the
    caller being left to pick the newest row. "Latest" is ambiguous between the
    newest draft and the one currently approved, and a screen that shows the
    wrong one is showing an unreviewed formulation as though the organization
    stood behind it.
    """
    from nanobio_studio.app.services import candidate_versioning as cvs

    candidate = await _scoped_candidate(session, ctx, candidate_id)

    versions = (await session.execute(
        scoped(select(CandidateVersion), CandidateVersion, ctx)
        .where(CandidateVersion.candidate_id == candidate.id)
        .order_by(CandidateVersion.version_number.asc()))).scalars().all()

    effective = await cvs.current_effective_version(session, candidate.id)
    approved = await cvs.latest_approved_version(session, candidate.id)
    newest_draft = await cvs.latest_draft_version(session, candidate.id)

    return {
        "candidate_id": candidate.id,
        "candidate_code": candidate.code,
        # Named explicitly, never "latest".
        "current_effective_version_id": effective.id if effective else None,
        "latest_approved_version_id": approved.id if approved else None,
        "latest_draft_version_id": newest_draft.id if newest_draft else None,
        "versions": [_candidate_version_summary(v) for v in versions],
        "total": len(versions),
    }


def _candidate_version_summary(version: CandidateVersion) -> dict:
    """One version, as the history screen needs it.

    Delegates to the serializer's allow-list, which is shared with the
    version-bound artefact router. The snapshot itself is deliberately absent —
    it can be large, and the history is a list. It is fetched per version by
    the comparison route.
    """
    return serialize_candidate_version(version)


@router.post("/candidate-versions/{version_id}/revise",
             summary="Create a revision derived from this version")
async def revise_candidate_version(
    version_id: int, request: CandidateRevisionRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """The replacement for editing a version that something depends on.

    The predecessor is not touched: not superseded, not withdrawn, not
    re-pointed. Superseding is a separate decision needing its own authority,
    because otherwise any author could retire an approved formulation by
    starting to edit it.
    """
    from nanobio_studio.app.services import candidate_versioning as cvs

    predecessor = await _scoped_candidate_version(session, ctx, version_id)

    try:
        version, created = await cvs.create_revision(
            session, predecessor=predecessor,
            design_inputs=request.design_inputs, reason=request.reason,
            actor_id=user.id, carry_results=request.carry_results,
            idempotency_key=request.idempotency_key)
        await session.commit()
    except cvs.VersioningError as exc:
        await session.rollback()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": exc.code, "message": exc.message,
                     "remedy": exc.remedy, "data_available": False})
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _handle(exc)

    changes = cvs.compare_snapshots(predecessor.design_snapshot_json,
                                    version.design_snapshot_json)
    consequence = cvs.consequence_of_change({c.field for c in changes})

    return {
        **_candidate_version_summary(version),
        # False when an idempotency key matched, so a retried submission is
        # visibly a retry rather than looking like a second revision.
        "created": created,
        "predecessor": _candidate_version_summary(predecessor),
        "changed_fields": [
            {"field": c.field, "before": c.before, "after": c.after,
             "kind": c.kind, "scientific": c.is_scientific}
            for c in changes
        ],
        "consequence": consequence,
        "notice": (
            "The previous version is unchanged, and every experiment, review, "
            "approval and report that referenced it still refers to it. This "
            "revision starts as a draft and carries no approval."),
    }


@router.get("/candidate-versions/{version_id}/compare/{other_version_id}",
            summary="Structured field-by-field comparison")
async def compare_candidate_versions(
    version_id: int, other_version_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """A structured comparison, not a text diff.

    A raw JSON diff is unreadable at exactly the moment it matters — a
    reviewer deciding whether a change needs a fresh safety opinion should not
    be counting braces to discover that the dose moved.
    """
    from nanobio_studio.app.services import candidate_versioning as cvs

    left = await _scoped_candidate_version(session, ctx, version_id)
    right = await _scoped_candidate_version(session, ctx, other_version_id)

    if left.candidate_id != right.candidate_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "different_candidates",
                     "message": ("Those versions belong to different "
                                 "candidates and are not comparable."),
                     "data_available": False})

    changes = cvs.compare_snapshots(left.design_snapshot_json,
                                    right.design_snapshot_json)
    consequence = cvs.consequence_of_change({c.field for c in changes})

    return {
        "left": _candidate_version_summary(left),
        "right": _candidate_version_summary(right),
        "changed_fields": [
            {"field": c.field, "before": c.before, "after": c.after,
             "kind": c.kind, "scientific": c.is_scientific}
            for c in changes
        ],
        "consequence": consequence,
        "identical": not changes,
    }


@router.post("/candidate-versions/{version_id}/supersede",
             summary="Record that a later version has taken over")
async def supersede_candidate_version(
    version_id: int, request: SupersessionRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Requires approval authority, not merely write access.

    Administrative authority is deliberately not sufficient: managing who has
    access is a different thing from deciding which formulation the
    organization stands behind, and the separation is the same one the review
    workflow already maintains.
    """
    from nanobio_studio.app.organizations.policy import Action, RecordFacts, require
    from nanobio_studio.app.services import candidate_versioning as cvs

    predecessor = await _scoped_candidate_version(session, ctx, version_id)
    successor = await _scoped_candidate_version(
        session, ctx, request.successor_version_id)

    candidate = await _scoped_candidate(session, ctx, predecessor.candidate_id)

    # Scientific authority, through the central policy. A version can only be
    # retired by somebody who could have approved it.
    #
    # `Action.APPROVE`, not `APPROVE_EXPERIMENT` — which does not exist on the
    # enum and never did. This line raised AttributeError for every caller who
    # reached it, so the route returned 500 rather than either superseding or
    # refusing. Nothing caught it because no test drove a supersession through
    # HTTP with a reachable pair of versions.
    require(ctx, Action.APPROVE,
            RecordFacts(organization_id=candidate.organization_id,
                        study_id=candidate.study_id,
                        owner_id=candidate.owner_id))

    # Separation of duty: the author of the successor must not be the one who
    # decides it replaces the predecessor.
    if successor.created_by is not None and successor.created_by == user.id:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "self_supersession_refused",
                     "message": ("You created the version that would take "
                                 "over, so you cannot also be the one who "
                                 "decides it replaces the current one."),
                     "remedy": ("Ask another approver. The separation is the "
                                "same one that stops an author approving "
                                "their own experiment."),
                     "data_available": False})

    try:
        await cvs.accept_supersession(
            session, predecessor=predecessor, successor=successor,
            actor_id=user.id, decision_id=request.decision_id,
            reason=request.reason,
            expected_revision=request.expected_revision)
        await session.commit()
    except cvs.VersioningError as exc:
        await session.rollback()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": exc.code, "message": exc.message,
                     "remedy": exc.remedy, "data_available": False})

    return {
        "superseded": _candidate_version_summary(predecessor),
        "successor_version_id": successor.id,
        "notice": (
            "The superseded version and everything that referenced it are "
            "unchanged. Superseding records which version to use next; it "
            "does not withdraw the work already done on the older one."),
    }


@router.post("/candidate-versions/{version_id}/withdraw",
             summary="Retire a version without a successor")
async def withdraw_candidate_version(
    version_id: int, request: VersionWithdrawRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Distinct from supersession, and the distinction is a scientific claim.

    Superseded means "use this newer one instead". Withdrawn means "we no
    longer stand behind this at all". Conflating them would let a rejected
    formulation read as an ordinary predecessor.
    """
    from nanobio_studio.app.services import candidate_versioning as cvs

    version = await _scoped_candidate_version(session, ctx, version_id)

    try:
        await cvs.withdraw_version(session, version=version,
                                   reason=request.reason, actor_id=user.id)
        await session.commit()
    except cvs.VersioningError as exc:
        await session.rollback()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": exc.code, "message": exc.message,
                     "remedy": exc.remedy, "data_available": False})

    return {
        **_candidate_version_summary(version),
        "notice": ("This version stays in the record and every result that "
                   "referenced it still does. Withdrawing states that it is "
                   "no longer relied upon."),
    }
