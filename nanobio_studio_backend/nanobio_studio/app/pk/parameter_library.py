"""Versioned library of pharmacokinetic parameter sets.

The contract
------------
A parameter set is a **cited claim about a specific drug, formulation, route and
population**. It is not a convenience default. Every set therefore carries its
therapeutic, formulation, route, population, indication, source citation, units,
model structure, version, review date, validation status and limitations — and
the dataclass makes all of those mandatory, so a set cannot be added without
them.

What "validated" means here
---------------------------
``ValidationStatus`` is a claim about evidence, not about whether the code runs.
A parameter set is only ``PUBLISHED_POPULATION_PK`` or ``REGULATORY_LABEL`` when
its values were taken from that source and the citation names it precisely. The
default is ``UNVERIFIED``, and unverified sets are refused by guided mode.

Why this library ships with no clinical parameter sets
------------------------------------------------------
Populating it requires reading an authoritative source — a regulatory product
label or a peer-reviewed population-PK publication — and recording the exact
population the parameters describe. That verification was **not** performed, so
no clinical set is included. Inventing plausible numbers, or copying them from
another drug or route, is precisely the failure this module exists to prevent.

The consequence is deliberate and correct: a therapeutic/route combination with
no reviewed parameter set reports itself as not operational and blocks
execution, rather than running on fabricated constants. See
``docs/PK_INPUT_SOURCES.md`` for what evidence is required to add a set.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .administration import AdministrationRoute
from .units import Dimension, Quantity

__all__ = [
    "ValidationStatus",
    "ModelStructure",
    "ParameterValue",
    "ParameterSet",
    "PARAMETER_LIBRARY",
    "LIBRARY_VERSION",
    "find_parameter_sets",
    "get_parameter_set",
    "guided_mode_sets",
]

#: Version of the library's *contents*. Bump whenever a set is added, changed or
#: withdrawn, so a stored run can be matched to the exact library it used.
LIBRARY_VERSION = "pk-parameter-library-0.1.0"


class ValidationStatus(str, enum.Enum):
    """The evidence standing of a parameter set."""

    #: Values taken from an approved regulatory product label.
    REGULATORY_LABEL = "regulatory_label"
    #: Values taken from a peer-reviewed population-PK publication.
    PUBLISHED_POPULATION_PK = "published_population_pk"
    #: Values from peer-reviewed non-population (e.g. preclinical) work.
    PUBLISHED_PRECLINICAL = "published_preclinical"
    #: Entered by a researcher for their own study. Never a platform claim.
    RESEARCHER_SUPPLIED = "researcher_supplied"
    #: Present but not traced to a source. Blocked from guided mode.
    UNVERIFIED = "unverified"


#: Only these may be offered in guided mode. Researcher-supplied parameters are
#: usable, but only through expert mode, where they are labelled as the
#: researcher's own inputs rather than as a platform prediction.
GUIDED_MODE_STATUSES = frozenset({
    ValidationStatus.REGULATORY_LABEL,
    ValidationStatus.PUBLISHED_POPULATION_PK,
})


class ModelStructure(str, enum.Enum):
    """The model a parameter set is expressed for.

    Parameters are only meaningful inside the structure they were estimated in.
    A two-compartment CL is not a one-compartment CL, and neither is usable in a
    target-mediated model.
    """

    ONE_COMPARTMENT_LINEAR = "one_compartment_linear"
    TWO_COMPARTMENT_LINEAR = "two_compartment_linear"
    TWO_COMPARTMENT_PARALLEL_LINEAR_MM = "two_compartment_parallel_linear_mm"
    TARGET_MEDIATED_DISPOSITION = "target_mediated_disposition"


@dataclass(frozen=True)
class ParameterValue:
    """One parameter, with its unit and expected dimension."""

    value: float
    unit: str
    dimension: Dimension

    def quantity(self, name: str) -> Quantity:
        return Quantity(self.value, self.unit).require(self.dimension, name)


@dataclass(frozen=True)
class ParameterSet:
    """A cited set of PK parameters for one drug/formulation/route/population."""

    # --- identity ----------------------------------------------------------
    id: str
    version: str

    # --- what it describes -------------------------------------------------
    therapeutic: str
    formulation: str
    route: AdministrationRoute
    population: str
    model_structure: ModelStructure
    indication: str | None

    # --- evidence ----------------------------------------------------------
    source_citation: str
    validation_status: ValidationStatus
    date_reviewed: str          # ISO date
    limitations: tuple[str, ...]

    # --- the parameters ----------------------------------------------------
    #: Keys are canonical names: CL, Vc, Q, Vp, F, ka.
    parameters: dict[str, ParameterValue] = field(default_factory=dict)

    #: Covariate relationships the SET documents. A covariate is only applied if
    #: it appears here AND the selected model implements it.
    covariates: tuple[str, ...] = ()

    #: Known PK features this parameter set / structure does NOT represent.
    not_represented: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_citation.strip():
            raise ValueError(
                f"parameter set {self.id!r} has no source citation; a set "
                "without a citation cannot be added.")
        # Validate every parameter's dimension at construction, so a bad unit
        # cannot lie dormant until a simulation runs.
        for name, pv in self.parameters.items():
            pv.quantity(f"{self.id}.{name}")

    @property
    def usable_in_guided_mode(self) -> bool:
        return self.validation_status in GUIDED_MODE_STATUSES


# ---------------------------------------------------------------------------
# The library
# ---------------------------------------------------------------------------
#
# Deliberately empty of clinical parameter sets. See the module docstring.
#
# To add one, you must be able to complete every field above from the source in
# front of you — in particular `population` (the exact patients the parameters
# describe) and `source_citation` (precise enough to retrieve). If any field
# would have to be guessed, the set is not ready to be added.

PARAMETER_LIBRARY: tuple[ParameterSet, ...] = ()


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def find_parameter_sets(
    *,
    therapeutic: str | None = None,
    route: AdministrationRoute | None = None,
    formulation: str | None = None,
    guided_only: bool = False,
) -> list[ParameterSet]:
    """Parameter sets matching the given criteria.

    Matching on therapeutic AND route is deliberate: a set estimated for one
    route must never be offered for another, because the absorption and
    bioavailability terms do not transfer.
    """
    results = []
    for ps in PARAMETER_LIBRARY:
        if therapeutic and ps.therapeutic.lower() != therapeutic.lower():
            continue
        if route and ps.route is not route:
            continue
        if formulation and ps.formulation.lower() != formulation.lower():
            continue
        if guided_only and not ps.usable_in_guided_mode:
            continue
        results.append(ps)
    return results


def get_parameter_set(set_id: str, version: str | None = None
                      ) -> ParameterSet | None:
    """Retrieve by id, optionally pinned to a version.

    Pinning by version is what keeps a historical run reproducible after the
    library is revised.
    """
    for ps in PARAMETER_LIBRARY:
        if ps.id == set_id and (version is None or ps.version == version):
            return ps
    return None


def guided_mode_sets(therapeutic: str, route: AdministrationRoute
                     ) -> list[ParameterSet]:
    return find_parameter_sets(therapeutic=therapeutic, route=route,
                               guided_only=True)
