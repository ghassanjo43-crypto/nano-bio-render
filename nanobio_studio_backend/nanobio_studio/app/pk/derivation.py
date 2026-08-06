"""Derive first-order rate constants from clearances and volumes.

The derivations
---------------
For a **linear two-compartment model** parameterised as (CL, Vc, Q, Vp):

    k_el = CL / Vc      elimination from the central compartment
    k_12 = Q  / Vc      central -> peripheral
    k_21 = Q  / Vp      peripheral -> central

These are algebraic restatements of the same model, not a new one: the
micro-constant and clearance parameterisations are equivalent for this
structure.

When they must NOT be applied
-----------------------------
The identities hold only for the linear two-compartment structure. Applying them
to a one-compartment set (no Q, no Vp), or to a model with parallel
Michaelis-Menten or target-mediated elimination (where clearance is not
constant), produces a number that has the right units and no meaning. So the
model structure is checked first and an incompatible set is refused.

Every derived value records the formula and the exact source quantities that
produced it, so the arithmetic is auditable rather than asserted.
"""

from __future__ import annotations

from dataclasses import dataclass

from .parameter_library import ModelStructure, ParameterSet
from .units import Dimension, Quantity, UnitError, divide

__all__ = [
    "DerivedConstant",
    "DerivationError",
    "DERIVABLE_STRUCTURES",
    "derive_rate_constants",
]


class DerivationError(ValueError):
    """A derivation could not be performed. Never returns a fallback number."""

    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


#: Only this structure supports the CL/V derivations.
DERIVABLE_STRUCTURES = frozenset({ModelStructure.TWO_COMPARTMENT_LINEAR})


@dataclass(frozen=True)
class DerivedConstant:
    """A rate constant computed from cited parameters, with its working shown."""

    name: str
    value: float
    unit: str
    formula: str
    #: The source quantities, as `name -> "value unit"`, exactly as cited.
    source_values: dict[str, str]
    #: Constant label for the interface. Derived values are never presented as
    #: something the user typed.
    provenance: str = "calculated_from_cited_model_parameters"


_REQUIRED = {
    "CL": Dimension.FLOW,
    "Vc": Dimension.VOLUME,
    "Q": Dimension.FLOW,
    "Vp": Dimension.VOLUME,
}


def derive_rate_constants(parameter_set: ParameterSet) -> dict[str, DerivedConstant]:
    """Derive k_el, k_12 and k_21 from a linear two-compartment parameter set.

    Raises
    ------
    DerivationError
        If the structure is incompatible, a parameter is missing, or the units
        do not resolve. No partial or defaulted result is ever returned.
    """
    if parameter_set.model_structure not in DERIVABLE_STRUCTURES:
        raise DerivationError(
            code="incompatible_model_structure",
            message=(
                "Rate constants cannot be derived from this parameter set: the "
                f"derivations apply to a linear two-compartment model, and this "
                f"set is expressed for {parameter_set.model_structure.value}."
            ),
            detail=(
                "k_el = CL/Vc assumes a constant clearance. In a model with "
                "saturable or target-mediated elimination, clearance varies "
                "with concentration and no single k_el exists."
            ),
        )

    missing = [name for name in _REQUIRED if name not in parameter_set.parameters]
    if missing:
        raise DerivationError(
            code="missing_parameters",
            message=("Cannot derive rate constants; the parameter set is "
                     "missing: " + ", ".join(sorted(missing))),
            detail=(
                "All four of CL, Vc, Q and Vp are required. No value is "
                "substituted for a missing one."
            ),
        )

    # Validate dimensions up front so a unit error is reported as a unit error,
    # not as a strange-looking rate constant.
    q: dict[str, Quantity] = {}
    for name, expected in _REQUIRED.items():
        pv = parameter_set.parameters[name]
        try:
            q[name] = Quantity(pv.value, pv.unit).require(expected, name)
        except UnitError as exc:
            raise DerivationError(
                code="unit_mismatch",
                message=f"Parameter {name} has an incompatible unit.",
                detail=str(exc),
            ) from exc

    def _derive(name: str, num: str, den: str) -> DerivedConstant:
        try:
            result = divide(q[num], q[den],
                            expect=Dimension.INVERSE_TIME, name=name)
        except UnitError as exc:
            raise DerivationError(
                code="unit_mismatch",
                message=f"Could not derive {name}: {exc}",
                detail=f"{num}={q[num]}, {den}={q[den]}",
            ) from exc
        return DerivedConstant(
            name=name,
            value=result.value,
            unit=result.unit,
            formula=f"{name} = {num} / {den}",
            source_values={
                num: str(parameter_set.parameters[num].value) + " "
                     + parameter_set.parameters[num].unit,
                den: str(parameter_set.parameters[den].value) + " "
                     + parameter_set.parameters[den].unit,
            },
        )

    return {
        "k_el": _derive("k_el", "CL", "Vc"),
        "k_12": _derive("k_12", "Q", "Vc"),
        "k_21": _derive("k_21", "Q", "Vp"),
    }
