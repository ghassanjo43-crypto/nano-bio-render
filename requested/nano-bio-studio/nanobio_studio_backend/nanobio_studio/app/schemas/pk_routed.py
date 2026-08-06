"""Schemas for the route-aware pharmacokinetic endpoints.

Bounds here are structural (a duration must be positive, a step must be usable),
not scientific judgements about a plausible physiological range. No field has a
scientific default: the parameters come from a cited set, and the dosing inputs
come from the protocol.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RoutedSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    therapeutic: str = Field(..., min_length=1, max_length=160)
    route: str = Field(..., description="See GET /pk/administration-routes")
    mode: str = Field("guided", pattern="^(guided|expert_research)$")

    parameter_set_id: Optional[str] = Field(None, max_length=120)
    #: Pinning the version is what keeps a historical run reproducible.
    parameter_set_version: Optional[str] = Field(None, max_length=40)

    # --- dosing, from the treatment protocol --------------------------------
    dose_basis: str = Field(..., pattern="^(fixed|per_kg|per_bsa)$")
    dose_amount: float = Field(..., gt=0)
    #: Required for a per_kg dose. Never defaulted to a "typical" weight.
    body_weight_kg: Optional[float] = Field(None, gt=0, le=500)
    bsa_m2: Optional[float] = Field(None, gt=0, le=5)

    infusion_duration_h: Optional[float] = Field(None, gt=0, le=48)
    dosing_interval_h: Optional[float] = Field(None, gt=0, le=2000)
    number_of_doses: int = Field(1, ge=1, le=100)

    #: Only meaningful for extravascular routes; refused by the engine for IV.
    k_abs_per_h: Optional[float] = Field(None, gt=0, le=100)
    bioavailability: Optional[float] = Field(None, gt=0, le=1)

    # --- simulation settings ------------------------------------------------
    duration_h: float = Field(48.0, gt=0, le=8760)
    time_step_h: float = Field(0.01, gt=0, le=1.0)
    output_interval_h: Optional[float] = Field(None, gt=0, le=24)

    #: The user must confirm the provenance summary before anything runs.
    provenance_confirmed: bool = False

    #: Expert-mode edits, recorded verbatim so they appear in the audit trail.
    expert_overrides: Dict[str, Any] = Field(default_factory=dict)


class PlannedInputOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    value: Any
    unit: str
    source: str
    source_label: str
    report_field: Optional[str]
    confirmation_status: Optional[str]
    formula: Optional[str]
    source_values: Optional[Dict[str, str]]
    editable: bool


class ParameterSetOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: str
    therapeutic: str
    formulation: str
    route: str
    population: str
    indication: Optional[str]
    model_structure: str
    source_citation: str
    validation_status: str
    date_reviewed: str
    limitations: List[str]
    covariates: List[str]
    not_represented: List[str]


class RunPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    therapeutic: str
    route: str
    mode: str
    model_label: str
    engine_version: str
    library_version: str
    runnable: bool
    blocking_reasons: List[str]
    missing_inputs: List[str]
    not_applicable: List[str]
    not_represented: List[str]
    warnings: List[str]
    suitability: str
    notice: str
    inputs: List[PlannedInputOut]
    parameter_set: Optional[ParameterSetOut]
