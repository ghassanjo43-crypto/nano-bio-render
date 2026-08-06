"""Representative inputs for the golden-vector baseline.

Single source of truth: both the capture harness (`capture.py`) and the
regression tests (`test_golden_vectors.py`) import from here, so a vector can
never be captured with one input and asserted with another.

Key-convention warning
----------------------
The legacy code uses two incompatible key conventions, and one function mixes
both. This is preserved verbatim here because the baseline must reflect the code
as it runs, not as it should have been written:

* ``core/scoring.py``      -> CapitalCase (``Size``, ``Charge``, ``Encapsulation``)
* ``utils/design_scorer.py`` -> lowercase (``size``, ``charge``, ``pdi``)
* ``utils/toxicity_model.py`` -> MIXED (``Size``/``Charge``/``PDI``/``Ligand``/
  ``Material`` but ``dose``/``payload``/``payload_amount``)

Any Pydantic schema in Phase 3 must reconcile these deliberately.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# core/scoring.py designs  (CapitalCase convention)
# ---------------------------------------------------------------------------

# The exact defaults the live app seeds into st.session_state.design
# Source: pages/1_Design_Parameters.py:157-182
APP_DEFAULT_DESIGN = {
    "Material": "Lipid NP",
    "Target": "Liver Cells",
    "Size": 100,
    "PDI": 0.15,
    "HydrodynamicSize": 120,
    "Encapsulation": 85,
    "EncapsulationMethod": "Passive Loading",
    "Charge": -5,
    "SurfaceArea": 250,
    "Stability": 85,
    "DegradationTime": 30,
    "CrystallinityIndex": 65,
    "PorosityLevel": "Mesoporous (2-50nm)",
    "PoreSize": 5.0,
    "SurfaceCoating": ["PEG (Stealth)"],
    "CoatingThickness": 2.5,
    "FunctionalGroups": ["-COOH (Carboxyl)"],
    "Hydrophobicity": 1.5,
    "Ligand": "GalNAc",
    "LigandDensity": 60,
    "Receptor": "ASGPR",
    "ReceptorBinding": 10.0,
    "ReleaseProfile": "Sustained (1 week)",
    "ReleasePredictability": 85,
}


def _d(**overrides):
    """APP_DEFAULT_DESIGN with overrides applied."""
    base = dict(APP_DEFAULT_DESIGN)
    base.update(overrides)
    return base


SCORING_DESIGNS = {
    # --- nominal ---
    "app_default": APP_DEFAULT_DESIGN,

    # --- only the three bare-subscript keys: exercises every .get() default ---
    "minimal_required_keys": {"Size": 100, "Charge": -5, "Encapsulation": 85},

    # --- size boundaries (optimum 80-120 nm in core/scoring.py) ---
    "size_50_below_optimal": _d(Size=50),
    "size_79_just_below": _d(Size=79),
    "size_80_lower_bound": _d(Size=80),
    "size_120_upper_bound": _d(Size=120),
    "size_121_just_above": _d(Size=121),
    "size_200_oversized": _d(Size=200),
    "size_320_zero_floor": _d(Size=320),   # drives size_score to its max(0, ...) floor

    # --- charge boundaries (optimum |z| <= 10 mV) ---
    "charge_zero": _d(Charge=0),
    "charge_neg10_bound": _d(Charge=-10),
    "charge_pos10_bound": _d(Charge=10),
    "charge_pos40_high": _d(Charge=40),
    "charge_neg60_extreme": _d(Charge=-60),

    # --- encapsulation ---
    "encap_40_low": _d(Encapsulation=40),
    "encap_100_max": _d(Encapsulation=100),

    # --- PDI ---
    "pdi_zero": _d(PDI=0.0),
    "pdi_045_high": _d(PDI=0.45),
    "pdi_060_floor": _d(PDI=0.60),         # 100 - 0.6*200 = -20 -> clamps to 0

    # --- targeting branches ---
    "ligand_none_passive": _d(Ligand="None"),
    "ligand_unknown_cost_default": _d(Ligand="Anti-CD19"),   # not in ligand_cost_map
    "ligand_density_low": _d(LigandDensity=10),
    "ligand_density_max": _d(LigandDensity=100),
    "receptor_binding_weak": _d(ReceptorBinding=800.0),

    # --- coating branches (list vs str vs empty vs all) ---
    "coating_all_four": _d(SurfaceCoating=[
        "PEG (Stealth)", "Hyaluronic Acid", "Chitosan", "Albumin"]),
    "coating_empty_list": _d(SurfaceCoating=[]),
    "coating_plain_string": _d(SurfaceCoating="PEG (Stealth)"),
    "coating_none_value": _d(SurfaceCoating=None),   # -> defaults to ["PEG (Stealth)"]
    "coating_thickness_zero": _d(CoatingThickness=0),
    "coating_thickness_thick": _d(CoatingThickness=9.0),

    # --- explicit None optionals: exercises the `is not None` guards ---
    "none_valued_optionals": _d(
        SurfaceArea=None, Hydrophobicity=None,
        CrystallinityIndex=None, CoatingThickness=None,
    ),

    # --- surface chemistry extremes ---
    "hydrophobicity_5_toxic": _d(Hydrophobicity=5.0),
    "hydrophobicity_negative": _d(Hydrophobicity=-1.0),
    "crystallinity_20_low": _d(CrystallinityIndex=20),
    "crystallinity_95_high": _d(CrystallinityIndex=95),
    "functional_groups_all": _d(FunctionalGroups=[
        "-COOH (Carboxyl)", "-NH2 (Amino)", "-OH (Hydroxyl)"]),
    "functional_groups_empty": _d(FunctionalGroups=[]),
    "degradation_time_long": _d(DegradationTime=120),
    "stability_low": _d(Stability=40),
}

# Error paths: core/scoring.py uses bare subscripts for these three keys,
# so absence must raise KeyError. Captured as INTENDED (fail loudly, not silently).
SCORING_ERROR_DESIGNS = {
    "missing_Size": {"Charge": -5, "Encapsulation": 85},
    "missing_Charge": {"Size": 100, "Encapsulation": 85},
    "missing_Encapsulation": {"Size": 100, "Charge": -5},
    "empty_design": {},
}

# Custom weight overrides. core/scoring.py:167-170 re-normalises any weight dict
# whose values do not sum to 1.0.
SCORING_WEIGHTS = {
    "default_none": None,
    "already_normalised": {
        "size": 0.18, "charge": 0.14, "encap": 0.18, "pdi": 0.10,
        "hydro": 0.06, "stability": 0.04, "targeting": 0.08,
        "release": 0.04, "surface_area": 0.04, "hydrophobicity": 0.05,
        "crystallinity": 0.05, "coating": 0.05,
    },
    "unnormalised_sums_to_2": {
        "size": 0.36, "charge": 0.28, "encap": 0.36, "pdi": 0.20,
        "hydro": 0.12, "stability": 0.08, "targeting": 0.16,
        "release": 0.08, "surface_area": 0.08, "hydrophobicity": 0.10,
        "crystallinity": 0.10, "coating": 0.10,
    },
    "partial_override_size_only": {"size": 0.50},
    "size_dominant": {
        "size": 1.0, "charge": 0.0, "encap": 0.0, "pdi": 0.0,
        "hydro": 0.0, "stability": 0.0, "targeting": 0.0,
        "release": 0.0, "surface_area": 0.0, "hydrophobicity": 0.0,
        "crystallinity": 0.0, "coating": 0.0,
    },
}

# ---------------------------------------------------------------------------
# utils/pk_model.py  (two-compartment, forward Euler, dt fixed)
# ---------------------------------------------------------------------------
# NOTE: dt=0.1 and the explicit Euler loop ARE the model's numerical identity.
# Do not substitute an adaptive solver during equivalence migration.

PK_PARAM_SETS = {
    "nominal_48h": dict(dose=3.0, kabs=0.5, kel=0.1, k12=0.2, k21=0.05,
                        duration=48.0, dt=0.1),
    "fast_elimination": dict(dose=3.0, kabs=0.5, kel=0.8, k12=0.2, k21=0.05,
                             duration=48.0, dt=0.1),
    "slow_absorption": dict(dose=3.0, kabs=0.05, kel=0.1, k12=0.2, k21=0.05,
                            duration=48.0, dt=0.1),
    "high_peripheral_partition": dict(dose=3.0, kabs=0.5, kel=0.1, k12=0.6,
                                      k21=0.02, duration=48.0, dt=0.1),
    "short_duration_6h": dict(dose=3.0, kabs=0.5, kel=0.1, k12=0.2, k21=0.05,
                              duration=6.0, dt=0.1),
    "zero_dose_edge": dict(dose=0.0, kabs=0.5, kel=0.1, k12=0.2, k21=0.05,
                           duration=48.0, dt=0.1),
    "no_elimination_edge": dict(dose=3.0, kabs=0.5, kel=0.0, k12=0.2, k21=0.05,
                                duration=48.0, dt=0.1),
}

RELEASE_PROFILES = {
    "burst": dict(release_type="burst", burst_fraction=0.2, release_rate=0.1),
    "sustained": dict(release_type="sustained", burst_fraction=0.2, release_rate=0.1),
    "controlled": dict(release_type="controlled", burst_fraction=0.2, release_rate=0.1),
    "unknown_falls_through_to_default": dict(
        release_type="not_a_real_mode", burst_fraction=0.2, release_rate=0.1),
    "sustained_high_rate": dict(release_type="sustained", burst_fraction=0.5,
                                release_rate=0.9),
}

# ---------------------------------------------------------------------------
# utils/toxicity_model.py  (MIXED key convention -- see module docstring)
# ---------------------------------------------------------------------------

TOXICITY_DESIGNS = {
    "nominal": {
        "Size": 100, "Charge": -5, "PDI": 0.15, "Ligand": "GalNAc",
        "Material": "Lipid NP", "dose": 10.0, "payload": "Drug",
        "payload_amount": 1.0,
    },
    "all_defaults_empty_dict": {},
    "small_high_charge": {
        "Size": 20, "Charge": 45, "PDI": 0.40, "Ligand": "None",
        "Material": "Gold NP", "dose": 100.0, "payload": "siRNA",
        "payload_amount": 5.0,
    },
    "large_neutral_low_dose": {
        "Size": 250, "Charge": 0, "PDI": 0.05, "Ligand": "Transferrin",
        "Material": "PLGA", "dose": 0.5, "payload": "mRNA",
        "payload_amount": 0.1,
    },
    "unknown_material_and_ligand": {
        "Size": 100, "Charge": -5, "PDI": 0.15, "Ligand": "Anti-CD19",
        "Material": "Unobtainium NP", "dose": 10.0, "payload": "Peptide",
        "payload_amount": 1.0,
    },
}

# Individual risk functions: (args...) tuples
TOXICITY_RISK_CASES = {
    "size_risk": [(10,), (20,), (50,), (100,), (150,), (250,), (500,)],
    "charge_risk": [(-5, 100), (0, 100), (10, 100), (30, 100), (50, 20), (-50, 20)],
    "dose_risk": [(0.5, 100), (10.0, 100), (50.0, 100), (200.0, 100), (10.0, 20)],
    "pdi_risk": [(0.0,), (0.1,), (0.2,), (0.3,), (0.5,), (0.8,)],
    "ligand_risk": [("GalNAc", -5), ("None", -5), ("Transferrin", 30),
                    ("Anti-CD19", -5), ("RGD Peptide", 0)],
    "payload_risk": [("Drug", 1.0), ("siRNA", 5.0), ("mRNA", 0.1),
                     ("Unknown Payload", 2.0), ("Drug", 0.0)],
    "material_risk": [("Lipid NP", 100), ("PLGA", 100), ("Gold NP", 20),
                      ("Unobtainium NP", 100), ("Lipid NP", 300)],
}

# ---------------------------------------------------------------------------
# utils/design_scorer.py  (lowercase convention; SECONDARY/LEGACY scorer)
# ---------------------------------------------------------------------------

DESIGN_SCORER_DESIGNS = {
    "nominal": {
        "size": 100, "charge": 0, "pdi": 0.15,
        "material": "Lipid Nanoparticle", "ligand": "PEG",
        "payload": "mRNA", "payload_amount": 50,
        "target": "Tumor Tissue (Solid)",
    },
    "all_defaults_empty_dict": {},
    "small_charged": {
        "size": 30, "charge": 25, "pdi": 0.35,
        "material": "Gold Nanoparticle", "ligand": "Folate",
        "payload": "siRNA", "payload_amount": 10,
        "target": "Liver",
    },
    "large_negative": {
        "size": 250, "charge": -30, "pdi": 0.05,
        "material": "PLGA", "ligand": "Transferrin",
        "payload": "Protein", "payload_amount": 90,
        "target": "Brain",
    },
}

# ---------------------------------------------------------------------------
# engine/ inputs  (TrialDesignInputs kwargs)
# ---------------------------------------------------------------------------

ENGINE_DESIGNS = {
    "hccs_pegylated_targeted": dict(
        case_id="GV-ENG-001", disease_code="HCC-S",
        trial_name="HCC-S PEGylated targeted LNP",
        nanoparticle_size_nm=100.0, surface_charge_mv=-5.0,
        peg_surface_coating=True, peg_density_percent=5.0,
        encapsulation_method="passive_loading", payload_drug="Sorafenib",
        payload_loading_percent=85.0, targeting_ligand="GalNAc",
        manufacturing_scale_target="g",
    ),
    "hccs_bare_untargeted": dict(
        case_id="GV-ENG-002", disease_code="HCC-S",
        trial_name="HCC-S bare untargeted",
        nanoparticle_size_nm=100.0, surface_charge_mv=-5.0,
        peg_surface_coating=False, peg_density_percent=0.0,
        encapsulation_method="passive_loading", payload_drug="Sorafenib",
        payload_loading_percent=85.0, targeting_ligand="None",
        manufacturing_scale_target="g",
    ),
    "hccs_oversized_cationic": dict(
        case_id="GV-ENG-003", disease_code="HCC-S",
        trial_name="HCC-S oversized cationic",
        nanoparticle_size_nm=250.0, surface_charge_mv=35.0,
        peg_surface_coating=False, peg_density_percent=0.0,
        encapsulation_method="active_loading", payload_drug="Doxorubicin",
        payload_loading_percent=40.0, targeting_ligand="None",
        manufacturing_scale_target="kg",
    ),
    "hccs_small_at_boundary": dict(
        case_id="GV-ENG-004", disease_code="HCC-S",
        trial_name="HCC-S at 80 nm boundary",
        nanoparticle_size_nm=80.0, surface_charge_mv=0.0,
        peg_surface_coating=True, peg_density_percent=10.0,
        encapsulation_method="passive_loading", payload_drug="siRNA",
        payload_loading_percent=95.0, targeting_ligand="Transferrin",
        manufacturing_scale_target="mg",
    ),
    "pdaci_targeted": dict(
        case_id="GV-ENG-005", disease_code="PDAC-I",
        trial_name="PDAC-I actively targeted",
        nanoparticle_size_nm=80.0, surface_charge_mv=5.0,
        peg_surface_coating=True, peg_density_percent=5.0,
        encapsulation_method="passive_loading", payload_drug="Gemcitabine",
        payload_loading_percent=70.0, targeting_ligand="RGD Peptide",
        manufacturing_scale_target="g",
    ),
    "pdaci_defaults_only": dict(
        case_id="GV-ENG-006", disease_code="PDAC-I",
        trial_name="PDAC-I dataclass defaults",
    ),
}

# Disease codes exercised against config.disease_profiles.get_disease_profile().
# Only HCC-S and PDAC-I are genuinely supported; everything else is the
# DEFECT-D1 silent fallback (see docs/GOLDEN_VECTOR_BASELINE.md).
DISEASE_CODES_SUPPORTED = ["HCC-S", "PDAC-I"]
DISEASE_CODES_UNSUPPORTED = [
    "HCC-MS", "HCC-L",
    "AFP-high HCC", "Immune-active HCC", "Immune-excluded HCC", "Immune-desert HCC",
    "Breast Cancer", "Triple-Negative (ER-, PR-, HER2-)",
    "Lung Cancer", "Colorectal Cancer", "Pancreatic Cancer",
    "", "UNKNOWN", "not-a-disease",
]

# Trial-ID generation: subtype strings the UI can actually produce.
# Only hcc_s / hcc_ms / hcc_l map; the real UI labels yield UNKNOWN (DEFECT-D4).
TRIAL_ID_SUBTYPES_MAPPED = ["hcc_s", "hcc_ms", "hcc_l"]
TRIAL_ID_SUBTYPES_UNMAPPED = [
    "AFP-high HCC", "Immune-desert HCC",
    "Triple-Negative (ER-, PR-, HER2-)", "Ductal Adenocarcinoma", "",
]

# ---------------------------------------------------------------------------
# components/ml_predictor.py  (heuristic fallback path)
# ---------------------------------------------------------------------------

ML_PREDICTOR_DESIGNS = {
    "app_default": APP_DEFAULT_DESIGN,
    "minimal": {"Size": 100, "Charge": -5, "Encapsulation": 85},
    "small_cationic": _d(Size=30, Charge=40),
    "large_anionic": _d(Size=250, Charge=-40),
}
