"""The E3 eligibility evaluator.

Deterministic, pure and versioned: the same experiment version and the same
``REGISTRY_VERSION`` always produce the same verdict, which is what makes a
stored decision re-checkable.

What E3 means here
------------------
**Approved in-vitro evidence for one scientific purpose, on one candidate
version.** Not that the candidate is validated, not that the study is
validated, and not that any other purpose is supported.

Two things this module refuses to do
------------------------------------
1. **Infer E3 from the experiment type.** A cytotoxicity assay is not evidence
   because it is a cytotoxicity assay. Every gate below is about whether the
   work was documented well enough to be checkable by somebody who was not
   there.

2. **Impose one universal replicate minimum.** A defensible n differs by assay
   — three independent preparations mean something different in a DLS
   measurement and in a cell-viability curve. So the evaluator requires the
   counts to be *reported* and leaves sufficiency to the reviewer, who must
   record a justification. A hard-coded number would be a scientific claim the
   platform cannot support.

Gate results are returned in full, passed and failed alike, with a
human-readable explanation. A verdict that says only "not eligible" is a dead
end for the person who has to fix it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from typing import Any, Sequence

from nanobio_studio.app.science.statuses import EvidenceLevel
from nanobio_studio.app.validation.vocabulary import (
    BLOCKING_SEVERITIES,
    CELL_BASED_SUBTYPES,
    GRANTABLE_LEVELS,
    RAW_DATA_CATEGORIES,
    REGISTRY_VERSION,
    AttachmentCategory,
    ExperimentStatus,
    ExperimentSubtype,
    QualitySeverity,
    ScientificPurpose,
    purpose_is_permitted,
)

__all__ = [
    "GateResult",
    "EligibilityVerdict",
    "ExperimentFacts",
    "evaluate_e3_eligibility",
    "GATE_IDS",
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateResult:
    id: str
    label: str
    passed: bool
    #: Why it passed or failed, in plain language.
    detail: str
    #: What the user must do. None when the gate passed.
    remedy: str | None = None
    #: True when the gate does not apply to this assay and was skipped.
    not_applicable: bool = False


@dataclass
class EligibilityVerdict:
    eligible: bool
    purpose: ScientificPurpose
    requested_level: EvidenceLevel | None
    approved_level: EvidenceLevel | None
    gates: list[GateResult] = dc_field(default_factory=list)
    missing_requirements: list[str] = dc_field(default_factory=list)
    contradiction_warning: str | None = None
    explanation: str = ""
    ruleset_version: str = REGISTRY_VERSION

    @property
    def passed_gates(self) -> list[GateResult]:
        return [g for g in self.gates if g.passed and not g.not_applicable]

    @property
    def failed_gates(self) -> list[GateResult]:
        return [g for g in self.gates if not g.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "purpose": self.purpose.value,
            "requested_level": (self.requested_level.value
                                if self.requested_level else None),
            "approved_level": (self.approved_level.value
                               if self.approved_level else None),
            "passed_gates": [g.id for g in self.passed_gates],
            "failed_gates": [g.id for g in self.failed_gates],
            "gates": [
                {"id": g.id, "label": g.label, "passed": g.passed,
                 "detail": g.detail, "remedy": g.remedy,
                 "not_applicable": g.not_applicable}
                for g in self.gates
            ],
            "missing_requirements": list(self.missing_requirements),
            "contradiction_warning": self.contradiction_warning,
            "explanation": self.explanation,
            "ruleset_version": self.ruleset_version,
        }


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

@dataclass
class ExperimentFacts:
    """Everything the evaluator reads, decoupled from the ORM.

    A plain structure rather than a model instance so the gates can be tested
    exhaustively without a database, and so the evaluator cannot accidentally
    trigger lazy loads or depend on session state.
    """

    subtype: ExperimentSubtype
    purpose: ScientificPurpose
    status: ExperimentStatus
    requested_level: EvidenceLevel | None

    candidate_version_id: int | None = None
    candidate_snapshot_checksum: str | None = None
    #: The checksum recomputed from the stored snapshot at evaluation time.
    candidate_snapshot_recomputed: str | None = None

    scientific_question: str | None = None
    protocol_identifier: str | None = None
    protocol_version: str | None = None
    laboratory_name: str | None = None
    investigator_name: str | None = None
    investigator_org: str | None = None

    biological_model: str | None = None
    cell_line: str | None = None
    cell_source: str | None = None
    cell_authentication_status: str | None = None
    assay_method: str | None = None

    control_positive: str | None = None
    control_negative: str | None = None
    control_vehicle: str | None = None
    controls_not_applicable_reason: str | None = None

    biological_replicates: int | None = None
    technical_replicates: int | None = None
    replicate_justification: str | None = None

    acceptance_criteria: list[dict[str, Any]] = dc_field(default_factory=list)
    acceptance_criteria_recorded_at: datetime | None = None
    acceptance_criteria_met: bool | None = None

    measurements: list[dict[str, Any]] = dc_field(default_factory=list)
    first_measurement_recorded_at: datetime | None = None

    attachment_categories: list[AttachmentCategory] = dc_field(default_factory=list)
    raw_data_reference: str | None = None

    statistical_method: str | None = None
    statistical_method_not_applicable_reason: str | None = None

    deviations: str | None = None
    exclusions: str | None = None
    missing_data: str | None = None
    disclosures_confirmed: bool = False

    quality_issues: list[dict[str, Any]] = dc_field(default_factory=list)
    provenance_declaration: str | None = None

    #: Approval facts.
    approved: bool = False
    performed_by: int | None = None
    decision_by: int | None = None
    reviewer_id: int | None = None
    decision_comments: str | None = None


def _filled(value: str | None) -> bool:
    return bool(value and value.strip())


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalise a timestamp to aware UTC before comparing.

    SQLite does not persist a timezone, so a value written as aware comes back
    naive. Comparing the two raises, which would make the predefined-criteria
    gate — the one that checks criteria predate results — crash on exactly the
    records it exists to examine.

    A naive timestamp is read as UTC because that is what every writer in this
    application stores.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

GATE_IDS: tuple[str, ...] = (
    "candidate_version_linkage",
    "candidate_snapshot_integrity",
    "purpose_declared",
    "purpose_compatible_with_subtype",
    "protocol_recorded",
    "provenance_recorded",
    "biological_model_and_method",
    "controls_present",
    "replicates_reported",
    "acceptance_criteria_predefined",
    "structured_results_recorded",
    "raw_data_available",
    "statistical_method_documented",
    "disclosures_made",
    "no_unresolved_critical_quality_issue",
    "acceptance_criteria_satisfied",
    "independent_approval",
)


def _gate_candidate_linkage(f: ExperimentFacts) -> GateResult:
    ok = f.candidate_version_id is not None
    return GateResult(
        "candidate_version_linkage", "Linked to an exact candidate version", ok,
        "The experiment is linked to a specific candidate version."
        if ok else "No candidate version is linked.",
        None if ok else
        "Link the experiment to the exact candidate version that was tested.")


def _gate_snapshot_integrity(f: ExperimentFacts) -> GateResult:
    """The linked snapshot must still be the one that was tested.

    Compares the checksum stored on the version against one recomputed from the
    snapshot now. A mismatch means the immutable record is not immutable, which
    invalidates every result attributed to it — so this fails loudly rather
    than being treated as a warning.
    """
    if f.candidate_snapshot_checksum is None:
        return GateResult(
            "candidate_snapshot_integrity", "Candidate snapshot verifiable",
            False, "The linked candidate version carries no checksum.",
            "Re-link the experiment to a candidate version created by this "
            "registry.")
    if f.candidate_snapshot_recomputed is None:
        return GateResult(
            "candidate_snapshot_integrity", "Candidate snapshot verifiable",
            False, "The candidate snapshot could not be read for verification.",
            "Investigate the stored candidate version.")
    ok = f.candidate_snapshot_checksum == f.candidate_snapshot_recomputed
    return GateResult(
        "candidate_snapshot_integrity", "Candidate snapshot verifiable", ok,
        "The candidate snapshot matches the checksum recorded when the "
        "experiment was linked to it."
        if ok else
        "The candidate snapshot does not match its recorded checksum. The "
        "material described has changed since the experiment was linked, so "
        "the results cannot be attributed to it.",
        None if ok else
        "Create a new candidate version and repeat the experiment against it.")


def _gate_purpose_declared(f: ExperimentFacts) -> GateResult:
    ok = _filled(f.scientific_question)
    return GateResult(
        "purpose_declared", "Scientific purpose and question stated", ok,
        "The experiment states the question it answers."
        if ok else "No scientific question is recorded.",
        None if ok else "State the scientific question this experiment answers.")


def _gate_purpose_compatible(f: ExperimentFacts) -> GateResult:
    """The assay must be capable of evidencing the purpose it claims.

    The other gates test whether the work was done well. This one tests whether
    it was work of the right kind — without it, a well-run cytotoxicity assay
    could promote structural visualization.
    """
    ok = purpose_is_permitted(f.subtype, f.purpose)
    return GateResult(
        "purpose_compatible_with_subtype",
        "Assay can evidence the claimed purpose", ok,
        f"A {f.subtype.value.replace('_', ' ')} assay is accepted as evidence "
        f"for {f.purpose.value.replace('_', ' ')}."
        if ok else
        f"A {f.subtype.value.replace('_', ' ')} assay is not accepted as "
        f"evidence for {f.purpose.value.replace('_', ' ')}. An in-vitro "
        "measurement cannot evidence a purpose it does not observe.",
        None if ok else
        "File this experiment against a purpose its method can speak to, or "
        "record a different experiment for this purpose.")


def _gate_protocol(f: ExperimentFacts) -> GateResult:
    ok = _filled(f.protocol_identifier) and _filled(f.protocol_version)
    return GateResult(
        "protocol_recorded", "Protocol and protocol version recorded", ok,
        "A protocol identifier and version are recorded."
        if ok else "The protocol identifier, its version, or both are missing.",
        None if ok else
        "Record the protocol identifier and the exact version followed.")


def _gate_provenance(f: ExperimentFacts) -> GateResult:
    missing = [name for name, value in (
        ("laboratory or CRO", f.laboratory_name),
        ("responsible investigator", f.investigator_name),
        ("investigator's organization", f.investigator_org),
    ) if not _filled(value)]
    ok = not missing
    return GateResult(
        "provenance_recorded", "Laboratory and investigator recorded", ok,
        "The laboratory, investigator and organization are recorded."
        if ok else f"Not recorded: {', '.join(missing)}.",
        None if ok else
        "Record who performed the work and where. A result nobody is named "
        "against cannot be followed up.")


def _gate_model_and_method(f: ExperimentFacts) -> GateResult:
    if not _filled(f.assay_method):
        return GateResult(
            "biological_model_and_method", "Biological model and assay method",
            False, "No assay method is recorded.",
            "Record the assay method.")
    if f.subtype in CELL_BASED_SUBTYPES:
        missing = [name for name, value in (
            ("biological model", f.biological_model),
            ("cell line or system", f.cell_line),
            ("cell source", f.cell_source),
            ("authentication status", f.cell_authentication_status),
        ) if not _filled(value)]
        if missing:
            return GateResult(
                "biological_model_and_method",
                "Biological model and assay method", False,
                f"This is a cell-based assay and these are not recorded: "
                f"{', '.join(missing)}.",
                "Record the cell system, where it came from and whether it "
                "was authenticated. An unauthenticated line is a known source "
                "of irreproducible results.")
        return GateResult(
            "biological_model_and_method", "Biological model and assay method",
            True, "The cell system, its source, its authentication status and "
            "the assay method are recorded.")
    return GateResult(
        "biological_model_and_method", "Biological model and assay method",
        True, "The assay method is recorded. This assay is not cell-based, so "
        "no cell system is required.")


def _gate_controls(f: ExperimentFacts) -> GateResult:
    """Controls, or a stated reason they do not apply.

    A physicochemical measurement often has no meaningful vehicle control, and
    demanding one would push people to type "n/a" into a scientific field. So
    an explicit, recorded reason is accepted — but silence is not.
    """
    present = [name for name, value in (
        ("positive", f.control_positive),
        ("negative", f.control_negative),
        ("vehicle", f.control_vehicle),
    ) if _filled(value)]

    if f.subtype in CELL_BASED_SUBTYPES:
        missing = [n for n in ("positive", "negative", "vehicle")
                   if n not in present]
        if missing and not _filled(f.controls_not_applicable_reason):
            return GateResult(
                "controls_present", "Applicable controls present", False,
                f"This is a cell-based assay and these controls are neither "
                f"recorded nor explained: {', '.join(missing)}.",
                "Record the controls used, or state why a control does not "
                "apply to this assay.")
        return GateResult(
            "controls_present", "Applicable controls present", True,
            f"Controls recorded: {', '.join(present) or 'none'}."
            + (" A reason is recorded for those not used."
               if missing else ""))

    if not present and not _filled(f.controls_not_applicable_reason):
        return GateResult(
            "controls_present", "Applicable controls present", False,
            "No controls are recorded and no reason is given for their "
            "absence.",
            "Record the controls used, or state why controls do not apply to "
            "this measurement.")
    return GateResult(
        "controls_present", "Applicable controls present", True,
        f"Controls recorded: {', '.join(present) or 'none'}."
        if present else
        "No controls, with a recorded reason why they do not apply.")


def _gate_replicates(f: ExperimentFacts) -> GateResult:
    """Replicate counts must be reported. Sufficiency is the reviewer's call.

    No universal minimum is imposed — see the module docstring. What is
    non-negotiable is disclosure: a result whose n is unknown cannot be
    weighed by anybody.
    """
    missing = [name for name, value in (
        ("biological replicates", f.biological_replicates),
        ("technical replicates", f.technical_replicates),
    ) if value is None]
    if missing:
        return GateResult(
            "replicates_reported", "Replicate counts reported", False,
            f"Not reported: {', '.join(missing)}.",
            "Report both counts. If a count is one, report one — the number "
            "is the information, and a low n disclosed is not the same "
            "problem as an n nobody stated.")
    if (f.biological_replicates or 0) < 1 or (f.technical_replicates or 0) < 1:
        return GateResult(
            "replicates_reported", "Replicate counts reported", False,
            "A replicate count below one is not a possible experiment.",
            "Correct the replicate counts.")
    return GateResult(
        "replicates_reported", "Replicate counts reported", True,
        f"{f.biological_replicates} biological and "
        f"{f.technical_replicates} technical replicates reported. Whether "
        "that is sufficient for this assay is a reviewer judgement, recorded "
        "with the approval.")


def _gate_acceptance_predefined(f: ExperimentFacts) -> GateResult:
    """Criteria must exist and must predate the results.

    The timestamp comparison is the substance of this gate. Criteria written
    after the data are not acceptance criteria; they are a description of what
    happened, and they cannot fail.
    """
    if not f.acceptance_criteria:
        return GateResult(
            "acceptance_criteria_predefined", "Acceptance criteria predefined",
            False, "No predefined acceptance criteria are recorded.",
            "Record the acceptance criteria before submitting results.")
    if f.acceptance_criteria_recorded_at is None:
        return GateResult(
            "acceptance_criteria_predefined", "Acceptance criteria predefined",
            False, "Acceptance criteria are recorded but carry no timestamp, "
            "so they cannot be shown to predate the results.",
            "Re-record the criteria so the time they were set is captured.")
    criteria_at = _as_utc(f.acceptance_criteria_recorded_at)
    first_at = _as_utc(f.first_measurement_recorded_at)
    if first_at is not None and criteria_at is not None and criteria_at > first_at:
        return GateResult(
            "acceptance_criteria_predefined", "Acceptance criteria predefined",
            False,
            "The acceptance criteria were recorded after the first "
            "measurement. Criteria set once the data are in cannot fail, so "
            "they are not acceptance criteria.",
            "Record criteria before results in a new version of this "
            "experiment.")
    return GateResult(
        "acceptance_criteria_predefined", "Acceptance criteria predefined",
        True, f"{len(f.acceptance_criteria)} criterion(s) recorded before the "
        "first measurement.")


def _gate_structured_results(f: ExperimentFacts) -> GateResult:
    usable = [m for m in f.measurements if not m.get("excluded")]
    if not usable:
        return GateResult(
            "structured_results_recorded", "Structured results and units", False,
            "No structured measurements are recorded."
            if not f.measurements else
            "Every recorded measurement is excluded.",
            "Record the measurements as structured rows, not only as a "
            "narrative conclusion.")
    missing_unit = [m for m in usable
                    if m.get("result_numeric") is not None
                    and not str(m.get("result_unit") or "").strip()]
    if missing_unit:
        return GateResult(
            "structured_results_recorded", "Structured results and units", False,
            f"{len(missing_unit)} numeric measurement(s) carry no unit. A "
            "bare number is not a measurement.",
            "Record the unit for every numeric result.")
    unresolved = [m for m in usable
                  if m.get("result_numeric") is None
                  and not str(m.get("result_text") or "").strip()
                  and not str(m.get("missing_value_reason") or "").strip()]
    if unresolved:
        return GateResult(
            "structured_results_recorded", "Structured results and units", False,
            f"{len(unresolved)} measurement(s) have neither a result nor a "
            "stated reason for being absent.",
            "Record a result, or state why the value is missing.")
    return GateResult(
        "structured_results_recorded", "Structured results and units", True,
        f"{len(usable)} structured measurement(s) recorded with units.")


def _gate_raw_data(f: ExperimentFacts) -> GateResult:
    has_raw = any(c in RAW_DATA_CATEGORIES for c in f.attachment_categories)
    has_reference = _filled(f.raw_data_reference)
    ok = has_raw or has_reference
    return GateResult(
        "raw_data_available", "Raw or source data attached or referenced", ok,
        ("Raw data is attached." if has_raw
         else "A raw-data reference is recorded.") if ok else
        "Neither raw data nor a reference to it is recorded. A processed "
        "summary cannot be its own source.",
        None if ok else
        "Attach the instrument output or raw dataset, or record a durable "
        "reference to where it is held.")


def _gate_statistics(f: ExperimentFacts) -> GateResult:
    """Required where an inference is drawn; excusable with a stated reason.

    A single-replicate descriptive measurement has nothing to test, and
    demanding a statistical method there produces ceremony rather than rigour.
    """
    if _filled(f.statistical_method):
        return GateResult(
            "statistical_method_documented", "Statistical method documented",
            True, "A statistical method is recorded.")
    if _filled(f.statistical_method_not_applicable_reason):
        return GateResult(
            "statistical_method_documented", "Statistical method documented",
            True, "No statistical method, with a recorded reason why none "
            "applies.", not_applicable=True)
    return GateResult(
        "statistical_method_documented", "Statistical method documented",
        False, "No statistical method is recorded and no reason is given for "
        "its absence.",
        "Record the statistical method, or state why none applies to this "
        "measurement.")


def _gate_disclosures(f: ExperimentFacts) -> GateResult:
    """Deviations, exclusions and missing data must be addressed explicitly.

    A blank field is ambiguous between "there were none" and "nobody looked",
    so an explicit confirmation is required alongside any text.
    """
    excluded = [m for m in f.measurements if m.get("excluded")]
    unjustified = [m for m in excluded
                   if not str(m.get("exclusion_justification") or "").strip()]
    if unjustified:
        return GateResult(
            "disclosures_made", "Deviations, exclusions and missing data", False,
            f"{len(unjustified)} measurement(s) are excluded without a "
            "justification.",
            "Justify every exclusion. An undisclosed exclusion is the "
            "difference between a result and a selected result.")
    if not f.disclosures_confirmed:
        return GateResult(
            "disclosures_made", "Deviations, exclusions and missing data", False,
            "Deviations, exclusions and missing data have not been "
            "explicitly confirmed.",
            "Confirm the disclosures, recording 'none' where that is the "
            "case.")
    return GateResult(
        "disclosures_made", "Deviations, exclusions and missing data", True,
        "Disclosures confirmed"
        + (f"; {len(excluded)} exclusion(s), each justified." if excluded
           else "; no exclusions."))


def _gate_quality(f: ExperimentFacts) -> GateResult:
    critical = [
        q for q in f.quality_issues
        if str(q.get("severity", "")).lower() in
        {s.value for s in BLOCKING_SEVERITIES} and not q.get("resolved")
    ]
    ok = not critical
    return GateResult(
        "no_unresolved_critical_quality_issue",
        "No unresolved critical quality issue", ok,
        "No unresolved critical quality issue is recorded." if ok else
        f"{len(critical)} unresolved critical quality issue(s) are recorded.",
        None if ok else
        "Resolve the critical issue and record the resolution, or record a "
        "new version of the experiment.")


def _gate_criteria_satisfied(f: ExperimentFacts) -> GateResult:
    """Did the results actually meet the predefined criteria?

    Evaluated from the measurements where the criteria are machine-checkable,
    and otherwise from the investigator's recorded determination — which the
    reviewer is separately required to confirm. The investigator's claim is
    never accepted where the data can answer directly.
    """
    if not f.acceptance_criteria:
        return GateResult(
            "acceptance_criteria_satisfied", "Results satisfy the criteria",
            False, "There are no criteria to satisfy.",
            "Record predefined acceptance criteria.")

    checkable = [c for c in f.acceptance_criteria
                 if c.get("endpoint") and c.get("comparator")
                 and c.get("value") is not None]
    failures: list[str] = []
    for criterion in checkable:
        endpoint = criterion["endpoint"]
        comparator = str(criterion["comparator"])
        threshold = float(criterion["value"])
        values = [
            m.get("result_numeric") for m in f.measurements
            if m.get("endpoint_name") == endpoint
            and not m.get("excluded")
            and m.get("result_numeric") is not None
        ]
        if not values:
            failures.append(
                f"{endpoint}: no usable measurement to test the criterion "
                "against")
            continue
        mean = sum(values) / len(values)
        satisfied = {
            ">=": mean >= threshold, ">": mean > threshold,
            "<=": mean <= threshold, "<": mean < threshold,
            "==": mean == threshold,
        }.get(comparator)
        if satisfied is None:
            failures.append(f"{endpoint}: unrecognised comparator "
                            f"{comparator!r}")
        elif not satisfied:
            failures.append(
                f"{endpoint}: mean {mean:g} does not satisfy "
                f"{comparator} {threshold:g}")

    if failures:
        return GateResult(
            "acceptance_criteria_satisfied", "Results satisfy the criteria",
            False, "; ".join(failures),
            "The experiment did not meet its predefined criteria. The record "
            "is preserved and remains visible; it does not support E3.")

    if not checkable:
        if f.acceptance_criteria_met is None:
            return GateResult(
                "acceptance_criteria_satisfied", "Results satisfy the criteria",
                False,
                "The criteria are not machine-checkable and the investigator "
                "has not recorded whether they were met.",
                "Record whether the predefined criteria were met.")
        if not f.acceptance_criteria_met:
            return GateResult(
                "acceptance_criteria_satisfied", "Results satisfy the criteria",
                False, "The investigator records that the criteria were not "
                "met.",
                "The record is preserved and remains visible; it does not "
                "support E3.")
        return GateResult(
            "acceptance_criteria_satisfied", "Results satisfy the criteria",
            True, "The investigator records that the predefined criteria were "
            "met. The criteria are not machine-checkable, so the reviewer's "
            "confirmation carries this gate.")

    return GateResult(
        "acceptance_criteria_satisfied", "Results satisfy the criteria", True,
        f"All {len(checkable)} machine-checkable criterion(s) are satisfied by "
        "the recorded measurements.")


def _gate_independent_approval(f: ExperimentFacts) -> GateResult:
    """Approved, by somebody who did not perform the work.

    The self-approval bar is enforced in the service as well; it is repeated
    here so a verdict computed on an already-stored record still reports it
    rather than assuming the earlier check held.
    """
    if not f.approved:
        return GateResult(
            "independent_approval", "Independent scientific approval", False,
            "The experiment version has not been approved.",
            "Submit the experiment for scientific review.")
    if f.decision_by is None:
        return GateResult(
            "independent_approval", "Independent scientific approval", False,
            "The approval records no approver.",
            "Re-record the approval with the approver's identity.")
    if f.performed_by is not None and f.decision_by == f.performed_by:
        return GateResult(
            "independent_approval", "Independent scientific approval", False,
            "The approver also performed the experiment. Self-approval is not "
            "independent review.",
            "Have a reviewer who did not perform the work approve the record.")
    return GateResult(
        "independent_approval", "Independent scientific approval", True,
        "Approved by a reviewer who did not perform the experiment.")


_GATES = (
    _gate_candidate_linkage,
    _gate_snapshot_integrity,
    _gate_purpose_declared,
    _gate_purpose_compatible,
    _gate_protocol,
    _gate_provenance,
    _gate_model_and_method,
    _gate_controls,
    _gate_replicates,
    _gate_acceptance_predefined,
    _gate_structured_results,
    _gate_raw_data,
    _gate_statistics,
    _gate_disclosures,
    _gate_quality,
    _gate_criteria_satisfied,
    _gate_independent_approval,
)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def evaluate_e3_eligibility(facts: ExperimentFacts) -> EligibilityVerdict:
    """Run every gate and return the full verdict.

    All gates always run. Short-circuiting on the first failure would return a
    verdict that is technically correct and useless — the person fixing the
    record would discover the next problem only after fixing this one.
    """
    gates = [gate(facts) for gate in _GATES]
    failed = [g for g in gates if not g.passed]

    # E3 is the only level this registry grants. A request for anything else is
    # refused outright rather than downgraded, because silently approving a
    # lower level than was asked for would misrepresent the decision.
    requested = facts.requested_level
    level_ok = requested is None or requested in GRANTABLE_LEVELS
    if not level_ok:
        gates.append(GateResult(
            "requested_level_grantable", "Requested level can be granted",
            False,
            f"{requested.value} cannot be granted by this registry. Only E3 "
            "is available; E4 to E6 require prospective in-vitro, in-vivo and "
            "clinical evidence that this milestone does not record.",
            "Request E3, or record the evidence a higher level requires when "
            "a later phase supports it."))
        failed = [g for g in gates if not g.passed]

    eligible = not failed
    approved_level = EvidenceLevel.E3 if eligible else None

    if eligible:
        explanation = (
            f"Eligible for E3 in support of "
            f"{facts.purpose.value.replace('_', ' ')}. Every applicable gate "
            f"passed: the experiment is linked to a verified candidate "
            f"version, its protocol and provenance are recorded, its "
            f"acceptance criteria were set before the results, the results "
            f"satisfy them, and it was approved by somebody who did not "
            f"perform it. This supports that purpose on that candidate "
            f"version only, and no other."
        )
    else:
        explanation = (
            f"Not eligible for E3. {len(failed)} gate(s) failed: "
            + "; ".join(g.label for g in failed)
            + ". The record is preserved and remains visible. E3 requires "
            "every applicable gate to pass — an experiment is not evidence "
            "because of what kind of experiment it is."
        )

    return EligibilityVerdict(
        eligible=eligible,
        purpose=facts.purpose,
        requested_level=requested,
        approved_level=approved_level,
        gates=gates,
        missing_requirements=[g.remedy for g in failed if g.remedy],
        explanation=explanation,
        ruleset_version=REGISTRY_VERSION,
    )


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------

def detect_contradiction(
    verdicts: Sequence[EligibilityVerdict],
    conclusions: Sequence[bool | None],
) -> str | None:
    """Warn when approved evidence for one purpose materially conflicts.

    Takes the eligible verdicts for a single purpose and candidate version,
    together with each experiment's recorded outcome. When approved records
    disagree, the readiness engine must not silently pick the favourable one —
    it shows the conflict and holds the level until a reviewer resolves it.
    """
    eligible = [v for v, _ in zip(verdicts, conclusions) if v.eligible]
    if len(eligible) < 2:
        return None
    outcomes = {c for v, c in zip(verdicts, conclusions)
                if v.eligible and c is not None}
    if len(outcomes) > 1:
        return (
            "Approved experiments for this purpose disagree: at least one "
            "met its acceptance criteria and at least one did not. The "
            "evidence level is held at its previously justified value until a "
            "reviewer records a resolution. No record has been discarded and "
            "the favourable result has not been preferred."
        )
    return None
