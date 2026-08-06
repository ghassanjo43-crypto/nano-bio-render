"""The readiness rules engine.

Deterministic and versioned: the same records and the same
``RULES_ENGINE_VERSION`` always produce the same assessment, which is what makes
a stored snapshot re-checkable.

Two invariants the whole design rests on
----------------------------------------
1. **A percentage never overrides a blocking requirement.** An area with every
   optional field populated and one blocking field missing is ``BLOCKED`` at
   95%. The percentage measures completeness; the status measures whether the
   work may proceed. They answer different questions and are reported separately.

2. **Evidence level comes from records, never from form completeness.** Filling
   in more fields raises the percentage. Only recorded experimental evidence
   raises the evidence level.

3. **A validation level is only ever established by a validation record.**
   E3–E6 assert that a prediction was checked against an independent result or
   an experiment. A value's own provenance cannot establish that, however
   strong: a cryo-TEM diameter is an observation, not a validation of anything.
   Neither can a *populated* in-vitro or in-vivo evidence field — that records
   the claim that an experiment exists, not that anything was checked against
   it. Phase 1 has no Experimental Validation Registry, so no such record can be
   stored, and the engine therefore never emits E3 or above.

Every block and every warning carries a plain-language explanation. A rule the
user cannot understand is a rule they cannot act on.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone

from .data_dictionary import (
    DICTIONARY_VERSION,
    fields_for_area,
    field_definition,
)
from .records import ScientificRecord
from .statuses import (
    AREA_DESCRIPTION,
    AREA_LABEL,
    EVIDENCE_ORDER,
    EXPERIMENTAL_VALIDATION_LEVELS,
    NOT_ACCREDITATION_NOTICE,
    RULES_ENGINE_VERSION,
    VALIDATION_REGISTRY_AVAILABLE,
    VALIDATION_REGISTRY_NOTICE,
    EvidenceLevel,
    ReadinessArea,
    ReadinessStatus,
    Requirement,
    ScientificStatus,
    cap_to_attainable_evidence_level,
    max_attainable_evidence_level,
)

__all__ = [
    "Finding",
    "AreaAssessment",
    "ReadinessReport",
    "evaluate_study",
    "evaluate_area",
]


@dataclass(frozen=True)
class Finding:
    """A single blocking issue, warning or assumption."""

    code: str
    message: str
    #: Fields the finding concerns, so the interface can link to them.
    field_ids: tuple[str, ...] = ()
    #: What the user can do about it.
    recommended_action: str | None = None


@dataclass
class AreaAssessment:
    area: ReadinessArea
    label: str
    description: str
    status: ReadinessStatus
    readiness_percent: int
    evidence_level: EvidenceLevel
    #: Why the level is what it is, and why it is not higher. Reported so the
    #: bare code "E2" is never the only thing a reader sees.
    evidence_level_rationale: str = ""
    #: The highest level this area could reach today, whatever it records.
    max_attainable_evidence_level: EvidenceLevel = EvidenceLevel.E0
    blocking_issues: list[Finding] = dc_field(default_factory=list)
    warnings: list[Finding] = dc_field(default_factory=list)
    missing_inputs: list[str] = dc_field(default_factory=list)
    incompatible_inputs: list[Finding] = dc_field(default_factory=list)
    assumptions: list[Finding] = dc_field(default_factory=list)
    recommended_actions: list[str] = dc_field(default_factory=list)

    def to_dict(self) -> dict:
        def findings(items: list[Finding]) -> list[dict]:
            return [{"code": f.code, "message": f.message,
                     "field_ids": list(f.field_ids),
                     "recommended_action": f.recommended_action}
                    for f in items]
        return {
            "area": self.area.value,
            "label": self.label,
            "description": self.description,
            "status": self.status.value,
            "readiness_percent": self.readiness_percent,
            "evidence_level": self.evidence_level.value,
            "evidence_level_rationale": self.evidence_level_rationale,
            "max_attainable_evidence_level":
                self.max_attainable_evidence_level.value,
            "blocking_issues": findings(self.blocking_issues),
            "warnings": findings(self.warnings),
            "missing_inputs": list(self.missing_inputs),
            "incompatible_inputs": findings(self.incompatible_inputs),
            "assumptions": findings(self.assumptions),
            "recommended_actions": list(self.recommended_actions),
        }


@dataclass
class ReadinessReport:
    areas: list[AreaAssessment]
    rules_engine_version: str
    dictionary_version: str
    evaluated_at: datetime
    notice: str = NOT_ACCREDITATION_NOTICE

    def to_dict(self) -> dict:
        return {
            "areas": [a.to_dict() for a in self.areas],
            "rules_engine_version": self.rules_engine_version,
            "dictionary_version": self.dictionary_version,
            "evaluated_at": self.evaluated_at.isoformat(),
            "notice": self.notice,
            # Stated on every assessment, not only where a level is capped: a
            # reader must be able to tell what the top of the scale means here
            # without inferring it from the levels that happen to appear.
            "validation_registry_available": VALIDATION_REGISTRY_AVAILABLE,
            "max_attainable_evidence_level":
                max_attainable_evidence_level().value,
            "evidence_ceiling_notice": VALIDATION_REGISTRY_NOTICE,
        }

    def area(self, area: ReadinessArea) -> AreaAssessment:
        return next(a for a in self.areas if a.area is area)


# ---------------------------------------------------------------------------
# Cross-cutting scientific rules
# ---------------------------------------------------------------------------

#: Architectures the connected structural models genuinely support.
SUPPORTED_ARCHITECTURES = {
    "solid", "core_shell", "liposome", "polymeric", "metallic", "silica",
    "hybrid",
}

#: Which architectures a bilayer/aqueous-core assumption may be applied to.
BILAYER_ARCHITECTURES = {"liposome"}

#: Ligand-density units from which a population can actually be derived.
UNAMBIGUOUS_DENSITY_UNITS = {
    "per_nm2", "per_particle", "surface_coverage_fraction",
}


def _by_id(records: list[ScientificRecord]) -> dict[str, ScientificRecord]:
    return {r.field_id: r for r in records}


def _present(rec: ScientificRecord | None) -> bool:
    return rec is not None and rec.contributes_to_readiness


def _check_architecture_model_match(
    recs: dict[str, ScientificRecord],
) -> list[Finding]:
    """Prevent architecture-specific models reaching unsupported classes."""
    findings: list[Finding] = []
    arch = recs.get("architecture")
    npclass = recs.get("nanoparticle_class")
    payload_loc = recs.get("payload_location")

    if _present(arch) and str(arch.value) not in SUPPORTED_ARCHITECTURES:
        findings.append(Finding(
            "unsupported_architecture",
            f"No connected structural model represents the architecture "
            f"{arch.value!r}. The study lies outside the domain of the models "
            "this platform can apply.",
            ("architecture",),
            "Record an architecture the platform supports, or treat the "
            "structural output as illustrative only."))

    # A bilayer/aqueous-core payload placement only makes sense for a vesicle.
    if (_present(payload_loc) and _present(arch)
            and str(payload_loc.value) in {"aqueous_core", "bilayer"}
            and str(arch.value) not in BILAYER_ARCHITECTURES):
        findings.append(Finding(
            "bilayer_assumption_misapplied",
            f"Payload location {payload_loc.value!r} describes a lipid "
            f"vesicle, but the recorded architecture is {arch.value!r}. "
            "Liposome assumptions are not applied to metallic, silica or "
            "polymeric particles.",
            ("payload_location", "architecture"),
            "Correct either the architecture or the payload location."))

    # Class and architecture must not contradict each other.
    if _present(arch) and _present(npclass):
        contradictions = {
            ("metallic", "lipid"), ("liposome", "metallic"),
            ("liposome", "polymeric"), ("silica", "lipid"),
        }
        if (str(arch.value), str(npclass.value)) in contradictions:
            findings.append(Finding(
                "class_architecture_conflict",
                f"Architecture {arch.value!r} and class {npclass.value!r} "
                "describe different materials.",
                ("architecture", "nanoparticle_class"),
                "Correct whichever is wrong."))
    return findings


def _check_measurement_compatibility(
    recs: dict[str, ScientificRecord],
) -> list[Finding]:
    """Detect measurements that are being treated as interchangeable."""
    findings: list[Finding] = []

    physical = recs.get("physical_diameter")
    hydro = recs.get("hydrodynamic_diameter")

    # DLS vs TEM: different quantities, different method families.
    if _present(physical) and physical.method_family == "scattering":
        findings.append(Finding(
            "physical_diameter_from_scattering",
            "The primary physical diameter is recorded with a light-scattering "
            "method. Scattering yields a hydrodynamic diameter, which includes "
            "the solvation layer and is not the physical core diameter.",
            ("physical_diameter",),
            "Record the scattering result as the hydrodynamic diameter, and "
            "reserve the physical diameter for microscopy."))

    if _present(hydro) and hydro.method_family == "microscopy":
        findings.append(Finding(
            "hydrodynamic_diameter_from_microscopy",
            "The hydrodynamic diameter is recorded with a microscopy method. "
            "Microscopy measures the physical particle, not its hydrodynamic "
            "size in dispersion.",
            ("hydrodynamic_diameter",),
            "Move this value to the physical diameter field."))

    # A hydrodynamic diameter smaller than the physical one is not possible.
    if _present(physical) and _present(hydro):
        try:
            p, h = float(physical.value), float(hydro.value)
            if physical.unit == hydro.unit and h < p:
                findings.append(Finding(
                    "hydrodynamic_smaller_than_physical",
                    f"The hydrodynamic diameter ({h} {hydro.unit}) is smaller "
                    f"than the physical diameter ({p} {physical.unit}). The "
                    "hydrodynamic size includes the solvation layer and cannot "
                    "be smaller.",
                    ("hydrodynamic_diameter", "physical_diameter"),
                    "Check which measurement, or which unit, is wrong."))
        except (TypeError, ValueError):
            pass

        conflicts = physical.conditions.conflicts_with(hydro.conditions)
        if conflicts:
            findings.append(Finding(
                "diameter_conditions_differ",
                "The physical and hydrodynamic diameters were measured under "
                f"different conditions ({'; '.join(conflicts)}). They describe "
                "the material in different states and are not directly "
                "comparable.",
                ("physical_diameter", "hydrodynamic_diameter"),
                "Record both under matched conditions, or state which "
                "condition each result applies to."))

    # A hydrodynamic diameter or PDI without a weighting basis.
    basis = recs.get("size_distribution_basis")
    for dependent in ("hydrodynamic_diameter", "pdi"):
        rec = recs.get(dependent)
        if _present(rec) and not _present(basis):
            findings.append(Finding(
                "distribution_basis_missing",
                f"{field_definition(dependent).label} is recorded without a "
                "size-distribution basis. Intensity-, volume- and "
                "number-weighted distributions of the same sample differ, "
                "often substantially.",
                (dependent, "size_distribution_basis"),
                "Record whether the distribution is intensity-, volume- or "
                "number-weighted."))

    # Geometry that cannot exist.
    coating = recs.get("coating_thickness")
    if _present(coating) and _present(physical):
        try:
            t, d = float(coating.value), float(physical.value)
            if coating.unit == physical.unit and 2 * t >= d:
                findings.append(Finding(
                    "coating_exceeds_diameter",
                    f"A coating {t} {coating.unit} thick on both sides "
                    f"consumes {2 * t} {coating.unit} of a {d} "
                    f"{physical.unit} particle, leaving no core. The geometry "
                    "as recorded is not physically possible.",
                    ("coating_thickness", "physical_diameter"),
                    "Check the coating thickness and the diameter."))
        except (TypeError, ValueError):
            pass

    return findings


def _check_ligand_density(recs: dict[str, ScientificRecord]) -> list[Finding]:
    """Block a ligand population when the density is ambiguous."""
    findings: list[Finding] = []
    value = recs.get("ligand_density_value")
    unit = recs.get("ligand_density_unit")

    if not _present(value):
        return findings

    if not _present(unit):
        findings.append(Finding(
            "ligand_density_unit_missing",
            "A ligand density is recorded without its unit and denominator. A "
            "bare number cannot be converted into a ligand population: it "
            "could mean molecules per square nanometre, molecules per "
            "particle, molar percent of lipid, mass percent of carrier, or "
            "fractional surface coverage, and these give different counts.",
            ("ligand_density_value", "ligand_density_unit"),
            "Record what the density is expressed against."))
        return findings

    unit_value = str(unit.value)
    if unit_value == "ambiguous_percent":
        findings.append(Finding(
            "ligand_density_ambiguous",
            "The ligand density is recorded as a bare percentage with no "
            "stated denominator. No ligand population is calculated: surface "
            "coverage, molar percent and mass percent give different answers.",
            ("ligand_density_unit",),
            "Record the denominator, or re-express the density as molecules "
            "per square nanometre."))
    elif unit_value in {"mol_percent_of_lipid", "mass_percent_of_carrier"}:
        needed = ("ligand_molecular_weight"
                  if unit_value == "mass_percent_of_carrier" else None)
        if needed and not _present(recs.get(needed)):
            findings.append(Finding(
                "ligand_conversion_inputs_missing",
                f"Converting a {unit_value.replace('_', ' ')} density into a "
                "ligand count needs the ligand molecular weight, which is not "
                "recorded.",
                ("ligand_density_unit", needed),
                f"Record the {field_definition(needed).label.lower()}."))
    elif unit_value == "surface_coverage_fraction":
        if not _present(recs.get("molecular_footprint")):
            findings.append(Finding(
                "footprint_missing",
                "A fractional surface coverage cannot be converted into a "
                "ligand count without the molecular footprint of the ligand.",
                ("molecular_footprint",),
                "Record the molecular footprint in nm²."))
        if not _present(recs.get("surface_area")) and not _present(
                recs.get("physical_diameter")):
            findings.append(Finding(
                "surface_area_missing",
                "A surface-area basis is needed to convert a coverage "
                "fraction into a count; neither a surface area nor a diameter "
                "is recorded.",
                ("surface_area", "physical_diameter"),
                "Record the particle diameter or its accessible surface area."))
    return findings


def _check_molecular_population(
    recs: dict[str, ScientificRecord],
) -> list[Finding]:
    """Block a payload population when the required constants are absent."""
    findings: list[Finding] = []
    has_payload = _present(recs.get("payload_identity"))
    if not has_payload:
        return findings

    mw = recs.get("payload_molecular_weight")
    loading = recs.get("loading_capacity")
    ratio = recs.get("drug_to_carrier_ratio")

    if not _present(mw):
        findings.append(Finding(
            "payload_molecular_weight_missing",
            "No payload molecular weight is recorded, so no payload molecule "
            "count can be derived. Encapsulation efficiency does not supply "
            "one: it is the fraction of offered drug that was encapsulated, "
            "which says nothing about how much was offered or what it weighs.",
            ("payload_molecular_weight",),
            "Record the payload molar mass."))

    if not _present(loading) and not _present(ratio):
        findings.append(Finding(
            "payload_quantity_missing",
            "Neither a loading capacity nor a drug-to-carrier ratio is "
            "recorded, so the amount of payload per particle is unknown.",
            ("loading_capacity", "drug_to_carrier_ratio"),
            "Record a loading capacity or a drug-to-carrier ratio."))
    return findings


def _check_biological_evidence(
    recs: dict[str, ScientificRecord],
) -> list[Finding]:
    """Targeting claims need recorded receptor evidence."""
    findings: list[Finding] = []
    expression = recs.get("receptor_expression_value")
    unit = recs.get("receptor_expression_unit")
    method = recs.get("expression_method")

    if not _present(expression):
        findings.append(Finding(
            "receptor_expression_missing",
            "No receptor-expression measurement is recorded. A targeting "
            "claim without expression evidence is a hypothesis, so biological "
            "targeting readiness is not reported.",
            ("receptor_expression_value",),
            "Record the measured receptor expression, its unit and the method."))
    else:
        if not _present(unit):
            findings.append(Finding(
                "expression_unit_missing",
                "A receptor-expression value is recorded without its unit. An "
                "IHC score and a receptors-per-cell count are different "
                "quantities and neither converts to the other.",
                ("receptor_expression_unit",),
                "Record the expression unit."))
        if not _present(method):
            findings.append(Finding(
                "expression_method_missing",
                "No method is recorded for the receptor-expression value, so "
                "it cannot be compared with any other measurement.",
                ("expression_method",),
                "Record the measurement method."))

    affinity = recs.get("binding_affinity")
    if _present(affinity) and not _present(recs.get("binding_assay")):
        findings.append(Finding(
            "binding_assay_missing",
            "A binding affinity is recorded without the assay used. Affinities "
            "from different assay formats are not directly comparable.",
            ("binding_assay",),
            "Record the binding assay."))
    return findings


def _validation_notes(area: ReadinessArea,
                      recs: dict[str, ScientificRecord]) -> list[Finding]:
    """State what the recorded data does *not* establish.

    Both notes address a specific misreading. The first: that a value marked
    ``measured`` has thereby been validated. The second: that filling in an
    in-vitro or in-vivo evidence field has thereby validated something. Neither
    is true, and both were previously acted on by the engine.
    """
    notes: list[Finding] = []
    area_fields = {spec.id for spec in fields_for_area(area)}

    required_ids = {spec.id for spec in fields_for_area(area)
                    if spec.area_requirements[area] is not Requirement.OPTIONAL}
    measured = tuple(sorted(
        field_id for field_id in required_ids
        if (rec := recs.get(field_id)) is not None and rec.is_evidence))
    if measured:
        notes.append(Finding(
            "measurement_is_not_validation",
            "Measured values are recorded for this area, but no validation "
            "record is. A measurement is an observation of this material; it "
            "is not a check of any prediction against an independent result, "
            "so on its own it does not reach E3. "
            + VALIDATION_REGISTRY_NOTICE,
            measured, None))

    populated = tuple(sorted(
        field_id
        for field_id in (*IN_VITRO_EVIDENCE_FIELDS, *IN_VIVO_EVIDENCE_FIELDS)
        if field_id in area_fields and _present(recs.get(field_id))))
    if populated:
        notes.append(Finding(
            "evidence_field_is_not_validation",
            "An in-vitro or in-vivo evidence field is populated. That records "
            "the claim that such an experiment exists; it does not record that "
            "a prediction was registered, tested against it, and found to "
            "hold. Populating it therefore does not raise this area to E4 or "
            "E5, and the platform has not verified that any experiment took "
            "place.",
            populated, None))
    return notes


def _absent_evidence_notes(recs: dict[str, ScientificRecord]) -> list[Finding]:
    """State plainly that absent evidence is not a negative result."""
    notes: list[Finding] = []
    for field_id, phrase in [
        ("cellular_uptake_evidence", "cellular uptake"),
        ("in_vivo_evidence", "in-vivo behaviour"),
        ("cytotoxicity_evidence", "cytotoxicity"),
        ("selectivity_evidence", "selectivity"),
    ]:
        if not _present(recs.get(field_id)):
            notes.append(Finding(
                f"absent_evidence_{field_id}",
                f"No {phrase} evidence is recorded. This means no such "
                "experiment is on file — it is not a finding that the effect "
                "is absent.",
                (field_id,),
                f"Record {phrase} data if an experiment exists."))
    return notes


# ---------------------------------------------------------------------------
# Evidence level
# ---------------------------------------------------------------------------

#: The level a record's own provenance supports, before any validation.
#:
#: Every entry is at or below E2 by construction, and a test enumerates
#: ``ScientificStatus`` against this table so a status added later cannot
#: default into a validation level by omission.
#:
#: MEASURED and CALCULATED landing on the same rung is not an oversight. E0–E2
#: rank how a value came to exist; E3+ rank whether anything was *checked*. A
#: measurement is the strongest basis available, and it is still unvalidated —
#: which is exactly what E2 means. The measured/predicted distinction is not
#: lost: it is carried by the record's own ``status``, which the report renders
#: separately, and named in the rationale below.
_BASIS_LEVEL: dict[ScientificStatus, EvidenceLevel] = {
    ScientificStatus.MEASURED: EvidenceLevel.E2,
    ScientificStatus.EXPERIMENTALLY_DERIVED: EvidenceLevel.E2,
    ScientificStatus.CALCULATED: EvidenceLevel.E2,
    ScientificStatus.COMPUTATIONALLY_PREDICTED: EvidenceLevel.E2,
    ScientificStatus.LITERATURE_DERIVED: EvidenceLevel.E1,
    # None of these is a claim about this material, so none supports a level.
    ScientificStatus.USER_SUPPLIED: EvidenceLevel.E0,
    ScientificStatus.ASSUMED_DEFAULT: EvidenceLevel.E0,
    ScientificStatus.ILLUSTRATIVE: EvidenceLevel.E0,
    ScientificStatus.MISSING: EvidenceLevel.E0,
}

#: Fields that record *that an experiment is claimed to exist*. Named here only
#: so the engine can say plainly that populating one does not establish E4/E5.
#: Nothing reads this list to raise a level.
IN_VITRO_EVIDENCE_FIELDS = (
    "cellular_uptake_evidence", "cytotoxicity_evidence", "binding_affinity",
    "release_profile_evidence", "selectivity_evidence", "trafficking_evidence",
)
IN_VIVO_EVIDENCE_FIELDS = ("in_vivo_evidence", "clearance_evidence")


def _recorded_validations(
    recs: dict[str, ScientificRecord],
    approved_evidence: dict[str, dict] | None = None,
    area: ReadinessArea | None = None,
) -> list[EvidenceLevel]:
    """Validation levels supported by approved registry evidence, for one area.

    This is the *only* place a level in ``EXPERIMENTAL_VALIDATION_LEVELS`` may
    originate. A test asserts no other function in this module so much as names
    one, which is what keeps the promotion path confined to evidence that went
    through review.

    ``approved_evidence`` is supplied by ``validation_service`` and contains
    **approved experiment versions only** — never a draft, a submitted record,
    a rejection or a superseded version. It is passed in rather than queried
    here because this module is pure and reads no database.

    Three properties, each load-bearing:

    * **Per purpose.** Evidence is looked up by the area being assessed. An
      approved cytotoxicity experiment promotes safety assessment and nothing
      else; E3 never propagates to an unrelated purpose.
    * **Held on contradiction.** When approved records for one purpose
      disagree, the service sets ``level`` to None and the area keeps its
      previously justified level. The favourable record is not preferred.
    * **E3 only.** ``cap_to_attainable_evidence_level`` still applies, and
      ``GRANTABLE_LEVELS`` in the registry contains E3 alone, so E4–E6 remain
      unreachable through this path as through every other.
    """
    if not VALIDATION_REGISTRY_AVAILABLE or not approved_evidence:
        return []
    if area is None:
        return []

    entry = approved_evidence.get(area.value)
    if not entry:
        return []

    # A contradiction is a reason to stop, not a reason to choose.
    if entry.get("contradiction") or entry.get("level") is None:
        return []

    try:
        level = EvidenceLevel(entry["level"])
    except (KeyError, ValueError):
        return []

    # Belt and braces: the registry may only grant E3. Anything else arriving
    # here is a bug elsewhere, and is dropped rather than published.
    return [level] if level is EvidenceLevel.E3 else []


def _basis_level(rec: ScientificRecord | None) -> EvidenceLevel:
    """The level one record's provenance supports. Never above E2."""
    if rec is None or not rec.is_present:
        return EvidenceLevel.E0
    return cap_to_attainable_evidence_level(
        _BASIS_LEVEL.get(rec.status, EvidenceLevel.E0))


def _evidence_level(area: ReadinessArea,
                    recs: dict[str, ScientificRecord],
                    approved_evidence: dict[str, dict] | None = None,
                    ) -> tuple[EvidenceLevel, str]:
    """Derive the evidence level from what is recorded, with its reason.

    Two rules, in order:

    1. **The basis level is the WEAKEST link** among the fields the area
       actually requires, because an area is only as well evidenced as its
       worst-supported input. Completing optional fields cannot raise it, and
       the basis level can never exceed E2 — see ``_BASIS_LEVEL``.
    2. **A validation level is added only from a validation record** of the
       matching kind, via ``_recorded_validations``. No provenance on a value,
       and no populated evidence field, contributes here.

    The final level is the higher of the two, capped at what is attainable. In
    Phase 1 rule 2 contributes nothing, so the result is rule 1's, at most E2.
    """
    required = [d for d in fields_for_area(area)
                if d.area_requirements[area] is not Requirement.OPTIONAL]
    if not required:
        return EvidenceLevel.E0, (
            "No field is required for this area, so no evidence level is "
            "asserted.")

    graded: list[tuple[EvidenceLevel, str, ScientificRecord | None]] = []
    for spec in required:
        rec = recs.get(spec.id)
        if rec is not None and rec.status is ScientificStatus.NOT_APPLICABLE:
            continue        # the field does not apply; it cannot weaken the area
        graded.append((_basis_level(rec), spec.label, rec))

    if not graded:
        return EvidenceLevel.E0, (
            "Every required field is marked not applicable, so there is "
            "nothing to assess and no evidence level is asserted.")

    # min() keeps the first of any tie, and fields_for_area is in dictionary
    # order, so the field named in the rationale is stable across runs.
    basis, weakest_label, weakest_rec = min(
        graded, key=lambda item: EVIDENCE_ORDER.index(item[0]))

    validations = _recorded_validations(recs, approved_evidence, area)
    level = basis
    if validations:                            # pragma: no cover - Phase 2
        best = max(validations, key=EVIDENCE_ORDER.index)
        if EVIDENCE_ORDER.index(best) > EVIDENCE_ORDER.index(level):
            level = best

    # Belt and braces. Nothing above should be able to produce an unattainable
    # level; if a future rule does, it is held here rather than published.
    level = cap_to_attainable_evidence_level(level)
    return level, _evidence_rationale(level, basis, weakest_label, weakest_rec)


def _evidence_rationale(level: EvidenceLevel, basis: EvidenceLevel,
                        weakest_label: str,
                        weakest_rec: ScientificRecord | None) -> str:
    """Say what set the level, and why it is not higher.

    A level shown without its reason invites the reading the framework exists to
    prevent — that E2 is a middling score rather than a statement that nothing
    has been validated.
    """
    if weakest_rec is None or not weakest_rec.is_present:
        weakest = (f"The weakest required field, {weakest_label}, is not "
                   f"recorded, which holds this area at "
                   f"{EvidenceLevel.E0.value}.")
    else:
        status = weakest_rec.status.value.replace("_", " ")
        weakest = (f"The weakest required field, {weakest_label}, is "
                   f"{status}, which supports {basis.value}. The area takes "
                   "the weakest of its required fields, not their average.")

    ceiling = max_attainable_evidence_level()
    if level in EXPERIMENTAL_VALIDATION_LEVELS:
        return (
            f"{weakest} An approved experiment in the Experimental Validation "
            f"Registry raises it to {level.value} for this purpose, on this "
            "candidate version. It says nothing about any other purpose.")
    return (
        f"{weakest} No approved validation record applies to this area, so no "
        f"level above {ceiling.value} is asserted. "
        f"{VALIDATION_REGISTRY_NOTICE}")


# ---------------------------------------------------------------------------
# Percentage
# ---------------------------------------------------------------------------

#: Weights by requirement level. Blocking fields dominate the percentage, so a
#: study that fills only optional fields cannot look nearly complete.
_WEIGHT = {
    Requirement.BLOCKING: 3.0,
    Requirement.CONDITIONAL: 2.0,
    Requirement.OPTIONAL: 1.0,
}


def _readiness_percent(area: ReadinessArea,
                       recs: dict[str, ScientificRecord]) -> int:
    """Weighted completeness of the fields this area depends on.

    Counts only records that contribute: assumed, illustrative and missing
    values score zero, so completing a form with defaults does not raise the
    percentage.
    """
    specs = fields_for_area(area)
    if not specs:
        return 0
    total = 0.0
    earned = 0.0
    for spec in specs:
        weight = _WEIGHT[spec.area_requirements[area]]
        rec = recs.get(spec.id)
        if rec is not None and rec.status is ScientificStatus.NOT_APPLICABLE:
            continue        # excluded from both numerator and denominator
        total += weight
        if rec is not None and rec.contributes_to_readiness:
            earned += weight
    if total == 0:
        return 0
    return int(round((earned / total) * 100))


# ---------------------------------------------------------------------------
# Area evaluation
# ---------------------------------------------------------------------------

def evaluate_area(area: ReadinessArea,
                  records: list[ScientificRecord],
                  approved_evidence: dict[str, dict] | None = None,
                  ) -> AreaAssessment:
    recs = _by_id(records)

    blocking: list[Finding] = []
    warnings: list[Finding] = []
    incompatible: list[Finding] = []
    assumptions: list[Finding] = []

    # --- blocking fields ---------------------------------------------------
    missing: list[str] = []
    for spec in fields_for_area(area):
        requirement = spec.area_requirements[area]
        rec = recs.get(spec.id)
        if rec is not None and rec.status is ScientificStatus.NOT_APPLICABLE:
            continue
        if rec is None or not rec.contributes_to_readiness:
            missing.append(spec.id)
            if requirement is Requirement.BLOCKING:
                reason = (f"{spec.label} is required before "
                          f"{AREA_LABEL[area].lower()} can proceed, and is "
                          "not recorded.")
                if rec is not None and rec.is_present:
                    reason = (
                        f"{spec.label} is recorded as "
                        f"{rec.status.value.replace('_', ' ')}, which is not "
                        "evidence about this material and cannot satisfy a "
                        "blocking requirement.")
                blocking.append(Finding(
                    f"blocking_missing_{spec.id}", reason, (spec.id,),
                    spec.researcher_note or f"Record {spec.label.lower()}."))

    # --- assumed and illustrative values -----------------------------------
    for rec in records:
        if rec.status is ScientificStatus.ASSUMED_DEFAULT:
            assumptions.append(Finding(
                f"assumed_{rec.field_id}",
                f"{rec.definition.label} uses a software default rather than a "
                "recorded value. It does not count as evidence and does not "
                "raise readiness.",
                (rec.field_id,),
                f"Record a measured or cited {rec.definition.label.lower()}."))
        elif rec.status is ScientificStatus.ILLUSTRATIVE:
            assumptions.append(Finding(
                f"illustrative_{rec.field_id}",
                f"{rec.definition.label} is illustrative — chosen so something "
                "could be shown. It makes no claim about this material.",
                (rec.field_id,), None))
        elif rec.status is ScientificStatus.USER_SUPPLIED and rec.is_present:
            warnings.append(Finding(
                f"unsourced_{rec.field_id}",
                f"{rec.definition.label} was entered without a method or "
                "source, so its provenance cannot be checked.",
                (rec.field_id,),
                "Record how the value was obtained."))

    # --- cross-cutting scientific rules ------------------------------------
    incompatible.extend(_check_architecture_model_match(recs))
    if area in {ReadinessArea.STRUCTURAL_VISUALIZATION,
                ReadinessArea.FORMULATION_ASSESSMENT,
                ReadinessArea.CINEMATIC_ANIMATION}:
        incompatible.extend(_check_measurement_compatibility(recs))
    if area is ReadinessArea.BIOLOGICAL_TARGETING:
        blocking.extend(_check_ligand_density(recs))
        blocking.extend(_check_biological_evidence(recs))
        warnings.extend(_absent_evidence_notes(recs))
    if area is ReadinessArea.PHARMACOKINETIC_MODELLING:
        blocking.extend(_check_molecular_population(recs))
        route = recs.get("administration_route")
        if _present(route) and str(route.value) in {"iv_bolus", "iv_infusion"}:
            assumptions.append(Finding(
                "iv_no_absorption",
                "The route is intravenous, so there is no absorption phase and "
                "no absorption rate constant applies.",
                ("administration_route",), None))
        dose = recs.get("dose_amount")
        if (_present(dose) and dose.unit == "mg/kg"
                and not _present(recs.get("body_weight"))):
            blocking.append(Finding(
                "body_weight_missing",
                "The dose is expressed per kilogram but no body weight is "
                "recorded. No default weight is applied: assuming one would "
                "invent a characteristic that scales every reported "
                "concentration.",
                ("body_weight", "dose_amount"),
                "Record the body weight."))
    if area is ReadinessArea.SAFETY_ASSESSMENT:
        warnings.extend(_absent_evidence_notes(recs))

    # --- percentage and evidence level -------------------------------------
    percent = _readiness_percent(area, recs)
    evidence, evidence_rationale = _evidence_level(area, recs,
                                                   approved_evidence)
    # Said on the card, not only in the rationale string, so a reader scanning
    # findings still sees what the recorded data does not establish.
    warnings.extend(_validation_notes(area, recs))

    # --- status ------------------------------------------------------------
    # Order matters: a domain problem outranks a block, and a block outranks
    # any percentage.
    outside_domain = [f for f in incompatible
                      if f.code == "unsupported_architecture"]
    if outside_domain:
        status = ReadinessStatus.OUTSIDE_MODEL_DOMAIN
    elif blocking or incompatible:
        status = ReadinessStatus.BLOCKED
    elif percent >= 80:
        status = ReadinessStatus.READY
    elif percent >= 40:
        status = ReadinessStatus.CONDITIONALLY_READY
    else:
        status = ReadinessStatus.INSUFFICIENT

    actions: list[str] = []
    for finding in (*blocking, *incompatible, *warnings):
        if finding.recommended_action and finding.recommended_action not in actions:
            actions.append(finding.recommended_action)

    return AreaAssessment(
        area=area,
        label=AREA_LABEL[area],
        description=AREA_DESCRIPTION[area],
        status=status,
        readiness_percent=percent,
        evidence_level=evidence,
        evidence_level_rationale=evidence_rationale,
        max_attainable_evidence_level=max_attainable_evidence_level(),
        blocking_issues=blocking,
        warnings=warnings,
        missing_inputs=missing,
        incompatible_inputs=incompatible,
        assumptions=assumptions,
        recommended_actions=actions,
    )


def evaluate_study(records: list[ScientificRecord],
                   approved_evidence: dict[str, dict] | None = None,
                   ) -> ReadinessReport:
    """Assess all six areas independently.

    There is deliberately no combined score. A single number across areas would
    let strong structural data mask absent biological evidence, which is
    exactly the misreading the framework exists to prevent.
    """
    return ReadinessReport(
        areas=[evaluate_area(area, records, approved_evidence)
               for area in ReadinessArea],
        rules_engine_version=RULES_ENGINE_VERSION,
        dictionary_version=DICTIONARY_VERSION,
        evaluated_at=datetime.now(timezone.utc),
    )
