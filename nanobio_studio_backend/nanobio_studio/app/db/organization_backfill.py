"""Assign a pre-multi-tenancy database to a legacy organization.

The decision this module had to make
------------------------------------
An upgraded installation has users and scientific records but no organizations.
Something has to put them in one. The brief says two things that pull against
each other:

    "Assign existing users and scientific records to it deterministically."
    "Do not silently create excessive administrative or scientific privileges."

The tension is real. Before this milestone, *every authenticated user could
read every record* and any researcher could review a colleague's experiment.
If the backfill preserved what people could actually do, it would mint an
organization-wide reviewer out of every account in the database — which is
precisely the excessive grant the second sentence forbids. If it preserved
nothing, an upgraded installation would be inert.

What it does, and why
---------------------
It restates facts the database already holds, and invents no authority:

============================  =========================================
Existing fact                 What it becomes
============================  =========================================
platform ``admin``            organization ADMINISTRATOR — access only
lowest-id platform ``admin``  organization OWNER — access only
platform ``researcher``       organization RESEARCHER
platform ``viewer``           organization AUDITOR (read-only)
``workspace_runs.owner_id``   StudyRole.OWNER on that study
============================  =========================================

**No reviewer or approver assignment is created.** Not one. There is nothing in
a Phase 1 or Milestone 1 database that records who was *entitled* to review —
only who happened to do it — and inferring entitlement from a past action would
grant tomorrow's approval authority on the strength of yesterday's convenience.
So the organization is created ``PENDING_CONFIRMATION``, which blocks
scientific writes until an administrator has looked at the memberships and
said they are right.

The consequence is deliberate and should be stated plainly: **after upgrading,
nobody can approve an experiment until an administrator assigns approvers.**
That is the correct failure direction. The alternative is an upgrade that
quietly hands approval rights to whoever happened to have an account.

What is preserved exactly
-------------------------
Everything. Users, sessions, projects, studies, candidates, versions,
experiments, measurements, attachments, approvals and audit rows are read and
re-pointed, never rewritten or deleted. An experiment approved before the
upgrade stays approved, and its E3 stays E3 — the evidence framework is
untouched by a change in who can log in.

Idempotent
----------
Safe to run on every startup. It claims only rows whose ``organization_id`` is
NULL, so a second run is a no-op and a *third* organization added later is not
disturbed by it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from nanobio_studio.app.db.auth_models import User, UserRole
from nanobio_studio.app.db.migrations import (
    ORGANIZATION_SCOPED_TABLES, _existing_columns,
)
from nanobio_studio.app.db.organization_models import (
    Organization, OrganizationAuditLog, OrganizationEvent,
    OrganizationMembership, StudyAssignment,
)
from nanobio_studio.app.organizations.vocabulary import (
    AccessScope, LEGACY_ORGANIZATION_SLUG, MembershipStatus, OrganizationRole,
    OrganizationStatus, StudyRole, default_scope_for,
)

__all__ = ["BackfillReport", "backfill_organizations",
           "PLATFORM_ROLE_TO_ORGANIZATION_ROLE"]


#: The deterministic mapping. Kept as data so a test can assert it, and so the
#: policy it encodes is legible without reading the procedure below.
PLATFORM_ROLE_TO_ORGANIZATION_ROLE: dict[UserRole, OrganizationRole] = {
    UserRole.ADMIN: OrganizationRole.ADMINISTRATOR,
    UserRole.RESEARCHER: OrganizationRole.RESEARCHER,
    UserRole.VIEWER: OrganizationRole.AUDITOR,
}


@dataclass
class BackfillReport:
    """What the backfill did. Returned for logging and asserted by tests."""

    organization_id: int | None = None
    created_organization: bool = False
    members_added: int = 0
    owner_username: str | None = None
    study_assignments_added: int = 0
    rows_assigned: dict[str, int] = field(default_factory=dict)
    skipped: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def total_rows_assigned(self) -> int:
        return sum(self.rows_assigned.values())

    def summary(self) -> str:
        if self.skipped:
            return "no legacy data to migrate"
        return (f"legacy organization #{self.organization_id}: "
                f"{self.members_added} member(s), "
                f"{self.study_assignments_added} study assignment(s), "
                f"{self.total_rows_assigned} record(s) assigned")


async def _has_unassigned_rows(conn) -> bool:
    """Is there anything from before multi-tenancy still to claim?"""
    for table in ORGANIZATION_SCOPED_TABLES:
        columns = await _existing_columns(conn, table)
        if "organization_id" not in columns:
            continue
        found = await conn.execute(text(
            f"SELECT 1 FROM {table} WHERE organization_id IS NULL LIMIT 1"))
        if found.first() is not None:
            return True
    return False


async def _has_unenrolled_users(conn) -> bool:
    """Is there an account that belongs to no organization at all?

    This is what makes a **fresh** installation work. Every non-global record
    must belong to an organization, so an account with no membership cannot
    create a project or a study — it would have nothing to file them under.
    Without this branch a new deployment would authenticate its first user and
    then refuse every action they tried, with a message about organizations
    they had no way to create.
    """
    if not await _existing_columns(conn, "auth_users"):
        return False
    found = await conn.execute(text(
        "SELECT 1 FROM auth_users u WHERE NOT EXISTS ("
        "  SELECT 1 FROM organization_memberships m WHERE m.user_id = u.id"
        ") LIMIT 1"))
    return found.first() is not None


async def _ensure_legacy_organization(
    session: AsyncSession, *, had_prior_records: bool,
) -> tuple[Organization, bool]:
    existing = (await session.execute(
        select(Organization).where(
            Organization.slug == LEGACY_ORGANIZATION_SLUG)
    )).scalar_one_or_none()
    if existing is not None:
        return existing, False

    organization = Organization(
        slug=LEGACY_ORGANIZATION_SLUG,
        name="Legacy workspace" if had_prior_records else "Default workspace",
        description=(
            "Created automatically when this installation was upgraded to "
            "multi-organization access control. It holds every project, "
            "study, candidate, experiment and record that existed before the "
            "upgrade. An administrator should review the memberships below "
            "and confirm or adjust them; scientific changes are blocked "
            "until they do."
            if had_prior_records else
            "Created automatically so the first accounts on this installation "
            "have somewhere to work. Rename it, or create further "
            "organizations and move people across."),
        # PENDING_CONFIRMATION only when there was prior scientific work.
        #
        # The hold exists so nobody resumes approving evidence under
        # memberships a machine guessed. On a fresh installation there is no
        # prior work to re-authorize and nothing for an administrator to
        # review, so holding it would be ceremony that blocks the first user
        # for no benefit. An upgrade carrying real records is the case that
        # needs a human to look.
        status=(OrganizationStatus.PENDING_CONFIRMATION if had_prior_records
                else OrganizationStatus.ACTIVE),
        is_legacy=True,
        created_by=None,
    )
    session.add(organization)
    await session.flush()
    return organization, True


async def _add_memberships(
    session: AsyncSession, organization: Organization, report: BackfillReport,
) -> None:
    """One membership per existing account, mapped from the platform role."""
    already = set((await session.execute(
        select(OrganizationMembership.user_id).where(
            OrganizationMembership.organization_id == organization.id)
    )).scalars().all())

    users = (await session.execute(
        select(User).order_by(User.id)
    )).scalars().all()

    # Deterministic: the lowest-numbered platform administrator becomes the
    # organization owner. Lowest id rather than "first found" so the outcome
    # does not depend on row order, and an administrator rather than an
    # arbitrary account so the upgrade confers nothing on anyone who did not
    # already hold administrative rights over the deployment.
    owner_candidates = [u for u in users if u.role is UserRole.ADMIN]
    owner_id = owner_candidates[0].id if owner_candidates else None
    if owner_id is None:
        report.notes.append(
            "No platform administrator exists, so no organization owner was "
            "assigned. Create an administrator account and confirm the "
            "organization before scientific work can resume.")

    for user in users:
        if user.id in already:
            continue
        if user.id == owner_id:
            role = OrganizationRole.OWNER
            report.owner_username = user.username
        else:
            role = PLATFORM_ROLE_TO_ORGANIZATION_ROLE.get(
                user.role, OrganizationRole.AUDITOR)

        session.add(OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=role,
            scope=default_scope_for(role),
            status=MembershipStatus.ACTIVE,
            invited_by=None,
        ))
        report.members_added += 1

    await session.flush()


async def _assign_study_owners(
    session: AsyncSession, organization: Organization, report: BackfillReport,
) -> None:
    """Restate ``workspace_runs.owner_id`` as a StudyRole.OWNER assignment.

    This is the only study assignment the backfill creates, and it invents
    nothing: the database already says this person owns this study. It is
    written as an assignment so that the policy — which reads assignments and
    not ``owner_id`` — keeps letting them at their own work.
    """
    from nanobio_studio.app.db.workspace_models import StoredRun

    runs = (await session.execute(
        select(StoredRun.id, StoredRun.owner_id).where(
            StoredRun.organization_id == organization.id,
            StoredRun.owner_id.is_not(None),
        )
    )).all()
    if not runs:
        return

    existing = set((await session.execute(
        select(StudyAssignment.study_id, StudyAssignment.user_id).where(
            StudyAssignment.organization_id == organization.id,
            StudyAssignment.role == StudyRole.OWNER,
        )
    )).all())

    members = set((await session.execute(
        select(OrganizationMembership.user_id).where(
            OrganizationMembership.organization_id == organization.id)
    )).scalars().all())

    for study_id, owner_id in runs:
        if (study_id, owner_id) in existing:
            continue
        # A study owned by an account that no longer exists keeps its
        # historical attribution in owner_id and simply gets no assignment.
        if owner_id not in members:
            continue
        session.add(StudyAssignment(
            organization_id=organization.id,
            study_id=study_id,
            user_id=owner_id,
            role=StudyRole.OWNER,
            status=MembershipStatus.ACTIVE,
            assigned_by=None,
        ))
        report.study_assignments_added += 1

    await session.flush()


async def backfill_organizations(engine: AsyncEngine) -> BackfillReport:
    """Claim every unassigned row for the legacy organization. Idempotent."""
    report = BackfillReport()

    async with engine.begin() as conn:
        if not await _existing_columns(conn, "organizations"):
            report.skipped = True
            report.notes.append("organizations table absent")
            return report
        had_prior_records = await _has_unassigned_rows(conn)
        needs_enrolment = await _has_unenrolled_users(conn)
        if not (had_prior_records or needs_enrolment):
            report.skipped = True
            return report

    async with AsyncSession(engine, expire_on_commit=False) as session:
        organization, created = await _ensure_legacy_organization(
            session, had_prior_records=had_prior_records)
        report.organization_id = organization.id
        report.created_organization = created

        # Parent-first, so a child is only ever given an organization its
        # parent already has. ORGANIZATION_SCOPED_TABLES is ordered for this.
        for table in ORGANIZATION_SCOPED_TABLES:
            columns = await _existing_columns(
                await session.connection(), table)
            if "organization_id" not in columns:
                continue
            result = await session.execute(text(
                f"UPDATE {table} SET organization_id = :oid "
                f"WHERE organization_id IS NULL"),
                {"oid": organization.id})
            if result.rowcount and result.rowcount > 0:
                report.rows_assigned[table] = result.rowcount

        await _add_memberships(session, organization, report)
        await _assign_study_owners(session, organization, report)

        session.add(OrganizationAuditLog(
            organization_id=organization.id,
            event=OrganizationEvent.LEGACY_DATA_MIGRATED,
            subject_type="organization",
            subject_id=organization.id,
            actor_id=None,
            actor_username=None,
            summary=(
                ("Existing installation upgraded to multi-organization access "
                 "control. " + report.summary() + ". No reviewer or approver "
                 "assignments were created; an administrator must confirm the "
                 "organization before scientific changes are permitted.")
                if had_prior_records else
                ("Default organization created for a new installation. "
                 + report.summary() + ". No reviewer or approver assignments "
                 "were created; assign them explicitly before review.")),
            detail_json=json.dumps({
                "rows_assigned": report.rows_assigned,
                "members_added": report.members_added,
                "owner": report.owner_username,
                "study_assignments_added": report.study_assignments_added,
                "notes": report.notes,
                "had_prior_records": had_prior_records,
                "migrated_at": datetime.now(timezone.utc).isoformat(),
            }, sort_keys=True),
        ))

        await session.commit()

    return report
