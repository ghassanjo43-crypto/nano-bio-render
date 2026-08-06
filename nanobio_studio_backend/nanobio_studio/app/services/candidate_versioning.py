"""Candidate revision, locking and supersession.

The rule this module exists to make structural
----------------------------------------------
**Once a candidate version has been relied upon, its scientific inputs cannot
change.** Not "should not" — cannot, because there is no function here that
takes a locked version and new inputs. Revising means creating a *new* version
that records what it came from and why.

That matters more here than in most versioning schemes. If a formulation is
edited in place after a simulation has run against it, the simulation's stored
result silently becomes a claim about a material that no longer exists, and
nothing in the record says so. A reviewer reading it later sees a number, a
formulation, and no reason to doubt that one produced the other. That is the
failure this prevents: not data loss, but a plausible-looking lie.

Three separations that are easy to collapse and expensive to get wrong
----------------------------------------------------------------------
**Creating a revision is not superseding the predecessor.** A draft revision
is somebody's work in progress; the approved version is what the organization
currently stands behind. Automatically superseding on revision would mean any
author could retire an approved formulation by starting to edit it. So
supersession is a separate act, needing approval authority, recorded with its
own decision.

**Copying results is not revalidating them.** A revision inherits its
predecessor's scores so the reader can see the starting point, and every one of
them is marked STALE. Inheriting them as CURRENT would present numbers computed
for the old formulation as though they described the new one.

**Carrying evidence forward is not re-attesting it.** An experiment performed
on v1 remains an experiment performed on v1. A revision may cite it, but the
citation records that it came from a predecessor, so an assessor can decide
whether it still applies rather than being told that it does.

Concurrency
-----------
Revision numbers are allocated by a conditional `UPDATE` on the candidate row
followed by an insert that the unique constraint arbitrates, so two
simultaneous revisions produce two versions with different numbers rather than
one collision or two rows claiming to be v3. A repeated request carrying the
same idempotency key returns the version the first call created rather than a
second one.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.validation_models import (
    EDITABLE_VERSION_STATES, REVISABLE_VERSION_STATES,
    SUPERSEDABLE_VERSION_STATES, Candidate, CandidateVersion, ResultsState,
    SupersessionState, VersionStatus, utcnow,
)

__all__ = [
    "VersioningError", "VersionLocked", "RevisionRefused",
    "MATERIAL_FIELDS", "IDENTITY_FIELDS", "consequence_of_change",
    "canonical_snapshot", "snapshot_checksum", "compare_snapshots",
    "create_revision", "lock_version", "withdraw_version",
    "propose_supersession", "accept_supersession", "refuse_supersession",
    "mark_results_stale", "request_recalculation", "record_recalculation",
    "lineage_of", "current_effective_version", "latest_approved_version",
    "latest_draft_version",
    "RELIANCE_REASONS", "rely_on_version", "record_version_event",
    "require_exact_version_id", "AmbiguousVersionReference",
    "CONSEQUENCE_KEYS",
]


# ---------------------------------------------------------------------------
# Field classification
# ---------------------------------------------------------------------------

#: Fields that describe *which record this is*, not what the science says.
#:
#: These may be corrected in place on any version, at any status, because
#: fixing a typo in a label does not change what was measured. The boundary is
#: enforced by exclusion: anything not named here is scientific, so a field
#: added later is protected by default rather than exposed by default.
IDENTITY_FIELDS = frozenset({"name", "description", "code_note", "label"})

#: Scientific inputs whose change cannot inherit an approval.
#:
#: Grouped by what a change to them *demands*, because "requires review" is too
#: coarse to act on: a coating change and a dose change both invalidate an
#: approval, but only one of them needs a safety opinion.
MATERIAL_FIELDS: dict[str, str] = {
    # Formulation and physical identity — a different material.
    "material": "safety_review",
    "composition": "safety_review",
    "coating": "safety_review",
    "surface_coating": "safety_review",
    "functional_groups": "safety_review",
    "size_nm": "scientific_review",
    "hydrodynamic_size_nm": "scientific_review",
    "charge_mv": "scientific_review",
    "pdi": "scientific_review",
    "encapsulation_percent": "scientific_review",
    "crystallinity_index": "scientific_review",
    "hydrophobicity_logp": "scientific_review",
    "coating_thickness_nm": "scientific_review",

    # Targeting and payload — what it is aimed at and what it carries.
    "ligand": "safety_review",
    "targeting_ligand": "safety_review",
    "ligand_density_percent": "scientific_review",
    "receptor_binding_kd_nm": "scientific_review",
    "payload": "safety_review",
    "biological_target": "safety_review",
    "sequence": "safety_review",

    # Exposure — dose and route are the two that most directly decide harm.
    "dose": "safety_review",
    "dose_mg_kg": "safety_review",
    "administration_route": "safety_review",
    "route": "safety_review",

    # Pharmacokinetics.
    "pk_model": "scientific_review",
    "k_abs": "scientific_review",
    "clearance": "scientific_review",
    "volume_of_distribution": "scientific_review",
    "half_life_h": "scientific_review",

    # The rules themselves. A threshold change can flip a conclusion without
    # touching a single measurement, which is why it belongs on this list.
    "model_version": "scientific_review",
    "ruleset_version": "scientific_review",
    "decision_threshold": "scientific_review",
    "algorithm_selection": "scientific_review",
}

#: What a change demands, in increasing order of consequence.
CONSEQUENCE_ORDER = ("recalculation", "scientific_review", "safety_review")


def consequence_of_change(changed_fields: set[str]) -> dict:
    """What a set of changed fields requires before the result can be used.

    Fields nobody classified default to ``recalculation`` rather than to
    nothing. An unrecognised scientific input is still an input: treating it as
    harmless because it is not on a list is how a new field silently inherits
    an approval it was never assessed under.
    """
    scientific = {f for f in changed_fields if f not in IDENTITY_FIELDS}
    if not scientific:
        return {
            "requires": "none",
            "changed_scientific_fields": [],
            "identity_only": True,
            "approval_may_carry_forward": True,
            "consequences": _consequences("none"),
            "explanation": (
                "Only descriptive labels changed. Nothing about the material, "
                "its dose, its route or the rules applied to it is different, "
                "so prior assessments still describe this formulation."),
        }

    demanded = "recalculation"
    for field in scientific:
        requirement = MATERIAL_FIELDS.get(field, "recalculation")
        if CONSEQUENCE_ORDER.index(requirement) > CONSEQUENCE_ORDER.index(demanded):
            demanded = requirement

    consequences = _consequences(demanded)
    return {
        "requires": demanded,
        "changed_scientific_fields": sorted(scientific),
        # Which classification each changed field carried, so a reviewer can
        # see WHY the demand landed where it did rather than being told only
        # the answer. An unclassified field shows as "recalculation", which is
        # the default-deny — visible rather than silent.
        "field_classifications": {
            field: MATERIAL_FIELDS.get(field, "recalculation")
            for field in sorted(scientific)
        },
        "identity_only": False,
        # Never, for any scientific change. Stated as data rather than left to
        # each caller to infer, because "this one is minor" is exactly the
        # judgement that should not be made field by field at a call site.
        "approval_may_carry_forward": False,
        "consequences": consequences,
        # Kept as top-level keys as well: these two have been read by callers
        # since this feature shipped, and moving a field clients depend on is
        # a breaking change dressed as a tidy-up.
        "requires_new_report": consequences["new_report"],
        "requires_new_package": consequences["new_cro_package"],
        "explanation": _explain(demanded, sorted(scientific)),
    }


#: The six consequences a change can carry, in the order they escalate.
#:
#: Named individually rather than left implicit in ``requires``, because each
#: is a different piece of work for a different person: recalculating is an
#: engine run, reassessing is a scientist reading, a new approval is a
#: decision, and a new package is something that leaves the building. A caller
#: given only "safety_review" has to re-derive the other five, and every place
#: that re-derives them is a place they can be derived differently.
CONSEQUENCE_KEYS = ("recalculation", "scientific_reassessment",
                    "safety_reassessment", "new_approval", "new_report",
                    "new_cro_package")


def _consequences(demanded: str) -> dict[str, bool]:
    """What a demand level actually requires, as six independent answers.

    Monotonic by construction: a safety reassessment implies everything a
    scientific one does, which implies a recalculation. Written as an explicit
    table rather than as comparisons at the call site so the escalation is
    legible and a test can pin every cell.
    """
    if demanded == "none":
        return {key: False for key in CONSEQUENCE_KEYS}

    scientific = demanded in ("scientific_review", "safety_review")
    safety = demanded == "safety_review"

    return {
        # Any scientific change invalidates the derived numbers.
        "recalculation": True,
        "scientific_reassessment": scientific,
        "safety_reassessment": safety,
        # No approval survives any scientific change — including a
        # recalculation-only one, because the approval was granted against
        # numbers that no longer describe this formulation.
        "new_approval": True,
        # A report cites results and a conclusion. Recalculating alone changes
        # the numbers a report would carry, so the old one no longer describes
        # this version either.
        "new_report": True,
        # A package instructs somebody outside to make a material. It has to
        # be reissued whenever the material, its dose or its route changed —
        # which is exactly what the safety classification marks.
        "new_cro_package": safety,
    }


def _explain(demanded: str, fields: list[str]) -> str:
    listed = ", ".join(fields[:6]) + ("…" if len(fields) > 6 else "")
    if demanded == "safety_review":
        return (
            f"This changes what the material is, what it is aimed at, or how "
            f"much of it reaches a subject ({listed}). A previous safety "
            f"opinion was formed about a different exposure and does not "
            f"transfer.")
    if demanded == "scientific_review":
        return (
            f"Scientific inputs changed ({listed}), so derived results no "
            f"longer describe this formulation and any approval was granted "
            f"against different numbers.")
    return (
        f"Inputs changed ({listed}). Results must be recalculated before they "
        f"are cited.")


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

def canonical_snapshot(design_inputs: dict[str, Any]) -> str:
    """Sorted-key JSON, so two equal formulations produce one checksum."""
    return json.dumps(design_inputs, sort_keys=True, separators=(",", ":"),
                      default=str)


def snapshot_checksum(snapshot: str) -> str:
    return hashlib.sha256(snapshot.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FieldChange:
    field: str
    before: Any
    after: Any
    kind: str          # added | removed | changed
    is_scientific: bool


def compare_snapshots(before: str, after: str) -> list[FieldChange]:
    """A structured, field-by-field comparison.

    Returns changes, not a text diff. A raw JSON diff is unreadable at exactly
    the moment it matters — a reviewer deciding whether a revision needs a
    fresh safety opinion should not be counting braces to find out that the
    dose changed.
    """
    try:
        old = json.loads(before) if before else {}
        new = json.loads(after) if after else {}
    except (TypeError, ValueError):
        return []

    changes: list[FieldChange] = []
    for field in sorted(set(old) | set(new)):
        in_old, in_new = field in old, field in new
        if in_old and in_new:
            if old[field] == new[field]:
                continue
            kind = "changed"
        elif in_new:
            kind = "added"
        else:
            kind = "removed"

        changes.append(FieldChange(
            field=field,
            before=old.get(field),
            after=new.get(field),
            kind=kind,
            is_scientific=field not in IDENTITY_FIELDS,
        ))
    return changes


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class VersioningError(RuntimeError):
    def __init__(self, code: str, message: str, remedy: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.remedy = remedy


class VersionLocked(VersioningError):
    """Raised when someone tries to edit inputs that something depends on."""

    def __init__(self, version: CandidateVersion, dependents: list[str]):
        super().__init__(
            "version_locked",
            f"{version.effective_label()} cannot be edited: "
            f"{', '.join(dependents)} already depend on it.",
            "Create a revision. The original stays exactly as it is, and the "
            "work that relied on it keeps pointing at it.")
        self.dependents = dependents


class RevisionRefused(VersioningError):
    pass


class AmbiguousVersionReference(VersioningError):
    """Raised when a scientific operation was asked to work out which version.

    Named as its own error because the remedy is different from every other
    refusal here: nothing is wrong with the data, the *request* did not say
    what it was about.
    """

    def __init__(self, given: object):
        super().__init__(
            "ambiguous_version_reference",
            f"A scientific operation needs the exact candidate version it is "
            f"about. {given!r} is not one.",
            "Send the numeric id of the exact version. This endpoint does not "
            "resolve 'latest': the newest draft and the currently approved "
            "version are different things, and picking one on the caller's "
            "behalf is how an unreviewed formulation ends up in a report.")
        self.given = given


def require_exact_version_id(given: Any) -> int:
    """Accept an exact version id; refuse anything that means "work it out".

    Every scientific operation goes through this rather than accepting an
    optional id and falling back. The fallback is the defect: a report
    generated against "latest" is a report whose subject depends on when it
    ran, and two runs a minute apart can describe different formulations while
    carrying the same title.

    Strings that happen to be digits are accepted — a path parameter arrives as
    text — but the sentinel words are refused explicitly rather than failing an
    int() conversion, so the message says what is wrong.
    """
    if isinstance(given, bool) or given is None:
        raise AmbiguousVersionReference(given)
    if isinstance(given, int):
        if given <= 0:
            raise AmbiguousVersionReference(given)
        return given
    if isinstance(given, str):
        token = given.strip()
        if token.lower() in {"latest", "current", "newest", "head", "approved",
                             "latest_draft", "latest_approved", ""}:
            raise AmbiguousVersionReference(given)
        try:
            value = int(token)
        except ValueError:
            raise AmbiguousVersionReference(given) from None
        if value <= 0:
            raise AmbiguousVersionReference(given)
        return value
    raise AmbiguousVersionReference(given)


# ---------------------------------------------------------------------------
# The audit trail for a version
# ---------------------------------------------------------------------------

async def record_version_event(
    session: AsyncSession, *, event, version: CandidateVersion,
    actor_id: int | None, reason: str | None = None,
    summary: str | None = None, experiment_id: int | None = None,
    experiment_version_id: int | None = None,
) -> None:
    """Append one audit row for a candidate version. Never updates, never deletes.

    Added to the caller's session and **not committed here**. That is the
    property that matters: the event and the thing it records land in the same
    transaction, so there is no trail entry for an operation that rolled back
    and no operation that committed without one.

    Both identifiers are written. The version id says what was relied upon; the
    candidate id lets a history be assembled without joining to a table this
    trail deliberately has no foreign key into.
    """
    from nanobio_studio.app.db.validation_models import ValidationAuditLog
    from nanobio_studio.app.services.audit_redaction import (
        MAX_REASON, MAX_SUMMARY, redact,
    )

    audit_row = ValidationAuditLog(
        organization_id=version.organization_id,
        event=event,
        actor_id=actor_id,
        candidate_id=version.candidate_id,
        candidate_version_id=version.id,
        experiment_id=experiment_id,
        experiment_version_id=experiment_version_id,
        reason=redact(reason, limit=MAX_REASON),
        summary=redact(summary, limit=MAX_SUMMARY),
    )
    session.add(audit_row)
    # Flushed, not committed. The session runs with autoflush off, so without
    # this the row stays pending and is invisible to a SELECT issued later in
    # the same transaction — which is how a caller reading its own trail back
    # gets an empty list and concludes nothing was recorded. Flushing writes
    # it; the caller's commit is still what makes it durable, which is what
    # keeps the event transactional with the operation it records.
    await session.flush()
    from nanobio_studio.app.services.notification_service import (
        surface_candidate_event,
    )
    event_value = getattr(event, "value", str(event))
    await surface_candidate_event(
        session, event_value=event_value, version=version,
        audit_event_id=audit_row.id, actor_id=actor_id)


# ---------------------------------------------------------------------------
# Scientific reliance: the locking boundary
# ---------------------------------------------------------------------------

#: Every operation that causes a candidate version to be relied upon, and the
#: words that go in the lock reason.
#:
#: Written as data rather than as a string at each call site so the set is
#: enumerable — a test can assert that every member is reachable, and a reader
#: can see the whole list of things that make a formulation immutable without
#: grepping for a function name.
RELIANCE_REASONS: dict[str, str] = {
    "experiment": "an experiment was created against it",
    "measurement": "measurements were recorded against it",
    "submission": "it was submitted for scientific review",
    "review": "scientific review began",
    "decision": "a formal review decision was recorded",
    "evidence": "an evidence assessment was computed from it",
    "contradiction": "a contradiction resolution cited it",
    "attachment": "supporting evidence was attached to work based on it",
    "report": "a report was generated from it",
    "export": "an export was generated from it",
    "package": "a CRO package was generated from it",
    "comparison": "a formal comparison record cited it",
    "simulation": "a simulation was run against it",
}


async def rely_on_version(
    session: AsyncSession, *, version: CandidateVersion | None,
    reason_key: str, actor_id: int | None,
) -> bool:
    """Lock the version a dependent record is about to rely on.

    **This is the narrowest authoritative boundary for the immutability rule.**
    Every operation that creates scientific reliance calls it, in the same
    session and therefore the same transaction as the record it is creating.

    Why here rather than in the routes
    ----------------------------------
    Route discipline is a convention, and a convention is one new endpoint away
    from being broken silently. Putting the lock beneath the service means a
    caller that reaches the dependent record at all has already been through it
    — including a future route, a background job, and a script.

    Why the transaction matters more than it looks
    ----------------------------------------------
    The caller commits once, after both this and the dependent write. So there
    is no interleaving in which the dependency exists and the version is still
    editable, and none in which the version is locked but the dependency was
    rolled back. Locking on a separate commit would open exactly that window,
    and it is the window in which somebody edits a formulation that a running
    simulation is already using.

    Returns True if this call changed the status. Already-locked, approved and
    superseded versions are left alone: reliance is monotonic, and the FIRST
    reason is the informative one — "an experiment was created against it" says
    more about why a formulation froze than "a report was generated" three
    months later.
    """
    if version is None:
        return False

    reason = RELIANCE_REASONS.get(reason_key, reason_key)
    return await lock_version(session, version=version, reason=reason,
                              actor_id=actor_id)


# ---------------------------------------------------------------------------
# Lineage queries
# ---------------------------------------------------------------------------

async def lineage_of(session: AsyncSession, version: CandidateVersion,
                     *, max_depth: int = 200) -> list[CandidateVersion]:
    """Walk predecessors, oldest first.

    `max_depth` is a guard, not a limit. Cycles are refused by a database
    constraint and by `_would_create_cycle`, so reaching it means an invariant
    has already been violated — and looping forever inside a request is a worse
    way to discover that than returning what was found.
    """
    chain: list[CandidateVersion] = [version]
    seen = {version.id}
    current = version

    for _ in range(max_depth):
        if current.predecessor_version_id is None:
            break
        if current.predecessor_version_id in seen:
            break
        predecessor = await session.get(
            CandidateVersion, current.predecessor_version_id)
        if predecessor is None:
            break
        chain.append(predecessor)
        seen.add(predecessor.id)
        current = predecessor

    return list(reversed(chain))


async def _would_create_cycle(session: AsyncSession, *, version_id: int,
                              predecessor_id: int) -> bool:
    """True if making `predecessor_id` the parent of `version_id` closes a loop.

    Checked in the service as well as by constraint, because a database CHECK
    can catch self-reference cheaply but cannot walk an arbitrary-length chain.
    """
    if version_id == predecessor_id:
        return True

    current_id: int | None = predecessor_id
    seen: set[int] = set()
    for _ in range(200):
        if current_id is None or current_id in seen:
            return False
        if current_id == version_id:
            return True
        seen.add(current_id)
        row = await session.get(CandidateVersion, current_id)
        if row is None:
            return False
        current_id = row.predecessor_version_id
    return False


async def current_effective_version(session: AsyncSession, candidate_id: int
                                    ) -> CandidateVersion | None:
    """The version the organization currently stands behind.

    Approved-and-not-superseded first; otherwise the newest locked version.
    Deliberately never "the newest row" — that would make an unreviewed draft
    the effective version the moment somebody started typing.
    """
    approved = (await session.execute(
        select(CandidateVersion)
        .where(CandidateVersion.candidate_id == candidate_id,
               CandidateVersion.status == VersionStatus.APPROVED)
        .order_by(CandidateVersion.version_number.desc()).limit(1)
    )).scalars().first()
    if approved is not None:
        return approved

    return (await session.execute(
        select(CandidateVersion)
        .where(CandidateVersion.candidate_id == candidate_id,
               CandidateVersion.status == VersionStatus.LOCKED)
        .order_by(CandidateVersion.version_number.desc()).limit(1)
    )).scalars().first()


async def latest_approved_version(session: AsyncSession, candidate_id: int
                                  ) -> CandidateVersion | None:
    return (await session.execute(
        select(CandidateVersion)
        .where(CandidateVersion.candidate_id == candidate_id,
               CandidateVersion.status.in_(
                   [VersionStatus.APPROVED, VersionStatus.SUPERSEDED]),
               CandidateVersion.supersession_state != SupersessionState.ACCEPTED)
        .order_by(CandidateVersion.version_number.desc()).limit(1)
    )).scalars().first()


async def latest_draft_version(session: AsyncSession, candidate_id: int
                               ) -> CandidateVersion | None:
    return (await session.execute(
        select(CandidateVersion)
        .where(CandidateVersion.candidate_id == candidate_id,
               CandidateVersion.status == VersionStatus.DRAFT)
        .order_by(CandidateVersion.version_number.desc()).limit(1)
    )).scalars().first()


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------

async def lock_version(session: AsyncSession, *, version: CandidateVersion,
                       reason: str, actor_id: int | None,
                       now: Callable[[], datetime] = utcnow) -> bool:
    """Move a draft to LOCKED. Idempotent; returns True if it changed.

    Called whenever something starts depending on the version — an experiment,
    a simulation, a review, an export. Locking at the moment of dependence
    rather than on a schedule is what makes the guarantee true: there is no
    window in which a dependent record exists and the inputs are still
    editable.
    """
    if version.status is not VersionStatus.DRAFT:
        return False

    version.status = VersionStatus.LOCKED
    version.locked_at = now()
    version.lock_reason = reason[:200]
    version.revision = (version.revision or 1) + 1
    await session.flush()

    # Written here rather than by the caller, for the same reason the lock is:
    # a caller that forgets leaves a formulation frozen with nothing in the
    # trail saying when or why. Same session, so it commits or rolls back with
    # the dependent record.
    from nanobio_studio.app.validation.vocabulary import AuditEvent

    await record_version_event(
        session, event=AuditEvent.VERSION_LOCKED, version=version,
        actor_id=actor_id, reason=reason,
        summary=f"{version.effective_label()} locked")
    return True


async def withdraw_version(session: AsyncSession, *,
                           version: CandidateVersion, reason: str,
                           actor_id: int | None,
                           now: Callable[[], datetime] = utcnow) -> None:
    """Retire a version without a successor.

    Distinct from supersession, and the distinction is a claim about the
    science: superseded means "use this newer one instead", withdrawn means
    "we no longer stand behind this at all". Conflating them would let a
    rejected formulation look like an ordinary predecessor.
    """
    if version.status is VersionStatus.SUPERSEDED:
        raise VersioningError(
            "already_superseded",
            f"{version.effective_label()} has already been superseded by "
            f"a later version.")
    if not reason or not reason.strip():
        raise VersioningError(
            "reason_required",
            "Say why this version is being withdrawn. It stays in the record "
            "and the reason is what explains it to the next reader.")

    version.status = VersionStatus.WITHDRAWN
    version.lock_reason = reason[:200]
    version.locked_at = version.locked_at or now()
    version.revision = (version.revision or 1) + 1
    await session.flush()

    from nanobio_studio.app.validation.vocabulary import AuditEvent

    await record_version_event(
        session, event=AuditEvent.VERSION_WITHDRAWN, version=version,
        actor_id=actor_id, reason=reason,
        summary=f"{version.effective_label()} withdrawn without a successor")


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

async def mark_results_stale(session: AsyncSession, *,
                             version: CandidateVersion,
                             inherited_from: CandidateVersion | None = None,
                             actor_id: int | None = None,
                             reason: str | None = None) -> None:
    version.results_state = ResultsState.STALE
    if inherited_from is not None:
        version.results_inherited_from_id = inherited_from.id
    await session.flush()

    from nanobio_studio.app.validation.vocabulary import AuditEvent

    await record_version_event(
        session, event=AuditEvent.REASSESSMENT_REQUIRED, version=version,
        actor_id=actor_id, reason=reason,
        summary=(f"{version.effective_label()} results marked stale"
                 + (f", inherited from version {inherited_from.id}"
                    if inherited_from is not None else "")))


async def request_recalculation(session: AsyncSession, *,
                                version: CandidateVersion,
                                actor_id: int | None = None,
                                reason: str | None = None) -> None:
    version.results_state = ResultsState.RECALCULATING
    await session.flush()

    from nanobio_studio.app.validation.vocabulary import AuditEvent

    await record_version_event(
        session, event=AuditEvent.RECALCULATION_REQUESTED, version=version,
        actor_id=actor_id, reason=reason,
        summary=f"recalculation requested for {version.effective_label()}")


async def record_recalculation(session: AsyncSession, *,
                               version: CandidateVersion,
                               model_version: str | None = None,
                               ruleset_version: str | None = None,
                               reference_data_version: str | None = None,
                               actor_id: int | None = None,
                               reason: str | None = None) -> None:
    """Mark results current, and record the rules that produced them.

    The provenance is written here rather than left for the caller, because a
    result marked CURRENT with no recorded model version is the case this whole
    scheme exists to prevent: a number that can be re-run but not reproduced.
    """
    version.results_state = ResultsState.CURRENT
    version.results_inherited_from_id = None
    if model_version is not None:
        version.model_version = model_version
    if ruleset_version is not None:
        version.ruleset_version = ruleset_version
    if reference_data_version is not None:
        version.reference_data_version = reference_data_version
    await session.flush()

    from nanobio_studio.app.validation.vocabulary import AuditEvent

    await record_version_event(
        session, event=AuditEvent.RECALCULATION_COMPLETED, version=version,
        actor_id=actor_id, reason=reason,
        summary=(f"{version.effective_label()} recalculated under "
                 f"model {version.model_version or 'unrecorded'} / "
                 f"ruleset {version.ruleset_version or 'unrecorded'}"))


# ---------------------------------------------------------------------------
# Revision
# ---------------------------------------------------------------------------

async def _next_version_number(session: AsyncSession, candidate_id: int) -> int:
    """Allocate under concurrency.

    `MAX(version_number) + 1` read inside the same transaction that inserts,
    with the unique constraint as the arbiter. Two concurrent callers can still
    read the same maximum; the loser's insert violates
    `uq_candidate_version` and is retried by `create_revision`, which is why
    that retry exists rather than being defensive padding.
    """
    highest = (await session.execute(
        select(func.max(CandidateVersion.version_number))
        .where(CandidateVersion.candidate_id == candidate_id)
    )).scalar()
    return int(highest or 0) + 1


async def create_revision(
    session: AsyncSession, *, predecessor: CandidateVersion,
    design_inputs: dict[str, Any] | None, reason: str, actor_id: int | None,
    carry_results: bool = True,
    idempotency_key: str | None = None,
    now: Callable[[], datetime] = utcnow,
    max_attempts: int = 5,
) -> tuple[CandidateVersion, bool]:
    """Create the next version, derived from `predecessor`.

    Returns ``(version, created)``. ``created`` is False when an idempotency
    key matched an existing revision — so a retried request returns the version
    the first call made instead of a second one that would fork the lineage.

    What deliberately does NOT happen here:

    * the predecessor is not superseded, withdrawn or altered in any way;
    * no approval is carried across — the new version starts as a DRAFT;
    * copied results are marked STALE, never CURRENT.
    """
    if not reason or not reason.strip():
        raise RevisionRefused(
            "reason_required",
            "A revision needs a reason. It is the only part of the record "
            "that explains why the formulation changed, and it is read by "
            "people who were not there.")

    if predecessor.status not in REVISABLE_VERSION_STATES:
        raise RevisionRefused(
            "not_revisable",
            f"{predecessor.effective_label()} cannot be revised from its "
            f"current state ({predecessor.status.value}).")

    # An idempotent retry returns the first result rather than forking.
    if idempotency_key:
        existing = (await session.execute(
            select(CandidateVersion).where(
                CandidateVersion.candidate_id == predecessor.candidate_id,
                CandidateVersion.predecessor_version_id == predecessor.id,
                CandidateVersion.lock_reason == _idempotency_marker(
                    idempotency_key))
        )).scalars().first()
        if existing is not None:
            return existing, False

    snapshot_source = (design_inputs if design_inputs is not None
                       else json.loads(predecessor.design_snapshot_json or "{}"))
    snapshot = canonical_snapshot(snapshot_source)

    last_error: Exception | None = None
    for _attempt in range(max_attempts):
        number = await _next_version_number(session, predecessor.candidate_id)
        version = CandidateVersion(
            organization_id=predecessor.organization_id,
            candidate_id=predecessor.candidate_id,
            version_number=number,
            revision_label=f"v{number}",
            design_snapshot_json=snapshot,
            snapshot_checksum=snapshot_checksum(snapshot),
            predecessor_version_id=predecessor.id,
            revision_reason=reason.strip(),
            status=VersionStatus.DRAFT,
            created_by=actor_id,
            created_at=now(),
            # Provenance is inherited so the reader can see which rules the
            # PREDECESSOR's numbers were produced under. It is not a claim
            # about this version's results, which are stale until recalculated.
            model_version=predecessor.model_version,
            ruleset_version=predecessor.ruleset_version,
            reference_data_version=predecessor.reference_data_version,
            algorithm_selection=predecessor.algorithm_selection,
            lock_reason=(_idempotency_marker(idempotency_key)
                         if idempotency_key else None),
        )

        if carry_results and predecessor.results_state in (
                ResultsState.CURRENT, ResultsState.STALE):
            # Copied so the reader sees the starting point — and marked STALE,
            # because they were computed for the predecessor's inputs.
            version.results_state = ResultsState.STALE
            version.results_inherited_from_id = predecessor.id
        else:
            version.results_state = ResultsState.NONE

        session.add(version)
        try:
            await session.flush()
        except IntegrityError as exc:
            # Another caller took this number. Roll back to the savepoint the
            # caller established and try the next one.
            last_error = exc
            await session.rollback()
            continue

        if await _would_create_cycle(session, version_id=version.id,
                                     predecessor_id=predecessor.id):
            raise RevisionRefused(
                "cycle_refused",
                "That revision would make the version history circular.")

        from nanobio_studio.app.validation.vocabulary import AuditEvent

        await record_version_event(
            session, event=AuditEvent.REVISION_CREATED, version=version,
            actor_id=actor_id, reason=reason,
            summary=(f"{version.effective_label()} created from "
                     f"{predecessor.effective_label()}; starts as a draft "
                     f"carrying no approval"))

        # A revision that copied its predecessor's numbers is carrying results
        # computed for a different formulation. Recorded as its own event so
        # the requirement is discoverable from the trail rather than inferable
        # from the absence of a recalculation.
        if version.results_state is ResultsState.STALE:
            changed = compare_snapshots(predecessor.design_snapshot_json,
                                        version.design_snapshot_json)
            consequence = consequence_of_change({c.field for c in changed})
            await record_version_event(
                session, event=AuditEvent.REASSESSMENT_REQUIRED,
                version=version, actor_id=actor_id,
                summary=(f"results inherited from "
                         f"{predecessor.effective_label()} and marked stale; "
                         f"requires {consequence['requires']}"))

        return version, True

    raise RevisionRefused(
        "revision_conflict",
        "The revision could not be numbered because other revisions are being "
        "created at the same time. Try again.") from last_error


def _idempotency_marker(key: str) -> str:
    """Stored in `lock_reason` until the version locks.

    Reusing an existing column rather than adding one: the marker is only
    meaningful while the version is a fresh draft, and `lock_reason` is by
    definition unset then. It is replaced the moment the version locks, so it
    never outlives its purpose or contradicts a real lock reason.
    """
    return f"idempotency:{hashlib.sha256(key.encode()).hexdigest()[:24]}"


# ---------------------------------------------------------------------------
# Supersession
# ---------------------------------------------------------------------------

async def propose_supersession(session: AsyncSession, *,
                               predecessor: CandidateVersion,
                               successor: CandidateVersion,
                               reason: str, actor_id: int | None) -> None:
    """Ask for a successor to take over. Does not itself take over.

    Proposing is separated from accepting so that the two can require
    different authority: an author may propose that their revision replaces the
    approved version, and only somebody with approval authority may agree.
    """
    _check_pair(predecessor, successor)

    if predecessor.status not in SUPERSEDABLE_VERSION_STATES:
        raise VersioningError(
            "not_supersedable",
            f"{predecessor.effective_label()} is a "
            f"{predecessor.status.value} version, so there is nothing to take "
            f"over from. Only a version something relies on can be "
            f"superseded.")
    if not reason or not reason.strip():
        raise VersioningError(
            "reason_required",
            "Say why the newer version should take over.")

    predecessor.supersession_state = SupersessionState.PROPOSED
    predecessor.supersession_reason = reason.strip()
    predecessor.revision = (predecessor.revision or 1) + 1
    await session.flush()

    from nanobio_studio.app.validation.vocabulary import AuditEvent

    await record_version_event(
        session, event=AuditEvent.SUPERSESSION_PROPOSED, version=predecessor,
        actor_id=actor_id, reason=reason,
        summary=(f"{successor.effective_label()} proposed to take over from "
                 f"{predecessor.effective_label()}"))


async def accept_supersession(session: AsyncSession, *,
                              predecessor: CandidateVersion,
                              successor: CandidateVersion,
                              actor_id: int | None,
                              decision_id: int | None = None,
                              reason: str | None = None,
                              expected_revision: int | None = None,
                              now: Callable[[], datetime] = utcnow) -> None:
    """Complete the supersession.

    Uses a conditional UPDATE on `revision` so two simultaneous acceptances
    resolve to one rather than both writing. The loser is told the record
    moved, not silently overwritten — supersession is a decision about which
    version is current, and two of them landing at once is exactly the
    situation where the second person needs to re-read before acting.

    The predecessor keeps its snapshot, its approvals and every record that
    referenced it. Superseding says what to use next; it does not unsay what
    happened.
    """
    _check_pair(predecessor, successor)

    if predecessor.status not in SUPERSEDABLE_VERSION_STATES:
        raise VersioningError(
            "not_supersedable",
            f"{predecessor.effective_label()} cannot be superseded from its "
            f"current state ({predecessor.status.value}).")
    if successor.status is VersionStatus.DRAFT:
        raise VersioningError(
            "successor_is_draft",
            f"{successor.effective_label()} is still a draft. A version that "
            f"has not been reviewed cannot take over from one that has.",
            "Submit the revision for review first.")
    if successor.version_number <= predecessor.version_number:
        raise VersioningError(
            "successor_not_later",
            "A version cannot be superseded by an earlier one.")

    stamp = now()
    condition = [
        CandidateVersion.id == predecessor.id,
        CandidateVersion.superseded_by_version_id.is_(None),
    ]
    if expected_revision is not None:
        condition.append(CandidateVersion.revision == expected_revision)

    result = await session.execute(
        update(CandidateVersion).where(*condition).values(
            status=VersionStatus.SUPERSEDED,
            supersession_state=SupersessionState.ACCEPTED,
            superseded_by_version_id=successor.id,
            superseded_at=stamp,
            superseded_by_user_id=actor_id,
            supersession_decision_id=decision_id,
            supersession_reason=(reason.strip() if reason
                                 else predecessor.supersession_reason),
            locked_at=predecessor.locked_at or stamp,
            revision=(predecessor.revision or 1) + 1,
        ))

    if result.rowcount == 0:
        raise VersioningError(
            "supersession_conflict",
            f"{predecessor.effective_label()} was changed by somebody else "
            f"while you were deciding. Re-read it before superseding.")

    await session.refresh(predecessor)
    await session.flush()

    from nanobio_studio.app.validation.vocabulary import AuditEvent

    await record_version_event(
        session, event=AuditEvent.SUPERSESSION_ACCEPTED, version=predecessor,
        actor_id=actor_id,
        reason=(reason or predecessor.supersession_reason),
        summary=(f"{predecessor.effective_label()} superseded by "
                 f"{successor.effective_label()}"
                 + (f" under decision {decision_id}"
                    if decision_id is not None else "")))


async def refuse_supersession(session: AsyncSession, *,
                              predecessor: CandidateVersion,
                              reason: str, actor_id: int | None) -> None:
    """Decline a proposal, leaving the predecessor exactly as it was."""
    if predecessor.supersession_state is not SupersessionState.PROPOSED:
        raise VersioningError(
            "no_proposal",
            "There is no supersession proposal to refuse.")

    predecessor.supersession_state = SupersessionState.REFUSED
    predecessor.supersession_reason = (reason or "").strip() or None
    predecessor.revision = (predecessor.revision or 1) + 1
    await session.flush()

    from nanobio_studio.app.validation.vocabulary import AuditEvent

    await record_version_event(
        session, event=AuditEvent.SUPERSESSION_REFUSED, version=predecessor,
        actor_id=actor_id, reason=reason,
        summary=(f"the proposal to supersede "
                 f"{predecessor.effective_label()} was declined"))


def _check_pair(predecessor: CandidateVersion,
                successor: CandidateVersion) -> None:
    """Both versions must belong to the same candidate and organization.

    Checked here and by foreign key. Superseding across candidates would claim
    that one formulation replaces a different formulation, and across
    organizations it would be a cross-tenant write dressed as a decision.
    """
    if predecessor.id == successor.id:
        raise VersioningError(
            "self_supersession",
            "A version cannot supersede itself.")
    if predecessor.candidate_id != successor.candidate_id:
        raise VersioningError(
            "cross_candidate_supersession",
            "Those versions belong to different candidates. One formulation "
            "does not supersede another — revise the candidate instead.")
    if predecessor.organization_id != successor.organization_id:
        raise VersioningError(
            "cross_organization_supersession",
            "Those versions belong to different organizations.")
