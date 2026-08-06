"""Persistence for the Experimental Validation Registry.

Hierarchy
---------
    workspace_projects
      └─ workspace_runs                    (Study)
          └─ validation_candidates         (a named formulation)
              └─ validation_candidate_versions   (immutable snapshot)
                  └─ validation_experiments
                      └─ validation_experiment_versions
                          ├─ validation_measurements
                          └─ validation_attachments

Two invariants the schema is shaped around
------------------------------------------
1. **An experiment version points at an exact candidate version, and that
   snapshot is immutable.** Without this, editing a formulation after the
   experiment would silently re-attribute the result to a material that was
   never tested. The snapshot is stored as JSON with a checksum so the link is
   verifiable rather than merely asserted.

2. **Approval freezes a version; correction creates a new one.** No approved
   row is ever updated in place, and nothing is destructively deleted. The
   audit table is append-only and deliberately holds no foreign key to its
   subject, so it outlives what it describes — the same choice
   ``report_models.ReportAuditLog`` makes, for the same reason.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Enum, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nanobio_studio.app.db.base import Base

# Registers the ``organizations`` table in the shared metadata. Needed because
# the ``organization_id`` foreign key below resolves by table name, and a test
# that imports only this module would otherwise fail at mapper configuration
# with "could not find table 'organizations'".
from nanobio_studio.app.db import organization_models  # noqa: F401,E402
from nanobio_studio.app.science.statuses import EvidenceLevel, ReadinessArea
from nanobio_studio.app.validation.vocabulary import (
    AttachmentCategory, AuditEvent, ExperimentStatus, ExperimentSubtype,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Candidate and its versions
# ---------------------------------------------------------------------------

class VersionStatus(str, enum.Enum):
    """Where a candidate version stands, scientifically.

    Five states, and the distinctions between them are the ones people
    actually confuse. "Latest" is not on this list on purpose: it is ambiguous
    between the newest draft and the one currently approved, and a screen that
    says it has told the reader nothing.

    A version leaves DRAFT once anything depends on it, and never returns.
    Nothing here is a soft delete: WITHDRAWN and SUPERSEDED both keep the row,
    its snapshot, and every record that referenced it.
    """

    #: Editable in place. No dependent scientific record exists yet.
    DRAFT = "draft"

    #: Something depends on it — a simulation, review, report, export or
    #: package. Scientific inputs are locked; changes need a revision.
    LOCKED = "locked"

    #: Carried a formal approval decision. Still locked; still citable.
    APPROVED = "approved"

    #: A later version has formally taken over. The record stays readable and
    #: every decision made on it stays true — supersession is about what to use
    #: NEXT, not about erasing what happened.
    SUPERSEDED = "superseded"

    #: Retired without a successor: withdrawn by its author, or rejected at
    #: review. Distinct from superseded, because "we replaced this" and "we
    #: stopped standing behind this" are different claims to a regulator.
    WITHDRAWN = "withdrawn"


#: States in which the scientific inputs may still be edited in place.
EDITABLE_VERSION_STATES = frozenset({VersionStatus.DRAFT})

#: States that can be superseded by a successor. A draft cannot: nothing has
#: relied on it, so it should be edited or discarded rather than replaced.
SUPERSEDABLE_VERSION_STATES = frozenset({
    VersionStatus.LOCKED, VersionStatus.APPROVED,
})

#: States a version may be revised FROM. Includes withdrawn and superseded
#: deliberately: revising a withdrawn version to correct what was wrong with it
#: is the normal recovery, and blocking it would push people to start again
#: with no lineage.
REVISABLE_VERSION_STATES = frozenset({
    VersionStatus.DRAFT, VersionStatus.LOCKED, VersionStatus.APPROVED,
    VersionStatus.SUPERSEDED, VersionStatus.WITHDRAWN,
})


class ResultsState(str, enum.Enum):
    """Whether the derived numbers on a version can still be believed.

    The state that matters is STALE. A revision copies its predecessor's
    scores so the reader can see what they were, and those numbers were
    computed for a *different* formulation — presenting them without a mark
    would be the single most misleading thing this feature could do.
    """

    #: Never calculated.
    NONE = "none"

    #: Computed for THIS version's inputs, under the recorded model versions.
    CURRENT = "current"

    #: Inherited from a predecessor, or invalidated by an input change. Must
    #: be shown as stale everywhere it appears, and recalculated before use.
    STALE = "stale"

    #: Recalculation asked for and not yet finished.
    RECALCULATING = "recalculating"


class SupersessionState(str, enum.Enum):
    """Supersession is a decision, so it has a lifecycle of its own.

    Proposing is not doing. Separating them is what lets supersession require
    an authority the proposer may not hold, which is the whole point of
    routing it through review rather than making it a side effect of creating
    a revision.
    """

    NONE = "none"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REFUSED = "refused"


class Candidate(Base):
    """A named formulation under a study.

    Introduced because Phase 1 had no such entity: a formulation lived inside
    ``workspace_runs.design_inputs_json``, which meant a study and a candidate
    were the same object. An experiment has to attach to *the material that was
    tested*, and one study routinely examines several.
    """

    __tablename__ = "validation_candidates"
    __table_args__ = (
        UniqueConstraint("study_id", "code", name="uq_candidate_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Owning organization. Denormalised onto every record rather than derived
    #: through the study, so the boundary can be a single indexed predicate in
    #: the same WHERE clause that finds the row. See
    #: ``db/organization_models.py`` for why.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    study_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_runs.id", ondelete="CASCADE"),
        nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_projects.id", ondelete="SET NULL"),
        nullable=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False, index=True)

    #: Human-readable, unique within the study. Shown wherever a candidate is
    #: referenced, so a reader never has to resolve an integer id by hand.
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
        onupdate=utcnow)

    versions: Mapped[list["CandidateVersion"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan")


class CandidateVersion(Base):
    """An immutable snapshot of a candidate's scientifically relevant attributes.

    ``design_snapshot_json`` is a verbatim copy taken at creation, never a
    reference. That is the whole point: a reference would follow later edits,
    and an experimental result would end up describing a material that no
    longer exists.

    ``snapshot_checksum`` is a SHA-256 over the canonical JSON. It makes the
    linkage checkable — an eligibility gate can confirm the snapshot is the one
    that was approved against, rather than trusting a foreign key.
    """

    __tablename__ = "validation_candidate_versions"
    __table_args__ = (
        UniqueConstraint("candidate_id", "version_number",
                         name="uq_candidate_version"),

        # ---- lineage integrity, in the database ---------------------------
        #
        # These are constraints rather than service-layer checks because they
        # have to hold for every writer that will ever exist — including a
        # migration, a repair script run at 2am, and whatever imports data
        # next year. Application code can only promise for the paths that go
        # through it.
        #
        # A version that is its own predecessor. Trivially wrong, and it makes
        # any lineage walk non-terminating.
        CheckConstraint("predecessor_version_id IS NULL "
                        "OR predecessor_version_id <> id",
                        name="ck_candidate_version_not_own_predecessor"),

        # Likewise for supersession, in both directions.
        CheckConstraint("superseded_by_version_id IS NULL "
                        "OR superseded_by_version_id <> id",
                        name="ck_candidate_version_not_own_successor"),

        # A revision number must be positive and ordered after its
        # predecessor's; enforced in the service, but the floor is here so no
        # writer can produce a zeroth or negative revision.
        CheckConstraint("version_number >= 1",
                        name="ck_candidate_version_number_positive"),

        # Supersession timestamps and targets travel together. A row claiming
        # SUPERSEDED with no successor, or a successor with no timestamp, is a
        # half-written decision — and a half-written decision about which
        # version to use is worse than none.
        CheckConstraint(
            "(status <> 'SUPERSEDED') OR "
            "(superseded_by_version_id IS NOT NULL AND superseded_at IS NOT NULL)",
            name="ck_candidate_version_supersession_complete"),

        # A locked, approved or superseded version must record WHY it left
        # draft. Without it the lock is unexplainable to the next reader.
        CheckConstraint(
            "(status = 'DRAFT') OR (locked_at IS NOT NULL)",
            name="ck_candidate_version_locked_has_timestamp"),

        # Walking a lineage is a common read; index the link.
        Index("ix_candidate_version_predecessor", "predecessor_version_id"),
        Index("ix_candidate_version_status", "candidate_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Owning organization. Denormalised onto every record rather than derived
    #: through the study, so the boundary can be a single indexed predicate in
    #: the same WHERE clause that finds the row. See
    #: ``db/organization_models.py`` for why.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidates.id", ondelete="CASCADE"),
        nullable=False, index=True)

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    #: The formulation as it stood. Canonical JSON, sorted keys.
    design_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_checksum: Mapped[str] = mapped_column(String(64), nullable=False,
                                                    index=True)

    #: Why this version exists. Free text, shown in the version history.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)

    # ---- lineage ---------------------------------------------------------

    #: The version this one was derived from. NULL only for the first version
    #: of a candidate, which is what makes a lineage walkable to its root.
    #:
    #: `ondelete="RESTRICT"`: a predecessor cannot be deleted while anything
    #: descends from it. Losing the middle of a lineage would leave a revision
    #: claiming a derivation nobody can inspect.
    predecessor_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=True)

    #: Why this version exists, in the author's words. Required for every
    #: revision — see `note`, which stays optional for the first version
    #: because "it is the first one" is not a reason worth typing.
    revision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Human-readable revision label, e.g. "v3". Derived from
    #: `version_number` and stored so it can be cited verbatim in a report
    #: that must still read correctly if the numbering scheme ever changes.
    revision_label: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ---- workflow --------------------------------------------------------

    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=16),
        nullable=False, default=VersionStatus.DRAFT, index=True)

    #: When and why the scientific inputs stopped being editable.
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    lock_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ---- derived results -------------------------------------------------

    results_state: Mapped[ResultsState] = mapped_column(
        Enum(ResultsState, native_enum=False, length=16),
        nullable=False, default=ResultsState.NONE, index=True)

    #: Set when results were inherited from a predecessor, so the interface
    #: can say *whose* numbers these were rather than only that they are old.
    results_inherited_from_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("validation_candidate_versions.id", ondelete="SET NULL"),
        nullable=True)

    # ---- provenance ------------------------------------------------------
    #
    # Without these a score can be re-run but not reproduced: re-running gives
    # today's answer under today's rules, which is a different number wearing
    # the same name. A regulated record needs to say which rules produced it.

    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ruleset_version: Mapped[str | None] = mapped_column(String(64),
                                                        nullable=True)
    reference_data_version: Mapped[str | None] = mapped_column(String(64),
                                                               nullable=True)
    algorithm_selection: Mapped[str | None] = mapped_column(String(120),
                                                            nullable=True)

    # ---- supersession ----------------------------------------------------

    supersession_state: Mapped[SupersessionState] = mapped_column(
        Enum(SupersessionState, native_enum=False, length=16),
        nullable=False, default=SupersessionState.NONE)

    #: The version that took over from this one.
    superseded_by_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    superseded_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True)
    supersession_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: The review or approval decision that authorised the supersession, when
    #: one exists. Supersession without a recorded decision is possible only
    #: for a version that never carried an approval.
    supersession_decision_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True)

    #: Optimistic-concurrency guard, matching the pattern used for
    #: memberships and assignments: a conditional UPDATE on this column is
    #: what makes two simultaneous supersessions resolve to one.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    candidate: Mapped[Candidate] = relationship(back_populates="versions")

    predecessor: Mapped["CandidateVersion | None"] = relationship(
        remote_side="CandidateVersion.id",
        foreign_keys="CandidateVersion.predecessor_version_id",
        backref="successors")

    def is_editable(self) -> bool:
        """Whether the scientific inputs may still be changed in place."""
        return self.status in EDITABLE_VERSION_STATES

    def effective_label(self) -> str:
        return self.revision_label or f"v{self.version_number}"


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------

class ValidationExperiment(Base):
    """The stable identity of an experiment, across all its versions.

    Holds only what cannot change between versions: which candidate it is
    about, what kind of assay it is, and which purpose it claims. Everything
    that a correction might alter lives on the version.
    """

    __tablename__ = "validation_experiments"
    __table_args__ = (
        UniqueConstraint("code", name="uq_experiment_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Owning organization. Denormalised onto every record rather than derived
    #: through the study, so the boundary can be a single indexed predicate in
    #: the same WHERE clause that finds the row. See
    #: ``db/organization_models.py`` for why.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )

    #: Human-readable, globally unique, e.g. "EXP-2026-0007".
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidates.id", ondelete="CASCADE"),
        nullable=False, index=True)
    study_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_runs.id", ondelete="CASCADE"),
        nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_projects.id", ondelete="SET NULL"),
        nullable=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False, index=True)

    subtype: Mapped[ExperimentSubtype] = mapped_column(
        Enum(ExperimentSubtype, native_enum=False, length=40),
        nullable=False, index=True)

    #: The single readiness area this experiment is evidence for. Fixed at
    #: creation: an experiment designed to answer one question must not be
    #: re-aimed at another after the results are in.
    purpose: Mapped[ReadinessArea] = mapped_column(
        Enum(ReadinessArea, native_enum=False, length=40),
        nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
        onupdate=utcnow)

    versions: Mapped[list["ExperimentVersion"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan",
        order_by="ExperimentVersion.version_number")


class ExperimentVersion(Base):
    """One revision of an experiment record. Frozen on submission.

    Conditional fields are nullable at the column level and required by the
    *validator* only where scientifically applicable — a passage number for a
    cell-free zeta-potential measurement is not missing data, it is a field
    that does not apply, and a NOT NULL constraint would force somebody to
    invent one.
    """

    __tablename__ = "validation_experiment_versions"
    __table_args__ = (
        UniqueConstraint("experiment_id", "version_number",
                         name="uq_experiment_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Owning organization. Denormalised onto every record rather than derived
    #: through the study, so the boundary can be a single indexed predicate in
    #: the same WHERE clause that finds the row. See
    #: ``db/organization_models.py`` for why.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("validation_experiments.id", ondelete="CASCADE"),
        nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    #: THE linkage that makes a result attributable. Not nullable.
    candidate_version_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=False, index=True)

    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus, native_enum=False, length=24),
        nullable=False, default=ExperimentStatus.DRAFT, index=True)

    # --- scientific framing ------------------------------------------------
    scientific_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- provenance --------------------------------------------------------
    laboratory_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    investigator_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    investigator_org: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    protocol_identifier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    protocol_version: Mapped[str | None] = mapped_column(String(40), nullable=True)

    nanoparticle_batch: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload_batch: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # --- biological system (conditional on subtype) ------------------------
    biological_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cell_line: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cell_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cell_authentication_status: Mapped[str | None] = mapped_column(String(120),
                                                                    nullable=True)
    passage_number: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # --- method ------------------------------------------------------------
    assay_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: JSON list of endpoint names.
    endpoints_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    measurement_units: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # --- controls ----------------------------------------------------------
    control_positive: Mapped[str | None] = mapped_column(Text, nullable=True)
    control_negative: Mapped[str | None] = mapped_column(Text, nullable=True)
    control_vehicle: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Set when a control genuinely does not apply, with the reason. Distinct
    #: from a blank control, which is a missing control.
    controls_not_applicable_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True)

    # --- replication -------------------------------------------------------
    #: Always required to be *reported*. No universal minimum is imposed: the
    #: defensible count differs by assay, so the gate checks disclosure and the
    #: reviewer judges sufficiency.
    biological_replicates: Mapped[int | None] = mapped_column(Integer, nullable=True)
    technical_replicates: Mapped[int | None] = mapped_column(Integer, nullable=True)
    replicate_justification: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- acceptance criteria ----------------------------------------------
    #: JSON list of {endpoint, comparator, value, unit, description}.
    acceptance_criteria_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: When the criteria were recorded. Compared against the first measurement
    #: timestamp to check they were predefined rather than fitted to the data.
    acceptance_criteria_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    # --- results -----------------------------------------------------------
    raw_data_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_results_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    statistical_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    statistical_method_not_applicable_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True)

    deviations: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclusions: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Explicit "nothing to disclose" acknowledgement. A blank deviations field
    #: is ambiguous between "none" and "not considered"; this resolves it.
    disclosures_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False)

    investigator_conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: JSON list of {severity, description, resolved, resolution}.
    quality_issues_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_declaration: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Whether the investigator asserts the predefined criteria were met.
    #: Checked independently against the measurements by the evaluator; this is
    #: the claim, not the finding.
    acceptance_criteria_met: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True)

    # --- evidence decision -------------------------------------------------
    requested_level: Mapped[EvidenceLevel | None] = mapped_column(
        Enum(EvidenceLevel, native_enum=False, length=8), nullable=True)
    approved_level: Mapped[EvidenceLevel | None] = mapped_column(
        Enum(EvidenceLevel, native_enum=False, length=8), nullable=True,
        index=True)

    # --- workflow ----------------------------------------------------------
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    submitted_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)

    review_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)

    decision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    decision_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    decision_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Who actually performed the work. Compared against the approver to bar
    #: self-approval, and recorded separately from ``owner_id`` because the
    #: person who files a record is not always the person who ran the assay.
    performed_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True,
        index=True)

    superseded_by_version_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True)

    #: Set when the version is frozen. Non-null means no further edits.
    frozen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    #: The evaluator's verdict, stored verbatim at decision time together with
    #: its ruleset version. Never recomputed for display: a historical approval
    #: must say what was concluded then, not what today's rules would say.
    eligibility_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    eligibility_ruleset_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
        onupdate=utcnow)

    experiment: Mapped[ValidationExperiment] = relationship(
        back_populates="versions")
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="version", cascade="all, delete-orphan")
    attachments: Mapped[list["ExperimentAttachment"]] = relationship(
        back_populates="version", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------

class Measurement(Base):
    """One structured observation.

    Stored per replicate, per time point, per group — not as a narrative
    summary. A conclusion is an interpretation; the measurements are what it
    was interpreted from, and an evaluator that can only read prose cannot
    check whether the acceptance criteria were met.

    The value as entered is preserved. Any normalisation is stored in separate
    columns beside its method, so the original is never overwritten by a
    derived number.
    """

    __tablename__ = "validation_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Owning organization. Denormalised onto every record rather than derived
    #: through the study, so the boundary can be a single indexed predicate in
    #: the same WHERE clause that finds the row. See
    #: ``db/organization_models.py`` for why.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("validation_experiment_versions.id", ondelete="CASCADE"),
        nullable=False, index=True)

    endpoint_name: Mapped[str] = mapped_column(String(160), nullable=False,
                                                index=True)
    sample_group: Mapped[str | None] = mapped_column(String(160), nullable=True)
    replicate_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    time_point: Mapped[str | None] = mapped_column(String(60), nullable=True)

    dose_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    dose_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)

    #: Exactly one of these carries the result. A categorical outcome
    #: ("no haemolysis observed") is a legitimate result and must not be
    #: coerced into a number.
    result_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    result_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)

    detection_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantification_limit: Mapped[float | None] = mapped_column(Float, nullable=True)

    method: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_file_reference: Mapped[str | None] = mapped_column(String(300),
                                                               nullable=True)

    #: Set instead of a result. Distinguishes "not measured" from "measured as
    #: zero", which are different findings.
    missing_value_reason: Mapped[str | None] = mapped_column(String(300),
                                                              nullable=True)

    excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exclusion_justification: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Derived values live here, never in `result_numeric`.
    normalized_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalization_method: Mapped[str | None] = mapped_column(String(200),
                                                              nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)

    version: Mapped[ExperimentVersion] = relationship(
        back_populates="measurements")


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------

class AttachmentState(str, enum.Enum):
    """Where an attachment is between "a user pressed upload" and "it is gone".

    The database and the object store are two systems that can disagree. A
    single boolean cannot say *how* they disagree, and the difference matters:
    an attachment whose bytes are in the bucket but whose row never finalised
    needs cleaning up, while one whose row exists and whose bytes are missing
    needs investigating. So each is its own state, with its own remedy.

    Transitions are one-way except ``PENDING_SCAN`` → ``AVAILABLE`` or
    ``QUARANTINED``, which is the point of having a scan state at all.
    """

    #: A row exists to claim an id and a key; the object is not there yet.
    #: Never downloadable, never listed as evidence.
    PENDING_UPLOAD = "pending_upload"

    #: Bytes stored, checksum verified, row finalised. The only servable state.
    AVAILABLE = "available"

    #: Stored and awaiting a malware verdict. Reachable only when a scanner is
    #: actually connected — the state exists now so that connecting one later
    #: is a configuration change rather than a redesign of this table.
    PENDING_SCAN = "pending_scan"

    #: A scanner rejected it. The object is retained for investigation and is
    #: never served.
    QUARANTINED = "quarantined"

    #: Deletion was requested and the object is still there. A retryable
    #: tombstone: the alternative is telling a user their file is gone while
    #: the bytes remain in a bucket.
    DELETE_PENDING = "delete_pending"

    #: Object removed and confirmed absent. The row survives so the audit
    #: history and the scientific provenance survive with it.
    DELETED = "deleted"

    #: The row says the object should exist and the store says it does not.
    #: Set by reconciliation. Distinct from DELETED because nobody asked for
    #: this, and it is a finding rather than an outcome.
    MISSING = "missing"


#: States in which an attachment may be served to a caller.
DOWNLOADABLE_ATTACHMENT_STATES = frozenset({AttachmentState.AVAILABLE})

#: States that are neither finished nor failed. Reconciliation reports one
#: stuck here for longer than an upload could plausibly take.
TRANSITIONAL_ATTACHMENT_STATES = frozenset({
    AttachmentState.PENDING_UPLOAD,
    AttachmentState.PENDING_SCAN,
    AttachmentState.DELETE_PENDING,
})


class ExperimentAttachment(Base):
    """Metadata for a stored file. The bytes live behind the storage adapter.

    No filesystem path is stored. ``storage_key`` is an opaque token the
    adapter resolves; exposing a path would leak the server's layout and invite
    traversal.
    """

    __tablename__ = "validation_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Owning organization. Denormalised onto every record rather than derived
    #: through the study, so the boundary can be a single indexed predicate in
    #: the same WHERE clause that finds the row. See
    #: ``db/organization_models.py`` for why.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("validation_experiment_versions.id", ondelete="CASCADE"),
        nullable=False, index=True)

    #: The exact candidate version the attached work was performed against.
    #:
    #: Reachable through ``version_id`` already, and denormalised anyway for
    #: the same reason ``organization_id`` is: "which formulation is this file
    #: evidence for?" should be one indexed predicate, not a two-table join
    #: that a listing query can forget to make. Nullable only because rows
    #: written before this column existed have to stay valid until the legacy
    #: migration binds them; every new write sets it.
    candidate_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=True, index=True)

    category: Mapped[AttachmentCategory] = mapped_column(
        Enum(AttachmentCategory, native_enum=False, length=32),
        nullable=False, index=True)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False,
                                                  index=True)

    #: Opaque handle for the object store. Never a path, never a filename.
    #: See ``app/storage/keys.py`` for what a key may and may not contain.
    storage_key: Mapped[str] = mapped_column(String(200), nullable=False)

    #: Which driver wrote it, and into which container.
    #:
    #: Recorded rather than assumed, because a deployment migrates from local
    #: to object storage while rows written under the old driver still exist.
    #: Reconciliation needs to know where to look for each object, and "look in
    #: whatever the current driver is" would report every unmigrated row as an
    #: orphan.
    storage_backend: Mapped[str | None] = mapped_column(
        String(32), nullable=True)
    storage_bucket: Mapped[str | None] = mapped_column(
        String(120), nullable=True)

    #: Where this attachment is in its lifecycle. See ``AttachmentState``.
    #:
    #: The whole reason this column exists: the database and the object store
    #: are two systems, and a write can succeed in one and fail in the other.
    #: A single boolean "uploaded" cannot express "the bytes are there but the
    #: row never finished", which is the state that produces an attachment
    #: nobody can download and nobody can find to clean up.
    state: Mapped["AttachmentState"] = mapped_column(
        Enum(AttachmentState, native_enum=False, length=24),
        nullable=False, default=AttachmentState.AVAILABLE,
        server_default="AVAILABLE", index=True)
    state_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    #: How many times deletion of the object has been attempted.
    #:
    #: A failed delete leaves the row in ``DELETE_PENDING`` as a retryable
    #: tombstone rather than reporting success. Telling a user their file is
    #: gone while the bytes remain in a bucket is the one deletion outcome that
    #: must never happen quietly.
    delete_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0")

    #: Short code from the last storage failure. Never a provider message.
    last_error_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True)

    #: Set when the binary content is disposed of under a retention rule while
    #: the metadata, audit history and scientific provenance are kept. An
    #: experiment performed against a file is still an experiment that was
    #: performed; losing the bytes must not lose the record of them.
    content_removed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)

    version: Mapped[ExperimentVersion] = relationship(
        back_populates="attachments")

    @property
    def is_downloadable(self) -> bool:
        """Whether the bytes may be served.

        Only ``AVAILABLE``. An attachment that is still uploading, awaiting a
        scan, quarantined, being deleted or missing is not servable, and each
        of those is a different sentence to show the user — which is why they
        are five states rather than one flag.
        """
        return self.state is AttachmentState.AVAILABLE


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class ContradictionResolution(Base):
    """A reviewer's recorded decision about conflicting approved evidence.

    Exists as its own row rather than a flag on an experiment because a
    contradiction is a property of a *purpose on a candidate version*, not of
    any one record — and because resolving it must not touch the conflicting
    experiments at all. Every one of them keeps its decision, its comments and
    its measurements exactly as they were; this table records only how the
    conflict was read.

    Append-only in practice: a later reading supersedes an earlier one by
    ``superseded_by_id`` rather than overwriting it, so the history of how a
    disagreement was understood is preserved alongside the disagreement.
    """

    __tablename__ = "validation_contradiction_resolutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Owning organization. Denormalised onto every record rather than derived
    #: through the study, so the boundary can be a single indexed predicate in
    #: the same WHERE clause that finds the row. See
    #: ``db/organization_models.py`` for why.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )

    study_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_runs.id", ondelete="CASCADE"),
        nullable=False, index=True)
    #: The readiness area the conflict concerns. A resolution is per purpose:
    #: settling safety says nothing about targeting.
    purpose: Mapped[ReadinessArea] = mapped_column(
        Enum(ReadinessArea, native_enum=False, length=40),
        nullable=False, index=True)
    candidate_version_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True)

    #: What the reviewer concluded. Free text and required: a resolution
    #: without a stated rationale is an assertion, not a review.
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    #: The level the purpose should hold given the conflict. Null means the
    #: reviewer decided it stays held — a legitimate outcome, and the default
    #: until somebody says otherwise.
    resolved_level: Mapped[EvidenceLevel | None] = mapped_column(
        Enum(EvidenceLevel, native_enum=False, length=8), nullable=True)

    #: Versions the resolution was made in the knowledge of. Recorded so a
    #: later, additional conflicting record does not silently fall under an
    #: earlier resolution.
    considered_version_ids: Mapped[str] = mapped_column(Text, nullable=False,
                                                         default="")

    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    superseded_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ValidationAuditLog(Base):
    """Append-only trail for the registry.

    No foreign key to the experiment: the trail must outlive its subject, which
    is the entire point of auditing a supersession. Nothing in the application
    updates or deletes a row here.
    """

    __tablename__ = "validation_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Owning organization. Denormalised onto every record rather than derived
    #: through the study, so the boundary can be a single indexed predicate in
    #: the same WHERE clause that finds the row. See
    #: ``db/organization_models.py`` for why.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )

    event: Mapped[AuditEvent] = mapped_column(
        Enum(AuditEvent, native_enum=False, length=32), nullable=False,
        index=True)

    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True,
        index=True)

    experiment_id: Mapped[int | None] = mapped_column(Integer, nullable=True,
                                                       index=True)
    experiment_version_id: Mapped[int | None] = mapped_column(Integer,
                                                               nullable=True,
                                                               index=True)
    candidate_version_id: Mapped[int | None] = mapped_column(Integer,
                                                              nullable=True,
                                                              index=True)

    #: The candidate the event concerns, alongside the exact version.
    #:
    #: Both, not one. The version id alone answers "what was relied upon" but
    #: cannot be grouped into a candidate's history without a join to a table
    #: this trail deliberately has no foreign key into — and the trail has to
    #: stay readable after its subject is gone, which is the whole reason
    #: there is no foreign key.
    candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True,
                                                      index=True)

    #: Why the actor did it, in their words, truncated. Separate from
    #: ``summary`` because a reason is something a person supplied and a
    #: summary is something the application composed; mixing them makes it
    #: impossible to tell an explanation from a description.
    #:
    #: **Redacted before storage.** See ``services/audit_redaction.py``: no
    #: patient data, no document content, no measurement values.
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    #: Non-sensitive context: a status transition, a gate name, a file
    #: category. Never a measurement value or a filename's full path.
    summary: Mapped[str | None] = mapped_column(String(600), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True)


Index("ix_validation_exp_candidate_purpose",
      ValidationExperiment.candidate_id, ValidationExperiment.purpose)
Index("ix_validation_version_status",
      ExperimentVersion.experiment_id, ExperimentVersion.status)
Index("ix_validation_audit_experiment_created",
      ValidationAuditLog.experiment_id, ValidationAuditLog.created_at)


# Registers the tables that depend on a candidate version — simulations,
# evidence assessments, reports, exports, CRO packages and filed comparisons.
#
# At the BOTTOM, and importing this module rather than any name from it,
# because the dependency is genuinely mutual: those models declare NOT NULL
# foreign keys onto `validation_candidate_versions`, and this module needs them
# on the shared metadata so that anything which builds the schema from
# `Base.metadata` gets the whole registry rather than the half that happened to
# be imported. Placing it here means the classes above are fully defined before
# the other module resolves its foreign keys, whichever of the two is imported
# first.
#
# Without it, `Base.metadata.create_all` produced a database in which a report
# could not be stored, and the failure appeared as a missing table in a test
# that had imported only this file.
from nanobio_studio.app.db import candidate_dependency_models  # noqa: F401,E402
