"""Persistence, isolation and read-state contract for in-app notifications."""

from __future__ import annotations

import pytest
import sys
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "nanobio_studio_backend"))

from nanobio_studio.app.db.organization_models import (
    Notification, NotificationAuditEvent, NotificationAuditLog,
    NotificationType, Organization, OrganizationMembership,
)
from nanobio_studio.app.db.auth_models import UserRole
from nanobio_studio.app.organizations.policy import RecordNotVisible, resolve_context
from nanobio_studio.app.organizations.vocabulary import (
    AccessScope, MembershipStatus, OrganizationRole, StudyRole,
)
from nanobio_studio.app.services import organization_service as notifications
from tests.conftest import run_async
from tests.test_organization_isolation import (
    _assign, _engine, _member, _organization, _study, _user,
)


async def _fixture():
    engine = await _engine()
    session = AsyncSession(engine, expire_on_commit=False)
    owner = await _user(session, "notification_owner")
    outsider = await _user(session, "notification_outsider")
    org = await _organization(session, "notification-lab")
    foreign = await _organization(session, "foreign-lab")
    await _member(session, org, owner, OrganizationRole.RESEARCHER,
                  AccessScope.ASSIGNED_STUDIES)
    await _member(session, foreign, outsider, OrganizationRole.RESEARCHER,
                  AccessScope.ORGANIZATION)
    study = await _study(session, org, owner, "Notification study")
    await _assign(session, study, owner, StudyRole.OWNER)
    await session.commit()
    return engine, session, owner, outsider, org, study


def test_retry_is_idempotent_and_audited_once():
    async def scenario():
        engine, session, owner, _outsider, org, study = await _fixture()
        try:
            kwargs = dict(
                recipient_id=owner.id, organization_id=org.id,
                study_id=study.id,
                event=NotificationType.CANDIDATE_REVISION_CREATED,
                summary="A candidate revision was created.",
                subject_type="candidate", subject_id=41,
                idempotency_key="candidate:41:revision:2")
            first = await notifications.notify(session, **kwargs)
            second = await notifications.notify(session, **kwargs)
            await session.commit()
            assert first.id == second.id
            assert len((await session.execute(select(Notification))).scalars().all()) == 1
            audit = (await session.execute(select(NotificationAuditLog))).scalars().all()
            assert [row.event for row in audit] == [NotificationAuditEvent.CREATED]
        finally:
            await session.close(); await engine.dispose()
    run_async(scenario())


def test_notification_http_contract_uses_real_authenticated_response(tmp_path):
    """The frontend's ``status: ok`` branch is backed by a real 200 JSON API."""
    from tests.conftest import make_isolated_auth_client
    from nanobio_studio.app.services.auth_service import create_user
    from nanobio_studio.app.organizations.vocabulary import OrganizationStatus

    app, client, factory = make_isolated_auth_client(tmp_path)

    async def seed():
        async with factory() as session:
            user = await create_user(
                session, username="notification_http_user",
                password="NotificationHttp-2026!", role=UserRole.RESEARCHER)
            org = Organization(slug="notification-http",
                               name="Notification HTTP",
                               status=OrganizationStatus.ACTIVE)
            session.add(org)
            await session.flush()
            session.add(OrganizationMembership(
                organization_id=org.id, user_id=user.id,
                role=OrganizationRole.RESEARCHER,
                scope=AccessScope.ORGANIZATION,
                status=MembershipStatus.ACTIVE))
            await notifications.notify(
                session, recipient_id=user.id, organization_id=org.id,
                event=NotificationType.RESULTS_STALE,
                summary="Stored results require attention.",
                idempotency_key="http-contract")
            await session.commit()

    run_async(seed())
    try:
        with client:
            login = client.post("/api/v1/auth/login", json={
                "username": "notification_http_user",
                "password": "NotificationHttp-2026!"})
            assert login.status_code == 200
            response = client.get(
                "/api/v1/organizations/notifications/mine")
            assert response.status_code == 200
            body = response.json()
            assert body["unread_count"] == 1
            assert len(body["notifications"]) == 1
            assert body["notifications"][0]["is_read"] is False
    finally:
        app.dependency_overrides.clear()


def test_unread_count_and_bulk_read_persist():
    async def scenario():
        engine, session, owner, _outsider, org, study = await _fixture()
        try:
            for number in range(3):
                await notifications.notify(
                    session, recipient_id=owner.id, organization_id=org.id,
                    study_id=study.id, event=NotificationType.RESULTS_STALE,
                    summary="Stored results require attention.",
                    idempotency_key=f"stale:{number}")
            await session.commit()
            ctx = await resolve_context(session, owner)
            assert await notifications.notification_unread_count(
                session, actor=ctx) == 3
            changed = await notifications.mark_notifications_read(
                session, actor=ctx, notification_ids=None)
            await session.commit()
            assert len(changed) == 3
            assert await notifications.notification_unread_count(
                session, actor=ctx) == 0
            await session.close()
            async with AsyncSession(engine, expire_on_commit=False) as reopened:
                reopened_ctx = await resolve_context(reopened, owner)
                assert await notifications.notification_unread_count(
                    reopened, actor=reopened_ctx) == 0
        finally:
            await engine.dispose()
    run_async(scenario())


def test_foreign_recipient_cannot_list_or_mark_a_notification():
    async def scenario():
        engine, session, owner, outsider, org, study = await _fixture()
        try:
            note = await notifications.notify(
                session, recipient_id=owner.id, organization_id=org.id,
                study_id=study.id, event=NotificationType.APPROVAL_REQUIRED,
                summary="An approval decision is required.",
                idempotency_key="approval:required:1")
            await session.commit()
            ctx = await resolve_context(session, outsider)
            assert await notifications.list_notifications(session, actor=ctx) == []
            with pytest.raises(RecordNotVisible):
                await notifications.mark_notification_read(
                    session, actor=ctx, notification_id=note.id)
        finally:
            await session.close(); await engine.dispose()
    run_async(scenario())


def test_lost_study_access_removes_the_link_but_keeps_safe_history():
    async def scenario():
        engine, session, owner, _outsider, org, study = await _fixture()
        try:
            note = await notifications.notify(
                session, recipient_id=owner.id, organization_id=org.id,
                study_id=study.id, event=NotificationType.REPORT_COMPLETED,
                summary="A version-bound report completed.",
                subject_type="organization", subject_id=org.id,
                idempotency_key="report:9:complete")
            await session.commit()
            ctx = await resolve_context(session, owner)
            assert (await notifications.notification_target(
                session, note, ctx))["target_status"] == "available"
            ctx.study_roles.clear()
            assert await notifications.notification_target(session, note, ctx) == {
                "target_status": "inaccessible", "href": None}
            assert "report" in note.summary.lower()
        finally:
            await session.close(); await engine.dispose()
    run_async(scenario())


def test_deleted_or_unknown_record_never_produces_a_link():
    async def scenario():
        engine, session, owner, _outsider, org, study = await _fixture()
        try:
            note = await notifications.notify(
                session, recipient_id=owner.id, organization_id=org.id,
                study_id=study.id, event=NotificationType.RESULTS_STALE,
                summary="Stored results require attention.",
                subject_type="candidate", subject_id=999999,
                idempotency_key="deleted:candidate")
            await session.commit()
            ctx = await resolve_context(session, owner)
            assert await notifications.notification_target(
                session, note, ctx) == {
                    "target_status": "inaccessible", "href": None}
        finally:
            await session.close(); await engine.dispose()
    run_async(scenario())
