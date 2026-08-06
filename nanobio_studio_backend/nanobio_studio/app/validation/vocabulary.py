"""Vocabularies for the Experimental Validation Registry.

Phase 2, Milestone 1. Nothing here performs a calculation; these are the words
the registry is written in.

The one rule this module exists to enforce
------------------------------------------
**E3 means "approved in-vitro evidence for a specific scientific purpose".** It
does not mean the candidate is validated, the study is validated, or that any
other purpose is supported. A cytotoxicity experiment that passes every gate
promotes *safety assessment* for *that candidate version* and nothing else.

Everything below — the purpose vocabulary, the subtype/purpose compatibility
map, the deliberate absence of E4–E6 — follows from that sentence.
"""

from __future__ import annotations

import enum

from nanobio_studio.app.science.statuses import EvidenceLevel, ReadinessArea

__all__ = [
    "ExperimentSubtype",
    "SUBTYPE_LABEL",
    "ScientificPurpose",
    "PURPOSE_LABEL",
    "SUBTYPE_PERMITTED_PURPOSES",
    "purpose_is_permitted",
    "ExperimentStatus",
    "TERMINAL_STATUSES",
    "EDITABLE_STATUSES",
    "STATUS_LABEL",
    "ReviewDecision",
    "AuditEvent",
    "CANDIDATE_VERSION_EVENTS",
    "EvidenceReuse",
    "EVIDENCE_REUSE_LABEL",
    "SimulationKind",
    "GeneratedArtifactFormat",
    "AttachmentCategory",
    "QualitySeverity",
    "GRANTABLE_LEVELS",
    "MILESTONE",
    "REGISTRY_VERSION",
]

#: Bump when the registry's *behaviour* changes in a way that could alter an
#: eligibility outcome. Stored on every decision, so a historical approval stays
#: interpretable against the rules that produced it.
#: 2.2.0 — contradiction resolution recorded explicitly rather than left
#: as a permanent hold. The gates are unchanged; what changed is that a
#: reviewer can now record WHY conflicting evidence should resolve one way,
#: and until they do the level stays held exactly as before.
REGISTRY_VERSION = "validation-registry-2.2.0"

MILESTONE = "phase-2-milestone-1"


# ---------------------------------------------------------------------------
# What was done
# ---------------------------------------------------------------------------

class ExperimentSubtype(str, enum.Enum):
    """In-vitro assay families.

    Separate subtypes because the measurements genuinely differ: a zeta
    potential is one number in mV under stated conditions, a release profile is
    a series over time, a selectivity assay is a comparison against a
    non-target control. Forcing all of them through one universal measurement
    form would either lose information or invent fields that do not apply.
    """

    PARTICLE_SIZE_PDI = "particle_size_pdi"
    ZETA_POTENTIAL = "zeta_potential"
    DRUG_LOADING = "drug_loading"
    ENCAPSULATION_EFFICIENCY = "encapsulation_efficiency"
    STABILITY = "stability"
    RELEASE_PROFILE = "release_profile"
    TARGET_BINDING = "target_binding"
    CELLULAR_UPTAKE = "cellular_uptake"
    CYTOTOXICITY = "cytotoxicity"
    SELECTIVITY = "selectivity"
    INTRACELLULAR_PATHWAY = "intracellular_pathway"
    HEMOCOMPATIBILITY = "hemocompatibility"
    BASIC_CELLULAR_TOXICITY = "basic_cellular_toxicity"
    OTHER_IN_VITRO = "other_in_vitro"


SUBTYPE_LABEL: dict[ExperimentSubtype, str] = {
    ExperimentSubtype.PARTICLE_SIZE_PDI: "Particle size and polydispersity",
    ExperimentSubtype.ZETA_POTENTIAL: "Zeta potential",
    ExperimentSubtype.DRUG_LOADING: "Drug loading",
    ExperimentSubtype.ENCAPSULATION_EFFICIENCY: "Encapsulation efficiency",
    ExperimentSubtype.STABILITY: "Stability",
    ExperimentSubtype.RELEASE_PROFILE: "Release profile",
    ExperimentSubtype.TARGET_BINDING: "Target binding or receptor affinity",
    ExperimentSubtype.CELLULAR_UPTAKE: "Cellular uptake",
    ExperimentSubtype.CYTOTOXICITY: "Cytotoxicity",
    ExperimentSubtype.SELECTIVITY: "Selectivity",
    ExperimentSubtype.INTRACELLULAR_PATHWAY: "Intracellular pathway response",
    ExperimentSubtype.HEMOCOMPATIBILITY: "Hemocompatibility",
    ExperimentSubtype.BASIC_CELLULAR_TOXICITY: "Basic cellular toxicity",
    ExperimentSubtype.OTHER_IN_VITRO: "Other in-vitro assay",
}

#: Subtypes that involve a biological system. Only these require a cell line,
#: its source and its authentication status — demanding a passage number for a
#: zeta-potential measurement would be a form asking for data that does not
#: exist, which trains people to type something to get past it.
CELL_BASED_SUBTYPES = frozenset({
    ExperimentSubtype.TARGET_BINDING,
    ExperimentSubtype.CELLULAR_UPTAKE,
    ExperimentSubtype.CYTOTOXICITY,
    ExperimentSubtype.SELECTIVITY,
    ExperimentSubtype.INTRACELLULAR_PATHWAY,
    ExperimentSubtype.BASIC_CELLULAR_TOXICITY,
})

#: Subtypes measured over time, where a single end-point value would discard
#: the shape of the result.
TIME_SERIES_SUBTYPES = frozenset({
    ExperimentSubtype.RELEASE_PROFILE,
    ExperimentSubtype.STABILITY,
})


# ---------------------------------------------------------------------------
# What it is evidence FOR
# ---------------------------------------------------------------------------

#: A scientific purpose is one of the six readiness areas.
#:
#: Chosen so an approval lands on the same axis the readiness dashboard already
#: reports, rather than introducing a second vocabulary that would have to be
#: mapped onto the first. The cost is granularity, and it is stated as a known
#: limitation: a single uptake experiment promotes *biological targeting* as a
#: whole rather than "uptake" specifically.
ScientificPurpose = ReadinessArea

PURPOSE_LABEL: dict[ScientificPurpose, str] = {
    ReadinessArea.STRUCTURAL_VISUALIZATION: "Structural visualization",
    ReadinessArea.FORMULATION_ASSESSMENT: "Formulation assessment",
    ReadinessArea.BIOLOGICAL_TARGETING: "Biological targeting",
    ReadinessArea.PHARMACOKINETIC_MODELLING: "Pharmacokinetic modelling",
    ReadinessArea.SAFETY_ASSESSMENT: "Safety assessment",
    ReadinessArea.CINEMATIC_ANIMATION: "Cinematic animation",
}


#: Which purposes each subtype may claim.
#:
#: This is the guard that stops an area-level purpose vocabulary becoming a
#: loophole. Without it a cytotoxicity assay could be filed against
#: "structural visualization" and, if every other gate passed, promote it — the
#: gates check that the work was done *well*, not that it was work of the right
#: kind. So the kind is checked here.
#:
#: Deliberately conservative. Where a subtype plausibly informs an area but does
#: not evidence it, the pairing is omitted: an in-vitro release profile
#: constrains a pharmacokinetic model but does not validate one, because
#: nothing in a dissolution vessel observes distribution or clearance in an
#: organism.
SUBTYPE_PERMITTED_PURPOSES: dict[ExperimentSubtype, frozenset[ScientificPurpose]] = {
    ExperimentSubtype.PARTICLE_SIZE_PDI: frozenset({
        ReadinessArea.STRUCTURAL_VISUALIZATION,
        ReadinessArea.FORMULATION_ASSESSMENT,
    }),
    ExperimentSubtype.ZETA_POTENTIAL: frozenset({
        ReadinessArea.FORMULATION_ASSESSMENT,
    }),
    ExperimentSubtype.DRUG_LOADING: frozenset({
        ReadinessArea.FORMULATION_ASSESSMENT,
    }),
    ExperimentSubtype.ENCAPSULATION_EFFICIENCY: frozenset({
        ReadinessArea.FORMULATION_ASSESSMENT,
    }),
    ExperimentSubtype.STABILITY: frozenset({
        ReadinessArea.FORMULATION_ASSESSMENT,
        ReadinessArea.SAFETY_ASSESSMENT,
    }),
    ExperimentSubtype.RELEASE_PROFILE: frozenset({
        ReadinessArea.FORMULATION_ASSESSMENT,
    }),
    ExperimentSubtype.TARGET_BINDING: frozenset({
        ReadinessArea.BIOLOGICAL_TARGETING,
    }),
    ExperimentSubtype.CELLULAR_UPTAKE: frozenset({
        ReadinessArea.BIOLOGICAL_TARGETING,
    }),
    ExperimentSubtype.CYTOTOXICITY: frozenset({
        ReadinessArea.SAFETY_ASSESSMENT,
    }),
    ExperimentSubtype.SELECTIVITY: frozenset({
        ReadinessArea.BIOLOGICAL_TARGETING,
        ReadinessArea.SAFETY_ASSESSMENT,
    }),
    ExperimentSubtype.INTRACELLULAR_PATHWAY: frozenset({
        ReadinessArea.BIOLOGICAL_TARGETING,
    }),
    ExperimentSubtype.HEMOCOMPATIBILITY: frozenset({
        ReadinessArea.SAFETY_ASSESSMENT,
    }),
    ExperimentSubtype.BASIC_CELLULAR_TOXICITY: frozenset({
        ReadinessArea.SAFETY_ASSESSMENT,
    }),
    # An unclassified assay must state its own method and endpoints, and is
    # restricted to the two areas an in-vitro measurement can speak to without
    # further argument. It is not a wildcard.
    ExperimentSubtype.OTHER_IN_VITRO: frozenset({
        ReadinessArea.FORMULATION_ASSESSMENT,
        ReadinessArea.SAFETY_ASSESSMENT,
    }),
}

#: No in-vitro subtype may claim these.
#:
#: Pharmacokinetic modelling describes what an organism does to a compound, and
#: no cell-culture experiment observes that. Cinematic animation is not
#: implemented at all. Both are listed as *unreachable from this registry*
#: rather than merely absent, so the reason is on the record.
PURPOSES_NO_IN_VITRO_EVIDENCE: frozenset[ScientificPurpose] = frozenset({
    ReadinessArea.PHARMACOKINETIC_MODELLING,
    ReadinessArea.CINEMATIC_ANIMATION,
})


def purpose_is_permitted(subtype: ExperimentSubtype,
                         purpose: ScientificPurpose) -> bool:
    """Whether this kind of experiment may claim this purpose at all."""
    return purpose in SUBTYPE_PERMITTED_PURPOSES.get(subtype, frozenset())


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

class ExperimentStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUIRED = "revision_required"
    SUPERSEDED = "superseded"


STATUS_LABEL: dict[ExperimentStatus, str] = {
    ExperimentStatus.DRAFT: "Draft",
    ExperimentStatus.SUBMITTED: "Submitted",
    ExperimentStatus.UNDER_REVIEW: "Under review",
    ExperimentStatus.APPROVED: "Approved",
    ExperimentStatus.REJECTED: "Rejected",
    ExperimentStatus.REVISION_REQUIRED: "Revision required",
    ExperimentStatus.SUPERSEDED: "Superseded",
}

#: Statuses in which the scientific content may still be edited.
#:
#: Only DRAFT. Submission freezes the version — that is what makes "the
#: acceptance criteria were recorded before the results" a checkable claim
#: rather than an assertion.
EDITABLE_STATUSES = frozenset({ExperimentStatus.DRAFT})

#: Statuses that end a version's life. A new version is the only way forward.
TERMINAL_STATUSES = frozenset({
    ExperimentStatus.APPROVED,
    ExperimentStatus.REJECTED,
    ExperimentStatus.SUPERSEDED,
})

#: Legal transitions. Anything absent is refused by the service, not merely
#: hidden in the interface.
ALLOWED_TRANSITIONS: dict[ExperimentStatus, frozenset[ExperimentStatus]] = {
    ExperimentStatus.DRAFT: frozenset({ExperimentStatus.SUBMITTED}),
    ExperimentStatus.SUBMITTED: frozenset({
        ExperimentStatus.UNDER_REVIEW,
        # A submission may be withdrawn to draft by its owner before review
        # starts. After review begins it may not: the reviewer has seen it.
        ExperimentStatus.DRAFT,
    }),
    ExperimentStatus.UNDER_REVIEW: frozenset({
        ExperimentStatus.APPROVED,
        ExperimentStatus.REJECTED,
        ExperimentStatus.REVISION_REQUIRED,
    }),
    ExperimentStatus.REVISION_REQUIRED: frozenset({
        # Revising creates a NEW version; this version is superseded by it.
        ExperimentStatus.SUPERSEDED,
    }),
    ExperimentStatus.APPROVED: frozenset({ExperimentStatus.SUPERSEDED}),
    ExperimentStatus.REJECTED: frozenset({ExperimentStatus.SUPERSEDED}),
    ExperimentStatus.SUPERSEDED: frozenset(),
}


class ReviewDecision(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"


# ---------------------------------------------------------------------------
# Evidence levels this registry may grant
# ---------------------------------------------------------------------------

#: Milestone 1 grants **E3 only**.
#:
#: E4, E5 and E6 are not in this set and no code path adds them. They require
#: prospective in-vitro registration, in-vivo work and clinical evidence
#: respectively — none of which this registry records — so offering them would
#: be an interface promising something the platform cannot substantiate.
GRANTABLE_LEVELS: frozenset[EvidenceLevel] = frozenset({EvidenceLevel.E3})

#: Shown in the interface so the scale's shape is visible, and explicitly not
#: selectable. Keyed to the milestone that would deliver each.
FUTURE_LEVELS: dict[EvidenceLevel, str] = {
    EvidenceLevel.E4: "Prospective in-vitro validation — coming in a later phase",
    EvidenceLevel.E5: "In-vivo validation — coming in a later phase",
    EvidenceLevel.E6: "Clinical evidence — coming in a later phase",
}


# ---------------------------------------------------------------------------
# Audit, attachments, quality
# ---------------------------------------------------------------------------

class AuditEvent(str, enum.Enum):
    CREATED = "created"
    EDITED = "edited"
    SUBMITTED = "submitted"
    REVIEW_STARTED = "review_started"
    REVIEW_DECISION = "review_decision"
    APPROVED = "approved"
    REJECTED = "rejected"
    VERSION_CREATED = "version_created"
    SUPERSEDED = "superseded"
    ATTACHMENT_ADDED = "attachment_added"
    ATTACHMENT_REMOVED = "attachment_removed"
    EVIDENCE_DECISION = "evidence_decision"
    CONTRADICTION_RESOLVED = "contradiction_resolved"
    PERMISSION_DENIED = "permission_denied"
    ADMIN_OVERRIDE = "admin_override"
    ACCESSED = "accessed"

    # --- candidate revision and supersession -----------------------------
    #
    # Separate members rather than one "version_changed" with a free-text
    # summary. A regulator reading this trail asks "when did this formulation
    # stop being editable, and what relied on it?" — a question an enum can
    # answer by filtering and a prose summary can only be grepped for.

    #: A revision was derived from a predecessor version.
    REVISION_CREATED = "revision_created"
    #: A version's scientific inputs stopped being editable, and why.
    VERSION_LOCKED = "version_locked"
    #: Somebody asked for derived results to be recomputed for a version.
    RECALCULATION_REQUESTED = "recalculation_requested"
    #: The recomputation finished and the results describe this version.
    RECALCULATION_COMPLETED = "recalculation_completed"
    #: A revision changed something that prior assessments cannot carry over.
    REASSESSMENT_REQUIRED = "reassessment_required"
    #: Retired without a successor.
    VERSION_WITHDRAWN = "version_withdrawn"
    #: A successor was put forward, agreed, or declined. Three members because
    #: proposing is not deciding, and a refusal is a finding in its own right.
    SUPERSESSION_PROPOSED = "supersession_proposed"
    SUPERSESSION_ACCEPTED = "supersession_accepted"
    SUPERSESSION_REFUSED = "supersession_refused"

    # --- dependent records -----------------------------------------------
    SIMULATION_RECORDED = "simulation_recorded"
    EVIDENCE_ASSESSED = "evidence_assessed"
    REPORT_GENERATED = "report_generated"
    EXPORT_GENERATED = "export_generated"
    PACKAGE_GENERATED = "package_generated"
    COMPARISON_RECORDED = "comparison_recorded"


#: Events that describe a candidate version rather than an experiment.
#:
#: Kept as data so the version-history screen can ask for exactly these
#: without hard-coding a list that drifts from the enum above.
CANDIDATE_VERSION_EVENTS: frozenset[AuditEvent] = frozenset({
    AuditEvent.VERSION_CREATED,
    AuditEvent.REVISION_CREATED,
    AuditEvent.VERSION_LOCKED,
    AuditEvent.RECALCULATION_REQUESTED,
    AuditEvent.RECALCULATION_COMPLETED,
    AuditEvent.REASSESSMENT_REQUIRED,
    AuditEvent.VERSION_WITHDRAWN,
    AuditEvent.SUPERSESSION_PROPOSED,
    AuditEvent.SUPERSESSION_ACCEPTED,
    AuditEvent.SUPERSESSION_REFUSED,
    AuditEvent.SIMULATION_RECORDED,
    AuditEvent.EVIDENCE_ASSESSED,
    AuditEvent.REPORT_GENERATED,
    AuditEvent.EXPORT_GENERATED,
    AuditEvent.PACKAGE_GENERATED,
    AuditEvent.COMPARISON_RECORDED,
})


class EvidenceReuse(str, enum.Enum):
    """How evidence gathered on one version relates to a later one.

    The three-way split exists because "the old data still applies" and "the
    old data needs looking at again" are different scientific claims, and
    leaving them both as an unqualified citation makes the weaker one look
    like the stronger. There is deliberately no fourth value meaning
    "unclassified": an assessment that has not been classified is one that has
    not been made.
    """

    #: The experiment was performed on a predecessor and is cited as such. It
    #: still describes what it described; it is not re-attested to this version.
    RETAINED_REFERENCE = "retained_reference"

    #: A material change means the earlier work can no longer speak for this
    #: version until somebody looks at it again.
    REASSESSMENT_REQUIRED = "reassessment_required"

    #: Work performed against THIS exact version.
    NEWLY_VALIDATED = "newly_validated"


EVIDENCE_REUSE_LABEL: dict[EvidenceReuse, str] = {
    EvidenceReuse.RETAINED_REFERENCE: "Retained reference from an earlier version",
    EvidenceReuse.REASSESSMENT_REQUIRED: "Reassessment required",
    EvidenceReuse.NEWLY_VALIDATED: "Newly validated against this version",
}


class SimulationKind(str, enum.Enum):
    """Which calculation produced a stored simulation result.

    Named rather than inferred from the payload shape: two engines that both
    return a curve are still two engines, and a stored record has to say which
    one it came from for the result to be reproducible.
    """

    PHARMACOKINETIC = "pharmacokinetic"
    DESIGN_SCORE = "design_score"
    READINESS = "readiness"


class GeneratedArtifactFormat(str, enum.Enum):
    JSON = "json"
    MARKDOWN = "markdown"
    CSV = "csv"


class AttachmentCategory(str, enum.Enum):
    RAW_DATA = "raw_data"
    PROCESSED_DATA = "processed_data"
    PROTOCOL = "protocol"
    LABORATORY_REPORT = "laboratory_report"
    IMAGE = "image"
    INSTRUMENT_EXPORT = "instrument_export"
    STATISTICAL_OUTPUT = "statistical_output"
    CERTIFICATE = "certificate"


#: Categories that count as raw or source data for the provenance gate.
#: A processed spreadsheet is not raw data, and accepting one as such would let
#: a result be "sourced" from its own summary.
RAW_DATA_CATEGORIES = frozenset({
    AttachmentCategory.RAW_DATA,
    AttachmentCategory.INSTRUMENT_EXPORT,
})


class QualitySeverity(str, enum.Enum):
    OBSERVATION = "observation"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


#: A severity that blocks E3 while unresolved.
BLOCKING_SEVERITIES = frozenset({QualitySeverity.CRITICAL})
