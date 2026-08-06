"""Assemble a pharmacokinetic run plan, and decide whether it may run.

What this module is for
-----------------------
The previous input screen presented seven boxes of equal weight — dose, four
rate constants, duration, time step — which implied they all came from the same
place, and in a patient-assessment context implied they came from the medical
report. They do not. This module classifies every input by **where it genuinely
comes from**, and refuses to run when a required input has no legitimate source.

The four sources
----------------
``InputSource`` is the whole point of the module:

* ``PATIENT_REPORT``   — a confirmed field from an uploaded report.
* ``MANUAL_ENTRY``     — typed by the user because no confirmed report value
                         existed. Labelled as such, never as report-derived.
* ``TREATMENT_PROTOCOL`` — the prescribed or planned regimen.
* ``PARAMETER_LIBRARY`` — a cited parameter set.
* ``DERIVED``          — computed from library parameters, with the formula
                         recorded.
* ``SIMULATION_SETTING`` — a numerical control, not a property of the patient
                         or the drug.

A value's source travels with it, so the pre-run summary and the stored record
can both say exactly where each number came from.

The blocking rule
-----------------
If no compatible reviewed parameter set exists for the therapeutic and route,
the plan is **not runnable**. Nothing is substituted, nothing is borrowed from
another drug, route or population, and the missing items are named. This is the
correct outcome, not a gap to be papered over.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .administration import AdministrationRoute, route_spec
from .derivation import DerivationError, derive_rate_constants
from .parameter_library import (
    LIBRARY_VERSION,
    ParameterSet,
    guided_mode_sets,
)

__all__ = [
    "InputSource",
    "InputMode",
    "PlannedInput",
    "DoseBasis",
    "RunPlan",
    "build_plan",
    "RESEARCH_USE_ONLY_NOTICE",
]

RESEARCH_USE_ONLY_NOTICE = (
    "Research Use Only — This simulation does not recommend treatment, "
    "determine an individual dose, or replace clinical pharmacology and "
    "medical judgment."
)


class InputSource(str, enum.Enum):
    PATIENT_REPORT = "patient_report"
    MANUAL_ENTRY = "manual_entry"
    TREATMENT_PROTOCOL = "treatment_protocol"
    PARAMETER_LIBRARY = "parameter_library"
    DERIVED = "derived"
    SIMULATION_SETTING = "simulation_setting"
    EXPERT_OVERRIDE = "expert_override"
    #: True by definition of the route, not taken from any parameter set.
    #: Bioavailability for an intravenous dose is the only current case.
    #: Kept distinct from PARAMETER_LIBRARY because labelling it "from a cited
    #: parameter set" would claim a citation that does not exist -- and for a
    #: blocked combination, no parameter set exists at all.
    ROUTE_DEFINITION = "route_definition"


#: Human labels. Kept here so the API, the UI and the stored record agree.
SOURCE_LABEL: dict[InputSource, str] = {
    InputSource.PATIENT_REPORT: "From medical report (confirmed)",
    InputSource.MANUAL_ENTRY: "Manually entered",
    InputSource.TREATMENT_PROTOCOL: "From treatment protocol",
    InputSource.PARAMETER_LIBRARY: "From cited parameter set",
    InputSource.DERIVED: "Calculated from cited model parameters",
    InputSource.SIMULATION_SETTING: "Simulation setting",
    InputSource.EXPERT_OVERRIDE: "Expert research override",
    InputSource.ROUTE_DEFINITION: "Fixed by administration route",
}


class InputMode(str, enum.Enum):
    GUIDED = "guided"
    EXPERT_RESEARCH = "expert_research"


class DoseBasis(str, enum.Enum):
    FIXED = "fixed"                 # mg
    PER_KG = "per_kg"               # mg/kg
    PER_BSA = "per_bsa"             # mg/m^2


@dataclass(frozen=True)
class PlannedInput:
    """One input, with its origin recorded."""

    name: str
    label: str
    value: float | str | None
    unit: str
    source: InputSource
    #: For report-derived values: the extraction provenance and confirmation.
    report_field: str | None = None
    confirmation_status: str | None = None
    #: For derived values: the formula and its inputs.
    formula: str | None = None
    source_values: dict[str, str] | None = None
    #: Whether the user may edit it in the current mode.
    editable: bool = True

    @property
    def source_label(self) -> str:
        return SOURCE_LABEL[self.source]


@dataclass
class RunPlan:
    """Everything needed to decide whether — and how — a simulation may run."""

    therapeutic: str
    route: AdministrationRoute
    mode: InputMode

    inputs: list[PlannedInput] = field(default_factory=list)
    parameter_set: ParameterSet | None = None
    library_version: str = LIBRARY_VERSION

    runnable: bool = False
    #: Precisely what is missing. Empty when runnable.
    blocking_reasons: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)
    #: Fields the route makes meaningless, so the UI can hide or mark them.
    not_applicable: list[str] = field(default_factory=list)
    #: PK features the selected structure does not represent.
    not_represented: list[str] = field(default_factory=list)

    suitability: str = ""
    model_label: str = ""
    notice: str = RESEARCH_USE_ONLY_NOTICE

    def by_source(self, source: InputSource) -> list[PlannedInput]:
        return [i for i in self.inputs if i.source is source]


def resolve_absolute_dose(
    *, basis: DoseBasis, amount: float,
    body_weight_kg: float | None = None,
    bsa_m2: float | None = None,
) -> tuple[float, str]:
    """Convert a dose in its stated basis to an absolute milligram amount.

    Returns ``(dose_mg, explanation)``. Raises when the covariate the basis
    requires is absent — a weight-based dose without a weight is not a dose, and
    substituting a "typical" 70 kg would silently invent a patient.
    """
    if basis is DoseBasis.FIXED:
        return amount, f"{amount} mg (fixed dose)"
    if basis is DoseBasis.PER_KG:
        if not body_weight_kg or body_weight_kg <= 0:
            raise ValueError(
                "A mg/kg dose requires a body weight. No default weight is "
                "applied, because assuming one would invent a patient "
                "characteristic that changes every reported concentration.")
        return amount * body_weight_kg, (
            f"{amount} mg/kg x {body_weight_kg} kg = "
            f"{amount * body_weight_kg} mg")
    if basis is DoseBasis.PER_BSA:
        if not bsa_m2 or bsa_m2 <= 0:
            raise ValueError(
                "A mg/m^2 dose requires a body surface area. No default is "
                "applied.")
        return amount * bsa_m2, f"{amount} mg/m^2 x {bsa_m2} m^2 = {amount * bsa_m2} mg"
    raise ValueError(f"unsupported dose basis: {basis}")


def build_plan(
    *,
    therapeutic: str,
    route: AdministrationRoute,
    mode: InputMode = InputMode.GUIDED,
    parameter_set: ParameterSet | None = None,
) -> RunPlan:
    """Build the plan for a therapeutic/route combination.

    In guided mode the parameter set is looked up and must be reviewed. In
    expert mode the caller supplies one, and it is labelled as the researcher's
    own input rather than as a platform-validated prediction.
    """
    spec = route_spec(route)
    plan = RunPlan(therapeutic=therapeutic, route=route, mode=mode)
    plan.not_applicable = list(spec.not_applicable_inputs)
    plan.model_label = f"Linear two-compartment, {spec.label.lower()} input"

    # --- simulation settings: always present, always clearly labelled -------
    plan.inputs.extend([
        PlannedInput("duration_h", "Simulation duration", 48.0, "h",
                     InputSource.SIMULATION_SETTING),
        PlannedInput("time_step_h", "Integration time step", 0.01, "h",
                     InputSource.SIMULATION_SETTING),
        PlannedInput("output_interval_h", "Output interval", 0.1, "h",
                     InputSource.SIMULATION_SETTING),
    ])

    # --- bioavailability: a route property for IV, not a free parameter -----
    if not spec.bioavailability_is_free:
        plan.inputs.append(PlannedInput(
            "bioavailability", "Bioavailability (F)",
            spec.fixed_bioavailability, "fraction",
            InputSource.ROUTE_DEFINITION,
            formula="F = 1 by definition of the route",
            source_values={"reason": spec.fixed_bioavailability_reason or ""},
            editable=False,
        ))

    # --- the parameter set --------------------------------------------------
    if mode is InputMode.GUIDED:
        candidates = guided_mode_sets(therapeutic, route)
        chosen = parameter_set or (candidates[0] if candidates else None)
        if chosen is None:
            plan.runnable = False
            plan.blocking_reasons.append(
                f"No reviewed pharmacokinetic parameter set exists for "
                f"{therapeutic} administered by {spec.label.lower()}.")
            plan.missing_inputs = ["CL", "Vc", "Q", "Vp"]
            plan.suitability = (
                f"Not yet operational for this therapeutic/route combination "
                f"({therapeutic} / {spec.label}).")
            plan.warnings.append(
                "No parameters have been substituted, and none have been "
                "copied from another therapeutic, formulation, route or "
                "population. Execution is blocked.")
            plan.warnings.append(
                "A researcher may supply their own cited parameters through "
                "expert research mode. Results from those parameters are "
                "labelled as researcher-supplied, not as platform predictions.")
            return plan
        plan.parameter_set = chosen
    else:
        if parameter_set is None:
            plan.runnable = False
            plan.blocking_reasons.append(
                "Expert research mode requires a parameter set: model type, "
                "values, units, route, source reference and assumptions.")
            plan.missing_inputs = ["parameter_set"]
            plan.suitability = "Awaiting researcher-supplied parameters."
            return plan
        plan.parameter_set = parameter_set
        plan.warnings.append(
            "These parameters were supplied by the researcher. Results are "
            "the researcher's own research output and are not a validated "
            "platform prediction.")

    ps = plan.parameter_set
    assert ps is not None

    # --- route compatibility ------------------------------------------------
    if ps.route is not route:
        plan.runnable = False
        plan.blocking_reasons.append(
            f"Parameter set {ps.id!r} was estimated for "
            f"{route_spec(ps.route).label.lower()} administration and cannot "
            f"be used for {spec.label.lower()}.")
        plan.suitability = "Parameter set incompatible with the selected route."
        return plan

    # --- library parameters -------------------------------------------------
    for name, pv in sorted(ps.parameters.items()):
        plan.inputs.append(PlannedInput(
            name, name, pv.value, pv.unit, InputSource.PARAMETER_LIBRARY,
            source_values={"parameter_set": f"{ps.id}@{ps.version}",
                           "citation": ps.source_citation,
                           "population": ps.population},
            editable=(mode is InputMode.EXPERT_RESEARCH),
        ))

    # --- derived rate constants --------------------------------------------
    try:
        derived = derive_rate_constants(ps)
    except DerivationError as exc:
        plan.runnable = False
        plan.blocking_reasons.append(exc.message)
        if exc.detail:
            plan.warnings.append(exc.detail)
        plan.missing_inputs = list(getattr(exc, "missing", []) or [])
        plan.suitability = "Rate constants could not be derived."
        return plan

    for dc in derived.values():
        plan.inputs.append(PlannedInput(
            dc.name, dc.name, dc.value, dc.unit, InputSource.DERIVED,
            formula=dc.formula, source_values=dc.source_values,
            # Derived constants are never editable in guided mode: editing one
            # would silently break its stated relationship to CL, Vc, Q and Vp.
            editable=(mode is InputMode.EXPERT_RESEARCH),
        ))

    # --- dosing inputs the user must still supply ---------------------------
    still_needed = [n for n in spec.required_dosing_inputs]
    plan.missing_inputs = still_needed
    plan.not_represented = list(ps.not_represented)

    plan.runnable = True
    plan.suitability = (
        f"{ps.model_structure.value.replace('_', ' ').title()} parameters for "
        f"{ps.therapeutic} by {spec.label.lower()} in: {ps.population}.")

    if ps.model_structure.value == "two_compartment_linear" and ps.not_represented:
        plan.warnings.append(
            "Limited exploratory model — not validated for individual dosing "
            "or clinical decision-making.")

    for limitation in ps.limitations:
        plan.warnings.append(limitation)

    return plan
