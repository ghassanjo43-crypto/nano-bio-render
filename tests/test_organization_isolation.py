"""Organization isolation, role separation and the upgrade path.

Scope of this file
------------------
These tests exercise the **authorization layer and the migration** — the
policy, the query-layer scoping and the backfill. They do not yet cover the
HTTP routes, because the routes have not been converted to call the policy.
That gap is stated plainly in the delivery report rather than papered over
here: a passing test file is not evidence about code it never calls.

What is asserted
----------------
* a member of one organization cannot select another's records, by any
  identifier, through the scoped query layer;
* the four scientific rules the brief requires to survive production
  hardening still hold, now that a second axis of authority exists;
* the upgrade grants nobody scientific authority they did not already have.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "nanobio_studio_backend"))

from nanobio_studio.app.db.auth_models import User, UserRole  # noqa: E402
from nanobio_studio.app.db.base import Base  # noqa: E402
from nanobio_studio.app.db.organization_backfill import (  # noqa: E402
    PLATFORM_ROLE_TO_ORGANIZATION_ROLE, backfill_organizations,
)
from nanobio_studio.app.db.organization_models import (  # noqa: E402
    Notification, NotificationType, Organization,
    OrganizationAuditLog, OrganizationEvent,
    OrganizationMembership, StudyAssignment,
)
from nanobio_studio.app.db.validation_models import (  # noqa: E402
    Candidate, ValidationExperiment,
)
from nanobio_studio.app.db.workspace_models import Project, StoredRun  # noqa: E402
from nanobio_studio.app.science.statuses import ReadinessArea  # noqa: E402
from nanobio_studio.app.validation.vocabulary import (  # noqa: E402
    ExperimentSubtype,
)
from nanobio_studio.app.organizations.policy import (  # noqa: E402
    AccessContext, Action, PolicyDenied, RecordFacts, RecordNotVisible,
    may, require, resolve_context, visible_organization_ids,
)
from nanobio_studio.app.organizations.scoping import (  # noqa: E402
    require_scoped, scoped,
)
from nanobio_studio.app.organizations.vocabulary import (  # noqa: E402
    AccessScope, LEGACY_ORGANIZATION_SLUG, MembershipStatus,
    OrganizationRole, OrganizationStatus, StudyRole,
)
from nanobio_studio.app.services import organization_service as orgs  # noqa: E402

from tests.conftest import run_async  # noqa: E402


UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


async def _engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def _user(session: AsyncSession, username: str,
                role: UserRole = UserRole.RESEARCHER) -> User:
    user = User(username=username, password_hash="not-a-real-hash",
                role=role, is_active=True)
    session.add(user)
    await session.flush()
    return user


async def _organization(session: AsyncSession, slug: str,
                        status: OrganizationStatus = OrganizationStatus.ACTIVE
                        ) -> Organization:
    organization = Organization(slug=slug, name=slug.title(), status=status)
    session.add(organization)
    await session.flush()
    return organization


async def _member(session: AsyncSession, organization: Organization,
                  user: User, role: OrganizationRole,
                  scope: AccessScope = AccessScope.ASSIGNED_STUDIES,
                  **kwargs) -> OrganizationMembership:
    membership = OrganizationMembership(
        organization_id=organization.id, user_id=user.id, role=role,
        scope=scope, status=MembershipStatus.ACTIVE, **kwargs)
    session.add(membership)
    await session.flush()
    return membership


async def _study(session: AsyncSession, organization: Organization,
                 owner: User, name: str) -> StoredRun:
    project = Project(name=f"{name} project", owner_id=owner.id,
                      organization_id=organization.id)
    session.add(project)
    await session.flush()
    study = StoredRun(name=name, project_id=project.id, owner_id=owner.id,
                      organization_id=organization.id)
    session.add(study)
    await session.flush()
    return study


async def _assign(session: AsyncSession, study: StoredRun, user: User,
                  role: StudyRole, **kwargs) -> StudyAssignment:
    assignment = StudyAssignment(
        organization_id=study.organization_id, study_id=study.id,
        user_id=user.id, role=role, status=MembershipStatus.ACTIVE, **kwargs)
    session.add(assignment)
    await session.flush()
    return assignment


# ===========================================================================
# 1. Cross-organization isolation
# ===========================================================================

class TestCrossOrganizationIsolation:
    """One organization must not be able to reach another's records."""

    def test_a_member_of_one_organization_selects_none_of_the_others(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                acme_user = await _user(s, "acme_researcher")
                other_user = await _user(s, "other_researcher")
                acme = await _organization(s, "acme")
                other = await _organization(s, "other-labs")
                await _member(s, acme, acme_user, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                await _member(s, other, other_user,
                              OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)

                acme_study = await _study(s, acme, acme_user, "Acme study")
                other_study = await _study(s, other, other_user, "Other study")
                await s.commit()

                ctx = await resolve_context(s, acme_user)

                visible = (await s.execute(
                    scoped(select(StoredRun), StoredRun, ctx)
                )).scalars().all()
                names = {r.name for r in visible}

                assert names == {"Acme study"}, (
                    f"scoped query returned {names}; the other organization's "
                    f"study must not appear")
                assert other_study.id not in {r.id for r in visible}
                assert acme_study.id in {r.id for r in visible}
            await engine.dispose()
        run_async(scenario())

    def test_guessing_an_identifier_yields_not_found_not_forbidden(self):
        """The error code must not confirm that the record exists.

        A 403 on a real identifier and a 404 on an absent one is an oracle:
        walk the integers and the gaps tell you the shape of somebody else's
        database. Both answers here have to be 404.
        """
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                intruder = await _user(s, "intruder")
                victim = await _user(s, "victim")
                acme = await _organization(s, "acme")
                other = await _organization(s, "other-labs")
                await _member(s, acme, intruder, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                await _member(s, other, victim, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                real = await _study(s, other, victim, "Confidential study")
                await s.commit()

                ctx = await resolve_context(s, intruder)

                # A real record belonging to somebody else.
                with pytest.raises(RecordNotVisible):
                    await require_scoped(
                        s,
                        scoped(select(StoredRun), StoredRun, ctx)
                        .where(StoredRun.id == real.id),
                        "study")

                # An identifier that does not exist at all.
                with pytest.raises(RecordNotVisible):
                    await require_scoped(
                        s,
                        scoped(select(StoredRun), StoredRun, ctx)
                        .where(StoredRun.id == 999_999),
                        "study")
            await engine.dispose()
        run_async(scenario())

    def test_registry_records_are_scoped_the_same_way_as_studies(self):
        """Every scoped model carries the column, so one helper covers all."""
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                a_user = await _user(s, "a_user")
                b_user = await _user(s, "b_user")
                a = await _organization(s, "org-a")
                b = await _organization(s, "org-b")
                await _member(s, a, a_user, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                await _member(s, b, b_user, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                a_study = await _study(s, a, a_user, "A study")
                b_study = await _study(s, b, b_user, "B study")

                for org, study, owner, label in (
                        (a, a_study, a_user, "A candidate"),
                        (b, b_study, b_user, "B candidate")):
                    candidate = Candidate(
                        code=label.replace(" ", "-").upper(), name=label,
                        study_id=study.id, project_id=study.project_id,
                        owner_id=owner.id, organization_id=org.id)
                    s.add(candidate)
                await s.commit()

                ctx = await resolve_context(s, a_user)
                names = {c.name for c in (await s.execute(
                    scoped(select(Candidate), Candidate, ctx)
                )).scalars().all()}
                assert names == {"A candidate"}, names
            await engine.dispose()
        run_async(scenario())

    def test_an_actor_with_no_membership_sees_nothing(self):
        """The empty case must be an impossible predicate, not a missing one."""
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                nobody = await _user(s, "unaffiliated")
                somebody = await _user(s, "affiliated")
                acme = await _organization(s, "acme")
                await _member(s, acme, somebody, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                await _study(s, acme, somebody, "A study")
                await s.commit()

                ctx = await resolve_context(s, nobody)
                assert visible_organization_ids(ctx) == frozenset()
                rows = (await s.execute(
                    scoped(select(StoredRun), StoredRun, ctx)
                )).scalars().all()
                assert rows == []
            await engine.dispose()
        run_async(scenario())

    def test_switching_organization_narrows_what_the_backend_returns(self):
        """A switcher that only redraws the frontend is not isolation.

        Somebody in two organizations who selects one must stop being able to
        read the other *from the backend*, so a stale component or a replayed
        request cannot surface the previous organization's rows.
        """
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                consultant = await _user(s, "consultant")
                a = await _organization(s, "org-a")
                b = await _organization(s, "org-b")
                await _member(s, a, consultant, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                await _member(s, b, consultant, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                await _study(s, a, consultant, "A study")
                await _study(s, b, consultant, "B study")
                await s.commit()

                both = await resolve_context(s, consultant)
                assert {r.name for r in (await s.execute(
                    scoped(select(StoredRun), StoredRun, both)
                )).scalars().all()} == {"A study", "B study"}

                only_a = await resolve_context(
                    s, consultant, active_organization_id=a.id)
                assert {r.name for r in (await s.execute(
                    scoped(select(StoredRun), StoredRun, only_a)
                )).scalars().all()} == {"A study"}
            await engine.dispose()
        run_async(scenario())

    def test_naming_an_organization_you_do_not_belong_to_yields_nothing(self):
        """The switcher cannot be used to *widen* access."""
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                outsider = await _user(s, "outsider")
                insider = await _user(s, "insider")
                a = await _organization(s, "org-a")
                b = await _organization(s, "org-b")
                await _member(s, a, outsider, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                await _member(s, b, insider, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                await _study(s, b, insider, "B study")
                await s.commit()

                ctx = await resolve_context(
                    s, outsider, active_organization_id=b.id)
                assert visible_organization_ids(ctx) == frozenset()
                assert (await s.execute(
                    scoped(select(StoredRun), StoredRun, ctx)
                )).scalars().all() == []
            await engine.dispose()
        run_async(scenario())


# ===========================================================================
# 2. The scientific rules must survive the new authority axis
# ===========================================================================

class TestScientificRulesUnchanged:
    """The brief lists four rules that production hardening must not weaken."""

    def test_an_administrator_cannot_act_on_science(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                admin = await _user(s, "org_admin", UserRole.ADMIN)
                scientist = await _user(s, "scientist")
                acme = await _organization(s, "acme")
                await _member(s, acme, admin, OrganizationRole.ADMINISTRATOR,
                              AccessScope.ORGANIZATION)
                await _member(s, acme, scientist, OrganizationRole.RESEARCHER)
                study = await _study(s, acme, scientist, "Study")
                # Even if somebody manages to attach an approver assignment,
                # the administrative role still refuses.
                await _assign(s, study, admin, StudyRole.APPROVER)
                await s.commit()

                ctx = await resolve_context(s, admin)
                facts = RecordFacts(organization_id=acme.id, study_id=study.id,
                                    owner_id=scientist.id,
                                    performer_ids=frozenset({scientist.id}))

                for action in (Action.APPROVE, Action.SUBMIT,
                               Action.START_REVIEW, Action.CREATE_EXPERIMENT,
                               Action.EDIT_DRAFT):
                    allowed, reason = may(ctx, action, facts)
                    assert not allowed, (
                        f"an organization administrator was permitted "
                        f"{action.value}")
                    assert "administrator" in reason.lower()

                # ...but administration itself still works.
                allowed, _ = may(ctx, Action.MANAGE_MEMBERS,
                                 RecordFacts(organization_id=acme.id))
                assert allowed
            await engine.dispose()
        run_async(scenario())

    def test_a_performer_cannot_approve_their_own_experiment(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                worker = await _user(s, "worker")
                acme = await _organization(s, "acme")
                await _member(s, acme, worker, OrganizationRole.APPROVER)
                study = await _study(s, acme, worker, "Study")
                # Legitimately holds both roles on the study.
                await _assign(s, study, worker, StudyRole.APPROVER)
                await _assign(s, study, worker, StudyRole.CONTRIBUTOR)
                await s.commit()

                ctx = await resolve_context(s, worker)

                own = RecordFacts(organization_id=acme.id, study_id=study.id,
                                  owner_id=worker.id,
                                  performer_ids=frozenset({worker.id}))
                allowed, reason = may(ctx, Action.APPROVE, own)
                assert not allowed
                assert "independent" in reason.lower()

                # The same person may approve a colleague's experiment.
                colleague = RecordFacts(
                    organization_id=acme.id, study_id=study.id,
                    owner_id=999, performer_ids=frozenset({999}))
                allowed, _ = may(ctx, Action.APPROVE, colleague)
                assert allowed
            await engine.dispose()
        run_async(scenario())

    def test_a_study_assignment_does_not_override_self_approval(self):
        """"Assignment does not override self-approval restrictions."."""
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                author = await _user(s, "author")
                acme = await _organization(s, "acme")
                await _member(s, acme, author, OrganizationRole.APPROVER)
                study = await _study(s, acme, author, "Study")
                await _assign(s, study, author, StudyRole.APPROVER)
                await s.commit()

                ctx = await resolve_context(s, author)
                # Authored it but did not perform it — still barred.
                facts = RecordFacts(organization_id=acme.id, study_id=study.id,
                                    owner_id=author.id,
                                    performer_ids=frozenset())
                allowed, reason = may(ctx, Action.APPROVE, facts)
                assert not allowed, (
                    "the person who created the experiment approved it")
                assert "created" in reason.lower()
            await engine.dispose()
        run_async(scenario())

    def test_science_requires_an_explicit_study_assignment(self):
        """Organization membership alone grants no scientific capability."""
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                researcher = await _user(s, "unassigned_researcher")
                owner = await _user(s, "owner")
                acme = await _organization(s, "acme")
                await _member(s, acme, researcher,
                              OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION)
                await _member(s, acme, owner, OrganizationRole.RESEARCHER)
                study = await _study(s, acme, owner, "Study")
                await s.commit()

                ctx = await resolve_context(s, researcher)
                allowed, reason = may(
                    ctx, Action.CREATE_EXPERIMENT,
                    RecordFacts(organization_id=acme.id, study_id=study.id))
                assert not allowed
                assert "assign" in reason.lower()

                # Organization-wide scope still permits reading.
                allowed, _ = may(
                    ctx, Action.VIEW_EXPERIMENT,
                    RecordFacts(organization_id=acme.id, study_id=study.id))
                assert allowed
            await engine.dispose()
        run_async(scenario())

    def test_a_lab_contributor_enters_data_but_never_reviews(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                cro = await _user(s, "cro_tech")
                sponsor = await _user(s, "sponsor")
                acme = await _organization(s, "acme")
                await _member(s, acme, cro, OrganizationRole.LAB_CONTRIBUTOR,
                              external_organization="Contract Labs Ltd")
                await _member(s, acme, sponsor, OrganizationRole.RESEARCHER)
                assigned = await _study(s, acme, sponsor, "Assigned study")
                other = await _study(s, acme, sponsor, "Unassigned study")
                await _assign(s, assigned, cro, StudyRole.LAB_CONTRIBUTOR)
                await s.commit()

                ctx = await resolve_context(s, cro)
                on_assigned = RecordFacts(organization_id=acme.id,
                                          study_id=assigned.id)

                assert may(ctx, Action.ADD_MEASUREMENT, on_assigned)[0]
                assert may(ctx, Action.SUBMIT, on_assigned)[0]
                assert not may(ctx, Action.APPROVE, on_assigned)[0]
                assert not may(ctx, Action.START_REVIEW, on_assigned)[0]
                assert not may(ctx, Action.CREATE_CANDIDATE, on_assigned)[0]

                # And nothing at all on the study they were not assigned to.
                on_other = RecordFacts(organization_id=acme.id,
                                       study_id=other.id)
                assert not may(ctx, Action.ADD_MEASUREMENT, on_other)[0]
                assert not may(ctx, Action.VIEW_EXPERIMENT, on_other)[0]
            await engine.dispose()
        run_async(scenario())

    def test_a_collaborator_barred_from_downloads_can_still_read(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                cro = await _user(s, "restricted_cro")
                sponsor = await _user(s, "sponsor")
                acme = await _organization(s, "acme")
                await _member(s, acme, cro, OrganizationRole.LAB_CONTRIBUTOR,
                              external_organization="Contract Labs Ltd",
                              may_download_attachments=False)
                await _member(s, acme, sponsor, OrganizationRole.RESEARCHER)
                study = await _study(s, acme, sponsor, "Study")
                await _assign(s, study, cro, StudyRole.LAB_CONTRIBUTOR)
                await s.commit()

                ctx = await resolve_context(s, cro)
                facts = RecordFacts(organization_id=acme.id,
                                    study_id=study.id)
                assert may(ctx, Action.VIEW_EXPERIMENT, facts)[0]
                allowed, reason = may(ctx, Action.DOWNLOAD_ATTACHMENT, facts)
                assert not allowed
                assert "download" in reason.lower()
            await engine.dispose()
        run_async(scenario())


# ===========================================================================
# 3. Expiry and revocation
# ===========================================================================

class TestExpiryAndRevocation:

    def test_an_expired_collaboration_grants_nothing_without_a_sweep(self):
        """Expiry is evaluated on read, not left to a housekeeping job.

        If access only stopped when something got round to marking the row
        EXPIRED, then a failed cron job would silently extend every external
        collaboration in the deployment.
        """
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                cro = await _user(s, "expired_cro")
                sponsor = await _user(s, "sponsor")
                acme = await _organization(s, "acme")
                await _member(s, acme, cro, OrganizationRole.LAB_CONTRIBUTOR,
                              AccessScope.ORGANIZATION,
                              external_organization="Contract Labs Ltd",
                              expires_at=_now() - timedelta(days=1))
                await _member(s, acme, sponsor, OrganizationRole.RESEARCHER)
                await _study(s, acme, sponsor, "Study")
                await s.commit()

                # Status is still ACTIVE — nothing has swept it.
                membership = (await s.execute(
                    select(OrganizationMembership).where(
                        OrganizationMembership.user_id == cro.id)
                )).scalar_one()
                assert membership.status is MembershipStatus.ACTIVE

                ctx = await resolve_context(s, cro)
                assert visible_organization_ids(ctx) == frozenset()
                assert (await s.execute(
                    scoped(select(StoredRun), StoredRun, ctx)
                )).scalars().all() == []
            await engine.dispose()
        run_async(scenario())

    def test_a_membership_that_has_not_started_grants_nothing(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                future = await _user(s, "future_starter")
                acme = await _organization(s, "acme")
                await _member(s, acme, future, OrganizationRole.RESEARCHER,
                              AccessScope.ORGANIZATION,
                              starts_at=_now() + timedelta(days=7))
                await _study(s, acme, future, "Study")
                await s.commit()

                ctx = await resolve_context(s, future)
                assert visible_organization_ids(ctx) == frozenset()
            await engine.dispose()
        run_async(scenario())

    def test_revocation_blocks_access_but_preserves_attribution(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                admin = await _user(s, "admin", UserRole.ADMIN)
                leaver = await _user(s, "leaver")
                acme = await _organization(s, "acme")
                await _member(s, acme, admin, OrganizationRole.OWNER,
                              AccessScope.ORGANIZATION)
                membership = await _member(s, acme, leaver,
                                           OrganizationRole.RESEARCHER)
                study = await _study(s, acme, leaver, "Their study")
                await _assign(s, study, leaver, StudyRole.CONTRIBUTOR)
                candidate = Candidate(
                    code="CAND-1", name="Their candidate", study_id=study.id,
                    project_id=study.project_id, owner_id=leaver.id,
                    organization_id=acme.id)
                s.add(candidate)
                await s.flush()
                experiment = ValidationExperiment(
                    code="EXP-1", title="Their experiment",
                    candidate_id=candidate.id, study_id=study.id,
                    project_id=study.project_id, owner_id=leaver.id,
                    organization_id=acme.id,
                    subtype=ExperimentSubtype.CYTOTOXICITY,
                    purpose=ReadinessArea.SAFETY_ASSESSMENT)
                s.add(experiment)
                await s.commit()

                admin_ctx = await resolve_context(s, admin)
                await orgs.revoke_member(
                    s, actor=admin_ctx, membership_id=membership.id,
                    reason="Left the organization")
                await s.commit()

                # Access is gone.
                ctx = await resolve_context(s, leaver)
                assert visible_organization_ids(ctx) == frozenset()

                # The work still says who did it.
                stored = await s.get(ValidationExperiment, experiment.id)
                assert stored is not None
                assert stored.owner_id == leaver.id

                # And the assignment row survives, marked revoked.
                assignment = (await s.execute(
                    select(StudyAssignment).where(
                        StudyAssignment.user_id == leaver.id)
                )).scalar_one()
                assert assignment.status is MembershipStatus.REVOKED
                assert assignment.ended_by == admin.id

                events = {e.event for e in (await s.execute(
                    select(OrganizationAuditLog))).scalars().all()}
                assert OrganizationEvent.MEMBER_REVOKED in events
            await engine.dispose()
        run_async(scenario())

    def test_the_last_owner_cannot_be_revoked(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                owner = await _user(s, "sole_owner", UserRole.ADMIN)
                acme = await _organization(s, "acme")
                membership = await _member(s, acme, owner,
                                           OrganizationRole.OWNER,
                                           AccessScope.ORGANIZATION)
                await s.commit()

                ctx = await resolve_context(s, owner)
                with pytest.raises(orgs.OrganizationError, match="only active owner"):
                    await orgs.revoke_member(
                        s, actor=ctx, membership_id=membership.id)
            await engine.dispose()
        run_async(scenario())


# ===========================================================================
# 4. Assignment cannot be used to escalate
# ===========================================================================

class TestAssignmentCannotEscalate:

    def test_an_administrator_cannot_assign_themselves_as_approver(self):
        """The back door the eligibility table exists to close."""
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                admin = await _user(s, "admin", UserRole.ADMIN)
                scientist = await _user(s, "scientist")
                acme = await _organization(s, "acme")
                await _member(s, acme, admin, OrganizationRole.ADMINISTRATOR,
                              AccessScope.ORGANIZATION)
                await _member(s, acme, scientist, OrganizationRole.RESEARCHER)
                study = await _study(s, acme, scientist, "Study")
                await s.commit()

                ctx = await resolve_context(s, admin)
                with pytest.raises(orgs.OrganizationError) as caught:
                    await orgs.assign_to_study(
                        s, actor=ctx, study_id=study.id, user_id=admin.id,
                        role=StudyRole.APPROVER)
                assert "cannot hold the study role" in str(caught.value)
            await engine.dispose()
        run_async(scenario())

    def test_a_researcher_cannot_be_assigned_as_approver(self):
        """Approval authority is granted by role change, visibly, not sideways."""
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                admin = await _user(s, "admin", UserRole.ADMIN)
                researcher = await _user(s, "researcher")
                acme = await _organization(s, "acme")
                await _member(s, acme, admin, OrganizationRole.ADMINISTRATOR,
                              AccessScope.ORGANIZATION)
                await _member(s, acme, researcher,
                              OrganizationRole.RESEARCHER)
                study = await _study(s, acme, researcher, "Study")
                await s.commit()

                ctx = await resolve_context(s, admin)
                with pytest.raises(orgs.OrganizationError):
                    await orgs.assign_to_study(
                        s, actor=ctx, study_id=study.id,
                        user_id=researcher.id, role=StudyRole.APPROVER)
            await engine.dispose()
        run_async(scenario())

    def test_assignment_is_refused_across_the_organization_boundary(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                admin = await _user(s, "a_admin", UserRole.ADMIN)
                outsider = await _user(s, "b_scientist")
                a = await _organization(s, "org-a")
                b = await _organization(s, "org-b")
                await _member(s, a, admin, OrganizationRole.ADMINISTRATOR,
                              AccessScope.ORGANIZATION)
                await _member(s, b, outsider, OrganizationRole.RESEARCHER)
                inhouse = await _user(s, "a_scientist")
                await _member(s, a, inhouse, OrganizationRole.RESEARCHER)
                study = await _study(s, a, inhouse, "Study")
                await s.commit()

                ctx = await resolve_context(s, admin)
                with pytest.raises(orgs.OrganizationError,
                                   match="not an active member"):
                    await orgs.assign_to_study(
                        s, actor=ctx, study_id=study.id,
                        user_id=outsider.id, role=StudyRole.CONTRIBUTOR)
            await engine.dispose()
        run_async(scenario())

    def test_an_administrator_of_one_organization_cannot_touch_another(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                a_admin = await _user(s, "a_admin", UserRole.ADMIN)
                b_owner = await _user(s, "b_owner", UserRole.ADMIN)
                a = await _organization(s, "org-a")
                b = await _organization(s, "org-b")
                await _member(s, a, a_admin, OrganizationRole.ADMINISTRATOR,
                              AccessScope.ORGANIZATION)
                await _member(s, b, b_owner, OrganizationRole.OWNER,
                              AccessScope.ORGANIZATION)
                victim = await _user(s, "b_member")
                await _member(s, b, victim, OrganizationRole.RESEARCHER)
                await s.commit()

                ctx = await resolve_context(s, a_admin)
                with pytest.raises(RecordNotVisible):
                    require(ctx, Action.MANAGE_MEMBERS,
                            RecordFacts(organization_id=b.id))
            await engine.dispose()
        run_async(scenario())


# ===========================================================================
# 5. Notifications
# ===========================================================================

class TestNotifications:

    def test_a_notification_is_readable_only_by_its_recipient(self):
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                recipient = await _user(s, "recipient")
                nosy = await _user(s, "nosy")
                acme = await _organization(s, "acme")
                await _member(s, acme, recipient, OrganizationRole.RESEARCHER)
                await _member(s, acme, nosy, OrganizationRole.RESEARCHER)
                note = await orgs.notify(
                    s, recipient_id=recipient.id, organization_id=acme.id,
                    event=NotificationType.EXPERIMENT_SUBMITTED,
                    summary="An experiment was submitted for review.")
                await s.commit()

                nosy_ctx = await resolve_context(s, nosy)
                assert await orgs.list_notifications(
                    s, actor=nosy_ctx) == []
                with pytest.raises(RecordNotVisible):
                    await orgs.mark_notification_read(
                        s, actor=nosy_ctx, notification_id=note.id)

                own_ctx = await resolve_context(s, recipient)
                mine = await orgs.list_notifications(s, actor=own_ctx)
                assert [n.id for n in mine] == [note.id]
            await engine.dispose()
        run_async(scenario())

    def test_a_notification_carries_no_scientific_detail(self):
        """What makes the retention rule safe.

        Somebody who loses access keeps the historical fact that they were
        asked to review something. If the row carried the measurement, losing
        access would not take the measurement back.
        """
        async def scenario():
            engine = await _engine()
            async with AsyncSession(engine, expire_on_commit=False) as s:
                admin = await _user(s, "admin", UserRole.ADMIN)
                reviewer = await _user(s, "reviewer")
                acme = await _organization(s, "acme")
                await _member(s, acme, admin, OrganizationRole.OWNER,
                              AccessScope.ORGANIZATION)
                await _member(s, acme, reviewer, OrganizationRole.REVIEWER)
                scientist = await _user(s, "scientist")
                await _member(s, acme, scientist, OrganizationRole.RESEARCHER)
                study = await _study(s, acme, scientist, "Study")
                await s.commit()

                ctx = await resolve_context(s, admin)
                await orgs.assign_to_study(
                    s, actor=ctx, study_id=study.id, user_id=reviewer.id,
                    role=StudyRole.REVIEWER)
                await s.commit()

                notes = (await s.execute(select(Notification))).scalars().all()
                assert notes, "assigning a reviewer should notify them"
                for note in notes:
                    columns = {c.name for c in Notification.__table__.columns}
                    assert "measurement" not in columns
                    assert "conclusion" not in columns
                    assert "payload" not in columns
                    # The summary says what happened, not what was found.
                    assert "assigned" in note.summary.lower()
            await engine.dispose()
        run_async(scenario())


# ===========================================================================
# 6. The upgrade path
# ===========================================================================

class TestUpgradeFromEarlierInstallations:
    """A genuine Phase 1 / Milestone 1 database, upgraded in place."""

    async def _legacy_database(self, *, with_admin: bool = True):
        """Build a database as it stood before organizations existed."""
        engine = await _engine()
        async with AsyncSession(engine, expire_on_commit=False) as s:
            if with_admin:
                s.add(User(username="legacy_admin", password_hash="h",
                           role=UserRole.ADMIN, is_active=True))
            s.add_all([
                User(username="legacy_researcher", password_hash="h",
                     role=UserRole.RESEARCHER, is_active=True),
                User(username="legacy_viewer", password_hash="h",
                     role=UserRole.VIEWER, is_active=True),
            ])
            await s.flush()
            researcher = (await s.execute(
                select(User).where(User.username == "legacy_researcher")
            )).scalar_one()
            project = Project(name="Legacy project", owner_id=researcher.id)
            s.add(project)
            await s.flush()
            study = StoredRun(name="Legacy study", project_id=project.id,
                              owner_id=researcher.id)
            s.add(study)
            await s.flush()
            s.add(Candidate(code="LEGACY-1", name="Legacy candidate",
                            study_id=study.id, project_id=project.id,
                            owner_id=researcher.id))
            await s.commit()
        return engine

    def test_every_record_and_account_survives_the_upgrade(self):
        async def scenario():
            engine = await self._legacy_database()
            async with AsyncSession(engine) as s:
                before = {
                    "users": len((await s.execute(
                        select(User))).scalars().all()),
                    "projects": len((await s.execute(
                        select(Project))).scalars().all()),
                    "studies": len((await s.execute(
                        select(StoredRun))).scalars().all()),
                    "candidates": len((await s.execute(
                        select(Candidate))).scalars().all()),
                }

            report = await backfill_organizations(engine)
            assert not report.skipped

            async with AsyncSession(engine) as s:
                after = {
                    "users": len((await s.execute(
                        select(User))).scalars().all()),
                    "projects": len((await s.execute(
                        select(Project))).scalars().all()),
                    "studies": len((await s.execute(
                        select(StoredRun))).scalars().all()),
                    "candidates": len((await s.execute(
                        select(Candidate))).scalars().all()),
                }
                assert before == after, "the upgrade lost or duplicated rows"

                # And everything now belongs to the legacy organization.
                organization = (await s.execute(
                    select(Organization).where(
                        Organization.slug == LEGACY_ORGANIZATION_SLUG)
                )).scalar_one()
                for model in (Project, StoredRun, Candidate):
                    rows = (await s.execute(select(model))).scalars().all()
                    assert all(r.organization_id == organization.id
                               for r in rows), model.__name__
            await engine.dispose()
        run_async(scenario())

    def test_the_upgrade_creates_no_reviewer_or_approver(self):
        """The decision recorded in ``organization_backfill``.

        Nothing in an earlier database records who was *entitled* to review,
        so inferring it would mint approval authority out of convenience.
        """
        async def scenario():
            engine = await self._legacy_database()
            await backfill_organizations(engine)
            async with AsyncSession(engine) as s:
                roles = {a.role for a in (await s.execute(
                    select(StudyAssignment))).scalars().all()}
                assert StudyRole.REVIEWER not in roles
                assert StudyRole.APPROVER not in roles
                assert roles <= {StudyRole.OWNER}, roles
            await engine.dispose()
        run_async(scenario())

    def test_the_upgraded_organization_blocks_science_until_confirmed(self):
        async def scenario():
            engine = await self._legacy_database()
            await backfill_organizations(engine)
            async with AsyncSession(engine, expire_on_commit=False) as s:
                organization = (await s.execute(
                    select(Organization))).scalar_one()
                assert (organization.status
                        is OrganizationStatus.PENDING_CONFIRMATION)

                researcher = (await s.execute(
                    select(User).where(User.username == "legacy_researcher")
                )).scalar_one()
                study = (await s.execute(select(StoredRun))).scalar_one()

                ctx = await resolve_context(s, researcher)
                allowed, reason = may(
                    ctx, Action.CREATE_EXPERIMENT,
                    RecordFacts(organization_id=organization.id,
                                study_id=study.id))
                assert not allowed
                assert "confirm" in reason.lower()

                # Reading their own work still works.
                assert may(ctx, Action.VIEW_STUDY,
                           RecordFacts(organization_id=organization.id,
                                       study_id=study.id))[0]

                # An administrator confirms, and science resumes.
                admin = (await s.execute(
                    select(User).where(User.username == "legacy_admin")
                )).scalar_one()
                admin_ctx = await resolve_context(s, admin)
                await orgs.confirm_organization(
                    s, actor=admin_ctx, organization_id=organization.id)
                await s.commit()

                ctx = await resolve_context(s, researcher)
                assert may(ctx, Action.CREATE_EXPERIMENT,
                           RecordFacts(organization_id=organization.id,
                                       study_id=study.id))[0]
            await engine.dispose()
        run_async(scenario())

    def test_platform_roles_map_deterministically(self):
        async def scenario():
            engine = await self._legacy_database()
            await backfill_organizations(engine)
            async with AsyncSession(engine) as s:
                rows = (await s.execute(
                    select(OrganizationMembership, User)
                    .join(User, User.id == OrganizationMembership.user_id)
                )).all()
                by_name = {u.username: m.role for m, u in rows}

                # The lowest-id administrator becomes owner; the rest map
                # straight across.
                assert by_name["legacy_admin"] is OrganizationRole.OWNER
                assert (by_name["legacy_researcher"]
                        is PLATFORM_ROLE_TO_ORGANIZATION_ROLE[
                            UserRole.RESEARCHER])
                assert (by_name["legacy_viewer"]
                        is PLATFORM_ROLE_TO_ORGANIZATION_ROLE[
                            UserRole.VIEWER])
            await engine.dispose()
        run_async(scenario())

    def test_an_upgrade_with_no_administrator_says_so_and_grants_no_owner(self):
        async def scenario():
            engine = await self._legacy_database(with_admin=False)
            report = await backfill_organizations(engine)
            assert report.owner_username is None
            assert any("administrator" in n.lower() for n in report.notes), (
                report.notes)
            async with AsyncSession(engine) as s:
                roles = {m.role for m in (await s.execute(
                    select(OrganizationMembership))).scalars().all()}
                assert OrganizationRole.OWNER not in roles
            await engine.dispose()
        run_async(scenario())

    def test_the_upgrade_is_recorded_and_idempotent(self):
        async def scenario():
            engine = await self._legacy_database()
            first = await backfill_organizations(engine)
            second = await backfill_organizations(engine)

            assert not first.skipped
            assert second.skipped, "a second run must change nothing"

            async with AsyncSession(engine) as s:
                events = (await s.execute(
                    select(OrganizationAuditLog).where(
                        OrganizationAuditLog.event
                        == OrganizationEvent.LEGACY_DATA_MIGRATED)
                )).scalars().all()
                assert len(events) == 1, "the migration recorded itself twice"
                assert "confirm" in events[0].summary.lower()
            await engine.dispose()
        run_async(scenario())
