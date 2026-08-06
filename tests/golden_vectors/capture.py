"""Golden-vector capture harness.

Runs every active scientific function in the *current* codebase against the
representative inputs in ``inputs.py`` and writes a machine-readable baseline to
``baseline.json``.

Run it from the repository root:

    python -m tests.golden_vectors.capture

Design rules
------------
1. **Read-only.** Nothing here writes to a real application database. The one
   DB-backed path (trial-ID generation) is redirected to a temporary directory.
2. **Deterministic.** Every captured function was verified free of ``random`` and
   ``uuid``. Exactly two wall-clock reads exist and both are normalised to a
   sentinel: ``datetime.now()`` at
   ``reports/scientific_report_generator.py:148`` and ``pd.Timestamp.now()`` at
   ``components/ml_predictor.py:412``. The second is easy to miss when grepping
   for ``datetime.now``.
3. **Classified.** Every vector carries ``classification`` of either
   ``intended`` or ``known_defect``. Known defects are recorded so that change
   is *detectable*, never because the behaviour is correct. See
   ``KNOWN_DEFECTS`` below and docs/GOLDEN_VECTOR_BASELINE.md.
4. **Full float precision.** ``json`` serialises Python floats with ``repr``,
   which round-trips exactly, so captured values are bit-identical on reload.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import os
import platform
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"

# Sentinel replacing the one non-deterministic value in the codebase.
TIMESTAMP_SENTINEL = "<NORMALISED_TIMESTAMP>"

# ---------------------------------------------------------------------------
# Known defects. Recorded for change-detection ONLY.
# These must never be treated as required target behaviour (Phase 2, item 5).
# ---------------------------------------------------------------------------
#: Defects CORRECTED in Phase 2 Step 1. Their vectors were reclassified from
#: `known_defect` to `intended`. The pre-correction evidence is preserved
#: verbatim and immutably in `baseline_step0_2026-07-30_legacy.json`; it is never
#: silently overwritten. Every reclassification is explained in
#: docs/GOLDEN_VECTOR_BASELINE.md section 6 (vector retirement log).
RESOLVED_DEFECTS = {
    "DEFECT-D8": (
        "CORRECTED in Step 1 under DECISION 5. `manufacturing_complexity` is now "
        "an explicit integer count in 0..2 over normalised inputs "
        "(engine/input_normalization.py), replacing `bool + str`. "
        "RegulatoryEngine.CALCULATION_VERSION = 2.0.0. Reclassified: the six "
        "`DEFECT.regulatory.*` vectors (status raised -> ok), the six "
        "`BLOCKED.confidence.*` vectors (replaced by real "
        "`confidence.*` vectors) and the two `DEFECT.report.*` vectors "
        "(status raised -> ok). Legacy evidence: baseline_step0 archive."
    ),
    "DEFECT-D9": (
        "CORRECTED in Step 1. `compute_impact()`, `get_recommendations()` and "
        "`regulatory_checklist()` now share one null contract via "
        "`_optional_float` / `_optional_value`: an absent key and a "
        "present-but-None value are equivalent. Verified exhaustively -- 21 "
        "optional keys x 3 functions = 63 consistency checks. The fix proved "
        "BROADER than first reported: compute_impact itself was None-unsafe for "
        "PDI, HydrodynamicSize, Stability, DegradationTime, LigandDensity, "
        "ReceptorBinding and ReleasePredictability, and a present-but-None "
        "'Ligand' was treated as a PRESENT ligand. Required keys "
        "(Size/Charge/Encapsulation) still raise KeyError -- never silently "
        "replaced by favourable defaults."
    ),
    "DEFECT-D10": (
        "PARTIALLY CORRECTED in Step 1 under DECISION 6. The field-name error is "
        "fixed (`disease_profile.name` -> `disease_profile.disease_name`) in all "
        "FIVE live occurrences, not the one originally reported. The favourable "
        "verdict remains DISABLED "
        "(RegulatoryEngine.FAVOURABLE_VERDICT_ENABLED = False): the >70 threshold "
        "is uncalibrated and unreachable (observed ceiling 68.33 over 1,792 "
        "combinations). Scores were NOT rescaled and the threshold was NOT "
        "lowered. Callers receive verdict_available=False and "
        "verdict_status='calibration_required'. Still awaiting a scientific "
        "calibration decision."
    ),
    "DEFECT-D11-partial": (
        "auth.py:171 `_reset_admin_session()` was removed by the 2026-07-30 "
        "security containment. design_persistence import-time write and the "
        "duplicate auth init_db() are addressed in Step 1 -- see the "
        "import_side_effects section."
    ),
}

#: Masked bugs that only became reachable once DEFECT-D8 stopped crashing first.
#: All were mechanical wrong-name / wrong-object references, fixed in Step 1
#: without inventing any scientific content.
UNMASKED_BY_D8_FIX = {
    "engine/mechanistic_engine.py:86": "disease_profile.name -> .disease_name",
    "engine/mechanistic_engine.py:369": "disease_profile.name -> .disease_name",
    "engine/regulatory_engine.py:487": "disease_profile.name -> .disease_name",
    "engine/regulatory_engine.py:596": "disease_profile.name -> .disease_name",
    "reports/scientific_report_generator.py:186":
        "full_report.disease_profile.name -> .disease_name",
    "reports/scientific_report_generator.py:127":
        "assumed all six engine results expose `.basis`, but only PredictionBasis "
        "declares it; four modules raised AttributeError. No basis is invented -- "
        "absence is now reported explicitly.",
    "reports/scientific_report_generator.py:286":
        "regulatory_assessment.gmp_pathway_readiness -> "
        "manufacturability_assessment.gmp_pathway_readiness (field belongs to "
        "ManufacturabilityProfile, not RegulatoryAssessment)",
}

KNOWN_DEFECTS = {
    "DEFECT-D1": (
        "config.disease_profiles.get_disease_profile() silently substitutes the "
        "HCC-S profile for any unrecognised disease code, so an assessment for a "
        "different disease is computed against hepatocellular-carcinoma biology "
        "and labelled with the user's selection. Per DECISION 1 the replacement "
        "must block the assessment and return a structured unsupported-model "
        "status instead."
    ),
    "DEFECT-D2": (
        "pages/2_Run_Simulation.py:314-323 sets the user-visible Overall Score to "
        "one of three hard-coded constants (92/89/82) by bucketing uptake "
        "efficiency. Not a calculation. Per DECISION 2 it is replaced and recorded "
        "only as legacy_overall_score."
    ),
    "DEFECT-D3": (
        "pages/2_Run_Simulation.py:337-338 returns overall_score=89 ('Good') from "
        "the exception handler, so any failure yields a favourable score. Per "
        "DECISION 2 no failure may produce a favourable numerical score."
    ),
    "DEFECT-D4": (
        "modules.trial_registry maps only hcc_s/hcc_ms/hcc_l, so the disease "
        "subtypes the UI actually produces are filed under trial ID 'UNKNOWN'."
    ),
    "DEFECT-D5": (
        "components.ml_predictor looks for models/{task}_model.pkl while the 57 "
        "trained bundles live in models_store/ under different names. No model "
        "ever loads; heuristic estimates are returned and surfaced under an 'ML "
        "PREDICTIONS' heading with the '(Using Heuristic)' disclosure collapsed "
        "by default (expanded=False)."
    ),
    "DEFECT-D6": (
        "pages/7_AI_Co_Designer.py:364-373 renders a hard-coded pandas DataFrame "
        "of five 'Mock candidate designs' with fabricated scores "
        "(94.2/91.5/89.8/87.3/84.9) presented as AI optimisation output. No "
        "optimisation runs; ai_engine is un-importable (DEFECT-D7)."
    ),
    "DEFECT-D7": (
        "ai_engine/__init__.py:52 imports 'nanobio_studio.core.types', a package "
        "layout that does not exist in this repository (root has core/types.py). "
        "The whole ai_engine package -- including the only optuna usage -- is "
        "un-importable, so it cannot be golden-vectored at all."
    ),
    "DEFECT-D8": (
        "engine/regulatory_engine.py:224 evaluates "
        "'design_inputs.peg_surface_coating + design_inputs.targeting_ligand', "
        "i.e. bool + str, which raises TypeError unconditionally. "
        "RegulatoryEngine.assess_regulatory_position() therefore fails for EVERY "
        "input. Because ConfidenceEngine.calculate_confidence_profile() consumes "
        "the regulatory result, and ScientificReportGenerator.generate_full_report() "
        "chains all five engines, 2 of the 6 engines and the entire scientific "
        "report generator are non-functional in the legacy application. "
        "The intended semantics are ambiguous (a truthiness check on 'has PEG or "
        "has a ligand', or a count of complexity factors) and MUST NOT be guessed: "
        "see the open question in docs/GOLDEN_VECTOR_BASELINE.md."
    ),
    "DEFECT-D9": (
        "core/scoring.py::get_recommendations() reads optional numeric fields with "
        "float(design.get(key, default)), which raises TypeError when the key is "
        "present but None. compute_impact() guards the same fields with an "
        "'is not None' check, so the two functions disagree about None-handling "
        "for identical input."
    ),
    "DEFECT-D11": (
        "Three modules create or mutate a real SQLite database as an import-time "
        "side effect, before any configuration or path override can apply: "
        "auth.py:88 (init_db), auth.py:171 (_reset_admin_session, whose own comment "
        "says 'Remove in production'), and design_persistence.py:568 "
        "(init_design_db, which writes a ~36 KB nano_bio.db into the current "
        "working directory on a bare import). This makes the modules untestable "
        "without filesystem side effects and is incompatible with Render's "
        "ephemeral filesystem. Database initialisation must become an explicit, "
        "callable step in the FastAPI lifespan, not an import."
    ),
    "DEFECT-D10": (
        "engine/regulatory_engine.py:216 reads 'disease_profile.name', but "
        "DiseaseProfile has no 'name' field (it is 'disease_name'), so this branch "
        "would raise AttributeError. It is currently unreachable: a sweep of 1,792 "
        "parameter combinations across both supported diseases found the maximum "
        "achievable disease_fit.overall_fit_score to be 68.33, never exceeding the "
        "'> 70' threshold that guards it. Two consequences: (a) the AttributeError "
        "is a masked latent bug, and (b) the higher-confidence 'predicted' "
        "regulatory language level is unreachable, so disease-fit can never return "
        "a favourable verdict."
    ),
}


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _hash_floats(values) -> str:
    """Stable SHA-256 over a float sequence at full repr precision."""
    h = hashlib.sha256()
    for v in values:
        h.update(repr(float(v)).encode("ascii"))
        h.update(b",")
    return h.hexdigest()


def normalise(obj, _depth: int = 0):
    """Convert an arbitrary result into a JSON-safe, comparable structure."""
    if _depth > 24:
        return {"__truncated__": "max depth exceeded"}

    # numpy is optional at this level but always present in practice
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        np = None

    if obj is None or isinstance(obj, (bool, int, str)):
        return obj

    if isinstance(obj, float):
        # Preserve non-finite values explicitly rather than emitting invalid JSON.
        if obj != obj:
            return {"__float__": "nan"}
        if obj in (float("inf"), float("-inf")):
            return {"__float__": "inf" if obj > 0 else "-inf"}
        return obj

    if np is not None:
        if isinstance(obj, np.ndarray):
            flat = obj.ravel().tolist()
            n = len(flat)
            idx = sorted({0, 1, 2, n // 4, n // 2, (3 * n) // 4, n - 2, n - 1}
                         & set(range(n))) if n else []
            return {
                "__ndarray__": {
                    "shape": list(obj.shape),
                    "dtype": str(obj.dtype),
                    "length": n,
                    "sha256": _hash_floats(flat),
                    "samples": {str(i): normalise(flat[i], _depth + 1) for i in idx},
                }
            }
        if isinstance(obj, np.generic):
            return normalise(obj.item(), _depth + 1)

    if isinstance(obj, enum.Enum):
        return {"__enum__": type(obj).__name__, "value": normalise(obj.value, _depth + 1)}

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out = {"__dataclass__": type(obj).__name__}
        for f in dataclasses.fields(obj):
            out[f.name] = normalise(getattr(obj, f.name), _depth + 1)
        return out

    if isinstance(obj, dict):
        return {str(k): normalise(v, _depth + 1) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        seq = sorted(obj, key=repr) if isinstance(obj, set) else obj
        return [normalise(v, _depth + 1) for v in seq]

    # pandas DataFrame / Series
    mod = type(obj).__module__ or ""
    if mod.startswith("pandas"):
        try:
            return {"__pandas__": type(obj).__name__,
                    "records": normalise(json.loads(obj.to_json(orient="records"
                                                                if hasattr(obj, "columns")
                                                                else "index")),
                                         _depth + 1)}
        except Exception as exc:  # pragma: no cover
            return {"__pandas_unserialisable__": f"{type(exc).__name__}: {exc}"}

    if isinstance(obj, bytes):
        return {"__bytes__": {"length": len(obj),
                              "sha256": hashlib.sha256(obj).hexdigest()}}

    return {"__repr__": repr(obj)}


def _normalise_timestamps(node):
    """Replace ISO-8601-ish strings with the sentinel (report generator only)."""
    if isinstance(node, dict):
        return {k: (TIMESTAMP_SENTINEL
                    if isinstance(v, str) and _looks_like_iso(v)
                    else _normalise_timestamps(v))
                for k, v in node.items()}
    if isinstance(node, list):
        return [_normalise_timestamps(v) for v in node]
    if isinstance(node, str) and _looks_like_iso(node):
        return TIMESTAMP_SENTINEL
    return node


def _looks_like_iso(s: str) -> bool:
    return (len(s) >= 19 and s[4] == "-" and s[7] == "-"
            and s[10] in "T " and s[13] == ":" and s[16] == ":")


# ---------------------------------------------------------------------------
# Vector recording
# ---------------------------------------------------------------------------

class Recorder:
    def __init__(self):
        self.vectors: list[dict] = []
        self.errors: list[str] = []

    def record(self, vector_id, module, function, inputs, call, *,
               classification="intended", defect_id=None, notes=None,
               assumptions=None, expect_exception=False,
               normalise_timestamps=False):
        entry = {
            "id": vector_id,
            "module": module,
            "function": function,
            "classification": classification,
            "inputs": normalise(inputs),
        }
        if defect_id:
            entry["defect_id"] = defect_id
            entry["defect_description"] = KNOWN_DEFECTS[defect_id]
        if notes:
            entry["notes"] = notes
        if assumptions:
            entry["assumptions"] = assumptions

        try:
            result = call()
        except Exception as exc:
            entry["status"] = "raised"
            entry["exception"] = {"type": type(exc).__name__, "message": str(exc)}
            entry["output"] = None
            if not expect_exception:
                self.errors.append(
                    f"{vector_id}: unexpected {type(exc).__name__}: {exc}")
        else:
            entry["status"] = "ok"
            out = normalise(result)
            if normalise_timestamps:
                out = _normalise_timestamps(out)
            entry["output"] = out
            if expect_exception:
                self.errors.append(
                    f"{vector_id}: expected an exception but the call succeeded")

        self.vectors.append(entry)
        return entry


# ---------------------------------------------------------------------------
# Capture sections
# ---------------------------------------------------------------------------

def capture_core_scoring(rec):
    from core import scoring
    from tests.golden_vectors import inputs as I

    for name, design in I.SCORING_DESIGNS.items():
        rec.record(f"core.compute_impact::{name}", "core.scoring",
                   "compute_impact", {"design": design, "weights": None},
                   lambda d=design: scoring.compute_impact(dict(d)))

    for wname, weights in I.SCORING_WEIGHTS.items():
        rec.record(f"core.compute_impact::app_default+weights={wname}",
                   "core.scoring", "compute_impact",
                   {"design": I.APP_DEFAULT_DESIGN, "weights": weights},
                   lambda w=weights: scoring.compute_impact(
                       dict(I.APP_DEFAULT_DESIGN), w),
                   notes=("core/scoring.py:167-170 re-normalises any weight dict "
                          "whose values do not sum to 1.0"))

    # Error paths: bare subscripts must raise, not silently default.
    for name, design in I.SCORING_ERROR_DESIGNS.items():
        rec.record(f"core.compute_impact::error::{name}", "core.scoring",
                   "compute_impact", {"design": design},
                   lambda d=design: scoring.compute_impact(dict(d)),
                   expect_exception=True,
                   notes=("Size/Charge/Encapsulation are read with bare "
                          "subscripts; absence must raise KeyError"))

    for name, design in I.SCORING_DESIGNS.items():
        rec.record(f"core.overall_score_from_impact::{name}", "core.scoring",
                   "overall_score_from_impact", {"design": design},
                   lambda d=design: scoring.overall_score_from_impact(
                       scoring.compute_impact(dict(d))),
                   notes="Delivery*0.6 + (10-Toxicity)*3 + (100-Cost)*0.1, clipped 0-100")

        # RECLASSIFIED in Step 1 (DEFECT-D9 corrected): get_recommendations()
        # previously raised TypeError on `none_valued_optionals`, an input that
        # compute_impact() accepted. Both now share one null contract.
        rec.record(f"core.get_recommendations::{name}", "core.scoring",
                   "get_recommendations", {"design": design},
                   lambda d=design: scoring.get_recommendations(dict(d)),
                   notes=("Shares the null contract with compute_impact(): an "
                          "absent key and a present-but-None value are equivalent."
                          if name == "none_valued_optionals" else None))

        rec.record(f"core.regulatory_checklist::{name}", "core.scoring",
                   "regulatory_checklist", {"design": design},
                   lambda d=design: scoring.regulatory_checklist(dict(d)))

    for param, value, rng in [
        ("Size", 100, [80, 120]), ("Size", 60, [80, 120]), ("Size", 300, [80, 120]),
        ("Charge", -5, [-10, 10]), ("Charge", 25, [-10, 10]),
        ("PDI", 0.15, [0.0, 0.3]),
    ]:
        rec.record(f"core.validate_parameter::{param}={value}", "core.scoring",
                   "validate_parameter", {"param": param, "value": value,
                                          "optimal_range": rng},
                   lambda p=param, v=value, r=rng: scoring.validate_parameter(p, v, r))


def capture_pk_model(rec):
    import numpy as np
    from utils import pk_model
    from tests.golden_vectors import inputs as I

    for name, params in I.PK_PARAM_SETS.items():
        rec.record(f"pk.two_compartment_model::{name}", "utils.pk_model",
                   "two_compartment_model", params,
                   lambda p=params: pk_model.two_compartment_model(**p),
                   assumptions=[
                       "Explicit forward-Euler integration at fixed dt",
                       "dt=0.1 h and the Euler scheme are the model's numerical "
                       "identity; substituting an adaptive solver changes results",
                       "Depot -> central -> peripheral, first-order transfers",
                   ])

        def _params(p=params):
            t, cp, ct = pk_model.two_compartment_model(**p)
            return pk_model.calculate_pk_parameters(t, cp, ct)

        rec.record(f"pk.calculate_pk_parameters::{name}", "utils.pk_model",
                   "calculate_pk_parameters", params, _params,
                   assumptions=[
                       "AUC by trapezoidal rule (np.trapezoid on NumPy >= 2)",
                       "t_half_plasma is None when concentration never halves "
                       "within the simulated window (bare except at pk_model.py:134)",
                   ])

    time = np.arange(0, 48.1, 0.1)
    for name, params in I.RELEASE_PROFILES.items():
        rec.record(f"pk.simulate_release_profile::{name}", "utils.pk_model",
                   "simulate_release_profile",
                   {"time": "np.arange(0, 48.1, 0.1)", **params},
                   lambda p=params: pk_model.simulate_release_profile(time, **p))


def capture_toxicity_model(rec):
    from utils import toxicity_model as tm
    from tests.golden_vectors import inputs as I

    fn_map = {
        "size_risk": tm.calculate_size_risk,
        "charge_risk": tm.calculate_charge_risk,
        "dose_risk": tm.calculate_dose_risk,
        "pdi_risk": tm.calculate_pdi_risk,
        "ligand_risk": tm.calculate_ligand_risk,
        "payload_risk": tm.calculate_payload_risk,
        "material_risk": tm.calculate_material_risk,
    }
    for fname, cases in I.TOXICITY_RISK_CASES.items():
        fn = fn_map[fname]
        for args in cases:
            rec.record(f"tox.{fname}::{args}", "utils.toxicity_model",
                       f"calculate_{fname}", {"args": list(args)},
                       lambda f=fn, a=args: f(*a))

    for name, design in I.TOXICITY_DESIGNS.items():
        rec.record(f"tox.calculate_overall_safety_score::{name}",
                   "utils.toxicity_model", "calculate_overall_safety_score",
                   {"design": design},
                   lambda d=design: tm.calculate_overall_safety_score(dict(d)),
                   assumptions=[
                       "7 risk factors weighted size .15 charge .20 dose .20 "
                       "pdi .10 ligand .10 payload .15 material .10",
                       "MIXED key convention: Size/Charge/PDI/Ligand/Material "
                       "capitalised but dose/payload/payload_amount lowercase",
                   ])


def capture_design_scorer(rec):
    from utils.design_scorer import DesignScorer
    from tests.golden_vectors import inputs as I

    scorer = DesignScorer()
    for name, design in I.DESIGN_SCORER_DESIGNS.items():
        rec.record(f"design_scorer.calculate_overall_score::{name}",
                   "utils.design_scorer", "DesignScorer.calculate_overall_score",
                   {"design": design},
                   lambda d=design: scorer.calculate_overall_score(dict(d)),
                   notes=("SECONDARY/LEGACY scorer (DECISION 3C). Only "
                          "modules/design.py uses it, but docs/scoring_system.md "
                          "documents it. Uses lowercase keys."),
                   assumptions=["Weights size .25 material .20 ligand .20 "
                                "charge .15 pdi .10 loading .10"])


def capture_disease_profiles(rec):
    from config import disease_profiles as dp
    from tests.golden_vectors import inputs as I

    rec.record("disease.list_supported_diseases", "config.disease_profiles",
               "list_supported_diseases", {}, dp.list_supported_diseases)

    for code in I.DISEASE_CODES_SUPPORTED:
        rec.record(f"disease.get_disease_profile::{code}",
                   "config.disease_profiles", "get_disease_profile",
                   {"disease_code": code},
                   lambda c=code: dp.get_disease_profile(c))

    for code in I.DISEASE_CODES_UNSUPPORTED:
        rec.record(f"disease.get_disease_profile::UNSUPPORTED::{code or '<empty>'}",
                   "config.disease_profiles", "get_disease_profile",
                   {"disease_code": code},
                   lambda c=code: dp.get_disease_profile(c),
                   classification="known_defect", defect_id="DEFECT-D1",
                   notes=("Captured to prove the silent substitution exists and "
                          "to detect when DECISION 1 removes it. The returned "
                          "HCC-S profile is NOT correct output for this input."))


def capture_engines(rec):
    from config.disease_profiles import get_disease_profile
    from engine.confidence_engine import ConfidenceEngine
    from engine.disease_fit import DiseaseFilEngine
    from engine.manufacturing_engine import ManufacturingEngine
    from engine.mechanistic_engine import MechanisticEngine
    from engine.regulatory_engine import RegulatoryEngine
    from engine.safety_engine import SafetyEngine
    from models.scientific_assessment import TrialDesignInputs
    from tests.golden_vectors import inputs as I

    for name, kwargs in I.ENGINE_DESIGNS.items():
        di = TrialDesignInputs(**kwargs)
        profile = get_disease_profile(di.disease_code)
        common = {"design_inputs": kwargs, "disease_profile": profile.disease_code}

        for meth in ("compute_toxicity_prediction", "compute_manufacturability",
                     "compute_storage_stability", "compute_payload_release"):
            rec.record(f"mechanistic.{meth}::{name}", "engine.mechanistic_engine",
                       f"MechanisticEngine.{meth}", {"design_inputs": kwargs},
                       lambda m=meth, d=di: getattr(MechanisticEngine, m)(d))

        for meth in ("compute_delivery_efficacy", "compute_targeting_efficacy"):
            rec.record(f"mechanistic.{meth}::{name}", "engine.mechanistic_engine",
                       f"MechanisticEngine.{meth}", common,
                       lambda m=meth, d=di, p=profile:
                           getattr(MechanisticEngine, m)(d, p))

        mech = MechanisticEngine.compute_all_predictions(di, profile)
        rec.record(f"mechanistic.compute_all_predictions::{name}",
                   "engine.mechanistic_engine",
                   "MechanisticEngine.compute_all_predictions", common,
                   lambda d=di, p=profile:
                       MechanisticEngine.compute_all_predictions(d, p),
                   assumptions=["OPTIMAL_SIZE 80-150 nm; SUBOPTIMAL_PENALTY 15; "
                                "OVERSIZED_PENALTY 20; PEG_COATING_BENEFIT 8; "
                                "PEG_DENSITY_BENEFIT 5; LIGAND_BENEFIT 12"])

        safety = SafetyEngine.assess_safety_profile(di)
        rec.record(f"safety.assess_safety_profile::{name}", "engine.safety_engine",
                   "SafetyEngine.assess_safety_profile", {"design_inputs": kwargs},
                   lambda d=di: SafetyEngine.assess_safety_profile(d),
                   assumptions=["6 risk components: systemic toxicity, "
                                "immunogenicity, off-target, aggregation, "
                                "premature release, metabolic burden"])

        fit = DiseaseFilEngine.assess_disease_fit(di, profile)
        rec.record(f"disease_fit.assess_disease_fit::{name}", "engine.disease_fit",
                   "DiseaseFilEngine.assess_disease_fit", common,
                   lambda d=di, p=profile:
                       DiseaseFilEngine.assess_disease_fit(d, p))

        mfg = ManufacturingEngine.assess_manufacturability(di)
        rec.record(f"manufacturing.assess_manufacturability::{name}",
                   "engine.manufacturing_engine",
                   "ManufacturingEngine.assess_manufacturability",
                   {"design_inputs": kwargs},
                   lambda d=di: ManufacturingEngine.assess_manufacturability(d))

        # RECLASSIFIED in Step 1: was DEFECT.regulatory.* (always raised
        # TypeError, DEFECT-D8). Now intended behaviour under DECISION 5.
        rec.record(f"regulatory.assess_regulatory_position::{name}",
                   "engine.regulatory_engine",
                   "RegulatoryEngine.assess_regulatory_position",
                   {**common, "chained_from": ["mechanistic", "safety", "disease_fit"]},
                   lambda d=di, p=profile, m=mech, s=safety, f=fit:
                       RegulatoryEngine.assess_regulatory_position(d, p, m, s, f),
                   notes=("manufacturing_complexity is a rule-based 0-2 indicator "
                          "(DECISION 5), NOT validated manufacturability. "
                          "verdict_available is False pending calibration "
                          "(DECISION 6)."),
                   assumptions=[
                       "RegulatoryEngine.CALCULATION_VERSION = 2.0.0",
                       "Favourable disease-fit verdict disabled: threshold "
                       "uncalibrated and unreachable (ceiling 68.33)",
                       "Not a regulatory approval prediction",
                   ])

        reg = RegulatoryEngine.assess_regulatory_position(di, profile, mech,
                                                          safety, fit)

        # RECLASSIFIED in Step 1: was BLOCKED.confidence.* (could not execute,
        # because DEFECT-D8 prevented its RegulatoryAssessment input existing).
        rec.record(f"confidence.calculate_confidence_profile::{name}",
                   "engine.confidence_engine",
                   "ConfidenceEngine.calculate_confidence_profile",
                   {"design_inputs": kwargs,
                    "chained_from": ["mechanistic", "safety", "disease_fit",
                                     "manufacturing", "regulatory"]},
                   lambda m=mech, s=safety, f=fit, g=mfg, r=reg:
                       ConfidenceEngine.calculate_confidence_profile(m, s, f, g, r),
                   assumptions=["Confidence thresholds high >= 0.75, medium >= 0.50 "
                                "(config/scoring_config.py)"])


def capture_engines_unsupported_disease(rec):
    """The DECISION-1 blocking case, captured as a defect.

    A disease the engines do not support still produces a full, confident-looking
    assessment because get_disease_profile() substitutes HCC-S.
    """
    from config.disease_profiles import get_disease_profile
    from engine.disease_fit import DiseaseFilEngine
    from engine.mechanistic_engine import MechanisticEngine
    from models.scientific_assessment import TrialDesignInputs

    for code in ("Triple-Negative (ER-, PR-, HER2-)", "HCC-L", "Lung Cancer"):
        di = TrialDesignInputs(case_id="GV-DEFECT-D1", disease_code=code,
                               nanoparticle_size_nm=100.0, surface_charge_mv=-5.0,
                               peg_surface_coating=True, peg_density_percent=5.0,
                               targeting_ligand="GalNAc")
        profile = get_disease_profile(code)
        rec.record(f"DEFECT.mechanistic.compute_all_predictions::{code}",
                   "engine.mechanistic_engine",
                   "MechanisticEngine.compute_all_predictions",
                   {"design_inputs_disease_code": code,
                    "disease_profile_actually_used": profile.disease_code},
                   lambda d=di, p=profile:
                       MechanisticEngine.compute_all_predictions(d, p),
                   classification="known_defect", defect_id="DEFECT-D1",
                   notes=(f"Requested {code!r}; computed against "
                          f"{profile.disease_code!r} biology. Under DECISION 1 this "
                          "must instead return an unsupported-model status."))

        rec.record(f"DEFECT.disease_fit.assess_disease_fit::{code}",
                   "engine.disease_fit", "DiseaseFilEngine.assess_disease_fit",
                   {"design_inputs_disease_code": code,
                    "disease_profile_actually_used": profile.disease_code},
                   lambda d=di, p=profile:
                       DiseaseFilEngine.assess_disease_fit(d, p),
                   classification="known_defect", defect_id="DEFECT-D1",
                   notes=("disease_name in the output is the SUBSTITUTED disease, "
                          "which is how mislabelling reaches the report."))


def capture_ml_predictor(rec):
    import logging
    from tests.golden_vectors import inputs as I

    logging.disable(logging.CRITICAL)
    try:
        from components.ml_predictor import MLPredictor

        p = MLPredictor(model_dir="models")
        rec.record("DEFECT.ml_predictor.load_models", "components.ml_predictor",
                   "MLPredictor.load_models", {"model_dir": "models"},
                   p.load_models, classification="known_defect",
                   defect_id="DEFECT-D5",
                   notes="Expected all-False: no model file matches the lookup name.")

        for name, design in I.ML_PREDICTOR_DESIGNS.items():
            for meth in ("predict_toxicity", "predict_uptake", "predict_particle_size"):
                rec.record(f"DEFECT.ml_predictor.{meth}::{name}",
                           "components.ml_predictor", f"MLPredictor.{meth}",
                           {"design": design},
                           lambda m=meth, d=design: getattr(p, m)(dict(d)),
                           classification="known_defect", defect_id="DEFECT-D5",
                           notes=("Value comes from the heuristic fallback, not a "
                                  "trained model. The number itself is a legitimate "
                                  "heuristic; the DEFECT is presenting it as ML "
                                  "output with collapsed disclosure."))

            rec.record(f"DEFECT.ml_predictor.get_predictions_summary::{name}",
                       "components.ml_predictor",
                       "MLPredictor.get_predictions_summary", {"design": design},
                       lambda d=design: p.get_predictions_summary(dict(d)),
                       classification="known_defect", defect_id="DEFECT-D5",
                       normalise_timestamps=True,
                       notes=("Contains pd.Timestamp.now() at ml_predictor.py:412, "
                              "normalised to a sentinel. Note also that this method "
                              "swallows every exception and returns {} "
                              "(ml_predictor.py:416-418), a silent-failure path."),
                       assumptions=["timestamp normalised for determinism"])
    finally:
        logging.disable(logging.NOTSET)


def capture_legacy_headline_score(rec):
    """DEFECT-D2 / D3: the hard-coded headline score, recorded as legacy only."""

    def legacy_overall_score(uptake_efficiency):
        # Verbatim transcription of pages/2_Run_Simulation.py:314-323.
        if uptake_efficiency > 85:
            return {"legacy_overall_score": 92, "legacy_overall_status": "Excellent"}
        elif uptake_efficiency > 75:
            return {"legacy_overall_score": 89, "legacy_overall_status": "Good"}
        return {"legacy_overall_score": 82, "legacy_overall_status": "Satisfactory"}

    for uptake in (95.0, 92.0, 85.0, 85.1, 80.0, 75.0, 74.9, 10.0, 0.0):
        rec.record(f"DEFECT.legacy_headline_score::uptake={uptake}",
                   "pages.2_Run_Simulation", "<inline bucketing at lines 314-323>",
                   {"uptake_efficiency": uptake},
                   lambda u=uptake: legacy_overall_score(u),
                   classification="known_defect", defect_id="DEFECT-D2",
                   notes=("Recorded as legacy_overall_score per DECISION 2. Only 3 "
                          "distinct values are reachable regardless of design."))

    rec.record("DEFECT.legacy_headline_score::exception_path",
               "pages.2_Run_Simulation", "<except handler at lines 337-338>",
               {"trigger": "any exception during ML prediction"},
               lambda: {"legacy_overall_score": 89, "legacy_overall_status": "Good"},
               classification="known_defect", defect_id="DEFECT-D3",
               notes=("A failure path that reports a favourable score. DECISION 2 "
                      "forbids this: failure must yield unavailable, not 89/Good."))


def capture_mock_ai_codesigner(rec):
    """DEFECT-D6: hard-coded 'AI optimisation' candidates."""
    rec.record("DEFECT.ai_codesigner.mock_candidates", "pages.7_AI_Co_Designer",
               "<hard-coded DataFrame at lines 364-373>",
               {"note": "independent of every design parameter"},
               lambda: {
                   "Rank": [1, 2, 3, 4, 5],
                   "Score": [94.2, 91.5, 89.8, 87.3, 84.9],
                   "Delivery": [92, 89, 87, 85, 82],
                   "Safety": [96, 93, 92, 90, 88],
                   "Cost": [88, 91, 90, 87, 85],
                   "Size (nm)": [100, 110, 95, 105, 115],
               },
               classification="known_defect", defect_id="DEFECT-D6",
               notes=("Only the Material column varies (a dict lookup on "
                      "disease/scenario). Scores are literals. Must not be "
                      "migrated as optimisation output."))


def capture_trial_registry(rec):
    """Trial-ID generation against an ISOLATED temporary database."""
    from tests.golden_vectors import inputs as I

    import modules.trial_registry as tr

    with tempfile.TemporaryDirectory(prefix="gv_trial_registry_") as tmp:
        original = tr.DB_PATH
        tr.DB_PATH = Path(tmp) / "trial_registry_isolated.db"
        try:
            for subtype in I.TRIAL_ID_SUBTYPES_MAPPED:
                rec.record(f"trial_registry.generate_trial_id::{subtype}",
                           "modules.trial_registry",
                           "TrialIDGenerator.generate_trial_id",
                           {"disease_subtype": subtype, "np_size_nm": 100,
                            "db": "<temporary isolated file>"},
                           lambda s=subtype: _mask_date(
                               tr.TrialIDGenerator.generate_trial_id(s, 100)),
                           notes=("Date component masked so the vector is stable "
                                  "across days."))

            for subtype in I.TRIAL_ID_SUBTYPES_UNMAPPED:
                rec.record(
                    f"DEFECT.trial_registry.generate_trial_id::{subtype or '<empty>'}",
                    "modules.trial_registry",
                    "TrialIDGenerator.generate_trial_id",
                    {"disease_subtype": subtype, "np_size_nm": 100,
                     "db": "<temporary isolated file>"},
                    lambda s=subtype: _mask_date(
                        tr.TrialIDGenerator.generate_trial_id(s, 100)),
                    classification="known_defect", defect_id="DEFECT-D4",
                    notes="Real UI subtype labels are filed as UNKNOWN.")
        finally:
            tr.DB_PATH = original


def _mask_date(trial_id: str) -> str:
    """TRIAL-HCC-S-NP100-20260730-00001 -> TRIAL-HCC-S-NP100-<YYYYMMDD>-00001"""
    parts = trial_id.split("-")
    for i, p in enumerate(parts):
        if len(p) == 8 and p.isdigit():
            parts[i] = "<YYYYMMDD>"
    return "-".join(parts)


def capture_report_generator(rec):
    from reports.scientific_report_generator import ScientificReportGenerator
    from models.scientific_assessment import TrialDesignInputs
    from tests.golden_vectors import inputs as I

    gen = ScientificReportGenerator()
    for name in ("hccs_pegylated_targeted", "pdaci_targeted"):
        kwargs = I.ENGINE_DESIGNS[name]
        di = TrialDesignInputs(**kwargs)
        # RECLASSIFIED in Step 1: was DEFECT.report.* (inherited the DEFECT-D8
        # crash through the five-engine chain). Now executes for supported inputs.
        rec.record(f"report.generate_full_report::{name}",
                   "reports.scientific_report_generator",
                   "ScientificReportGenerator.generate_full_report",
                   {"trial_design_inputs": kwargs,
                    "disease_code": kwargs["disease_code"],
                    "blocked_by": "DEFECT-D8"},
                   lambda d=di, c=kwargs["disease_code"]:
                       gen.generate_full_report(d, disease_code=c,
                                                trial_id="GV-FIXED-TRIAL-ID"),
                   normalise_timestamps=True,
                   notes=("Every value is a computational research-planning "
                          "result: not experimentally or clinically validated, "
                          "and not a regulatory approval prediction."),
                   assumptions=["datetime.now() at "
                                "scientific_report_generator.py:148 is normalised "
                                "to a sentinel for determinism",
                                "Four of six modules declare no structured "
                                "prediction basis; the absence is reported, "
                                "never invented"])


def capture_unreachable(rec):
    """DEFECT-D7: record that ai_engine cannot be imported at all."""
    def _try_import():
        import ai_engine  # noqa: F401
        return "imported"

    rec.record("DEFECT.ai_engine.import", "ai_engine", "<package import>",
               {"expected": "ModuleNotFoundError: No module named 'nanobio_studio'"},
               _try_import, classification="known_defect", defect_id="DEFECT-D7",
               expect_exception=True,
               notes=("Blocks golden-vectoring of the Optuna optimiser, Pareto "
                      "front, sensitivity analysis and audit-record code. optuna "
                      "is a declared dependency reachable by nothing."))


def capture_import_side_effects(rec):
    """DEFECT-D11: document import-time database writes WITHOUT triggering them.

    These vectors are static assertions about source text. Executing the imports
    would create real databases, which is exactly the defect being recorded, so
    the harness reads the files instead of importing them.
    """
    def _module_level_call_lines(filename: str, call: str) -> list[int]:
        """1-indexed lines where `call` appears at column 0 (module scope)."""
        text = (REPO_ROOT / filename).read_text(encoding="utf-8", errors="replace")
        return [i for i, line in enumerate(text.splitlines(), start=1)
                if line.rstrip() == call]

    # (vector id, file, module-level call, still a defect?, note)
    # All three are now RESOLVED. Each vector asserts ABSENCE, so a regression
    # that re-introduces an import-time database write fails the contract suite.
    checks = [
        ("auth.py::init_db_at_import", "auth.py", "init_db()", False,
         "RESOLVED in Step 1 (DEFECT-D11). Both module-level calls were removed "
         "-- it was invoked TWICE (lines 88 and 1420), so importing auth.py "
         "initialised the database twice. Initialisation is now explicit via "
         "auth.initialize_database(), plus an idempotent _ensure_initialized() "
         "guard on all 32 DB-touching functions."),
        ("design_persistence.py::init_design_db_at_import",
         "design_persistence.py", "init_design_db()", False,
         "RESOLVED in Step 1 (DEFECT-D11). A bare `import design_persistence` "
         "wrote a ~36 KB nano_bio.db into the working directory -- it actually "
         "leaked into the repository root during Step 0 harness development. "
         "Initialisation is now lazy and explicit."),
        ("auth.py::_reset_admin_session_at_import", "auth.py",
         "_reset_admin_session()", False,
         "RESOLVED by the 2026-07-30 security containment: the module-level call "
         "was removed, so this vector asserts ABSENCE. A regression that re-adds "
         "the call will fail this test."),
    ]

    for vid, filename, call, is_defect, note in checks:
        def _check(f=filename, c=call):
            lines = _module_level_call_lines(f, c)
            return {"file": f, "module_level_call": c,
                    "occurrences": len(lines), "lines": lines,
                    "called_at_import": bool(lines)}

        prefix = "DEFECT" if is_defect else "RESOLVED"
        rec.record(f"{prefix}.import_side_effect::{vid}", filename,
                   "<module-level statement>",
                   {"file": filename, "module_level_call": call},
                   _check,
                   classification="known_defect" if is_defect else "intended",
                   defect_id="DEFECT-D11" if is_defect else None,
                   notes=("Verified by reading source, NOT by importing: importing "
                          "would create a real database, which is the defect. "
                          + note))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def capture_step1_corrections(rec):
    """Vectors pinning the Phase 2 Step 1 corrections (DECISION 5, 6, 9, 11)."""
    from config.disease_profiles import get_disease_profile
    from engine.disease_fit import DiseaseFilEngine
    from engine.input_normalization import (
        has_peg_coating,
        has_targeting_ligand,
        manufacturing_complexity_count,
        normalise_ligand,
    )
    from engine.mechanistic_engine import MechanisticEngine
    from engine.regulatory_engine import RegulatoryEngine
    from engine.safety_engine import SafetyEngine
    from models.scientific_assessment import TrialDesignInputs

    # --- DECISION 5: all four PEG/ligand presence combinations --------------
    for peg in (False, True):
        for lig in ("None", "GalNAc"):
            rec.record(
                f"D5.manufacturing_complexity_count::peg={peg},ligand={lig}",
                "engine.input_normalization", "manufacturing_complexity_count",
                {"peg_surface_coating": peg, "targeting_ligand": lig},
                lambda p=peg, l=lig: manufacturing_complexity_count(p, l),
                notes=("Rule-based manufacturing complexity indicator, 0-2. NOT "
                       "validated manufacturability, NOT a regulatory approval "
                       "probability, NOT evidence of production success."))

    # --- DECISION 5: the "None"-is-truthy hazard the rule must not fall for --
    for value in ("None", "none", " NONE ", "", "   ", None, "n/a", "NA", "-",
                  "GalNAc", " Transferrin ", "RGD Peptide"):
        rec.record(f"D5.normalise_ligand::{value!r}",
                   "engine.input_normalization", "normalise_ligand",
                   {"value": value}, lambda v=value: normalise_ligand(v),
                   notes="Canonical absent representation is None, not the string 'None'.")
        rec.record(f"D5.has_targeting_ligand::{value!r}",
                   "engine.input_normalization", "has_targeting_ligand",
                   {"value": value}, lambda v=value: has_targeting_ligand(v))

    for value in (True, False, None, "None", "PEG (Stealth)", [], ["PEG (Stealth)"]):
        rec.record(f"D5.has_peg_coating::{value!r}",
                   "engine.input_normalization", "has_peg_coating",
                   {"value": value}, lambda v=value: has_peg_coating(v))

    # --- DECISION 5/6: regulatory provenance fields per combination ----------
    for peg in (False, True):
        for lig in ("None", "GalNAc"):
            di = TrialDesignInputs(case_id="D5", disease_code="HCC-S",
                                   peg_surface_coating=peg, targeting_ligand=lig)
            prof = get_disease_profile("HCC-S")
            mech = MechanisticEngine.compute_all_predictions(di, prof)
            saf = SafetyEngine.assess_safety_profile(di)
            fit = DiseaseFilEngine.assess_disease_fit(di, prof)

            def _fields(d=di, p=prof, m=mech, s=saf, f=fit):
                r = RegulatoryEngine.assess_regulatory_position(d, p, m, s, f)
                return {
                    "calculation_version": r.calculation_version,
                    "manufacturing_complexity": r.manufacturing_complexity,
                    "manufacturing_complexity_basis": r.manufacturing_complexity_basis,
                    "verdict_available": r.verdict_available,
                    "verdict_status": r.verdict_status,
                    "regulatory_category": r.regulatory_category,
                }

            rec.record(
                f"D5.regulatory_provenance::peg={peg},ligand={lig}",
                "engine.regulatory_engine",
                "RegulatoryEngine.assess_regulatory_position",
                {"peg_surface_coating": peg, "targeting_ligand": lig},
                _fields,
                notes=("regulatory_category now uses normalised ligand presence: "
                       "an untargeted design is no longer classified as a "
                       "Combination Product because the string 'None' is truthy. "
                       "Documented language change under DECISION 5.8."))

    # --- DECISION 6: verdict withheld, component scores still returned ------
    for code in ("HCC-S", "PDAC-I"):
        prof = get_disease_profile(code)
        di = TrialDesignInputs(case_id="D6", disease_code=code,
                               nanoparticle_size_nm=80.0, surface_charge_mv=0.0,
                               peg_surface_coating=True, peg_density_percent=5.0,
                               targeting_ligand="GalNAc",
                               payload_loading_percent=85.0)

        def _verdict(d=di, p=prof):
            f = DiseaseFilEngine.assess_disease_fit(d, p)
            return {
                "overall_fit_score": f.overall_fit_score,
                "n_barrier_scores": len(f.barrier_mitigation_scores),
                "verdict_available": f.verdict_available,
                "verdict_status": f.verdict_status,
                "favourable_verdict_threshold": f.favourable_verdict_threshold,
                "observed_model_ceiling": f.observed_model_ceiling,
                "score_below_threshold": (
                    f.overall_fit_score < DiseaseFilEngine.FAVOURABLE_VERDICT_THRESHOLD),
            }

        rec.record(f"D6.disease_fit_verdict_status::{code}", "engine.disease_fit",
                   "DiseaseFilEngine.assess_disease_fit", {"disease_code": code},
                   _verdict,
                   notes=("Scores remain valid and are still returned; only the "
                          "VERDICT is withheld. Not a regulatory approval "
                          "likelihood."),
                   assumptions=[
                       "Favourable threshold 70.0 is uncalibrated",
                       "Observed model ceiling 68.33 over 1,792 combinations",
                       "Scores NOT rescaled, threshold NOT lowered",
                   ])

    rec.record("D6.favourable_verdict_flag_is_disabled", "engine.regulatory_engine",
               "RegulatoryEngine.FAVOURABLE_VERDICT_ENABLED", {},
               lambda: {
                   "FAVOURABLE_VERDICT_ENABLED":
                       RegulatoryEngine.FAVOURABLE_VERDICT_ENABLED,
                   "DISEASE_FIT_FAVOURABLE_THRESHOLD":
                       RegulatoryEngine.DISEASE_FIT_FAVOURABLE_THRESHOLD,
                   "CALCULATION_VERSION": RegulatoryEngine.CALCULATION_VERSION,
               },
               notes="Must stay False until a scientifically reviewed calibration decision.")

    # --- DECISION 9: paired null contract across the three functions --------
    from core import scoring
    from tests.golden_vectors import inputs as I

    def _null_contract_matrix():
        base = dict(I.APP_DEFAULT_DESIGN)
        optional = [k for k in base if k not in scoring.REQUIRED_DESIGN_KEYS]
        mismatches = []
        for key in optional:
            absent = {k: v for k, v in base.items() if k != key}
            none_valued = dict(base)
            none_valued[key] = None
            for fn in (scoring.compute_impact, scoring.get_recommendations,
                       scoring.regulatory_checklist):
                try:
                    same = fn(dict(absent)) == fn(dict(none_valued))
                except Exception as exc:
                    mismatches.append(f"{key}/{fn.__name__}: {type(exc).__name__}")
                    continue
                if not same:
                    mismatches.append(f"{key}/{fn.__name__}: absent != None")
        return {
            "optional_keys_checked": len(optional),
            "functions_checked": 3,
            "total_checks": len(optional) * 3,
            "mismatches": mismatches,
            "all_consistent": not mismatches,
        }

    rec.record("D9.null_contract_consistency_matrix", "core.scoring",
               "compute_impact / get_recommendations / regulatory_checklist",
               {"property": "absent key == present-but-None, for every optional key"},
               _null_contract_matrix,
               notes=("DEFECT-D9 correction. Required keys are excluded: they must "
                      "still raise KeyError and must never be replaced by "
                      "favourable defaults."))

    def _required_keys_still_raise():
        base = dict(I.APP_DEFAULT_DESIGN)
        out = {}
        for key in scoring.REQUIRED_DESIGN_KEYS:
            d = {k: v for k, v in base.items() if k != key}
            try:
                scoring.compute_impact(dict(d))
                out[key] = "NO RAISE"
            except KeyError:
                out[key] = "KeyError"
        return out

    rec.record("D9.required_keys_still_raise", "core.scoring", "compute_impact",
               {"required": list(scoring.REQUIRED_DESIGN_KEYS)},
               _required_keys_still_raise,
               notes="Scientifically required inputs must fail loudly, not default.")


def capture_ai_codesigner_quarantine(rec):
    """DECISION 7: prove the fabricated optimisation output is gone."""
    page = REPO_ROOT / "pages" / "7_AI_Co_Designer.py"
    quarantined = (REPO_ROOT / "legacy_streamlit" / "quarantined"
                   / "7_AI_Co_Designer.legacy.py")
    fabricated = ("94.2", "91.5", "89.8", "87.3", "84.9", "387 / 500",
                  "2026-03-17 15:30:45 UTC")

    def _check():
        text = page.read_text(encoding="utf-8", errors="replace")
        code_lines = [ln for ln in text.splitlines()
                      if ln.strip() and not ln.lstrip().startswith("#")]
        # Strip the module docstring, which legitimately names the removed values.
        body = "\n".join(code_lines)
        doc_end = body.find('"""', body.find('"""') + 3)
        code_only = body[doc_end + 3:] if doc_end != -1 else body
        return {
            "page_exists": page.exists(),
            "fabricated_values_in_executable_code": [
                v for v in fabricated if v in code_only],
            "renders_dataframe_or_metric": any(
                tok in code_only for tok in
                ("pd.DataFrame", "st.metric", "st.bar_chart", "st.line_chart",
                 "st.dataframe")),
            "declares_not_operational": "not yet operational" in text.lower(),
            "quarantined_copy_preserved": quarantined.exists(),
            "quarantined_copy_outside_pages_dir": "pages" not in quarantined.parts[:-1],
        }

    rec.record("D7.ai_codesigner_quarantine", "pages.7_AI_Co_Designer",
               "<page render surface>",
               {"fabricated_values_checked": list(fabricated)},
               _check,
               notes=("DECISION 7: fabricated candidate scores, rationale, "
                      "sensitivity charts and the fabricated AUDIT TRAIL are "
                      "removed from the live page. The original is preserved as "
                      "synthetic demonstration data outside pages/, so Streamlit "
                      "cannot route to it and it can never be mixed with real "
                      "saved simulations."))


SECTIONS = [
    ("core_scoring", capture_core_scoring),
    ("pk_model", capture_pk_model),
    ("toxicity_model", capture_toxicity_model),
    ("design_scorer", capture_design_scorer),
    ("disease_profiles", capture_disease_profiles),
    ("engines", capture_engines),
    ("engines_unsupported_disease", capture_engines_unsupported_disease),
    ("ml_predictor", capture_ml_predictor),
    ("legacy_headline_score", capture_legacy_headline_score),
    ("mock_ai_codesigner", capture_mock_ai_codesigner),
    ("trial_registry", capture_trial_registry),
    ("report_generator", capture_report_generator),
    ("unreachable_modules", capture_unreachable),
    ("import_side_effects", capture_import_side_effects),
    ("step1_corrections", capture_step1_corrections),
    ("ai_codesigner_quarantine", capture_ai_codesigner_quarantine),
]


def build_baseline() -> dict:
    rec = Recorder()
    section_status = {}

    for name, fn in SECTIONS:
        before = len(rec.vectors)
        try:
            fn(rec)
            section_status[name] = {"status": "ok",
                                    "vectors": len(rec.vectors) - before}
        except Exception as exc:
            section_status[name] = {
                "status": "section_failed",
                "vectors": len(rec.vectors) - before,
                "error": f"{type(exc).__name__}: {exc}",
            }
            rec.errors.append(f"section {name} failed: {type(exc).__name__}: {exc}")

    intended = [v for v in rec.vectors if v["classification"] == "intended"]
    defects = [v for v in rec.vectors if v["classification"] == "known_defect"]

    import numpy
    import pandas
    import sklearn

    return {
        "schema_version": "1.0",
        "baseline_version": "step1-2026-07-30",
        "description": (
            "Golden-vector baseline for the legacy Streamlit NanoBio Studio "
            "scientific engine. Captured before any migration code was written. "
            "Vectors classified 'intended' MUST be reproduced by the new backend. "
            "Vectors classified 'known_defect' record current behaviour for "
            "change-detection only and MUST NOT be treated as target behaviour."
        ),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": numpy.__version__,
            "pandas": pandas.__version__,
            "scikit_learn": sklearn.__version__,
            "cwd_note": "captured from repository root",
        },
        "known_defects": KNOWN_DEFECTS,
        "resolved_defects": RESOLVED_DEFECTS,
        "unmasked_by_d8_fix": UNMASKED_BY_D8_FIX,
        "legacy_baseline_archive": "baseline_step0_2026-07-30_legacy.json",
        "sections": section_status,
        "counts": {
            "total": len(rec.vectors),
            "intended": len(intended),
            "known_defect": len(defects),
            "raised": sum(1 for v in rec.vectors if v["status"] == "raised"),
        },
        "capture_errors": rec.errors,
        "vectors": rec.vectors,
    }


def main() -> int:
    baseline = build_baseline()
    BASELINE_PATH.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=False,
                   allow_nan=False) + "\n",
        encoding="utf-8",
    )

    c = baseline["counts"]
    print(f"wrote {BASELINE_PATH.relative_to(REPO_ROOT)}")
    print(f"  vectors: {c['total']}  intended: {c['intended']}  "
          f"known_defect: {c['known_defect']}  raised: {c['raised']}")
    for name, st in baseline["sections"].items():
        flag = "OK " if st["status"] == "ok" else "FAIL"
        print(f"  [{flag}] {name}: {st['vectors']} vectors"
              + (f" -- {st.get('error')}" if st.get("error") else ""))
    if baseline["capture_errors"]:
        print(f"\n  capture errors ({len(baseline['capture_errors'])}):")
        for e in baseline["capture_errors"]:
            print(f"    - {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
