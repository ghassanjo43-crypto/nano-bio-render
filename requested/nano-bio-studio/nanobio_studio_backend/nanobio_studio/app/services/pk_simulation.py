"""Adapter between the API layer and the canonical pharmacokinetic model.

Scientific source of truth
--------------------------
``utils/pk_model.py`` in the repository root — the two-compartment model that
the legacy Streamlit page ``modules/simulation.py`` executed. Both
``two_compartment_model()`` and ``calculate_pk_parameters()`` are imported and
called **verbatim**. Nothing in this module reimplements, re-derives, adjusts,
rounds or recalibrates any part of the model.

If a number here differs from the legacy Streamlit application for the same
input, that is a bug in this adapter — not a correction.

Why the legacy implementation was left untouched
------------------------------------------------
The audit (``docs/CURRENT_APPLICATION_AUDIT.md`` §3.2) records that the explicit
forward-Euler loop at fixed ``dt`` **is** the model's numerical identity.
Substituting ``scipy.integrate.solve_ivp`` or any adaptive solver changes the
results. The golden-vector suite asserts this and this adapter preserves it: the
same loop runs, at the same step size, in the same order.

What this module IS allowed to do
---------------------------------
* validate that every scientifically required input is present and usable;
* call the legacy functions and convert their NumPy output to JSON-safe values;
* attach provenance (calculation version, assumptions, evidence, limitations);
* convert failures into structured errors.

What it must NOT do
-------------------
* change, tune or "improve" any equation, constant or integration step;
* derive a quantity the legacy model does not produce (notably **clearance** —
  see ``QUANTITIES_NOT_PRODUCED``);
* substitute a default for a missing scientific input;
* return a favourable number when a calculation fails;
* consume, or appear to consume, the disease/therapeutic selection — the model
  takes no such input;
* mix its output with the design impact score, which is a different calculation.

Scientific positioning
----------------------
The output is a computational research-planning result. It is not experimentally
validated, not clinically validated, not a regulatory approval prediction, not a
diagnosis, not a treatment recommendation, and not a substitute for wet-lab or
in-vivo pharmacokinetic study.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# TEMPORARY path bootstrap (vertical slice only)
# ---------------------------------------------------------------------------
# Identical rationale to services/design_scoring.py: the canonical scientific
# code still lives in the repository root beside the legacy Streamlit
# application. Removed once the scientific core is ported into the backend
# package. Documented as temporary in docs/PK_SLICE.md.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np  # noqa: E402  (import must follow the bootstrap)

from utils.pk_model import (  # noqa: E402
    calculate_pk_parameters,
    two_compartment_model,
)

__all__ = [
    "PK_CALCULATION_VERSION",
    "PK_MODEL_NAME",
    "SCIENTIFIC_SOURCE",
    "PREDICTION_BASIS",
    "EVIDENCE_LEVEL",
    "VALIDATION_STATUS",
    "ASSUMPTIONS",
    "LIMITATIONS",
    "QUANTITIES_NOT_PRODUCED",
    "REQUIRED_PK_INPUTS",
    "LEGACY_DURATION_H",
    "LEGACY_TIME_STEP_H",
    "PKSimulationFailure",
    "simulate_pk",
]

# ---------------------------------------------------------------------------
# Provenance constants
# ---------------------------------------------------------------------------

#: Version of THIS adapter's output contract *and* of the migrated model as
#: served. The legacy module carries no version of its own; assigning one is
#: recorded as open question Q-PK1 in docs/PK_SLICE.md. Bump on any change to
#: how the calculation is assembled, and never silently on a change to the
#: numbers — a numerical change is a separate, reviewed scientific decision.
PK_CALCULATION_VERSION = "pk-two-compartment-adapter-0.1.0"

PK_MODEL_NAME = "two_compartment_depot_forward_euler"

SCIENTIFIC_SOURCE = (
    "utils.pk_model.two_compartment_model + utils.pk_model.calculate_pk_parameters"
)

#: How the numbers were derived. A mechanistic compartmental ODE model solved
#: numerically — not a trained model, and not fitted to this formulation.
PREDICTION_BASIS = "mechanistic_compartmental_ode_forward_euler"

#: Evidence standing. The structure is textbook compartmental PK; the rate
#: constants are user-supplied and are not fitted to observed data here.
EVIDENCE_LEVEL = "structural_model_with_user_supplied_rate_constants"

#: Experimental validation status. Universally absent in this platform.
VALIDATION_STATUS = "not_experimentally_validated"

#: Scientific assumptions of the migrated model, stated so a reader can judge
#: the output. Taken from the model's own structure and from the migration
#: constraints recorded in docs/CURRENT_APPLICATION_AUDIT.md §3.2.
ASSUMPTIONS: tuple[str, ...] = (
    "Three-stage linear structure: depot (administration site) -> central "
    "(plasma) -> peripheral (tissue), with return transfer from peripheral.",
    "All transfers are first-order with constant rate coefficients; no "
    "saturable or concentration-dependent kinetics are modelled.",
    "Elimination occurs only from the central compartment.",
    "Rate constants (k_abs, k_el, k_12, k_21) are supplied by the user. They "
    "are not fitted, predicted, or derived from the formulation parameters.",
    "Solved by explicit forward-Euler integration at a fixed time step. The "
    "step size is part of the model's numerical identity: an adaptive solver "
    "would produce different numbers and is deliberately not used.",
    "The whole dose is placed in the depot compartment at t = 0.",
    "Compartment volumes are not modelled, so the state variables are "
    "dose-scaled amounts, reported in arbitrary units rather than mass per "
    "volume.",
    "AUC is computed by the trapezoidal rule over the simulated window only; "
    "it is not extrapolated to infinity.",
    "Terminal half-life is read as the first time after the peak at which the "
    "central-compartment value falls to half the peak. It is reported as null "
    "when that never happens inside the simulated window.",
)

LIMITATIONS: tuple[str, ...] = (
    "Computational research-planning result only. Not experimentally "
    "validated, not clinically validated, and not a substitute for an in-vivo "
    "pharmacokinetic study.",
    "Not a regulatory approval prediction, diagnosis, dosing recommendation, "
    "or treatment recommendation.",
    "The rate constants are inputs, not predictions. The model does not infer "
    "them from particle size, charge, coating or any other design parameter, "
    "so the profile reflects the rate constants entered rather than the "
    "formulation itself.",
    "No compartment volume is modelled, so concentrations are in arbitrary "
    "dose-scaled units. Values must not be read as ng/mL or any other "
    "mass-per-volume unit.",
    "AUC is truncated at the end of the simulated window; no extrapolation to "
    "infinity is performed, so it is not AUC(0-inf).",
    "No inter-individual variability, uncertainty quantification or confidence "
    "interval is produced. The model is deterministic.",
    "The disease, subtype and therapeutic agent selected in the workflow are "
    "NOT inputs to this model and do not affect any value it returns.",
    "This is a separate calculation from the design impact score. The two "
    "share no inputs, no model and no version, and must not be combined.",
    "The legacy PDF report labelled these values 'ng/mL'. That label was "
    "inconsistent with the model, which has no volume term, and is not "
    "reproduced here.",
)

#: Quantities a reader might expect from a PK run that this migrated model does
#: NOT produce. Listed explicitly so their absence is a stated fact rather than
#: an unexplained gap. Deriving any of them would require new science and
#: scientific approval, which this slice does not have.
QUANTITIES_NOT_PRODUCED: tuple[dict[str, str], ...] = (
    {
        "quantity": "clearance",
        "reason": (
            "The migrated model has no volume-of-distribution term, so a "
            "clearance in volume/time cannot be derived from its output. "
            "Computing one (for example Dose/AUC) would introduce a new "
            "scientific quantity that the legacy implementation never "
            "produced, so none is returned."
        ),
    },
    {
        "quantity": "volume_of_distribution",
        "reason": (
            "Not modelled. The state variables are dose-scaled amounts, not "
            "concentrations, so no volume term exists to report."
        ),
    },
    {
        "quantity": "bioavailability",
        "reason": (
            "Not modelled. The full dose is placed in the depot compartment "
            "and no absorbed fraction is estimated."
        ),
    },
    {
        "quantity": "auc_extrapolated_to_infinity",
        "reason": (
            "The legacy implementation integrates over the simulated window "
            "only. Extrapolation would be a new calculation."
        ),
    },
)

#: Scientifically required inputs. These are NEVER defaulted: substituting a
#: value would silently invent the pharmacokinetics being reported.
REQUIRED_PK_INPUTS: tuple[str, ...] = ("dose", "kabs", "kel", "k12", "k21")

#: Numerical-window settings and their legacy defaults, taken from
#: utils/pk_model.py's own signature. These are simulation settings rather than
#: properties of the system, and the legacy Streamlit page applied exactly these
#: values when the user did not change them.
LEGACY_DURATION_H = 48.0
LEGACY_TIME_STEP_H = 0.1


class PKSimulationFailure(RuntimeError):
    """Raised when a pharmacokinetic profile cannot be produced.

    Carries a machine-readable ``code`` so the API can return a structured error
    instead of numbers. There is deliberately no fallback profile: a failed
    calculation must never yield a favourable curve, half-life or AUC.
    """

    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------


def _require_finite(name: str, value: Any) -> float:
    """Coerce one required input to a finite float, or fail loudly."""
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PKSimulationFailure(
            code="invalid_input_value",
            message=f"Pharmacokinetic input '{name}' is not a number.",
            detail=f"{type(exc).__name__}: {value!r}",
        ) from exc

    if not math.isfinite(number):
        raise PKSimulationFailure(
            code="invalid_input_value",
            message=f"Pharmacokinetic input '{name}' must be a finite number.",
            detail=f"{name}={value!r}",
        )
    return number


def _json_safe(value: Any) -> Any:
    """Convert a NumPy scalar to a JSON-serialisable Python value.

    Non-finite results are rejected rather than serialised: NaN and Infinity are
    not valid JSON and, more importantly, are not a pharmacokinetic result.
    """
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        raise PKSimulationFailure(
            code="calculation_failed",
            message="The pharmacokinetic model produced a non-finite value.",
            detail=repr(value),
        )
    return number


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def simulate_pk(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the migrated two-compartment model and wrap it with provenance.

    Parameters
    ----------
    payload
        Keys ``dose``, ``kabs``, ``kel``, ``k12``, ``k21`` are required.
        ``duration`` and ``dt`` are optional and fall back to the legacy
        defaults declared in ``utils/pk_model.py``.

    Raises
    ------
    PKSimulationFailure
        On any failure. No numeric fallback is ever produced.
    """
    # --- required-input check ----------------------------------------------
    missing = [k for k in REQUIRED_PK_INPUTS
               if k not in payload or payload[k] is None]
    if missing:
        raise PKSimulationFailure(
            code="missing_required_input",
            message=(
                "Required pharmacokinetic inputs are missing: "
                + ", ".join(missing)
            ),
            detail=(
                "Dose and the four first-order rate constants are "
                "scientifically required. They are never replaced by a "
                "default, because substituting one would invent the "
                "pharmacokinetics being reported."
            ),
        )

    values = {k: _require_finite(k, payload[k]) for k in REQUIRED_PK_INPUTS}

    duration_supplied = payload.get("duration") is not None
    step_supplied = payload.get("dt") is not None
    duration = (_require_finite("duration", payload["duration"])
                if duration_supplied else LEGACY_DURATION_H)
    dt = (_require_finite("dt", payload["dt"])
          if step_supplied else LEGACY_TIME_STEP_H)

    # The integration window must be usable. These are structural requirements
    # of the loop, not scientific judgements about a plausible range.
    if dt <= 0:
        raise PKSimulationFailure(
            code="invalid_input_value",
            message="The integration time step must be greater than zero.",
            detail=f"dt={dt!r}",
        )
    if duration <= 0:
        raise PKSimulationFailure(
            code="invalid_input_value",
            message="The simulation duration must be greater than zero.",
            detail=f"duration={duration!r}",
        )
    if dt > duration:
        raise PKSimulationFailure(
            code="invalid_input_value",
            message=(
                "The integration time step cannot exceed the simulation "
                "duration."
            ),
            detail=f"dt={dt!r}, duration={duration!r}",
        )

    # --- the canonical calculation, called verbatim -------------------------
    try:
        time, c_plasma, c_tissue = two_compartment_model(
            dose=values["dose"],
            kabs=values["kabs"],
            kel=values["kel"],
            k12=values["k12"],
            k21=values["k21"],
            duration=duration,
            dt=dt,
        )
    except (TypeError, ValueError) as exc:
        raise PKSimulationFailure(
            code="invalid_input_value",
            message="A pharmacokinetic input was rejected by the model.",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc
    except Exception as exc:
        raise PKSimulationFailure(
            code="calculation_failed",
            message="The pharmacokinetic profile could not be calculated.",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    try:
        pk_params = calculate_pk_parameters(time, c_plasma, c_tissue)
    except Exception as exc:
        raise PKSimulationFailure(
            code="calculation_failed",
            message="The derived pharmacokinetic parameters could not be "
                    "calculated.",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    # A non-finite curve is a failure, not a profile.
    for label, series in (("time", time), ("plasma", c_plasma),
                          ("tissue", c_tissue)):
        if not np.all(np.isfinite(series)):
            raise PKSimulationFailure(
                code="calculation_failed",
                message=(
                    f"The {label} series contained a non-finite value. No "
                    "profile is returned."
                ),
                detail=(
                    "Forward-Euler integration can diverge when a rate "
                    "constant is large relative to the time step."
                ),
            )

    return {
        "concentration_time": {
            "time_h": [_json_safe(v) for v in time],
            "central_plasma": [_json_safe(v) for v in c_plasma],
            "peripheral_tissue": [_json_safe(v) for v in c_tissue],
            "point_count": int(len(time)),
            "concentration_unit": "arbitrary units (dose-scaled amount)",
            "time_unit": "hours",
        },
        "pk_parameters": _build_parameters(pk_params),
        "calculation_version": PK_CALCULATION_VERSION,
        "model_name": PK_MODEL_NAME,
        "normalized_inputs": {
            "dose": values["dose"],
            "kabs": values["kabs"],
            "kel": values["kel"],
            "k12": values["k12"],
            "k21": values["k21"],
            "duration": duration,
            "dt": dt,
        },
        "warnings": _collect_warnings(
            values, duration, dt,
            duration_supplied=duration_supplied,
            step_supplied=step_supplied,
            half_life=pk_params.get("t_half_plasma"),
        ),
        "assumptions": list(ASSUMPTIONS),
        "limitations": list(LIMITATIONS),
        "quantities_not_produced": [dict(q) for q in QUANTITIES_NOT_PRODUCED],
        "prediction_basis": PREDICTION_BASIS,
        "evidence_level": EVIDENCE_LEVEL,
        "validation_status": VALIDATION_STATUS,
        "scientific_source": SCIENTIFIC_SOURCE,
    }


def _build_parameters(pk_params: dict[str, Any]) -> dict[str, Any]:
    """Expose exactly the parameters the legacy function returns.

    Every key below exists in ``calculate_pk_parameters``' return value. No
    parameter is added, renamed into something it is not, or derived.
    ``half_life_central_h`` is deliberately nullable, mirroring the legacy
    contract that the half-life is unknown when the curve never halves inside
    the simulated window.
    """
    return {
        "peak_concentration_central": _json_safe(pk_params["C_max_plasma"]),
        "peak_concentration_peripheral": _json_safe(pk_params["C_max_tissue"]),
        "time_to_peak_central_h": _json_safe(pk_params["T_max_plasma"]),
        "time_to_peak_peripheral_h": _json_safe(pk_params["T_max_tissue"]),
        "auc_central": _json_safe(pk_params["AUC_plasma"]),
        "auc_peripheral": _json_safe(pk_params["AUC_tissue"]),
        "half_life_central_h": _json_safe(pk_params["t_half_plasma"]),
        "tissue_accumulation_ratio": _json_safe(
            pk_params["tissue_accumulation_ratio"]),
        "vss_ratio": _json_safe(pk_params["Vss_ratio"]),
    }


def _collect_warnings(
    values: dict[str, float],
    duration: float,
    dt: float,
    *,
    duration_supplied: bool,
    step_supplied: bool,
    half_life: Any,
) -> list[str]:
    """Transparency notes about how the run was configured and read.

    These are never blocking and never change a number. They exist so a reader
    can tell which values were theirs and which came from the legacy defaults.
    """
    warnings: list[str] = []

    defaulted: list[str] = []
    if not duration_supplied:
        defaulted.append(f"duration = {LEGACY_DURATION_H} h")
    if not step_supplied:
        defaulted.append(f"time step = {LEGACY_TIME_STEP_H} h")
    if defaulted:
        warnings.append(
            "Simulation window not fully specified; the legacy documented "
            "defaults were applied: " + ", ".join(defaulted) + ". These are "
            "numerical settings, not scientific inputs — the dose and rate "
            "constants were never defaulted."
        )

    if step_supplied and dt != LEGACY_TIME_STEP_H:
        warnings.append(
            f"A non-default integration step ({dt} h) was used. The legacy "
            f"model's reference step is {LEGACY_TIME_STEP_H} h; because the "
            "solver is explicit forward Euler, changing the step changes the "
            "numbers. Results at different step sizes are not interchangeable."
        )

    if half_life is None:
        warnings.append(
            "Terminal half-life could not be determined: the central "
            "compartment never fell to half its peak within the simulated "
            f"window of {duration} h. It is reported as null rather than "
            "estimated or extrapolated."
        )

    if values["kel"] == 0:
        warnings.append(
            "The elimination rate constant is zero, so the model removes no "
            "drug from the central compartment. The profile describes "
            "distribution only."
        )

    if values["dose"] == 0:
        warnings.append(
            "The dose is zero, so every concentration in the profile is zero. "
            "The result is returned as calculated rather than suppressed."
        )

    # Explicit Euler is only stable when the step is small relative to the
    # fastest rate. This flags the condition; it does not alter the result.
    fastest = max(values["kabs"], values["kel"], values["k12"], values["k21"])
    if fastest > 0 and dt * fastest > 1.0:
        warnings.append(
            f"The time step ({dt} h) is large relative to the fastest rate "
            f"constant ({fastest} per h). Explicit forward-Euler integration "
            "can be inaccurate or unstable in this regime. The value is "
            "reported as calculated; it has not been corrected."
        )

    warnings.append(
        "Concentrations are in arbitrary dose-scaled units. The model has no "
        "volume term, so they are not mass-per-volume concentrations."
    )

    return warnings
