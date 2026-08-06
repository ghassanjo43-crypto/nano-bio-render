"""Vocabularies for the Scientific Readiness Framework.

Why these are separate enumerations
-----------------------------------
Three different questions get asked about a study, and collapsing them loses
information:

* **How do we know this value?** — ``ScientificStatus``, per field.
* **Can this area of work proceed?** — ``ReadinessStatus``, per readiness area.
* **How strong is the underlying evidence?** — ``EvidenceLevel``, per area.

A study can be 90% populated and still ``BLOCKED``; it can be ``READY`` for
structural visualisation and ``INSUFFICIENT`` for pharmacokinetics. One combined
score would hide both facts, which is why the framework never produces one.

Nothing here performs a calculation. These are the words the rest of the
framework is written in.
"""

from __future__ import annotations

import enum

__all__ = [
    "ScientificStatus",
    "EVIDENCE_BEARING_STATUSES",
    "STATUS_LABEL",
    "STATUS_DESCRIPTION",
    "ReadinessArea",
    "AREA_LABEL",
    "AREA_DESCRIPTION",
    "ReadinessStatus",
    "READINESS_LABEL",
    "EvidenceLevel",
    "EVIDENCE_LABEL",
    "EVIDENCE_ORDER",
    "ValidationKind",
    "VALIDATION_KIND_LABEL",
    "VALIDATION_KIND_LEVEL",
    "EXPERIMENTAL_VALIDATION_LEVELS",
    "EVIDENCE_LEVEL_REQUIREMENT",
    "VALIDATION_REGISTRY_AVAILABLE",
    "VALIDATION_REGISTRY_NOTICE",
    "MAX_ATTAINABLE_EVIDENCE_LEVEL",
    "evidence_level_is_attainable",
    "cap_to_attainable_evidence_level",
    "Requirement",
    "RULES_ENGINE_VERSION",
    "NOT_ACCREDITATION_NOTICE",
]

#: Version of the rules engine's *behaviour*. Bump whenever a rule is added,
#: removed or changed in a way that could alter an outcome, so a stored snapshot
#: remains interpretable against the rules that produced it.
#:
#: 1.1.0 — evidence levels E3–E6 were separated from record provenance. Before
#: it, a field marked ``measured`` reached E3 on its own and a *populated*
#: in-vitro or in-vivo evidence field promoted an area to E4 or E5. Neither is a
#: validation, so neither may assert one; see ``EVIDENCE_LEVEL_REQUIREMENT``.
RULES_ENGINE_VERSION = "readiness-rules-1.1.0"

NOT_ACCREDITATION_NOTICE = (
    "Scientific readiness describes whether the information recorded for this "
    "study is sufficient and self-consistent for a given kind of analysis. It "
    "is not regulatory approval, clinical validation, scientific accreditation, "
    "or evidence that any result is correct. A study can be fully ready and "
    "still be scientifically wrong."
)


class ScientificStatus(str, enum.Enum):
    """How a single recorded value came to be known."""

    #: Directly measured on this material, by a stated method.
    MEASURED = "measured"
    #: Derived from measurements on this material (e.g. fitted from a curve).
    EXPERIMENTALLY_DERIVED = "experimentally_derived"
    #: Taken from published work on a comparable material.
    LITERATURE_DERIVED = "literature_derived"
    #: Computed from other recorded values by a stated formula.
    CALCULATED = "calculated"
    #: Output of a model rather than a measurement.
    COMPUTATIONALLY_PREDICTED = "computationally_predicted"
    #: Entered by the user without a stated method or source.
    USER_SUPPLIED = "user_supplied"
    #: A default the software applied because nothing was recorded.
    ASSUMED_DEFAULT = "assumed_default"
    #: Chosen so something could be drawn or shown. Not a claim about reality.
    ILLUSTRATIVE = "illustrative"
    #: Nothing is recorded.
    MISSING = "missing"
    #: The field does not apply to this study.
    NOT_APPLICABLE = "not_applicable"


#: Statuses that constitute evidence about *this* material.
#:
#: Deliberately excludes USER_SUPPLIED: a number typed with no method and no
#: source may well be correct, but it carries no evidence that it is. It also
#: excludes ASSUMED_DEFAULT and ILLUSTRATIVE, which are software choices.
EVIDENCE_BEARING_STATUSES = frozenset({
    ScientificStatus.MEASURED,
    ScientificStatus.EXPERIMENTALLY_DERIVED,
})

#: Statuses that can support an analysis without being evidence themselves.
SUPPORTING_STATUSES = frozenset({
    ScientificStatus.LITERATURE_DERIVED,
    ScientificStatus.CALCULATED,
    ScientificStatus.COMPUTATIONALLY_PREDICTED,
    ScientificStatus.USER_SUPPLIED,
})

#: Statuses that must never raise readiness or evidence level.
NON_CONTRIBUTING_STATUSES = frozenset({
    ScientificStatus.ASSUMED_DEFAULT,
    ScientificStatus.ILLUSTRATIVE,
    ScientificStatus.MISSING,
})

STATUS_LABEL: dict[ScientificStatus, str] = {
    ScientificStatus.MEASURED: "Measured",
    ScientificStatus.EXPERIMENTALLY_DERIVED: "Experimentally derived",
    ScientificStatus.LITERATURE_DERIVED: "Literature-derived",
    ScientificStatus.CALCULATED: "Calculated",
    ScientificStatus.COMPUTATIONALLY_PREDICTED: "Computationally predicted",
    ScientificStatus.USER_SUPPLIED: "User-supplied (no method recorded)",
    ScientificStatus.ASSUMED_DEFAULT: "Assumed default",
    ScientificStatus.ILLUSTRATIVE: "Illustrative only",
    ScientificStatus.MISSING: "Missing",
    ScientificStatus.NOT_APPLICABLE: "Not applicable",
}

STATUS_DESCRIPTION: dict[ScientificStatus, str] = {
    ScientificStatus.MEASURED:
        "Measured directly on this material by a stated method.",
    ScientificStatus.EXPERIMENTALLY_DERIVED:
        "Derived from measurements on this material.",
    ScientificStatus.LITERATURE_DERIVED:
        "Taken from published work on a comparable material. It describes that "
        "material, not necessarily this one.",
    ScientificStatus.CALCULATED:
        "Computed from other recorded values by a stated formula. It is only as "
        "sound as its inputs.",
    ScientificStatus.COMPUTATIONALLY_PREDICTED:
        "Produced by a model. A prediction, not an observation.",
    ScientificStatus.USER_SUPPLIED:
        "Entered without a stated method or source, so it carries no evidence "
        "of how it was obtained.",
    ScientificStatus.ASSUMED_DEFAULT:
        "A value the software applied because nothing was recorded. It is not "
        "evidence and never raises readiness.",
    ScientificStatus.ILLUSTRATIVE:
        "Chosen so something could be shown. It makes no claim about this "
        "material and never raises readiness.",
    ScientificStatus.MISSING:
        "Nothing is recorded. Absence of a record is not a result.",
    ScientificStatus.NOT_APPLICABLE:
        "The field does not apply to this study.",
}


class ReadinessArea(str, enum.Enum):
    """The six areas, assessed independently."""

    STRUCTURAL_VISUALIZATION = "structural_visualization"
    FORMULATION_ASSESSMENT = "formulation_assessment"
    BIOLOGICAL_TARGETING = "biological_targeting"
    PHARMACOKINETIC_MODELLING = "pharmacokinetic_modelling"
    SAFETY_ASSESSMENT = "safety_assessment"
    CINEMATIC_ANIMATION = "cinematic_animation"


AREA_LABEL: dict[ReadinessArea, str] = {
    ReadinessArea.STRUCTURAL_VISUALIZATION: "Structural visualization",
    ReadinessArea.FORMULATION_ASSESSMENT: "Formulation assessment",
    ReadinessArea.BIOLOGICAL_TARGETING: "Biological targeting assessment",
    ReadinessArea.PHARMACOKINETIC_MODELLING: "Pharmacokinetic modelling",
    ReadinessArea.SAFETY_ASSESSMENT: "Safety assessment",
    ReadinessArea.CINEMATIC_ANIMATION: "Future cinematic animation",
}

AREA_DESCRIPTION: dict[ReadinessArea, str] = {
    ReadinessArea.STRUCTURAL_VISUALIZATION:
        "Whether enough is recorded to draw the particle without inventing its "
        "structure. A drawing is a claim; this area governs which claims the "
        "picture is entitled to make.",
    ReadinessArea.FORMULATION_ASSESSMENT:
        "Whether the physical and chemical characterisation is complete and "
        "internally consistent enough to assess the formulation itself.",
    ReadinessArea.BIOLOGICAL_TARGETING:
        "Whether there is recorded evidence about the target, the ligand and "
        "their interaction. Absent evidence is missing evidence, never a "
        "negative result.",
    ReadinessArea.PHARMACOKINETIC_MODELLING:
        "Whether the dosing, route and disposition parameters exist for the "
        "selected model, in compatible units.",
    ReadinessArea.SAFETY_ASSESSMENT:
        "Whether toxicity, degradation and clearance evidence exists. This "
        "platform performs no safety determination; the area reports what "
        "evidence is recorded.",
    ReadinessArea.CINEMATIC_ANIMATION:
        "Whether the structural and behavioural information needed for a "
        "scientifically defensible animation exists. Not implemented; this "
        "area reports its own prerequisites only.",
}


class ReadinessStatus(str, enum.Enum):
    #: Every blocking requirement is met.
    READY = "ready"
    #: Usable, with stated caveats and non-blocking gaps.
    CONDITIONALLY_READY = "conditionally_ready"
    #: Too little recorded to proceed, but nothing contradictory.
    INSUFFICIENT = "insufficient"
    #: A mandatory requirement is absent or a hard conflict exists.
    BLOCKED = "blocked"
    #: The study lies outside what the connected models can represent.
    OUTSIDE_MODEL_DOMAIN = "outside_model_domain"


READINESS_LABEL: dict[ReadinessStatus, str] = {
    ReadinessStatus.READY: "Ready",
    ReadinessStatus.CONDITIONALLY_READY: "Conditionally ready",
    ReadinessStatus.INSUFFICIENT: "Insufficient data",
    ReadinessStatus.BLOCKED: "Blocked",
    ReadinessStatus.OUTSIDE_MODEL_DOMAIN: "Outside model domain",
}


class EvidenceLevel(str, enum.Enum):
    """Strength of the evidence actually recorded.

    Assigned from records, never promoted by hand. Completing a form raises the
    readiness percentage; it does not raise the evidence level.

    The scale has two halves, and confusing them was the defect this vocabulary
    was rewritten to prevent:

    * **E0–E2 describe the basis of a value that has not been validated.** How
      the number came to exist — a placeholder, a citation, a model output, an
      instrument reading. A measurement is the strongest *basis*, but a basis is
      not a validation, so a measurement alone stops at E2.
    * **E3–E6 describe validation.** They assert that something was checked
      against an independent reference, an in-vitro experiment, an in-vivo
      experiment, or clinical evidence. Only a formally recorded validation can
      establish one, and no amount of provenance on the value itself substitutes.
    """

    E0 = "E0"   # illustrative only
    E1 = "E1"   # literature-derived estimate
    E2 = "E2"   # unvalidated basis: computational prediction or measurement
    E3 = "E3"   # retrospectively validated
    E4 = "E4"   # prospectively validated in vitro
    E5 = "E5"   # validated in vivo
    E6 = "E6"   # supported by clinical evidence


EVIDENCE_LABEL: dict[EvidenceLevel, str] = {
    EvidenceLevel.E0: "E0 — illustrative only",
    EvidenceLevel.E1: "E1 — literature-derived estimate",
    EvidenceLevel.E2:
        "E2 — computational prediction or unvalidated measurement",
    EvidenceLevel.E3: "E3 — retrospectively validated",
    EvidenceLevel.E4: "E4 — prospectively validated in vitro",
    EvidenceLevel.E5: "E5 — validated in vivo",
    EvidenceLevel.E6: "E6 — supported by clinical evidence",
}

#: Ordering, so "the weakest level across required fields" is well defined.
EVIDENCE_ORDER: list[EvidenceLevel] = [
    EvidenceLevel.E0, EvidenceLevel.E1, EvidenceLevel.E2, EvidenceLevel.E3,
    EvidenceLevel.E4, EvidenceLevel.E5, EvidenceLevel.E6,
]


class ValidationKind(str, enum.Enum):
    """A kind of validation that, when *formally recorded*, supports a level.

    These name the records the Experimental Validation Registry will hold. They
    exist here so the requirement for each level is stated and testable, not so
    a level can be claimed: nothing in Phase 1 produces one.
    """

    #: A prediction compared, after the fact, against an independent reference
    #: dataset or a recorded outcome that was not used to produce it.
    RETROSPECTIVE_INDEPENDENT = "retrospective_independent"
    #: A prediction registered first, then tested in a cell-based experiment.
    PROSPECTIVE_IN_VITRO = "prospective_in_vitro"
    #: A prediction tested in an animal study.
    IN_VIVO = "in_vivo"
    #: A prediction supported by evidence from human clinical study.
    CLINICAL = "clinical"


VALIDATION_KIND_LABEL: dict[ValidationKind, str] = {
    ValidationKind.RETROSPECTIVE_INDEPENDENT:
        "Retrospective validation against an independent reference or outcome",
    ValidationKind.PROSPECTIVE_IN_VITRO:
        "Prospective in-vitro validation",
    ValidationKind.IN_VIVO: "In-vivo validation",
    ValidationKind.CLINICAL: "Clinical evidence, formally supported",
}

#: The one level each kind of recorded validation would support. A registry
#: record of one kind never establishes a level above its own.
VALIDATION_KIND_LEVEL: dict[ValidationKind, EvidenceLevel] = {
    ValidationKind.RETROSPECTIVE_INDEPENDENT: EvidenceLevel.E3,
    ValidationKind.PROSPECTIVE_IN_VITRO: EvidenceLevel.E4,
    ValidationKind.IN_VIVO: EvidenceLevel.E5,
    ValidationKind.CLINICAL: EvidenceLevel.E6,
}

#: Levels that assert experimental validation. Reachable *only* from a recorded
#: validation of the matching kind — never from a value's own provenance, and
#: never from a populated evidence field.
EXPERIMENTAL_VALIDATION_LEVELS: frozenset[EvidenceLevel] = frozenset(
    VALIDATION_KIND_LEVEL.values())

#: What each level requires, in plain language. Returned by the API so the
#: requirement is visible to a reader rather than buried in the engine.
EVIDENCE_LEVEL_REQUIREMENT: dict[EvidenceLevel, str] = {
    EvidenceLevel.E0:
        "Nothing recorded, or only values that make no claim about this "
        "material: assumed defaults, illustrative placeholders, and numbers "
        "entered with no method or source.",
    EvidenceLevel.E1:
        "Every required field is at least literature-derived, with a citation. "
        "It describes a comparable material, not necessarily this one.",
    EvidenceLevel.E2:
        "Every required field has a stated basis on this material — a "
        "measurement, a derivation from measurements, a calculation, or a "
        "model output. Nothing has been validated against an independent "
        "result; this is the highest level that asserts no validation.",
    EvidenceLevel.E3:
        "An explicitly recorded retrospective validation against an "
        "independent reference dataset or a recorded outcome that was not used "
        "to produce the prediction.",
    EvidenceLevel.E4:
        "An explicitly documented prospective in-vitro validation: the "
        "prediction registered before the experiment, and the experiment "
        "recorded against it.",
    EvidenceLevel.E5:
        "An explicitly documented in-vivo validation, with the species, route, "
        "protocol and outcome recorded.",
    EvidenceLevel.E6:
        "Formally supported clinical evidence. There is no recording path for "
        "it, and the engine never emits this level.",
}

#: The Experimental Validation Registry exists as of Phase 2, Milestone 1.
#:
#: This flag is the single switch, and it was flipped together with the
#: implementation it depends on: ``rules._recorded_validations`` now reads
#: approved experiment versions supplied by ``validation_service``. Setting it
#: True without that lookup would make the engine emit E3 for studies with no
#: validation at all.
VALIDATION_REGISTRY_AVAILABLE = True

#: What the registry can actually grant, which is narrower than what exists.
#:
#: Milestone 1 records in-vitro experiments only. E4 requires a prediction
#: registered *before* the experiment, E5 requires in-vivo work and E6 clinical
#: evidence — none of which this milestone records, so none is grantable and
#: none is selectable in the interface.
REGISTRY_GRANTABLE_LEVELS: frozenset[EvidenceLevel] = frozenset({
    EvidenceLevel.E3,
})

VALIDATION_REGISTRY_NOTICE = (
    "E3 is granted only by the Experimental Validation Registry, and only for "
    "a specific scientific purpose on a specific candidate version: an "
    "approved in-vitro experiment that passed every eligibility gate and was "
    "approved by somebody who did not perform it. It does not mean the "
    "candidate or the study is validated. E4 to E6 assert prospective "
    "in-vitro, in-vivo and clinical validation respectively; this milestone "
    "records none of them, so they remain unreachable and are never asserted."
)


def max_attainable_evidence_level() -> EvidenceLevel:
    """The highest level any study can currently reach.

    Derived from what the registry can grant rather than hard-coded, so the
    ceiling can only move when the capability behind it does. With the registry
    available and E3 its only grantable level, the ceiling is E3.
    """
    if not VALIDATION_REGISTRY_AVAILABLE:
        below = [level for level in EVIDENCE_ORDER
                 if level not in EXPERIMENTAL_VALIDATION_LEVELS]
        return below[-1]
    grantable = [level for level in EVIDENCE_ORDER
                 if level in REGISTRY_GRANTABLE_LEVELS]
    unvalidated = [level for level in EVIDENCE_ORDER
                   if level not in EXPERIMENTAL_VALIDATION_LEVELS]
    return grantable[-1] if grantable else unvalidated[-1]


#: Convenience constant for callers that only need the value.
MAX_ATTAINABLE_EVIDENCE_LEVEL: EvidenceLevel = max_attainable_evidence_level()


def evidence_level_is_attainable(level: EvidenceLevel) -> bool:
    """Whether a level can be reached at all with the platform as it stands."""
    return (EVIDENCE_ORDER.index(level)
            <= EVIDENCE_ORDER.index(max_attainable_evidence_level()))


def cap_to_attainable_evidence_level(level: EvidenceLevel) -> EvidenceLevel:
    """Hold a level to the ceiling. The last line of defence.

    Every path that assigns a level runs through this, so a future rule that
    computes E4 from something that is not a validation record still cannot
    publish it.
    """
    return level if evidence_level_is_attainable(level) else (
        max_attainable_evidence_level())


class Requirement(str, enum.Enum):
    """How strongly an area depends on a field."""

    #: Absent -> the area is BLOCKED, whatever the percentage.
    BLOCKING = "blocking"
    #: Required only when a stated condition holds.
    CONDITIONAL = "conditional"
    #: Improves the assessment; absence produces a warning at most.
    OPTIONAL = "optional"
