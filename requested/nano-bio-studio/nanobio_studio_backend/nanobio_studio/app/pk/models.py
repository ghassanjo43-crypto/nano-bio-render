"""Route-specific two-compartment models.

Scientific justification for adding these equations
---------------------------------------------------
The pre-existing engine (``utils/pk_model.two_compartment_model``) places the
whole dose in a depot compartment and moves it into the central compartment by a
first-order rate ``k_abs``. That is an **extravascular model**. It cannot
represent intravenous administration:

* ``C_plasma[0]`` is always 0, whereas an IV bolus has the entire dose in the
  central compartment at t = 0;
* the limit ``k_abs -> infinity`` is not reachable numerically — at
  ``k_abs * dt > 1`` the explicit Euler step overshoots and the model returns
  **negative concentrations**, then diverges (verified: at dt = 0.1 h,
  k_abs = 20 /h gives a minimum of -93.8; k_abs = 50 /h overflows to ~1e146);
* ``k_abs = 0`` yields an all-zero profile, so absorption cannot be switched off.

So intravenous administration required new equations rather than a new
parameterisation of the old ones. These are the standard linear two-compartment
equations in **amounts**, which is what makes the volume terms explicit and the
output a genuine mass-per-volume concentration:

    IV bolus            A_c(0) = F * Dose,  A_p(0) = 0
    IV infusion         A_c(0) = 0, constant input R0 = F * Dose / T_inf
                        while t < T_inf
    Extravascular       A_d(0) = Dose, first-order transfer F * k_a * A_d

    dA_c/dt = <input> - (k_el + k_12) * A_c + k_21 * A_p
    dA_p/dt =           k_12 * A_c        - k_21 * A_p

    C_c = A_c / V_c        C_p = A_p / V_p

What was NOT changed
--------------------
``utils/pk_model.py`` is untouched. Its depot model, its Euler loop, its step
size and its outputs are byte-identical, and its golden-vector tests are
unchanged. This module is a **separate, separately-versioned** implementation
that runs alongside it; nothing here reaches back into it.

Numerical scheme
----------------
Explicit forward Euler at a fixed step, matching the existing engine so the two
remain comparable. Euler is conditionally stable, so the caller is warned when
``dt * fastest_rate > 1``. ``verify_against_analytical_solution`` checks the
implementation against the closed-form biexponential IV-bolus solution, so the
integrator is validated rather than assumed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .administration import AdministrationRoute, InputFunction, route_spec

__all__ = [
    "PK_ENGINE_VERSION",
    "DoseRegimen",
    "ModelInputs",
    "SimulationOutput",
    "ModelExecutionError",
    "simulate",
    "analytical_iv_bolus_central",
    "verify_against_analytical_solution",
]

#: Version of THIS engine. Distinct from the legacy depot adapter's version, so
#: a stored run always says which of the two produced it.
PK_ENGINE_VERSION = "pk-route-aware-two-compartment-0.1.0"


class ModelExecutionError(RuntimeError):
    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


@dataclass(frozen=True)
class DoseRegimen:
    """What is given, how much, and how often."""

    #: Absolute dose per administration, in mg. Weight- or BSA-based dosing is
    #: resolved to an absolute amount BEFORE reaching the model, so the model
    #: never has to guess a body weight.
    dose_mg: float
    #: Infusion duration in hours. Required for IV infusion; ignored otherwise.
    infusion_duration_h: float | None = None
    #: Hours between doses. None for a single dose.
    dosing_interval_h: float | None = None
    number_of_doses: int = 1

    def __post_init__(self) -> None:
        if self.dose_mg < 0:
            raise ModelExecutionError("invalid_input",
                                      "Dose cannot be negative.")
        if self.number_of_doses < 1:
            raise ModelExecutionError("invalid_input",
                                      "Number of doses must be at least 1.")
        if self.number_of_doses > 1 and not self.dosing_interval_h:
            raise ModelExecutionError(
                "invalid_input",
                "A dosing interval is required for repeated dosing.",
                "Without an interval the model cannot place the later doses.")


@dataclass(frozen=True)
class ModelInputs:
    """Everything the model consumes. Volumes are required."""

    route: AdministrationRoute
    regimen: DoseRegimen
    k_el_per_h: float
    k_12_per_h: float
    k_21_per_h: float
    v_c_litres: float
    v_p_litres: float
    bioavailability: float = 1.0
    #: First-order absorption rate. Only for extravascular routes.
    k_abs_per_h: float | None = None
    duration_h: float = 48.0
    time_step_h: float = 0.01
    #: Reporting interval. Must be a multiple of the integration step.
    output_interval_h: float | None = None


@dataclass(frozen=True)
class SimulationOutput:
    time_h: list[float]
    central_concentration: list[float]
    peripheral_concentration: list[float]
    central_amount: list[float]
    peripheral_amount: list[float]
    concentration_unit: str
    amount_unit: str
    warnings: list[str]
    engine_version: str


def _dose_times(regimen: DoseRegimen) -> list[float]:
    if regimen.number_of_doses == 1:
        return [0.0]
    interval = regimen.dosing_interval_h or 0.0
    return [i * interval for i in range(regimen.number_of_doses)]


def simulate(inputs: ModelInputs) -> SimulationOutput:
    """Run the route-appropriate two-compartment model.

    Raises ``ModelExecutionError`` on any failure. There is no fallback profile.
    """
    spec = route_spec(inputs.route)

    # --- structural validation ---------------------------------------------
    if inputs.v_c_litres <= 0 or inputs.v_p_litres <= 0:
        raise ModelExecutionError(
            "invalid_input",
            "Central and peripheral volumes must be greater than zero.",
            "Concentrations are amount/volume; a zero volume has no meaning.")
    if inputs.time_step_h <= 0 or inputs.duration_h <= 0:
        raise ModelExecutionError("invalid_input",
                                  "Duration and time step must be positive.")
    if inputs.time_step_h > inputs.duration_h:
        raise ModelExecutionError(
            "invalid_input", "The time step cannot exceed the duration.")

    if spec.has_absorption_phase:
        if inputs.k_abs_per_h is None or inputs.k_abs_per_h <= 0:
            raise ModelExecutionError(
                "missing_required_input",
                f"{spec.label} administration requires a positive absorption "
                "rate constant.",
                "It is never defaulted: a substituted value would invent the "
                "absorption kinetics being reported.")
    elif inputs.k_abs_per_h is not None:
        # Refused rather than ignored. Silently discarding an input the user
        # supplied would let them believe it affected the result.
        raise ModelExecutionError(
            "input_not_applicable",
            f"An absorption rate constant was supplied for {spec.label}, which "
            "has no absorption phase.",
            "The dose enters the central compartment directly, so k_abs has no "
            "role in these equations.")

    if inputs.route is AdministrationRoute.IV_INFUSION:
        if not inputs.infusion_duration_or_none():
            raise ModelExecutionError(
                "missing_required_input",
                "Intravenous infusion requires an infusion duration.",
                "The infusion rate is dose / infusion duration; without it the "
                "input function is undefined.")

    # --- integration --------------------------------------------------------
    dt = float(inputs.time_step_h)
    n = int(round(inputs.duration_h / dt)) + 1
    time = np.arange(n) * dt

    a_central = np.zeros(n)
    a_periph = np.zeros(n)
    a_depot = np.zeros(n)

    k_el, k12, k21 = inputs.k_el_per_h, inputs.k_12_per_h, inputs.k_21_per_h
    f = inputs.bioavailability
    dose_times = _dose_times(inputs.regimen)
    t_inf = inputs.regimen.infusion_duration_h

    # Doses are placed on the nearest grid index. With a fixed step this is the
    # only unambiguous placement; the resulting time is reported back.
    bolus_idx: dict[int, float] = {}
    for t0 in dose_times:
        idx = int(round(t0 / dt))
        if 0 <= idx < n:
            bolus_idx[idx] = bolus_idx.get(idx, 0.0) + inputs.regimen.dose_mg

    def infusion_rate_at(t: float) -> float:
        """Total zero-order input rate at time t, summed over active infusions."""
        if t_inf is None or t_inf <= 0:
            return 0.0
        rate = f * inputs.regimen.dose_mg / t_inf
        active = sum(1 for t0 in dose_times if t0 <= t < t0 + t_inf)
        return rate * active

    # Initial conditions.
    if spec.input_function is InputFunction.INSTANTANEOUS_CENTRAL:
        a_central[0] = f * bolus_idx.get(0, 0.0)
    elif spec.input_function is InputFunction.FIRST_ORDER_DEPOT:
        a_depot[0] = bolus_idx.get(0, 0.0)
    # ZERO_ORDER_CENTRAL starts empty; input arrives through infusion_rate_at.

    ka = inputs.k_abs_per_h or 0.0

    for i in range(n - 1):
        t = time[i]

        absorption = 0.0
        if spec.input_function is InputFunction.FIRST_ORDER_DEPOT:
            d_depot = -ka * a_depot[i]
            absorption = f * ka * a_depot[i]
            a_depot[i + 1] = a_depot[i] + d_depot * dt

        infusion = (infusion_rate_at(t)
                    if spec.input_function is InputFunction.ZERO_ORDER_CENTRAL
                    else 0.0)

        d_central = (absorption + infusion
                     - (k_el + k12) * a_central[i]
                     + k21 * a_periph[i])
        d_periph = k12 * a_central[i] - k21 * a_periph[i]

        a_central[i + 1] = a_central[i] + d_central * dt
        a_periph[i + 1] = a_periph[i] + d_periph * dt

        # Later doses, applied after the step that lands on them.
        nxt = i + 1
        if nxt in bolus_idx and nxt != 0:
            if spec.input_function is InputFunction.INSTANTANEOUS_CENTRAL:
                a_central[nxt] += f * bolus_idx[nxt]
            elif spec.input_function is InputFunction.FIRST_ORDER_DEPOT:
                a_depot[nxt] += bolus_idx[nxt]

    if not (np.all(np.isfinite(a_central)) and np.all(np.isfinite(a_periph))):
        raise ModelExecutionError(
            "calculation_failed",
            "The model produced a non-finite value; no profile is returned.",
            "Explicit forward-Euler integration diverges when a rate constant "
            "is large relative to the time step.")

    warnings: list[str] = []
    fastest = max(k_el, k12, k21, ka)
    if fastest > 0 and dt * fastest > 1.0:
        warnings.append(
            f"The time step ({dt} h) is large relative to the fastest rate "
            f"constant ({fastest} /h). Explicit forward-Euler integration is "
            "unstable in this regime; the values are reported as calculated "
            "and have not been corrected.")
    if np.min(a_central) < 0 or np.min(a_periph) < 0:
        warnings.append(
            "The integration produced negative amounts, which are not "
            "physically possible. This indicates the time step is too large "
            "for these rate constants. The result should not be used.")

    # --- output thinning ----------------------------------------------------
    step = 1
    if inputs.output_interval_h:
        step = max(1, int(round(inputs.output_interval_h / dt)))
    sl = slice(None, None, step)

    return SimulationOutput(
        time_h=[float(v) for v in time[sl]],
        central_concentration=[float(v) for v in (a_central[sl] / inputs.v_c_litres)],
        peripheral_concentration=[float(v) for v in (a_periph[sl] / inputs.v_p_litres)],
        central_amount=[float(v) for v in a_central[sl]],
        peripheral_amount=[float(v) for v in a_periph[sl]],
        concentration_unit="mg/L",
        amount_unit="mg",
        warnings=warnings,
        engine_version=PK_ENGINE_VERSION,
    )


# Small helper kept on the dataclass for readability at the call site.
def _infusion_duration_or_none(self: ModelInputs) -> float | None:
    return self.regimen.infusion_duration_h


ModelInputs.infusion_duration_or_none = _infusion_duration_or_none  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Verification against the closed-form solution
# ---------------------------------------------------------------------------


def analytical_iv_bolus_central(dose_mg: float, k_el: float, k12: float,
                                k21: float, v_c: float,
                                t: np.ndarray) -> np.ndarray:
    """Closed-form central concentration for an IV bolus, two-compartment.

    The standard biexponential solution:

        C(t) = (D/Vc) * [ ((a - k21)/(a - b)) e^{-a t}
                        + ((k21 - b)/(a - b)) e^{-b t} ]

    where a (alpha) and b (beta) are the roots of
        s^2 + (k_el + k12 + k21) s + k_el * k21 = 0.

    Used only to verify the numerical integrator. It is never used to produce a
    reported result, because it exists for this one route and input function.
    """
    total = k_el + k12 + k21
    disc = math.sqrt(max(total * total - 4.0 * k_el * k21, 0.0))
    alpha = 0.5 * (total + disc)
    beta = 0.5 * (total - disc)
    if abs(alpha - beta) < 1e-12:
        raise ValueError("degenerate roots; analytical form does not apply")
    c0 = dose_mg / v_c
    return c0 * (((alpha - k21) / (alpha - beta)) * np.exp(-alpha * t)
                 + ((k21 - beta) / (alpha - beta)) * np.exp(-beta * t))


def verify_against_analytical_solution(
    *, dose_mg: float = 100.0, k_el: float = 0.1, k12: float = 0.3,
    k21: float = 0.15, v_c: float = 5.0, v_p: float = 10.0,
    duration_h: float = 48.0, time_step_h: float = 0.001,
) -> float:
    """Max relative error of the numerical IV-bolus solution. Lower is better.

    Exposed so the check can be run as a test rather than asserted in prose.
    """
    out = simulate(ModelInputs(
        route=AdministrationRoute.IV_BOLUS,
        regimen=DoseRegimen(dose_mg=dose_mg),
        k_el_per_h=k_el, k_12_per_h=k12, k_21_per_h=k21,
        v_c_litres=v_c, v_p_litres=v_p,
        duration_h=duration_h, time_step_h=time_step_h,
    ))
    t = np.array(out.time_h)
    numeric = np.array(out.central_concentration)
    exact = analytical_iv_bolus_central(dose_mg, k_el, k12, k21, v_c, t)
    # Compare where the exact solution is large enough for a relative error to
    # be meaningful.
    mask = exact > exact.max() * 1e-6
    return float(np.max(np.abs(numeric[mask] - exact[mask]) / exact[mask]))
