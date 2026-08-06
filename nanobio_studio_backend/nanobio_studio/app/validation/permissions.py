"""Capabilities for the Experimental Validation Registry.

Why capabilities rather than new roles
--------------------------------------
The platform has three roles — ``admin``, ``researcher``, ``viewer`` — and they
are stored on every existing account. Adding three more would mean migrating
authentication data to express something that is really about *this record*,
not about the person in general: the same researcher is a performer on their
own experiment and a legitimate reviewer on a colleague's.

So the six capabilities in the brief are derived per (user, record) from the
existing role plus the record's own facts. Nothing in the auth schema changes,
and the rules below are the single place the answer is computed.

Enforced in the service, not the interface
------------------------------------------
Every check here is called from the service layer before the mutation happens.
Hiding a button is a courtesy; refusing the call is the control.

The two rules that are not negotiable
-------------------------------------
1. **A performer cannot approve their own experiment.** Independence is the
   entire content of the approval gate; without it, "approved" would mean
   "the person who ran it said it was fine".

2. **An administrator cannot make a scientific decision.** Admin exists to
   manage access. Letting it approve, or rewrite an approval, would make the
   scientific record answerable to whoever holds the most privilege — which is
   the opposite of what a review process is for.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle avoidance
    from nanobio_studio.app.organizations.policy import AccessContext

from nanobio_studio.app.db.auth_models import UserRole
from nanobio_studio.app.validation.vocabulary import (
    EDITABLE_STATUSES, ExperimentStatus,
)

__all__ = [
    "Capability",
    "RegistryActor",
    "ExperimentContext",
    "PermissionDenied",
    "capabilities_for",
    "require",
]


class Capability(str, enum.Enum):
    """The six capabilities from the brief, expressed as verbs."""

    #: Researcher / laboratory contributor.
    CREATE_EXPERIMENT = "create_experiment"
    EDIT_DRAFT = "edit_draft"
    SUBMIT = "submit"
    ADD_ATTACHMENT = "add_attachment"

    #: Scientific reviewer.
    START_REVIEW = "start_review"
    REQUEST_REVISION = "request_revision"
    REJECT = "reject"

    #: Scientific approver.
    APPROVE = "approve"

    #: Administrator — access management only.
    MANAGE_ACCESS = "manage_access"

    #: Auditor / viewer.
    VIEW = "view"
    VIEW_AUDIT = "view_audit"


@dataclass(frozen=True)
class RegistryActor:
    user_id: int
    role: UserRole

    #: The organization-level access facts for this request, resolved once by
    #: ``api/deps_organization.get_access_context``.
    #:
    #: Optional because the registry's own capability rules — who may review,
    #: who may approve, what a draft permits — are decided by the record and
    #: the platform role and do not need it. What needs it is the *outer*
    #: question this milestone added: may this person reach the record at all.
    #: Services take that path only when the context is present, which is what
    #: lets the several hundred existing unit tests keep constructing a bare
    #: actor without every one of them having to build an organization first.
    #:
    #: Every route supplies it, and that is verified mechanically rather than
    #: by review: ``test_every_scoped_route_resolves_an_access_context`` walks
    #: the router and fails if any route omits the dependency. A silently
    #: unenforced route is the failure mode this field would otherwise invite,
    #: so the guard is a test that cannot be forgotten, not a convention.
    access: "AccessContext | None" = None


@dataclass(frozen=True)
class ExperimentContext:
    """The record facts a permission decision depends on."""

    owner_id: int
    status: ExperimentStatus
    performed_by: int | None = None
    #: Contributors explicitly granted edit access, e.g. a CRO contact.
    contributor_ids: frozenset[int] = frozenset()


class PermissionDenied(PermissionError):
    def __init__(self, capability: Capability, reason: str):
        super().__init__(reason)
        self.capability = capability
        self.reason = reason


def _is_contributor(actor: RegistryActor, ctx: ExperimentContext) -> bool:
    return actor.user_id == ctx.owner_id or actor.user_id in ctx.contributor_ids


def _performed_by_actor(actor: RegistryActor, ctx: ExperimentContext) -> bool:
    """Whether this actor did the work.

    Falls back to ownership when no performer is recorded. That is deliberate:
    an unrecorded performer must not become a route to self-approval, so the
    conservative reading — the owner performed it — applies.
    """
    if ctx.performed_by is not None:
        return actor.user_id == ctx.performed_by
    return actor.user_id == ctx.owner_id


def capabilities_for(actor: RegistryActor,
                     ctx: ExperimentContext) -> frozenset[Capability]:
    """Everything this actor may do to this record, right now."""
    caps: set[Capability] = {Capability.VIEW}

    # Auditors and viewers read, including the audit trail. Read access to the
    # trail is what makes an auditor an auditor.
    if actor.role in {UserRole.ADMIN, UserRole.RESEARCHER, UserRole.VIEWER}:
        caps.add(Capability.VIEW_AUDIT)

    if actor.role is UserRole.ADMIN:
        caps.add(Capability.MANAGE_ACCESS)
        # Deliberately nothing else. An administrator may manage who has
        # access; they may not author, submit, review or approve science.
        return frozenset(caps)

    if actor.role is UserRole.VIEWER:
        return frozenset(caps)

    # --- researcher ------------------------------------------------------
    caps.add(Capability.CREATE_EXPERIMENT)

    editable = ctx.status in EDITABLE_STATUSES
    if editable and _is_contributor(actor, ctx):
        caps.add(Capability.EDIT_DRAFT)
        caps.add(Capability.ADD_ATTACHMENT)
        caps.add(Capability.SUBMIT)

    # Review and approval of somebody else's work. A researcher is a competent
    # scientific reviewer; what disqualifies them is having done the work, not
    # their job title.
    if ctx.status is ExperimentStatus.SUBMITTED:
        if not _performed_by_actor(actor, ctx):
            caps.add(Capability.START_REVIEW)

    if ctx.status is ExperimentStatus.UNDER_REVIEW:
        if not _performed_by_actor(actor, ctx):
            caps.add(Capability.REQUEST_REVISION)
            caps.add(Capability.REJECT)
            caps.add(Capability.APPROVE)

    return frozenset(caps)


def require(actor: RegistryActor, ctx: ExperimentContext,
            capability: Capability) -> None:
    """Raise unless the actor holds the capability. Call before mutating."""
    if capability in capabilities_for(actor, ctx):
        return

    # The message names the reason rather than a generic denial, because the
    # commonest denial — self-approval — is a rule people need explained, not
    # merely enforced.
    if capability is Capability.APPROVE:
        if actor.role is UserRole.ADMIN:
            raise PermissionDenied(
                capability,
                "Administrators manage access and cannot approve scientific "
                "records. Approval must come from a scientific reviewer who "
                "did not perform the work.")
        if _performed_by_actor(actor, ctx):
            raise PermissionDenied(
                capability,
                "You performed this experiment, so you cannot approve it. "
                "Independent review is the whole content of the approval "
                "gate.")
        if ctx.status is not ExperimentStatus.UNDER_REVIEW:
            raise PermissionDenied(
                capability,
                f"An experiment can only be approved from "
                f"'{ExperimentStatus.UNDER_REVIEW.value}'; this version is "
                f"'{ctx.status.value}'.")

    if capability is Capability.EDIT_DRAFT and ctx.status not in EDITABLE_STATUSES:
        raise PermissionDenied(
            capability,
            f"This version is '{ctx.status.value}' and is frozen. Corrections "
            "are made by creating a new version, which preserves the record "
            "that was reviewed.")

    raise PermissionDenied(
        capability,
        f"Your role does not permit '{capability.value}' on a record in state "
        f"'{ctx.status.value}'.")
