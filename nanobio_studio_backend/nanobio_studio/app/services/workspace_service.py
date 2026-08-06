"""Storage and retrieval of runs and projects.

This module stores and returns records. It performs **no scientific
calculation** and never derives a value: results arrive already computed by the
connected engines and are written verbatim.

Two invariants it enforces:

1. **A result cannot be stored without the inputs that produced it.** Storing an
   orphan result would create a record that cannot be reproduced or audited.
2. **A run's engine list reflects what actually ran.** ``engines_run`` is derived
   from which result payloads are present, not from what the caller claims.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.organizations.policy import (
    AccessContext, RecordNotVisible, visible_organization_ids,
)
from nanobio_studio.app.organizations.scoping import (
    scoped, scoped_runs, visible_project_ids,
)
from nanobio_studio.app.db.workspace_models import (
    Project,
    RecordOrigin,
    RunStatus,
    StoredRun,
    StudyPathway,
)

__all__ = [
    "WorkspaceError",
    "DESIGN_ENGINE_NAME",
    "PK_ENGINE_NAME",
    "create_run",
    "list_runs",
    "get_run",
    "delete_run",
    "create_project",
    "list_projects",
    "delete_project",
    "assign_run_to_project",
    "run_to_summary",
    "run_to_detail",
    "build_comparison_rows",
]

DESIGN_ENGINE_NAME = "Design impact score (core.scoring.compute_impact)"
PK_ENGINE_NAME = "Pharmacokinetic simulation (utils.pk_model)"


class WorkspaceError(RuntimeError):
    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def _dumps(value: Any | None) -> str | None:
    return None if value is None else json.dumps(value)


def _loads(value: str | None) -> Any | None:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        # A record we cannot parse is reported as absent rather than guessed at.
        return None


def _lines(value: str) -> list[str]:
    return [line for line in (value or "").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


async def _authorized_project(
    session: AsyncSession, *, access: "AccessContext | None", owner_id: int,
    project_id: int,
) -> Project:
    """Resolve a project the caller may use as a parent, or refuse.

    This is the parent-injection guard. A caller may legitimately own study A
    and pass project B belonging to another organization, hoping the write
    lands with the foreign parent attached; resolving the parent through the
    same predicate that governs reads makes that impossible.

    The organization is taken from the stored parent row. A client-supplied
    ``organization_id`` is never read — there is deliberately no parameter for
    one anywhere in this service.
    """
    if access is not None:
        project = (await session.execute(
            scoped(select(Project), Project, access)
            .where(Project.id == project_id).limit(1)
        )).scalars().first()
        if project is None:
            raise RecordNotVisible("project")
        return project

    project = await session.get(Project, project_id)
    if project is None or project.owner_id != owner_id:
        raise WorkspaceError("project_not_found",
                             "The requested project does not exist.")
    return project


async def create_run(
    session: AsyncSession,
    *,
    owner_id: int,
    name: str,
    disease: str | None,
    subtype: str | None,
    drug: str | None,
    design_inputs: dict | None,
    pk_inputs: dict | None,
    design_result: dict | None,
    pk_result: dict | None,
    engines_not_run: Sequence[dict],
    project_id: int | None,
    is_demo: bool,
    demo_scenario_slug: str | None,
    demo_fixture_version: str | None,
    pathway: StudyPathway = StudyPathway.RESEARCH_DESIGN,
    research_purpose: str | None = None,
    report_assessment_id: int | None = None,
    access: "AccessContext | None" = None,
    organization_id: int | None = None,
) -> StoredRun:
    """Persist a run exactly as the engines produced it."""
    # Invariant 1: a result without its inputs is not reproducible.
    if design_result is not None and design_inputs is None:
        raise WorkspaceError(
            "inputs_required",
            "A design result cannot be stored without the design inputs that "
            "produced it.",
            "Storing an orphan result would create an unreproducible record.")
    if pk_result is not None and pk_inputs is None:
        raise WorkspaceError(
            "inputs_required",
            "A pharmacokinetic result cannot be stored without the inputs that "
            "produced it.",
            "Storing an orphan result would create an unreproducible record.")

    parent_project: Project | None = None
    if project_id is not None:
        parent_project = await _authorized_project(
            session, access=access, owner_id=owner_id,
            project_id=project_id)
        # The child inherits the *stored parent's* organization, so a
        # mismatched pairing cannot survive even if one were requested.
        organization_id = parent_project.organization_id
    elif organization_id is None and access is not None:
        # No parent to inherit from: fall back to the single organization
        # the caller is acting within. Ambiguity is refused rather than
        # guessed, because guessing would file the study in the wrong
        # workspace and nothing downstream would notice.
        candidates = visible_organization_ids(access)
        if len(candidates) == 1:
            organization_id = next(iter(candidates))
        elif not candidates:
            raise WorkspaceError(
                "no_organization",
                "You are not a member of any organization.")
        else:
            raise WorkspaceError(
                "organization_required",
                "You belong to several organizations. Select one before "
                "creating a study.")

    # A study begun from a patient assessment carries a reference to it. That
    # reference is a parent link like any other, and until it was checked it
    # was the one place a client-supplied identifier crossed the boundary: a
    # user who legitimately belongs to two organizations could attach one
    # organization's assessment to the other's study, and the study detail
    # would then carry a pointer into a tenant it has nothing to do with.
    #
    # Belonging to both organizations is exactly the case this refuses. Access
    # to two organizations is not permission to link their records together.
    if report_assessment_id is not None and access is not None:
        from nanobio_studio.app.db.report_models import ReportAssessment

        assessment = (await session.execute(
            select(ReportAssessment).where(
                ReportAssessment.id == report_assessment_id,
                ReportAssessment.organization_id.in_(
                    visible_organization_ids(access)),
            ).limit(1)
        )).scalars().first()

        # 404 rather than a validation message: an assessment the caller
        # cannot see must look absent, and one they can see but which belongs
        # to their *other* organization must look the same as one that never
        # existed.
        if assessment is None or assessment.owner_id != owner_id:
            raise RecordNotVisible("assessment")
        if (organization_id is not None
                and assessment.organization_id != organization_id):
            raise RecordNotVisible("assessment")
        if organization_id is None:
            organization_id = assessment.organization_id

    # Invariant 2: engines_run is derived from what is actually present.
    engines_run: list[str] = []
    if design_result is not None:
        engines_run.append(DESIGN_ENGINE_NAME)
    if pk_result is not None:
        engines_run.append(PK_ENGINE_NAME)

    if not engines_run:
        status = RunStatus.BLOCKED
    elif len(engines_run) == 2:
        status = RunStatus.COMPLETE
    else:
        status = RunStatus.PARTIAL

    # `origin` stays the two-value demo/user flag the reset command scopes on;
    # `pathway` carries the richer fact. Deriving one from the other keeps them
    # consistent without overloading either.
    if pathway is StudyPathway.DEMO_SCENARIO:
        is_demo = True

    run = StoredRun(
        # Taken from the resolved parent or the caller's organization,
        # never from the request body.
        organization_id=organization_id,
        owner_id=owner_id,
        project_id=project_id,
        name=name,
        origin=RecordOrigin.DEMO if is_demo else RecordOrigin.USER,
        pathway=pathway,
        research_purpose=research_purpose,
        inputs_are_synthetic=is_demo,
        report_assessment_id=report_assessment_id,
        demo_scenario_slug=demo_scenario_slug if is_demo else None,
        demo_fixture_version=demo_fixture_version if is_demo else None,
        disease=disease,
        subtype=subtype,
        drug=drug,
        status=status,
        design_inputs_json=_dumps(design_inputs),
        pk_inputs_json=_dumps(pk_inputs),
        design_result_json=_dumps(design_result),
        pk_result_json=_dumps(pk_result),
        design_score_version=(design_result or {}).get("score_version"),
        pk_calculation_version=(pk_result or {}).get("calculation_version"),
        engines_run="\n".join(engines_run),
        engines_not_run="\n".join(
            f"{item['engine']}\t{item['reason']}" for item in engines_not_run),
    )
    session.add(run)
    await session.flush()
    return run


async def list_runs(
    session: AsyncSession,
    *,
    owner_id: int,
    origin: RecordOrigin | None = None,
    pathway: StudyPathway | None = None,
    disease: str | None = None,
    scenario_slug: str | None = None,
    status: RunStatus | None = None,
    project_id: int | None = None,
    limit: int = 100,
    access: "AccessContext | None" = None,
) -> tuple[list[StoredRun], int]:
    # The count is scoped by the same predicate as the list. A total that
    # counted rows the list cannot show would disclose how much work
    # another organization holds — an aggregate is a leak too.
    if access is not None:
        stmt = await scoped_runs(session, access)
        count_stmt = await scoped_runs(
            session, access,
            select(func.count()).select_from(StoredRun))
    else:
        stmt = select(StoredRun).where(StoredRun.owner_id == owner_id)
        count_stmt = (select(func.count()).select_from(StoredRun)
                      .where(StoredRun.owner_id == owner_id))

    for condition in (
        (StoredRun.origin == origin) if origin is not None else None,
        (StoredRun.pathway == pathway) if pathway is not None else None,
        (StoredRun.disease == disease) if disease else None,
        (StoredRun.demo_scenario_slug == scenario_slug) if scenario_slug else None,
        (StoredRun.status == status) if status is not None else None,
        (StoredRun.project_id == project_id) if project_id is not None else None,
    ):
        if condition is not None:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

    stmt = stmt.order_by(StoredRun.created_at.desc(), StoredRun.id.desc()).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())
    total = int((await session.execute(count_stmt)).scalar_one())
    return rows, total


async def get_run(session: AsyncSession, *, owner_id: int,
                  run_id: int,
                  access: "AccessContext | None" = None) -> StoredRun:
    """Resolve one study, or refuse without revealing whether it exists.

    With an access context the predicate is applied in SQL, so a study in
    another organization is never loaded. Without one the historical
    ownership check applies, which is what the workspace unit tests use.
    """
    if access is not None:
        query = await scoped_runs(session, access)
        run = (await session.execute(
            query.where(StoredRun.id == run_id).limit(1))).scalars().first()
        if run is None:
            raise RecordNotVisible("run")
        return run

    run = await session.get(StoredRun, run_id)
    # Ownership is checked before existence is revealed, so this endpoint cannot
    # be used to probe for other users' record ids.
    if run is None or run.owner_id != owner_id:
        raise WorkspaceError("run_not_found", "The requested run does not exist.")
    return run


async def delete_run(session: AsyncSession, *, owner_id: int,
                     run_id: int,
                     access: "AccessContext | None" = None) -> StoredRun:
    run = await get_run(session, owner_id=owner_id, run_id=run_id,
                        access=access)
    await session.delete(run)
    await session.flush()
    return run


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


async def create_project(session: AsyncSession, *, owner_id: int, name: str,
                         description: str | None, is_demo: bool,
                         access: "AccessContext | None" = None,
                         organization_id: int | None = None) -> Project:
    if organization_id is None and access is not None:
        candidates = visible_organization_ids(access)
        if len(candidates) == 1:
            organization_id = next(iter(candidates))
        elif not candidates:
            raise WorkspaceError(
                "no_organization",
                "You are not a member of any organization.")
        else:
            raise WorkspaceError(
                "organization_required",
                "You belong to several organizations. Select one before "
                "creating a project.")
    project = Project(
        organization_id=organization_id,
        owner_id=owner_id,
        name=name,
        description=description,
        origin=RecordOrigin.DEMO if is_demo else RecordOrigin.USER,
    )
    session.add(project)
    await session.flush()
    return project


async def list_projects(
    session: AsyncSession, *, owner_id: int,
    access: "AccessContext | None" = None,
) -> list[tuple[Project, int]]:
    stmt = (select(Project, func.count(StoredRun.id))
            .outerjoin(StoredRun, StoredRun.project_id == Project.id))
    if access is not None:
        stmt = scoped(stmt, Project, access)
        project_ids = await visible_project_ids(session, access)
        if project_ids is not None:
            stmt = stmt.where(Project.id.in_(project_ids))
    else:
        stmt = stmt.where(Project.owner_id == owner_id)
    stmt = (stmt
            .group_by(Project.id)
            .order_by(Project.updated_at.desc()))
    return [(project, int(count))
            for project, count in (await session.execute(stmt)).all()]


async def delete_project(session: AsyncSession, *, owner_id: int,
                         project_id: int,
                         access: "AccessContext | None" = None) -> Project:
    project = await _authorized_project(
        session, access=access, owner_id=owner_id, project_id=project_id)
    # Runs survive; their project_id is nulled by the FK's ON DELETE SET NULL.
    # Deleting a grouping must never destroy calculated records.
    await session.delete(project)
    await session.flush()
    return project


async def assign_run_to_project(session: AsyncSession, *, owner_id: int,
                                run_id: int,
                                project_id: int | None,
                                access: "AccessContext | None" = None,
                                ) -> StoredRun:
    """Move a study between projects, refusing a cross-organization pairing.

    Both sides are resolved through the scoped predicate before anything is
    written. Re-parenting a study into another organization's project would
    otherwise be a one-request way to hand a record across the boundary.
    """
    run = await get_run(session, owner_id=owner_id, run_id=run_id,
                        access=access)
    if project_id is not None:
        project = await _authorized_project(
            session, access=access, owner_id=owner_id,
            project_id=project_id)
        if (project.organization_id is not None
                and run.organization_id is not None
                and project.organization_id != run.organization_id):
            raise RecordNotVisible("project")
    run.project_id = project_id
    await session.flush()
    return run


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def run_to_summary(run: StoredRun) -> dict:
    return {
        "id": run.id,
        "name": run.name,
        "origin": run.origin.value,
        "pathway": run.pathway.value,
        "research_purpose": run.research_purpose,
        "inputs_are_synthetic": run.inputs_are_synthetic,
        "report_assessment_id": run.report_assessment_id,
        "demo_scenario_slug": run.demo_scenario_slug,
        "disease": run.disease,
        "subtype": run.subtype,
        "drug": run.drug,
        "status": run.status.value,
        "engines_run": _lines(run.engines_run),
        "has_design_result": run.design_result_json is not None,
        "has_pk_result": run.pk_result_json is not None,
        "design_score_version": run.design_score_version,
        "pk_calculation_version": run.pk_calculation_version,
        "project_id": run.project_id,
        "created_at": run.created_at,
    }


def run_to_detail(run: StoredRun) -> dict:
    not_run = []
    for line in _lines(run.engines_not_run):
        engine, _, reason = line.partition("\t")
        not_run.append({"engine": engine, "reason": reason})

    return {
        **run_to_summary(run),
        "design_inputs": _loads(run.design_inputs_json),
        "pk_inputs": _loads(run.pk_inputs_json),
        "design_result": _loads(run.design_result_json),
        "pk_result": _loads(run.pk_result_json),
        "engines_not_run": not_run,
        "demo_fixture_version": run.demo_fixture_version,
    }


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

#: Rows of the comparison table. Each entry names where the value is read from
#: in the stored engine response. Nothing is recomputed, rescaled or combined.
_COMPARISON_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("Indication", "context", "disease"),
    ("Subtype", "context", "subtype"),
    ("Therapeutic agent", "context", "drug"),
    ("Origin", "context", "origin"),
    ("Particle size (nm)", "design_input", "size_nm"),
    ("Surface charge (mV)", "design_input", "charge_mv"),
    ("Encapsulation (%)", "design_input", "encapsulation_percent"),
    ("Polydispersity index", "design_input", "pdi"),
    ("Targeting ligand", "design_input", "ligand"),
    ("Delivery (0-100, higher better)", "design_score", "delivery"),
    ("Toxicity (0-10, lower better)", "design_score", "toxicity"),
    ("Cost (0-100, lower better)", "design_score", "cost"),
    ("Design score version", "design_meta", "score_version"),
    ("Design validation status", "design_meta", "validation_status"),
    ("Dose (mg/kg)", "pk_input", "dose_mg_kg"),
    ("k_el (per h)", "pk_input", "kel_per_h"),
    ("Peak amount, central", "pk_param", "peak_concentration_central"),
    ("Time to peak, central (h)", "pk_param", "time_to_peak_central_h"),
    ("AUC, central", "pk_param", "auc_central"),
    ("Terminal half-life (h)", "pk_param", "half_life_central_h"),
    ("Tissue accumulation ratio", "pk_param", "tissue_accumulation_ratio"),
    ("PK calculation version", "pk_meta", "calculation_version"),
    ("PK validation status", "pk_meta", "validation_status"),
)


def build_comparison_rows(details: Sequence[dict]) -> list[dict]:
    """Align stored runs field by field.

    Every value is copied verbatim from a stored engine response. A value that a
    run does not have is reported as ``None`` and rendered as "not available" —
    never as zero, and never substituted from another run.
    """
    rows: list[dict] = []

    for label, source, key in _COMPARISON_FIELDS:
        values: list[Any] = []
        for detail in details:
            values.append(_extract(detail, source, key))

        # A row where no run has a value carries no information; omitting it
        # keeps the table honest rather than padding it with blanks.
        if all(v is None for v in values):
            continue

        rows.append({
            "label": label,
            "source": source,
            "key": key,
            "values": values,
            "unit_note": _UNIT_NOTES.get(source),
        })

    return rows


_UNIT_NOTES: dict[str, str] = {
    "pk_param": ("Dose-scaled compartment amount in arbitrary units; AUC in "
                 "amount x hours. Not a concentration."),
}


def _extract(detail: dict, source: str, key: str) -> Any:
    if source == "context":
        return detail.get(key)
    if source == "design_input":
        return (detail.get("design_inputs") or {}).get(key)
    if source == "pk_input":
        return (detail.get("pk_inputs") or {}).get(key)
    if source == "design_score":
        result = detail.get("design_result") or {}
        return (result.get("design_impact_score") or {}).get(key)
    if source == "design_meta":
        return (detail.get("design_result") or {}).get(key)
    if source == "pk_param":
        result = detail.get("pk_result") or {}
        return (result.get("pk_parameters") or {}).get(key)
    if source == "pk_meta":
        return (detail.get("pk_result") or {}).get(key)
    return None
