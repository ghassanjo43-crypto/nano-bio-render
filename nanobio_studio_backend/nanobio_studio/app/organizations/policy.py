"""The single authorization policy for organization-scoped records.

What this replaces
------------------
``validation/permissions.py`` granted ``Capability.VIEW`` to every
authenticated user, unconditionally, on every record in the database. That was
adequate while the deployment was one laboratory; it is a cross-tenant read of
everything the moment a second organization exists.

This module is the one place the question "may this person do this to this
record" is answered. Routes call it. Services call it. Nothing decides for
itself, and the frontend decides nothing at all — hiding a control is a
courtesy to the user, never a control on the data.

The seven inputs
----------------
A decision composes, in this order:

1. **Platform role** — ``auth_users.role``. Governs the deployment, not the
   science. A platform admin can reach organization administration and cannot
   thereby touch evidence.
2. **Organization membership** — is the actor in the record's organization, is
   the membership ACTIVE, and has it expired?
3. **Study assignment** — the sole source of scientific capability.
4. **Scientific role** — which study role, and does it permit this verb?
5. **Ownership / contribution** — did the actor create this record?
6. **Experiment status** — a draft is editable, an approved record is not.
7. **Performer / authorship conflict** — did this actor perform or materially
   author the thing they are proposing to approve?

Absence is the default answer
-----------------------------
``visible_organization_ids`` and ``visible_study_ids`` return what the actor may
see, and the query layer intersects with them *inside the SQL*. A record in
another organization is not fetched and then hidden; it is never selected. The
route then cannot tell a caller "forbidden", because it does not have the row —
so ``RecordNotVisible`` maps to **404**, and asking for an identifier reveals
nothing about whether it exists.

Denial is recorded
------------------
A refused cross-organization read writes an ``ACCESS_DENIED`` audit row. One is
somebody following a stale link. A hundred is somebody walking the identifier
space, and that is only visible if the misses are recorded as well as the hits.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.auth_models import User, UserRole
from nanobio_studio.app.db.organization_models import (
    Organization, OrganizationMembership, StudyAssignment,
)
from nanobio_studio.app.organizations.vocabulary import (
    ACTIVE_MEMBERSHIP_STATUSES, ADMINISTRATIVE_ROLES, AccessScope,
    MembershipStatus, OrganizationRole, OrganizationStatus,
    REVIEW_CAPABLE_STUDY_ROLES, StudyRole,
)

__all__ = [
    "Action",
    "AccessContext",
    "PolicyDenied",
    "RecordNotVisible",
    "RecordFacts",
    "resolve_context",
    "visible_organization_ids",
    "visible_study_ids",
    "may",
    "require",
    "REPORT_ACTIONS",
    "REPORT_ROLE_ACTIONS",
    "REPORT_OWNER_ONLY_ACTIONS",
    "writing_organization_for",
]


class PolicyDenied(Exception):
    """The actor may see the record but not perform this action → 403."""

    def __init__(self, action: "Action", reason: str) -> None:
        super().__init__(reason)
        self.action = action
        self.reason = reason


class RecordNotVisible(Exception):
    """The record is outside the actor's organizations → 404, never 403.

    Raised instead of ``PolicyDenied`` whenever telling the truth would confirm
    that an identifier belongs to a real record in an organization the caller
    has nothing to do with.
    """

    def __init__(self, record_type: str = "record") -> None:
        super().__init__(f"{record_type} not found")
        self.record_type = record_type


class Action(str, enum.Enum):
    """Every verb the policy arbitrates."""

    # --- reading ---
    VIEW_ORGANIZATION = "view_organization"
    VIEW_STUDY = "view_study"
    VIEW_EXPERIMENT = "view_experiment"
    VIEW_ATTACHMENT = "view_attachment"
    DOWNLOAD_ATTACHMENT = "download_attachment"
    VIEW_AUDIT = "view_audit"
    VIEW_READINESS = "view_readiness"

    # --- science ---
    CREATE_CANDIDATE = "create_candidate"
    CREATE_VERSION = "create_version"
    CREATE_EXPERIMENT = "create_experiment"
    EDIT_DRAFT = "edit_draft"
    ADD_MEASUREMENT = "add_measurement"
    ADD_ATTACHMENT = "add_attachment"
    DELETE_ATTACHMENT = "delete_attachment"
    SUBMIT = "submit"
    START_REVIEW = "start_review"
    REQUEST_REVISION = "request_revision"
    REJECT = "reject"
    APPROVE = "approve"
    RESOLVE_CONTRADICTION = "resolve_contradiction"

    # --- medical reports ---
    # Separate verbs rather than reusing the scientific ones, because a report
    # assessment hangs off no study. Folding them into SCIENTIFIC_ACTIONS would
    # require a study assignment that cannot exist, so every report request
    # would be refused; folding them into the general read branch would let an
    # organization administrator read patient assessments, which is the exact
    # thing this separation exists to prevent.
    VIEW_REPORT = "view_report"
    CREATE_REPORT = "create_report"
    AMEND_REPORT = "amend_report"
    DOWNLOAD_REPORT_DOCUMENT = "download_report_document"
    DELETE_REPORT = "delete_report"
    VIEW_REPORT_HISTORY = "view_report_history"
    PURGE_REPORTS = "purge_reports"

    # --- administration ---
    MANAGE_ORGANIZATION = "manage_organization"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_ASSIGNMENTS = "manage_assignments"
    MANAGE_COLLABORATORS = "manage_collaborators"
    VIEW_ACCESS_HISTORY = "view_access_history"
    MANAGE_ACCOUNTS = "manage_accounts"


#: Verbs that change evidence. An administrative role never grants these, no
#: matter how privileged it is.
SCIENTIFIC_ACTIONS = frozenset({
    Action.CREATE_CANDIDATE, Action.CREATE_VERSION, Action.CREATE_EXPERIMENT,
    Action.EDIT_DRAFT, Action.ADD_MEASUREMENT, Action.ADD_ATTACHMENT,
    Action.DELETE_ATTACHMENT, Action.SUBMIT, Action.START_REVIEW,
    Action.REQUEST_REVISION, Action.REJECT, Action.APPROVE,
    Action.RESOLVE_CONTRADICTION,
})

#: Verbs over patient assessments.
#:
#: A report holds the most sensitive data in the application, and it belongs to
#: an organization rather than to a study. So it gets its own branch, and its
#: own table of who may do what — reproduced in
#: ``docs/MEDICAL_REPORT_PATHWAY.md``.
REPORT_ACTIONS = frozenset({
    Action.VIEW_REPORT, Action.CREATE_REPORT, Action.AMEND_REPORT,
    Action.DOWNLOAD_REPORT_DOCUMENT, Action.DELETE_REPORT,
    Action.VIEW_REPORT_HISTORY, Action.PURGE_REPORTS,
})

#: Which organization roles may perform each report verb.
#:
#: Two absences are the whole design and neither is an oversight.
#:
#: **OWNER and ADMINISTRATOR appear nowhere except history and purge.** An
#: organization administrator manages people and access; letting that role read
#: patient assessments would mean the account that can add itself to anything
#: is also the account that can read every clinical document. History is
#: administrative information — who touched what, not what it said — and purge
#: acts on dates rather than content, so both are theirs.
#:
#: **LAB_CONTRIBUTOR appears nowhere at all.** That is the external CRO role.
#: A contract laboratory has no business reading a patient's report under any
#: assignment, and there is deliberately no way to grant it.
REPORT_ROLE_ACTIONS: dict[OrganizationRole, frozenset[Action]] = {
    OrganizationRole.OWNER: frozenset({
        Action.VIEW_REPORT_HISTORY, Action.PURGE_REPORTS,
    }),
    OrganizationRole.ADMINISTRATOR: frozenset({
        Action.VIEW_REPORT_HISTORY,
    }),
    OrganizationRole.RESEARCHER: frozenset({
        Action.VIEW_REPORT, Action.CREATE_REPORT, Action.AMEND_REPORT,
        Action.DOWNLOAD_REPORT_DOCUMENT, Action.DELETE_REPORT,
        Action.VIEW_REPORT_HISTORY,
    }),
    OrganizationRole.REVIEWER: frozenset({
        Action.VIEW_REPORT, Action.CREATE_REPORT, Action.AMEND_REPORT,
        Action.DOWNLOAD_REPORT_DOCUMENT, Action.VIEW_REPORT_HISTORY,
    }),
    OrganizationRole.APPROVER: frozenset({
        Action.VIEW_REPORT, Action.CREATE_REPORT, Action.AMEND_REPORT,
        Action.DOWNLOAD_REPORT_DOCUMENT, Action.VIEW_REPORT_HISTORY,
    }),
    #: Reads the trail, not the documents. That is the entire role.
    OrganizationRole.AUDITOR: frozenset({
        Action.VIEW_REPORT_HISTORY,
    }),
    OrganizationRole.LAB_CONTRIBUTOR: frozenset(),
}

#: Report verbs that only the record's own author may perform.
#:
#: Amendment and deletion change or destroy a clinical judgement. Somebody
#: else's colleague with organization-wide *read* scope may look at it; only
#: its author may alter it, and nobody at all may alter it on behalf of the
#: author. That keeps "who decided this field said X" answerable.
REPORT_OWNER_ONLY_ACTIONS = frozenset({
    Action.AMEND_REPORT, Action.DELETE_REPORT,
})

#: Verbs that change access.
ADMINISTRATIVE_ACTIONS = frozenset({
    Action.MANAGE_ORGANIZATION, Action.MANAGE_MEMBERS,
    Action.MANAGE_ASSIGNMENTS, Action.MANAGE_COLLABORATORS,
    Action.MANAGE_ACCOUNTS,
})

#: Which study roles may perform which scientific verb.
STUDY_ROLE_ACTIONS: dict[StudyRole, frozenset[Action]] = {
    StudyRole.OWNER: frozenset({
        Action.CREATE_CANDIDATE, Action.CREATE_VERSION,
        Action.CREATE_EXPERIMENT, Action.EDIT_DRAFT, Action.ADD_MEASUREMENT,
        Action.ADD_ATTACHMENT, Action.DELETE_ATTACHMENT, Action.SUBMIT,
    }),
    StudyRole.CONTRIBUTOR: frozenset({
        Action.CREATE_CANDIDATE, Action.CREATE_VERSION,
        Action.CREATE_EXPERIMENT, Action.EDIT_DRAFT, Action.ADD_MEASUREMENT,
        Action.ADD_ATTACHMENT, Action.DELETE_ATTACHMENT, Action.SUBMIT,
    }),
    #: A laboratory contributor enters results and nothing else. No candidate
    #: creation: defining what is being tested is the sponsor's call, not the
    #: contract laboratory's.
    StudyRole.LAB_CONTRIBUTOR: frozenset({
        Action.EDIT_DRAFT, Action.ADD_MEASUREMENT, Action.ADD_ATTACHMENT,
        Action.SUBMIT,
    }),
    StudyRole.REVIEWER: frozenset({
        Action.START_REVIEW, Action.REQUEST_REVISION, Action.REJECT,
        Action.RESOLVE_CONTRADICTION,
    }),
    StudyRole.APPROVER: frozenset({
        Action.START_REVIEW, Action.REQUEST_REVISION, Action.REJECT,
        Action.APPROVE, Action.RESOLVE_CONTRADICTION,
    }),
    #: Reads only. This is the entire content of the role.
    StudyRole.AUDITOR: frozenset(),
}


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite drops tzinfo on write; treat a naive timestamp as UTC.

    Without this an expiry comparison raises ``TypeError`` on a database that
    round-tripped through SQLite, which would turn an access check into a 500.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_in_force(status: MembershipStatus, starts_at: datetime | None,
                 expires_at: datetime | None, now: datetime) -> bool:
    """Is this membership or assignment granting anything right now?

    Expiry is evaluated here rather than relying on a sweep job having run.
    A row whose ``expires_at`` has passed grants nothing from that instant,
    whether or not anything has got round to marking it EXPIRED.
    """
    if status not in ACTIVE_MEMBERSHIP_STATUSES:
        return False
    starts = _as_utc(starts_at)
    if starts is not None and now < starts:
        return False
    expires = _as_utc(expires_at)
    if expires is not None and now >= expires:
        return False
    return True


@dataclass(frozen=True)
class AccessContext:
    """Everything the policy knows about one actor, resolved once per request.

    Built by :func:`resolve_context` with a bounded number of queries, then
    passed down through the service layer. Services must not re-derive any of
    this: one resolution per request is what makes the answer consistent for
    the whole of that request.
    """

    user_id: int
    username: str
    platform_role: UserRole
    is_active: bool

    #: organization_id → membership facts, for organizations where the
    #: membership is in force *now*.
    memberships: dict[int, "MembershipFacts"] = field(default_factory=dict)

    #: study_id → the study roles in force now.
    study_roles: dict[int, frozenset[StudyRole]] = field(default_factory=dict)

    #: study_id → organization_id, for every study reachable through an
    #: assignment. Lets a study-scoped check avoid a join.
    study_organizations: dict[int, int] = field(default_factory=dict)

    #: Studies on which *some* in-force assignment withholds attachment
    #: downloads. Stored as the denial rather than the permission, so a study
    #: absent from this set is one nothing has restricted — the direction that
    #: fails safe if an assignment is ever missed when building the context.
    #:
    #: A restriction on any one assignment restricts the study: somebody
    #: holding both a general contributor assignment and a narrower one under a
    #: contract that forbids taking raw files off-site is bound by the narrower.
    studies_without_downloads: frozenset[int] = frozenset()

    #: The organization the client asked to act within, if it named one.
    active_organization_id: int | None = None

    def membership(self, organization_id: int) -> "MembershipFacts | None":
        """The membership in force *for this request*.

        Respects the active-organization selection. When the client has named
        an organization, memberships in every other organization report as
        absent — so selecting one narrows authorization consistently, without
        each caller having to remember to intersect.

        This is the central enforcement of the contract's "selection narrows"
        rule. Reading ``self.memberships`` directly bypasses it, and exactly
        one caller is entitled to do that: the organization switcher, which
        must keep listing everything the user belongs to or they could never
        switch away.
        """
        if (self.active_organization_id is not None
                and organization_id != self.active_organization_id):
            return None
        return self.memberships.get(organization_id)

    def is_member_of(self, organization_id: int) -> bool:
        return self.membership(organization_id) is not None

    def all_memberships(self) -> dict[int, "MembershipFacts"]:
        """Every membership, ignoring the active-organization selection.

        Only for the switcher. Named verbosely so its use stands out in
        review — anything else calling this is very likely a scoping bug.
        """
        return dict(self.memberships)

    def roles_on(self, study_id: int) -> frozenset[StudyRole]:
        return self.study_roles.get(study_id, frozenset())

    def is_org_administrator(self, organization_id: int) -> bool:
        m = self.memberships.get(organization_id)
        return m is not None and m.role in ADMINISTRATIVE_ROLES


@dataclass(frozen=True)
class MembershipFacts:
    organization_id: int
    role: OrganizationRole
    scope: AccessScope
    may_download_attachments: bool
    is_external: bool
    expires_at: datetime | None
    organization_status: OrganizationStatus

    @property
    def is_organization_wide(self) -> bool:
        return self.scope is AccessScope.ORGANIZATION

    @property
    def awaiting_confirmation(self) -> bool:
        """True while an upgraded organization has not been confirmed.

        Reads are permitted; scientific and administrative changes are not,
        until an administrator has looked at the memberships the migration
        proposed and said they are right.
        """
        return self.organization_status is OrganizationStatus.PENDING_CONFIRMATION


async def resolve_context(
    session: AsyncSession,
    user: User,
    active_organization_id: int | None = None,
) -> AccessContext:
    """Load every access fact for one actor. Two queries, no N+1."""
    now = datetime.now(timezone.utc)

    membership_rows = (await session.execute(
        select(OrganizationMembership, Organization)
        .join(Organization,
              Organization.id == OrganizationMembership.organization_id)
        .where(OrganizationMembership.user_id == user.id)
    )).all()

    memberships: dict[int, MembershipFacts] = {}
    for membership, organization in membership_rows:
        if not _is_in_force(membership.status, membership.starts_at,
                            membership.expires_at, now):
            continue
        # An archived or suspended organization grants nothing to anybody.
        if organization.status in {OrganizationStatus.ARCHIVED,
                                   OrganizationStatus.SUSPENDED}:
            continue
        memberships[membership.organization_id] = MembershipFacts(
            organization_id=membership.organization_id,
            role=membership.role,
            scope=membership.scope,
            may_download_attachments=membership.may_download_attachments,
            is_external=membership.external_organization is not None,
            expires_at=_as_utc(membership.expires_at),
            organization_status=organization.status,
        )

    assignment_rows = (await session.execute(
        select(StudyAssignment).where(StudyAssignment.user_id == user.id)
    )).scalars().all()

    study_roles: dict[int, set[StudyRole]] = {}
    study_organizations: dict[int, int] = {}
    no_downloads: set[int] = set()
    for assignment in assignment_rows:
        if not _is_in_force(assignment.status, assignment.starts_at,
                            assignment.expires_at, now):
            continue
        # An assignment inside an organization the actor is no longer a member
        # of grants nothing. Removing somebody from an organization must not
        # require hunting down each of their study assignments first.
        if assignment.organization_id not in memberships:
            continue
        study_roles.setdefault(assignment.study_id, set()).add(assignment.role)
        study_organizations[assignment.study_id] = assignment.organization_id
        # NULL means "defer to the membership". Only an explicit False here is
        # a restriction, and it can only ever subtract.
        if assignment.may_download_attachments is False:
            no_downloads.add(assignment.study_id)

    return AccessContext(
        user_id=user.id,
        username=user.username,
        platform_role=user.role,
        is_active=user.is_active,
        memberships=memberships,
        study_roles={k: frozenset(v) for k, v in study_roles.items()},
        study_organizations=study_organizations,
        studies_without_downloads=frozenset(no_downloads),
        active_organization_id=active_organization_id,
    )


def visible_organization_ids(ctx: AccessContext) -> frozenset[int]:
    """Organizations whose records the actor may read.

    If the client named an active organization, the answer is narrowed to it —
    so switching organization in the interface genuinely changes what the
    backend will return, rather than merely what the frontend draws.
    """
    ids = frozenset(ctx.memberships)
    if ctx.active_organization_id is not None:
        return ids & {ctx.active_organization_id}
    return ids


async def visible_study_ids(
    session: AsyncSession, ctx: AccessContext,
) -> frozenset[int] | None:
    """Studies the actor may read, or ``None`` meaning "not study-limited".

    ``None`` is returned when every one of the actor's visible organizations
    grants organization-wide scope, because in that case a study predicate
    would be redundant and the organization predicate alone is both correct
    and cheaper. Callers must treat ``None`` as "no additional restriction",
    never as "nothing visible" — the empty frozenset means that.
    """
    org_ids = visible_organization_ids(ctx)
    if not org_ids:
        return frozenset()

    limited = {
        oid for oid in org_ids
        if not ctx.memberships[oid].is_organization_wide
    }
    if not limited:
        return None

    from nanobio_studio.app.db.workspace_models import StoredRun

    # Studies reachable through an assignment, plus studies the actor owns in
    # a restricted organization. Ownership is included because somebody who
    # created a study before assignments existed must not lose their own work.
    owned = (await session.execute(
        select(StoredRun.id).where(
            StoredRun.owner_id == ctx.user_id,
            StoredRun.organization_id.in_(limited),
        )
    )).scalars().all()

    assigned = {
        sid for sid, oid in ctx.study_organizations.items() if oid in limited
    }

    # Studies in organization-wide organizations are unrestricted, but this
    # branch only runs when at least one organization is restricted, so those
    # have to be added back explicitly.
    wide = org_ids - limited
    if wide:
        wide_studies = (await session.execute(
            select(StoredRun.id).where(StoredRun.organization_id.in_(wide))
        )).scalars().all()
        return frozenset(assigned) | set(owned) | set(wide_studies)

    return frozenset(assigned) | set(owned)


@dataclass(frozen=True)
class RecordFacts:
    """The record-specific inputs to a decision.

    Every field is optional because the same policy answers questions about
    organizations, studies, experiments and attachments, and not every subject
    has every fact.
    """

    organization_id: int | None = None
    study_id: int | None = None
    owner_id: int | None = None

    #: Whoever performed or materially authored the work. Compared against the
    #: actor for the approval-independence check.
    performer_ids: frozenset[int] = frozenset()

    #: Set for experiment-version subjects.
    status: object | None = None

    #: Set for attachment subjects.
    is_attachment: bool = False


def may(ctx: AccessContext, action: Action,
        facts: RecordFacts) -> tuple[bool, str]:
    """Answer one question. Returns ``(allowed, reason)``.

    The reason is always populated, including on success, because a denial the
    user cannot understand generates a support ticket and a denial the
    *developer* cannot understand generates a workaround.
    """
    if not ctx.is_active:
        return False, "This account is deactivated."

    org_id = facts.organization_id

    # ---- organization membership -----------------------------------------
    if org_id is not None:
        membership = ctx.membership(org_id)
        if membership is None:
            return False, "No active membership in this organization."
    else:
        membership = None

    # ---- administrative verbs --------------------------------------------
    if action in ADMINISTRATIVE_ACTIONS:
        if action is Action.MANAGE_ACCOUNTS:
            if ctx.platform_role is UserRole.ADMIN:
                return True, "Platform administrator."
            if membership is not None and membership.role is OrganizationRole.OWNER:
                return True, "Organization owner."
            return False, "Account management requires an administrator."
        if membership is None:
            return False, "No active membership in this organization."
        if membership.role not in ADMINISTRATIVE_ROLES:
            return False, (
                "Managing access requires the organization owner or an "
                "organization administrator.")
        if (action is Action.MANAGE_ORGANIZATION
                and membership.role is not OrganizationRole.OWNER):
            return False, "Only the organization owner can do this."
        return True, f"Organization {membership.role.value}."

    # ---- scientific verbs -------------------------------------------------
    if action in SCIENTIFIC_ACTIONS:
        if membership is not None and membership.awaiting_confirmation:
            return False, (
                "This organization was created by an upgrade and is awaiting "
                "administrator confirmation. Scientific changes are blocked "
                "until the memberships are confirmed.")

        # The rule that gives this module its name. An administrative role
        # confers no scientific authority, ever — including platform admin.
        if membership is not None and membership.role in ADMINISTRATIVE_ROLES:
            return False, (
                "Administrators manage access, not evidence. A separate "
                "scientific role and study assignment are required.")
        if ctx.platform_role is UserRole.ADMIN and membership is None:
            return False, "Administrators cannot act on science."
        if ctx.platform_role is UserRole.VIEWER:
            return False, "This account is read-only."

        study_id = facts.study_id
        if study_id is None:
            return False, "This action requires a study."

        roles = ctx.roles_on(study_id)
        if not roles:
            return False, (
                "You are not assigned to this study. Scientific access "
                "requires an explicit study assignment.")

        permitted: set[Action] = set()
        for role in roles:
            permitted |= STUDY_ROLE_ACTIONS.get(role, frozenset())
        if action not in permitted:
            held = ", ".join(sorted(r.value for r in roles))
            return False, (
                f"Your assignment on this study ({held}) does not permit "
                f"this action.")

        # ---- independence ----------------------------------------------
        # Assignment does not override self-approval restrictions. Somebody
        # can legitimately be both a contributor and an approver on a study;
        # what they cannot be is both on the *same experiment*.
        if action is Action.APPROVE:
            if ctx.user_id in facts.performer_ids:
                return False, (
                    "You performed or authored this experiment. Approval "
                    "must be independent of the work.")
            if facts.owner_id == ctx.user_id:
                return False, (
                    "You created this experiment. Approval must be "
                    "independent of the work.")
        if action in {Action.START_REVIEW, Action.REQUEST_REVISION,
                      Action.REJECT}:
            if ctx.user_id in facts.performer_ids or facts.owner_id == ctx.user_id:
                return False, (
                    "You performed or authored this experiment and cannot "
                    "review it.")
            if not (roles & REVIEW_CAPABLE_STUDY_ROLES):
                return False, "Review requires a reviewer or approver assignment."

        return True, "Study assignment permits this action."

    # ---- medical reports --------------------------------------------------
    #
    # Placed before the general read branch on purpose. Falling through to it
    # would let any member with organization-wide scope read every patient
    # assessment in the organization — including the administrator whose whole
    # separation from evidence this module exists to maintain.
    if action in REPORT_ACTIONS:
        if membership is None:
            return False, "No active membership in this organization."
        if membership.awaiting_confirmation and action is not Action.VIEW_REPORT:
            return False, (
                "This organization was created by an upgrade and is awaiting "
                "administrator confirmation. Changes are blocked until the "
                "memberships are confirmed.")
        if ctx.platform_role is UserRole.VIEWER and action is not Action.VIEW_REPORT:
            return False, "This account is read-only."

        permitted = REPORT_ROLE_ACTIONS.get(membership.role, frozenset())

        # Retention disposal is a deployment duty, not a clinical one: it acts
        # on dates and reads no content. A platform administrator may run it —
        # but only inside an organization they actually belong to, so it stays
        # scoped like every other read. Membership was already established
        # above, which is what makes this safe to add.
        if (action is Action.PURGE_REPORTS
                and ctx.platform_role is UserRole.ADMIN):
            permitted = permitted | {Action.PURGE_REPORTS}

        if action not in permitted:
            if membership.role in ADMINISTRATIVE_ROLES:
                return False, (
                    "Organization administrators manage access, not patient "
                    "assessments. A clinical role is required to read or "
                    "change a report.")
            return False, (
                f"An organization {membership.role.value} may not do this to a "
                f"report assessment.")

        # Only the author may change or destroy their clinical judgement.
        if action in REPORT_OWNER_ONLY_ACTIONS and facts.owner_id != ctx.user_id:
            return False, (
                "Only the person who created this assessment can amend or "
                "delete it. Confirmed clinical fields record who decided them, "
                "and that has to stay answerable.")

        # Reading somebody else's assessment needs organization-wide scope.
        # An assigned-studies membership reaches studies, and an assessment
        # hangs off no study — so without ownership there is nothing to reach
        # it through.
        if action in {Action.VIEW_REPORT, Action.DOWNLOAD_REPORT_DOCUMENT}:
            if (facts.owner_id != ctx.user_id
                    and not membership.is_organization_wide):
                return False, (
                    "Your membership reaches only studies you are assigned "
                    "to, and a report assessment belongs to no study.")

        if action is Action.DOWNLOAD_REPORT_DOCUMENT:
            if not membership.may_download_attachments:
                return False, (
                    "This collaboration permits viewing results but not "
                    "downloading documents.")

        return True, f"Organization {membership.role.value}."

    # ---- access history ---------------------------------------------------
    # Deliberately not folded into the general read branch below.
    #
    # The organization audit trail is a record of who was granted what, by
    # whom, and who was removed. That is administrative information: it maps
    # the organization's authority structure and its personnel changes. A
    # researcher with organization-wide *scientific* visibility has no reason
    # to read it, and until this was separated they could — the action fell
    # through to "member with organization-wide scope may read", which is the
    # right rule for studies and the wrong one for access control.
    #
    # Auditors are included because reading the trail is the entire function
    # of the role.
    if action is Action.VIEW_ACCESS_HISTORY:
        if membership is None:
            return False, "No active membership in this organization."
        if (membership.role in ADMINISTRATIVE_ROLES
                or membership.role is OrganizationRole.AUDITOR):
            return True, f"Organization {membership.role.value}."
        return False, (
            "Access history is available to organization owners, "
            "administrators and auditors.")

    # ---- reading ----------------------------------------------------------
    if action is Action.DOWNLOAD_ATTACHMENT:
        if membership is not None and not membership.may_download_attachments:
            return False, (
                "This collaboration permits viewing results but not "
                "downloading attachments.")
        # A per-study restriction subtracts from an otherwise-permitted
        # membership. Checked here rather than folded into the membership flag
        # so the two remain separately auditable: an access review needs to see
        # whether a collaborator is restricted everywhere or on one study.
        if (facts.study_id is not None
                and facts.study_id in ctx.studies_without_downloads):
            return False, (
                "Your assignment on this study permits viewing results but "
                "not downloading attachments.")

    if org_id is not None and membership is not None:
        if membership.is_organization_wide:
            return True, f"Organization-wide {membership.role.value}."
        study_id = facts.study_id
        if study_id is not None and ctx.roles_on(study_id):
            return True, "Assigned to this study."
        if facts.owner_id == ctx.user_id:
            return True, "Own record."
        return False, "Not assigned to this study."

    return False, "No applicable grant."


class OrganizationRequired(Exception):
    """The caller belongs to several organizations and named none → 409.

    Not a 400: the request is well formed. Not a guess either — guessing which
    organization a patient assessment belongs to is how a document lands in the
    wrong tenant, and nothing later in the system would ever notice.
    """

    def __init__(self, record_type: str = "record") -> None:
        super().__init__(
            f"Select an organization before creating a {record_type}. You "
            f"belong to more than one, and which it belongs to is not "
            f"something the server may decide for you.")
        self.record_type = record_type


def writing_organization_for(ctx: AccessContext, record_type: str) -> int:
    """Which organization a new *parentless* record belongs to.

    The contract's third case (``ACTIVE_ORGANIZATION_CONTRACT.md`` §2.6): a
    record with a stored parent inherits from the parent; a record with none
    inherits the caller's single organization; a caller in several who has not
    selected one is refused rather than guessed at.

    A report assessment is the parentless case. It is uploaded before it is
    attached to anything, so there is no stored parent to inherit from — which
    is precisely why this must not fall back to "the first one".
    """
    if ctx.active_organization_id is not None:
        if ctx.active_organization_id in ctx.memberships:
            return ctx.active_organization_id
        # The header named an organization the caller is not in. Selection can
        # only narrow, so the answer is an empty scope, not a different one.
        raise RecordNotVisible(record_type)

    every = sorted(ctx.memberships)
    if not every:
        raise RecordNotVisible(record_type)
    if len(every) > 1:
        raise OrganizationRequired(record_type)
    return every[0]


def require(ctx: AccessContext, action: Action, facts: RecordFacts) -> None:
    """Raise unless permitted.

    Raises :class:`RecordNotVisible` — a 404 — when the actor is not a member
    of the record's organization at all, and :class:`PolicyDenied` — a 403 —
    only once membership is established. The caller therefore cannot use an
    error code to discover whether an identifier exists elsewhere.
    """
    if (facts.organization_id is not None
            and not ctx.is_member_of(facts.organization_id)):
        raise RecordNotVisible()
    allowed, reason = may(ctx, action, facts)
    if not allowed:
        raise PolicyDenied(action, reason)
