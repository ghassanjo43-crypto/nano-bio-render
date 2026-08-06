"""Remove what a walkthrough run leaves behind, and nothing else.

What this removes, and what it deliberately does not
---------------------------------------------------
A live walkthrough creates real accounts, real uploads and real objects,
because that is the only way it proves anything. Afterwards the development
database should not be carrying a test collaborator with a known password, nor
a bucket carrying files nobody will ever open.

So this removes:

* named walkthrough accounts and their memberships;
* attachment rows created by a walkthrough, and their objects;
* invitations issued to walkthrough addresses;
* report assessments uploaded by a walkthrough.

It does **not** remove organizations, projects, studies, candidates or
experiments. Those are legitimate development seed data — somebody's local
workspace — and a cleanup script that deletes a colleague's study to tidy up
after a test is worse than the mess it was clearing.

It does not touch audit rows either. An audit trail whose entries disappear
when the thing they describe is deleted is not an audit trail; the whole point
of the append-only design is that the record outlives the record.

Every account is named explicitly. There is no pattern match on "wt_" or
"test", because the day somebody's real username starts with those letters is
the day this script deletes them.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, or_, select  # noqa: E402

#: Named, not matched. A pattern would eventually catch a real account.
WALKTHROUGH_ACCOUNTS = (
    "wt_attach_cro",
    "cleanstart_probe",
    "wt_acct_owner",
)

#: Prefixes removable only when `--prefix` is passed explicitly.
#:
#: The account walkthrough must create a *new* account on every run, because
#: activation happens once and a fixed name would pass on a clean database and
#: fail on the second run. So it generates `wt_activate_<random>`, which a
#: named list cannot enumerate.
#:
#: Matching stays opt-in rather than becoming the default, because the reason
#: for naming accounts has not changed: a pattern applied automatically will
#: eventually match something somebody cares about, and this script deletes.
#: An operator asking for a prefix is making that judgement deliberately, and
#: the dry run shows them exactly which accounts it resolved to first.
REMOVABLE_PREFIXES = (
    "wt_activate_",
)

#: Addresses a walkthrough invites. Removed so no live invitation remains.
WALKTHROUGH_EMAILS = ()


async def run(*, confirm: bool, accounts: tuple[str, ...],
              prefixes: tuple[str, ...] = ()) -> int:
    from nanobio_studio.app.db.auth_models import User
    from nanobio_studio.app.db.auth_session import AuthSessionLocal, init_auth_db
    from nanobio_studio.app.db.organization_models import (
        OrganizationInvitation, OrganizationMembership,
    )
    from nanobio_studio.app.db.report_models import ReportAssessment
    from nanobio_studio.app.db.validation_models import (
        AttachmentState, ExperimentAttachment,
    )
    from nanobio_studio.app.storage import object_store
    from nanobio_studio.app.storage.objects import ObjectNotFound, StorageError

    await init_auth_db()
    store = object_store()
    planned: dict[str, list] = {
        "accounts": [], "memberships": 0, "invitations": 0,
        "report_assessments": [], "attachments": [], "objects": [],
    }

    async with AuthSessionLocal() as session:
        conditions = [User.username.in_(accounts)]
        for prefix in prefixes:
            conditions.append(User.username.startswith(prefix))
        users = list((await session.execute(
            select(User).where(or_(*conditions))
        )).scalars().all())
        planned["accounts"] = [u.username for u in users]
        user_ids = [u.id for u in users]

        if user_ids:
            planned["memberships"] = len(list((await session.execute(
                select(OrganizationMembership.id).where(
                    OrganizationMembership.user_id.in_(user_ids))
            )).scalars().all()))

            planned["report_assessments"] = list((await session.execute(
                select(ReportAssessment.id).where(
                    ReportAssessment.owner_id.in_(user_ids))
            )).scalars().all())

        # Attachments a walkthrough uploaded: either owned by one of these
        # accounts, or already deleted (the walkthrough removed them) and
        # therefore holding nothing but a tombstone whose object may linger.
        attachments = list((await session.execute(
            select(ExperimentAttachment).where(
                (ExperimentAttachment.uploaded_by.in_(user_ids or [-1]))
                | (ExperimentAttachment.state == AttachmentState.DELETED)
            )
        )).scalars().all())
        planned["attachments"] = [a.id for a in attachments]
        for attachment in attachments:
            if attachment.storage_key and store.exists(attachment.storage_key):
                planned["objects"].append(attachment.storage_key)

        if WALKTHROUGH_EMAILS:
            planned["invitations"] = len(list((await session.execute(
                select(OrganizationInvitation.id).where(
                    OrganizationInvitation.email.in_(WALKTHROUGH_EMAILS))
            )).scalars().all()))

        if not confirm:
            print("Dry run. Nothing was removed.")
            _report(planned)
            return 0

        # Objects first: a row removed before its object is an orphan nobody
        # can trace, which is the exact failure the lifecycle exists to avoid.
        removed_objects = 0
        for key in planned["objects"]:
            try:
                if store.delete(key):
                    removed_objects += 1
            except StorageError as exc:
                print(f"  ! could not remove object ({exc.code})")

        if planned["attachments"]:
            await session.execute(delete(ExperimentAttachment).where(
                ExperimentAttachment.id.in_(planned["attachments"])))

        if planned["report_assessments"]:
            await session.execute(delete(ReportAssessment).where(
                ReportAssessment.id.in_(planned["report_assessments"])))

        if user_ids:
            await session.execute(delete(OrganizationMembership).where(
                OrganizationMembership.user_id.in_(user_ids)))
        if WALKTHROUGH_EMAILS:
            await session.execute(delete(OrganizationInvitation).where(
                OrganizationInvitation.email.in_(WALKTHROUGH_EMAILS)))
        for user in users:
            await session.delete(user)

        await session.commit()
        planned["objects"] = planned["objects"][:removed_objects]
        print("Removed:")
        _report(planned)

    return 0


def _report(planned: dict) -> None:
    print(f"  accounts           : {planned['accounts'] or 'none'}")
    print(f"  memberships        : {planned['memberships']}")
    print(f"  invitations        : {planned['invitations']}")
    print(f"  report assessments : {len(planned['report_assessments'])}")
    print(f"  attachment rows    : {len(planned['attachments'])}")
    print(f"  stored objects     : {len(planned['objects'])}")
    print("  (organizations, projects, studies, candidates, experiments and "
          "audit rows are deliberately untouched)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--confirm", action="store_true",
                        help="Actually remove. Without it, reports only.")
    parser.add_argument(
        "--prefix", action="append", default=[],
        choices=list(REMOVABLE_PREFIXES),
        help=("Also remove accounts whose username starts with this prefix. "
              "Restricted to the prefixes a walkthrough is known to generate; "
              "an arbitrary prefix is refused, because this script deletes."))
    parser.add_argument("--account", action="append", default=[],
                        help="Additional named account to remove.")
    args = parser.parse_args()
    accounts = tuple(WALKTHROUGH_ACCOUNTS) + tuple(args.account)
    return asyncio.run(run(confirm=args.confirm, accounts=accounts,
                           prefixes=tuple(args.prefix)))


if __name__ == "__main__":
    raise SystemExit(main())
