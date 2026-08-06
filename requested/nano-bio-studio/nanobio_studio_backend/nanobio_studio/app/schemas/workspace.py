"""Pydantic schemas for the demo workspace, stored runs and projects.

Scientific contract enforced by these schemas
---------------------------------------------
* A **demo scenario** carries inputs and teaching metadata only. There is no
  field on ``DemoScenarioDetail`` that could hold a score, a concentration, a
  half-life or an assessment verdict — a fabricated result cannot be expressed
  in this type, let alone stored.
* A **stored run** carries the engine responses verbatim, plus the exact
  inputs and engine versions that produced them, plus the list of engines that
  did *not* run. A historical record can therefore never be misread as having
  included an engine that never executed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ===========================================================================
# Demo scenarios
# ===========================================================================


class EngineNotRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: str
    reason: str


class DemoScenarioSummary(BaseModel):
    """Card-level view for the scenario picker."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    purpose: str
    disease: str
    subtype: str
    drug: str
    technical: bool
    #: Whether each connected engine can run with the scenario's inputs as-is.
    score_runnable: bool
    pk_runnable: bool
    engines_expected_to_run: List[str]
    engine_count_not_running: int
    fixture_version: str
    #: Constant. Rendered as a badge on every scenario, without exception.
    data_classification: str = Field(
        "Synthetic demonstration data",
        description="Never clinical, experimental or patient data.")


class DemoScenarioDetail(DemoScenarioSummary):
    """Full preview, shown before a scenario is loaded.

    Deliberately has no result field of any kind.
    """

    model_config = ConfigDict(extra="forbid")

    design_inputs: Dict[str, Any]
    pk_inputs: Dict[str, Any]
    assumptions: List[str]
    #: What the user should expect to see. NOT the engine's output.
    expected_warnings: List[str]
    engines_that_will_not_run: List[EngineNotRun]
    provenance: List[str]
    #: Design fields that are scientifically required but absent, which is why
    #: execution will be blocked. Empty for a complete scenario.
    missing_required_design_inputs: List[str]
    missing_required_pk_inputs: List[str]


class DemoScenarioListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_version: str
    scenarios: List[DemoScenarioSummary]
    #: Restated on every listing so the classification travels with the data.
    notice: str


# ===========================================================================
# Stored runs
# ===========================================================================


class RunCreateRequest(BaseModel):
    """Persist a completed run.

    The results must be the **verbatim engine responses**. The server records
    what it is given together with the inputs and versions; it does not
    recompute, and it does not accept a result without the inputs that produced
    it (enforced in the route).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)

    disease: Optional[str] = Field(None, max_length=120)
    subtype: Optional[str] = Field(None, max_length=160)
    drug: Optional[str] = Field(None, max_length=160)

    design_inputs: Optional[Dict[str, Any]] = None
    pk_inputs: Optional[Dict[str, Any]] = None

    design_result: Optional[Dict[str, Any]] = None
    pk_result: Optional[Dict[str, Any]] = None

    engines_not_run: List[EngineNotRun] = Field(default_factory=list)

    project_id: Optional[int] = None

    #: How the study began. Recorded so a patient assessment, a research design
    #: and a demonstration stay distinguishable wherever studies are listed.
    pathway: str = Field(
        "research_design",
        description="patient_assessment | research_design | demo_scenario")
    research_purpose: Optional[str] = Field(None, max_length=80)
    report_assessment_id: Optional[int] = None

    #: Marks the run as demo-generated. A demo run is never presented as the
    #: user's own research work.
    is_demo: bool = False
    demo_scenario_slug: Optional[str] = Field(None, max_length=100)


class RunSummary(BaseModel):
    """List-level view for Simulation History."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    origin: str
    pathway: str
    research_purpose: Optional[str]
    inputs_are_synthetic: bool
    report_assessment_id: Optional[int]
    demo_scenario_slug: Optional[str]
    disease: Optional[str]
    subtype: Optional[str]
    drug: Optional[str]
    status: str
    engines_run: List[str]
    has_design_result: bool
    has_pk_result: bool
    design_score_version: Optional[str]
    pk_calculation_version: Optional[str]
    project_id: Optional[int]
    created_at: datetime


class RunDetail(RunSummary):
    """Full stored record, including the verbatim engine responses."""

    model_config = ConfigDict(extra="forbid")

    design_inputs: Optional[Dict[str, Any]]
    pk_inputs: Optional[Dict[str, Any]]
    design_result: Optional[Dict[str, Any]]
    pk_result: Optional[Dict[str, Any]]
    engines_not_run: List[EngineNotRun]
    demo_fixture_version: Optional[str]


class RunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: List[RunSummary]
    total: int


# ===========================================================================
# Projects
# ===========================================================================


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    is_demo: bool = False


class ProjectSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    description: Optional[str]
    origin: str
    run_count: int
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: List[ProjectSummary]
    total: int


# ===========================================================================
# Comparison
# ===========================================================================


class ComparisonResponse(BaseModel):
    """Aligned view of two or more stored runs.

    Deliberately carries **no combined ranking and no aggregate score**. No
    approved formula exists for combining these measures (blocker B5 in
    docs/MODULE_INVENTORY.md), so the API aligns the genuinely calculated values
    and stops there.
    """

    model_config = ConfigDict(extra="forbid")

    runs: List[RunDetail]
    #: Field-by-field alignment for rendering. Values are copied verbatim from
    #: the stored engine responses; nothing is recomputed or normalised.
    rows: List[Dict[str, Any]]
    notice: str


# ===========================================================================
# Demo reset
# ===========================================================================


class DemoResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Without this, the endpoint reports scope and deletes nothing.
    confirm: bool = False
    include_templates: bool = False
    #: Restrict to the calling user's own demo records.
    mine_only: bool = True


class DemoResetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool
    deleted: bool
    demo_runs: int
    demo_projects: int
    demo_templates: int
    user_runs_preserved: int
    user_projects_preserved: int
    message: str


class DemoSeedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_version: str
    created: List[str]
    updated: List[str]
    unchanged: List[str]
    total: int


class WorkspaceErrorResponse(BaseModel):
    """Structured failure carrying no data field."""

    model_config = ConfigDict(extra="forbid")

    error: str
    message: str
    detail: Optional[str] = None
    data_available: bool = Field(False, description="Always false on failure.")
