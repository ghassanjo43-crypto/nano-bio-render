"""Authorized, safe notification fan-out for scientific workflow events."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.auth_models import User
from nanobio_studio.app.db.organization_models import (
    NotificationType, OrganizationMembership, StudyAssignment,
)
from nanobio_studio.app.db.validation_models import (
    Candidate, CandidateVersion, ExperimentVersion, ValidationExperiment,
)
from nanobio_studio.app.organizations.vocabulary import (
    ACTIVE_MEMBERSHIP_STATUSES, MembershipStatus, StudyRole,
)
from nanobio_studio.app.services.organization_service import notify


EVENTS = {
    "version_locked": (NotificationType.CANDIDATE_VERSION_LOCKED,
                       "A candidate version was locked."),
    "revision_created": (NotificationType.CANDIDATE_REVISION_CREATED,
                         "A candidate revision was created."),
    "reassessment_required": (
        NotificationType.SCIENTIFIC_REASSESSMENT_REQUIRED,
        "A candidate version requires scientific reassessment."),
    "recalculation_requested": (NotificationType.RECALCULATION_REQUIRED,
                                "A candidate version requires recalculation."),
    "recalculation_completed": (NotificationType.RECALCULATION_COMPLETED,
                                "Candidate recalculation completed."),
    "supersession_proposed": (NotificationType.SUPERSESSION_PROPOSED,
                              "A candidate supersession was proposed."),
    "supersession_accepted": (NotificationType.SUPERSESSION_ACCEPTED,
                              "A candidate supersession was accepted."),
    "supersession_refused": (NotificationType.SUPERSESSION_REFUSED,
                             "A candidate supersession was refused."),
    "report_generated": (NotificationType.REPORT_COMPLETED,
                         "A version-bound report completed."),
    "export_generated": (NotificationType.EXPORT_COMPLETED,
                         "A version-bound export completed."),
    "package_generated": (NotificationType.CRO_PACKAGE_COMPLETED,
                          "A version-bound CRO package completed."),
}

DECISION_EVENTS = {
    "reassessment_required", "supersession_proposed",
    "supersession_accepted", "supersession_refused",
}


async def surface_candidate_event(
    session: AsyncSession, *, event_value: str,
    version: CandidateVersion, audit_event_id: int,
    actor_id: int | None,
) -> int:
    """Fan out one candidate event to currently authorized study assignees.

    The summary is selected here, never copied from an audit reason or
    scientific payload.  This prevents measurements, filenames and conclusions
    from entering a generic notification row.
    """
    definition = EVENTS.get(event_value.lower())
    if definition is None or version.organization_id is None:
        return 0
    candidate = await session.get(Candidate, version.candidate_id)
    if candidate is None:
        return 0
    now = datetime.now(timezone.utc)
    roles = ({StudyRole.REVIEWER, StudyRole.APPROVER}
             if event_value.lower() in DECISION_EVENTS else set(StudyRole))
    recipients = (await session.execute(
        select(StudyAssignment.user_id)
        .join(OrganizationMembership, (
            OrganizationMembership.user_id == StudyAssignment.user_id) &
            (OrganizationMembership.organization_id ==
             StudyAssignment.organization_id))
        .join(User, User.id == StudyAssignment.user_id)
        .where(
            StudyAssignment.study_id == candidate.study_id,
            StudyAssignment.organization_id == version.organization_id,
            StudyAssignment.role.in_(roles),
            StudyAssignment.status == MembershipStatus.ACTIVE,
            OrganizationMembership.status.in_(ACTIVE_MEMBERSHIP_STATUSES),
            User.is_active.is_(True),
            or_(StudyAssignment.starts_at.is_(None),
                StudyAssignment.starts_at <= now),
            or_(StudyAssignment.expires_at.is_(None),
                StudyAssignment.expires_at > now),
            or_(OrganizationMembership.starts_at.is_(None),
                OrganizationMembership.starts_at <= now),
            or_(OrganizationMembership.expires_at.is_(None),
                OrganizationMembership.expires_at > now),
        ).distinct())).scalars().all()
    notification_type, summary = definition
    count = 0
    for recipient_id in recipients:
        if actor_id is not None and recipient_id == actor_id:
            continue
        await notify(
            session, recipient_id=recipient_id,
            organization_id=version.organization_id,
            study_id=candidate.study_id, event=notification_type,
            summary=summary, subject_type="candidate",
            subject_id=candidate.id,
            idempotency_key=f"candidate-audit:{audit_event_id}:{recipient_id}")
        count += 1
    return count


async def surface_experiment_event(
    session: AsyncSession, *, event_value: str, experiment_id: int,
    experiment_version_id: int | None, audit_event_id: int,
    actor_id: int | None,
) -> int:
    experiment = await session.get(ValidationExperiment, experiment_id)
    if experiment is None or experiment.organization_id is None:
        return 0
    value = event_value.lower()
    if value == "submitted":
        event = NotificationType.REVIEW_SUBMITTED
        summary = "An experiment was submitted for review."
        roles = {StudyRole.REVIEWER, StudyRole.APPROVER}
    elif value == "review_started":
        event = NotificationType.REVIEWER_ASSIGNED
        summary = "Scientific review started."
        roles = {StudyRole.OWNER, StudyRole.CONTRIBUTOR}
    elif value == "review_decision":
        version = (await session.get(ExperimentVersion, experiment_version_id)
                   if experiment_version_id else None)
        approved = version is not None and getattr(version.status, "value", "") == "approved"
        event = (NotificationType.APPROVAL_GRANTED if approved
                 else NotificationType.REVIEW_REFUSED)
        summary = ("Scientific approval was granted." if approved
                   else "Scientific review was refused or returned.")
        roles = {StudyRole.OWNER, StudyRole.CONTRIBUTOR}
    else:
        return 0
    now = datetime.now(timezone.utc)
    recipients = (await session.execute(
        select(StudyAssignment.user_id)
        .join(OrganizationMembership, (
            OrganizationMembership.user_id == StudyAssignment.user_id) &
            (OrganizationMembership.organization_id ==
             StudyAssignment.organization_id))
        .join(User, User.id == StudyAssignment.user_id)
        .where(
            StudyAssignment.study_id == experiment.study_id,
            StudyAssignment.organization_id == experiment.organization_id,
            StudyAssignment.role.in_(roles),
            StudyAssignment.status == MembershipStatus.ACTIVE,
            OrganizationMembership.status.in_(ACTIVE_MEMBERSHIP_STATUSES),
            User.is_active.is_(True),
            or_(StudyAssignment.starts_at.is_(None),
                StudyAssignment.starts_at <= now),
            or_(StudyAssignment.expires_at.is_(None),
                StudyAssignment.expires_at > now),
            or_(OrganizationMembership.starts_at.is_(None),
                OrganizationMembership.starts_at <= now),
            or_(OrganizationMembership.expires_at.is_(None),
                OrganizationMembership.expires_at > now),
        ).distinct()
    )).scalars().all()
    count = 0
    for recipient_id in recipients:
        if actor_id is not None and recipient_id == actor_id:
            continue
        await notify(
            session, recipient_id=recipient_id,
            organization_id=experiment.organization_id,
            study_id=experiment.study_id, event=event, summary=summary,
            subject_type="experiment", subject_id=experiment.id,
            idempotency_key=f"experiment-audit:{audit_event_id}:{recipient_id}")
        count += 1
    return count
