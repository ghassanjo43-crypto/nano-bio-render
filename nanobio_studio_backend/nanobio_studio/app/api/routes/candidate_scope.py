"""Resolving a candidate or a candidate version the caller may reach.

Why this is its own module
--------------------------
These resolvers are the choke point for candidate reachability, and there are
now two routers that need them: the registry (``routes/validation.py``) and the
version-bound artefacts (``routes/candidate_artifacts.py``). Copying three
short functions into the second router would work on the day it was written and
would drift the first time somebody tightened one of them — and the failure
mode of a drifted authorization check is that one router keeps refusing a
foreign organization while the other quietly stops.

So there is one definition, imported by both. ``routes/validation.py`` keeps
its ``_scoped_candidate`` / ``_scoped_candidate_version`` names as thin
delegates, because those names appear in existing tests and in the reasoning
recorded around them.

The pattern itself
------------------
The organization predicate is part of the same WHERE clause that finds the row,
so a record belonging to another organization is never loaded. A caller walking
the identifier space learns nothing: a real record they cannot see and an
identifier that was never issued give the same answer.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.validation_models import Candidate, CandidateVersion
from nanobio_studio.app.organizations.policy import AccessContext
from nanobio_studio.app.organizations.scoping import require_scoped, scoped

__all__ = ["resolve_candidate", "resolve_candidate_version"]


async def resolve_candidate(session: AsyncSession, ctx: AccessContext,
                            candidate_id: int) -> Candidate:
    """Resolve a candidate the caller may reach, or raise the 404.

    This did not exist once, and its absence was the hole.
    ``create_candidate_version`` loaded its candidate with a bare
    ``session.get()`` — no organization predicate, no study scope, no policy
    call — so any authenticated account that could name a candidate id could
    append a scientific version to it, across organizations and with no
    membership at all. The appended version then sat in the candidate's history
    looking exactly like one the owning organization had written.
    """
    return await require_scoped(
        session,
        scoped(select(Candidate), Candidate, ctx).where(
            Candidate.id == candidate_id),
        "candidate")


async def resolve_candidate_version(session: AsyncSession, ctx: AccessContext,
                                    version_id: int) -> CandidateVersion:
    """Resolve a candidate version the caller may reach, or raise the 404.

    Resolved by identifier and then re-checked through its candidate, which is
    scoped properly. The indirection is deliberate: a version written before
    the organization column was populated carries NULL there and would be
    unreachable under a direct predicate — or, if the predicate were dropped to
    accommodate that, reachable by everyone. The candidate check is what makes
    the fallback safe.
    """
    version = await require_scoped(
        session,
        select(CandidateVersion).where(CandidateVersion.id == version_id),
        "candidate version")
    await resolve_candidate(session, ctx, version.candidate_id)
    return version
