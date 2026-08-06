"""Adapter between the API layer and the canonical scientific scoring function.

Scientific source of truth
--------------------------
``core/scoring.py::compute_impact()`` in the repository root. It is imported and
called **verbatim**. Nothing in this module reimplements, re-derives, adjusts or
rounds any part of the formula. If a number here differs from the legacy
Streamlit application for the same input, that is a bug in this adapter.

What this module IS allowed to do
---------------------------------
* translate an API request into the ``dict`` shape ``compute_impact`` expects
  (CapitalCase keys);
* apply the Step 1 DEFECT-D9 null contract, by reusing the canonical helpers
  rather than reimplementing them;
* attach provenance (version, basis, evidence level, validation status);
* convert failures into structured errors.

What it must NOT do
-------------------
* combine the design score with assessment-engine outputs;
* emit the deprecated hard-coded 92/89/82 headline score;
* return a favourable number when a calculation fails;
* present the result as validated in any sense.

Scientific positioning
----------------------
The output is a computational research-planning result. It is not experimentally
validated, not clinically validated, not a regulatory approval prediction, not a
diagnosis, not a treatment recommendation, and not a substitute for wet-lab
testing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# TEMPORARY path bootstrap (vertical slice only)
# ---------------------------------------------------------------------------
# The canonical scientific code still lives in the repository root alongside the
# legacy Streamlit application. Until Step 3 moves it into
# `backend/app/scientific/`, the backend reaches it by putting the repo root on
# sys.path. This is deliberately explicit and is documented as temporary in
# docs/VERTICAL_SLICE.md. It must be removed once the scientific core is ported.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.scoring import (  # noqa: E402  (import must follow the bootstrap)
    REQUIRED_DESIGN_KEYS,
    _optional_float,
    _optional_value,
    compute_impact,
)

__all__ = [
    "SCORE_VERSION",
    "SCIENTIFIC_SOURCE",
    "PREDICTION_BASIS",
    "EVIDENCE_LEVEL",
    "VALIDATION_STATUS",
    "LIMITATIONS",
    "ScoringFailure",
    "build_design_dict",
    "score_design",
]

# ---------------------------------------------------------------------------
# Provenance constants
# ---------------------------------------------------------------------------

#: Version of THIS adapter's output contract. Bumped on any change to how the
#: canonical result is assembled or presented. The underlying formula in
#: core/scoring.py is unversioned in the legacy codebase; assigning it a formal
#: version is open question Q-VS1 in docs/VERTICAL_SLICE.md.
SCORE_VERSION = "design-impact-adapter-0.1.0"

SCIENTIFIC_SOURCE = "core.scoring.compute_impact"

#: How the numbers were derived. Rule-based, not a trained model.
PREDICTION_BASIS = "rule_based_physicochemical_heuristic"

#: Evidence standing of the underlying rules.
EVIDENCE_LEVEL = "literature_informed_unvalidated"

#: Experimental validation status. Universally absent in this platform.
VALIDATION_STATUS = "not_experimentally_validated"

LIMITATIONS: tuple[str, ...] = (
    "Computational research-planning result only. Not experimentally validated, "
    "not clinically validated, and not a substitute for wet-lab testing.",
    "Not a regulatory approval prediction, diagnosis, or treatment recommendation.",
    "Scores are produced by rule-based physicochemical heuristics, not by a "
    "trained or calibrated model.",
    "No uncertainty quantification exists for these values (open question Q5 in "
    "docs/SCORING_CANONICALIZATION.md).",
    "Delivery, Toxicity and Cost are reported separately. No single composite "
    "'Overall Score' is produced: the candidate formula is documented but NOT "
    "implemented, pending scientific review.",
    "The 12 internal sub-scores that feed Delivery are not exposed, because the "
    "canonical function does not return them and this slice must not modify it.",
    "Only the design score is computed here. Assessment-engine outputs "
    "(safety, disease-fit, manufacturability, regulatory, confidence) are NOT "
    "included and must not be combined with it.",
)


class ScoringFailure(RuntimeError):
    """Raised when a score cannot be produced.

    Carries a machine-readable ``code`` so the API can return a structured error
    instead of a number. There is deliberately no fallback value: a failed
    calculation must never yield a favourable score (DECISION 2).
    """

    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


# ---------------------------------------------------------------------------
# Request -> canonical design dict
# ---------------------------------------------------------------------------

#: Optional fields the canonical function reads, with the defaults it applies.
#: Mirrors core/scoring.py exactly. `HydrodynamicSize` is omitted because its
#: default is derived from Size (Size * 1.2) inside the canonical function.
_OPTIONAL_NUMERIC_DEFAULTS: dict[str, float] = {
    "PDI": 0.15,
    "Stability": 85,
    "SurfaceArea": 250,
    "DegradationTime": 30,
    "Hydrophobicity": 1.5,
    "CrystallinityIndex": 65,
    "CoatingThickness": 2.5,
    "LigandDensity": 0,
    "ReceptorBinding": 100.0,
    "ReleasePredictability": 85,
}

_OPTIONAL_OTHER_DEFAULTS: dict[str, Any] = {
    "SurfaceCoating": ["PEG (Stealth)"],
    "FunctionalGroups": [],
    "Ligand": "None",
}


def build_design_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Translate an API payload into the CapitalCase dict ``compute_impact`` takes.

    Only keys the caller actually supplied are forwarded. Absent keys are left
    absent so the canonical function applies its own documented defaults --
    this adapter does not duplicate them.

    Under the Step 1 DEFECT-D9 contract, an explicit ``null`` is equivalent to an
    absent key, so ``None`` values are simply passed through: the canonical
    helpers already treat them as absent.
    """
    design: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            # Pass through; core.scoring treats present-but-None as absent.
            design[key] = None
        else:
            design[key] = value
    return design


def _normalised_inputs(design: dict[str, Any]) -> dict[str, Any]:
    """Report the effective values the canonical function will use.

    Computed with the *canonical* helpers (``_optional_float`` /
    ``_optional_value``) rather than a local copy, so this can never drift from
    the scoring function's own interpretation of the input.
    """
    out: dict[str, Any] = {}

    for key in REQUIRED_DESIGN_KEYS:
        out[key] = design[key]  # KeyError here is caught by score_design()

    for key, default in _OPTIONAL_NUMERIC_DEFAULTS.items():
        out[key] = _optional_float(design, key, default)

    for key, default in _OPTIONAL_OTHER_DEFAULTS.items():
        out[key] = _optional_value(design, key, default)

    # HydrodynamicSize default is derived from Size inside compute_impact.
    out["HydrodynamicSize"] = _optional_float(
        design, "HydrodynamicSize", float(design["Size"]) * 1.2
    )
    return out


def _collect_warnings(payload: dict[str, Any], design: dict[str, Any]) -> list[str]:
    """Transparency notes about how the input was interpreted. Never blocking."""
    warnings: list[str] = []

    explicit_nulls = sorted(k for k, v in payload.items() if v is None)
    if explicit_nulls:
        warnings.append(
            "Fields supplied as null were treated as not provided and the "
            "documented default was used: " + ", ".join(explicit_nulls)
        )

    supplied = {k for k, v in payload.items() if v is not None}
    omitted = sorted(
        (set(_OPTIONAL_NUMERIC_DEFAULTS) | set(_OPTIONAL_OTHER_DEFAULTS))
        - supplied
    )
    if omitted:
        warnings.append(
            "Optional fields not provided; canonical defaults applied: "
            + ", ".join(omitted)
        )

    ligand = _optional_value(design, "Ligand", "None")
    if ligand == "None":
        warnings.append(
            "No targeting ligand specified. The canonical function applies a "
            "fixed passive-targeting baseline of 60/100 for the targeting "
            "component; its derivation is an open scientific question (Q7)."
        )

    if "SurfaceCoating" not in supplied:
        warnings.append(
            "SurfaceCoating not provided. The scoring function defaults to "
            "['PEG (Stealth)'], i.e. the design is scored as PEGylated. Whether "
            "this default is scientifically correct is open question Q6."
        )

    return warnings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def score_design(payload: dict[str, Any], weights: dict[str, float] | None = None) -> dict[str, Any]:
    """Score a design using the canonical function and wrap it with provenance.

    Raises
    ------
    ScoringFailure
        On any failure. No numeric fallback is ever produced.
    """
    design = build_design_dict(payload)

    # --- required-input check (mirrors the canonical KeyError contract) -----
    missing = [k for k in REQUIRED_DESIGN_KEYS
               if k not in design or design[k] is None]
    if missing:
        raise ScoringFailure(
            code="missing_required_input",
            message=(
                "Required design inputs are missing: " + ", ".join(missing)
            ),
            detail=(
                "Size, Charge and Encapsulation are scientifically required. They "
                "are never replaced by defaults, because substituting a value "
                "would silently invent an input."
            ),
        )

    try:
        normalized = _normalised_inputs(design)
    except Exception as exc:  # pragma: no cover - defensive
        raise ScoringFailure(
            code="input_normalisation_failed",
            message="Design inputs could not be normalised.",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    # --- the canonical calculation, called verbatim -------------------------
    try:
        impact = compute_impact(dict(design), weights)
    except KeyError as exc:
        raise ScoringFailure(
            code="missing_required_input",
            message=f"Required design input missing: {exc}",
        ) from exc
    except (TypeError, ValueError) as exc:
        raise ScoringFailure(
            code="invalid_input_value",
            message="A design input had a value the scoring function rejected.",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc
    except Exception as exc:
        raise ScoringFailure(
            code="calculation_failed",
            message="The score could not be calculated.",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    # A non-finite result is a failure, not a score.
    for name, value in impact.items():
        if value != value or value in (float("inf"), float("-inf")):
            raise ScoringFailure(
                code="calculation_failed",
                message=f"The {name} score was not a finite number.",
                detail=f"{name}={value!r}",
            )

    return {
        "design_impact_score": {
            "delivery": float(impact["Delivery"]),
            "toxicity": float(impact["Toxicity"]),
            "cost": float(impact["Cost"]),
        },
        "score_version": SCORE_VERSION,
        "component_scores": {
            "delivery": {
                "value": float(impact["Delivery"]),
                "scale": "0-100 (higher is better)",
                "meaning": "Predicted delivery performance of the formulation.",
            },
            "toxicity": {
                "value": float(impact["Toxicity"]),
                "scale": "0-10 (lower is better)",
                "meaning": "Predicted toxicity burden of the formulation.",
            },
            "cost": {
                "value": float(impact["Cost"]),
                "scale": "0-100 (lower is better)",
                "meaning": "Relative formulation cost indicator.",
            },
        },
        "normalized_inputs": normalized,
        "warnings": _collect_warnings(payload, design),
        "prediction_basis": PREDICTION_BASIS,
        "evidence_level": EVIDENCE_LEVEL,
        "validation_status": VALIDATION_STATUS,
        "limitations": list(LIMITATIONS),
        "scientific_source": SCIENTIFIC_SOURCE,
    }
