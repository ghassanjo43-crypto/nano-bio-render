"""Organizations, memberships, study assignments and notifications.

Every function here writes an audit row. That is not diligence for its own
sake: a membership row shows who has access *now*, and an access review needs
to know who had it in March. The row is mutated; the trail is appended to.

Nothing here is destructive. Revoking a membership sets a status and an end
reason and leaves the row in place, because historical attribution has to
survive the loss of access — an experiment performed by somebody who has since
left is still an experiment they performed.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.core.config import settings
from nanobio_studio.app.db.auth_models import User
from nanobio_studio.app.db.organization_models import (
    Notification, NotificationAuditEvent, NotificationAuditLog,
    NotificationType, Organization, OrganizationAuditLog,
    OrganizationEvent, OrganizationInvitation, OrganizationMembership,
    StudyAssignment,
)
from nanobio_studio.app.organizations.policy import (
    AccessContext, Action, PolicyDenied, RecordFacts, RecordNotVisible, may,
    require,
)
from nanobio_studio.app.organizations.vocabulary import (
    ADMINISTRATIVE_ROLES, AccessScope, InvitationStatus,
    LEGACY_ORGANIZATION_SLUG, MembershipStatus, OrganizationRole,
    OrganizationStatus, ROLE_MAY_BE_ASSIGNED_STUDY_ROLES, StudyRole,
    default_scope_for,
)
from nanobio_studio.app.services import invitation_delivery

__all__ = [
    "OrganizationError",
    "ConcurrentModification",
    "create_organization", "confirm_organization", "update_organization",
    "get_organization", "list_organizations", "set_membership_status",
    "add_member", "change_member_role", "revoke_member",
    "assign_to_study", "amend_assignment", "revoke_assignment",
    "list_members", "get_membership", "list_collaborators",
    "list_assignments", "assignment_history", "access_history",
    "invite_member", "list_invitations", "revoke_invitation",
    "resend_invitation", "accept_invitation",
    "notify", "list_notifications", "notification_unread_count",
    "mark_notification_read", "mark_notifications_read",
    "notification_target",
    "expire_due_memberships",
]

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")

#: Deliberately permissive, and deliberately not RFC 5322. The address is not
#: validated as *deliverable* here — only as an address-shaped string that
#: cannot be a header injection. Rejecting an unusual but valid address is a
#: worse failure than accepting one that bounces.
_EMAIL_RE = re.compile(r"^[^\s@,;<>\"]+@[^\s@,;<>\"]+\.[^\s@,;<>\"]{2,}$")


class OrganizationError(RuntimeError):
    """A request that is well-formed but not permitted by the model."""


class ConcurrentModification(OrganizationError):
    """The row changed under the caller between reading it and writing it.

    Separate from its parent so a route can answer 409 with an explanation the
    user can act on — reload and look again — rather than the generic conflict
    text, which would invite them to simply retry and overwrite.
    """


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _claim(
    session: AsyncSession, model, row, expected_revision: int | None,
) -> None:
    """Take the row for this write, or refuse.

    Issues ``UPDATE ... SET revision = revision + 1 WHERE id = :id AND
    revision = :seen``. If the statement matches no row, somebody else changed
    it after this request read it, and applying our change would silently
    discard theirs.

    Two things are going on and both matter:

    * When the caller supplies ``expected_revision``, this enforces *their*
      view of the row — the revision the screen was rendered from. That catches
      the slow case: two administrators with the members page open, one
      suspends, the other demotes ten seconds later against a stale form.
    * When the caller supplies nothing, it still enforces the revision this
      request loaded a moment ago, which catches the fast case: two requests
      interleaving inside the same second.

    The in-memory object is corrected to match, so the ORM flush that follows
    writes the same number rather than the stale one it loaded.
    """
    seen = row.revision if expected_revision is None else expected_revision
    result = await session.execute(
        update(model)
        .where(model.id == row.id, model.revision == seen)
        .values(revision=seen + 1)
    )
    if result.rowcount == 0:
        raise ConcurrentModification(
            "Somebody else changed this record while you were working on it. "
            "Reload to see the current state before making the change again — "
            "applying it now would discard their change without either of you "
            "seeing it.")
    row.revision = seen + 1


async def _audit(
    session: AsyncSession, *, organization_id: int | None,
    event: OrganizationEvent, actor: AccessContext | None,
    subject_type: str | None, subject_id: int | None,
    summary: str, detail: dict | None = None,
) -> None:
    session.add(OrganizationAuditLog(
        organization_id=organization_id,
        event=event,
        subject_type=subject_type,
        subject_id=subject_id,
        actor_id=actor.user_id if actor else None,
        actor_username=actor.username if actor else None,
        summary=summary,
        detail_json=json.dumps(detail, sort_keys=True, default=str)
        if detail else None,
    ))


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

async def create_organization(
    session: AsyncSession, *, actor: AccessContext, slug: str, name: str,
    description: str | None = None,
) -> Organization:
    """Create an organization. The creator becomes its owner.

    Owner rather than administrator because somebody has to be able to hand
    the organization on, and an organization whose only owner is the platform
    administrator has put a scientific tenant under the control of whoever
    runs the servers.
    """
    slug = slug.strip().lower()
    if not _SLUG_RE.match(slug):
        raise OrganizationError(
            "Slug must be 3–64 characters, lowercase letters, digits and "
            "hyphens, and may not start or end with a hyphen.")
    if slug == LEGACY_ORGANIZATION_SLUG:
        raise OrganizationError(
            f"'{LEGACY_ORGANIZATION_SLUG}' is reserved for the organization "
            "created when an installation is upgraded.")

    clash = (await session.execute(
        select(Organization.id).where(Organization.slug == slug)
    )).scalar_one_or_none()
    if clash is not None:
        raise OrganizationError(f"An organization '{slug}' already exists.")

    organization = Organization(
        slug=slug, name=name.strip(), description=description,
        status=OrganizationStatus.ACTIVE, created_by=actor.user_id,
    )
    session.add(organization)
    await session.flush()

    session.add(OrganizationMembership(
        organization_id=organization.id, user_id=actor.user_id,
        role=OrganizationRole.OWNER,
        scope=default_scope_for(OrganizationRole.OWNER),
        status=MembershipStatus.ACTIVE, invited_by=actor.user_id,
    ))
    await _audit(
        session, organization_id=organization.id,
        event=OrganizationEvent.ORGANIZATION_CREATED, actor=actor,
        subject_type="organization", subject_id=organization.id,
        summary=f"Organization '{name}' created by {actor.username}.",
        detail={"slug": slug})
    await session.flush()
    return organization


async def confirm_organization(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
) -> Organization:
    """Release an upgraded organization from PENDING_CONFIRMATION.

    This is the administrator's acknowledgement that the memberships the
    backfill proposed are the right ones. Until it happens the organization
    accepts no scientific change, which is what stops an upgrade from
    silently resuming work under memberships nobody has looked at.
    """
    require(actor, Action.MANAGE_ORGANIZATION,
            RecordFacts(organization_id=organization_id))

    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise RecordNotVisible("organization")
    if organization.status is not OrganizationStatus.PENDING_CONFIRMATION:
        return organization

    organization.status = OrganizationStatus.ACTIVE
    organization.confirmed_at = _utcnow()
    organization.confirmed_by = actor.user_id

    await _audit(
        session, organization_id=organization_id,
        event=OrganizationEvent.ORGANIZATION_CONFIRMED, actor=actor,
        subject_type="organization", subject_id=organization_id,
        summary=(f"{actor.username} confirmed the memberships of "
                 f"'{organization.name}'. Scientific changes are now "
                 f"permitted."))
    await session.flush()
    return organization


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------

async def add_member(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
    user_id: int, role: OrganizationRole,
    scope: AccessScope | None = None,
    expires_at: datetime | None = None,
    external_organization: str | None = None,
    may_download_attachments: bool = True,
) -> OrganizationMembership:
    """Add somebody to an organization, or restore a revoked membership."""
    require(actor, Action.MANAGE_MEMBERS,
            RecordFacts(organization_id=organization_id))

    if await session.get(User, user_id) is None:
        raise OrganizationError("No such user.")

    existing = (await session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id)
    )).scalar_one_or_none()

    if existing is not None and existing.status is MembershipStatus.ACTIVE:
        raise OrganizationError("That person is already a member.")

    if scope is None:
        scope = default_scope_for(role)

    if existing is not None:
        # Restore rather than insert: the row carries the history of the
        # earlier revocation and must not be replaced by a fresh one.
        existing.role = role
        existing.scope = scope
        existing.status = MembershipStatus.ACTIVE
        existing.expires_at = expires_at
        existing.external_organization = external_organization
        existing.may_download_attachments = may_download_attachments
        existing.updated_at = _utcnow()
        existing.ended_at = None
        existing.ended_by = None
        existing.end_reason = None
        membership = existing
        event = OrganizationEvent.MEMBER_REINSTATED
    else:
        membership = OrganizationMembership(
            organization_id=organization_id, user_id=user_id, role=role,
            scope=scope, status=MembershipStatus.ACTIVE,
            expires_at=expires_at,
            external_organization=external_organization,
            may_download_attachments=may_download_attachments,
            invited_by=actor.user_id,
        )
        session.add(membership)
        event = (OrganizationEvent.COLLABORATION_GRANTED
                 if external_organization else OrganizationEvent.MEMBER_ADDED)

    await session.flush()
    await _audit(
        session, organization_id=organization_id, event=event, actor=actor,
        subject_type="membership", subject_id=membership.id,
        summary=(f"{actor.username} granted user #{user_id} the role "
                 f"'{role.value}'"
                 + (f" as an external collaborator from "
                    f"{external_organization}" if external_organization else "")
                 + (f", expiring {expires_at.date().isoformat()}"
                    if expires_at else "") + "."),
        detail={"role": role.value, "scope": scope.value,
                "expires_at": expires_at,
                "may_download_attachments": may_download_attachments})

    if external_organization:
        await notify(
            session, recipient_id=user_id, organization_id=organization_id,
            event=NotificationType.COLLABORATION_ASSIGNED,
            summary=(f"You have been given time-limited access to "
                     f"{external_organization}'s collaboration space."),
            subject_type="membership", subject_id=membership.id)

    return membership


async def change_member_role(
    session: AsyncSession, *, actor: AccessContext, membership_id: int,
    role: OrganizationRole | None = None,
    scope: AccessScope | None = None,
    expected_revision: int | None = None,
) -> OrganizationMembership:
    membership = await session.get(OrganizationMembership, membership_id)
    if membership is None:
        raise RecordNotVisible("membership")
    require(actor, Action.MANAGE_MEMBERS,
            RecordFacts(organization_id=membership.organization_id))

    # ---- the self-escalation bar -------------------------------------
    # Nobody changes their own organization role. Ever, including an owner.
    #
    # Without this the entire administrative/scientific separation is
    # decorative. An administrator holds MANAGE_MEMBERS, so they could set
    # their own role to APPROVER, then — now holding a scientific role —
    # assign themselves as study approver and approve evidence. Two requests,
    # no second person involved, and the audit trail would show a routine
    # role change.
    #
    # With it, escalation always requires somebody else to act: a membership
    # carries exactly one role, so an administrator who becomes an approver
    # *stops* being an administrator and loses the ability to appoint. See
    # docs/APPOINTMENT_AUTHORITY.md.
    if membership.user_id == actor.user_id:
        raise OrganizationError(
            "You cannot change your own organization role. Ask another owner "
            "or administrator to make the change, so that no one person can "
            "grant themselves scientific authority.")

    # An organization must never be left with no owner: nobody would be able
    # to transfer or archive it, and the only remedy would be a platform
    # administrator reaching past the tenant boundary.
    if (membership.role is OrganizationRole.OWNER
            and role is not None and role is not OrganizationRole.OWNER):
        await _require_another_owner(session, membership,
                                     "demoting this owner")

    await _claim(session, OrganizationMembership, membership, expected_revision)

    before = {"role": membership.role.value, "scope": membership.scope.value}
    if role is not None:
        membership.role = role
        # A role change can invalidate the scope's default; only widen or
        # narrow deliberately, never silently.
        if scope is None and membership.scope is not default_scope_for(role):
            scope = default_scope_for(role)
    if scope is not None:
        membership.scope = scope
    membership.updated_at = _utcnow()

    await _audit(
        session, organization_id=membership.organization_id,
        event=OrganizationEvent.MEMBER_ROLE_CHANGED, actor=actor,
        subject_type="membership", subject_id=membership.id,
        summary=(f"{actor.username} changed user #{membership.user_id} from "
                 f"{before['role']} to {membership.role.value}."),
        detail={"before": before,
                "after": {"role": membership.role.value,
                          "scope": membership.scope.value}})
    await session.flush()
    return membership


async def revoke_member(
    session: AsyncSession, *, actor: AccessContext, membership_id: int,
    reason: str | None = None, expected_revision: int | None = None,
) -> OrganizationMembership:
    """End a membership. The row survives; only the access stops."""
    membership = await session.get(OrganizationMembership, membership_id)
    if membership is None:
        raise RecordNotVisible("membership")
    require(actor, Action.MANAGE_MEMBERS,
            RecordFacts(organization_id=membership.organization_id))

    if membership.role is OrganizationRole.OWNER:
        await _require_another_owner(session, membership,
                                     "revoking this membership")

    await _claim(session, OrganizationMembership, membership, expected_revision)

    membership.status = MembershipStatus.REVOKED
    membership.ended_at = _utcnow()
    membership.ended_by = actor.user_id
    membership.end_reason = reason

    # Study assignments inside this organization stop too. The policy already
    # ignores an assignment whose organization membership has lapsed, so this
    # is belt and braces — but leaving them ACTIVE would misreport who has
    # access on the study team screen.
    assignments = (await session.execute(
        select(StudyAssignment).where(
            StudyAssignment.organization_id == membership.organization_id,
            StudyAssignment.user_id == membership.user_id,
            StudyAssignment.status == MembershipStatus.ACTIVE)
    )).scalars().all()
    for assignment in assignments:
        assignment.status = MembershipStatus.REVOKED
        assignment.ended_at = _utcnow()
        assignment.ended_by = actor.user_id
        assignment.end_reason = "Organization membership revoked."

    event = (OrganizationEvent.COLLABORATION_REVOKED
             if membership.external_organization
             else OrganizationEvent.MEMBER_REVOKED)
    await _audit(
        session, organization_id=membership.organization_id, event=event,
        actor=actor, subject_type="membership", subject_id=membership.id,
        summary=(f"{actor.username} revoked access for user "
                 f"#{membership.user_id}"
                 + (f": {reason}" if reason else ".")),
        detail={"assignments_ended": len(assignments), "reason": reason})

    if membership.external_organization:
        await notify(
            session, recipient_id=membership.user_id,
            organization_id=membership.organization_id,
            event=NotificationType.COLLABORATION_REVOKED,
            summary="Your collaboration access has ended.",
            subject_type="membership", subject_id=membership.id)

    await session.flush()
    return membership


async def update_organization(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
    name: str | None = None, description: str | None = None,
) -> Organization:
    """Rename or re-describe an organization. Owner only.

    The slug is deliberately not editable. Audit rows written years ago name
    the organization by slug precisely so a rename stays traceable; letting
    the slug move would break that.
    """
    require(actor, Action.MANAGE_ORGANIZATION,
            RecordFacts(organization_id=organization_id))

    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise RecordNotVisible("organization")

    before = {"name": organization.name,
              "description": organization.description}
    if name is not None:
        if not name.strip():
            raise OrganizationError("An organization needs a name.")
        organization.name = name.strip()
    if description is not None:
        organization.description = description.strip() or None

    await _audit(
        session, organization_id=organization_id,
        event=OrganizationEvent.ORGANIZATION_UPDATED, actor=actor,
        subject_type="organization", subject_id=organization_id,
        summary=f"{actor.username} updated the organization profile.",
        detail={"before": before,
                "after": {"name": organization.name,
                          "description": organization.description}})
    await session.flush()
    return organization


async def set_membership_status(
    session: AsyncSession, *, actor: AccessContext, membership_id: int,
    status: MembershipStatus, reason: str | None = None,
    expected_revision: int | None = None,
) -> OrganizationMembership:
    """Suspend or reinstate a membership.

    Suspension is reversible and keeps the row; it is the right tool for "stop
    this person for now" without discarding the history that revocation is
    for. Only these two transitions are offered — moving a membership to
    INVITED or EXPIRED by hand would misstate how it got there.
    """
    if status not in {MembershipStatus.ACTIVE, MembershipStatus.SUSPENDED}:
        raise OrganizationError(
            "Only 'active' and 'suspended' can be set directly. Use the "
            "revoke action to end a membership, and let expiry dates produce "
            "'expired' on their own.")

    membership = await session.get(OrganizationMembership, membership_id)
    if membership is None:
        raise RecordNotVisible("membership")
    require(actor, Action.MANAGE_MEMBERS,
            RecordFacts(organization_id=membership.organization_id))

    # Suspending yourself would lock the organization out of administration
    # if you were its only administrator, and there is no legitimate reason
    # to do it.
    if membership.user_id == actor.user_id:
        raise OrganizationError(
            "You cannot change your own membership status.")

    if (membership.role is OrganizationRole.OWNER
            and status is MembershipStatus.SUSPENDED):
        await _require_another_owner(session, membership,
                                     "suspending this owner")

    if membership.status in {MembershipStatus.REVOKED,
                             MembershipStatus.EXPIRED}:
        raise OrganizationError(
            "This membership has ended. Add the person again rather than "
            "reviving a terminal record.")

    await _claim(session, OrganizationMembership, membership, expected_revision)

    before = membership.status
    membership.status = status
    membership.updated_at = _utcnow()

    await _audit(
        session, organization_id=membership.organization_id,
        event=(OrganizationEvent.MEMBER_SUSPENDED
               if status is MembershipStatus.SUSPENDED
               else OrganizationEvent.MEMBER_REINSTATED),
        actor=actor, subject_type="membership", subject_id=membership.id,
        summary=(f"{actor.username} changed user #{membership.user_id} from "
                 f"{before.value} to {status.value}"
                 + (f": {reason}" if reason else ".")),
        detail={"before": before.value, "after": status.value,
                "reason": reason})
    await session.flush()
    return membership


async def _require_another_owner(
    session: AsyncSession, membership: OrganizationMembership, action: str,
) -> None:
    """Refuse if this is the last active owner.

    An organization with no owner cannot be transferred or archived, and the
    only remedy would be a platform administrator reaching across the tenant
    boundary — which is exactly the thing the boundary exists to prevent.
    """
    owners = (await session.execute(
        select(OrganizationMembership.id).where(
            OrganizationMembership.organization_id
            == membership.organization_id,
            OrganizationMembership.role == OrganizationRole.OWNER,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
            OrganizationMembership.id != membership.id)
    )).scalars().all()
    if not owners:
        raise OrganizationError(
            f"This is the only active owner, so {action} would leave the "
            f"organization with nobody able to administer it. Appoint another "
            f"owner first.")


async def get_organization(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
) -> Organization:
    """One organization the caller belongs to, or a 404."""
    if not actor.is_member_of(organization_id):
        raise RecordNotVisible("organization")
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise RecordNotVisible("organization")
    return organization


async def list_organizations(
    session: AsyncSession, *, actor: AccessContext,
) -> list[tuple[Organization, OrganizationMembership]]:
    """Every organization the caller is currently a member of.

    Drives the switcher. Returns the membership alongside so the interface can
    show the role without a second request, and so it never has to infer
    authority from the organization alone.
    """
    # The one legitimate use of all_memberships(): a switcher narrowed to the
    # current selection could never switch away from it.
    every = actor.all_memberships()
    if not every:
        return []
    rows = (await session.execute(
        select(Organization, OrganizationMembership)
        .join(OrganizationMembership,
              OrganizationMembership.organization_id == Organization.id)
        .where(OrganizationMembership.user_id == actor.user_id,
               Organization.id.in_(every))
        .order_by(Organization.name)
    )).all()
    return [(o, m) for o, m in rows]


# ---------------------------------------------------------------------------
# Study assignments
# ---------------------------------------------------------------------------

async def assign_to_study(
    session: AsyncSession, *, actor: AccessContext, study_id: int,
    user_id: int, role: StudyRole,
    starts_at: datetime | None = None,
    expires_at: datetime | None = None,
    permitted_subtypes: list[str] | None = None,
    may_download_attachments: bool | None = None,
    note: str | None = None,
) -> StudyAssignment:
    """Give somebody a scientific role on one study.

    Refuses a role their organization membership does not make them eligible
    for. Without that check, a study assignment would be a back door around
    the administrative/scientific separation: an organization administrator
    could assign *themselves* as approver on a study and be approving science
    a moment later, having granted nothing that looks like a role change.
    """
    from nanobio_studio.app.db.workspace_models import StoredRun

    study = await session.get(StoredRun, study_id)
    if study is None or study.organization_id is None:
        raise RecordNotVisible("study")

    require(actor, Action.MANAGE_ASSIGNMENTS,
            RecordFacts(organization_id=study.organization_id,
                        study_id=study_id))

    membership = (await session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == study.organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE)
    )).scalar_one_or_none()
    if membership is None:
        raise OrganizationError(
            "That person is not an active member of this organization.")

    eligible = ROLE_MAY_BE_ASSIGNED_STUDY_ROLES.get(
        membership.role, frozenset())
    if role not in eligible:
        permitted = ", ".join(sorted(r.value for r in eligible)) or "none"
        raise OrganizationError(
            f"An organization {membership.role.value} cannot hold the study "
            f"role '{role.value}'. Eligible study roles: {permitted}. "
            f"Change their organization role first — scientific authority is "
            f"granted deliberately, not through a study assignment.")

    existing = (await session.execute(
        select(StudyAssignment).where(
            StudyAssignment.study_id == study_id,
            StudyAssignment.user_id == user_id,
            StudyAssignment.role == role)
    )).scalar_one_or_none()

    if existing is not None and existing.status is MembershipStatus.ACTIVE:
        # The unique constraint on (study, user, role) makes this a genuine
        # guarantee rather than a check: two simultaneous requests cannot both
        # pass here and both insert. One of them fails on the constraint.
        raise OrganizationError("That assignment already exists.")

    if starts_at is not None and expires_at is not None \
            and expires_at <= starts_at:
        raise OrganizationError(
            "The expiry date must be after the start date. An assignment that "
            "expires before it begins would grant nothing while appearing on "
            "the study team.")

    if existing is not None:
        # Reinstating a revoked assignment. Claimed with the concurrency check
        # so a simultaneous amendment of the same row cannot be lost.
        await _claim(session, StudyAssignment, existing, None)
        existing.status = MembershipStatus.ACTIVE
        existing.starts_at = starts_at
        existing.expires_at = expires_at
        existing.may_download_attachments = may_download_attachments
        existing.note = note
        existing.permitted_subtypes_json = (
            json.dumps(sorted(permitted_subtypes))
            if permitted_subtypes else None)
        existing.updated_at = _utcnow()
        existing.ended_at = None
        existing.ended_by = None
        existing.end_reason = None
        assignment = existing
    else:
        assignment = StudyAssignment(
            organization_id=study.organization_id, study_id=study_id,
            user_id=user_id, role=role, status=MembershipStatus.ACTIVE,
            starts_at=starts_at, expires_at=expires_at,
            may_download_attachments=may_download_attachments, note=note,
            assigned_by=actor.user_id,
            permitted_subtypes_json=(json.dumps(sorted(permitted_subtypes))
                                     if permitted_subtypes else None),
        )
        session.add(assignment)

    await session.flush()
    await _audit(
        session, organization_id=study.organization_id,
        event=OrganizationEvent.ASSIGNMENT_CREATED, actor=actor,
        subject_type="study_assignment", subject_id=assignment.id,
        summary=(f"{actor.username} assigned user #{user_id} as "
                 f"'{role.value}' on study #{study_id}"
                 + (f", expiring {expires_at.date().isoformat()}"
                    if expires_at else "")
                 + (", without attachment downloads"
                    if may_download_attachments is False else "")
                 + (f": {note}" if note else ".")),
        detail={"role": role.value, "study_id": study_id,
                "starts_at": starts_at, "expires_at": expires_at,
                "permitted_subtypes": permitted_subtypes,
                "may_download_attachments": may_download_attachments,
                "note": note})

    if role in {StudyRole.REVIEWER, StudyRole.APPROVER}:
        await notify(
            session, recipient_id=user_id,
            organization_id=study.organization_id, study_id=study_id,
            study_name=study.name,
            event=(NotificationType.REVIEWER_ASSIGNED
                   if role is StudyRole.REVIEWER
                   else NotificationType.APPROVER_ASSIGNED),
            summary=f"You have been assigned as {role.value} on a study.",
            subject_type="study", subject_id=study_id)

    return assignment


async def amend_assignment(
    session: AsyncSession, *, actor: AccessContext, assignment_id: int,
    starts_at: datetime | None = None,
    expires_at: datetime | None = None,
    permitted_subtypes: list[str] | None = None,
    may_download_attachments: bool | None = None,
    note: str | None = None,
    expected_revision: int | None = None,
) -> StudyAssignment:
    assignment = await session.get(StudyAssignment, assignment_id)
    if assignment is None:
        raise RecordNotVisible("assignment")
    require(actor, Action.MANAGE_ASSIGNMENTS,
            RecordFacts(organization_id=assignment.organization_id,
                        study_id=assignment.study_id))

    if starts_at is not None and expires_at is not None \
            and expires_at <= starts_at:
        raise OrganizationError(
            "The expiry date must be after the start date.")

    await _claim(session, StudyAssignment, assignment, expected_revision)

    before = {"starts_at": assignment.starts_at,
              "expires_at": assignment.expires_at,
              "permitted_subtypes": assignment.permitted_subtypes_json,
              "may_download_attachments":
                  assignment.may_download_attachments,
              "note": assignment.note}
    assignment.starts_at = starts_at
    assignment.expires_at = expires_at
    assignment.may_download_attachments = may_download_attachments
    if note is not None:
        assignment.note = note or None
    if permitted_subtypes is not None:
        assignment.permitted_subtypes_json = json.dumps(
            sorted(permitted_subtypes)) if permitted_subtypes else None
    assignment.updated_at = _utcnow()

    await _audit(
        session, organization_id=assignment.organization_id,
        event=OrganizationEvent.ASSIGNMENT_AMENDED, actor=actor,
        subject_type="study_assignment", subject_id=assignment.id,
        summary=(f"{actor.username} amended the '{assignment.role.value}' "
                 f"assignment for user #{assignment.user_id} on study "
                 f"#{assignment.study_id}."),
        detail={"before": before, "after": {
            "starts_at": starts_at,
            "expires_at": expires_at,
            "permitted_subtypes": permitted_subtypes,
            "may_download_attachments": may_download_attachments,
            "note": assignment.note}})
    await session.flush()
    return assignment


async def revoke_assignment(
    session: AsyncSession, *, actor: AccessContext, assignment_id: int,
    reason: str | None = None, expected_revision: int | None = None,
) -> StudyAssignment:
    """End an assignment.

    Blocks future access from the next request onwards — the context is
    rebuilt per request, so there is no window in which a revoked assignment
    still works. The row stays, and so does every audit line and every record
    naming this person as its performer: revocation is about what somebody may
    do next, never about rewriting what they did.
    """
    assignment = await session.get(StudyAssignment, assignment_id)
    if assignment is None:
        raise RecordNotVisible("assignment")
    require(actor, Action.MANAGE_ASSIGNMENTS,
            RecordFacts(organization_id=assignment.organization_id,
                        study_id=assignment.study_id))

    await _claim(session, StudyAssignment, assignment, expected_revision)

    assignment.status = MembershipStatus.REVOKED
    assignment.ended_at = _utcnow()
    assignment.ended_by = actor.user_id
    assignment.end_reason = reason

    await _audit(
        session, organization_id=assignment.organization_id,
        event=OrganizationEvent.ASSIGNMENT_REVOKED, actor=actor,
        subject_type="study_assignment", subject_id=assignment.id,
        summary=(f"{actor.username} revoked the '{assignment.role.value}' "
                 f"assignment for user #{assignment.user_id} on study "
                 f"#{assignment.study_id}"
                 + (f": {reason}" if reason else ".")),
        detail={"reason": reason})
    await session.flush()
    return assignment


async def expire_due_memberships(session: AsyncSession) -> dict[str, int]:
    """Mark lapsed rows EXPIRED.

    Housekeeping only. The policy already refuses an expired row on sight, so
    this changes nothing about who can do what — it exists so the members
    screen and an access review show ``expired`` rather than a stale
    ``active`` beside a date in the past.
    """
    now = _utcnow()
    counts = {"memberships": 0, "assignments": 0, "invitations": 0}

    memberships = (await session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.status == MembershipStatus.ACTIVE,
            OrganizationMembership.expires_at.is_not(None))
    )).scalars().all()
    for membership in memberships:
        expires = membership.expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires is not None and now >= expires:
            membership.status = MembershipStatus.EXPIRED
            membership.ended_at = now
            counts["memberships"] += 1
            await _audit(
                session, organization_id=membership.organization_id,
                event=OrganizationEvent.MEMBER_EXPIRED, actor=None,
                subject_type="membership", subject_id=membership.id,
                summary=(f"Membership for user #{membership.user_id} expired "
                         f"on {expires.date().isoformat()}."))

    assignments = (await session.execute(
        select(StudyAssignment).where(
            StudyAssignment.status == MembershipStatus.ACTIVE,
            StudyAssignment.expires_at.is_not(None))
    )).scalars().all()
    for assignment in assignments:
        expires = assignment.expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires is not None and now >= expires:
            assignment.status = MembershipStatus.EXPIRED
            assignment.ended_at = now
            counts["assignments"] += 1
            await _audit(
                session, organization_id=assignment.organization_id,
                event=OrganizationEvent.ASSIGNMENT_EXPIRED, actor=None,
                subject_type="study_assignment", subject_id=assignment.id,
                summary=(f"'{assignment.role.value}' assignment for user "
                         f"#{assignment.user_id} expired."))

    invitations = (await session.execute(
        select(OrganizationInvitation).where(
            OrganizationInvitation.status == InvitationStatus.PENDING)
    )).scalars().all()
    for invitation in invitations:
        if _invitation_is_live(invitation, now):
            continue
        invitation.status = InvitationStatus.EXPIRED
        invitation.ended_at = now
        counts["invitations"] += 1
        await _audit(
            session, organization_id=invitation.organization_id,
            event=OrganizationEvent.INVITATION_EXPIRED, actor=None,
            subject_type="invitation", subject_id=invitation.id,
            summary=(f"The invitation to {invitation.email} expired without "
                     f"being accepted."))

    await session.flush()
    return counts


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def list_members(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
) -> list[tuple[OrganizationMembership, User]]:
    if not actor.is_member_of(organization_id):
        raise RecordNotVisible("organization")
    rows = (await session.execute(
        select(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(OrganizationMembership.organization_id == organization_id)
        .order_by(OrganizationMembership.id)
    )).all()
    return [(m, u) for m, u in rows]


async def get_membership(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
    membership_id: int,
) -> tuple[OrganizationMembership, User]:
    """One membership, with the account it belongs to.

    The organization comes from the URL and is checked against the stored row
    rather than trusted. Without that, ``/organizations/{mine}/members/{id}``
    would read any membership in the installation by identifier, with the path
    segment doing nothing but decorating the request — the exact shape of
    parent injection the contract forbids.
    """
    if not actor.is_member_of(organization_id):
        raise RecordNotVisible("membership")
    membership = await session.get(OrganizationMembership, membership_id)
    if membership is None or membership.organization_id != organization_id:
        raise RecordNotVisible("membership")
    user = await session.get(User, membership.user_id)
    if user is None:
        raise RecordNotVisible("membership")
    return membership, user


async def list_collaborators(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
) -> list[tuple[OrganizationMembership, User]]:
    """External memberships only, in one organization.

    A separate read rather than a filter the caller applies, so "who from
    outside this organization can currently reach our data" is one question
    with one answer, and a screen cannot accidentally answer it by filtering a
    list that had already been truncated.
    """
    rows = await list_members(session, actor=actor,
                              organization_id=organization_id)
    return [(m, u) for m, u in rows if m.external_organization is not None]


async def list_assignments(
    session: AsyncSession, *, actor: AccessContext, study_id: int,
) -> list[tuple[StudyAssignment, User]]:
    """The team on one study. Visible only to somebody who can see the study.

    Organization membership is not enough, and an earlier version of this
    function stopped there. That was a real leak, found by the browser
    walkthrough rather than by any unit test: a member with
    ``ASSIGNED_STUDIES`` scope and no assignment on this study got a **200**
    listing everybody on it — names, roles and dates for work they cannot
    otherwise reach at all.

    Reusing the study-visibility rule closes it. ``RecordNotVisible`` rather
    than ``PolicyDenied`` because that is how the study itself behaves: a study
    outside the caller's reach is never selected by the workspace queries and
    404s, so the team endpoint must not be the one place that confirms it
    exists.
    """
    from nanobio_studio.app.db.workspace_models import StoredRun

    study = await session.get(StoredRun, study_id)
    if study is None or study.organization_id is None:
        raise RecordNotVisible("study")
    if not actor.is_member_of(study.organization_id):
        raise RecordNotVisible("study")

    visible, _reason = may(actor, Action.VIEW_STUDY, RecordFacts(
        organization_id=study.organization_id, study_id=study_id,
        owner_id=study.owner_id))
    if not visible:
        raise RecordNotVisible("study")

    rows = (await session.execute(
        select(StudyAssignment, User)
        .join(User, User.id == StudyAssignment.user_id)
        .where(StudyAssignment.study_id == study_id)
        .order_by(StudyAssignment.id)
    )).all()
    return [(a, u) for a, u in rows]


async def access_history(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
    limit: int = 200, event: OrganizationEvent | None = None,
    subject_type: str | None = None,
) -> list[OrganizationAuditLog]:
    require(actor, Action.VIEW_ACCESS_HISTORY,
            RecordFacts(organization_id=organization_id))
    query = select(OrganizationAuditLog).where(
        OrganizationAuditLog.organization_id == organization_id)
    if event is not None:
        query = query.where(OrganizationAuditLog.event == event)
    if subject_type is not None:
        query = query.where(
            OrganizationAuditLog.subject_type == subject_type)
    return list((await session.execute(
        query.order_by(OrganizationAuditLog.created_at.desc(),
                       OrganizationAuditLog.id.desc())
        .limit(min(limit, 500))
    )).scalars().all())


async def assignment_history(
    session: AsyncSession, *, actor: AccessContext, study_id: int,
    limit: int = 200,
) -> list[OrganizationAuditLog]:
    """Every appointment, amendment and revocation on one study.

    Read from the audit trail rather than from the assignment rows, because a
    row shows the state now and the question here is what changed. An
    assignment that was created, amended twice and revoked is one row and four
    audit lines, and the four lines are the answer.

    Requires ``VIEW_ACCESS_HISTORY`` — owner, administrator or auditor. The
    study team itself is readable by any member of the organization; who
    appointed whom, and who took it away, is administrative information.
    """
    from nanobio_studio.app.db.workspace_models import StoredRun

    study = await session.get(StoredRun, study_id)
    if study is None or study.organization_id is None:
        raise RecordNotVisible("study")
    require(actor, Action.VIEW_ACCESS_HISTORY,
            RecordFacts(organization_id=study.organization_id,
                        study_id=study_id))

    assignment_ids = set((await session.execute(
        select(StudyAssignment.id).where(
            StudyAssignment.study_id == study_id)
    )).scalars().all())
    if not assignment_ids:
        return []

    return list((await session.execute(
        select(OrganizationAuditLog)
        .where(OrganizationAuditLog.organization_id == study.organization_id,
               OrganizationAuditLog.subject_type == "study_assignment",
               OrganizationAuditLog.subject_id.in_(assignment_ids))
        .order_by(OrganizationAuditLog.created_at.desc(),
                  OrganizationAuditLog.id.desc())
        .limit(min(limit, 500))
    )).scalars().all())


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------
#
# An invitation is an offer, not an access grant. Nothing in
# ``organization_memberships`` exists until somebody accepts, so there is no
# row for an access query to misread. See ``OrganizationInvitation``.


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalise_email(email: str) -> str:
    normalised = email.strip().lower()
    if not _EMAIL_RE.match(normalised) or len(normalised) > 320:
        raise OrganizationError(
            "That does not look like an email address.")
    return normalised


def _invitation_is_live(invitation: OrganizationInvitation,
                        now: datetime) -> bool:
    """Is this invitation redeemable *right now*?

    Expiry is evaluated here, on read, exactly as membership expiry is. A
    ``PENDING`` row whose date has passed grants nothing from that instant,
    whether or not the sweep has marked it ``EXPIRED``.
    """
    if invitation.status is not InvitationStatus.PENDING:
        return False
    expires = invitation.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires is None or now < expires


async def invite_member(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
    email: str, role: OrganizationRole, scope: AccessScope | None = None,
    membership_expires_at: datetime | None = None,
    external_organization: str | None = None,
    may_download_attachments: bool = True,
    ttl_hours: int | None = None,
) -> tuple[OrganizationInvitation, str]:
    """Issue an invitation. Returns the row and the raw token, once.

    The token is returned to the caller and never stored in the clear. If
    delivery is not configured, the administrator hands it over themselves —
    which is why it comes back at all.

    Nothing here reveals whether the address already has an account. An
    administrator inviting ``someone@example.com`` gets the same response
    whether or not that person is registered, so the endpoint cannot be used to
    ask "does this person have an account here" — a question an administrator
    of one organization has no business asking about the installation.
    """
    require(actor, Action.MANAGE_MEMBERS,
            RecordFacts(organization_id=organization_id))

    address = _normalise_email(email)
    if scope is None:
        scope = default_scope_for(role)

    now = _utcnow()
    hours = ttl_hours if ttl_hours is not None else settings.invitation_ttl_hours
    if hours <= 0 or hours > 24 * 30:
        raise OrganizationError(
            "An invitation must stay open for between one hour and thirty "
            "days.")
    if membership_expires_at is not None and membership_expires_at <= now:
        raise OrganizationError(
            "The access expiry date is in the past, so accepting would grant "
            "nothing.")

    # Refuse a second live invitation for the same address. The partial unique
    # index enforces this at the database too, so two simultaneous requests
    # cannot both succeed.
    outstanding = (await session.execute(
        select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.email == address,
            OrganizationInvitation.status == InvitationStatus.PENDING)
    )).scalars().all()
    for existing in outstanding:
        if _invitation_is_live(existing, now):
            raise OrganizationError(
                "An invitation to that address is already outstanding. Revoke "
                "it before issuing another, so that only one link is live.")
        # Lapsed but never swept. Close it here rather than leaving two
        # PENDING rows, which the unique index would refuse anyway.
        existing.status = InvitationStatus.EXPIRED
        existing.ended_at = now

    # 32 bytes of entropy. Long enough that guessing is not a strategy, and
    # generated by `secrets` rather than `random`, which is seeded predictably.
    token = secrets.token_urlsafe(32)
    invitation = OrganizationInvitation(
        organization_id=organization_id, email=address, role=role,
        scope=scope, status=InvitationStatus.PENDING,
        token_hash=_hash_token(token), token_prefix=token[:8],
        expires_at=now + timedelta(hours=hours),
        membership_expires_at=membership_expires_at,
        external_organization=external_organization,
        may_download_attachments=may_download_attachments,
        invited_by=actor.user_id,
    )
    session.add(invitation)
    await session.flush()

    organization = await session.get(Organization, organization_id)
    provider = invitation_delivery.get_provider()
    result = provider.send(invitation_delivery.InvitationMessage(
        recipient_email=address,
        organization_name=organization.name if organization else "",
        role=role.value,
        invited_by=actor.username,
        expires_at=invitation.expires_at,
        link=invitation_delivery.build_invitation_link(token),
    ))
    invitation.delivery_provider = result.provider
    invitation.delivery_status = result.status
    invitation.delivery_detail = result.detail

    await _audit(
        session, organization_id=organization_id,
        event=OrganizationEvent.MEMBER_INVITED, actor=actor,
        subject_type="invitation", subject_id=invitation.id,
        summary=(f"{actor.username} invited {address} as '{role.value}'"
                 + (f" on behalf of {external_organization}"
                    if external_organization else "")
                 + f" (invitation {invitation.token_prefix}…)."),
        # The token is absent, deliberately. An audit trail is read by more
        # people than the invitation was ever sent to.
        detail={"role": role.value, "scope": scope.value,
                "expires_at": invitation.expires_at,
                "membership_expires_at": membership_expires_at,
                "may_download_attachments": may_download_attachments,
                "delivery": result.status})
    await session.flush()
    return invitation, token


async def list_invitations(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
    include_closed: bool = False,
) -> list[OrganizationInvitation]:
    """Outstanding invitations. Administrative — never a member-visible list."""
    require(actor, Action.MANAGE_MEMBERS,
            RecordFacts(organization_id=organization_id))
    query = select(OrganizationInvitation).where(
        OrganizationInvitation.organization_id == organization_id)
    if not include_closed:
        query = query.where(
            OrganizationInvitation.status == InvitationStatus.PENDING)
    return list((await session.execute(
        query.order_by(OrganizationInvitation.id.desc())
    )).scalars().all())


async def _scoped_invitation(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
    invitation_id: int,
) -> OrganizationInvitation:
    require(actor, Action.MANAGE_MEMBERS,
            RecordFacts(organization_id=organization_id))
    invitation = await session.get(OrganizationInvitation, invitation_id)
    # The organization in the path is checked against the stored row: an
    # administrator of one organization must not reach another's invitation by
    # naming their own organization in the URL.
    if invitation is None or invitation.organization_id != organization_id:
        raise RecordNotVisible("invitation")
    return invitation


async def revoke_invitation(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
    invitation_id: int, reason: str | None = None,
) -> OrganizationInvitation:
    """Withdraw an unaccepted invitation. The link stops working at once."""
    invitation = await _scoped_invitation(
        session, actor=actor, organization_id=organization_id,
        invitation_id=invitation_id)

    if invitation.status is not InvitationStatus.PENDING:
        raise OrganizationError(
            f"That invitation is already {invitation.status.value} and cannot "
            f"be withdrawn.")

    await _claim(session, OrganizationInvitation, invitation, None)
    invitation.status = InvitationStatus.REVOKED
    invitation.ended_at = _utcnow()
    invitation.ended_by = actor.user_id
    invitation.end_reason = reason

    await _audit(
        session, organization_id=organization_id,
        event=OrganizationEvent.INVITATION_REVOKED, actor=actor,
        subject_type="invitation", subject_id=invitation.id,
        summary=(f"{actor.username} withdrew the invitation to "
                 f"{invitation.email}"
                 + (f": {reason}" if reason else ".")),
        detail={"reason": reason})
    await session.flush()
    return invitation


async def resend_invitation(
    session: AsyncSession, *, actor: AccessContext, organization_id: int,
    invitation_id: int,
) -> tuple[OrganizationInvitation, str]:
    """Issue a fresh token for an outstanding invitation.

    The previous token stops working immediately. Re-sending the *same* token
    would mean a link recovered from an old mailbox stays valid for as long as
    anybody keeps re-sending, which is the opposite of what re-issuing is for.
    """
    invitation = await _scoped_invitation(
        session, actor=actor, organization_id=organization_id,
        invitation_id=invitation_id)

    if invitation.status is not InvitationStatus.PENDING:
        raise OrganizationError(
            f"That invitation is {invitation.status.value}. Issue a new "
            f"invitation instead of reviving a closed one.")

    await _claim(session, OrganizationInvitation, invitation, None)

    token = secrets.token_urlsafe(32)
    now = _utcnow()
    invitation.token_hash = _hash_token(token)
    invitation.token_prefix = token[:8]
    invitation.expires_at = now + timedelta(
        hours=settings.invitation_ttl_hours)

    organization = await session.get(Organization, organization_id)
    provider = invitation_delivery.get_provider()
    result = provider.send(invitation_delivery.InvitationMessage(
        recipient_email=invitation.email,
        organization_name=organization.name if organization else "",
        role=invitation.role.value,
        invited_by=actor.username,
        expires_at=invitation.expires_at,
        link=invitation_delivery.build_invitation_link(token),
    ))
    invitation.delivery_provider = result.provider
    invitation.delivery_status = result.status
    invitation.delivery_detail = result.detail

    await _audit(
        session, organization_id=organization_id,
        event=OrganizationEvent.INVITATION_RESENT, actor=actor,
        subject_type="invitation", subject_id=invitation.id,
        summary=(f"{actor.username} re-issued the invitation to "
                 f"{invitation.email}. The previous link no longer works "
                 f"(invitation {invitation.token_prefix}…)."),
        detail={"delivery": result.status})
    await session.flush()
    return invitation, token


async def accept_invitation(
    session: AsyncSession, *, user: User, token: str,
) -> tuple[OrganizationInvitation, OrganizationMembership]:
    """Redeem a token, creating the membership it describes.

    Takes the acting ``User`` rather than an ``AccessContext``: the whole point
    is that the caller has no membership in this organization yet, so there is
    nothing for a context to authorise against. The token is the authorisation.

    Every failure — unknown token, revoked, expired, already used, wrong
    account — raises the same :class:`RecordNotVisible` with the same text.
    Distinguishing them would turn the endpoint into an oracle: "revoked" tells
    a stranger the token was real, which tells them the organization exists and
    that somebody there was inviting people.
    """
    if not token or len(token) > 512:
        raise RecordNotVisible("invitation")

    now = _utcnow()
    invitation = (await session.execute(
        select(OrganizationInvitation).where(
            OrganizationInvitation.token_hash == _hash_token(token))
    )).scalar_one_or_none()

    if invitation is None or not _invitation_is_live(invitation, now):
        raise RecordNotVisible("invitation")

    # The invitation was issued to an address, so it is redeemable only by the
    # account holding that address. Without this the token is a bearer
    # credential for a role in somebody else's organization, and forwarding the
    # message — accidentally or otherwise — would hand it over.
    if (user.email or "").strip().lower() != invitation.email:
        raise RecordNotVisible("invitation")

    organization = await session.get(Organization, invitation.organization_id)
    if organization is None or organization.status in {
            OrganizationStatus.ARCHIVED, OrganizationStatus.SUSPENDED}:
        raise RecordNotVisible("invitation")

    # Claim the row before creating anything. Two simultaneous redemptions of
    # one token reach here together; exactly one wins the conditional UPDATE,
    # and the other is refused rather than producing a second membership.
    await _claim(session, OrganizationInvitation, invitation, None)

    existing = (await session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id
            == invitation.organization_id,
            OrganizationMembership.user_id == user.id)
    )).scalar_one_or_none()

    if existing is not None and existing.status is MembershipStatus.ACTIVE:
        # Already a member. Spend the invitation anyway — it has been used, and
        # leaving it live would keep a working credential outstanding.
        membership = existing
    elif existing is not None:
        existing.role = invitation.role
        existing.scope = invitation.scope
        existing.status = MembershipStatus.ACTIVE
        existing.expires_at = invitation.membership_expires_at
        existing.external_organization = invitation.external_organization
        existing.may_download_attachments = invitation.may_download_attachments
        existing.updated_at = now
        existing.ended_at = None
        existing.ended_by = None
        existing.end_reason = None
        membership = existing
    else:
        membership = OrganizationMembership(
            organization_id=invitation.organization_id, user_id=user.id,
            role=invitation.role, scope=invitation.scope,
            status=MembershipStatus.ACTIVE,
            expires_at=invitation.membership_expires_at,
            external_organization=invitation.external_organization,
            may_download_attachments=invitation.may_download_attachments,
            invited_by=invitation.invited_by,
        )
        session.add(membership)

    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = now
    invitation.accepted_by = user.id
    await session.flush()

    await _audit(
        session, organization_id=invitation.organization_id,
        event=OrganizationEvent.INVITATION_ACCEPTED, actor=None,
        subject_type="membership", subject_id=membership.id,
        summary=(f"{user.username} accepted the invitation to "
                 f"{invitation.email} and joined as "
                 f"'{invitation.role.value}'."),
        detail={"invitation_id": invitation.id,
                "role": invitation.role.value,
                "expires_at": invitation.membership_expires_at})
    await session.flush()
    return invitation, membership


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

async def notify(
    session: AsyncSession, *, recipient_id: int, organization_id: int,
    event: NotificationType, summary: str,
    study_id: int | None = None, study_name: str | None = None,
    subject_type: str | None = None, subject_id: int | None = None,
    organization_name: str | None = None,
    idempotency_key: str | None = None,
) -> Notification:
    """Record one in-app notification.

    ``summary`` must be safe for somebody who later loses access to the
    record — see the note on :class:`Notification`. Callers pass a sentence
    about *what happened*, never a measurement, conclusion or file name.
    """
    if idempotency_key:
        existing = await session.scalar(select(Notification).where(
            Notification.recipient_id == recipient_id,
            Notification.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
    notification = Notification(
        recipient_id=recipient_id, organization_id=organization_id,
        organization_name=organization_name, study_id=study_id,
        study_name=study_name, event=event, subject_type=subject_type,
        subject_id=subject_id, summary=summary,
        idempotency_key=idempotency_key,
    )
    try:
        async with session.begin_nested():
            session.add(notification)
            await session.flush()
    except IntegrityError:
        if not idempotency_key:
            raise
        existing = await session.scalar(select(Notification).where(
            Notification.recipient_id == recipient_id,
            Notification.idempotency_key == idempotency_key))
        if existing is None:
            raise
        return existing
    session.add(NotificationAuditLog(
        notification_id=notification.id, recipient_id=recipient_id,
        event=NotificationAuditEvent.CREATED, actor_id=None))
    await session.flush()
    return notification


async def list_notifications(
    session: AsyncSession, *, actor: AccessContext, unread_only: bool = False,
    limit: int = 50,
) -> list[Notification]:
    """A person's own notifications. Never anybody else's."""
    query = select(Notification).where(
        Notification.recipient_id == actor.user_id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    query = query.order_by(Notification.created_at.desc(),
                           Notification.id.desc()).limit(min(limit, 200))
    return list((await session.execute(query)).scalars().all())


async def notification_unread_count(
    session: AsyncSession, *, actor: AccessContext,
) -> int:
    return int(await session.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == actor.user_id,
            Notification.read_at.is_(None))) or 0)


async def notification_target(
    session: AsyncSession, notification: Notification,
    actor: AccessContext,
) -> dict[str, str | None]:
    """Return a route only while the recipient can still reach its scope."""
    membership = actor.membership(notification.organization_id)
    if membership is None:
        return {"target_status": "inaccessible", "href": None}
    if (notification.study_id is not None
            and not membership.is_organization_wide
            and not actor.roles_on(notification.study_id)):
        return {"target_status": "inaccessible", "href": None}
    subject_id = notification.subject_id
    if notification.subject_type == "candidate" and subject_id:
        from nanobio_studio.app.db.validation_models import Candidate
        record = await session.get(Candidate, subject_id)
        if (record is None or record.organization_id != notification.organization_id
                or (notification.study_id is not None
                    and record.study_id != notification.study_id)):
            return {"target_status": "inaccessible", "href": None}
    elif notification.subject_type == "experiment" and subject_id:
        from nanobio_studio.app.db.validation_models import ValidationExperiment
        record = await session.get(ValidationExperiment, subject_id)
        if (record is None or record.organization_id != notification.organization_id
                or (notification.study_id is not None
                    and record.study_id != notification.study_id)):
            return {"target_status": "inaccessible", "href": None}
    routes = {
        "candidate": (f"/validation/candidates/{subject_id}/versions"
                      if subject_id else None),
        "experiment": (f"/validation/experiments/{subject_id}"
                       if subject_id else None),
        "account_security": "/settings/security",
        "organization": "/organization",
    }
    href = routes.get(notification.subject_type or "")
    return {"target_status": "available" if href else "no_link",
            "href": href}


async def mark_notification_read(
    session: AsyncSession, *, actor: AccessContext, notification_id: int,
) -> Notification:
    notification = await session.get(Notification, notification_id)
    # Not the recipient: 404, not 403. Otherwise the identifier space of
    # other people's notifications becomes probeable.
    if notification is None or notification.recipient_id != actor.user_id:
        raise RecordNotVisible("notification")
    if notification.read_at is None:
        notification.read_at = _utcnow()
        session.add(NotificationAuditLog(
            notification_id=notification.id,
            recipient_id=notification.recipient_id,
            event=NotificationAuditEvent.MARKED_READ,
            actor_id=actor.user_id))
        await session.flush()
    return notification


async def mark_notifications_read(
    session: AsyncSession, *, actor: AccessContext,
    notification_ids: list[int] | None = None,
) -> list[int]:
    query = select(Notification).where(
        Notification.recipient_id == actor.user_id,
        Notification.read_at.is_(None))
    if notification_ids is not None:
        unique_ids = sorted(set(notification_ids))
        if len(unique_ids) > 200:
            raise OrganizationError("At most 200 notifications may be updated.")
        query = query.where(Notification.id.in_(unique_ids))
    rows = list((await session.execute(query)).scalars().all())
    now = _utcnow()
    for notification in rows:
        notification.read_at = now
        session.add(NotificationAuditLog(
            notification_id=notification.id,
            recipient_id=notification.recipient_id,
            event=NotificationAuditEvent.BULK_MARKED_READ,
            actor_id=actor.user_id))
    await session.flush()
    return [row.id for row in rows]
