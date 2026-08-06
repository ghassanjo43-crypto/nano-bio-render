"""Vocabulary for organizations, memberships and study assignments.

The one idea this module exists to encode
-----------------------------------------
**Administrative authority and scientific authority are different things, and
holding one must never confer the other.**

Phase 2 Milestone 1 already enforced a narrow version of this: an administrator
could not approve an experiment. Production hardening generalises it. An
organization owner can add and remove people, rename the organization and end a
collaboration — and cannot submit, review or approve a single experiment unless
somebody has explicitly assigned them to that study in a scientific role.

The reason is the same one that bars self-approval. If the person who controls
access can also grant themselves the authority to approve, then "approved" means
"the most privileged account said so", and the review process is decoration. So
the two ladders are kept separate all the way down:

    administrative   OWNER > ADMINISTRATOR                  (people and access)
    scientific       APPROVER, REVIEWER, RESEARCHER, LAB    (evidence)

A person may hold both. They must be given both, separately, by someone.

Why organization roles are stored and registry capabilities are still derived
----------------------------------------------------------------------------
``validation/permissions.py`` derives capabilities per (user, record) because
the same researcher is a performer on their own experiment and a legitimate
reviewer on a colleague's — that is a fact about the record, not the person.
That stays true. What is added here is the *outer* question the registry never
asked: may this person see this organization's records at all?

Membership is a stored fact about a person. Capability remains derived. The
policy in ``organizations/policy.py`` composes the two.
"""

from __future__ import annotations

import enum

__all__ = [
    "ORGANIZATION_MODEL_VERSION",
    "OrganizationRole",
    "StudyRole",
    "MembershipStatus",
    "OrganizationStatus",
    "InvitationStatus",
    "AccessScope",
    "ADMINISTRATIVE_ROLES",
    "SCIENTIFIC_ROLES",
    "ASSIGNABLE_STUDY_ROLES",
    "ROLE_MAY_BE_ASSIGNED_STUDY_ROLES",
    "ACTIVE_MEMBERSHIP_STATUSES",
    "SCIENTIFIC_STUDY_ROLES",
    "REVIEW_CAPABLE_STUDY_ROLES",
    "LEGACY_ORGANIZATION_SLUG",
]

#: Bumped when the meaning of a role or the composition rules change, so a
#: stored authorization decision can be read back against the rules that were
#: in force when it was made.
ORGANIZATION_MODEL_VERSION = "organization-model-1.0.0"

#: The organization created by the upgrade migration to hold pre-existing data.
#: Deliberately a reserved slug: no user-created organization may claim it, so
#: "was this record here before multi-tenancy?" stays answerable forever.
LEGACY_ORGANIZATION_SLUG = "legacy-single-tenant"


class OrganizationRole(str, enum.Enum):
    """Membership role, held by a person within one organization.

    Ordering in this enum is not precedence. There is deliberately no single
    ranking, because the two ladders do not compare: an APPROVER does not
    "outrank" an ADMINISTRATOR, they hold authority over a different thing.
    """

    #: Administrative. Full control of the organization including its lifecycle
    #: and the removal of other administrators. Cannot act on science.
    OWNER = "owner"

    #: Administrative. Manages members, assignments and collaborations. Cannot
    #: transfer or archive the organization, and cannot act on science.
    ADMINISTRATOR = "administrator"

    #: Scientific. May be assigned to studies as a contributor, and may author
    #: experiments where assigned.
    RESEARCHER = "researcher"

    #: Scientific, external or specialised. Enters laboratory data only, only
    #: within an explicit study assignment. Never reviews or approves.
    LAB_CONTRIBUTOR = "lab_contributor"

    #: Scientific. Eligible to be assigned as a reviewer on a study.
    REVIEWER = "reviewer"

    #: Scientific. Eligible to be assigned as an approver on a study.
    APPROVER = "approver"

    #: Read-only across the organization, including audit history. Holds no
    #: authority to change anything at all, which is what makes the role
    #: suitable for an auditor.
    AUDITOR = "auditor"


class StudyRole(str, enum.Enum):
    """Assignment role, held by a person on one study.

    Scientific capability comes from here and nowhere else. Organization role
    governs *eligibility* to hold these; it never substitutes for holding one.
    """

    OWNER = "study_owner"
    CONTRIBUTOR = "contributor"
    LAB_CONTRIBUTOR = "lab_contributor"
    REVIEWER = "reviewer"
    APPROVER = "approver"
    AUDITOR = "auditor"


class MembershipStatus(str, enum.Enum):
    """Lifecycle of a membership or a study assignment.

    ``REVOKED`` and ``EXPIRED`` are distinct on purpose. Both block access
    identically, but one is a decision somebody made and the other is a date
    passing, and an access review needs to tell them apart.
    """

    #: Created but not yet accepted. No access.
    INVITED = "invited"

    #: In force, subject to any expiry date.
    ACTIVE = "active"

    #: Temporarily blocked, retaining the row so it can be restored.
    SUSPENDED = "suspended"

    #: Ended by a person. Terminal.
    REVOKED = "revoked"

    #: Ended by its own expiry date passing. Terminal without anyone acting.
    EXPIRED = "expired"


class OrganizationStatus(str, enum.Enum):
    """Organization lifecycle.

    ``PENDING_CONFIRMATION`` exists for the upgrade path. The migration cannot
    know which of the existing accounts should hold scientific authority, and
    guessing would silently mint approvers. So it creates the organization in
    this state, grants nobody scientific authority, and waits.
    """

    PENDING_CONFIRMATION = "pending_confirmation"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class InvitationStatus(str, enum.Enum):
    """Lifecycle of an invitation to join an organization.

    Separate from :class:`MembershipStatus` on purpose. An invitation is not a
    weak membership — it grants nothing at all, and conflating the two is how
    an "invited" row ends up being treated as access somewhere down the line.
    The only thing an invitation can do is *become* a membership, once, by
    being accepted.

    Every terminal state is reached exactly once and is never left. That is
    what makes an invitation single-use: acceptance moves it to ``ACCEPTED``,
    and the acceptance path refuses any status but ``PENDING``, so a replayed
    link finds a row that can no longer do anything.
    """

    #: Issued, not yet accepted. Grants nothing.
    PENDING = "pending"

    #: Redeemed. Terminal — the token is spent whatever else happens to the
    #: membership it produced.
    ACCEPTED = "accepted"

    #: Withdrawn by an administrator before acceptance. Terminal.
    REVOKED = "revoked"

    #: Its own expiry date passed before anybody accepted. Terminal.
    EXPIRED = "expired"


class AccessScope(str, enum.Enum):
    """How far a membership's read access reaches inside its organization.

    An auditor reads everything by design. A contributor reads only studies
    they are assigned to. This is separate from role because an organization
    may want a researcher with organization-wide visibility, or an approver
    restricted to named studies.
    """

    #: Every study in the organization.
    ORGANIZATION = "organization"

    #: Only studies carrying an active assignment for this person.
    ASSIGNED_STUDIES = "assigned_studies"


# ---------------------------------------------------------------------------
# Role composition
# ---------------------------------------------------------------------------

#: Roles carrying authority over people and access.
ADMINISTRATIVE_ROLES = frozenset({
    OrganizationRole.OWNER,
    OrganizationRole.ADMINISTRATOR,
})

#: Roles carrying eligibility for authority over evidence. Note that OWNER and
#: ADMINISTRATOR are absent, and that this is the whole point of the module.
SCIENTIFIC_ROLES = frozenset({
    OrganizationRole.RESEARCHER,
    OrganizationRole.LAB_CONTRIBUTOR,
    OrganizationRole.REVIEWER,
    OrganizationRole.APPROVER,
})

#: Study roles that confer the ability to change evidence rather than read it.
SCIENTIFIC_STUDY_ROLES = frozenset({
    StudyRole.OWNER,
    StudyRole.CONTRIBUTOR,
    StudyRole.LAB_CONTRIBUTOR,
    StudyRole.REVIEWER,
    StudyRole.APPROVER,
})

#: Study roles permitted to act on somebody else's submission.
REVIEW_CAPABLE_STUDY_ROLES = frozenset({
    StudyRole.REVIEWER,
    StudyRole.APPROVER,
})

#: Every study role an assignment may name.
ASSIGNABLE_STUDY_ROLES = frozenset(StudyRole)

#: Which study roles each organization role may be assigned.
#:
#: An administrator appears here with an empty scientific set: they may be
#: assigned as AUDITOR (read-only) and nothing more. To give an administrator
#: scientific authority, their organization role must first be changed — a
#: visible, audited act — rather than being handed to them through a study
#: assignment where nobody would look for it.
ROLE_MAY_BE_ASSIGNED_STUDY_ROLES: dict[OrganizationRole, frozenset[StudyRole]] = {
    OrganizationRole.OWNER: frozenset({StudyRole.AUDITOR}),
    OrganizationRole.ADMINISTRATOR: frozenset({StudyRole.AUDITOR}),
    OrganizationRole.RESEARCHER: frozenset({
        StudyRole.OWNER, StudyRole.CONTRIBUTOR, StudyRole.AUDITOR,
    }),
    OrganizationRole.LAB_CONTRIBUTOR: frozenset({StudyRole.LAB_CONTRIBUTOR}),
    OrganizationRole.REVIEWER: frozenset({
        StudyRole.REVIEWER, StudyRole.CONTRIBUTOR, StudyRole.AUDITOR,
    }),
    OrganizationRole.APPROVER: frozenset({
        StudyRole.APPROVER, StudyRole.REVIEWER, StudyRole.AUDITOR,
    }),
    OrganizationRole.AUDITOR: frozenset({StudyRole.AUDITOR}),
}

#: Statuses under which a membership or assignment grants anything at all.
#: Note this is a single-element set: only ACTIVE grants. INVITED has not been
#: accepted, SUSPENDED is paused, and the two terminal states are over.
ACTIVE_MEMBERSHIP_STATUSES = frozenset({MembershipStatus.ACTIVE})


def default_scope_for(role: OrganizationRole) -> AccessScope:
    """The scope a membership gets when its creator does not specify one.

    Least privilege: everyone is restricted to assigned studies except the
    roles whose entire function requires breadth — administration and audit.
    """
    if role in ADMINISTRATIVE_ROLES or role is OrganizationRole.AUDITOR:
        return AccessScope.ORGANIZATION
    return AccessScope.ASSIGNED_STUDIES
