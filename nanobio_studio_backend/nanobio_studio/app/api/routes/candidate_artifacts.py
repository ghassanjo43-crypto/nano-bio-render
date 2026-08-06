"""Endpoints for records that depend on an exact candidate version.

The contract, in one sentence
-----------------------------
**Every route here is addressed to a version, never to a candidate.** An
endpoint that took a candidate id and worked out which version it meant would
produce a report, export or package whose subject depended on when it ran, and
two runs a minute apart could describe different formulations under the same
title. ``require_exact_version_id`` refuses ``"latest"`` explicitly rather than
letting it fail an ``int()`` conversion, so the refusal says what is wrong.

Transport only
--------------
Nothing here locks a version, writes an audit row or decides a permission of
its own. Locking, auditing and the dependent insert all happen inside
``services/candidate_dependencies.py``, in one transaction — so a future route
that forgets a step cannot reach the tables at all. These functions resolve
reachability, apply the organization policy, call the service, and commit once.

Why it is a separate module from ``routes/validation.py``
---------------------------------------------------------
That file is the registry: experiments, measurements, reviews, decisions. This
one is the artefacts a version produces. Keeping them apart is partly size and
mostly the ``_version_summary`` defect — one module with two families of
helpers is where a second function quietly replaced the first and broke a route
nobody had touched. Shared resolvers live in ``candidate_scope.py``; shared
serialisation lives in ``serializers/validation_serializers.py``. Neither is
copied.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.api.deps_auth import get_current_user
from nanobio_studio.app.api.deps_organization import get_access_context
from nanobio_studio.app.api.routes.candidate_scope import (
    resolve_candidate, resolve_candidate_version,
)
from nanobio_studio.app.api.serializers.validation_serializers import (
    serialize_candidate_version,
)
from nanobio_studio.app.db.auth_models import User
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.db.candidate_dependency_models import CandidateReport
from nanobio_studio.app.db.validation_models import (
    CandidateVersion, ValidationAuditLog,
)
from nanobio_studio.app.organizations.policy import (
    AccessContext, Action, RecordFacts, require as require_policy,
)
from nanobio_studio.app.organizations.scoping import require_scoped, scoped
from nanobio_studio.app.schemas.validation import (
    ComparisonRecordRequest, CROPackageRequest, EvidenceAssessmentRequest,
    ExportGenerationRequest, RecalculationRequest, ReportGenerationRequest,
    SimulationRecordRequest, SupersessionProposalRequest,
    SupersessionRefusalRequest,
)
from nanobio_studio.app.science.statuses import EvidenceLevel, ReadinessArea
from nanobio_studio.app.services import candidate_dependencies as deps
from nanobio_studio.app.services import candidate_versioning as cvs
from nanobio_studio.app.validation.permissions import (
    PermissionDenied, RegistryActor,
)
from nanobio_studio.app.validation.vocabulary import (
    EVIDENCE_REUSE_LABEL, EvidenceReuse, GeneratedArtifactFormat,
    SimulationKind,
)

router = APIRouter(prefix="/api/v1/validation", tags=["candidate-artifacts"])


# ---------------------------------------------------------------------------
# Shared plumbing
# ---------------------------------------------------------------------------

def _failure(code: str, message: str, http_status: int,
             detail: str | None = None,
             remedy: str | None = None) -> JSONResponse:
    """Structured refusal. Never carries a partial artefact.

    ``registry_available: False`` matches the shape the registry's own
    failures use, so a rejected request cannot be mistaken by the interface
    for an empty result.
    """
    return JSONResponse(
        status_code=http_status,
        content={"error": code, "message": message, "detail": detail,
                 "remedy": remedy, "registry_available": False})


def _translate(exc: Exception) -> JSONResponse:
    """Map a service refusal onto HTTP, keeping the remedy the caller can act on.

    An ambiguous version reference is a 400 about the *request* — nothing is
    wrong with the data, the caller did not say what the operation was about.
    A versioning conflict is a 409 because the record moved. A missing record
    is a 404. Collapsing the three into one code would leave the caller unable
    to tell "you asked wrongly" from "somebody else changed it".
    """
    if isinstance(exc, cvs.AmbiguousVersionReference):
        return _failure(exc.code, exc.message, status.HTTP_400_BAD_REQUEST,
                        remedy=exc.remedy)
    if isinstance(exc, cvs.VersioningError):
        return _failure(exc.code, exc.message, status.HTTP_409_CONFLICT,
                        remedy=exc.remedy)
    if isinstance(exc, deps.DependencyError):
        http = (status.HTTP_404_NOT_FOUND if exc.code.endswith("_not_found")
                else status.HTTP_400_BAD_REQUEST)
        return _failure(exc.code, exc.message, http, detail=exc.detail)
    if isinstance(exc, PermissionDenied):
        return _failure("permission_denied", exc.reason,
                        status.HTTP_403_FORBIDDEN,
                        detail=f"capability: {exc.capability.value}")
    raise exc


def _registry_actor(user: User, ctx: AccessContext) -> RegistryActor:
    """The actor, carrying this request's access facts.

    Resolved once per request by the dependency and passed down; nothing below
    re-derives it. A membership revoked midway through a request must not be in
    force for one check and absent from the next.
    """
    return RegistryActor(user_id=user.id, role=user.role, access=ctx)


async def _authorize_write(session: AsyncSession, ctx: AccessContext,
                           version: CandidateVersion, action: Action) -> None:
    """The organization's answer, before any dependent record is written.

    The service refuses a viewer and an administrator on its own — that is a
    property of the role and holds for every caller. This adds what the service
    has no view of: membership status, study assignment, collaboration terms.
    Both are needed, and neither is a substitute for the other.
    """
    candidate = await resolve_candidate(session, ctx, version.candidate_id)
    require_policy(ctx, action, RecordFacts(
        organization_id=candidate.organization_id,
        study_id=candidate.study_id,
        owner_id=candidate.owner_id))


def _identity(version: CandidateVersion) -> dict:
    """The three facts an artefact reference must always carry.

    Repeated in every response rather than left for the client to join,
    because a list of report ids with no version attached is the exact shape
    that lets an interface show a historical report under the current version.
    """
    return {
        "candidate_id": version.candidate_id,
        "candidate_version_id": version.id,
        "version_label": version.effective_label(),
    }


# ---------------------------------------------------------------------------
# Simulations
# ---------------------------------------------------------------------------

@router.post("/candidate-versions/{version_id}/simulations",
             summary="Record a simulation result against this exact version")
async def record_simulation(
    version_id: int, request: SimulationRecordRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Running a simulation is what makes a formulation immutable.

    The lock is applied in the same transaction as the stored result, so there
    is no moment at which a result exists and its inputs can still be edited.
    """
    version = await resolve_candidate_version(session, ctx, version_id)
    await _authorize_write(session, ctx, version, Action.CREATE_EXPERIMENT)

    try:
        kind = SimulationKind(request.kind)
    except ValueError:
        return _failure(
            "unknown_simulation_kind",
            f"{request.kind!r} is not a simulation this platform runs.",
            status.HTTP_400_BAD_REQUEST,
            detail="One of: " + ", ".join(k.value for k in SimulationKind))

    try:
        simulation = await deps.record_simulation(
            session, actor=_registry_actor(user, ctx),
            candidate_version_id=version_id, kind=kind,
            engine_version=request.engine_version, inputs=request.inputs,
            result=request.result, ruleset_version=request.ruleset_version,
            failure_reason=request.failure_reason)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _translate(exc)

    return {
        **_identity(version),
        "simulation_id": simulation.id,
        "kind": simulation.kind.value,
        "state": simulation.state.value,
        "engine_version": simulation.engine_version,
        "inputs_checksum": simulation.inputs_checksum,
        "created_at": simulation.created_at.isoformat(),
        "version_status": version.status.value,
        "version_locked": not version.is_editable(),
        "lock_reason": version.lock_reason,
        "results_state": version.results_state.value,
        "notice": (
            "This result is attributed to the exact version named above. The "
            "formulation's scientific inputs are now locked; changing them "
            "means creating a revision."),
    }


@router.get("/candidate-versions/{version_id}/simulations",
            summary="Simulations recorded against this exact version")
async def list_simulations(
    version_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Reading locks nothing. Looking at a formulation is not depending on it."""
    version = await resolve_candidate_version(session, ctx, version_id)
    rows = await deps.simulations_for_version(session, version.id)

    return {
        **_identity(version),
        "simulations": [
            {"id": r.id, "kind": r.kind.value, "state": r.state.value,
             "engine_version": r.engine_version,
             "ruleset_version": r.ruleset_version,
             "inputs_checksum": r.inputs_checksum,
             # Stated per row rather than inferred from the version: a copied
             # result is stale even where the version's own results are not.
             "is_stale": r.state.value in ("copied_stale", "invalidated"),
             "copied_from_simulation_id": r.copied_from_simulation_id,
             "source_candidate_version_id": r.source_candidate_version_id,
             "failure_reason": r.failure_reason,
             "created_at": r.created_at.isoformat(),
             "created_by": r.created_by}
            for r in rows
        ],
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

@router.post("/candidate-versions/{version_id}/evidence",
             summary="Record how evidence stands for this exact version")
async def record_evidence(
    version_id: int, request: EvidenceAssessmentRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Evidence reuse must be classified, and unclassified is not an option.

    An experiment performed on v1 remains an experiment performed on v1. A
    revision may cite it, and the citation has to say so — otherwise the
    interface has re-attested it to a formulation nobody tested.
    """
    version = await resolve_candidate_version(session, ctx, version_id)
    await _authorize_write(session, ctx, version, Action.CREATE_EXPERIMENT)

    try:
        purpose = ReadinessArea(request.purpose)
    except ValueError:
        return _failure("unknown_purpose",
                        f"{request.purpose!r} is not a readiness area.",
                        status.HTTP_400_BAD_REQUEST)
    try:
        reuse = EvidenceReuse(request.reuse)
    except ValueError:
        return _failure(
            "unknown_reuse_classification",
            f"{request.reuse!r} is not an evidence reuse classification.",
            status.HTTP_400_BAD_REQUEST,
            detail="One of: " + ", ".join(r.value for r in EvidenceReuse))

    level = None
    if request.level is not None:
        try:
            level = EvidenceLevel(request.level)
        except ValueError:
            return _failure("unknown_evidence_level",
                            f"{request.level!r} is not an evidence level.",
                            status.HTTP_400_BAD_REQUEST)

    try:
        assessment = await deps.record_evidence_assessment(
            session, actor=_registry_actor(user, ctx),
            candidate_version_id=version_id, purpose=purpose, level=level,
            reuse=reuse, rationale=request.rationale,
            source_candidate_version_id=request.source_candidate_version_id,
            considered_experiment_version_ids=(
                request.considered_experiment_version_ids))
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _translate(exc)

    return {
        **_identity(version),
        "assessment_id": assessment.id,
        "purpose": assessment.purpose.value,
        "level": assessment.level.value if assessment.level else None,
        "reuse": assessment.reuse.value,
        "reuse_label": EVIDENCE_REUSE_LABEL.get(assessment.reuse,
                                                assessment.reuse.value),
        "source_candidate_version_id": assessment.source_candidate_version_id,
        "created_at": assessment.created_at.isoformat(),
    }


@router.get("/candidate-versions/{version_id}/evidence",
            summary="Evidence assessments for this exact version")
async def list_evidence(
    version_id: int, include_superseded: bool = Query(False),
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    version = await resolve_candidate_version(session, ctx, version_id)
    rows = await deps.evidence_for_version(
        session, version.id, include_superseded=include_superseded)

    return {
        **_identity(version),
        "assessments": [
            {"id": r.id, "purpose": r.purpose.value,
             "level": r.level.value if r.level else None,
             "reuse": r.reuse.value,
             "reuse_label": EVIDENCE_REUSE_LABEL.get(r.reuse, r.reuse.value),
             "source_candidate_version_id": r.source_candidate_version_id,
             "rationale": r.rationale,
             "ruleset_version": r.ruleset_version,
             "superseded_by_id": r.superseded_by_id,
             "created_at": r.created_at.isoformat(),
             "assessed_by": r.assessed_by}
            for r in rows
        ],
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@router.post("/candidate-versions/{version_id}/reports",
             summary="Generate a report frozen against this exact version")
async def generate_report(
    version_id: int, request: ReportGenerationRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    version = await resolve_candidate_version(session, ctx, version_id)
    # `CREATE_EXPERIMENT`, not `CREATE_REPORT`. The report actions belong to
    # patient assessments, which hang off no study and are deliberately
    # arbitrated on a separate branch that does not require a study
    # assignment. A candidate report IS scientific output about a study, so
    # asking the wrong verb let a member scoped to assigned studies — with no
    # assignment on this one — generate one. Found by the authorization
    # matrix below, which drives every refusal case through HTTP.
    await _authorize_write(session, ctx, version, Action.CREATE_EXPERIMENT)

    try:
        artifact_format = GeneratedArtifactFormat(request.format)
    except ValueError:
        return _failure(
            "unknown_format",
            f"{request.format!r} is not a format this platform generates.",
            status.HTTP_400_BAD_REQUEST)

    try:
        report = await deps.generate_report(
            session, actor=_registry_actor(user, ctx),
            candidate_version_id=version_id, title=request.title,
            body=request.body, format=artifact_format)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _translate(exc)

    return {
        **_identity(version),
        "report_id": report.id,
        "title": report.title,
        "version_checksum": report.version_checksum,
        "content_checksum": report.content_checksum,
        "format": report.format.value,
        "generated_at": report.generated_at.isoformat(),
        "generated_by": report.generated_by,
        "notice": (
            "This report is frozen against the version named above. Reopening "
            "it shows what it said when it was issued, not what today's data "
            "would say."),
    }


@router.get("/candidate-versions/{version_id}/reports",
            summary="Reports generated from this exact version")
async def list_reports(
    version_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    version = await resolve_candidate_version(session, ctx, version_id)
    rows = await deps.reports_for_version(session, version.id)

    return {
        **_identity(version),
        "reports": [
            {"id": r.id, "title": r.title, "version_label": r.version_label,
             "candidate_version_id": r.candidate_version_id,
             "version_checksum": r.version_checksum,
             "content_checksum": r.content_checksum,
             "format": r.format.value,
             "generated_at": r.generated_at.isoformat(),
             "generated_by": r.generated_by}
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/candidate-reports/{report_id}",
            summary="Reopen a report exactly as it was issued")
async def read_report(
    report_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Serves the stored content. Nothing is re-rendered.

    This is the route the whole freezing arrangement exists for. Regenerating
    the report from current data would answer a different question under the
    same title, and the reader would have no way to tell.
    """
    report = await require_scoped(
        session,
        scoped(select(CandidateReport), CandidateReport, ctx).where(
            CandidateReport.id == report_id),
        "report")
    # Reachability is decided by the candidate, which is scoped properly.
    await resolve_candidate(session, ctx, report.candidate_id)

    version = await session.get(CandidateVersion, report.candidate_version_id)
    superseded = (version is not None
                  and version.superseded_by_version_id is not None)

    return {
        "report_id": report.id,
        "candidate_id": report.candidate_id,
        "candidate_version_id": report.candidate_version_id,
        "version_label": report.version_label,
        "version_checksum": report.version_checksum,
        "title": report.title,
        "format": report.format.value,
        "content": json.loads(report.content_json),
        "content_checksum": report.content_checksum,
        "generated_at": report.generated_at.isoformat(),
        "generated_by": report.generated_by,
        # Said explicitly, because it is the reason to trust what is above.
        "regenerated": False,
        "historical": superseded,
        "superseded_by_version_id": (version.superseded_by_version_id
                                     if version is not None else None),
        "notice": (
            "Served from the stored content as issued. It has not been "
            "regenerated from current data."
            + (" The version it describes has since been superseded; it "
               "remains a true record of what was concluded then."
               if superseded else "")),
    }


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

@router.post("/candidate-versions/{version_id}/exports",
             summary="Generate an export identifying this exact version")
async def generate_export(
    version_id: int, request: ExportGenerationRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    version = await resolve_candidate_version(session, ctx, version_id)
    await _authorize_write(session, ctx, version, Action.CREATE_EXPERIMENT)

    try:
        artifact_format = GeneratedArtifactFormat(request.format)
    except ValueError:
        return _failure(
            "unknown_format",
            f"{request.format!r} is not a format this platform generates.",
            status.HTTP_400_BAD_REQUEST)

    try:
        export = await deps.generate_export(
            session, actor=_registry_actor(user, ctx),
            candidate_version_id=version_id, format=artifact_format,
            purpose_note=request.purpose_note, payload=request.payload)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _translate(exc)

    return {
        **_identity(version),
        "export_id": export.id,
        "format": export.format.value,
        "version_checksum": export.version_checksum,
        "content_checksum": export.content_checksum,
        "generated_at": export.generated_at.isoformat(),
        "manifest": json.loads(export.manifest_json),
    }


@router.get("/candidate-versions/{version_id}/exports",
            summary="Exports generated from this exact version")
async def list_exports(
    version_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    version = await resolve_candidate_version(session, ctx, version_id)
    rows = await deps.exports_for_version(session, version.id)

    return {
        **_identity(version),
        "exports": [
            {"id": r.id, "format": r.format.value,
             "version_label": r.version_label,
             "candidate_version_id": r.candidate_version_id,
             "version_checksum": r.version_checksum,
             "content_checksum": r.content_checksum,
             "purpose_note": r.purpose_note,
             "generated_at": r.generated_at.isoformat(),
             "generated_by": r.generated_by}
            for r in rows
        ],
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# CRO packages
# ---------------------------------------------------------------------------

@router.post("/candidate-versions/{version_id}/cro-packages",
             summary="Generate a CRO package for this exact version")
async def generate_cro_package(
    version_id: int, request: CROPackageRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """The most consequential artefact here: somebody outside will make this.

    So the manifest names the candidate, the exact version, its revision
    label, its snapshot checksum and the generation timestamp — and states
    whether the results it carries were computed for this version or inherited
    from a predecessor.
    """
    version = await resolve_candidate_version(session, ctx, version_id)
    await _authorize_write(session, ctx, version, Action.CREATE_EXPERIMENT)

    try:
        package = await deps.generate_cro_package(
            session, actor=_registry_actor(user, ctx),
            candidate_version_id=version_id,
            recipient_name=request.recipient_name,
            package_code=request.package_code,
            quotation_reference=request.quotation_reference,
            scope_note=request.scope_note)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _translate(exc)

    return {
        **_identity(version),
        "package_id": package.id,
        "package_code": package.package_code,
        "recipient_name": package.recipient_name,
        "quotation_reference": package.quotation_reference,
        "version_checksum": package.version_checksum,
        "content_checksum": package.content_checksum,
        "generated_at": package.generated_at.isoformat(),
        "manifest": json.loads(package.manifest_json),
    }


@router.get("/candidate-versions/{version_id}/cro-packages",
            summary="CRO packages generated from this exact version")
async def list_cro_packages(
    version_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    version = await resolve_candidate_version(session, ctx, version_id)
    rows = await deps.packages_for_version(session, version.id)

    return {
        **_identity(version),
        "packages": [
            {"id": r.id, "package_code": r.package_code,
             "recipient_name": r.recipient_name,
             "quotation_reference": r.quotation_reference,
             "version_label": r.version_label,
             "candidate_version_id": r.candidate_version_id,
             "version_checksum": r.version_checksum,
             "content_checksum": r.content_checksum,
             "generated_at": r.generated_at.isoformat(),
             "generated_by": r.generated_by}
            for r in rows
        ],
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# Filed comparisons
# ---------------------------------------------------------------------------

@router.post("/candidate-versions/{version_id}/comparisons",
             summary="File a comparison as a formal record")
async def record_comparison(
    version_id: int, request: ComparisonRecordRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Filing a comparison locks both sides. Browsing one does not.

    The registry's read-only compare route answers a question. This one says
    "this comparison is the basis of what happens next", which is an act, and
    from that point neither version may move underneath it.
    """
    left = await resolve_candidate_version(session, ctx, version_id)
    right = await resolve_candidate_version(session, ctx,
                                            request.other_version_id)
    await _authorize_write(session, ctx, left, Action.CREATE_EXPERIMENT)

    try:
        comparison = await deps.record_comparison(
            session, actor=_registry_actor(user, ctx), left_version_id=left.id,
            right_version_id=right.id, note=request.note)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _translate(exc)

    return {
        "comparison_id": comparison.id,
        "candidate_id": comparison.candidate_id,
        "left_version_id": comparison.left_version_id,
        "right_version_id": comparison.right_version_id,
        "changed_fields": json.loads(comparison.changed_fields_json),
        "consequence": json.loads(comparison.consequence_json),
        "material_classification": comparison.material_classification,
        "created_at": comparison.created_at.isoformat(),
        "notice": (
            "Both versions are now locked. A filed comparison is a basis for "
            "a decision, and neither side may change underneath it."),
    }


@router.get("/candidates/{candidate_id}/comparisons",
            summary="Comparisons filed for this candidate")
async def list_comparisons(
    candidate_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    candidate = await resolve_candidate(session, ctx, candidate_id)
    rows = await deps.comparisons_for_candidate(session, candidate.id)

    return {
        "candidate_id": candidate.id,
        "comparisons": [
            {"id": r.id, "left_version_id": r.left_version_id,
             "right_version_id": r.right_version_id,
             "material_classification": r.material_classification,
             "note": r.note,
             "created_at": r.created_at.isoformat(),
             "created_by": r.created_by}
            for r in rows
        ],
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# Recalculation, dependents, audit
# ---------------------------------------------------------------------------

@router.post("/candidate-versions/{version_id}/recalculate",
             summary="Ask for derived results to be recomputed")
async def request_recalculation(
    version_id: int, request: RecalculationRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Marks the version as recalculating. It does not invent a result.

    Recording the actual numbers is what ``POST .../simulations`` does, from a
    genuine engine response. Separating the request from the result is what
    keeps a version from reaching CURRENT because somebody asked for it.
    """
    version = await resolve_candidate_version(session, ctx, version_id)
    await _authorize_write(session, ctx, version, Action.CREATE_EXPERIMENT)

    try:
        await cvs.request_recalculation(session, version=version,
                                        actor_id=user.id,
                                        reason=request.reason)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _translate(exc)

    return {
        **serialize_candidate_version(version),
        "notice": (
            "Recalculation requested. The results stay unusable until an "
            "engine actually produces new ones for this version."),
    }


@router.get("/candidate-versions/{version_id}/dependents",
            summary="What depends on this exact version")
async def list_dependents(
    version_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Explains a lock in the terms the reader cares about.

    "Two simulations and a report depend on this" is an answer. "Locked" is a
    state, and somebody looking at a form they cannot edit needs the first one.
    """
    version = await resolve_candidate_version(session, ctx, version_id)
    counts = await deps.dependents_of_version(session, version.id)
    total = sum(counts.values())

    return {
        **_identity(version),
        "status": version.status.value,
        "editable": version.is_editable(),
        "lock_reason": version.lock_reason,
        "locked_at": (version.locked_at.isoformat()
                      if version.locked_at else None),
        "dependents": counts,
        "total_dependents": total,
        "explanation": (
            "Nothing depends on this version yet, so its scientific inputs "
            "can still be edited in place."
            if total == 0 else
            "These records were produced from this exact version. Editing its "
            "scientific inputs would silently re-describe what they were "
            "based on, so a change means creating a revision."),
    }


@router.get("/candidate-versions/{version_id}/audit",
            summary="Append-only history for this exact version")
async def version_audit(
    version_id: int, user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Reads the trail. Nothing in this application writes, updates or deletes one."""
    version = await resolve_candidate_version(session, ctx, version_id)
    candidate = await resolve_candidate(session, ctx, version.candidate_id)
    require_policy(ctx, Action.VIEW_AUDIT, RecordFacts(
        organization_id=candidate.organization_id,
        study_id=candidate.study_id, owner_id=candidate.owner_id))

    rows = (await session.execute(
        select(ValidationAuditLog)
        .where(ValidationAuditLog.candidate_version_id == version.id)
        .order_by(ValidationAuditLog.created_at.asc(),
                  ValidationAuditLog.id.asc()))).scalars().all()

    return {
        **_identity(version),
        "events": [
            {"id": r.id, "event": r.event.value, "actor_id": r.actor_id,
             "candidate_id": r.candidate_id,
             "candidate_version_id": r.candidate_version_id,
             "experiment_id": r.experiment_id,
             "reason": r.reason, "summary": r.summary,
             "created_at": r.created_at.isoformat()}
            for r in rows
        ],
        "total": len(rows),
        "notice": ("This trail is append-only. No route in this application "
                   "updates or deletes an entry."),
    }


# ---------------------------------------------------------------------------
# Supersession: proposing and refusing
# ---------------------------------------------------------------------------
#
# Accepting a supersession lives in ``routes/validation.py`` alongside the rest
# of the decision surface. Proposing and refusing are here because they are the
# two halves that are NOT the decision, and keeping them beside it made it easy
# to give all three the same authority — which would defeat the separation.


@router.post("/candidate-versions/{version_id}/propose-supersession",
             summary="Put a successor forward without deciding it")
async def propose_supersession(
    version_id: int, request: SupersessionProposalRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Proposing needs write access; accepting needs approval authority.

    Kept apart so an author can put their revision forward without also being
    the person who decides it replaces what the organization stands behind.
    """
    predecessor = await resolve_candidate_version(session, ctx, version_id)
    successor = await resolve_candidate_version(
        session, ctx, request.successor_version_id)
    await _authorize_write(session, ctx, predecessor, Action.CREATE_EXPERIMENT)

    try:
        await cvs.propose_supersession(
            session, predecessor=predecessor, successor=successor,
            reason=request.reason, actor_id=user.id)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _translate(exc)

    return {
        **serialize_candidate_version(predecessor),
        "proposed_successor_version_id": successor.id,
        "notice": (
            "Proposed, not decided. Somebody with approval authority — and "
            "not the author of the successor — has to agree before the "
            "current version is replaced."),
    }


@router.post("/candidate-versions/{version_id}/refuse-supersession",
             summary="Decline a supersession proposal")
async def refuse_supersession(
    version_id: int, request: SupersessionRefusalRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Refusing needs the same authority as accepting.

    A refusal is a decision about which formulation the organization stands
    behind, exactly as an acceptance is. Letting a lesser authority decline one
    would make any proposal killable by whoever disagreed with it first.
    """
    predecessor = await resolve_candidate_version(session, ctx, version_id)
    candidate = await resolve_candidate(session, ctx,
                                        predecessor.candidate_id)
    require_policy(ctx, Action.APPROVE, RecordFacts(
        organization_id=candidate.organization_id,
        study_id=candidate.study_id, owner_id=candidate.owner_id))

    try:
        await cvs.refuse_supersession(session, predecessor=predecessor,
                                      reason=request.reason,
                                      actor_id=user.id)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return _translate(exc)

    return {
        **serialize_candidate_version(predecessor),
        "notice": ("The proposal was declined. The predecessor is unchanged "
                   "and remains what the organization stands behind."),
    }
