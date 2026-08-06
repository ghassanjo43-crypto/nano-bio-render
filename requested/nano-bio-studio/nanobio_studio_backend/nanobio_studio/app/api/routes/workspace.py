"""Demo workspace, stored runs, projects and comparison routes.

Transport only. No scientific calculation happens in this module: results
arrive already computed by the connected engines (`/design/score`, `/pk/simulate`)
and are stored and returned verbatim.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.api.deps_auth import get_current_user
from nanobio_studio.app.db.auth_models import User, UserRole
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.db.workspace_models import (
    RecordOrigin,
    RunStatus,
    StudyPathway,
)
from nanobio_studio.app.demo.scenarios import (
    DEMO_FIXTURE_VERSION,
    SCENARIOS,
    scenario_by_slug,
)
from nanobio_studio.app.demo.seeding import reset_demo_data, seed_demo_templates
from nanobio_studio.app.schemas.workspace import (
    ComparisonResponse,
    DemoResetRequest,
    DemoResetResponse,
    DemoScenarioDetail,
    DemoScenarioListResponse,
    DemoSeedResponse,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectSummary,
    RunCreateRequest,
    RunDetail,
    RunListResponse,
    WorkspaceErrorResponse,
)
from nanobio_studio.app.services import workspace_service as svc

router = APIRouter(prefix="/api/v1", tags=["workspace"])

#: Restated on every scenario listing so the classification travels with the
#: data rather than living only in the UI.
DEMO_NOTICE = (
    "Synthetic demonstration inputs. These scenarios are not patient data, not "
    "clinical data, not validated experimental data, not treatment "
    "recommendations, and not known-successful formulations. They contain no "
    "stored scientific results: every score, profile and chart is calculated at "
    "runtime by the genuine connected engines."
)

_REQUIRED_DESIGN = ("size_nm", "charge_mv", "encapsulation_percent")
_REQUIRED_PK = ("dose_mg_kg", "kabs_per_h", "kel_per_h", "k12_per_h", "k21_per_h")


def _error(code: str, message: str, http: int,
           detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=http,
        content=WorkspaceErrorResponse(error=code, message=message,
                                       detail=detail,
                                       data_available=False).model_dump(),
    )


# ===========================================================================
# Demo scenarios
# ===========================================================================


def _summary(scenario) -> dict:
    return {
        "slug": scenario.slug,
        "name": scenario.name,
        "purpose": scenario.purpose,
        "disease": scenario.disease,
        "subtype": scenario.subtype,
        "drug": scenario.drug,
        "technical": scenario.technical,
        "score_runnable": scenario.is_score_runnable,
        "pk_runnable": scenario.is_pk_runnable,
        "engines_expected_to_run": list(scenario.engines_expected_to_run),
        "engine_count_not_running": len(scenario.engines_that_will_not_run),
        "fixture_version": DEMO_FIXTURE_VERSION,
    }


@router.get(
    "/demo/scenarios",
    response_model=DemoScenarioListResponse,
    summary="List demonstration scenarios",
    description=(
        "Returns the versioned demonstration-scenario set. Scenarios carry "
        "**inputs and teaching metadata only** — no stored scientific results. "
        "Loading one populates the ordinary workflow; nothing is calculated "
        "until the user deliberately runs it."
    ),
)
async def list_scenarios(_user: User = Depends(get_current_user)):
    return {
        "fixture_version": DEMO_FIXTURE_VERSION,
        "scenarios": [_summary(s) for s in SCENARIOS],
        "notice": DEMO_NOTICE,
    }


@router.get(
    "/demo/scenarios/{slug}",
    response_model=DemoScenarioDetail,
    responses={404: {"model": WorkspaceErrorResponse}},
    summary="Preview one demonstration scenario before loading it",
)
async def get_scenario(slug: str, _user: User = Depends(get_current_user)):
    scenario = scenario_by_slug(slug)
    if scenario is None:
        return _error("scenario_not_found",
                      f"No demonstration scenario named {slug!r}.",
                      status.HTTP_404_NOT_FOUND)

    missing_design = [k for k in _REQUIRED_DESIGN
                      if scenario.design_inputs.get(k) is None]
    missing_pk = [k for k in _REQUIRED_PK
                  if scenario.pk_inputs.get(k) is None]

    return {
        **_summary(scenario),
        "design_inputs": dict(scenario.design_inputs),
        "pk_inputs": dict(scenario.pk_inputs),
        "assumptions": list(scenario.assumptions),
        "expected_warnings": list(scenario.expected_warnings),
        "engines_that_will_not_run": [
            {"engine": engine, "reason": reason}
            for engine, reason in scenario.engines_that_will_not_run
        ],
        "provenance": list(scenario.provenance),
        "missing_required_design_inputs": missing_design,
        "missing_required_pk_inputs": missing_pk,
    }


@router.post(
    "/demo/seed",
    response_model=DemoSeedResponse,
    responses={403: {"model": WorkspaceErrorResponse}},
    summary="Install or refresh the demonstration templates (idempotent)",
    description=(
        "Keyed on scenario slug, so running it twice updates in place and never "
        "creates duplicates. Admin only."
    ),
)
async def seed_demo(user: User = Depends(get_current_user),
                    session: AsyncSession = Depends(get_auth_session)):
    if user.role is not UserRole.ADMIN:
        return _error("forbidden", "Seeding demonstration data requires an "
                                   "administrator account.",
                      status.HTTP_403_FORBIDDEN)
    report = await seed_demo_templates(session)
    return report.as_dict()


@router.post(
    "/demo/reset",
    response_model=DemoResetResponse,
    summary="Remove demo-generated records only",
    description=(
        "Without `confirm`, reports the exact scope and deletes nothing. Every "
        "statement it issues is filtered on `origin = 'demo'`; genuine user "
        "records are counted as proof of scope and never deleted."
    ),
)
async def reset_demo(request: DemoResetRequest,
                     user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(get_auth_session)):
    # A non-admin may only reset their own demo records. Clearing every user's
    # demo data is an administrative action.
    if not request.mine_only and user.role is not UserRole.ADMIN:
        return _error("forbidden",
                      "Resetting demonstration data for all users requires an "
                      "administrator account.", status.HTTP_403_FORBIDDEN)
    if request.include_templates and user.role is not UserRole.ADMIN:
        return _error("forbidden",
                      "Removing the shared scenario templates requires an "
                      "administrator account.", status.HTTP_403_FORBIDDEN)

    scope = await reset_demo_data(
        session,
        confirm=request.confirm,
        include_templates=request.include_templates,
        owner_id=user.id if request.mine_only else None,
    )

    message = (
        f"Deleted {scope.demo_runs} demo run(s) and "
        f"{scope.demo_projects} demo project(s). "
        f"{scope.user_runs_preserved} user run(s) and "
        f"{scope.user_projects_preserved} user project(s) were not touched."
        if scope.confirmed else
        f"Nothing was deleted. Confirming would remove {scope.demo_runs} demo "
        f"run(s) and {scope.demo_projects} demo project(s), leaving "
        f"{scope.user_runs_preserved} user run(s) untouched."
    )
    return {**scope.as_dict(), "message": message}


# ===========================================================================
# Runs
# ===========================================================================


@router.post(
    "/runs",
    response_model=RunDetail,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": WorkspaceErrorResponse}},
    summary="Store a completed run",
    description=(
        "Records the verbatim engine responses together with the exact inputs "
        "and engine versions that produced them. A result cannot be stored "
        "without its inputs, and the recorded engine list is derived from which "
        "results are actually present — not from what the caller claims."
    ),
)
async def create_run(request: RunCreateRequest,
                     user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(get_auth_session)):
    scenario = (scenario_by_slug(request.demo_scenario_slug)
                if request.demo_scenario_slug else None)
    if request.is_demo and request.demo_scenario_slug and scenario is None:
        return _error("scenario_not_found",
                      f"No demonstration scenario named "
                      f"{request.demo_scenario_slug!r}.",
                      status.HTTP_400_BAD_REQUEST)

    try:
        run = await svc.create_run(
            session,
            owner_id=user.id,
            name=request.name,
            disease=request.disease,
            subtype=request.subtype,
            drug=request.drug,
            design_inputs=request.design_inputs,
            pk_inputs=request.pk_inputs,
            design_result=request.design_result,
            pk_result=request.pk_result,
            engines_not_run=[e.model_dump() for e in request.engines_not_run],
            project_id=request.project_id,
            is_demo=request.is_demo,
            demo_scenario_slug=request.demo_scenario_slug,
            demo_fixture_version=DEMO_FIXTURE_VERSION if request.is_demo else None,
            pathway=StudyPathway(request.pathway),
            research_purpose=request.research_purpose,
            report_assessment_id=request.report_assessment_id,
        )
    except ValueError:
        return _error("invalid_pathway",
                      f"{request.pathway!r} is not a recognised study pathway.",
                      status.HTTP_400_BAD_REQUEST,
                      "Expected patient_assessment, research_design or "
                      "demo_scenario.")
    except svc.WorkspaceError as exc:
        return _error(exc.code, exc.message, status.HTTP_400_BAD_REQUEST,
                      exc.detail)

    return svc.run_to_detail(run)


@router.get(
    "/runs",
    response_model=RunListResponse,
    summary="List stored runs (Simulation History)",
)
async def list_runs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_auth_session),
    origin: Optional[str] = Query(None, pattern="^(user|demo)$"),
    pathway: Optional[str] = Query(
        None, pattern="^(patient_assessment|research_design|demo_scenario)$"),
    disease: Optional[str] = None,
    scenario: Optional[str] = None,
    run_status: Optional[str] = Query(None, alias="status",
                                      pattern="^(complete|partial|blocked)$"),
    project_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=500),
):
    runs, total = await svc.list_runs(
        session,
        owner_id=user.id,
        origin=RecordOrigin(origin) if origin else None,
        pathway=StudyPathway(pathway) if pathway else None,
        disease=disease,
        scenario_slug=scenario,
        status=RunStatus(run_status) if run_status else None,
        project_id=project_id,
        limit=limit,
    )
    return {"runs": [svc.run_to_summary(r) for r in runs], "total": total}


@router.get(
    "/runs/{run_id}",
    response_model=RunDetail,
    responses={404: {"model": WorkspaceErrorResponse}},
    summary="Open one stored run",
)
async def get_run(run_id: int, user: User = Depends(get_current_user),
                  session: AsyncSession = Depends(get_auth_session)):
    try:
        run = await svc.get_run(session, owner_id=user.id, run_id=run_id)
    except svc.WorkspaceError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)
    return svc.run_to_detail(run)


@router.delete(
    "/runs/{run_id}",
    responses={404: {"model": WorkspaceErrorResponse},
               403: {"model": WorkspaceErrorResponse}},
    summary="Delete one stored run",
)
async def delete_run(run_id: int, user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(get_auth_session)):
    # Viewers may read history but not destroy records.
    if user.role is UserRole.VIEWER:
        return _error("forbidden", "Your role cannot delete stored runs.",
                      status.HTTP_403_FORBIDDEN)
    try:
        run = await svc.delete_run(session, owner_id=user.id, run_id=run_id)
    except svc.WorkspaceError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)
    return {"deleted": True, "id": run_id, "name": run.name}


@router.post(
    "/runs/{run_id}/project",
    response_model=RunDetail,
    responses={404: {"model": WorkspaceErrorResponse}},
    summary="Assign a run to a project, or detach it",
)
async def assign_project(run_id: int, project_id: Optional[int] = None,
                         user: User = Depends(get_current_user),
                         session: AsyncSession = Depends(get_auth_session)):
    try:
        run = await svc.assign_run_to_project(
            session, owner_id=user.id, run_id=run_id, project_id=project_id)
    except svc.WorkspaceError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)
    return svc.run_to_detail(run)


# ===========================================================================
# Comparison
# ===========================================================================


@router.get(
    "/runs/compare/select",
    response_model=ComparisonResponse,
    responses={400: {"model": WorkspaceErrorResponse}},
    summary="Compare two or more stored runs",
    description=(
        "Aligns the genuinely calculated values of the selected runs field by "
        "field. **No combined ranking or aggregate score is produced** — no "
        "approved formula exists for combining these measures, so the API "
        "aligns them and stops."
    ),
)
async def compare_runs(
    ids: str = Query(..., description="Comma-separated run ids, 2 to 4."),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        run_ids = [int(part) for part in ids.split(",") if part.strip()]
    except ValueError:
        return _error("invalid_selection", "Run ids must be integers.",
                      status.HTTP_400_BAD_REQUEST, f"received {ids!r}")

    if not 2 <= len(run_ids) <= 4:
        return _error("invalid_selection",
                      "Select between two and four runs to compare.",
                      status.HTTP_400_BAD_REQUEST,
                      f"received {len(run_ids)} id(s)")

    details = []
    for run_id in run_ids:
        try:
            run = await svc.get_run(session, owner_id=user.id, run_id=run_id)
        except svc.WorkspaceError as exc:
            return _error(exc.code, f"Run {run_id} is not available.",
                          status.HTTP_404_NOT_FOUND, exc.message)
        details.append(svc.run_to_detail(run))

    return {
        "runs": details,
        "rows": svc.build_comparison_rows(details),
        "notice": (
            "Values are copied verbatim from the stored engine responses. "
            "Nothing is recomputed, rescaled or combined: no overall ranking is "
            "produced, because no approved formula exists for combining these "
            "measures. A value shown as unavailable was never calculated for "
            "that run."
        ),
    }


# ===========================================================================
# Projects
# ===========================================================================


@router.post(
    "/projects",
    response_model=ProjectSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def create_project(request: ProjectCreateRequest,
                         user: User = Depends(get_current_user),
                         session: AsyncSession = Depends(get_auth_session)):
    project = await svc.create_project(
        session, owner_id=user.id, name=request.name,
        description=request.description, is_demo=request.is_demo)
    return {
        "id": project.id, "name": project.name,
        "description": project.description, "origin": project.origin.value,
        "run_count": 0, "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


@router.get("/projects", response_model=ProjectListResponse,
            summary="List projects")
async def list_projects(user: User = Depends(get_current_user),
                        session: AsyncSession = Depends(get_auth_session)):
    rows = await svc.list_projects(session, owner_id=user.id)
    return {
        "projects": [
            {"id": p.id, "name": p.name, "description": p.description,
             "origin": p.origin.value, "run_count": count,
             "created_at": p.created_at, "updated_at": p.updated_at}
            for p, count in rows
        ],
        "total": len(rows),
    }


@router.delete("/projects/{project_id}",
               responses={404: {"model": WorkspaceErrorResponse},
                          403: {"model": WorkspaceErrorResponse}},
               summary="Delete a project (its runs are preserved)")
async def delete_project(project_id: int,
                         user: User = Depends(get_current_user),
                         session: AsyncSession = Depends(get_auth_session)):
    if user.role is UserRole.VIEWER:
        return _error("forbidden", "Your role cannot delete projects.",
                      status.HTTP_403_FORBIDDEN)
    try:
        project = await svc.delete_project(session, owner_id=user.id,
                                           project_id=project_id)
    except svc.WorkspaceError as exc:
        return _error(exc.code, exc.message, status.HTTP_404_NOT_FOUND)
    return {"deleted": True, "id": project_id, "name": project.name,
            "runs_preserved": True}
