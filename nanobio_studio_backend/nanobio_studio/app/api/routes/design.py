"""Design scoring routes.

Thin transport layer only. All scientific behaviour lives in
``app/services/design_scoring.py``, which calls the canonical
``core/scoring.py::compute_impact()`` verbatim. No formula, threshold, weight or
default appears in this module.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from nanobio_studio.app.api.deps_auth import get_current_user
from nanobio_studio.app.db.auth_models import User

from nanobio_studio.app.schemas.design_score import (
    DesignScoreRequest,
    DesignScoreResponse,
    ScoreErrorResponse,
)
from nanobio_studio.app.services.design_scoring import ScoringFailure, score_design

router = APIRouter(prefix="/api/v1", tags=["design"])


@router.post(
    "/design/score",
    response_model=DesignScoreResponse,
    responses={
        422: {"model": ScoreErrorResponse,
              "description": "Request failed schema validation."},
        400: {"model": ScoreErrorResponse,
              "description": "Inputs were rejected by the scoring function."},
        401: {"model": ScoreErrorResponse,
              "description": "Authentication required."},
        500: {"model": ScoreErrorResponse,
              "description": "Calculation failed. No score is returned."},
    },
    summary="Calculate the design impact score for a nanoparticle formulation",
    description=(
        "Computes Delivery, Toxicity and Cost using the canonical scientific "
        "function `core.scoring.compute_impact`.\n\n"
        "**Scientific positioning.** The result is a computational "
        "research-planning output. It is not experimentally validated, not "
        "clinically validated, not a regulatory approval prediction, not a "
        "diagnosis, and not a treatment recommendation.\n\n"
        "No single composite 'Overall Score' is returned: the candidate formula "
        "is documented but not implemented, pending scientific review. The "
        "deprecated hard-coded 92/89/82 headline score is never returned."
    ),
)
async def score_design_endpoint(
    request: DesignScoreRequest,
    _user: User = Depends(get_current_user),
):
    """Score a design, or fail with a structured error carrying no number.

    Requires an authenticated session (application-shell slice). The
    numerical behaviour is unchanged: the same canonical function is called
    with the same inputs and returns the same values.
    """
    try:
        result = score_design(request.to_canonical_payload())
    except ScoringFailure as exc:
        http_status = {
            "missing_required_input": status.HTTP_400_BAD_REQUEST,
            "invalid_input_value": status.HTTP_400_BAD_REQUEST,
            "input_normalisation_failed": status.HTTP_400_BAD_REQUEST,
        }.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        return JSONResponse(
            status_code=http_status,
            content=ScoreErrorResponse(
                error=exc.code,
                message=exc.message,
                detail=exc.detail,
                score_available=False,
            ).model_dump(),
        )

    return result
