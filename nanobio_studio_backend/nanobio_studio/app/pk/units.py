"""Unit handling and dimensional validation for pharmacokinetic parameters.

Why this is a separate module with real checks
----------------------------------------------
The derivations ``k_el = CL / Vc``, ``k12 = Q / Vc`` and ``k21 = Q / Vp`` are
only correct when the clearance and volume are expressed in compatible units.
``CL`` in L/h divided by ``Vc`` in mL yields a number that is wrong by a factor
of a thousand and carries no visible sign of being wrong — it is still a
plausible-looking rate constant.

So units are not free text here. Every quantity carries a unit drawn from a
closed set, conversion is explicit, and a division whose dimensions do not
resolve to 1/time is rejected rather than performed.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

__all__ = [
    "Dimension",
    "Unit",
    "Quantity",
    "UnitError",
    "to_canonical",
    "divide",
]


class UnitError(ValueError):
    """A unit was unknown, or an operation's dimensions did not resolve."""


class Dimension(str, enum.Enum):
    VOLUME = "volume"
    FLOW = "volume/time"        # clearance, intercompartmental clearance
    TIME = "time"
    INVERSE_TIME = "1/time"
    MASS = "mass"
    MASS_PER_VOLUME = "mass/volume"
    DIMENSIONLESS = "dimensionless"


@dataclass(frozen=True)
class Unit:
    symbol: str
    dimension: Dimension
    #: Multiplier to the canonical unit of this dimension.
    to_canonical_factor: float


#: Canonical units: litre, litre/hour, hour, 1/hour, milligram, mg/L.
_UNITS: dict[str, Unit] = {
    # volume -> L
    "L": Unit("L", Dimension.VOLUME, 1.0),
    "mL": Unit("mL", Dimension.VOLUME, 1e-3),
    "dL": Unit("dL", Dimension.VOLUME, 1e-1),
    # flow -> L/h
    "L/h": Unit("L/h", Dimension.FLOW, 1.0),
    "mL/h": Unit("mL/h", Dimension.FLOW, 1e-3),
    "L/day": Unit("L/day", Dimension.FLOW, 1.0 / 24.0),
    "mL/min": Unit("mL/min", Dimension.FLOW, 1e-3 * 60.0),
    # time -> h
    "h": Unit("h", Dimension.TIME, 1.0),
    "min": Unit("min", Dimension.TIME, 1.0 / 60.0),
    "day": Unit("day", Dimension.TIME, 24.0),
    # inverse time -> 1/h
    "1/h": Unit("1/h", Dimension.INVERSE_TIME, 1.0),
    "1/day": Unit("1/day", Dimension.INVERSE_TIME, 1.0 / 24.0),
    # mass -> mg
    "mg": Unit("mg", Dimension.MASS, 1.0),
    "g": Unit("g", Dimension.MASS, 1e3),
    "ug": Unit("ug", Dimension.MASS, 1e-3),
    # mass/volume -> mg/L
    "mg/L": Unit("mg/L", Dimension.MASS_PER_VOLUME, 1.0),
    "ug/mL": Unit("ug/mL", Dimension.MASS_PER_VOLUME, 1.0),   # identical
    "ug/L": Unit("ug/L", Dimension.MASS_PER_VOLUME, 1e-3),
    "ng/mL": Unit("ng/mL", Dimension.MASS_PER_VOLUME, 1e-3),
    "g/L": Unit("g/L", Dimension.MASS_PER_VOLUME, 1e3),
    # dimensionless
    "": Unit("", Dimension.DIMENSIONLESS, 1.0),
    "fraction": Unit("fraction", Dimension.DIMENSIONLESS, 1.0),
}

#: The canonical unit symbol for each dimension.
CANONICAL: dict[Dimension, str] = {
    Dimension.VOLUME: "L",
    Dimension.FLOW: "L/h",
    Dimension.TIME: "h",
    Dimension.INVERSE_TIME: "1/h",
    Dimension.MASS: "mg",
    Dimension.MASS_PER_VOLUME: "mg/L",
    Dimension.DIMENSIONLESS: "",
}


@dataclass(frozen=True)
class Quantity:
    """A number with a unit. Immutable, so a converted copy is always explicit."""

    value: float
    unit: str

    def __post_init__(self) -> None:
        if self.unit not in _UNITS:
            raise UnitError(
                f"Unknown unit {self.unit!r}. Known units: "
                + ", ".join(sorted(u for u in _UNITS if u))
            )

    @property
    def dimension(self) -> Dimension:
        return _UNITS[self.unit].dimension

    def canonical(self) -> "Quantity":
        spec = _UNITS[self.unit]
        return Quantity(self.value * spec.to_canonical_factor,
                        CANONICAL[spec.dimension])

    def require(self, dimension: Dimension, name: str) -> "Quantity":
        """Assert this quantity's dimension, or fail with a usable message."""
        if self.dimension is not dimension:
            raise UnitError(
                f"{name} must be a {dimension.value} quantity, but "
                f"{self.value}{self.unit} is {self.dimension.value}."
            )
        return self

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.value} {self.unit}".strip()


def to_canonical(value: float, unit: str) -> Quantity:
    return Quantity(value, unit).canonical()


def divide(numerator: Quantity, denominator: Quantity, *,
           expect: Dimension, name: str) -> Quantity:
    """Divide two quantities and assert the resulting dimension.

    This is the guard that makes ``CL / Vc`` safe: both operands are converted
    to canonical units first, and the result's dimension is checked against what
    the caller expects. A flow divided by a volume is a rate; a flow divided by
    a time is not, and is refused.
    """
    a = numerator.canonical()
    b = denominator.canonical()

    if b.value == 0:
        raise UnitError(f"{name}: division by zero ({denominator}).")

    resolved = _resolve(a.dimension, b.dimension)
    if resolved is not expect:
        raise UnitError(
            f"{name}: dividing {a.dimension.value} by {b.dimension.value} "
            f"yields {resolved.value if resolved else 'an unsupported dimension'}, "
            f"not {expect.value}."
        )
    return Quantity(a.value / b.value, CANONICAL[expect])


def _resolve(numerator: Dimension, denominator: Dimension) -> Dimension | None:
    """The dimension of numerator/denominator, for the combinations we support."""
    table: dict[tuple[Dimension, Dimension], Dimension] = {
        (Dimension.FLOW, Dimension.VOLUME): Dimension.INVERSE_TIME,
        (Dimension.VOLUME, Dimension.FLOW): Dimension.TIME,
        (Dimension.MASS, Dimension.VOLUME): Dimension.MASS_PER_VOLUME,
        (Dimension.MASS, Dimension.TIME): Dimension.FLOW,   # not physical here
        (Dimension.DIMENSIONLESS, Dimension.TIME): Dimension.INVERSE_TIME,
    }
    return table.get((numerator, denominator))
