"""Seed a disposable candidate-version browser fixture.

Requires an isolated ``AUTH_DATABASE_URL`` and reads the account password from
``NANOBIO_ADMIN_PASSWORD``.  It prints only record identifiers as JSON; the
credential is never accepted on argv and is never logged.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from nanobio_studio.app.db.auth_models import UserRole
from nanobio_studio.app.db.auth_session import AuthSessionLocal, init_auth_db
from nanobio_studio.app.db.organization_models import (
    NotificationType, Organization, OrganizationMembership, StudyAssignment,
)
from nanobio_studio.app.db.validation_models import Candidate, CandidateVersion
from nanobio_studio.app.db.workspace_models import StoredRun
from nanobio_studio.app.organizations.vocabulary import (
    AccessScope, MembershipStatus, OrganizationRole, OrganizationStatus,
    StudyRole,
)
from nanobio_studio.app.services.auth_service import create_user
from nanobio_studio.app.services.organization_service import notify


def canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


async def seed_notifications(session, *, candidate: Candidate) -> list[int]:
    definitions = (
        (NotificationType.CANDIDATE_REVISION_CREATED,
         "A candidate revision was created.", "browser:revision"),
        (NotificationType.RECALCULATION_REQUIRED,
         "A candidate version requires recalculation.", "browser:recalc"),
    )
    ids = []
    for event, summary, key in definitions:
        item = await notify(
            session, recipient_id=candidate.owner_id,
            organization_id=candidate.organization_id,
            study_id=candidate.study_id, event=event, summary=summary,
            subject_type="candidate", subject_id=candidate.id,
            idempotency_key=key)
        ids.append(item.id)
        if key == "browser:revision":
            retried = await notify(
                session, recipient_id=candidate.owner_id,
                organization_id=candidate.organization_id,
                study_id=candidate.study_id, event=event, summary=summary,
                subject_type="candidate", subject_id=candidate.id,
                idempotency_key=key)
            assert retried.id == item.id
    inaccessible = await notify(
        session, recipient_id=candidate.owner_id,
        organization_id=candidate.organization_id,
        study_id=candidate.study_id, event=NotificationType.RESULTS_STALE,
        summary="Stored results require attention.",
        subject_type="candidate", subject_id=999999,
        idempotency_key="browser:inaccessible")
    ids.append(inaccessible.id)
    return ids


async def main() -> None:
    password = os.environ.get("NANOBIO_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("NANOBIO_ADMIN_PASSWORD is required")
    url = os.environ.get("AUTH_DATABASE_URL", "")
    if "candidate-browser" not in url:
        raise SystemExit("Refusing to seed a database not named candidate-browser")

    await init_auth_db()
    async with AuthSessionLocal() as session:
        existing = await session.scalar(select(Candidate).where(
            Candidate.code == "BROWSER-CANDIDATE"))
        if existing is not None:
            versions = (await session.execute(select(CandidateVersion).where(
                CandidateVersion.candidate_id == existing.id).order_by(
                    CandidateVersion.version_number))).scalars().all()
            notification_ids = await seed_notifications(
                session, candidate=existing)
            await session.commit()
            print(json.dumps({"candidate_id": existing.id,
                              "version_ids": [v.id for v in versions],
                              "notification_ids": notification_ids}))
            return

        author = await create_user(session, username="candidate_browser_author",
                                   password=password, role=UserRole.RESEARCHER,
                                   email="candidate-browser@test.invalid")
        foreign_user = await create_user(
            session, username="notification_foreign", password=password,
            role=UserRole.RESEARCHER, email="notification-foreign@test.invalid")
        unassigned_user = await create_user(
            session, username="notification_unassigned", password=password,
            role=UserRole.RESEARCHER, email="notification-unassigned@test.invalid")
        revoked_user = await create_user(
            session, username="notification_revoked", password=password,
            role=UserRole.RESEARCHER, email="notification-revoked@test.invalid")
        org = Organization(slug="candidate-browser-lab",
                           name="Candidate Browser Test Lab",
                           status=OrganizationStatus.ACTIVE)
        session.add(org)
        await session.flush()
        session.add(OrganizationMembership(
            organization_id=org.id, user_id=author.id,
            role=OrganizationRole.RESEARCHER,
            scope=AccessScope.ORGANIZATION, status=MembershipStatus.ACTIVE))
        session.add(OrganizationMembership(
            organization_id=org.id, user_id=unassigned_user.id,
            role=OrganizationRole.RESEARCHER,
            scope=AccessScope.ASSIGNED_STUDIES,
            status=MembershipStatus.ACTIVE))
        session.add(OrganizationMembership(
            organization_id=org.id, user_id=revoked_user.id,
            role=OrganizationRole.RESEARCHER,
            scope=AccessScope.ASSIGNED_STUDIES,
            status=MembershipStatus.REVOKED))
        foreign_org = Organization(slug="notification-foreign-lab",
                                   name="Notification Foreign Lab",
                                   status=OrganizationStatus.ACTIVE)
        session.add(foreign_org)
        await session.flush()
        session.add(OrganizationMembership(
            organization_id=foreign_org.id, user_id=foreign_user.id,
            role=OrganizationRole.RESEARCHER, scope=AccessScope.ORGANIZATION,
            status=MembershipStatus.ACTIVE))
        run = StoredRun(organization_id=org.id, owner_id=author.id,
                        name="Candidate browser persistence study")
        session.add(run)
        await session.flush()
        session.add(StudyAssignment(
            organization_id=org.id, study_id=run.id, user_id=author.id,
            role=StudyRole.OWNER, status=MembershipStatus.ACTIVE))
        session.add(StudyAssignment(
            organization_id=org.id, study_id=run.id, user_id=revoked_user.id,
            role=StudyRole.REVIEWER, status=MembershipStatus.REVOKED))
        candidate = Candidate(
            organization_id=org.id, study_id=run.id, owner_id=author.id,
            code="BROWSER-CANDIDATE", name="Persistent candidate fixture")
        session.add(candidate)
        await session.flush()

        snapshots = [
            {"size_nm": 92.0, "charge_mv": -11.0, "coating": "PEG"},
            {"size_nm": 97.0, "charge_mv": -9.0, "coating": "PEG"},
        ]
        predecessor = None
        versions = []
        for number, inputs in enumerate(snapshots, 1):
            payload = canonical(inputs)
            version = CandidateVersion(
                organization_id=org.id, candidate_id=candidate.id,
                version_number=number, design_snapshot_json=payload,
                snapshot_checksum=hashlib.sha256(payload.encode()).hexdigest(),
                note="Initial browser fixture" if number == 1 else None,
                created_by=author.id,
                predecessor_version_id=predecessor,
                revision_reason=(None if number == 1
                                 else "Adjust size for browser verification"),
                revision_label=f"v{number}",
            )
            session.add(version)
            await session.flush()
            predecessor = version.id
            versions.append(version.id)
        notification_ids = await seed_notifications(
            session, candidate=candidate)
        await session.commit()
        print(json.dumps({"candidate_id": candidate.id,
                          "organization_id": org.id,
                          "study_id": run.id, "version_ids": versions,
                          "notification_ids": notification_ids}))


if __name__ == "__main__":
    asyncio.run(main())
