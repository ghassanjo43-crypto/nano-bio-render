"""Versioned demonstration-scenario fixtures.

WHAT THIS FILE IS
-----------------
The single, typed, versioned source of demonstration **inputs**. Scenario data
lives here rather than scattered through React components so that it can be
validated, tested, seeded into a database and diffed between versions.

WHAT IT MUST NEVER CONTAIN
--------------------------
**Stored or hard-coded scientific RESULTS.** No score, no concentration, no
half-life, no AUC, no assessment verdict appears anywhere below. Every number a
user eventually sees is produced at runtime by the genuine connected engines
from these inputs. A fixture that carried a result would be indistinguishable
from the fabricated-output defects this platform exists to avoid
(DEFECT-D5/D6/D7 in the golden-vector baseline).

`expected_warnings` below is the one place that anticipates engine behaviour. It
is a *teaching note about what to look out for*, rendered as "warnings you should
expect to see", never as the engine's actual output — the real warning list is
always read from the response.

PROVENANCE OF THE INPUT VALUES
------------------------------
The disease / subtype / therapeutic triples are taken **verbatim** from the
application's own curated mapping (`data/disease_drug_mapping.py`, mirrored to
`frontend/src/workflow/diseaseData.ts`). No disease, subtype or drug is invented,
and `test_scenario_mappings_are_valid` proves every triple exists in that mapping.

The nanoparticle and pharmacokinetic values are **synthetic**: they are plausible
values chosen to exercise the engines across their input ranges. They are not
measurements, not literature values for a specific published formulation, and not
a recommended formulation. Where a value was chosen to sit at a documented
threshold of the scoring function, the threshold is cited in `provenance`.

WHAT THESE SCENARIOS ARE NOT
----------------------------
Not patient data. Not clinical data. Not validated experimental data. Not
treatment recommendations. Not successful formulations. No real
patient-identifying information appears anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DEMO_FIXTURE_VERSION",
    "DemoScenario",
    "SCENARIOS",
    "scenario_by_slug",
    "scenario_slugs",
]

#: Version of the fixture set. Bump on ANY change to scenario content, so a
#: stored demo run can be traced to the exact inputs it came from. The seeding
#: command uses this to decide whether a stored template needs refreshing.
DEMO_FIXTURE_VERSION = "demo-scenarios-1.0.0"


@dataclass(frozen=True)
class DemoScenario:
    """One demonstration scenario. Inputs and teaching metadata only."""

    slug: str
    name: str
    purpose: str

    # --- therapeutic context (must exist in the curated mapping) ------------
    disease: str
    subtype: str
    drug: str

    #: Nanoparticle design inputs, keyed by the API's own field names. Only keys
    #: the design endpoint actually accepts may appear; a typo is a test failure.
    design_inputs: dict[str, Any]

    #: Pharmacokinetic inputs, keyed by the PK endpoint's field names. May be
    #: deliberately incomplete — that is the point of scenario 6.
    pk_inputs: dict[str, Any]

    #: Scientific assumptions a reader should hold while interpreting the run.
    assumptions: tuple[str, ...]

    #: Warnings the user should expect to see. NOT the engine's output — the
    #: real list always comes from the response.
    expected_warnings: tuple[str, ...]

    #: Engines that will run for this scenario, and those that will not, with
    #: the reason. Verified against the live module registry by test.
    engines_expected_to_run: tuple[str, ...]
    engines_that_will_not_run: tuple[tuple[str, str], ...]

    #: Where any externally-derived value came from. Empty when every value is
    #: synthetic, which is stated explicitly rather than left blank.
    provenance: tuple[str, ...] = field(default_factory=tuple)

    #: Marks the two technical scenarios, which demonstrate platform behaviour
    #: rather than an indication.
    technical: bool = False

    @property
    def is_pk_runnable(self) -> bool:
        """True when every scientifically required PK input is present."""
        required = ("dose_mg_kg", "kabs_per_h", "kel_per_h", "k12_per_h",
                    "k21_per_h")
        return all(self.pk_inputs.get(k) is not None for k in required)

    @property
    def is_score_runnable(self) -> bool:
        """True when every scientifically required design input is present."""
        required = ("size_nm", "charge_mv", "encapsulation_percent")
        return all(self.design_inputs.get(k) is not None for k in required)


# ---------------------------------------------------------------------------
# Shared text
# ---------------------------------------------------------------------------

_SYNTHETIC = (
    "All nanoparticle and pharmacokinetic values are synthetic demonstration "
    "inputs. They are not measurements and not literature values for any "
    "specific published formulation."
)

_RATE_CONSTANTS = (
    "The pharmacokinetic rate constants are inputs, not predictions. The "
    "two-compartment model does not derive them from the formulation, so the "
    "profile reflects the constants entered rather than the particle described."
)

_DISEASE_INDEPENDENT = (
    "Neither connected engine takes a disease as input. The therapeutic context "
    "is recorded for traceability and does not change any calculated value."
)

_UNIT_NOTE = (
    "Pharmacokinetic outputs are dose-scaled compartment amounts in arbitrary "
    "units. The model has no volume term, so they are not concentrations and "
    "must not be read as ng/mL."
)

#: Engines that genuinely run for every scenario with complete inputs.
_CONNECTED = ("Design impact score (core.scoring.compute_impact)",
              "Pharmacokinetic simulation (utils.pk_model)")

#: Assessment availability is limited by the disease-profile ceiling recorded in
#: docs/MODULE_INVENTORY.md §1: config/disease_profiles.py defines only HCC-S and
#: PDAC-I. For every other indication the assessment engines would silently
#: compute hepatocellular-carcinoma biology (DEFECT-D1), so they are refused.
_ASSESSMENTS_SUPPORTED = (
    "Scientific assessments (engine/ ×5)",
)

_NO_ASSESSMENT_PROFILE = (
    "Scientific assessments",
    "config/disease_profiles.py defines profiles only for hepatocellular "
    "carcinoma (HCC-S) and pancreatic ductal adenocarcinoma (PDAC-I). No "
    "profile exists for this indication, so the assessment engines are not run "
    "— running them would compute another disease's biology under this "
    "indication's name.",
)

_NOT_MIGRATED = (
    ("AI Co-Designer",
     "Optimises against a placeholder objective function "
     "(ai_engine/simulator_adapter.py), so no candidate it produces is "
     "traceable to a genuine calculation."),
    ("Molecular visualisation",
     "The legacy 3-D viewer is not migrated to the React interface."),
    ("ML property prediction",
     "Only a toxicity model exists in models_store/; uptake and particle size "
     "silently fall back to heuristics in the legacy code."),
)

_REGULATORY_BLOCKED = (
    "Regulatory verdict",
    "RegulatoryEngine.verdict_available is False pending calibration: the "
    "favourable disease-fit threshold is uncalibrated and unreachable "
    "(ceiling 68.33).",
)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
# Requested coverage was breast, lung, colorectal, pancreatic and prostate.
# The curated mapping contains NO prostate indication, so — per the instruction
# to adapt to the genuine mappings and never invent a combination — the fifth
# indication scenario uses Liver Cancer (HCC), which is the remaining available
# indication and additionally one of the two with a genuine assessment profile.

SCENARIOS: tuple[DemoScenario, ...] = (

    # ---------------------------------------------------------------- 1. breast
    DemoScenario(
        slug="breast-her2-targeted",
        name="Breast cancer — HER2-targeted stealth nanoparticle",
        purpose=(
            "Demonstrates a well-formed, actively-targeted design running the "
            "full connected path: design impact score plus a complete "
            "pharmacokinetic profile. Use it to see what a clean run looks like "
            "before exploring the edge cases."
        ),
        disease="Breast Cancer",
        subtype="HER2-enriched (ER-, PR-, HER2+)",
        drug="Trastuzumab (Herceptin)",
        design_inputs={
            "size_nm": 95,
            "charge_mv": -8,
            "encapsulation_percent": 88,
            "pdi": 0.12,
            "hydrodynamic_size_nm": 112,
            "surface_coating": ["PEG (Stealth)"],
            "coating_thickness_nm": 3.0,
            "surface_area_nm2": 280,
            "hydrophobicity_logp": 1.2,
            "crystallinity_index": 60,
            "functional_groups": ["-COOH (Carboxyl)"],
            "ligand": "Anti-HER2",
            "ligand_density_percent": 55,
            "receptor_binding_kd_nm": 8,
            "stability_percent": 90,
            "degradation_time_days": 28,
            "release_predictability_percent": 88,
        },
        pk_inputs={
            "dose_mg_kg": 4.0,
            "kabs_per_h": 0.4,
            "kel_per_h": 0.06,
            "k12_per_h": 0.25,
            "k21_per_h": 0.08,
            "duration_h": 72,
        },
        assumptions=(
            _SYNTHETIC,
            _RATE_CONSTANTS,
            _DISEASE_INDEPENDENT,
            _UNIT_NOTE,
            "Size 95 nm and zeta -8 mV sit inside the scoring function's "
            "documented optimum bands, so this design is expected to score well "
            "on those components.",
        ),
        expected_warnings=(
            "Optional design fields not supplied will be reported as defaulted.",
            "A note that pharmacokinetic outputs are in arbitrary dose-scaled units.",
        ),
        engines_expected_to_run=_CONNECTED,
        engines_that_will_not_run=(_NO_ASSESSMENT_PROFILE,) + _NOT_MIGRATED,
        provenance=(
            "Size optimum 80–120 nm and zeta optimum ±10 mV are the documented "
            "bands of core/scoring.py (see docs/scoring_system.md).",
            "All other values are synthetic.",
        ),
    ),

    # ------------------------------------------------------------------ 2. lung
    DemoScenario(
        slug="lung-nsclc-checkpoint",
        name="Lung cancer — NSCLC passive-targeting carrier",
        purpose=(
            "A passively-targeted design with no ligand, to contrast with the "
            "actively-targeted breast scenario. Shows how the scoring function "
            "reports its fixed passive-targeting baseline, and how a faster "
            "elimination constant shortens the pharmacokinetic profile."
        ),
        disease="Lung Cancer",
        subtype="Non-Small Cell Lung Cancer (NSCLC)",
        drug="Pembrolizumab",
        design_inputs={
            "size_nm": 110,
            "charge_mv": -12,
            "encapsulation_percent": 74,
            "pdi": 0.18,
            "surface_coating": ["PEG (Stealth)"],
            "coating_thickness_nm": 2.5,
            "hydrophobicity_logp": 1.8,
            "crystallinity_index": 65,
            "stability_percent": 82,
            "degradation_time_days": 21,
            "release_predictability_percent": 80,
        },
        pk_inputs={
            "dose_mg_kg": 2.0,
            "kabs_per_h": 0.6,
            "kel_per_h": 0.18,
            "k12_per_h": 0.30,
            "k21_per_h": 0.10,
            "duration_h": 48,
        },
        assumptions=(
            _SYNTHETIC,
            _RATE_CONSTANTS,
            _DISEASE_INDEPENDENT,
            _UNIT_NOTE,
            "No targeting ligand is specified, so the scoring function applies "
            "its fixed passive-targeting baseline of 60/100 for the targeting "
            "component. The derivation of that constant is an open scientific "
            "question (Q7 in docs/SCORING_CANONICALIZATION.md).",
        ),
        expected_warnings=(
            "A warning that no targeting ligand was specified and the passive "
            "baseline was applied.",
            "Defaulted optional fields reported explicitly.",
        ),
        engines_expected_to_run=_CONNECTED,
        engines_that_will_not_run=(_NO_ASSESSMENT_PROFILE,) + _NOT_MIGRATED,
        provenance=(
            "The 60/100 passive-targeting baseline is a documented constant of "
            "core/scoring.py, not a value chosen here.",
            "All input values are synthetic.",
        ),
    ),

    # ------------------------------------------------------------ 3. colorectal
    DemoScenario(
        slug="colorectal-msi-high",
        name="Colorectal cancer — MSI-H carrier with alternative coating",
        purpose=(
            "Uses a non-PEG coating and a positive surface charge to show how "
            "the scoring function penalises a zeta potential outside its "
            "optimum band, and how coating choice changes the coating "
            "sub-score. Useful for comparing against the breast scenario."
        ),
        disease="Colorectal Cancer",
        subtype="Microsatellite Unstable (MSI-H)",
        drug="Pembrolizumab",
        design_inputs={
            "size_nm": 140,
            "charge_mv": 18,
            "encapsulation_percent": 66,
            "pdi": 0.24,
            "surface_coating": ["Chitosan"],
            "coating_thickness_nm": 4.0,
            "hydrophobicity_logp": 2.4,
            "crystallinity_index": 55,
            "functional_groups": ["-NH2 (Amino)"],
            "stability_percent": 74,
            "degradation_time_days": 45,
            "release_predictability_percent": 70,
        },
        pk_inputs={
            "dose_mg_kg": 6.0,
            "kabs_per_h": 0.35,
            "kel_per_h": 0.12,
            "k12_per_h": 0.45,
            "k21_per_h": 0.06,
            "duration_h": 96,
        },
        assumptions=(
            _SYNTHETIC,
            _RATE_CONSTANTS,
            _DISEASE_INDEPENDENT,
            _UNIT_NOTE,
            "Zeta +18 mV lies outside the documented ±10 mV optimum, so the "
            "charge sub-score is expected to be penalised. This is a property "
            "of the scoring rules, not a safety finding.",
            "A high k_12 relative to k_21 drives accumulation in the peripheral "
            "compartment; the reported accumulation ratio is a model output, "
            "not evidence of tissue targeting.",
        ),
        expected_warnings=(
            "A passive-targeting warning (no ligand specified).",
            "Defaulted optional fields reported explicitly.",
        ),
        engines_expected_to_run=_CONNECTED,
        engines_that_will_not_run=(_NO_ASSESSMENT_PROFILE,) + _NOT_MIGRATED,
        provenance=(
            "Charge optimum ±10 mV and the coating bonus table (PEG +30, "
            "hyaluronic acid +20, chitosan +15, albumin +10) are documented "
            "constants of core/scoring.py.",
            "All input values are synthetic.",
        ),
    ),

    # ------------------------------------------------------------ 4. pancreatic
    DemoScenario(
        slug="pancreatic-pdac-stroma",
        name="Pancreatic cancer — PDAC small-particle carrier",
        purpose=(
            "One of only two indications with a genuine disease profile in "
            "config/disease_profiles.py (PDAC-I). Uses a smaller particle and a "
            "slow elimination constant to produce a long circulation profile, "
            "and demonstrates a run where the terminal half-life may not be "
            "determinable inside the simulated window."
        ),
        disease="Pancreatic Cancer",
        subtype="Ductal Adenocarcinoma",
        drug="Abraxane (Albumin-bound Paclitaxel)",
        design_inputs={
            "size_nm": 68,
            "charge_mv": -4,
            "encapsulation_percent": 81,
            "pdi": 0.14,
            "hydrodynamic_size_nm": 84,
            "surface_coating": ["Albumin"],
            "coating_thickness_nm": 2.0,
            "surface_area_nm2": 320,
            "hydrophobicity_logp": 2.9,
            "crystallinity_index": 48,
            "ligand": "Transferrin",
            "ligand_density_percent": 40,
            "receptor_binding_kd_nm": 25,
            "stability_percent": 78,
            "degradation_time_days": 60,
            "release_predictability_percent": 76,
        },
        pk_inputs={
            "dose_mg_kg": 5.0,
            "kabs_per_h": 0.25,
            "kel_per_h": 0.02,
            "k12_per_h": 0.15,
            "k21_per_h": 0.04,
            "duration_h": 120,
        },
        assumptions=(
            _SYNTHETIC,
            _RATE_CONSTANTS,
            _DISEASE_INDEPENDENT,
            _UNIT_NOTE,
            "Size 68 nm is below the documented 80–120 nm optimum, so the size "
            "sub-score is expected to be penalised.",
            "A very low elimination constant may mean the central compartment "
            "never falls to half its peak inside the window, in which case the "
            "half-life is reported as not determined rather than estimated.",
        ),
        expected_warnings=(
            "Possibly a warning that the terminal half-life could not be "
            "determined within the simulated window.",
            "Defaulted optional fields reported explicitly.",
        ),
        engines_expected_to_run=_CONNECTED,
        engines_that_will_not_run=(_REGULATORY_BLOCKED,) + _NOT_MIGRATED,
        provenance=(
            "Size optimum 80–120 nm is a documented band of core/scoring.py.",
            "PDAC-I is a genuine profile in config/disease_profiles.py.",
            "All input values are synthetic.",
        ),
    ),

    # ----------------------------------------------------------------- 5. liver
    DemoScenario(
        slug="liver-hcc-galnac",
        name="Liver cancer (HCC) — GalNAc hepatocyte-targeted particle",
        purpose=(
            "The other indication with a genuine disease profile (HCC-S). Uses "
            "GalNAc/ASGPR hepatocyte targeting and sits close to the centre of "
            "every documented optimum band, so it serves as the reference point "
            "for comparison against the other scenarios."
        ),
        disease="Liver Cancer (HCC)",
        subtype="AFP-high HCC",
        drug="Sorafenib",
        design_inputs={
            "size_nm": 100,
            "charge_mv": -5,
            "encapsulation_percent": 85,
            "pdi": 0.15,
            "hydrodynamic_size_nm": 120,
            "surface_coating": ["PEG (Stealth)"],
            "coating_thickness_nm": 2.5,
            "surface_area_nm2": 250,
            "hydrophobicity_logp": 1.5,
            "crystallinity_index": 65,
            "functional_groups": ["-COOH (Carboxyl)"],
            "ligand": "GalNAc",
            "ligand_density_percent": 60,
            "receptor_binding_kd_nm": 10,
            "stability_percent": 85,
            "degradation_time_days": 30,
            "release_predictability_percent": 85,
        },
        pk_inputs={
            "dose_mg_kg": 3.0,
            "kabs_per_h": 0.5,
            "kel_per_h": 0.1,
            "k12_per_h": 0.2,
            "k21_per_h": 0.05,
            "duration_h": 48,
            "time_step_h": 0.1,
        },
        assumptions=(
            _SYNTHETIC,
            _RATE_CONSTANTS,
            _DISEASE_INDEPENDENT,
            _UNIT_NOTE,
            "Every design value sits inside the documented optimum band, so "
            "this scenario is the least-penalised of the five and is intended "
            "as a comparison baseline.",
        ),
        expected_warnings=(
            "Few or no interpretation warnings, since almost every optional "
            "field is supplied.",
        ),
        engines_expected_to_run=_CONNECTED,
        engines_that_will_not_run=(_REGULATORY_BLOCKED,) + _NOT_MIGRATED,
        provenance=(
            "These design values are the legacy application's own documented "
            "defaults for the 23-field design schema "
            "(pages/1_Design_Parameters.py:157-182), reused here so the "
            "scenario is directly comparable with the legacy baseline.",
            "The PK values are the nominal golden-vector parameter set from "
            "tests/golden_vectors/inputs.py::PK_PARAM_SETS['nominal_48h'].",
        ),
    ),

    # ---------------------------------------------------- 6. technical: blocked
    DemoScenario(
        slug="technical-incomplete-inputs",
        name="Technical — incomplete design, execution blocked",
        purpose=(
            "Demonstrates that the platform refuses to calculate rather than "
            "filling gaps. Encapsulation efficiency and three of the five "
            "pharmacokinetic inputs are deliberately absent. Loading this "
            "scenario should leave the run action blocked, and the results page "
            "should report an honest empty state rather than a partial or "
            "assumed profile."
        ),
        disease="Breast Cancer",
        subtype="Triple-Negative (ER-, PR-, HER2-)",
        drug="Paclitaxel",
        design_inputs={
            "size_nm": 105,
            "charge_mv": -6,
            # encapsulation_percent deliberately omitted -> score is blocked
            "pdi": 0.16,
            "surface_coating": ["PEG (Stealth)"],
        },
        pk_inputs={
            "dose_mg_kg": 3.0,
            "kabs_per_h": 0.5,
            # kel_per_h, k12_per_h, k21_per_h deliberately omitted
        },
        assumptions=(
            _SYNTHETIC,
            "This scenario exists to demonstrate validation behaviour. It is "
            "not a formulation proposal.",
            "Encapsulation efficiency is a scientifically required input to the "
            "scoring function and is never defaulted; omitting it must block "
            "the calculation.",
            "Three of the four pharmacokinetic rate constants are absent, so "
            "the two-compartment model must not run at all.",
        ),
        expected_warnings=(
            "A required-field validation message on encapsulation efficiency.",
            "A statement that the pharmacokinetic simulation will not run "
            "because its required inputs are incomplete.",
        ),
        engines_expected_to_run=(),
        engines_that_will_not_run=(
            ("Design impact score",
             "Encapsulation efficiency is required and was not supplied. The "
             "engine is not called; no score is produced."),
            ("Pharmacokinetic simulation",
             "Three of the four rate constants are absent. The engine is not "
             "called; no curve, half-life or AUC is produced."),
            _NO_ASSESSMENT_PROFILE,
        ) + _NOT_MIGRATED,
        provenance=("All values are synthetic; the omissions are deliberate.",),
        technical=True,
    ),

    # --------------------------------------------------- 7. technical: boundary
    DemoScenario(
        slug="technical-boundary-values",
        name="Technical — boundary values, warnings without bypass",
        purpose=(
            "Every input sits at or near the extreme end of its accepted range, "
            "while remaining valid. Demonstrates that the platform surfaces "
            "scientific warnings — a very large particle, a strongly positive "
            "charge, a coarse integration step — without silently clamping any "
            "value or skipping validation. The run proceeds and the warnings "
            "are the engine's own."
        ),
        disease="Colorectal Cancer",
        subtype="Adenocarcinoma",
        drug="Irinotecan",
        design_inputs={
            "size_nm": 400,
            "charge_mv": 45,
            "encapsulation_percent": 100,
            "pdi": 0.95,
            "hydrodynamic_size_nm": 900,
            "surface_coating": [],
            "coating_thickness_nm": 0,
            "surface_area_nm2": 0,
            "hydrophobicity_logp": 9.5,
            "crystallinity_index": 0,
            "ligand_density_percent": 100,
            "receptor_binding_kd_nm": 0,
            "stability_percent": 0,
            "degradation_time_days": 0,
            "release_predictability_percent": 0,
        },
        pk_inputs={
            "dose_mg_kg": 100.0,
            "kabs_per_h": 5.0,
            "kel_per_h": 2.0,
            "k12_per_h": 2.0,
            "k21_per_h": 0.01,
            "duration_h": 168,
            "time_step_h": 1.0,
        },
        assumptions=(
            _SYNTHETIC,
            "Every value is at or near a documented bound. This is a stress "
            "test of the validation and warning paths, not a formulation "
            "proposal, and it should not be read as a design recommendation.",
            "A 1-hour integration step is large relative to rate constants of "
            "2–5 per hour. Explicit forward-Euler integration is expected to be "
            "inaccurate in this regime; the engine reports that rather than "
            "correcting it, and the returned numbers are still exactly what the "
            "model produced.",
            "Results computed at a non-default integration step are not "
            "interchangeable with results at the reference 0.1-hour step.",
        ),
        expected_warnings=(
            "A stiffness warning that the time step is large relative to the "
            "fastest rate constant.",
            "A warning that a non-default integration step was used and results "
            "are not interchangeable.",
            "A passive-targeting warning (no ligand).",
            "A note that surface coating was supplied as an empty list rather "
            "than defaulted.",
        ),
        engines_expected_to_run=_CONNECTED,
        engines_that_will_not_run=(_NO_ASSESSMENT_PROFILE,) + _NOT_MIGRATED,
        provenance=(
            "The bounds exercised here are the legacy Streamlit widget ranges "
            "reproduced in the API schemas (modules/design.py, "
            "modules/simulation.py).",
            "All input values are synthetic.",
        ),
        technical=True,
    ),
)


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def scenario_slugs() -> tuple[str, ...]:
    return tuple(s.slug for s in SCENARIOS)


def scenario_by_slug(slug: str) -> DemoScenario | None:
    for s in SCENARIOS:
        if s.slug == slug:
            return s
    return None
