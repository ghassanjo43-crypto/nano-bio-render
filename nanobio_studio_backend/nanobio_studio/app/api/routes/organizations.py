"""Organization and study-team management.

Every route resolves an ``AccessContext`` and passes it to the service, which
is where the decision is made. Nothing here decides anything itself.

Two error shapes, and the difference matters
--------------------------------------------
* ``RecordNotVisible`` → **404**, for anything outside the caller's
  organizations. Raised by the service before any other validation runs, so a
  malformed request against a foreign organization still returns "not found"
  rather than a validation message that would confirm the organization exists.
* ``OrganizationError`` → **409**, for a request that is well-formed and
  authorised but conflicts with the model: the last owner, a duplicate
  membership, a role the target is not eligible for.

409 rather than 400 because these are state conflicts, not malformed input —
the same request may succeed once the state changes.
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.api.deps_auth import get_current_user
from nanobio_studio.app.api.deps_organization import get_access_context
from nanobio_studio.app.db.auth_models import User
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.db.organization_models import OrganizationEvent
from nanobio_studio.app.organizations.policy import (
    AccessContext, Action, PolicyDenied, RecordFacts, RecordNotVisible, may,
)
from nanobio_studio.app.organizations.vocabulary import (
    ACTIVE_MEMBERSHIP_STATUSES, ADMINISTRATIVE_ROLES,
    ROLE_MAY_BE_ASSIGNED_STUDY_ROLES, AccessScope, MembershipStatus,
    OrganizationRole, StudyRole,
)
from nanobio_studio.app.services import organization_service as svc
from nanobio_studio.app.services.invitation_delivery import (
    build_invitation_link,
)

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


def _error(code: str, message: str, http: int,
           detail: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=http, content={
        "error": code, "message": message, "detail": detail,
        "organizations_available": False,
    })


def _conflict(exc: svc.OrganizationError) -> JSONResponse:
    """409, with a code the interface can act on differently.

    A concurrency conflict is not the same kind of refusal as "that would
    remove the last owner". The first is answered by reloading and looking
    again; the second is answered by appointing another owner. Giving them one
    code would make the interface offer "retry" for both, and retrying a lost
    update is how the other administrator's change disappears.
    """
    code = ("concurrent_modification"
            if isinstance(exc, svc.ConcurrentModification) else "not_permitted")
    return _error(code, str(exc), status.HTTP_409_CONFLICT)


# ---------------------------------------------------------------------------
# Serialisation — explicit allow-lists, never the model object
# ---------------------------------------------------------------------------

def _organization_payload(organization, membership=None) -> dict:
    payload = {
        "id": organization.id,
        "slug": organization.slug,
        "name": organization.name,
        "description": organization.description,
        "status": organization.status.value,
        "is_legacy": organization.is_legacy,
        "awaiting_confirmation": (
            organization.status.value == "pending_confirmation"),
        "confirmed_at": organization.confirmed_at,
        "created_at": organization.created_at,
    }
    if membership is not None:
        payload["your_role"] = membership.role.value
        payload["your_scope"] = membership.scope.value
        payload["is_administrative"] = membership.role in ADMINISTRATIVE_ROLES
        payload["may_download_attachments"] = (
            membership.may_download_attachments)
    return payload


def _membership_payload(membership, user) -> dict:
    """Never includes a password hash, a token or an email address.

    The members screen needs a username and a role. An email address is
    personal data that the screen does not use, so it is not sent — a field
    that is not in the response cannot leak from it.
    """
    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "username": user.username,
        "role": membership.role.value,
        "is_administrative": membership.role in ADMINISTRATIVE_ROLES,
        "scope": membership.scope.value,
        "status": membership.status.value,
        "is_active": membership.status in ACTIVE_MEMBERSHIP_STATUSES,
        "starts_at": membership.starts_at,
        "expires_at": membership.expires_at,
        "external_organization": membership.external_organization,
        "is_external": membership.external_organization is not None,
        "may_download_attachments": membership.may_download_attachments,
        "created_at": membership.created_at,
        "ended_at": membership.ended_at,
        "end_reason": membership.end_reason,
        # Echoed so the client can send it back on the next write. This is what
        # makes a stale management screen fail loudly instead of overwriting
        # somebody else's change.
        "revision": membership.revision,
        "assignable_study_roles": sorted(
            r.value for r in ROLE_MAY_BE_ASSIGNED_STUDY_ROLES.get(
                membership.role, frozenset())),
    }


def _assignment_payload(assignment, user) -> dict:
    return {
        "id": assignment.id,
        "user_id": assignment.user_id,
        "username": user.username,
        "study_id": assignment.study_id,
        "role": assignment.role.value,
        "status": assignment.status.value,
        "is_active": assignment.status in ACTIVE_MEMBERSHIP_STATUSES,
        "starts_at": assignment.starts_at,
        "expires_at": assignment.expires_at,
        "may_download_attachments": assignment.may_download_attachments,
        "note": assignment.note,
        "permitted_subtypes": (
            json.loads(assignment.permitted_subtypes_json)
            if assignment.permitted_subtypes_json else None),
        "created_at": assignment.created_at,
        "ended_at": assignment.ended_at,
        "end_reason": assignment.end_reason,
        "revision": assignment.revision,
    }


def _invitation_payload(invitation, token: str | None = None) -> dict:
    """Never contains the token, except in the one response that issues it.

    ``token`` is passed only by the create and re-send handlers, and only into
    their own response. Every list and detail read omits it, because the row
    holds a hash and could not produce it even if this function asked.
    """
    payload = {
        "id": invitation.id,
        "organization_id": invitation.organization_id,
        "email": invitation.email,
        "role": invitation.role.value,
        "scope": invitation.scope.value,
        "status": invitation.status.value,
        "is_administrative": invitation.role in ADMINISTRATIVE_ROLES,
        "token_prefix": invitation.token_prefix,
        "expires_at": invitation.expires_at,
        "membership_expires_at": invitation.membership_expires_at,
        "external_organization": invitation.external_organization,
        "is_external": invitation.external_organization is not None,
        "may_download_attachments": invitation.may_download_attachments,
        "delivery_provider": invitation.delivery_provider,
        "delivery_status": invitation.delivery_status,
        "delivery_detail": invitation.delivery_detail,
        "created_at": invitation.created_at,
        "accepted_at": invitation.accepted_at,
        "ended_at": invitation.ended_at,
        "end_reason": invitation.end_reason,
    }
    if token is not None:
        payload["invitation_link"] = build_invitation_link(token)
        payload["link_shown_once"] = True
        payload["notice"] = (
            "This link is shown once and cannot be retrieved again. It can be "
            "used a single time and grants the role above when accepted. If "
            "it is lost, re-issue the invitation — which also stops the "
            "previous link working.")
    return payload


def _audit_payload(row) -> dict:
    return {
        "id": row.id,
        "event": row.event.value,
        "subject_type": row.subject_type,
        "subject_id": row.subject_id,
        "actor_username": row.actor_username,
        "summary": row.summary,
        "created_at": row.created_at,
    }


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class OrganizationCreateRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class MemberAddRequest(BaseModel):
    user_id: int
    role: str
    scope: str | None = None
    expires_at: datetime | None = None
    external_organization: str | None = Field(default=None, max_length=200)
    may_download_attachments: bool = True


class MemberRoleRequest(BaseModel):
    role: str | None = None
    scope: str | None = None
    #: The revision the screen was rendered from. Optional, because a script
    #: acting on a value it read a moment earlier does not need it — the
    #: service still checks the revision it loaded. Supplying it upgrades the
    #: check from "nothing changed during this request" to "nothing changed
    #: since you looked", which is what an administration screen needs.
    expected_revision: int | None = None


class MemberStatusRequest(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=1000)
    expected_revision: int | None = None


class MemberRevokeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
    expected_revision: int | None = None


class InvitationCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str
    scope: str | None = None
    #: When the *membership* should expire, not the link.
    expires_at: datetime | None = None
    external_organization: str | None = Field(default=None, max_length=200)
    may_download_attachments: bool = True
    ttl_hours: int | None = Field(default=None, ge=1, le=24 * 30)


class InvitationRevokeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class InvitationAcceptRequest(BaseModel):
    #: The token, and nothing else. There is deliberately no `next`,
    #: `redirect` or `return_to` field: an invitation link that could be told
    #: where to land afterwards is a phishing primitive carrying an
    #: organization's name. Where acceptance leads is decided by the
    #: application, not by whoever composed the link.
    token: str = Field(min_length=8, max_length=512)


class AssignmentCreateRequest(BaseModel):
    user_id: int
    role: str
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    permitted_subtypes: list[str] | None = None
    #: ``False`` withholds attachment downloads on this study alone. ``None``
    #: defers to the membership. It can only restrict — see the policy.
    may_download_attachments: bool | None = None
    note: str | None = Field(default=None, max_length=1000)


class AssignmentAmendRequest(BaseModel):
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    permitted_subtypes: list[str] | None = None
    may_download_attachments: bool | None = None
    note: str | None = Field(default=None, max_length=1000)
    expected_revision: int | None = None


class AssignmentRevokeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
    expected_revision: int | None = None


def _enum(raw: str, enum_cls, label: str):
    try:
        return enum_cls(raw)
    except ValueError:
        permitted = ", ".join(sorted(m.value for m in enum_cls))
        raise svc.OrganizationError(
            f"{raw!r} is not a {label}. Permitted: {permitted}.")


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

@router.get("", summary="Organizations you belong to")
async def list_organizations(
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Drives the switcher.

    Returns only organizations with an in-force membership. One with no
    memberships gets an empty list rather than an error — that is a legitimate
    state for a newly created account, and the interface needs to render it.
    """
    rows = await svc.list_organizations(session, actor=ctx)
    return {
        "organizations": [_organization_payload(o, m) for o, m in rows],
        "active_organization_id": ctx.active_organization_id,
        # The contract: one organization may be selected automatically;
        # several must be chosen explicitly and are never guessed.
        "requires_explicit_selection": len(rows) > 1,
    }


@router.post("", status_code=status.HTTP_201_CREATED,
             summary="Create an organization")
async def create_organization(
    request: OrganizationCreateRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        organization = await svc.create_organization(
            session, actor=ctx, slug=request.slug, name=request.name,
            description=request.description)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    return _organization_payload(organization)


@router.get("/{organization_id}", summary="Organization profile")
async def get_organization(
    organization_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    organization = await svc.get_organization(
        session, actor=ctx, organization_id=organization_id)
    membership = ctx.membership(organization_id)
    payload = _organization_payload(organization)
    if membership is not None:
        payload["your_role"] = membership.role.value
        payload["is_administrative"] = membership.role in ADMINISTRATIVE_ROLES
    # What the interface may offer. Advisory only — every one of these is
    # re-checked by the service when the action is actually attempted.
    facts = RecordFacts(organization_id=organization_id)
    payload["capabilities"] = {
        action.value: may(ctx, action, facts)[0]
        for action in (Action.MANAGE_ORGANIZATION, Action.MANAGE_MEMBERS,
                       Action.MANAGE_ASSIGNMENTS, Action.VIEW_ACCESS_HISTORY)
    }
    return payload


@router.patch("/{organization_id}", summary="Update the organization profile")
async def update_organization(
    organization_id: int, request: OrganizationUpdateRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        organization = await svc.update_organization(
            session, actor=ctx, organization_id=organization_id,
            name=request.name, description=request.description)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    return _organization_payload(organization)


@router.post("/{organization_id}/confirm",
             summary="Confirm a migrated organization")
async def confirm_organization(
    organization_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Lift the hold placed on an upgraded organization.

    Grants no scientific authority to anybody. It only releases the block on
    scientific writes; approvers must still be appointed explicitly.
    """
    try:
        organization = await svc.confirm_organization(
            session, actor=ctx, organization_id=organization_id)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    payload = _organization_payload(organization)
    payload["notice"] = (
        "Scientific changes are now permitted. No reviewer or approver was "
        "created by confirming; appoint them explicitly.")
    return payload


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

@router.get("/{organization_id}/members", summary="Members and their roles")
async def list_members(
    organization_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    rows = await svc.list_members(
        session, actor=ctx, organization_id=organization_id)
    return {
        "organization_id": organization_id,
        "members": [_membership_payload(m, u) for m, u in rows],
    }


@router.get("/{organization_id}/members/{membership_id}",
            summary="One membership in detail")
async def get_member(
    organization_id: int, membership_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """The organization in the path is checked against the stored row.

    A membership identifier from another organization returns 404 even when
    the caller administers the organization they named — the path segment is
    not decoration, and injecting a foreign parent must not widen anything.
    """
    membership, target = await svc.get_membership(
        session, actor=ctx, organization_id=organization_id,
        membership_id=membership_id)
    payload = _membership_payload(membership, target)
    payload["invited_by"] = membership.invited_by
    return payload


@router.get("/{organization_id}/collaborators",
            summary="External collaborators")
async def list_collaborators(
    organization_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Everyone from outside this organization who can currently reach it.

    Least privilege is only auditable if it is legible, and it is not legible
    from a members list of forty rows where four of them are external. This is
    the same data, asked as the question an access review actually asks.
    """
    rows = await svc.list_collaborators(
        session, actor=ctx, organization_id=organization_id)
    return {
        "organization_id": organization_id,
        "collaborators": [_membership_payload(m, u) for m, u in rows],
        "notice": (
            "External collaborators reach only the studies they are "
            "explicitly assigned to. Organization-wide records are never "
            "included, and expiry is evaluated on every request."),
    }


@router.post("/{organization_id}/members",
             status_code=status.HTTP_201_CREATED, summary="Add a member")
async def add_member(
    organization_id: int, request: MemberAddRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        role = _enum(request.role, OrganizationRole, "organization role")
        scope = (_enum(request.scope, AccessScope, "access scope")
                 if request.scope else None)
        membership = await svc.add_member(
            session, actor=ctx, organization_id=organization_id,
            user_id=request.user_id, role=role, scope=scope,
            expires_at=request.expires_at,
            external_organization=request.external_organization,
            may_download_attachments=request.may_download_attachments)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    target = await session.get(User, request.user_id)
    return _membership_payload(membership, target)


@router.patch("/{organization_id}/members/{membership_id}",
              summary="Change a member's organization role")
async def change_member_role(
    organization_id: int, membership_id: int, request: MemberRoleRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Refuses a self-change. See docs/APPOINTMENT_AUTHORITY.md."""
    try:
        role = (_enum(request.role, OrganizationRole, "organization role")
                if request.role else None)
        scope = (_enum(request.scope, AccessScope, "access scope")
                 if request.scope else None)
        membership = await svc.change_member_role(
            session, actor=ctx, membership_id=membership_id,
            role=role, scope=scope,
            expected_revision=request.expected_revision)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    target = await session.get(User, membership.user_id)
    return _membership_payload(membership, target)


@router.post("/{organization_id}/members/{membership_id}/status",
             summary="Suspend or reinstate a member")
async def set_member_status(
    organization_id: int, membership_id: int, request: MemberStatusRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        new_status = _enum(request.status, MembershipStatus,
                           "membership status")
        membership = await svc.set_membership_status(
            session, actor=ctx, membership_id=membership_id,
            status=new_status, reason=request.reason,
            expected_revision=request.expected_revision)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    target = await session.get(User, membership.user_id)
    return _membership_payload(membership, target)


@router.delete("/{organization_id}/members/{membership_id}",
               summary="Revoke a membership")
async def revoke_member(
    organization_id: int, membership_id: int,
    request: MemberRevokeRequest | None = None,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Ends access. The row survives, so attribution survives with it."""
    try:
        membership = await svc.revoke_member(
            session, actor=ctx, membership_id=membership_id,
            reason=request.reason if request else None,
            expected_revision=(request.expected_revision
                               if request else None))
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    target = await session.get(User, membership.user_id)
    payload = _membership_payload(membership, target)
    payload["notice"] = (
        "Access has ended. Historical attribution on work this person "
        "performed is unchanged.")
    return payload


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------

@router.get("/{organization_id}/invitations", summary="Outstanding invitations")
async def list_invitations(
    organization_id: int,
    include_closed: bool = Query(False),
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    rows = await svc.list_invitations(
        session, actor=ctx, organization_id=organization_id,
        include_closed=include_closed)
    return {
        "organization_id": organization_id,
        "invitations": [_invitation_payload(i) for i in rows],
        "delivery_provider": svc.invitation_delivery.get_provider().name,
    }


@router.post("/{organization_id}/invitations",
             status_code=status.HTTP_201_CREATED,
             summary="Invite somebody to the organization")
async def create_invitation(
    organization_id: int, request: InvitationCreateRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Issue a single-use invitation. The link is returned once, here.

    The response is identical whether or not the address already has an
    account, so this cannot be used to enumerate the installation's users.

    No password is set, transmitted or displayed anywhere in this flow. The
    recipient signs in with their own credentials and redeems the token; an
    administrator never learns, chooses or resets it.
    """
    try:
        role = _enum(request.role, OrganizationRole, "organization role")
        scope = (_enum(request.scope, AccessScope, "access scope")
                 if request.scope else None)
        invitation, token = await svc.invite_member(
            session, actor=ctx, organization_id=organization_id,
            email=request.email, role=role, scope=scope,
            membership_expires_at=request.expires_at,
            external_organization=request.external_organization,
            may_download_attachments=request.may_download_attachments,
            ttl_hours=request.ttl_hours)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    return _invitation_payload(invitation, token=token)


@router.post("/{organization_id}/invitations/{invitation_id}/resend",
             summary="Re-issue an invitation")
async def resend_invitation(
    organization_id: int, invitation_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Issues a new token and invalidates the previous one."""
    try:
        invitation, token = await svc.resend_invitation(
            session, actor=ctx, organization_id=organization_id,
            invitation_id=invitation_id)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    return _invitation_payload(invitation, token=token)


@router.delete("/{organization_id}/invitations/{invitation_id}",
               summary="Withdraw an invitation")
async def revoke_invitation(
    organization_id: int, invitation_id: int,
    request: InvitationRevokeRequest | None = None,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        invitation = await svc.revoke_invitation(
            session, actor=ctx, organization_id=organization_id,
            invitation_id=invitation_id,
            reason=request.reason if request else None)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    return _invitation_payload(invitation)


@router.post("/invitations/accept", summary="Accept an invitation")
async def accept_invitation(
    request: InvitationAcceptRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Redeem a token as the signed-in account.

    Requires an authenticated caller, and the account's address must match the
    one invited. The token authorises joining an organization the caller has no
    membership in, so the ``AccessContext`` is resolved — every route does —
    but it is deliberately not what decides this.

    A bad token of any kind returns the same 404 with the same body. An
    endpoint that distinguished "revoked" from "unknown" would confirm to a
    stranger that a token they hold was once real.
    """
    try:
        invitation, membership = await svc.accept_invitation(
            session, user=user, token=request.token)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    return {
        "organization_id": invitation.organization_id,
        "membership_id": membership.id,
        "role": membership.role.value,
        "is_administrative": membership.role in ADMINISTRATIVE_ROLES,
        "expires_at": membership.expires_at,
        "notice": (
            "You are now a member of this organization. This grants no "
            "scientific authority on any study: reviewing and approving "
            "require an explicit study assignment."),
    }


# ---------------------------------------------------------------------------
# Study teams
# ---------------------------------------------------------------------------

@router.get("/{organization_id}/studies/{study_id}/team",
            summary="Study team and scientific assignments")
async def list_study_team(
    organization_id: int, study_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    rows = await svc.list_assignments(session, actor=ctx, study_id=study_id)
    return {
        "study_id": study_id,
        "assignments": [_assignment_payload(a, u) for a, u in rows],
    }


@router.post("/{organization_id}/studies/{study_id}/team",
             status_code=status.HTTP_201_CREATED,
             summary="Assign somebody a scientific role on a study")
async def assign_to_study(
    organization_id: int, study_id: int, request: AssignmentCreateRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Appointment is administrative; eligibility comes from the org role.

    An administrator cannot appoint somebody to a study role their
    organization role does not permit, and cannot change their own
    organization role to become eligible. See docs/APPOINTMENT_AUTHORITY.md.
    """
    try:
        role = _enum(request.role, StudyRole, "study role")
        assignment = await svc.assign_to_study(
            session, actor=ctx, study_id=study_id, user_id=request.user_id,
            role=role, starts_at=request.starts_at,
            expires_at=request.expires_at,
            permitted_subtypes=request.permitted_subtypes,
            may_download_attachments=request.may_download_attachments,
            note=request.note)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    target = await session.get(User, request.user_id)
    return _assignment_payload(assignment, target)


@router.patch("/{organization_id}/studies/{study_id}/team/{assignment_id}",
              summary="Amend an assignment")
async def amend_assignment(
    organization_id: int, study_id: int, assignment_id: int,
    request: AssignmentAmendRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        assignment = await svc.amend_assignment(
            session, actor=ctx, assignment_id=assignment_id,
            starts_at=request.starts_at, expires_at=request.expires_at,
            permitted_subtypes=request.permitted_subtypes,
            may_download_attachments=request.may_download_attachments,
            note=request.note,
            expected_revision=request.expected_revision)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    target = await session.get(User, assignment.user_id)
    return _assignment_payload(assignment, target)


@router.delete("/{organization_id}/studies/{study_id}/team/{assignment_id}",
               summary="Revoke an assignment")
async def revoke_assignment(
    organization_id: int, study_id: int, assignment_id: int,
    request: AssignmentRevokeRequest | None = None,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        assignment = await svc.revoke_assignment(
            session, actor=ctx, assignment_id=assignment_id,
            reason=request.reason if request else None,
            expected_revision=(request.expected_revision
                               if request else None))
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    target = await session.get(User, assignment.user_id)
    payload = _assignment_payload(assignment, target)
    payload["notice"] = (
        "Access ends from the next request. Records this person performed or "
        "authored still name them — revocation governs what happens next, not "
        "what already happened.")
    return payload


@router.get("/{organization_id}/studies/{study_id}/team/history",
            summary="Assignment and revocation history")
async def study_team_history(
    organization_id: int, study_id: int,
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Who was appointed, amended and revoked on this study, and by whom.

    Administrative rather than member-visible: the team list says who is on the
    study now, which any member may see; this says who granted it, which is
    access-control information.
    """
    rows = await svc.assignment_history(
        session, actor=ctx, study_id=study_id, limit=limit)
    return {"study_id": study_id, "events": [_audit_payload(r) for r in rows]}


# ---------------------------------------------------------------------------
# Access history
# ---------------------------------------------------------------------------

@router.get("/{organization_id}/audit", summary="Access and audit history")
async def access_history(
    organization_id: int,
    limit: int = Query(200, ge=1, le=500),
    subject_type: str | None = Query(
        None, description="membership | study_assignment | invitation | "
                          "organization"),
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Append-only. Nothing in this API amends or deletes an audit row."""
    if subject_type is not None and subject_type not in {
            "membership", "study_assignment", "invitation", "organization"}:
        return _error("invalid_filter",
                      "Unknown subject type.", status.HTTP_400_BAD_REQUEST)
    rows = await svc.access_history(
        session, actor=ctx, organization_id=organization_id, limit=limit,
        subject_type=subject_type)
    return {
        "organization_id": organization_id,
        "events": [_audit_payload(r) for r in rows],
        "append_only": True,
    }


@router.post("/{organization_id}/maintenance/expire",
             summary="Mark lapsed memberships, assignments and invitations")
async def expire_lapsed(
    organization_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Housekeeping only. Changes nothing about who can do what.

    Expiry is already evaluated on every request, so a lapsed row grants
    nothing whether or not this has run. What this fixes is the *display*: a
    members screen showing ``active`` beside a date in the past is technically
    accurate about the stored status and misleading about the access, and an
    access review reads the screen.
    """
    try:
        require_admin = svc.RecordFacts(organization_id=organization_id)
        svc.require(ctx, Action.MANAGE_MEMBERS, require_admin)
        counts = await svc.expire_due_memberships(session)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    return {"organization_id": organization_id, "expired": counts,
            "notice": ("Housekeeping only. Expiry was already in force on "
                       "every request; this updates what the screens show.")}


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationReadRequest(BaseModel):
    ids: list[int] | None = Field(
        default=None, max_length=200,
        description="Notification ids, or null to mark every unread item.")


async def _notification_json(n, ctx: AccessContext,
                             session: AsyncSession) -> dict:
    target = await svc.notification_target(session, n, ctx)
    return {
        "id": n.id, "event": n.event.value,
        "organization_id": n.organization_id,
        "study_id": n.study_id, "subject_type": n.subject_type,
        "subject_id": n.subject_id, "summary": n.summary,
        "created_at": n.created_at, "read_at": n.read_at,
        "is_read": n.is_read, **target,
    }

@router.get("/notifications/mine", summary="Your own notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    rows = await svc.list_notifications(
        session, actor=ctx, unread_only=unread_only, limit=limit)
    return {"notifications": [await _notification_json(n, ctx, session)
                              for n in rows],
            "unread_count": await svc.notification_unread_count(
                session, actor=ctx)}


@router.get("/notifications/unread-count", summary="Your unread count")
async def unread_notification_count(
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    return {"unread_count": await svc.notification_unread_count(
        session, actor=ctx)}


@router.post("/notifications/{notification_id}/read",
             summary="Mark a notification read")
async def mark_notification_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    notification = await svc.mark_notification_read(
        session, actor=ctx, notification_id=notification_id)
    await session.commit()
    return {"id": notification.id, "read_at": notification.read_at,
            "is_read": notification.is_read}


@router.post("/notifications/mark-read", summary="Mark notifications read")
async def mark_notifications_read(
    request: NotificationReadRequest,
    user: User = Depends(get_current_user),
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    try:
        changed = await svc.mark_notifications_read(
            session, actor=ctx, notification_ids=request.ids)
        await session.commit()
    except svc.OrganizationError as exc:
        await session.rollback()
        return _conflict(exc)
    return {"marked_read_ids": changed,
            "marked_read_count": len(changed),
            "unread_count": await svc.notification_unread_count(
                session, actor=ctx)}
