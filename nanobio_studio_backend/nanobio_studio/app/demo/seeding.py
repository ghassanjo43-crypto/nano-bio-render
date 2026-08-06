"""Idempotent seeding and scoped reset of demonstration data.

Two operations, deliberately kept far apart in behaviour:

``seed_demo_templates``
    Installs or refreshes the scenario templates from ``scenarios.py``. Keyed on
    ``slug``, so running it twice updates in place and **never creates a
    duplicate**. Returns a report of what it created, updated and left alone.

``reset_demo_data``
    Deletes demo-generated records **only**. It first counts exactly what it
    would remove and, unless explicitly confirmed, returns that scope without
    deleting anything. Every statement it issues is filtered on
    ``origin == RecordOrigin.DEMO``; there is no code path in this module that
    can touch a row whose origin is ``USER``.

The asymmetry is intentional: seeding is safe to repeat, deletion is not, so
deletion must be asked for twice.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.db.workspace_models import (
    DemoTemplate,
    Project,
    RecordOrigin,
    StoredRun,
)
from nanobio_studio.app.demo.scenarios import (
    DEMO_FIXTURE_VERSION,
    SCENARIOS,
    DemoScenario,
)

__all__ = [
    "SeedReport",
    "ResetScope",
    "scenario_payload",
    "seed_demo_templates",
    "reset_demo_data",
]


@dataclass
class SeedReport:
    """What a seeding run actually did."""

    fixture_version: str
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.created) + len(self.updated) + len(self.unchanged)

    def as_dict(self) -> dict:
        return {
            "fixture_version": self.fixture_version,
            "created": list(self.created),
            "updated": list(self.updated),
            "unchanged": list(self.unchanged),
            "total": self.total,
        }


@dataclass
class ResetScope:
    """Exactly what a reset removed, or would remove when not confirmed."""

    confirmed: bool
    demo_runs: int
    demo_projects: int
    demo_templates: int
    #: Proof of scope: how many genuine user records exist and were untouched.
    user_runs_preserved: int
    user_projects_preserved: int

    def as_dict(self) -> dict:
        return {
            "confirmed": self.confirmed,
            "demo_runs": self.demo_runs,
            "demo_projects": self.demo_projects,
            "demo_templates": self.demo_templates,
            "user_runs_preserved": self.user_runs_preserved,
            "user_projects_preserved": self.user_projects_preserved,
            "deleted": self.confirmed,
        }


def scenario_payload(scenario: DemoScenario) -> dict:
    """Serialise a scenario's inputs and teaching metadata.

    Everything except the identity/context columns, which are stored as their
    own columns for indexing. Contains inputs only — the dataclass has no field
    that could carry a scientific result.
    """
    data = asdict(scenario)
    for key in ("slug", "name", "purpose", "disease", "subtype", "drug",
                "technical"):
        data.pop(key, None)
    data["is_score_runnable"] = scenario.is_score_runnable
    data["is_pk_runnable"] = scenario.is_pk_runnable
    return data


async def seed_demo_templates(session: AsyncSession) -> SeedReport:
    """Install or refresh every scenario template. Safe to run repeatedly.

    Idempotency is by ``slug``. A second run with unchanged fixtures reports
    everything as ``unchanged`` and writes nothing.
    """
    report = SeedReport(fixture_version=DEMO_FIXTURE_VERSION)

    existing_rows = (await session.execute(select(DemoTemplate))).scalars().all()
    existing = {row.slug: row for row in existing_rows}

    for scenario in SCENARIOS:
        payload = json.dumps(scenario_payload(scenario), sort_keys=True)
        row = existing.get(scenario.slug)

        if row is None:
            session.add(DemoTemplate(
                slug=scenario.slug,
                fixture_version=DEMO_FIXTURE_VERSION,
                name=scenario.name,
                purpose=scenario.purpose,
                disease=scenario.disease,
                subtype=scenario.subtype,
                drug=scenario.drug,
                payload_json=payload,
                technical=scenario.technical,
            ))
            report.created.append(scenario.slug)
            continue

        changed = (
            row.fixture_version != DEMO_FIXTURE_VERSION
            or row.name != scenario.name
            or row.purpose != scenario.purpose
            or row.disease != scenario.disease
            or row.subtype != scenario.subtype
            or row.drug != scenario.drug
            or row.payload_json != payload
            or row.technical != scenario.technical
        )
        if not changed:
            report.unchanged.append(scenario.slug)
            continue

        row.fixture_version = DEMO_FIXTURE_VERSION
        row.name = scenario.name
        row.purpose = scenario.purpose
        row.disease = scenario.disease
        row.subtype = scenario.subtype
        row.drug = scenario.drug
        row.payload_json = payload
        row.technical = scenario.technical
        report.updated.append(scenario.slug)

    # Templates whose slug no longer exists in the fixture set are removed, so a
    # renamed scenario does not leave an orphan behind. Only templates are
    # affected; runs generated from them keep their slug for traceability.
    live = {s.slug for s in SCENARIOS}
    for slug, row in existing.items():
        if slug not in live:
            await session.delete(row)

    await session.flush()
    return report


async def reset_demo_data(session: AsyncSession, *,
                          confirm: bool = False,
                          include_templates: bool = False,
                          owner_id: int | None = None) -> ResetScope:
    """Remove demo-generated records, after reporting their exact scope.

    Parameters
    ----------
    confirm
        When ``False`` (the default) nothing is deleted; the counts that *would*
        be affected are returned instead. Deletion requires an explicit second
        request.
    include_templates
        Whether to also drop the seeded templates. Off by default, because
        removing runs is the common case and templates are cheap to re-seed.
    owner_id
        Restrict to one user's demo records. ``None`` covers all users.

    Every statement below filters on ``origin == RecordOrigin.DEMO``. Genuine
    user records are counted and reported, never selected for deletion.
    """
    run_scope = [StoredRun.origin == RecordOrigin.DEMO]
    project_scope = [Project.origin == RecordOrigin.DEMO]
    if owner_id is not None:
        run_scope.append(StoredRun.owner_id == owner_id)
        project_scope.append(Project.owner_id == owner_id)

    async def _count(model, conditions) -> int:
        stmt = select(func.count()).select_from(model)
        for condition in conditions:
            stmt = stmt.where(condition)
        return int((await session.execute(stmt)).scalar_one())

    demo_runs = await _count(StoredRun, run_scope)
    demo_projects = await _count(Project, project_scope)
    demo_templates = (await _count(DemoTemplate, [])
                      if include_templates else 0)

    # Counted for the report as evidence of scope. Never deleted.
    user_runs = await _count(StoredRun, [StoredRun.origin == RecordOrigin.USER])
    user_projects = await _count(Project, [Project.origin == RecordOrigin.USER])

    scope = ResetScope(
        confirmed=confirm,
        demo_runs=demo_runs,
        demo_projects=demo_projects,
        demo_templates=demo_templates,
        user_runs_preserved=user_runs,
        user_projects_preserved=user_projects,
    )

    if not confirm:
        return scope

    run_delete = delete(StoredRun).where(StoredRun.origin == RecordOrigin.DEMO)
    project_delete = delete(Project).where(Project.origin == RecordOrigin.DEMO)
    if owner_id is not None:
        run_delete = run_delete.where(StoredRun.owner_id == owner_id)
        project_delete = project_delete.where(Project.owner_id == owner_id)

    # Runs first: they reference projects.
    await session.execute(run_delete)
    await session.execute(project_delete)
    if include_templates:
        await session.execute(delete(DemoTemplate))

    await session.flush()
    return scope
