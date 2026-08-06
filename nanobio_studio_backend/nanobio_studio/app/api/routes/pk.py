"""Pharmacokinetic simulation routes.

Thin transport layer only. All scientific behaviour lives in
``app/services/pk_simulation.py``, which calls the legacy
``utils/pk_model.py`` functions verbatim. No equation, rate constant, default,
integration step or derived quantity appears in this module.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from nanobio_studio.app.api.deps_auth import get_current_user
from nanobio_studio.app.db.auth_models import User
from nanobio_studio.app.schemas.pk_simulation import (
    PKErrorResponse,
    PKSimulationRequest,
    PKSimulationResponse,
)
from nanobio_studio.app.services.pk_simulation import (
    PKSimulationFailure,
    simulate_pk,
)

router = APIRouter(prefix="/api/v1", tags=["pharmacokinetics"])


@router.post(
    "/pk/simulate",
    response_model=PKSimulationResponse,
    responses={
        422: {"model": PKErrorResponse,
              "description": "Request failed schema validation."},
        400: {"model": PKErrorResponse,
              "description": "Inputs were rejected by the pharmacokinetic "
                             "model."},
        401: {"model": PKErrorResponse,
              "description": "Authentication required."},
        500: {"model": PKErrorResponse,
              "description": "Calculation failed. No profile is returned."},
    },
    summary="Run the two-compartment pharmacokinetic model",
    description=(
        "Executes the migrated two-compartment model "
        "(`utils.pk_model.two_compartment_model`) and its derived-parameter "
        "function, both called verbatim, and returns the concentration–time "
        "profile with the parameters the model genuinely produces.\n\n"
        "**Scientific positioning.** The result is a computational "
        "research-planning output. It is not experimentally validated, not "
        "clinically validated, not a regulatory approval prediction, not a "
        "dosing recommendation, and not a substitute for an in-vivo "
        "pharmacokinetic study.\n\n"
        "**Clearance is not returned.** The model has no volume term, so no "
        "clearance can be derived from it. The quantities it does not produce "
        "are listed explicitly in `quantities_not_produced` rather than left "
        "as an unexplained gap.\n\n"
        "**This is not the design impact score.** It is a separate "
        "calculation, with separate inputs and its own version. The two must "
        "not be combined.\n\n"
        "The disease and therapeutic selection made in the workflow are not "
        "inputs here and do not affect any returned value."
    ),
)
async def simulate_pk_endpoint(
    request: PKSimulationRequest,
    _user: User = Depends(get_current_user),
):
    """Run the model, or fail with a structured error carrying no numbers.

    Requires an authenticated session, matching the design-scoring endpoint.
    Authentication is transport, not science: it does not alter a single value.
    """
    try:
        result = simulate_pk(request.to_legacy_payload())
    except PKSimulationFailure as exc:
        http_status = {
            "missing_required_input": status.HTTP_400_BAD_REQUEST,
            "invalid_input_value": status.HTTP_400_BAD_REQUEST,
        }.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        return JSONResponse(
            status_code=http_status,
            content=PKErrorResponse(
                error=exc.code,
                message=exc.message,
                detail=exc.detail,
                results_available=False,
            ).model_dump(),
        )

    return result
