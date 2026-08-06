"""Route-aware pharmacokinetic endpoints.

Transport only. Every scientific decision — which model a route implies, whether
a parameter set may be used, how rate constants are derived — lives in
``app/pk/``. This module adds no equation, constant or default.

Separate from ``routes/pk.py`` on purpose: that endpoint continues to serve the
legacy depot model unchanged, so existing stored runs remain reproducible
against the engine that produced them.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from nanobio_studio.app.api.deps_auth import get_current_user
from nanobio_studio.app.db.auth_models import User
from nanobio_studio.app.pk.administration import AdministrationRoute, all_routes
from nanobio_studio.app.pk.models import (
    DoseRegimen,
    ModelExecutionError,
    ModelInputs,
    PK_ENGINE_VERSION,
    simulate,
)
from nanobio_studio.app.pk.parameter_library import (
    LIBRARY_VERSION,
    get_parameter_set,
)
from nanobio_studio.app.pk.planning import (
    RESEARCH_USE_ONLY_NOTICE,
    DoseBasis,
    InputMode,
    RunPlan,
    build_plan,
    resolve_absolute_dose,
)
from nanobio_studio.app.schemas.pk_routed import (
    RoutedSimulationRequest,
    RunPlanResponse,
)

router = APIRouter(prefix="/api/v1/pk", tags=["pharmacokinetics"])


def _error(code: str, message: str, http_status: int,
           detail: str | None = None) -> JSONResponse:
    """Structured failure. Never carries a numeric result."""
    return JSONResponse(
        status_code=http_status,
        content={"error": code, "message": message, "detail": detail,
                 "data_available": False},
    )


@router.get("/administration-routes",
            summary="Administration routes and what each one requires")
async def list_routes(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "routes": [
            {
                "route": s.route.value,
                "label": s.label,
                "input_function": s.input_function.value,
                "description": s.description,
                "has_absorption_phase": s.has_absorption_phase,
                "required_dosing_inputs": list(s.required_dosing_inputs),
                "not_applicable_inputs": list(s.not_applicable_inputs),
                "bioavailability_is_free": s.bioavailability_is_free,
                "fixed_bioavailability": s.fixed_bioavailability,
                "fixed_bioavailability_reason": s.fixed_bioavailability_reason,
                "notes": list(s.notes),
            }
            for s in all_routes()
        ],
        "notice": RESEARCH_USE_ONLY_NOTICE,
    }


def _plan_to_dict(plan: RunPlan) -> dict[str, Any]:
    ps = plan.parameter_set
    return {
        "therapeutic": plan.therapeutic,
        "route": plan.route.value,
        "mode": plan.mode.value,
        "model_label": plan.model_label,
        "engine_version": PK_ENGINE_VERSION,
        "library_version": plan.library_version,
        "runnable": plan.runnable,
        "blocking_reasons": plan.blocking_reasons,
        "missing_inputs": plan.missing_inputs,
        "not_applicable": plan.not_applicable,
        "not_represented": plan.not_represented,
        "warnings": plan.warnings,
        "suitability": plan.suitability,
        "notice": plan.notice,
        "inputs": [
            {
                "name": i.name, "label": i.label, "value": i.value,
                "unit": i.unit, "source": i.source.value,
                "source_label": i.source_label,
                "report_field": i.report_field,
                "confirmation_status": i.confirmation_status,
                "formula": i.formula, "source_values": i.source_values,
                "editable": i.editable,
            }
            for i in plan.inputs
        ],
        "parameter_set": None if ps is None else {
            "id": ps.id, "version": ps.version,
            "therapeutic": ps.therapeutic, "formulation": ps.formulation,
            "route": ps.route.value, "population": ps.population,
            "indication": ps.indication,
            "model_structure": ps.model_structure.value,
            "source_citation": ps.source_citation,
            "validation_status": ps.validation_status.value,
            "date_reviewed": ps.date_reviewed,
            "limitations": list(ps.limitations),
            "covariates": list(ps.covariates),
            "not_represented": list(ps.not_represented),
        },
    }


@router.get("/plan", response_model=RunPlanResponse,
            summary="Build the run plan for a therapeutic and route")
async def get_plan(
    therapeutic: str = Query(..., min_length=1, max_length=160),
    route: str = Query(...),
    mode: str = Query("guided", pattern="^(guided|expert_research)$"),
    parameter_set_id: str | None = Query(None),
    parameter_set_version: str | None = Query(None),
    user: User = Depends(get_current_user),
):
    try:
        route_enum = AdministrationRoute(route)
    except ValueError:
        return _error("unknown_route", f"{route!r} is not a known "
                      "administration route.", status.HTTP_400_BAD_REQUEST,
                      "Known routes: "
                      + ", ".join(r.value for r in AdministrationRoute))

    ps = None
    if parameter_set_id:
        ps = get_parameter_set(parameter_set_id, parameter_set_version)
        if ps is None:
            return _error(
                "parameter_set_not_found",
                f"No parameter set {parameter_set_id!r}"
                + (f" at version {parameter_set_version!r}"
                   if parameter_set_version else "")
                + " exists.",
                status.HTTP_404_NOT_FOUND,
                "A stored run pinned to a withdrawn parameter set cannot be "
                "re-run; its original values remain in the stored record.")

    plan = build_plan(therapeutic=therapeutic, route=route_enum,
                      mode=InputMode(mode), parameter_set=ps)
    return _plan_to_dict(plan)


@router.post("/simulate-routed",
             summary="Run the route-aware two-compartment model")
async def simulate_routed(request: RoutedSimulationRequest,
                          user: User = Depends(get_current_user)):
    try:
        route_enum = AdministrationRoute(request.route)
    except ValueError:
        return _error("unknown_route", f"{request.route!r} is not a known "
                      "administration route.", status.HTTP_400_BAD_REQUEST)

    # Explicit confirmation of the provenance summary is required before a run.
    if not request.provenance_confirmed:
        return _error(
            "confirmation_required",
            "The input provenance summary must be reviewed and confirmed "
            "before the simulation runs.",
            status.HTTP_400_BAD_REQUEST,
            "This ensures the user has seen which values came from the report, "
            "which were entered manually, and which came from a cited "
            "parameter set.")

    ps = None
    if request.parameter_set_id:
        ps = get_parameter_set(request.parameter_set_id,
                               request.parameter_set_version)
        if ps is None:
            return _error("parameter_set_not_found",
                          "The requested parameter set does not exist.",
                          status.HTTP_404_NOT_FOUND)

    plan = build_plan(therapeutic=request.therapeutic, route=route_enum,
                      mode=InputMode(request.mode), parameter_set=ps)
    if not plan.runnable:
        return _error(
            "not_operational",
            plan.suitability or "This combination cannot be simulated.",
            status.HTTP_400_BAD_REQUEST,
            " ".join(plan.blocking_reasons))

    # --- resolve the dose ---------------------------------------------------
    try:
        dose_mg, dose_explanation = resolve_absolute_dose(
            basis=DoseBasis(request.dose_basis),
            amount=request.dose_amount,
            body_weight_kg=request.body_weight_kg,
            bsa_m2=request.bsa_m2,
        )
    except ValueError as exc:
        return _error("missing_required_input", str(exc),
                      status.HTTP_400_BAD_REQUEST)

    derived = {i.name: i for i in plan.inputs if i.source.value == "derived"}
    library = {i.name: i for i in plan.inputs
               if i.source.value == "parameter_library"}

    try:
        output = simulate(ModelInputs(
            route=route_enum,
            regimen=DoseRegimen(
                dose_mg=dose_mg,
                infusion_duration_h=request.infusion_duration_h,
                dosing_interval_h=request.dosing_interval_h,
                number_of_doses=request.number_of_doses,
            ),
            k_el_per_h=float(derived["k_el"].value),
            k_12_per_h=float(derived["k_12"].value),
            k_21_per_h=float(derived["k_21"].value),
            v_c_litres=float(library["Vc"].value),
            v_p_litres=float(library["Vp"].value),
            bioavailability=request.bioavailability
                if request.bioavailability is not None else 1.0,
            k_abs_per_h=request.k_abs_per_h,
            duration_h=request.duration_h,
            time_step_h=request.time_step_h,
            output_interval_h=request.output_interval_h,
        ))
    except ModelExecutionError as exc:
        return _error(exc.code, exc.message, status.HTTP_400_BAD_REQUEST,
                      exc.detail)

    assert plan.parameter_set is not None
    return {
        "concentration_time": {
            "time_h": output.time_h,
            "central_concentration": output.central_concentration,
            "peripheral_concentration": output.peripheral_concentration,
            "central_amount": output.central_amount,
            "peripheral_amount": output.peripheral_amount,
            "concentration_unit": output.concentration_unit,
            "amount_unit": output.amount_unit,
            "time_unit": "hours",
            "point_count": len(output.time_h),
        },
        # Everything needed to reproduce this run, stored with it.
        "reproducibility": {
            "engine_version": PK_ENGINE_VERSION,
            "library_version": LIBRARY_VERSION,
            "parameter_set_id": plan.parameter_set.id,
            "parameter_set_version": plan.parameter_set.version,
            "model_structure": plan.parameter_set.model_structure.value,
            "route": route_enum.value,
            "mode": request.mode,
            "dose_mg": dose_mg,
            "dose_basis": request.dose_basis,
            "dose_explanation": dose_explanation,
            "dosing_interval_h": request.dosing_interval_h,
            "number_of_doses": request.number_of_doses,
            "infusion_duration_h": request.infusion_duration_h,
            "duration_h": request.duration_h,
            "time_step_h": request.time_step_h,
            "output_interval_h": request.output_interval_h,
            "formulas": {name: d.formula for name, d in derived.items()},
            "expert_overrides": request.expert_overrides,
            "deterministic": True,
        },
        "input_provenance": [
            {"name": i.name, "value": i.value, "unit": i.unit,
             "source": i.source.value, "source_label": i.source_label,
             "formula": i.formula, "source_values": i.source_values}
            for i in plan.inputs
        ],
        "suitability": plan.suitability,
        "warnings": output.warnings + plan.warnings,
        "not_represented": plan.not_represented,
        "validation_status": plan.parameter_set.validation_status.value,
        "source_citation": plan.parameter_set.source_citation,
        "population": plan.parameter_set.population,
        "notice": RESEARCH_USE_ONLY_NOTICE,
    }
