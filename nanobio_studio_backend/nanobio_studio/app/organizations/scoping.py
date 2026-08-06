"""Apply the organization boundary inside the SQL, not after it.

The distinction this module exists to enforce
---------------------------------------------
There are two ways to keep one organization's records away from another:

    # Wrong. The row was read; only the response was filtered.
    experiment = await session.get(ValidationExperiment, experiment_id)
    if experiment.organization_id not in ctx.memberships:
        raise HTTPException(403)

    # Right. The row is never selected.
    experiment = await one_or_none(
        session, scoped(select(ValidationExperiment), ValidationExperiment, ctx)
                 .where(ValidationExperiment.id == experiment_id))

The first leaks in three ways that are easy to miss. It tells the caller the
identifier exists (403 ≠ 404). It is measurably slower for a real record than
an absent one, so the identifier space is walkable by timing even if the codes
match. And it is one forgotten branch away from returning the row — which is
exactly the failure the ``get()``-then-check shape invites, because the object
is already sitting in a local variable.

The second cannot leak, because there is nothing in the variable to leak.

Use
---
Every read of an organization-scoped model goes through :func:`scoped`.
:func:`require_scoped` fetches one row and raises ``RecordNotVisible`` — a
404 — when the predicate excludes it, which is the only outcome a caller
outside the organization is allowed to observe.
"""

from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.organizations.policy import (
    AccessContext, RecordNotVisible, visible_organization_ids,
    visible_study_ids,
)

__all__ = ["scoped", "require_scoped", "scoped_study_ids", "scoped_runs",
           "visible_project_ids", "assert_same_organization"]

T = TypeVar("T")


def scoped(query: Select, model: Any, ctx: AccessContext,
           study_column: Any | None = None,
           study_ids: frozenset[int] | None = None) -> Select:
    """Add the organization predicate — and, where needed, the study one.

    ``study_ids`` comes from :func:`visible_study_ids`. Pass ``None`` when the
    actor has organization-wide scope everywhere, in which case the
    organization predicate alone is both correct and cheaper.

    An actor with no memberships gets ``organization_id IN ()``, which matches
    nothing. That is the correct answer, and it is expressed as an impossible
    predicate rather than an early return so there is no code path where the
    filter is simply absent.
    """
    org_ids = visible_organization_ids(ctx)
    query = query.where(model.organization_id.in_(org_ids))

    if study_ids is not None and study_column is not None:
        query = query.where(study_column.in_(study_ids))

    return query


async def scoped_study_ids(
    session: AsyncSession, ctx: AccessContext,
) -> frozenset[int] | None:
    """Convenience re-export so callers need only import this module."""
    return await visible_study_ids(session, ctx)


async def scoped_runs(session: AsyncSession, ctx: AccessContext,
                      query: Select | None = None) -> Select:
    """Studies (``workspace_runs``) the actor may read.

    A study is the hinge of the whole model — candidates, experiments,
    readiness records and reports all hang off it — so this is the predicate
    that must not be got wrong. It replaces the previous ``owner_id ==``
    filter, which was wrong in both directions: it hid a study from a reviewer
    legitimately assigned to it, and it kept showing a study to a former owner
    who had since been removed from the organization.
    """
    from nanobio_studio.app.db.workspace_models import StoredRun

    if query is None:
        query = select(StoredRun)
    return scoped(query, StoredRun, ctx,
                  study_column=StoredRun.id,
                  study_ids=await visible_study_ids(session, ctx))


async def visible_project_ids(
    session: AsyncSession, ctx: AccessContext,
) -> frozenset[int] | None:
    """Projects the actor may read, or ``None`` for "not project-limited".

    A project is not a study, so it has no assignment of its own. Within an
    organization-wide membership the organization predicate is the whole
    answer. Within a restricted membership the actor sees projects they own
    plus projects containing a study they are assigned to — otherwise a
    contributor assigned to one study would lose the project that contains it,
    and with it the navigation path to their own work.
    """
    from nanobio_studio.app.db.workspace_models import Project, StoredRun

    org_ids = visible_organization_ids(ctx)
    if not org_ids:
        return frozenset()

    limited = {oid for oid in org_ids
               if not ctx.memberships[oid].is_organization_wide}
    if not limited:
        return None

    owned = (await session.execute(
        select(Project.id).where(
            Project.owner_id == ctx.user_id,
            Project.organization_id.in_(limited))
    )).scalars().all()

    study_ids = await visible_study_ids(session, ctx)
    through_studies: list[int] = []
    if study_ids:
        rows = (await session.execute(
            select(StoredRun.project_id).where(
                StoredRun.id.in_(study_ids),
                StoredRun.project_id.is_not(None))
        )).scalars().all()
        through_studies = [p for p in rows if p is not None]

    wide = org_ids - limited
    wide_projects: list[int] = []
    if wide:
        wide_projects = list((await session.execute(
            select(Project.id).where(Project.organization_id.in_(wide))
        )).scalars().all())

    return frozenset(owned) | set(through_studies) | set(wide_projects)


async def assert_same_organization(
    session: AsyncSession, ctx: AccessContext, *,
    parent_organization_id: int | None, child_description: str,
) -> None:
    """Refuse a parent/child pairing that crosses the boundary.

    Guards against parent injection: a caller supplying a legitimate study id
    of their own together with a project id belonging to somebody else, hoping
    the write lands with the foreign parent attached. The organization is
    always taken from the *stored parent*, never from the request — a
    client-supplied ``organization_id`` is not trusted anywhere in this
    codebase, and there is deliberately no code path that reads one.
    """
    if parent_organization_id is None:
        raise RecordNotVisible(child_description)
    if parent_organization_id not in visible_organization_ids(ctx):
        raise RecordNotVisible(child_description)


async def require_scoped(
    session: AsyncSession, query: Select, record_type: str = "record",
) -> Any:
    """Fetch exactly one scoped row, or raise the 404.

    Never raises a 403. If the predicate excluded the row, the caller is not
    entitled to know whether it exists, so "not found" is the whole truth
    they get.
    """
    row = (await session.execute(query.limit(1))).scalars().first()
    if row is None:
        raise RecordNotVisible(record_type)
    return row
