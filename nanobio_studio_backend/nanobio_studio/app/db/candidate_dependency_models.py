"""Records that depend on an exact candidate version.

The single rule these tables exist to make structural
-----------------------------------------------------
**Every scientific record that relies on a formulation names the exact version
it relied on, and cannot be written without one.** ``candidate_version_id`` is
``NOT NULL`` on every table here and carries ``ondelete="RESTRICT"``, so there
is no way to store a simulation, report, export or package that points at "the
candidate" and leaves which revision it described to be worked out later.

Why that is worth six tables
----------------------------
The failure this prevents is specific. A report generated against v1, listed
under a candidate that has since moved to v3, reads as a report about v3 — the
numbers look current, the formulation looks current, and nothing on the page
says otherwise. A nullable or absent version link is what makes that possible;
a required one makes it impossible to express.

They are separate tables rather than one row-kind-discriminated table because
the payloads genuinely differ. A simulation carries inputs, a result and a
staleness state. A report carries frozen rendered content. An export carries a
manifest and a checksum. A comparison carries *two* version ids, which a
single ``candidate_version_id`` column cannot express at all. Collapsing them
would mean a wide table of mostly-NULL columns whose meaning depends on a
discriminator — which is the shape that lets a writer populate the wrong ones.

What is deliberately frozen
---------------------------
``content_json`` on a report, and ``manifest_json`` on an export or package,
are verbatim copies taken at generation time. They are never re-rendered for
display. A historical report must say what was concluded *then*, under the
inputs and rules of *then*; regenerating it from today's data would answer a
different question while looking like the original.

Retention
---------
Nothing here is deleted by the application. A superseded version keeps every
dependent record that ever pointed at it, because superseding says which
version to use next — it does not unsay what was done with the old one.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from nanobio_studio.app.db.base import Base

# Registers the ``organizations`` and candidate tables in the shared metadata.
# The foreign keys below resolve by table name, and a test that imported only
# this module would otherwise fail at mapper configuration.
from nanobio_studio.app.db import organization_models  # noqa: F401,E402
from nanobio_studio.app.db import validation_models  # noqa: F401,E402
from nanobio_studio.app.science.statuses import EvidenceLevel, ReadinessArea
from nanobio_studio.app.validation.vocabulary import (
    EvidenceReuse, GeneratedArtifactFormat, SimulationKind,
)

__all__ = [
    "DependentResultState",
    "CandidateSimulation",
    "CandidateEvidenceAssessment",
    "CandidateReport",
    "CandidateExport",
    "CandidateCROPackage",
    "CandidateVersionComparison",
    "DEPENDENT_TABLES",
    "VERSION_COLUMN",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


#: The column every table here shares, named once so the migration, the
#: consistency check and the tests can all refer to the same string.
VERSION_COLUMN = "candidate_version_id"

#: Every dependent table, with the table it hangs off. Read by the legacy
#: migration and by the schema tests, so the set cannot drift from the models.
DEPENDENT_TABLES: tuple[str, ...] = (
    "validation_candidate_simulations",
    "validation_candidate_evidence_assessments",
    "validation_candidate_reports",
    "validation_candidate_exports",
    "validation_cro_packages",
    "validation_version_comparisons",
)


class DependentResultState(str, enum.Enum):
    """Whether a stored derived result still describes its version.

    ``COPIED_STALE`` is the member that earns this enum. A revision may carry
    its predecessor's numbers forward so a reader can see the starting point,
    and those numbers were computed for a different formulation. Storing them
    as ``CURRENT`` would present a measurement of one material as a
    measurement of another; storing them with no state at all would leave the
    interface guessing.
    """

    #: Computed from THIS version's inputs.
    CURRENT = "current"

    #: Carried over from a predecessor. ``copied_from_simulation_id`` and
    #: ``source_candidate_version_id`` say from where.
    COPIED_STALE = "copied_stale"

    #: Computed for this version, then invalidated by a later input change.
    INVALIDATED = "invalidated"

    #: The engine ran and refused to produce a number. Stored, because a
    #: blocked calculation is an outcome and hiding it would let the next
    #: reader assume nobody tried.
    FAILED = "failed"


class CandidateSimulation(Base):
    """A persisted simulation result, attributed to one exact version.

    This is the record that made locking necessary in the first place. A
    simulation is a claim of the form "these inputs produce this curve"; if the
    inputs can change afterwards, the claim quietly becomes false while
    continuing to look like a measurement.
    """

    __tablename__ = "validation_candidate_simulations"
    __table_args__ = (
        # A stale copy has to say what it was copied from. A row claiming
        # COPIED_STALE with no source is an unattributable number, which is
        # exactly the thing the state exists to prevent.
        CheckConstraint(
            "(state <> 'COPIED_STALE') OR "
            "(source_candidate_version_id IS NOT NULL)",
            name="ck_simulation_stale_names_its_source"),
        Index("ix_candidate_simulation_version",
              "candidate_version_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)

    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True)

    #: Denormalised for listing. The version is the authoritative link; this
    #: exists so "every simulation for this candidate" is one indexed
    #: predicate rather than a join through the version table.
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidates.id", ondelete="CASCADE"),
        nullable=False, index=True)

    #: THE link. Not nullable, and RESTRICT on delete: a version cannot be
    #: removed while a result claims to describe it.
    candidate_version_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=False, index=True)

    kind: Mapped[SimulationKind] = mapped_column(
        Enum(SimulationKind, native_enum=False, length=24),
        nullable=False, index=True)

    #: Which engine produced it. Without this a result can be re-run but not
    #: reproduced: re-running gives today's answer under today's rules.
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset_version: Mapped[str | None] = mapped_column(String(64),
                                                        nullable=True)

    #: The checksum of the version snapshot at the moment the engine ran.
    #: Compared against the version's current checksum by the integrity check,
    #: so "this result was computed from that formulation" is verifiable rather
    #: than merely asserted by a foreign key.
    inputs_checksum: Mapped[str] = mapped_column(String(64), nullable=False,
                                                  index=True)

    inputs_json: Mapped[str] = mapped_column(Text, nullable=False)
    #: Null when the engine refused. A failed simulation is stored with
    #: ``state = FAILED`` and a reason, never with a fabricated result.
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(300),
                                                        nullable=True)

    state: Mapped[DependentResultState] = mapped_column(
        Enum(DependentResultState, native_enum=False, length=16),
        nullable=False, default=DependentResultState.CURRENT, index=True)

    #: Set on a result carried forward into a revision. Both are recorded: the
    #: row it was copied from, and the version that row described.
    copied_from_simulation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("validation_candidate_simulations.id",
                            ondelete="SET NULL"), nullable=True)
    source_candidate_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("validation_candidate_versions.id",
                            ondelete="RESTRICT"), nullable=True)

    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class CandidateEvidenceAssessment(Base):
    """How evidence for one readiness area stands, for one exact version.

    ``reuse`` is required and has no default. An assessment that inherits
    evidence from a predecessor without saying so is the quiet failure this
    table exists to prevent: an experiment performed on v1 remains an
    experiment performed on v1, and a screen that lists it under v3 without
    qualification has re-attested it on nobody's authority.
    """

    __tablename__ = "validation_candidate_evidence_assessments"
    __table_args__ = (
        # One live assessment per (version, purpose). A second reading of the
        # same purpose supersedes rather than duplicating, so the interface
        # never has to choose between two current answers.
        UniqueConstraint("candidate_version_id", "purpose", "superseded_by_id",
                         name="uq_evidence_assessment_purpose"),
        # Carried-forward evidence must name where it came from.
        CheckConstraint(
            "(reuse <> 'RETAINED_REFERENCE') OR "
            "(source_candidate_version_id IS NOT NULL)",
            name="ck_evidence_retained_names_its_source"),
        Index("ix_evidence_assessment_version",
              "candidate_version_id", "purpose"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)

    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidates.id", ondelete="CASCADE"),
        nullable=False, index=True)
    candidate_version_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=False, index=True)

    purpose: Mapped[ReadinessArea] = mapped_column(
        Enum(ReadinessArea, native_enum=False, length=40), nullable=False)

    #: Null means "no level held". Distinct from E1: an area nobody has
    #: assessed and an area assessed as weak are different findings.
    level: Mapped[EvidenceLevel | None] = mapped_column(
        Enum(EvidenceLevel, native_enum=False, length=8), nullable=True)

    reuse: Mapped[EvidenceReuse] = mapped_column(
        Enum(EvidenceReuse, native_enum=False, length=32), nullable=False,
        index=True)

    #: Where retained evidence was performed. Required when reuse is
    #: RETAINED_REFERENCE, by the constraint above.
    source_candidate_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("validation_candidate_versions.id",
                            ondelete="RESTRICT"), nullable=True)

    #: The experiment versions this reading was made from, as JSON ids. Not a
    #: join table: the assessment is a statement about what was known at a
    #: moment, and later experiments must not silently join it.
    considered_experiment_version_ids: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]")

    #: Why. Required — an assessment without a stated rationale is an
    #: assertion, which is the same reasoning ``ContradictionResolution``
    #: applies to its own rationale column.
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    ruleset_version: Mapped[str] = mapped_column(String(64), nullable=False)

    #: Append-only: a later reading points back rather than overwriting, so
    #: how the evidence was understood over time survives.
    superseded_by_id: Mapped[int | None] = mapped_column(Integer,
                                                          nullable=True)

    assessed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class CandidateReport(Base):
    """A generated report, frozen against the version it was generated from.

    ``content_json`` is stored, not re-rendered. Reopening a historical report
    must show what it said when it was issued — regenerating it from current
    data would silently answer a different question with the same title.
    """

    __tablename__ = "validation_candidate_reports"
    __table_args__ = (
        Index("ix_candidate_report_version",
              "candidate_version_id", "generated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)

    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidates.id", ondelete="CASCADE"),
        nullable=False, index=True)
    candidate_version_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)

    #: The version's label as it stood at generation. Stored verbatim so the
    #: report still reads correctly if the numbering scheme ever changes, and
    #: so the header is not derived from a row that may since have moved.
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    version_checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    #: The report as issued. Frozen.
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False,
                                                   index=True)

    format: Mapped[GeneratedArtifactFormat] = mapped_column(
        Enum(GeneratedArtifactFormat, native_enum=False, length=16),
        nullable=False, default=GeneratedArtifactFormat.JSON)

    generated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class CandidateExport(Base):
    """An export, carrying the identity of exactly what was exported.

    ``manifest_json`` always names the candidate, the exact version, its
    revision label and the generation timestamp. That is the difference
    between a file somebody can act on and a file that describes an
    unidentifiable formulation.
    """

    __tablename__ = "validation_candidate_exports"
    __table_args__ = (
        Index("ix_candidate_export_version",
              "candidate_version_id", "generated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)

    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidates.id", ondelete="CASCADE"),
        nullable=False, index=True)
    candidate_version_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=False, index=True)

    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    version_checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    format: Mapped[GeneratedArtifactFormat] = mapped_column(
        Enum(GeneratedArtifactFormat, native_enum=False, length=16),
        nullable=False, default=GeneratedArtifactFormat.JSON)

    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False,
                                                   index=True)

    #: What the export is for, in the requester's words. Free text, and
    #: recorded because an export leaves the platform: knowing why one was
    #: taken is most of what makes the trail useful.
    purpose_note: Mapped[str | None] = mapped_column(String(300),
                                                      nullable=True)

    generated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class CandidateCROPackage(Base):
    """A package prepared for a contract research organization.

    The most consequential artefact on this list: somebody outside the
    organization is going to synthesise or test whatever it describes. A
    package that names the candidate but not the exact version is an
    instruction to make an ambiguous material.
    """

    __tablename__ = "validation_cro_packages"
    __table_args__ = (
        UniqueConstraint("package_code", name="uq_cro_package_code"),
        Index("ix_cro_package_version",
              "candidate_version_id", "generated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)

    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidates.id", ondelete="CASCADE"),
        nullable=False, index=True)
    candidate_version_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=False, index=True)

    #: Human-readable and unique, so a quotation can cite it.
    package_code: Mapped[str] = mapped_column(String(64), nullable=False)

    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    version_checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    #: The receiving laboratory, as typed. Not a foreign key: a CRO is not an
    #: account on this platform and inventing a row for one would imply
    #: a relationship the system does not manage.
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)

    #: The requesting organization's own reference for the quotation.
    quotation_reference: Mapped[str | None] = mapped_column(String(120),
                                                             nullable=True)

    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False,
                                                   index=True)

    generated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class CandidateVersionComparison(Base):
    """A comparison kept as a formal record.

    Stored only when somebody asks for it to be. Browsing a comparison on
    screen is a question, not a decision, and freezing a formulation because
    a reviewer looked at it would make the lock meaningless. Recording one is
    an act — it says "this comparison is the basis of what happens next" —
    and that is what locks both sides.
    """

    __tablename__ = "validation_version_comparisons"
    __table_args__ = (
        CheckConstraint("left_version_id <> right_version_id",
                        name="ck_comparison_two_distinct_versions"),
        Index("ix_version_comparison_left", "left_version_id"),
        Index("ix_version_comparison_right", "right_version_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)

    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidates.id", ondelete="CASCADE"),
        nullable=False, index=True)

    #: Two exact versions. Both RESTRICT: neither side of a recorded
    #: comparison can be deleted out from under it.
    left_version_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=False)
    right_version_id: Mapped[int] = mapped_column(
        ForeignKey("validation_candidate_versions.id", ondelete="RESTRICT"),
        nullable=False)

    #: The structured field-by-field result, frozen. Recomputing it later
    #: would give the comparison of whatever those versions say now, which for
    #: two locked versions is the same answer — and for a draft is not.
    changed_fields_json: Mapped[str] = mapped_column(Text, nullable=False)
    consequence_json: Mapped[str] = mapped_column(Text, nullable=False)

    #: The highest consequence the change set demands, denormalised so the
    #: list can be filtered without parsing JSON.
    material_classification: Mapped[str] = mapped_column(String(32),
                                                          nullable=False,
                                                          index=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True)
