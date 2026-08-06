"""Pydantic schemas for POST /api/v1/design/score.

Input contract mirrors the Step 1 DEFECT-D9 correction exactly:

* **Required** -- ``size_nm``, ``charge_mv``, ``encapsulation_percent``. These are
  scientifically required and are NEVER replaced by a default. Omitting one is a
  validation error, not a silently-defaulted value.
* **Optional** -- an omitted field and an explicit ``null`` are equivalent; both
  cause the canonical function's own documented default to apply.

API field names are snake_case with units; the adapter maps them to the
CapitalCase keys the canonical function uses. The mapping is declared here in one
place so it cannot drift.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DesignScoreRequest(BaseModel):
    """A nanoparticle design submitted for scoring."""

    model_config = ConfigDict(
        extra="forbid",  # reject unknown fields rather than ignoring them
        json_schema_extra={
            "example": {
                "size_nm": 100,
                "charge_mv": -5,
                "encapsulation_percent": 85,
                "pdi": 0.15,
                "surface_coating": ["PEG (Stealth)"],
                "ligand": "GalNAc",
            }
        },
    )

    # --- required -----------------------------------------------------------
    size_nm: float = Field(
        ..., gt=0, le=10000,
        description="Core particle diameter in nanometres. Required.",
    )
    charge_mv: float = Field(
        ..., ge=-200, le=200,
        description="Zeta potential in millivolts. Required.",
    )
    encapsulation_percent: float = Field(
        ..., ge=0, le=100,
        description="Encapsulation efficiency, percent. Required.",
    )

    # --- optional -----------------------------------------------------------
    pdi: Optional[float] = Field(
        None, ge=0, le=1, description="Polydispersity index. Default 0.15.")
    hydrodynamic_size_nm: Optional[float] = Field(
        None, gt=0, le=10000,
        description="Hydrodynamic diameter. Defaults to size_nm * 1.2.")
    stability_percent: Optional[float] = Field(
        None, ge=0, le=100, description="Stability percent. Default 85.")
    surface_area_nm2: Optional[float] = Field(
        None, ge=0, description="Surface area in nm^2. Default 250.")
    degradation_time_days: Optional[float] = Field(
        None, ge=0, description="Degradation time in days. Default 30.")
    crystallinity_index: Optional[float] = Field(
        None, ge=0, le=100, description="Crystallinity percent. Default 65.")
    hydrophobicity_logp: Optional[float] = Field(
        None, ge=-10, le=10, description="LogP. Default 1.5.")
    coating_thickness_nm: Optional[float] = Field(
        None, ge=0, description="Coating thickness in nm. Default 2.5.")
    ligand_density_percent: Optional[float] = Field(
        None, ge=0, le=100, description="Ligand density percent. Default 0.")
    receptor_binding_kd_nm: Optional[float] = Field(
        None, ge=0, description="Receptor binding Kd in nM. Default 100.")
    release_predictability_percent: Optional[float] = Field(
        None, ge=0, le=100,
        description="Release predictability percent. Default 85.")

    ligand: Optional[str] = Field(
        None, max_length=100,
        description="Targeting ligand name, or 'None'. Default 'None'.")
    surface_coating: Optional[List[str]] = Field(
        None, description="Coatings. Default ['PEG (Stealth)'].")
    functional_groups: Optional[List[str]] = Field(
        None, description="Surface functional groups. Default [].")

    @field_validator("surface_coating", "functional_groups")
    @classmethod
    def _reject_blank_entries(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        if any((not isinstance(s, str)) or not s.strip() for s in v):
            raise ValueError("list entries must be non-empty strings")
        return v

    #: API field name -> canonical CapitalCase key used by core.scoring.
    #: MUST be ClassVar: a bare annotated assignment is interpreted by Pydantic v2
    #: as a model *field*, which would both leak this mapping into the public
    #: request schema and make it settable by callers.
    FIELD_MAP: ClassVar[Dict[str, str]] = {
        "size_nm": "Size",
        "charge_mv": "Charge",
        "encapsulation_percent": "Encapsulation",
        "pdi": "PDI",
        "hydrodynamic_size_nm": "HydrodynamicSize",
        "stability_percent": "Stability",
        "surface_area_nm2": "SurfaceArea",
        "degradation_time_days": "DegradationTime",
        "crystallinity_index": "CrystallinityIndex",
        "hydrophobicity_logp": "Hydrophobicity",
        "coating_thickness_nm": "CoatingThickness",
        "ligand_density_percent": "LigandDensity",
        "receptor_binding_kd_nm": "ReceptorBinding",
        "release_predictability_percent": "ReleasePredictability",
        "ligand": "Ligand",
        "surface_coating": "SurfaceCoating",
        "functional_groups": "FunctionalGroups",
    }

    def to_canonical_payload(self) -> Dict[str, Any]:
        """Map to the canonical dict shape.

        Fields the caller never mentioned are omitted entirely; fields explicitly
        set to null are forwarded as ``None``. Both routes reach the same
        canonical default, per the DEFECT-D9 contract.
        """
        supplied = self.model_dump(exclude_unset=True)
        payload: Dict[str, Any] = {}
        for api_name, canonical in self.FIELD_MAP.items():
            if api_name in supplied:
                payload[canonical] = supplied[api_name]
        # Required fields are always present even if not "set" explicitly.
        for api_name in ("size_nm", "charge_mv", "encapsulation_percent"):
            payload[self.FIELD_MAP[api_name]] = getattr(self, api_name)
        return payload


class ComponentScore(BaseModel):
    value: float
    scale: str
    meaning: str


class DesignImpactScore(BaseModel):
    """The three canonical outputs of ``compute_impact``.

    Deliberately NOT a single composite number. The candidate composite formula
    is documented in docs/SCORING_CANONICALIZATION.md but is explicitly not
    implemented pending scientific review, so none is returned here.
    """

    delivery: float = Field(..., description="0-100, higher is better.")
    toxicity: float = Field(..., description="0-10, lower is better.")
    cost: float = Field(..., description="0-100, lower is better.")


class DesignScoreResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_impact_score: DesignImpactScore
    score_version: str
    component_scores: Dict[str, ComponentScore]
    normalized_inputs: Dict[str, Any]
    warnings: List[str]
    prediction_basis: str
    evidence_level: str
    validation_status: str
    limitations: List[str]
    scientific_source: str


class ScoreErrorResponse(BaseModel):
    """Structured failure. Deliberately carries no numeric score field.

    A failed calculation must never produce a favourable number (DECISION 2).
    """

    model_config = ConfigDict(extra="forbid")

    error: str = Field(..., description="Machine-readable failure code.")
    message: str
    detail: Optional[str] = None
    score_available: bool = Field(
        False, description="Always false. No score is produced on failure.")
