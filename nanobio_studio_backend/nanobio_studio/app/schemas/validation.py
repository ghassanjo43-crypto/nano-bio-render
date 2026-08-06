"""Request and response schemas for the Experimental Validation Registry.

Bounds here are structural. No field carries a scientific default: a default
would manufacture provenance the experiment does not have, which is the whole
failure mode the registry exists to prevent.

Conditional validation lives in the eligibility evaluator, not here. The schema
accepts a partially-filled draft on purpose — an investigator records what they
have as they get it, and the gates decide whether the result is enough to
support E3. Refusing an incomplete draft at the schema would force people to
invent values to save their work.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CandidateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: int
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=4000)


class CandidateVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: The formulation to freeze. Copied verbatim into an immutable snapshot.
    design_inputs: Dict[str, Any]
    note: Optional[str] = Field(None, max_length=2000)


class ExperimentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_version_id: int
    subtype: str = Field(..., description="An ExperimentSubtype value.")
    purpose: str = Field(..., description="A ReadinessArea value.")
    title: str = Field(..., min_length=1, max_length=300)
    code: Optional[str] = Field(None, max_length=64)
    #: Who ran the assay, when that is not the person filing the record.
    #: Compared against the approver to bar self-approval.
    performed_by: Optional[int] = None


class DraftUpdateRequest(BaseModel):
    """Every editable scientific field. All optional; a draft grows over time."""

    model_config = ConfigDict(extra="forbid")

    scientific_question: Optional[str] = Field(None, max_length=4000)
    hypothesis: Optional[str] = Field(None, max_length=4000)

    laboratory_name: Optional[str] = Field(None, max_length=200)
    investigator_name: Optional[str] = Field(None, max_length=200)
    investigator_org: Optional[str] = Field(None, max_length=200)
    start_date: Optional[str] = Field(None, max_length=10)
    completion_date: Optional[str] = Field(None, max_length=10)

    protocol_identifier: Optional[str] = Field(None, max_length=120)
    protocol_version: Optional[str] = Field(None, max_length=40)
    nanoparticle_batch: Optional[str] = Field(None, max_length=120)
    payload_batch: Optional[str] = Field(None, max_length=120)

    biological_model: Optional[str] = Field(None, max_length=200)
    cell_line: Optional[str] = Field(None, max_length=200)
    cell_source: Optional[str] = Field(None, max_length=200)
    cell_authentication_status: Optional[str] = Field(None, max_length=120)
    passage_number: Optional[str] = Field(None, max_length=60)

    assay_method: Optional[str] = Field(None, max_length=4000)
    endpoints_json: Optional[str] = Field(None, max_length=4000)
    measurement_units: Optional[str] = Field(None, max_length=200)

    control_positive: Optional[str] = Field(None, max_length=2000)
    control_negative: Optional[str] = Field(None, max_length=2000)
    control_vehicle: Optional[str] = Field(None, max_length=2000)
    controls_not_applicable_reason: Optional[str] = Field(None, max_length=2000)

    biological_replicates: Optional[int] = Field(None, ge=0, le=10_000)
    technical_replicates: Optional[int] = Field(None, ge=0, le=10_000)
    replicate_justification: Optional[str] = Field(None, max_length=2000)

    acceptance_criteria_json: Optional[str] = Field(None, max_length=8000)
    raw_data_reference: Optional[str] = Field(None, max_length=2000)
    processed_results_summary: Optional[str] = Field(None, max_length=8000)
    statistical_method: Optional[str] = Field(None, max_length=2000)
    statistical_method_not_applicable_reason: Optional[str] = Field(
        None, max_length=2000)

    deviations: Optional[str] = Field(None, max_length=4000)
    exclusions: Optional[str] = Field(None, max_length=4000)
    missing_data: Optional[str] = Field(None, max_length=4000)
    disclosures_confirmed: Optional[bool] = None

    investigator_conclusion: Optional[str] = Field(None, max_length=8000)
    quality_issues_json: Optional[str] = Field(None, max_length=8000)
    provenance_declaration: Optional[str] = Field(None, max_length=4000)
    acceptance_criteria_met: Optional[bool] = None

    requested_level: Optional[str] = Field(
        None, description="Only 'E3' is grantable in this milestone.")


class MeasurementRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_name: str = Field(..., min_length=1, max_length=160)
    sample_group: Optional[str] = Field(None, max_length=160)
    replicate_id: Optional[str] = Field(None, max_length=60)
    time_point: Optional[str] = Field(None, max_length=60)
    dose_value: Optional[float] = None
    dose_unit: Optional[str] = Field(None, max_length=40)

    result_numeric: Optional[float] = None
    result_text: Optional[str] = Field(None, max_length=300)
    result_unit: Optional[str] = Field(None, max_length=40)

    detection_limit: Optional[float] = None
    quantification_limit: Optional[float] = None
    method: Optional[str] = Field(None, max_length=200)
    source_file_reference: Optional[str] = Field(None, max_length=300)
    missing_value_reason: Optional[str] = Field(None, max_length=300)

    excluded: bool = False
    exclusion_justification: Optional[str] = Field(None, max_length=2000)

    #: Derived values are stored beside their method, never in place of the
    #: value as entered.
    normalized_value: Optional[float] = None
    normalization_method: Optional[str] = Field(None, max_length=200)


class MeasurementBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: List[MeasurementRow] = Field(..., min_length=1, max_length=2000)


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(..., description="approve | reject | request_revision")
    #: Required. A decision without a stated reason cannot be reviewed by
    #: anybody else, which is what makes the trail worth keeping.
    comments: str = Field(..., min_length=1, max_length=8000)


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Re-link to a different candidate version when the material changed.
    candidate_version_id: Optional[int] = None


class ContradictionResolutionRequest(BaseModel):
    """A reviewer's reading of conflicting approved evidence.

    ``resolved_level`` is optional and may only be "E3" or omitted. Omitted
    means the reviewer examined the conflict and decided the purpose stays
    held — a legitimate and common outcome, and the default.
    """

    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(..., description="A ReadinessArea value.")
    #: Required. A resolution without a stated reason cannot be weighed by
    #: anybody else.
    rationale: str = Field(..., min_length=1, max_length=8000)
    resolved_level: Optional[str] = Field(
        None, description="'E3' to settle, or omitted to keep it held.")
    candidate_version_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Candidate revision and supersession
# ---------------------------------------------------------------------------

class CandidateRevisionRequest(BaseModel):
    """Create a new immutable version derived from an existing one."""

    model_config = ConfigDict(extra="forbid")

    #: The formulation for the new version. Omitted means "copy the
    #: predecessor's inputs unchanged", which is the right default for a
    #: revision whose purpose is to attach new work rather than to change the
    #: material.
    design_inputs: Optional[Dict[str, Any]] = None

    #: Required, and deliberately not defaulted. It is the only part of the
    #: record that explains why the formulation changed, and it is read by
    #: people who were not there.
    reason: str = Field(min_length=3, max_length=2000)

    #: Whether to copy the predecessor's derived results. They are marked
    #: STALE either way — this only decides whether the reader sees the
    #: previous numbers as a starting point or an empty slate.
    carry_results: bool = True

    #: Supplied by the client so a retried submission returns the version the
    #: first call created rather than forking the lineage.
    idempotency_key: Optional[str] = Field(None, max_length=128)


class SupersessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: The version taking over.
    successor_version_id: int

    reason: str = Field(min_length=3, max_length=2000)

    #: The review or approval decision authorising this, when one exists.
    decision_id: Optional[int] = None

    #: The revision the caller last read. A conditional update on it is what
    #: makes two simultaneous supersessions resolve to one rather than the
    #: second silently overwriting the first.
    expected_revision: Optional[int] = None


class VersionWithdrawRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)


class SupersessionProposalRequest(BaseModel):
    """Ask for a successor to take over. Does not itself take over.

    Separate from ``SupersessionRequest`` because the two require different
    authority: an author may propose that their revision replaces the approved
    version, and only somebody who could have approved it may agree.
    """

    model_config = ConfigDict(extra="forbid")

    successor_version_id: int
    reason: str = Field(min_length=3, max_length=2000)


class SupersessionRefusalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)


# ---------------------------------------------------------------------------
# Records that depend on an exact candidate version
# ---------------------------------------------------------------------------
#
# Every request below is addressed to a version, never to a candidate. That is
# deliberate and it is the whole contract: an endpoint that took a candidate id
# and worked out which version it meant would produce an artefact whose subject
# depends on when it ran.


class SimulationRecordRequest(BaseModel):
    """Persist a simulation result against the version it was computed from."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(..., description="pharmacokinetic | design_score | readiness")
    engine_version: str = Field(..., min_length=1, max_length=64)
    inputs: Dict[str, Any]

    #: Omitted for a run that produced nothing. A failure is stored with its
    #: reason rather than discarded, because "nobody tried" and "the engine
    #: refused" lead to different decisions.
    result: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = Field(None, max_length=300)
    ruleset_version: Optional[str] = Field(None, max_length=64)


class EvidenceAssessmentRequest(BaseModel):
    """File how evidence for one purpose stands, for one exact version."""

    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(..., description="A ReadinessArea value.")

    #: Omitted means "no level held", which is distinct from E1: an area
    #: nobody has assessed and an area assessed as weak are different findings.
    level: Optional[str] = Field(None, description="An EvidenceLevel value.")

    #: Required, with no default. Evidence carried forward from a predecessor
    #: without being classified has been re-attested on nobody's authority.
    reuse: str = Field(
        ...,
        description=("retained_reference | reassessment_required | "
                     "newly_validated"))

    rationale: str = Field(..., min_length=1, max_length=8000)

    #: Required when reuse is retained_reference: the version the work was
    #: actually performed on.
    source_candidate_version_id: Optional[int] = None

    considered_experiment_version_ids: Optional[List[int]] = None


class ReportGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=300)
    body: Dict[str, Any] = Field(default_factory=dict)
    format: str = Field("json", description="json | markdown | csv")


class ExportGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str = Field("json", description="json | markdown | csv")
    purpose_note: Optional[str] = Field(None, max_length=300)
    payload: Optional[Dict[str, Any]] = None


class CROPackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_name: str = Field(..., min_length=1, max_length=200)
    package_code: str = Field(..., min_length=1, max_length=64)
    quotation_reference: Optional[str] = Field(None, max_length=120)
    scope_note: Optional[str] = Field(None, max_length=2000)


class ComparisonRecordRequest(BaseModel):
    """File a comparison as a formal record, locking both sides.

    Browsing a comparison is a question and locks nothing. Filing one says
    "this is the basis of what happens next", which is an act.
    """

    model_config = ConfigDict(extra="forbid")

    other_version_id: int
    note: Optional[str] = Field(None, max_length=2000)


class RecalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(None, max_length=2000)
