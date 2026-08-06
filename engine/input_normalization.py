"""Canonical normalisation of formulation inputs.

Why this module exists
----------------------
The legacy code decided "is a targeting ligand present?" by evaluating the raw
string with Python truthiness. That is wrong, because the sentinel the UI actually
stores is the **string** ``"None"``, which is truthy:

    >>> bool("None")
    True

So an untargeted formulation was treated as targeted. ``regulatory_engine.py``
contained both the broken form (``if design_inputs.targeting_ligand``) and a
correct one (``... .lower() != "none"``) a few lines apart.

DECISION 5 requires a canonical null representation rather than permanent reliance
on the string ``"None"``. Everything that asks "is this modification present?" must
route through this module.

Scientific positioning
----------------------
Nothing here is a scientific model. These are input-hygiene helpers. They do not
predict, score, or validate anything.
"""

from __future__ import annotations

import enum
from typing import Optional

__all__ = [
    "Presence",
    "NULL_TOKENS",
    "normalise_ligand",
    "has_targeting_ligand",
    "has_peg_coating",
    "manufacturing_complexity_count",
    "MANUFACTURING_COMPLEXITY_BASIS",
    "MANUFACTURING_COMPLEXITY_RANGE",
]


class Presence(enum.Enum):
    """Canonical presence of an optional formulation modification."""

    ABSENT = "absent"
    PRESENT = "present"

    @property
    def as_int(self) -> int:
        return 1 if self is Presence.PRESENT else 0


#: Strings that mean "no value", case-insensitively and whitespace-insensitively.
#: ``"none"`` is included because it is the sentinel the legacy UI stores; it is
#: recognised here precisely so that no other module has to special-case it.
NULL_TOKENS = frozenset({
    "", "none", "null", "nil", "n/a", "na", "-", "--", "nan", "no", "false",
    "not applicable", "not specified", "unspecified", "undefined",
})


def normalise_ligand(value: object) -> Optional[str]:
    """Return a cleaned ligand name, or ``None`` when no ligand is present.

    ``None`` is the canonical absent representation. The string ``"None"`` and the
    other :data:`NULL_TOKENS` all normalise to ``None``.

    >>> normalise_ligand("GalNAc")
    'GalNAc'
    >>> normalise_ligand("  Transferrin ")
    'Transferrin'
    >>> normalise_ligand("None") is None
    True
    >>> normalise_ligand("") is None
    True
    >>> normalise_ligand(None) is None
    True
    """
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.casefold() in NULL_TOKENS:
            return None
        return cleaned or None
    # Non-string, non-None: keep it but stringify, so callers get a stable type.
    text = str(value).strip()
    return None if text.casefold() in NULL_TOKENS else (text or None)


def has_targeting_ligand(value: object) -> bool:
    """True when a real targeting ligand is present.

    >>> has_targeting_ligand("GalNAc"), has_targeting_ligand("None")
    (True, False)
    """
    return normalise_ligand(value) is not None


def has_peg_coating(value: object) -> bool:
    """True when PEG surface coating is present.

    Accepts the ``bool`` used by ``TrialDesignInputs.peg_surface_coating`` and is
    also tolerant of the string forms other layers may supply.

    >>> has_peg_coating(True), has_peg_coating(False)
    (True, False)
    >>> has_peg_coating("None"), has_peg_coating("PEG (Stealth)")
    (False, True)
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().casefold() not in NULL_TOKENS
    if isinstance(value, (list, tuple, set, frozenset)):
        # A coating list, e.g. ["PEG (Stealth)"]; empty means absent.
        return any(has_peg_coating(v) for v in value)
    return bool(value)


#: Human-readable basis string. Required wording per DECISION 5: this indicator
#: must never be described as validated manufacturability, regulatory approval
#: probability, production success, or clinical evidence.
MANUFACTURING_COMPLEXITY_BASIS = "Rule-based manufacturing complexity indicator"

#: Inclusive range of :func:`manufacturing_complexity_count`.
MANUFACTURING_COMPLEXITY_RANGE = (0, 2)


def manufacturing_complexity_count(
    peg_surface_coating: object,
    targeting_ligand: object,
) -> int:
    """Count present surface modifications as an integer 0-2 (DECISION 5).

    ``0`` neither PEG coating nor targeting ligand
    ``1`` exactly one modification present
    ``2`` both present

    This is a **rule-based indicator of process complexity**, derived only from
    which modifications the formulation declares. It is *not* a manufacturability
    prediction, not a probability of production success, not a regulatory
    approval likelihood, and carries no experimental validation.

    >>> manufacturing_complexity_count(False, "None")
    0
    >>> manufacturing_complexity_count(True, "None")
    1
    >>> manufacturing_complexity_count(False, "GalNAc")
    1
    >>> manufacturing_complexity_count(True, "GalNAc")
    2
    """
    return int(has_peg_coating(peg_surface_coating)) + int(
        has_targeting_ligand(targeting_ligand)
    )
