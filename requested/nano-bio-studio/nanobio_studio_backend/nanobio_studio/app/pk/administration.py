"""Administration routes, and what each one scientifically requires.

Why this module exists
----------------------
The pharmacokinetic input screen previously asked every user for an absorption
rate constant (``k_abs``), a depot-model parameter, regardless of how the drug
is given. For an intravenous therapeutic there is no absorption phase and no
depot: the dose enters the central compartment directly. Asking for ``k_abs``
in that situation is not a cosmetic problem — the value is genuinely consumed by
the depot model, so any number entered silently changes the reported profile of
a drug that has no absorption step at all.

This module is the single source of truth for which route implies which input
function, so the question "does this route have an absorption phase?" is
answered in one place and cannot drift between the schema, the API and the UI.

It contains **no parameters and no equations** — only the structural facts about
each route. Parameters live in ``parameter_library``; equations in ``models``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

__all__ = [
    "AdministrationRoute",
    "InputFunction",
    "RouteSpec",
    "ROUTES",
    "route_spec",
    "all_routes",
]


class AdministrationRoute(str, enum.Enum):
    """How the dose enters the body."""

    IV_BOLUS = "iv_bolus"
    IV_INFUSION = "iv_infusion"
    SUBCUTANEOUS = "subcutaneous"
    ORAL = "oral"
    INTRAPERITONEAL = "intraperitoneal"


class InputFunction(str, enum.Enum):
    """The mathematical form by which the dose enters the model.

    This is the property that actually decides whether an absorption constant is
    meaningful — not the route name.
    """

    #: Entire dose placed in the central compartment at t = 0.
    INSTANTANEOUS_CENTRAL = "instantaneous_central"
    #: Constant-rate input into the central compartment over a finite duration.
    ZERO_ORDER_CENTRAL = "zero_order_central"
    #: Dose placed in a depot and transferred first-order into the central
    #: compartment. The only form for which k_abs exists.
    FIRST_ORDER_DEPOT = "first_order_depot"


@dataclass(frozen=True)
class RouteSpec:
    route: AdministrationRoute
    label: str
    input_function: InputFunction
    #: Plain statement of how the dose enters. Shown to the user.
    description: str
    #: Inputs this route requires beyond the parameter set.
    required_dosing_inputs: tuple[str, ...] = ()
    #: Inputs that are meaningless for this route and must not be requested.
    not_applicable_inputs: tuple[str, ...] = ()
    #: Whether bioavailability F is a free parameter for this route.
    bioavailability_is_free: bool = True
    #: The value F takes when it is not free, and why.
    fixed_bioavailability: float | None = None
    fixed_bioavailability_reason: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_absorption_phase(self) -> bool:
        return self.input_function is InputFunction.FIRST_ORDER_DEPOT


ROUTES: dict[AdministrationRoute, RouteSpec] = {
    AdministrationRoute.IV_BOLUS: RouteSpec(
        route=AdministrationRoute.IV_BOLUS,
        label="Intravenous bolus",
        input_function=InputFunction.INSTANTANEOUS_CENTRAL,
        description=(
            "The entire dose is placed in the central compartment at time zero. "
            "There is no absorption phase and no depot compartment."
        ),
        required_dosing_inputs=("dose",),
        not_applicable_inputs=("k_abs", "infusion_duration_h"),
        bioavailability_is_free=False,
        fixed_bioavailability=1.0,
        fixed_bioavailability_reason=(
            "The dose is delivered directly into the systemic circulation, so "
            "the absorbed fraction is 1 by definition. This is a property of the "
            "route, not a fitted parameter."
        ),
    ),
    AdministrationRoute.IV_INFUSION: RouteSpec(
        route=AdministrationRoute.IV_INFUSION,
        label="Intravenous infusion",
        input_function=InputFunction.ZERO_ORDER_CENTRAL,
        description=(
            "The dose is delivered into the central compartment at a constant "
            "rate over the infusion duration. There is no absorption phase and "
            "no depot compartment."
        ),
        required_dosing_inputs=("dose", "infusion_duration_h"),
        not_applicable_inputs=("k_abs",),
        bioavailability_is_free=False,
        fixed_bioavailability=1.0,
        fixed_bioavailability_reason=(
            "The dose is delivered directly into the systemic circulation, so "
            "the absorbed fraction is 1 by definition."
        ),
        notes=(
            "The infusion rate is derived as dose / infusion duration; it is not "
            "entered separately, so the two cannot disagree.",
        ),
    ),
    AdministrationRoute.SUBCUTANEOUS: RouteSpec(
        route=AdministrationRoute.SUBCUTANEOUS,
        label="Subcutaneous",
        input_function=InputFunction.FIRST_ORDER_DEPOT,
        description=(
            "The dose is placed at the injection site and transferred into the "
            "central compartment by a first-order absorption process."
        ),
        required_dosing_inputs=("dose", "k_abs"),
        notes=(
            "Requires a route-specific parameter set: absorption rate and "
            "bioavailability for a subcutaneous dose are not transferable from "
            "an intravenous parameter set.",
        ),
    ),
    AdministrationRoute.ORAL: RouteSpec(
        route=AdministrationRoute.ORAL,
        label="Oral",
        input_function=InputFunction.FIRST_ORDER_DEPOT,
        description=(
            "The dose is placed in a gut depot and absorbed first-order into "
            "the central compartment."
        ),
        required_dosing_inputs=("dose", "k_abs"),
        notes=(
            "First-pass metabolism is not modelled separately; it can only be "
            "represented through the bioavailability of the parameter set.",
        ),
    ),
    AdministrationRoute.INTRAPERITONEAL: RouteSpec(
        route=AdministrationRoute.INTRAPERITONEAL,
        label="Intraperitoneal",
        input_function=InputFunction.FIRST_ORDER_DEPOT,
        description=(
            "The dose is placed in a peritoneal depot and absorbed first-order "
            "into the central compartment."
        ),
        required_dosing_inputs=("dose", "k_abs"),
        notes=(
            "Common in preclinical rodent studies. A parameter set derived from "
            "another route must not be reused here.",
        ),
    ),
}


def route_spec(route: AdministrationRoute | str) -> RouteSpec:
    """Look up a route. Raises KeyError for an unknown route rather than
    guessing a default, because guessing would change the input function."""
    if isinstance(route, str):
        route = AdministrationRoute(route)
    return ROUTES[route]


def all_routes() -> list[RouteSpec]:
    return [ROUTES[r] for r in AdministrationRoute]
