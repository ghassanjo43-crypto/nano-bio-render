"""Pydantic schemas for POST /api/v1/pk/simulate.

Input contract
--------------
* **Required** — ``dose_mg_kg``, ``kabs_per_h``, ``kel_per_h``, ``k12_per_h``,
  ``k21_per_h``. These are the scientific inputs of the two-compartment model
  and are **never** defaulted. Omitting one is a validation error, not a
  silently-substituted value. This is what makes the endpoint honour "execute
  only when all scientifically required inputs are present and valid".
* **Optional** — ``duration_h`` and ``time_step_h`` are numerical window
  settings rather than properties of the system. Omitted, they fall back to the
  defaults declared in ``utils/pk_model.py`` (48 h, 0.1 h), which is exactly
  what the legacy Streamlit page did. The response always reports which were
  defaulted.

Bounds
------
The numeric bounds below reproduce the legacy Streamlit widget ranges in
``modules/design.py`` (dose and the four rate constants) and
``modules/simulation.py`` (duration and time step). They are the input contract
the legacy application enforced, so mirroring them keeps the migrated endpoint
reachable by exactly the same inputs — no wider, no narrower.

API field names are snake_case with units; the adapter maps them to the
positional names the legacy function uses. The mapping is declared here in one
place so it cannot drift.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

#: Time-step values the legacy simulation page offered. Restated here so the
#: API cannot be driven into a step size the legacy application never ran.
LEGACY_TIME_STEP_CHOICES: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 1.0)


class PKSimulationRequest(BaseModel):
    """Inputs for one two-compartment pharmacokinetic run."""

    model_config = ConfigDict(
        extra="forbid",  # reject unknown fields rather than ignoring them
        json_schema_extra={
            "example": {
                "dose_mg_kg": 10.0,
                "kabs_per_h": 0.5,
                "kel_per_h": 0.1,
                "k12_per_h": 0.3,
                "k21_per_h": 0.2,
                "duration_h": 48,
                "time_step_h": 0.1,
            }
        },
    )

    # --- required scientific inputs ----------------------------------------
    dose_mg_kg: float = Field(
        ..., ge=0.1, le=100.0,
        description=(
            "Administered dose in mg per kg body weight. Required; never "
            "defaulted. Legacy range 0.1–100."
        ),
    )
    kabs_per_h: float = Field(
        ..., ge=0.01, le=5.0,
        description=(
            "First-order absorption rate constant from the depot, per hour. "
            "Required; never defaulted. Legacy range 0.01–5.0."
        ),
    )
    kel_per_h: float = Field(
        ..., ge=0.001, le=2.0,
        description=(
            "First-order elimination rate constant from the central "
            "compartment, per hour. Required; never defaulted. Legacy range "
            "0.001–2.0."
        ),
    )
    k12_per_h: float = Field(
        ..., ge=0.01, le=2.0,
        description=(
            "First-order transfer rate constant, central to peripheral, per "
            "hour. Required; never defaulted. Legacy range 0.01–2.0."
        ),
    )
    k21_per_h: float = Field(
        ..., ge=0.01, le=2.0,
        description=(
            "First-order transfer rate constant, peripheral to central, per "
            "hour. Required; never defaulted. Legacy range 0.01–2.0."
        ),
    )

    # --- optional numerical window ------------------------------------------
    duration_h: Optional[float] = Field(
        None, ge=12, le=168,
        description=(
            "Length of the simulated window in hours. Legacy default 48, "
            "legacy range 12–168."
        ),
    )
    time_step_h: Optional[float] = Field(
        None,
        description=(
            "Forward-Euler integration step in hours. Legacy default 0.1. "
            "Must be one of "
            + ", ".join(str(v) for v in LEGACY_TIME_STEP_CHOICES)
            + " — the step size is part of the model's numerical identity, so "
            "arbitrary values are not accepted."
        ),
        json_schema_extra={"enum": list(LEGACY_TIME_STEP_CHOICES)},
    )

    #: API field name -> the keyword the legacy function takes.
    #: MUST be ClassVar: a bare annotated assignment would be read by Pydantic
    #: v2 as a model *field* and leak into the public request schema.
    FIELD_MAP: ClassVar[Dict[str, str]] = {
        "dose_mg_kg": "dose",
        "kabs_per_h": "kabs",
        "kel_per_h": "kel",
        "k12_per_h": "k12",
        "k21_per_h": "k21",
        "duration_h": "duration",
        "time_step_h": "dt",
    }

    def model_post_init(self, _context: Any) -> None:
        if (self.time_step_h is not None
                and self.time_step_h not in LEGACY_TIME_STEP_CHOICES):
            raise ValueError(
                "time_step_h must be one of "
                + ", ".join(str(v) for v in LEGACY_TIME_STEP_CHOICES)
            )

    def to_legacy_payload(self) -> Dict[str, Any]:
        """Map to the keyword names ``utils.pk_model`` takes.

        Optional fields the caller never mentioned are omitted entirely, so the
        adapter applies the legacy default and reports that it did.
        """
        payload: Dict[str, Any] = {}
        for api_name, legacy in self.FIELD_MAP.items():
            value = getattr(self, api_name)
            if value is not None:
                payload[legacy] = value
        return payload


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class ConcentrationTimeSeries(BaseModel):
    """The calculated concentration–time profile.

    Three parallel arrays of equal length. Charts must be drawn from these
    values and nothing else; there is no smoothing, resampling or interpolation
    between the model and this field.
    """

    model_config = ConfigDict(extra="forbid")

    time_h: List[float] = Field(..., description="Time points, hours.")
    central_plasma: List[float] = Field(
        ..., description="Central (plasma) compartment values.")
    peripheral_tissue: List[float] = Field(
        ..., description="Peripheral (tissue) compartment values.")
    point_count: int
    concentration_unit: str = Field(
        ...,
        description=(
            "Arbitrary dose-scaled units. The model has no volume term, so "
            "these are not mass-per-volume concentrations."
        ),
    )
    time_unit: str


class PKParameters(BaseModel):
    """Derived parameters, exactly as the legacy function returns them.

    Nothing here is derived by the API layer. In particular there is **no
    clearance field**: the migrated model produces none, and inventing one
    would be new science. See ``quantities_not_produced``.
    """

    model_config = ConfigDict(extra="forbid")

    peak_concentration_central: float
    peak_concentration_peripheral: float
    time_to_peak_central_h: float
    time_to_peak_peripheral_h: float
    auc_central: float
    auc_peripheral: float
    half_life_central_h: Optional[float] = Field(
        None,
        description=(
            "Terminal half-life in hours, or null when the central "
            "compartment never halves within the simulated window. Null is a "
            "real answer here and is never replaced by an estimate."
        ),
    )
    tissue_accumulation_ratio: float
    vss_ratio: float


class UnproducedQuantity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: str
    reason: str


class PKSimulationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concentration_time: ConcentrationTimeSeries
    pk_parameters: PKParameters
    calculation_version: str
    model_name: str
    normalized_inputs: Dict[str, float]
    warnings: List[str]
    assumptions: List[str]
    limitations: List[str]
    quantities_not_produced: List[UnproducedQuantity]
    prediction_basis: str
    evidence_level: str
    validation_status: str
    scientific_source: str


class PKErrorResponse(BaseModel):
    """Structured failure. Deliberately carries no numeric result field.

    A failed calculation must never produce a curve, half-life or AUC —
    favourable or otherwise.
    """

    model_config = ConfigDict(extra="forbid")

    error: str = Field(..., description="Machine-readable failure code.")
    message: str
    detail: Optional[str] = None
    results_available: bool = Field(
        False,
        description="Always false. No pharmacokinetic result is produced on "
                    "failure.",
    )
