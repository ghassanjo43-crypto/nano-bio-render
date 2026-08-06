"""Storage and workflow for the Experimental Validation Registry.

Follows the existing service conventions: ownership before existence, no
scientific judgement of its own — it loads records, hands them to
``validation.eligibility``, and stores what comes back.

Three rules enforced here rather than in the interface
------------------------------------------------------
1. **Approval freezes a version.** Every mutating call checks
   ``permissions.require`` first, and an approved version has no capability
   that edits it. A correction creates a new version.
2. **A performer cannot approve their own record.** Checked here and again by
   the eligibility gate, so a record stored by any route still reports it.
3. **Nothing scientific is deleted.** Supersession sets a pointer; the
   superseded row stays, and the audit trail outlives both.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.auth_models import UserRole
from nanobio_studio.app.db.validation_models import (
    AttachmentState,
    Candidate, CandidateVersion, ContradictionResolution, ExperimentAttachment,
    ExperimentVersion, Measurement, ValidationAuditLog, ValidationExperiment,
)
from nanobio_studio.app.db.workspace_models import StoredRun
from nanobio_studio.app.science.statuses import EvidenceLevel, ReadinessArea
# Imported at module level, not inside each function. The reliance boundary is
# not an optional extra that a call site may or may not reach for, and a
# deferred import reads as though it were.
from nanobio_studio.app.services import candidate_versioning as _cvs
from nanobio_studio.app.validation.eligibility import (
    EligibilityVerdict, ExperimentFacts, evaluate_e3_eligibility,
)
from nanobio_studio.app.validation.permissions import (
    Capability, ExperimentContext, PermissionDenied, RegistryActor, require,
)
from nanobio_studio.app.validation.storage import (
    AttachmentStore, default_store, validate_attachment,
)
from nanobio_studio.app.validation.vocabulary import (
    ALLOWED_TRANSITIONS, REGISTRY_VERSION, AttachmentCategory, AuditEvent,
    ExperimentStatus, ExperimentSubtype, ReviewDecision, purpose_is_permitted,
)

__all__ = [
    "ValidationError",
    "canonical_snapshot",
    "snapshot_checksum",
    "create_candidate",
    "create_candidate_version",
    "create_experiment",
    "update_draft",
    "add_measurements",
    "record_attachment",
    "upload_attachment",
    "read_attachment",
    "remove_attachment",
    "submit_version",
    "start_review",
    "record_decision",
    "create_revision",
    "evaluate_version",
    "approved_evidence_for_study",
    "audit_trail",
    "resolve_contradiction",
    "list_resolutions",
]


class ValidationError(RuntimeError):
    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Candidate snapshots
# ---------------------------------------------------------------------------

def canonical_snapshot(design_inputs: dict[str, Any]) -> str:
    """Canonical JSON for a candidate snapshot.

    Sorted keys and fixed separators, so the checksum depends on the content
    and not on dictionary ordering. Without this, re-serialising the same
    formulation could produce a different checksum and fail the integrity gate
    for no scientific reason.
    """
    return json.dumps(design_inputs, sort_keys=True, separators=(",", ":"),
                      default=str)


def snapshot_checksum(snapshot_json: str) -> str:
    return hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()


async def _audit(session: AsyncSession, *, event: AuditEvent,
                 actor_id: int | None, experiment_id: int | None = None,
                 version_id: int | None = None,
                 candidate_version_id: int | None = None,
                 candidate_id: int | None = None,
                 organization_id: int | None = None,
                 reason: str | None = None,
                 summary: str | None = None) -> None:
    """Append one audit row. Never updates, never deletes.

    Both text fields go through ``redact`` rather than a bare slice. A slice
    bounds the length of a leak; it does not stop one. This trail outlives
    every record it describes, so a clinical value written into a summary
    survives the deletion of the assessment it came from.
    """
    from nanobio_studio.app.services.audit_redaction import (
        MAX_REASON, MAX_SUMMARY, redact,
    )

    audit_row = ValidationAuditLog(
        organization_id=organization_id,
        event=event, actor_id=actor_id, experiment_id=experiment_id,
        experiment_version_id=version_id,
        candidate_version_id=candidate_version_id,
        candidate_id=candidate_id,
        reason=redact(reason, limit=MAX_REASON),
        summary=redact(summary, limit=MAX_SUMMARY),
    )
    session.add(audit_row)
    await session.flush()
    if experiment_id is not None:
        from nanobio_studio.app.services.notification_service import (
            surface_experiment_event,
        )
        await surface_experiment_event(
            session, event_value=event.value,
            experiment_id=experiment_id,
            experiment_version_id=version_id,
            audit_event_id=audit_row.id, actor_id=actor_id)


def _context(version: ExperimentVersion,
             experiment: ValidationExperiment) -> ExperimentContext:
    return ExperimentContext(
        owner_id=experiment.owner_id,
        status=version.status,
        performed_by=version.performed_by,
    )


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

async def create_candidate(session: AsyncSession, *, actor: RegistryActor,
                           study_id: int, code: str, name: str,
                           description: str | None = None) -> Candidate:
    run = await session.get(StoredRun, study_id)
    if run is None:
        raise ValidationError("study_not_found",
                              "The requested study does not exist.")

    # Reachability is decided by the route's scoped resolver, which applies
    # the organization and assigned-study predicates. The ownership test that
    # used to live here was wrong in both directions — it refused a colleague
    # legitimately assigned to the study, and accepted a former owner who had
    # since been removed from the organization — and it is exactly the
    # predicate the organization work replaced everywhere else.

    candidate = Candidate(
        # Inherited from the study rather than from the request. A
        # client-supplied organization would be a client-chosen tenant, and
        # leaving it NULL (which is what happened before) makes the row
        # invisible to every scoped read, including its author's.
        organization_id=run.organization_id,
        study_id=study_id, project_id=run.project_id, owner_id=actor.user_id,
        code=code, name=name, description=description)
    session.add(candidate)
    await session.flush()
    await _audit(session, event=AuditEvent.CREATED, actor_id=actor.user_id,
                 candidate_id=candidate.id,
                 organization_id=candidate.organization_id,
                 summary=f"candidate {code} created")
    return candidate


async def _next_candidate_version_number(session: AsyncSession,
                                         candidate_id: int) -> int:
    """MAX(version_number) + 1, not COUNT(*) + 1.

    Counting rows gives the wrong answer the moment a version is ever removed,
    and it gave a *duplicate* answer under concurrency — two callers counting
    N both wrote N+1. The unique constraint turned that into an integrity
    error rather than corruption, but the loser got a database exception
    instead of a version. MAX+1 still races; the difference is that the
    retry in `candidate_versioning.create_revision` can resolve it, because
    the next attempt reads a maximum that has moved.
    """
    from sqlalchemy import func

    highest = (await session.execute(
        select(func.max(CandidateVersion.version_number))
        .where(CandidateVersion.candidate_id == candidate_id))).scalar()
    return int(highest or 0) + 1


async def create_candidate_version(
    session: AsyncSession, *, actor: RegistryActor, candidate_id: int,
    design_inputs: dict[str, Any], note: str | None = None,
) -> CandidateVersion:
    """Freeze the formulation as it stands.

    The snapshot is a copy, never a reference. A reference would follow later
    edits and silently re-attribute finished experiments to a material that was
    never tested.
    """
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        raise ValidationError("candidate_not_found",
                              "The requested candidate does not exist.")

    snapshot = canonical_snapshot(design_inputs)

    number = await _next_candidate_version_number(session, candidate_id)
    version = CandidateVersion(
        # Inherited from the candidate. See `create_candidate` for why this
        # is not taken from the request and must not be left NULL.
        organization_id=candidate.organization_id,
        candidate_id=candidate_id,
        version_number=number,
        revision_label=f"v{number}",
        design_snapshot_json=snapshot,
        snapshot_checksum=snapshot_checksum(snapshot),
        note=note,
        created_by=actor.user_id,
    )
    session.add(version)
    await session.flush()
    await _audit(session, event=AuditEvent.VERSION_CREATED,
                 actor_id=actor.user_id, candidate_version_id=version.id,
                 candidate_id=candidate.id,
                 organization_id=candidate.organization_id,
                 reason=note,
                 summary=f"candidate version {version.version_number}")
    return version


# ---------------------------------------------------------------------------
# Scientific reliance: the locking boundary
# ---------------------------------------------------------------------------

#: Every operation that causes a candidate version to be relied upon, and the
#: words that go in the lock reason.
#:
#: Defined in ``candidate_versioning`` and re-exported here. One table, because
#: the registry and the dependent-artefact service both write lock reasons and
#: two copies would drift — a version frozen by a report and one frozen by an
#: export would end up explaining themselves in different vocabularies.
RELIANCE_REASONS: dict[str, str] = _cvs.RELIANCE_REASONS


async def _rely_on_candidate_version(
    session: AsyncSession, *, candidate_version_id: int | None,
    reason_key: str, actor_id: int | None,
) -> bool:
    """Lock the candidate version a dependent record is about to rely on.

    Resolves the id and delegates to ``candidate_versioning.rely_on_version``,
    which is the narrowest authoritative boundary for the immutability rule.
    This wrapper exists because the registry's call sites hold an *id* — from a
    request, from an experiment version — and the boundary takes the row, so
    that a caller who already has it cannot be made to re-fetch it.

    Why the boundary is below the service rather than in the routes
    ---------------------------------------------------------------
    Route discipline is a convention, and a convention is one new endpoint away
    from being broken silently. A caller that reaches a dependent record at all
    has already been through here — including a future route, a background job,
    and a script.

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
    if candidate_version_id is None:
        return False

    version = await session.get(CandidateVersion, candidate_version_id)
    if version is None:
        # The caller resolves reachability; a missing row here means the
        # dependent record references something that does not exist, which the
        # foreign key will refuse on flush. Not this function's error to raise.
        return False

    return await _cvs.rely_on_version(
        session, version=version, reason_key=reason_key, actor_id=actor_id)


async def _rely_via_experiment_version(
    session: AsyncSession, *, version: ExperimentVersion, reason_key: str,
    actor_id: int | None,
) -> bool:
    """Convenience for the paths that hold an experiment version."""
    return await _rely_on_candidate_version(
        session, candidate_version_id=version.candidate_version_id,
        reason_key=reason_key, actor_id=actor_id)


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

async def create_experiment(
    session: AsyncSession, *, actor: RegistryActor, candidate_version_id: int,
    subtype: ExperimentSubtype, purpose: ReadinessArea, title: str,
    code: str, performed_by: int | None = None,
) -> tuple[ValidationExperiment, ExperimentVersion]:
    """Create an experiment and its first draft version.

    The purpose is fixed at creation and the subtype/purpose pairing is checked
    here as well as at the gate. Refusing it up front means an investigator
    finds out before doing the work, not after.
    """
    if actor.role is UserRole.VIEWER:
        raise PermissionDenied(Capability.CREATE_EXPERIMENT,
                               "Viewers cannot create experiments.")
    if actor.role is UserRole.ADMIN:
        raise PermissionDenied(
            Capability.CREATE_EXPERIMENT,
            "Administrators manage access and do not author scientific "
            "records.")

    cversion = await session.get(CandidateVersion, candidate_version_id)
    if cversion is None:
        raise ValidationError("candidate_version_not_found",
                              "The requested candidate version does not exist.")
    candidate = await session.get(Candidate, cversion.candidate_id)
    assert candidate is not None

    if not purpose_is_permitted(subtype, purpose):
        raise ValidationError(
            "purpose_not_permitted",
            f"A {subtype.value.replace('_', ' ')} assay is not accepted as "
            f"evidence for {purpose.value.replace('_', ' ')}.",
            "An in-vitro measurement cannot evidence a purpose it does not "
            "observe. Choose a purpose this method can speak to.")

    # Reliance begins here: from this point the formulation has been used to
    # design an experiment, and editing it would silently re-describe what was
    # tested. Locked in the same transaction as the experiment itself.
    await _rely_on_candidate_version(
        session, candidate_version_id=cversion.id, reason_key="experiment",
        actor_id=actor.user_id)

    experiment = ValidationExperiment(
        # Inherited from the candidate, exactly as `create_candidate` inherits
        # from the study. Left NULL, these rows were invisible to every scoped
        # read until the next startup backfill claimed them — and the backfill
        # claims unassigned rows for the LEGACY organization, so on a
        # multi-organization installation a new experiment would have been
        # adopted by the wrong tenant. Found by the dependency-binding tests,
        # which asserted that an attachment agrees with its candidate version
        # about who owns it.
        organization_id=candidate.organization_id,
        code=code, candidate_id=candidate.id, study_id=candidate.study_id,
        project_id=candidate.project_id, owner_id=actor.user_id,
        subtype=subtype, purpose=purpose, title=title)
    session.add(experiment)
    await session.flush()

    version = ExperimentVersion(
        organization_id=candidate.organization_id,
        experiment_id=experiment.id, version_number=1,
        candidate_version_id=candidate_version_id,
        status=ExperimentStatus.DRAFT,
        performed_by=performed_by if performed_by is not None else actor.user_id,
    )
    session.add(version)
    await session.flush()

    await _audit(session, event=AuditEvent.CREATED, actor_id=actor.user_id,
                 experiment_id=experiment.id, version_id=version.id,
                 candidate_version_id=candidate_version_id,
                 summary=f"{code} v1 created ({subtype.value} -> {purpose.value})")
    return experiment, version


async def update_draft(session: AsyncSession, *, actor: RegistryActor,
                       version_id: int, fields: dict[str, Any]) -> ExperimentVersion:
    """Edit a draft. Refused on any frozen version."""
    version = await session.get(ExperimentVersion, version_id)
    if version is None:
        raise ValidationError("version_not_found",
                              "The requested experiment version does not exist.")
    experiment = await session.get(ValidationExperiment, version.experiment_id)
    assert experiment is not None

    require(actor, _context(version, experiment), Capability.EDIT_DRAFT)

    # Only declared columns are writable, and never the workflow or decision
    # fields — those move through their own transitions, which audit.
    forbidden = {
        "id", "experiment_id", "version_number", "status", "submitted_at",
        "submitted_by", "review_started_at", "reviewer_id", "decision_at",
        "decision_by", "approved_level", "frozen_at", "eligibility_json",
        "eligibility_ruleset_version", "superseded_by_version_id",
    }
    changed: list[str] = []
    for key, value in fields.items():
        if key in forbidden or not hasattr(version, key):
            continue
        setattr(version, key, value)
        changed.append(key)

    # Recorded the first time criteria are set, so "predefined" is checkable
    # against the first measurement rather than asserted.
    if "acceptance_criteria_json" in changed and not version.acceptance_criteria_recorded_at:
        version.acceptance_criteria_recorded_at = _utcnow()

    version.updated_at = _utcnow()
    await session.flush()
    await _audit(session, event=AuditEvent.EDITED, actor_id=actor.user_id,
                 experiment_id=experiment.id, version_id=version.id,
                 summary=f"edited: {', '.join(sorted(changed)) or 'no change'}")
    return version


async def add_measurements(session: AsyncSession, *, actor: RegistryActor,
                           version_id: int,
                           rows: Sequence[dict[str, Any]]) -> list[Measurement]:
    version = await session.get(ExperimentVersion, version_id)
    if version is None:
        raise ValidationError("version_not_found",
                              "The requested experiment version does not exist.")
    experiment = await session.get(ValidationExperiment, version.experiment_id)
    assert experiment is not None
    require(actor, _context(version, experiment), Capability.EDIT_DRAFT)

    # Measured data describes the material as it stood. Editing the
    # formulation afterwards would re-label what was actually measured.
    await _rely_via_experiment_version(
        session, version=version, reason_key="measurement",
        actor_id=actor.user_id)

    created: list[Measurement] = []
    for row in rows:
        measurement = Measurement(
            version_id=version_id,
            # Inherited from the experiment version, for the same reason every
            # other row here inherits it: a NULL organization is invisible to
            # every scoped read until a backfill claims it, and the backfill
            # claims unassigned rows for the legacy organization.
            organization_id=version.organization_id,
            **{k: v for k, v in row.items() if hasattr(Measurement, k)})
        session.add(measurement)
        created.append(measurement)
    await session.flush()
    await _audit(session, event=AuditEvent.EDITED, actor_id=actor.user_id,
                 experiment_id=experiment.id, version_id=version_id,
                 summary=f"{len(created)} measurement(s) recorded")
    return created


def _malware_scanning_enabled() -> bool:
    """Whether a scanner is actually connected.

    Read from configuration on every upload rather than captured at import, so
    connecting a scanner is a restart rather than a redeploy. Defaults to
    false, and the API says "not scanned" rather than "clean" — a platform that
    claims scanning it does not perform is worse than one that admits it,
    because the claim is what stops anybody adding a scanner.
    """
    from nanobio_studio.app.core.config import settings
    return bool(settings.storage_malware_scanning_enabled)


def _unservable_reason(attachment) -> tuple[str, str, str]:
    """Why this attachment cannot be downloaded, in the caller's terms."""
    state = attachment.state
    if state is AttachmentState.PENDING_UPLOAD:
        return ("attachment_incomplete",
                "This upload did not finish, so there is nothing to download.",
                "It is recorded as incomplete rather than deleted, so it can "
                "be cleaned up and so the gap is visible.")
    if state is AttachmentState.PENDING_SCAN:
        return ("attachment_pending_scan",
                "This file is waiting for a malware scan.",
                "It will become available when the scanner reports.")
    if state is AttachmentState.QUARANTINED:
        return ("attachment_quarantined",
                "This file was quarantined and will not be served.",
                "It is retained for investigation. Ask an administrator.")
    if state is AttachmentState.DELETE_PENDING:
        return ("attachment_deleting",
                "This file is being deleted.",
                "Deletion was requested and has not yet been confirmed.")
    if state is AttachmentState.DELETED:
        return ("attachment_deleted",
                "This file has been deleted.",
                "Its metadata and audit history are retained, so the record "
                "of the work it supported survives the file itself.")
    return ("attachment_missing",
            "The stored file is not present.",
            "Its metadata is retained so the gap is visible rather than "
            "silent.")


async def record_attachment(
    session: AsyncSession, *, actor: RegistryActor, version_id: int,
    category: AttachmentCategory, original_filename: str, mime_type: str,
    size_bytes: int, checksum_sha256: str, storage_key: str,
) -> ExperimentAttachment:
    version = await session.get(ExperimentVersion, version_id)
    if version is None:
        raise ValidationError("version_not_found",
                              "The requested experiment version does not exist.")
    experiment = await session.get(ValidationExperiment, version.experiment_id)
    assert experiment is not None
    require(actor, _context(version, experiment), Capability.ADD_ATTACHMENT)

    # Attaching evidence to work is reliance on the formulation that work was
    # performed against. Same transaction as the attachment row.
    await _rely_via_experiment_version(
        session, version=version, reason_key="attachment",
        actor_id=actor.user_id)

    attachment = ExperimentAttachment(
        version_id=version_id, category=category,
        organization_id=version.organization_id,
        # Bound to the exact formulation, not left to be inferred through the
        # experiment version by whoever queries next.
        candidate_version_id=version.candidate_version_id,
        original_filename=original_filename, mime_type=mime_type,
        size_bytes=size_bytes, checksum_sha256=checksum_sha256,
        storage_key=storage_key, uploaded_by=actor.user_id)
    session.add(attachment)
    await session.flush()
    await _audit(session, event=AuditEvent.ATTACHMENT_ADDED,
                 actor_id=actor.user_id, experiment_id=experiment.id,
                 version_id=version_id,
                 candidate_version_id=version.candidate_version_id,
                 candidate_id=experiment.candidate_id,
                 organization_id=version.organization_id,
                 summary=f"{category.value} attached ({size_bytes} bytes)")
    return attachment


async def upload_attachment(
    session: AsyncSession, *, actor: RegistryActor, version_id: int,
    category: AttachmentCategory, filename: str, declared_mime: str,
    content: bytes, store: "AttachmentStore | None" = None,
) -> ExperimentAttachment:
    """Validate, reserve, store, verify, publish — in that order.

    Why five steps and not two
    --------------------------
    The database and the object store are separate systems, and a write can
    succeed in one and fail in the other. The previous two-step version — put
    the bytes, then insert the row — had a window in which an upload that
    crashed between them left bytes in the store that no row referenced and
    nothing would ever find.

    So the row is created **first**, in ``PENDING_UPLOAD``. That does three
    things at once: it allocates the identifier the object key is built from,
    it makes the attachment unservable until it is finished, and it turns the
    orphan case into a *row* — which reconciliation can see — rather than a
    loose object nobody knows about.

    What each step guarantees:

    1. **Validate** — size, type, magic bytes, filename. A refused file leaves
       no row and no bytes.
    2. **Reserve** — insert ``PENDING_UPLOAD`` and flush, so ``attachment.id``
       exists and can go into the key.
    3. **Store** — write the object under the derived key. A failure leaves the
       row in ``PENDING_UPLOAD`` with the error code recorded; the caller sees
       a failure and reconciliation sees a stuck row.
    4. **Verify** — compare the store's own reported size and checksum. The
       store recomputed the digest independently; a disagreement means the two
       halves saw different bytes, and nothing is published.
    5. **Publish** — move to ``AVAILABLE``, or ``PENDING_SCAN`` when a scanner
       is actually connected. Only now is it downloadable.

    Idempotent under retry because the key carries 128 random bits: a retried
    upload writes a new object rather than silently overwriting a finalised one.
    """
    version = await session.get(ExperimentVersion, version_id)
    if version is None:
        raise ValidationError("version_not_found",
                              "The requested experiment version does not exist.")
    experiment = await session.get(ValidationExperiment, version.experiment_id)
    assert experiment is not None
    require(actor, _context(version, experiment), Capability.ADD_ATTACHMENT)

    # 1. Validate. Nothing is written until this passes.
    checked = validate_attachment(filename=filename,
                                  declared_mime=declared_mime,
                                  content=content, category=category)

    active = store or default_store()

    # Reliance begins at the reservation, not at the publish. A file that
    # never finishes uploading was still evidence somebody set out to attach
    # to this formulation, and the row it leaves behind refers to it.
    await _rely_via_experiment_version(
        session, version=version, reason_key="attachment",
        actor_id=actor.user_id)

    # 2. Reserve. The row owns the identifier the key is built from.
    attachment = ExperimentAttachment(
        version_id=version_id, category=category,
        organization_id=version.organization_id,
        candidate_version_id=version.candidate_version_id,
        original_filename=checked.display_name, mime_type=checked.mime_type,
        size_bytes=checked.size_bytes,
        checksum_sha256=checked.checksum_sha256,
        storage_key="",
        state=AttachmentState.PENDING_UPLOAD,
        state_changed_at=_utcnow(),
        uploaded_by=actor.user_id)
    session.add(attachment)
    await session.flush()

    await _audit(session, event=AuditEvent.ATTACHMENT_ADDED,
                 actor_id=actor.user_id, experiment_id=experiment.id,
                 version_id=version_id,
                 summary=f"{category.value} upload initiated "
                         f"({checked.size_bytes} bytes)")

    # Committed here, deliberately, against this module's usual convention
    # that services flush and routes commit.
    #
    # The reservation exists to survive the failure of the step after it. The
    # route's error handler rolls the session back, so a merely-flushed row
    # would vanish at exactly the moment it became useful — leaving, in the
    # worst case, bytes in the object store that no row references and nothing
    # can find. Committing makes the incomplete upload a durable, visible fact
    # that reconciliation can report and an operator can clear up.
    await session.commit()

    # 3. Store, under a key derived from immutable identifiers.
    try:
        blob = active.put(
            content, checksum_sha256=checked.checksum_sha256,
            organization_id=version.organization_id,
            attachment_id=attachment.id)
    except Exception as exc:  # noqa: BLE001 — recorded, then re-raised
        attachment.last_error_code = getattr(exc, "code", "storage_put_failed")
        attachment.state_changed_at = _utcnow()
        # Committed for the same reason as the reservation: the caller's error
        # handler rolls back, and the record of *why* this upload is stuck is
        # the thing an operator needs most.
        await session.commit()
        raise ValidationError(
            "attachment_storage_failed",
            "The file could not be stored. Nothing was attached.",
            "The upload is recorded as incomplete so it can be cleaned up; no "
            "partial attachment is visible as evidence.") from exc

    attachment.storage_key = blob.storage_key
    attachment.storage_backend = blob.backend
    attachment.storage_bucket = blob.bucket

    # 4. Verify against the store's own view before publishing.
    if (blob.checksum_sha256 != checked.checksum_sha256
            or blob.size_bytes != checked.size_bytes):
        attachment.last_error_code = "checksum_mismatch"
        attachment.state_changed_at = _utcnow()
        await session.commit()
        raise ValidationError(
            "attachment_checksum_mismatch",
            "The stored file does not match what was received.",
            "Nothing has been published. The two halves of the upload saw "
            "different bytes, which is what the checksum exists to catch.")

    # 5. Publish.
    attachment.state = (AttachmentState.PENDING_SCAN
                        if _malware_scanning_enabled()
                        else AttachmentState.AVAILABLE)
    attachment.state_changed_at = _utcnow()
    await session.flush()

    await _audit(session, event=AuditEvent.ATTACHMENT_ADDED,
                 actor_id=actor.user_id, experiment_id=experiment.id,
                 version_id=version_id,
                 summary=f"{category.value} upload completed, state "
                         f"{attachment.state.value}")
    return attachment


async def read_attachment(
    session: AsyncSession, *, actor: RegistryActor, attachment_id: int,
    store: "AttachmentStore | None" = None,
) -> tuple[ExperimentAttachment, bytes]:
    """Fetch an attachment's bytes, verifying integrity on the way out.

    A stored file whose checksum no longer matches is refused rather than
    served: silently returning altered bytes would undermine every result
    attributed to them.
    """
    attachment = await session.get(ExperimentAttachment, attachment_id)
    if attachment is None:
        raise ValidationError("attachment_not_found",
                              "The requested attachment does not exist.")
    version = await session.get(ExperimentVersion, attachment.version_id)
    assert version is not None
    experiment = await session.get(ValidationExperiment, version.experiment_id)
    assert experiment is not None

    # Reading is a VIEW capability; every authenticated role holds it, and the
    # route layer has already established who the caller is.
    require(actor, _context(version, experiment), Capability.VIEW)

    # The lifecycle state decides servability, and each unservable state gets
    # its own sentence. "Not available" for a file that is quarantined, still
    # uploading and deleted would be three different situations wearing one
    # message, and the user cannot act on any of them.
    if attachment.state is not AttachmentState.AVAILABLE:
        await _audit(session, event=AuditEvent.ACCESSED,
                     actor_id=actor.user_id, experiment_id=experiment.id,
                     version_id=version.id,
                     summary=f"attachment download refused, state "
                             f"{attachment.state.value}")
        raise ValidationError(*_unservable_reason(attachment))

    active = store or default_store()
    try:
        content = active.get(attachment.storage_key)
    except KeyError as exc:
        # The row says it should be there and the store says it is not. Record
        # that, so reconciliation reports a finding rather than this being
        # rediscovered by the next person who asks for the file.
        attachment.state = AttachmentState.MISSING
        attachment.state_changed_at = _utcnow()
        attachment.last_error_code = "object_missing"
        # Committed so the finding outlives the failed request. Otherwise the
        # gap is rediscovered by every subsequent reader and recorded by none
        # of them.
        await session.commit()
        raise ValidationError(
            "attachment_missing",
            "The stored file is no longer present.",
            "Its metadata is retained so the gap is visible rather than "
            "silent, and it is now flagged for reconciliation.") from exc
    except Exception as exc:  # noqa: BLE001 — storage outage, not absence
        # Deliberately NOT marked MISSING. An unreachable store is not an
        # absent object, and flagging every attachment as missing during an
        # outage would turn a ten-minute incident into a data-integrity alarm.
        raise ValidationError(
            "attachment_unavailable",
            "The file store could not be reached. The attachment has not been "
            "lost.",
            "Try again; this is a storage availability problem, not a missing "
            "record.") from exc

    if hashlib.sha256(content).hexdigest() != attachment.checksum_sha256:
        attachment.last_error_code = "checksum_mismatch"
        await session.flush()
        raise ValidationError(
            "attachment_corrupt",
            "The stored file no longer matches its recorded checksum.",
            "It has not been served. Every result attributed to it should be "
            "treated as unsupported until this is resolved.")

    await _audit(session, event=AuditEvent.ACCESSED, actor_id=actor.user_id,
                 experiment_id=experiment.id, version_id=version.id,
                 summary=f"attachment {attachment.category.value} download "
                         f"authorized")
    return attachment, content


async def remove_attachment(
    session: AsyncSession, *, actor: RegistryActor, attachment_id: int,
    store: "AttachmentStore | None" = None,
) -> None:
    """Remove an attachment from a DRAFT version only.

    Once a version is submitted its attachments are part of what was reviewed.
    Removing one afterwards would change the evidence behind a decision without
    changing the decision — so it is refused, and a correction goes through a
    new version like every other change.
    """
    attachment = await session.get(ExperimentAttachment, attachment_id)
    if attachment is None:
        raise ValidationError("attachment_not_found",
                              "The requested attachment does not exist.")
    version = await session.get(ExperimentVersion, attachment.version_id)
    assert version is not None
    experiment = await session.get(ValidationExperiment, version.experiment_id)
    assert experiment is not None

    if version.status is not ExperimentStatus.DRAFT:
        raise ValidationError(
            "attachment_immutable",
            f"This version is '{version.status.value}'. Its attachments are "
            "part of the record that was submitted for review and cannot be "
            "removed.",
            "Create a new version if the evidence needs to change.")

    require(actor, _context(version, experiment), Capability.ADD_ATTACHMENT)

    # Mark first, delete second, confirm third.
    #
    # Deleting the object and then the row leaves a window in which a crash
    # loses the only reference to bytes that are still in the bucket. Marking
    # first means the worst case is a tombstone somebody can retry — and a
    # tombstone is a state an operator can act on, which a silently orphaned
    # object is not.
    attachment.state = AttachmentState.DELETE_PENDING
    attachment.state_changed_at = _utcnow()
    attachment.delete_attempts += 1
    await session.flush()
    await _audit(session, event=AuditEvent.ATTACHMENT_REMOVED,
                 actor_id=actor.user_id, experiment_id=experiment.id,
                 version_id=version.id,
                 summary=f"{attachment.category.value} deletion requested")
    # Durable before the object is touched. A tombstone that a rollback erases
    # is not a tombstone — and "we told them it was deleted while the bytes
    # remained" is the one deletion outcome that must never happen quietly.
    await session.commit()

    try:
        (store or default_store()).delete(attachment.storage_key)
    except Exception as exc:  # noqa: BLE001 — retained as a retryable tombstone
        attachment.last_error_code = getattr(exc, "code",
                                             "storage_delete_failed")
        await session.commit()
        raise ValidationError(
            "attachment_delete_failed",
            "The file could not be removed from storage.",
            "It is recorded as pending deletion and will be retried. Telling "
            "you it was deleted while the bytes remain would be the one "
            "outcome that must never happen quietly.") from exc

    # Confirmed gone. The row survives so the audit history and the scientific
    # provenance survive with it — an experiment performed against a file is
    # still an experiment that was performed.
    attachment.state = AttachmentState.DELETED
    attachment.state_changed_at = _utcnow()
    attachment.content_removed_at = _utcnow()
    attachment.last_error_code = None
    await session.flush()
    await _audit(session, event=AuditEvent.ATTACHMENT_REMOVED,
                 actor_id=actor.user_id, experiment_id=experiment.id,
                 version_id=version.id,
                 summary=f"{attachment.category.value} deletion completed")


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

def _assert_transition(current: ExperimentStatus,
                       target: ExperimentStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise ValidationError(
            "illegal_transition",
            f"An experiment cannot move from '{current.value}' to "
            f"'{target.value}'.",
            "The workflow is Draft to Submitted to Under review to a "
            "decision. Corrections create a new version rather than reopening "
            "a reviewed one.")


async def submit_version(session: AsyncSession, *, actor: RegistryActor,
                         version_id: int) -> ExperimentVersion:
    """Freeze the version and hand it to review."""
    version = await session.get(ExperimentVersion, version_id)
    if version is None:
        raise ValidationError("version_not_found",
                              "The requested experiment version does not exist.")
    experiment = await session.get(ValidationExperiment, version.experiment_id)
    assert experiment is not None

    require(actor, _context(version, experiment), Capability.SUBMIT)
    _assert_transition(version.status, ExperimentStatus.SUBMITTED)

    await _rely_via_experiment_version(
        session, version=version, reason_key="submission",
        actor_id=actor.user_id)

    version.status = ExperimentStatus.SUBMITTED
    version.submitted_at = _utcnow()
    version.submitted_by = actor.user_id
    # Frozen here, not at approval. This is what makes "the criteria predated
    # the results" a fact about the record rather than a claim about intent.
    version.frozen_at = version.submitted_at
    await session.flush()
    await _audit(session, event=AuditEvent.SUBMITTED, actor_id=actor.user_id,
                 experiment_id=experiment.id, version_id=version_id,
                 summary="submitted; version frozen")
    return version


async def start_review(session: AsyncSession, *, actor: RegistryActor,
                       version_id: int) -> ExperimentVersion:
    version = await session.get(ExperimentVersion, version_id)
    if version is None:
        raise ValidationError("version_not_found",
                              "The requested experiment version does not exist.")
    experiment = await session.get(ValidationExperiment, version.experiment_id)
    assert experiment is not None

    require(actor, _context(version, experiment), Capability.START_REVIEW)
    _assert_transition(version.status, ExperimentStatus.UNDER_REVIEW)

    await _rely_via_experiment_version(
        session, version=version, reason_key="review", actor_id=actor.user_id)

    version.status = ExperimentStatus.UNDER_REVIEW
    version.review_started_at = _utcnow()
    version.reviewer_id = actor.user_id
    await session.flush()
    await _audit(session, event=AuditEvent.REVIEW_STARTED,
                 actor_id=actor.user_id, experiment_id=experiment.id,
                 version_id=version_id, summary="review started")
    return version


async def record_decision(
    session: AsyncSession, *, actor: RegistryActor, version_id: int,
    decision: ReviewDecision, comments: str,
) -> tuple[ExperimentVersion, EligibilityVerdict | None]:
    """Record a review outcome.

    On approval the eligibility verdict is computed and stored **verbatim**
    with its ruleset version. It is never recomputed for display: a historical
    approval must say what was concluded then, not what today's rules would
    conclude.

    An approval whose gates do not all pass is refused. The reviewer's judgement
    governs the gates that call for judgement — replicate sufficiency, criteria
    that are not machine-checkable — but it cannot substitute for a missing
    protocol or absent raw data.
    """
    version = await session.get(ExperimentVersion, version_id)
    if version is None:
        raise ValidationError("version_not_found",
                              "The requested experiment version does not exist.")
    experiment = await session.get(ValidationExperiment, version.experiment_id)
    assert experiment is not None

    context = _context(version, experiment)
    capability = {
        ReviewDecision.APPROVE: Capability.APPROVE,
        ReviewDecision.REJECT: Capability.REJECT,
        ReviewDecision.REQUEST_REVISION: Capability.REQUEST_REVISION,
    }[decision]
    try:
        require(actor, context, capability)
    except PermissionDenied as exc:
        await _audit(session, event=AuditEvent.PERMISSION_DENIED,
                     actor_id=actor.user_id, experiment_id=experiment.id,
                     version_id=version_id,
                     summary=f"{capability.value} refused: {exc.reason[:200]}")
        raise

    # An approval names a formulation. If that formulation can still change,
    # the approval names nothing — so reliance is recorded before the decision
    # is, in the same transaction.
    await _rely_via_experiment_version(
        session, version=version, reason_key="decision",
        actor_id=actor.user_id)

    if not comments or not comments.strip():
        raise ValidationError(
            "comments_required",
            "A review decision must record the reviewer's comments.",
            "A decision without a stated reason cannot be reviewed by anybody "
            "else.")

    target = {
        ReviewDecision.APPROVE: ExperimentStatus.APPROVED,
        ReviewDecision.REJECT: ExperimentStatus.REJECTED,
        ReviewDecision.REQUEST_REVISION: ExperimentStatus.REVISION_REQUIRED,
    }[decision]
    _assert_transition(version.status, target)

    verdict: EligibilityVerdict | None = None
    if decision is ReviewDecision.APPROVE:
        verdict = await evaluate_version(session, version_id=version_id,
                                         assume_approved_by=actor.user_id)
        if not verdict.eligible:
            raise ValidationError(
                "not_eligible",
                "This experiment does not satisfy every E3 gate and cannot be "
                "approved for evidence promotion.",
                "; ".join(g.label for g in verdict.failed_gates))
        version.approved_level = EvidenceLevel.E3
        version.eligibility_json = json.dumps(verdict.to_dict())
        version.eligibility_ruleset_version = verdict.ruleset_version

    version.status = target
    version.decision_at = _utcnow()
    version.decision_by = actor.user_id
    version.decision_comments = comments
    version.frozen_at = version.frozen_at or version.decision_at
    await session.flush()

    await _audit(session, event=AuditEvent.REVIEW_DECISION,
                 actor_id=actor.user_id, experiment_id=experiment.id,
                 version_id=version_id,
                 summary=f"decision={decision.value}")
    await _audit(
        session,
        event=(AuditEvent.APPROVED if decision is ReviewDecision.APPROVE
               else AuditEvent.REJECTED),
        actor_id=actor.user_id, experiment_id=experiment.id,
        version_id=version_id,
        summary=f"status={target.value}")
    if verdict is not None:
        await _audit(session, event=AuditEvent.EVIDENCE_DECISION,
                     actor_id=actor.user_id, experiment_id=experiment.id,
                     version_id=version_id,
                     summary=(f"E3 granted for {experiment.purpose.value} "
                              f"under {verdict.ruleset_version}"))
    return version, verdict


async def create_revision(session: AsyncSession, *, actor: RegistryActor,
                          version_id: int,
                          candidate_version_id: int | None = None,
                          ) -> ExperimentVersion:
    """Supersede a version with a new draft, preserving the original.

    Copies the scientific content forward so a correction does not mean
    retyping everything, but resets every workflow and decision field: the new
    version has not been submitted, reviewed or approved, and must not inherit
    the appearance of having been.
    """
    old = await session.get(ExperimentVersion, version_id)
    if old is None:
        raise ValidationError("version_not_found",
                              "The requested experiment version does not exist.")
    experiment = await session.get(ValidationExperiment, old.experiment_id)
    assert experiment is not None

    if actor.role is UserRole.VIEWER:
        raise PermissionDenied(Capability.CREATE_EXPERIMENT,
                               "Viewers cannot create versions.")

    existing = (await session.execute(
        select(ExperimentVersion)
        .where(ExperimentVersion.experiment_id == experiment.id))).scalars().all()

    carried = {
        c.name: getattr(old, c.name)
        for c in ExperimentVersion.__table__.columns
        if c.name not in {
            "id", "experiment_id", "version_number", "status", "submitted_at",
            "submitted_by", "review_started_at", "reviewer_id", "decision_at",
            "decision_by", "decision_comments", "approved_level", "frozen_at",
            "eligibility_json", "eligibility_ruleset_version",
            "superseded_by_version_id", "created_at", "updated_at",
            "candidate_version_id",
        }
    }
    bound_version_id = candidate_version_id or old.candidate_version_id

    # Re-linking a correction to a different formulation is reliance on that
    # formulation, not merely on the old one. Locked in this transaction, so
    # there is no window in which the new version is named by an experiment
    # and its inputs can still be edited.
    await _rely_on_candidate_version(
        session, candidate_version_id=bound_version_id,
        reason_key="experiment", actor_id=actor.user_id)

    fresh = ExperimentVersion(
        experiment_id=experiment.id,
        version_number=len(existing) + 1,
        candidate_version_id=bound_version_id,
        status=ExperimentStatus.DRAFT,
        **carried,
    )
    session.add(fresh)
    await session.flush()

    # The old version is superseded, not deleted. Its decision, its comments
    # and its measurements stay exactly as they were.
    old.superseded_by_version_id = fresh.id
    old.status = ExperimentStatus.SUPERSEDED
    await session.flush()

    await _audit(session, event=AuditEvent.VERSION_CREATED,
                 actor_id=actor.user_id, experiment_id=experiment.id,
                 version_id=fresh.id,
                 summary=f"v{fresh.version_number} created from "
                         f"v{old.version_number}")
    await _audit(session, event=AuditEvent.SUPERSEDED, actor_id=actor.user_id,
                 experiment_id=experiment.id, version_id=old.id,
                 summary=f"superseded by v{fresh.version_number}")
    return fresh


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

async def evaluate_version(session: AsyncSession, *, version_id: int,
                           assume_approved_by: int | None = None,
                           ) -> EligibilityVerdict:
    """Build the facts and run the evaluator.

    ``assume_approved_by`` lets the approval path ask "would this be eligible
    if I approved it?" without writing anything first — which is what allows an
    ineligible approval to be refused rather than recorded and then undone.
    """
    version = await session.get(ExperimentVersion, version_id)
    if version is None:
        raise ValidationError("version_not_found",
                              "The requested experiment version does not exist.")
    experiment = await session.get(ValidationExperiment, version.experiment_id)
    assert experiment is not None
    cversion = await session.get(CandidateVersion, version.candidate_version_id)

    measurements = (await session.execute(
        select(Measurement).where(
            Measurement.version_id == version_id))).scalars().all()
    attachments = (await session.execute(
        select(ExperimentAttachment).where(
            ExperimentAttachment.version_id == version_id))).scalars().all()

    def _json_list(raw: str | None) -> list[dict[str, Any]]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else []

    first_measured = min((m.created_at for m in measurements), default=None)

    approved = (version.status is ExperimentStatus.APPROVED
                or assume_approved_by is not None)
    decision_by = (assume_approved_by if assume_approved_by is not None
                   else version.decision_by)

    facts = ExperimentFacts(
        subtype=experiment.subtype,
        purpose=experiment.purpose,
        status=version.status,
        requested_level=version.requested_level,
        candidate_version_id=version.candidate_version_id,
        candidate_snapshot_checksum=(cversion.snapshot_checksum
                                     if cversion else None),
        candidate_snapshot_recomputed=(
            snapshot_checksum(cversion.design_snapshot_json)
            if cversion else None),
        scientific_question=version.scientific_question,
        protocol_identifier=version.protocol_identifier,
        protocol_version=version.protocol_version,
        laboratory_name=version.laboratory_name,
        investigator_name=version.investigator_name,
        investigator_org=version.investigator_org,
        biological_model=version.biological_model,
        cell_line=version.cell_line,
        cell_source=version.cell_source,
        cell_authentication_status=version.cell_authentication_status,
        assay_method=version.assay_method,
        control_positive=version.control_positive,
        control_negative=version.control_negative,
        control_vehicle=version.control_vehicle,
        controls_not_applicable_reason=version.controls_not_applicable_reason,
        biological_replicates=version.biological_replicates,
        technical_replicates=version.technical_replicates,
        replicate_justification=version.replicate_justification,
        acceptance_criteria=_json_list(version.acceptance_criteria_json),
        acceptance_criteria_recorded_at=version.acceptance_criteria_recorded_at,
        acceptance_criteria_met=version.acceptance_criteria_met,
        measurements=[{
            "endpoint_name": m.endpoint_name,
            "result_numeric": m.result_numeric,
            "result_text": m.result_text,
            "result_unit": m.result_unit,
            "excluded": m.excluded,
            "exclusion_justification": m.exclusion_justification,
            "missing_value_reason": m.missing_value_reason,
        } for m in measurements],
        first_measurement_recorded_at=first_measured,
        attachment_categories=[a.category for a in attachments],
        raw_data_reference=version.raw_data_reference,
        statistical_method=version.statistical_method,
        statistical_method_not_applicable_reason=(
            version.statistical_method_not_applicable_reason),
        deviations=version.deviations,
        exclusions=version.exclusions,
        missing_data=version.missing_data,
        disclosures_confirmed=version.disclosures_confirmed,
        quality_issues=_json_list(version.quality_issues_json),
        provenance_declaration=version.provenance_declaration,
        approved=approved,
        performed_by=version.performed_by,
        decision_by=decision_by,
        reviewer_id=version.reviewer_id,
        decision_comments=version.decision_comments,
    )
    return evaluate_e3_eligibility(facts)


# ---------------------------------------------------------------------------
# The readiness bridge
# ---------------------------------------------------------------------------

async def approved_evidence_for_study(
    session: AsyncSession, *, study_id: int,
) -> dict[str, dict[str, Any]]:
    """Approved E3 evidence for a study, grouped by purpose.

    **Only approved versions are read.** A draft, a submitted record, a
    rejection and a superseded version all stay visible in the registry and
    none of them promotes anything — which is the point of having a review
    step at all.

    Returns a mapping the readiness engine consumes, keyed by the readiness
    area. Contradictions are reported rather than resolved: where approved
    records for one purpose disagree, the caller is told and holds the level.
    """
    try:
        rows = (await session.execute(
            select(ExperimentVersion, ValidationExperiment)
            .join(ValidationExperiment,
                  ValidationExperiment.id == ExperimentVersion.experiment_id)
            .where(ValidationExperiment.study_id == study_id,
                   ExperimentVersion.status == ExperimentStatus.APPROVED,
                   ExperimentVersion.approved_level == EvidenceLevel.E3)
        )).all()
    except OperationalError:
        # The registry tables are not present — a Phase 1 database that has
        # not yet run startup migrations, or a session built against a partial
        # schema.
        #
        # Returning "no approved evidence" is both the safe answer and the
        # correct one: with no registry there are no approvals, so every area
        # keeps its E0-E2 outcome exactly as Phase 1 computed it. Readiness
        # must not become unavailable because a Phase 2 table is missing —
        # that would make an upgrade able to break the feature it extends.
        await session.rollback()
        return {}

    by_purpose: dict[str, dict[str, Any]] = {}
    for version, experiment in rows:
        entry = by_purpose.setdefault(experiment.purpose.value, {
            "purpose": experiment.purpose.value,
            "level": EvidenceLevel.E3.value,
            "experiments": [],
            "outcomes": [],
            "contradiction": None,
            "ruleset_versions": set(),
        })
        entry["experiments"].append({
            "experiment_id": experiment.id,
            "code": experiment.code,
            "title": experiment.title,
            "subtype": experiment.subtype.value,
            "version_id": version.id,
            "version_number": version.version_number,
            "candidate_version_id": version.candidate_version_id,
            "approved_at": (version.decision_at.isoformat()
                            if version.decision_at else None),
            "ruleset_version": version.eligibility_ruleset_version,
        })
        entry["outcomes"].append(version.acceptance_criteria_met)
        if version.eligibility_ruleset_version:
            entry["ruleset_versions"].add(version.eligibility_ruleset_version)

    # Active resolutions, keyed by purpose. Read once rather than per entry.
    try:
        resolutions = {
            r.purpose.value: r for r in (await session.execute(
                select(ContradictionResolution)
                .where(ContradictionResolution.study_id == study_id,
                       ContradictionResolution.superseded_by_id.is_(None))
            )).scalars().all()
        }
    except OperationalError:
        await session.rollback()
        resolutions = {}

    for purpose_key, entry in by_purpose.items():
        outcomes = {o for o in entry["outcomes"] if o is not None}
        if len(outcomes) > 1:
            resolution = resolutions.get(purpose_key)

            # A resolution only covers the conflict it was recorded against.
            # An approved experiment added afterwards reopens the conflict:
            # a reviewer cannot settle evidence they never saw.
            considered = set()
            if resolution and resolution.considered_version_ids:
                considered = {int(v) for v
                              in resolution.considered_version_ids.split(",")
                              if v.strip().isdigit()}
            current = {e["version_id"] for e in entry["experiments"]}
            covers_current = resolution is not None and current <= considered

            if covers_current and resolution.resolved_level is not None:
                entry["level"] = resolution.resolved_level.value
                entry["contradiction"] = None
                entry["resolution"] = {
                    "id": resolution.id,
                    "rationale": resolution.rationale,
                    "resolved_by": resolution.resolved_by,
                    "resolved_at": resolution.resolved_at.isoformat(),
                    "resolved_level": resolution.resolved_level.value,
                    "considered_version_ids": sorted(considered),
                }
            else:
                entry["contradiction"] = (
                    "Approved experiments for this purpose disagree: at least "
                    "one met its acceptance criteria and at least one did "
                    "not. The level is held until a reviewer records a "
                    "resolution. Every record is preserved and the favourable "
                    "result has not been preferred."
                ) if not resolution else (
                    "Approved experiments for this purpose disagree, and the "
                    "recorded resolution "
                    + ("does not cover every current record — an experiment "
                       "was approved after it was written, so the conflict is "
                       "reopened."
                       if not covers_current else
                       "holds the level rather than settling it.")
                )
                # Held, not promoted. A contradiction is a reason to stop, not
                # a reason to pick.
                entry["level"] = None
                if resolution is not None:
                    entry["resolution"] = {
                        "id": resolution.id,
                        "rationale": resolution.rationale,
                        "resolved_by": resolution.resolved_by,
                        "resolved_at": resolution.resolved_at.isoformat(),
                        "resolved_level": (resolution.resolved_level.value
                                           if resolution.resolved_level
                                           else None),
                        "considered_version_ids": sorted(considered),
                        "covers_current_records": covers_current,
                    }
        entry["ruleset_versions"] = sorted(entry["ruleset_versions"])
    return by_purpose


async def audit_trail(session: AsyncSession, *, experiment_id: int,
                      limit: int = 200) -> list[ValidationAuditLog]:
    rows = (await session.execute(
        select(ValidationAuditLog)
        .where(ValidationAuditLog.experiment_id == experiment_id)
        .order_by(ValidationAuditLog.created_at.asc(),
                  ValidationAuditLog.id.asc())
        .limit(limit))).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# Contradiction resolution
# ---------------------------------------------------------------------------

async def resolve_contradiction(
    session: AsyncSession, *, actor: RegistryActor, study_id: int,
    purpose: ReadinessArea, rationale: str,
    resolved_level: EvidenceLevel | None,
    candidate_version_id: int | None = None,
) -> ContradictionResolution:
    """Record how conflicting approved evidence should be read.

    What this does NOT do, deliberately:

    * It does not touch a single conflicting experiment. Every one keeps its
      approval, its comments and its measurements exactly as they were —
      resolving a disagreement is a statement about how to read the records,
      not permission to edit them.
    * It does not delete or supersede any record. A superseding *resolution*
      points at the one it replaces; the evidence underneath is untouched.
    * It does not let a resolution invent a level. ``resolved_level`` may only
      be E3 (the conflict is settled in favour of promotion) or None (it stays
      held). Anything else would be a route to a level no experiment earned.

    Authorization: only somebody who could review or approve science. An
    administrator cannot resolve a contradiction for the same reason they
    cannot approve an experiment — access management is not a scientific
    judgement.
    """
    if actor.role is UserRole.ADMIN:
        raise PermissionDenied(
            Capability.APPROVE,
            "Administrators manage access and cannot resolve scientific "
            "contradictions. A resolution is a scientific reading of "
            "conflicting evidence and must come from a reviewer.")
    if actor.role is UserRole.VIEWER:
        raise PermissionDenied(
            Capability.APPROVE,
            "Viewers cannot resolve contradictions.")

    if not rationale or not rationale.strip():
        raise ValidationError(
            "rationale_required",
            "A contradiction resolution must record the reviewer's rationale.",
            "A resolution without a stated reason is an assertion, not a "
            "review, and cannot be weighed by anybody else.")

    if resolved_level is not None and resolved_level is not EvidenceLevel.E3:
        raise ValidationError(
            "level_not_grantable",
            f"A resolution may hold the purpose or settle it at E3; "
            f"{resolved_level.value} is not available.",
            "E4 to E6 require evidence this milestone does not record.")

    conflicting = (await session.execute(
        select(ExperimentVersion.id)
        .join(ValidationExperiment,
              ValidationExperiment.id == ExperimentVersion.experiment_id)
        .where(ValidationExperiment.study_id == study_id,
               ValidationExperiment.purpose == purpose,
               ExperimentVersion.status == ExperimentStatus.APPROVED)
    )).scalars().all()

    if len(conflicting) < 2:
        raise ValidationError(
            "no_contradiction",
            "There is no conflict to resolve for this purpose.",
            "A resolution is only meaningful where two or more approved "
            "experiments disagree.")

    # A performer of any of the conflicting experiments cannot resolve the
    # conflict between them: the same independence the approval gate requires.
    performers = (await session.execute(
        select(ExperimentVersion.performed_by)
        .where(ExperimentVersion.id.in_(conflicting)))).scalars().all()
    if actor.user_id in {p for p in performers if p is not None}:
        raise PermissionDenied(
            Capability.APPROVE,
            "You performed one of the conflicting experiments, so you cannot "
            "decide how the conflict is read.")

    # An earlier resolution is superseded, never overwritten: how a
    # disagreement was previously understood is part of the record.
    previous = (await session.execute(
        select(ContradictionResolution)
        .where(ContradictionResolution.study_id == study_id,
               ContradictionResolution.purpose == purpose,
               ContradictionResolution.superseded_by_id.is_(None))
    )).scalars().all()

    # A resolution that cites a specific version relies on it: the
    # reading it records is a reading OF that formulation.
    await _rely_on_candidate_version(
        session, candidate_version_id=candidate_version_id,
        reason_key="contradiction", actor_id=actor.user_id)

    resolution = ContradictionResolution(
        study_id=study_id, purpose=purpose,
        candidate_version_id=candidate_version_id,
        rationale=rationale.strip(),
        resolved_level=resolved_level,
        considered_version_ids=",".join(str(v) for v in sorted(conflicting)),
        resolved_by=actor.user_id,
    )
    session.add(resolution)
    await session.flush()

    for old in previous:
        old.superseded_by_id = resolution.id
    await session.flush()

    await _audit(
        session, event=AuditEvent.CONTRADICTION_RESOLVED,
        actor_id=actor.user_id,
        summary=(f"purpose={purpose.value} "
                 f"level={resolved_level.value if resolved_level else 'held'} "
                 f"versions={len(conflicting)}"))
    return resolution


async def list_resolutions(session: AsyncSession, *, study_id: int
                           ) -> list[ContradictionResolution]:
    rows = (await session.execute(
        select(ContradictionResolution)
        .where(ContradictionResolution.study_id == study_id)
        .order_by(ContradictionResolution.resolved_at.desc()))).scalars().all()
    return list(rows)
