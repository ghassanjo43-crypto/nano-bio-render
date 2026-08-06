"""Creating a record that depends on an exact candidate version.

What every function here does, in the same order, for the same reason
---------------------------------------------------------------------
1. **Refuse an inexact reference.** ``require_exact_version_id`` rejects
   ``None``, ``"latest"`` and everything else that means "work it out". A
   report generated against "latest" is a report whose subject depends on when
   it ran.
2. **Resolve the version.** One row, by id.
3. **Lock it**, through ``candidate_versioning.rely_on_version`` — the single
   authoritative boundary, in the caller's session.
4. **Write the audit event**, in the same session.
5. **Insert the dependent record**, in the same session.
6. **Return without committing.**

Step 6 is the one that carries the guarantee. The caller commits once, so all
of it lands or none of it does. There is no interleaving in which a simulation
result exists and its inputs are still editable, and none in which a version is
frozen for a report that was rolled back — which would leave a formulation
locked, unexplainable and uneditable, for a thing that never happened.

Why these live together rather than beside their features
---------------------------------------------------------
Because the invariant is about the *set*. Scattering them would mean the rule
"every dependency-creating operation locks" is enforced by six modules
agreeing, and a seventh feature added later agreeing by convention. Here it is
enforced by there being no other function that writes these tables.

What is deliberately NOT here
-----------------------------
Reading. Fetching a report, listing simulations and browsing a comparison on
screen create no reliance and lock nothing — looking at a formulation is not
depending on it. Only ``record_comparison``, which files a comparison as a
formal record, locks; the read-only compare endpoint does not.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.auth_models import UserRole
from nanobio_studio.app.db.candidate_dependency_models import (
    CandidateCROPackage, CandidateEvidenceAssessment, CandidateExport,
    CandidateReport, CandidateSimulation, CandidateVersionComparison,
    DependentResultState,
)
from nanobio_studio.app.db.validation_models import (
    Candidate, CandidateVersion, ResultsState,
)
from nanobio_studio.app.science.statuses import EvidenceLevel, ReadinessArea
from nanobio_studio.app.services import candidate_versioning as cvs
from nanobio_studio.app.validation.permissions import (
    Capability, PermissionDenied, RegistryActor,
)
from nanobio_studio.app.validation.vocabulary import (
    REGISTRY_VERSION, AuditEvent, EvidenceReuse, GeneratedArtifactFormat,
    SimulationKind,
)

__all__ = [
    "DependencyError",
    "record_simulation",
    "copy_simulation_forward",
    "record_evidence_assessment",
    "generate_report",
    "generate_export",
    "generate_cro_package",
    "record_comparison",
    "simulations_for_version",
    "reports_for_version",
    "exports_for_version",
    "packages_for_version",
    "evidence_for_version",
    "comparisons_for_candidate",
    "dependents_of_version",
    "DEPENDENCY_OPERATIONS",
]


class DependencyError(RuntimeError):
    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      default=str)


#: operation name -> the reliance key it locks under.
#:
#: Data rather than literals at the call sites, so a test can walk the set and
#: assert that each operation is reachable and locks. A boundary that exists
#: only as a string inside one function is a boundary nobody can enumerate.
DEPENDENCY_OPERATIONS: dict[str, str] = {
    "record_simulation": "simulation",
    "record_evidence_assessment": "evidence",
    "generate_report": "report",
    "generate_export": "export",
    "generate_cro_package": "package",
    "record_comparison": "comparison",
}


# ---------------------------------------------------------------------------
# Shared preamble
# ---------------------------------------------------------------------------

async def _resolve_and_rely(
    session: AsyncSession, *, candidate_version_id: Any, reason_key: str,
    actor: RegistryActor,
) -> tuple[CandidateVersion, Candidate]:
    """Steps 1–3, identically, for every operation below.

    Factored out rather than repeated because a copy of these three lines that
    forgets the third is exactly the defect this module exists to prevent, and
    a reviewer comparing six near-identical preambles will not spot it.
    """
    exact_id = cvs.require_exact_version_id(candidate_version_id)

    version = await session.get(CandidateVersion, exact_id)
    if version is None:
        raise DependencyError(
            "candidate_version_not_found",
            "The requested candidate version does not exist.")

    candidate = await session.get(Candidate, version.candidate_id)
    if candidate is None:
        raise DependencyError(
            "candidate_not_found",
            "The candidate this version belongs to does not exist.")

    await cvs.rely_on_version(session, version=version, reason_key=reason_key,
                              actor_id=actor.user_id)
    return version, candidate


def _refuse_administrative_only(actor: RegistryActor,
                                capability: Capability) -> None:
    """An administrative role alone is not scientific authority.

    Managing who has access and deciding what the organization stands behind
    are different jobs, and the separation is the same one the review workflow
    already maintains. Stated here as well as in the policy because these
    operations produce artefacts that leave the platform.
    """
    if actor.role is UserRole.VIEWER:
        raise PermissionDenied(
            capability,
            "Viewers may read scientific records and may not create them.")
    if actor.role is UserRole.ADMIN:
        raise PermissionDenied(
            capability,
            "Administrators manage access and do not author scientific "
            "records. Ask a researcher on this study.")


def _version_identity(version: CandidateVersion,
                      candidate: Candidate) -> dict[str, Any]:
    """The block every generated artefact carries.

    Candidate id, candidate code, exact version id, revision label, snapshot
    checksum and generation timestamp — the six facts that make an artefact
    identify what it is about. An export missing any of them describes an
    ambiguous material, and a CRO reading it has to guess.
    """
    return {
        "candidate_id": candidate.id,
        "candidate_code": candidate.code,
        "candidate_name": candidate.name,
        "candidate_version_id": version.id,
        "version_number": version.version_number,
        "revision_label": version.effective_label(),
        "snapshot_checksum": version.snapshot_checksum,
        "version_status": version.status.value,
        "results_state": version.results_state.value,
        "model_version": version.model_version,
        "ruleset_version": version.ruleset_version,
        "reference_data_version": version.reference_data_version,
        "generated_at": _utcnow().isoformat(),
        "registry_version": REGISTRY_VERSION,
    }


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

async def record_simulation(
    session: AsyncSession, *, actor: RegistryActor,
    candidate_version_id: Any, kind: SimulationKind, engine_version: str,
    inputs: dict[str, Any], result: dict[str, Any] | None,
    ruleset_version: str | None = None,
    failure_reason: str | None = None,
) -> CandidateSimulation:
    """Persist a simulation result against the exact version it describes.

    A failed run is stored too, with ``state = FAILED``, no result and the
    reason. Discarding it would leave the next reader unable to distinguish
    "nobody tried" from "the engine refused", and those lead to different
    decisions.

    Recording the result also marks the version's derived results CURRENT, but
    only for a successful run. A failure changes nothing about whether the
    previous numbers can be believed.
    """
    _refuse_administrative_only(actor, Capability.CREATE_EXPERIMENT)

    version, candidate = await _resolve_and_rely(
        session, candidate_version_id=candidate_version_id,
        reason_key="simulation", actor=actor)

    succeeded = result is not None
    simulation = CandidateSimulation(
        organization_id=version.organization_id,
        candidate_id=candidate.id,
        candidate_version_id=version.id,
        kind=kind,
        engine_version=engine_version,
        ruleset_version=ruleset_version,
        # The snapshot as it stood when the engine ran. Compared against the
        # version's current checksum by `verify_result_integrity`, so the
        # attribution is checkable rather than merely asserted by a key.
        inputs_checksum=version.snapshot_checksum,
        inputs_json=_canonical(inputs),
        result_json=_canonical(result) if succeeded else None,
        failure_reason=None if succeeded else (failure_reason or
                                               "the engine returned no result"),
        state=(DependentResultState.CURRENT if succeeded
               else DependentResultState.FAILED),
        created_by=actor.user_id,
        created_at=_utcnow(),
    )
    session.add(simulation)
    await session.flush()

    if succeeded:
        await cvs.record_recalculation(
            session, version=version, model_version=engine_version,
            ruleset_version=ruleset_version, actor_id=actor.user_id,
            reason=f"{kind.value} simulation recorded")

    await cvs.record_version_event(
        session, event=AuditEvent.SIMULATION_RECORDED, version=version,
        actor_id=actor.user_id,
        summary=(f"{kind.value} simulation #{simulation.id} recorded against "
                 f"{version.effective_label()} under engine {engine_version} "
                 f"({'result stored' if succeeded else 'no result: failure'})"))

    return simulation


async def copy_simulation_forward(
    session: AsyncSession, *, actor: RegistryActor,
    source: CandidateSimulation, target_version: CandidateVersion,
) -> CandidateSimulation:
    """Carry a predecessor's result into a revision, marked stale.

    The copy is ``COPIED_STALE`` and names both the row and the version it came
    from. Copying it as ``CURRENT`` would present numbers computed for one
    formulation as though they described another — which is the single most
    misleading thing this feature could do, and the reason the state exists.
    """
    copied = CandidateSimulation(
        organization_id=target_version.organization_id,
        candidate_id=target_version.candidate_id,
        candidate_version_id=target_version.id,
        kind=source.kind,
        engine_version=source.engine_version,
        ruleset_version=source.ruleset_version,
        # The SOURCE's checksum, deliberately. It records which formulation
        # produced these numbers; overwriting it with the target's would erase
        # the very mismatch that makes the copy stale.
        inputs_checksum=source.inputs_checksum,
        inputs_json=source.inputs_json,
        result_json=source.result_json,
        state=DependentResultState.COPIED_STALE,
        copied_from_simulation_id=source.id,
        source_candidate_version_id=source.candidate_version_id,
        created_by=actor.user_id,
        created_at=_utcnow(),
    )
    session.add(copied)
    await session.flush()
    return copied


# ---------------------------------------------------------------------------
# Evidence assessment
# ---------------------------------------------------------------------------

async def record_evidence_assessment(
    session: AsyncSession, *, actor: RegistryActor,
    candidate_version_id: Any, purpose: ReadinessArea,
    level: EvidenceLevel | None, reuse: EvidenceReuse, rationale: str,
    source_candidate_version_id: int | None = None,
    considered_experiment_version_ids: list[int] | None = None,
) -> CandidateEvidenceAssessment:
    """File how evidence for one purpose stands, for one exact version.

    ``reuse`` is required and unclassified is not an option. An assessment that
    carries a predecessor's experiment forward without saying so has
    re-attested it on nobody's authority — the experiment was performed on the
    old formulation and still was.
    """
    _refuse_administrative_only(actor, Capability.CREATE_EXPERIMENT)

    if not rationale or not rationale.strip():
        raise DependencyError(
            "rationale_required",
            "Say why the evidence stands where you are recording it. An "
            "assessment without a stated rationale is an assertion.")

    if (reuse is EvidenceReuse.RETAINED_REFERENCE
            and source_candidate_version_id is None):
        raise DependencyError(
            "retained_evidence_needs_a_source",
            "Retained evidence has to name the version it was gathered on.",
            "An experiment performed on an earlier revision remains an "
            "experiment performed on that revision. Recording it without its "
            "source would present it as work done on this one.")

    version, candidate = await _resolve_and_rely(
        session, candidate_version_id=candidate_version_id,
        reason_key="evidence", actor=actor)

    if (source_candidate_version_id is not None
            and source_candidate_version_id != version.id):
        source = await session.get(CandidateVersion,
                                   source_candidate_version_id)
        if source is None or source.candidate_id != candidate.id:
            raise DependencyError(
                "source_version_not_in_lineage",
                "The cited source version does not belong to this candidate.")

    # A later reading supersedes an earlier one rather than overwriting it, so
    # how the evidence was understood over time survives.
    previous = (await session.execute(
        select(CandidateEvidenceAssessment).where(
            CandidateEvidenceAssessment.candidate_version_id == version.id,
            CandidateEvidenceAssessment.purpose == purpose,
            CandidateEvidenceAssessment.superseded_by_id.is_(None))
    )).scalars().all()

    assessment = CandidateEvidenceAssessment(
        organization_id=version.organization_id,
        candidate_id=candidate.id,
        candidate_version_id=version.id,
        purpose=purpose,
        level=level,
        reuse=reuse,
        source_candidate_version_id=source_candidate_version_id,
        considered_experiment_version_ids=_canonical(
            sorted(considered_experiment_version_ids or [])),
        rationale=rationale.strip(),
        ruleset_version=REGISTRY_VERSION,
        assessed_by=actor.user_id,
        created_at=_utcnow(),
    )
    session.add(assessment)
    await session.flush()

    for earlier in previous:
        earlier.superseded_by_id = assessment.id
    if previous:
        await session.flush()

    await cvs.record_version_event(
        session, event=AuditEvent.EVIDENCE_ASSESSED, version=version,
        actor_id=actor.user_id, reason=rationale,
        summary=(f"{purpose.value} assessed as "
                 f"{level.value if level else 'no level held'} on "
                 f"{version.effective_label()}, classified {reuse.value}"))

    return assessment


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

async def generate_report(
    session: AsyncSession, *, actor: RegistryActor,
    candidate_version_id: Any, title: str, body: dict[str, Any],
    format: GeneratedArtifactFormat = GeneratedArtifactFormat.JSON,
) -> CandidateReport:
    """Freeze a report against the version it was generated from.

    The content is stored, not re-rendered on read. Reopening a historical
    report has to show what it said when it was issued; regenerating it from
    current data would answer a different question under the same title, and
    the reader has no way to tell.
    """
    _refuse_administrative_only(actor, Capability.CREATE_EXPERIMENT)

    version, candidate = await _resolve_and_rely(
        session, candidate_version_id=candidate_version_id,
        reason_key="report", actor=actor)

    content = {
        "identity": _version_identity(version, candidate),
        "design_snapshot": json.loads(version.design_snapshot_json or "{}"),
        "body": body,
        # Stated in the document, not left to the interface. A report whose
        # numbers were inherited from a predecessor must say so on its face,
        # because the file is read outside the application that knows.
        "results_qualification": _results_qualification(version),
    }
    payload = _canonical(content)

    report = CandidateReport(
        organization_id=version.organization_id,
        candidate_id=candidate.id,
        candidate_version_id=version.id,
        title=title,
        version_label=version.effective_label(),
        version_checksum=version.snapshot_checksum,
        content_json=payload,
        content_checksum=_checksum(payload),
        format=format,
        generated_by=actor.user_id,
        generated_at=_utcnow(),
    )
    session.add(report)
    await session.flush()

    await cvs.record_version_event(
        session, event=AuditEvent.REPORT_GENERATED, version=version,
        actor_id=actor.user_id,
        summary=(f"report #{report.id} generated from "
                 f"{version.effective_label()} "
                 f"(checksum {report.content_checksum[:12]})"))

    return report


def _results_qualification(version: CandidateVersion) -> dict[str, Any]:
    """What the document must say about the numbers it carries."""
    stale = version.results_state is ResultsState.STALE
    return {
        "results_state": version.results_state.value,
        "inherited_from_version_id": version.results_inherited_from_id,
        "safe_to_cite": version.results_state is ResultsState.CURRENT,
        "statement": (
            "These results were computed for an earlier revision of this "
            "candidate and have not been recalculated for the version named "
            "above. They must not be cited as describing it."
            if stale else
            "These results were computed for the version named above, under "
            "the model and ruleset recorded in the identity block."
            if version.results_state is ResultsState.CURRENT else
            "No derived results have been computed for this version."),
    }


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

async def generate_export(
    session: AsyncSession, *, actor: RegistryActor,
    candidate_version_id: Any,
    format: GeneratedArtifactFormat = GeneratedArtifactFormat.JSON,
    purpose_note: str | None = None,
    payload: dict[str, Any] | None = None,
) -> CandidateExport:
    """Produce an export whose manifest identifies exactly what it contains."""
    _refuse_administrative_only(actor, Capability.CREATE_EXPERIMENT)

    version, candidate = await _resolve_and_rely(
        session, candidate_version_id=candidate_version_id,
        reason_key="export", actor=actor)

    manifest = {
        **_version_identity(version, candidate),
        "export_format": format.value,
        "purpose_note": purpose_note,
        "results_qualification": _results_qualification(version),
        "design_snapshot": json.loads(version.design_snapshot_json or "{}"),
        "payload": payload or {},
    }
    body = _canonical(manifest)

    export = CandidateExport(
        organization_id=version.organization_id,
        candidate_id=candidate.id,
        candidate_version_id=version.id,
        version_label=version.effective_label(),
        version_checksum=version.snapshot_checksum,
        format=format,
        manifest_json=body,
        content_checksum=_checksum(body),
        purpose_note=purpose_note,
        generated_by=actor.user_id,
        generated_at=_utcnow(),
    )
    session.add(export)
    await session.flush()

    await cvs.record_version_event(
        session, event=AuditEvent.EXPORT_GENERATED, version=version,
        actor_id=actor.user_id, reason=purpose_note,
        summary=(f"export #{export.id} generated from "
                 f"{version.effective_label()} as {format.value}"))

    return export


# ---------------------------------------------------------------------------
# CRO package
# ---------------------------------------------------------------------------

async def generate_cro_package(
    session: AsyncSession, *, actor: RegistryActor,
    candidate_version_id: Any, recipient_name: str,
    package_code: str, quotation_reference: str | None = None,
    scope_note: str | None = None,
) -> CandidateCROPackage:
    """Prepare a package for an external laboratory.

    The most consequential artefact in this module: somebody outside the
    organization is going to make or test whatever it describes. So the
    manifest names the exact version and its checksum, and a package cannot be
    produced from a version whose results are stale without that being stated
    inside the document.
    """
    _refuse_administrative_only(actor, Capability.CREATE_EXPERIMENT)

    if not recipient_name or not recipient_name.strip():
        raise DependencyError(
            "recipient_required",
            "Name the laboratory this package is for. A package with no "
            "recipient cannot be traced to what was sent where.")

    version, candidate = await _resolve_and_rely(
        session, candidate_version_id=candidate_version_id,
        reason_key="package", actor=actor)

    manifest = {
        **_version_identity(version, candidate),
        "recipient": recipient_name.strip(),
        "quotation_reference": quotation_reference,
        "scope_note": scope_note,
        "results_qualification": _results_qualification(version),
        "design_snapshot": json.loads(version.design_snapshot_json or "{}"),
        "instruction": (
            "Synthesise and test the formulation described by the design "
            "snapshot in this manifest. It is identified by candidate code, "
            "exact version id and snapshot checksum; if any of the three "
            "disagrees with what you were told separately, stop and ask."),
    }
    body = _canonical(manifest)

    package = CandidateCROPackage(
        organization_id=version.organization_id,
        candidate_id=candidate.id,
        candidate_version_id=version.id,
        package_code=package_code,
        version_label=version.effective_label(),
        version_checksum=version.snapshot_checksum,
        recipient_name=recipient_name.strip(),
        quotation_reference=quotation_reference,
        manifest_json=body,
        content_checksum=_checksum(body),
        generated_by=actor.user_id,
        generated_at=_utcnow(),
    )
    session.add(package)
    await session.flush()

    await cvs.record_version_event(
        session, event=AuditEvent.PACKAGE_GENERATED, version=version,
        actor_id=actor.user_id, reason=scope_note,
        summary=(f"CRO package {package_code} generated from "
                 f"{version.effective_label()} for an external laboratory"))

    return package


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

async def record_comparison(
    session: AsyncSession, *, actor: RegistryActor,
    left_version_id: Any, right_version_id: Any, note: str | None = None,
) -> CandidateVersionComparison:
    """File a comparison as a formal record, locking both sides.

    Browsing a comparison locks nothing — looking at two formulations is not
    depending on either. Filing one says "this comparison is the basis of what
    happens next", and from that point neither side may move underneath it.
    """
    _refuse_administrative_only(actor, Capability.CREATE_EXPERIMENT)

    left_id = cvs.require_exact_version_id(left_version_id)
    right_id = cvs.require_exact_version_id(right_version_id)
    if left_id == right_id:
        raise DependencyError(
            "identical_versions",
            "A version compared with itself has nothing to report.")

    left, candidate = await _resolve_and_rely(
        session, candidate_version_id=left_id, reason_key="comparison",
        actor=actor)
    right, _right_candidate = await _resolve_and_rely(
        session, candidate_version_id=right_id, reason_key="comparison",
        actor=actor)

    if left.candidate_id != right.candidate_id:
        raise DependencyError(
            "different_candidates",
            "Those versions belong to different candidates and are not "
            "comparable. One formulation does not revise another.")

    changes = cvs.compare_snapshots(left.design_snapshot_json,
                                    right.design_snapshot_json)
    consequence = cvs.consequence_of_change({c.field for c in changes})

    comparison = CandidateVersionComparison(
        organization_id=left.organization_id,
        candidate_id=candidate.id,
        left_version_id=left.id,
        right_version_id=right.id,
        changed_fields_json=_canonical([
            {"field": c.field, "before": c.before, "after": c.after,
             "kind": c.kind, "scientific": c.is_scientific}
            for c in changes
        ]),
        consequence_json=_canonical(consequence),
        material_classification=consequence["requires"],
        note=note,
        created_by=actor.user_id,
        created_at=_utcnow(),
    )
    session.add(comparison)
    await session.flush()

    for side in (left, right):
        await cvs.record_version_event(
            session, event=AuditEvent.COMPARISON_RECORDED, version=side,
            actor_id=actor.user_id, reason=note,
            summary=(f"comparison #{comparison.id} recorded between "
                     f"{left.effective_label()} and {right.effective_label()}; "
                     f"requires {consequence['requires']}"))

    return comparison


# ---------------------------------------------------------------------------
# Reads. These lock nothing.
# ---------------------------------------------------------------------------

async def simulations_for_version(session: AsyncSession, version_id: int
                                  ) -> list[CandidateSimulation]:
    return list((await session.execute(
        select(CandidateSimulation)
        .where(CandidateSimulation.candidate_version_id == version_id)
        .order_by(CandidateSimulation.created_at.desc(),
                  CandidateSimulation.id.desc()))).scalars().all())


async def reports_for_version(session: AsyncSession, version_id: int
                              ) -> list[CandidateReport]:
    return list((await session.execute(
        select(CandidateReport)
        .where(CandidateReport.candidate_version_id == version_id)
        .order_by(CandidateReport.generated_at.desc(),
                  CandidateReport.id.desc()))).scalars().all())


async def exports_for_version(session: AsyncSession, version_id: int
                              ) -> list[CandidateExport]:
    return list((await session.execute(
        select(CandidateExport)
        .where(CandidateExport.candidate_version_id == version_id)
        .order_by(CandidateExport.generated_at.desc(),
                  CandidateExport.id.desc()))).scalars().all())


async def packages_for_version(session: AsyncSession, version_id: int
                               ) -> list[CandidateCROPackage]:
    return list((await session.execute(
        select(CandidateCROPackage)
        .where(CandidateCROPackage.candidate_version_id == version_id)
        .order_by(CandidateCROPackage.generated_at.desc(),
                  CandidateCROPackage.id.desc()))).scalars().all())


async def evidence_for_version(session: AsyncSession, version_id: int,
                               *, include_superseded: bool = False
                               ) -> list[CandidateEvidenceAssessment]:
    query = (select(CandidateEvidenceAssessment)
             .where(CandidateEvidenceAssessment.candidate_version_id
                    == version_id))
    if not include_superseded:
        query = query.where(
            CandidateEvidenceAssessment.superseded_by_id.is_(None))
    return list((await session.execute(
        query.order_by(CandidateEvidenceAssessment.purpose,
                       CandidateEvidenceAssessment.id))).scalars().all())


async def comparisons_for_candidate(session: AsyncSession, candidate_id: int
                                    ) -> list[CandidateVersionComparison]:
    return list((await session.execute(
        select(CandidateVersionComparison)
        .where(CandidateVersionComparison.candidate_id == candidate_id)
        .order_by(CandidateVersionComparison.created_at.desc(),
                  CandidateVersionComparison.id.desc()))).scalars().all())


async def dependents_of_version(session: AsyncSession, version_id: int
                                ) -> dict[str, int]:
    """How many records depend on this version, by kind.

    Used by the interface to explain a lock in the terms the person reading it
    cares about — "two simulations and a report depend on this" is an answer;
    "locked" is not.
    """
    from nanobio_studio.app.db.validation_models import (
        ExperimentAttachment, ExperimentVersion,
    )
    from sqlalchemy import func

    async def count(model, column) -> int:
        return int((await session.execute(
            select(func.count()).select_from(model)
            .where(column == version_id))).scalar() or 0)

    comparisons = int((await session.execute(
        select(func.count()).select_from(CandidateVersionComparison)
        .where((CandidateVersionComparison.left_version_id == version_id)
               | (CandidateVersionComparison.right_version_id == version_id))
    )).scalar() or 0)

    return {
        "experiments": await count(ExperimentVersion,
                                   ExperimentVersion.candidate_version_id),
        "attachments": await count(ExperimentAttachment,
                                   ExperimentAttachment.candidate_version_id),
        "simulations": await count(CandidateSimulation,
                                   CandidateSimulation.candidate_version_id),
        "evidence_assessments": await count(
            CandidateEvidenceAssessment,
            CandidateEvidenceAssessment.candidate_version_id),
        "reports": await count(CandidateReport,
                               CandidateReport.candidate_version_id),
        "exports": await count(CandidateExport,
                               CandidateExport.candidate_version_id),
        "cro_packages": await count(CandidateCROPackage,
                                    CandidateCROPackage.candidate_version_id),
        "comparisons": comparisons,
    }
