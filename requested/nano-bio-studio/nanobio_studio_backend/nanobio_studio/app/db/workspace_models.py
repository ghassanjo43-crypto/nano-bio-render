"""SQLAlchemy models for stored runs, projects and demo templates.

Why these exist
---------------
Simulation History, Projects, Compare Designs and Reports were placeholder pages
because nothing was stored server-side. Browser `localStorage` drafts are not an
acceptable substitute for a project or a report record: they are per-browser,
silently lost, and cannot be shared or audited.

These are the **intended production models**, running against SQLite locally and
PostgreSQL in deployment through the same declarative layer; only the URL
changes. They live alongside the auth models on the same `Base`, so `init_db()`
creates them together.

The scientific contract
-----------------------
A `StoredRun` records **what was calculated, by which engine version, from which
inputs** — it is a receipt, not a cache to compute from. Two consequences:

* `result_json` is only ever written from a genuine engine response. There is no
  code path that writes a fabricated or defaulted result.
* `engines_run` / `engines_not_run` are recorded per run, so a historical record
  cannot later be misread as having included an engine that never executed.

Demo isolation
--------------
`origin` distinguishes demo-generated records from genuine user work, and is
indexed so the reset command can scope its deletion exactly. A demo run is never
silently presented as the user's own research.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nanobio_studio.app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecordOrigin(str, enum.Enum):
    """Where a stored record came from.

    This is the single mechanism that keeps demonstration material separate from
    genuine user work. It is deliberately an explicit column rather than a naming
    convention, so it can be indexed, filtered and safely used to scope deletion.
    """

    #: Created by the user through the ordinary workflow.
    USER = "user"
    #: Created by loading a demonstration scenario. Synthetic inputs.
    DEMO = "demo"


class StudyPathway(str, enum.Enum):
    """How a study began.

    Distinct from ``RecordOrigin`` on purpose. ``origin`` is the two-value
    demo/user flag that the reset command scopes its deletion on, and changing
    its meaning would weaken a safety property that is already tested. ``pathway``
    is the richer three-value fact the interface needs, and ``origin`` is derived
    from it on write, so both stay true without either being overloaded.
    """

    PATIENT_ASSESSMENT = "patient_assessment"
    RESEARCH_DESIGN = "research_design"
    DEMO_SCENARIO = "demo_scenario"


class RunStatus(str, enum.Enum):
    #: Saved but not yet run.
    DRAFT = "draft"
    #: Every engine the run attempted returned a result.
    COMPLETE = "complete"
    #: At least one engine ran and at least one was skipped or failed.
    PARTIAL = "partial"
    #: Nothing was calculated. Stored so a blocked attempt is still auditable.
    BLOCKED = "blocked"


class Project(Base):
    """A named grouping of runs."""

    __tablename__ = "workspace_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    origin: Mapped[RecordOrigin] = mapped_column(
        Enum(RecordOrigin, native_enum=False, length=16),
        nullable=False, default=RecordOrigin.USER, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow,
                                                 onupdate=utcnow)

    runs: Mapped[list["StoredRun"]] = relationship(back_populates="project")


class StoredRun(Base):
    """A completed (or deliberately blocked) execution of the connected engines.

    ``inputs_json`` and ``result_json`` are stored as JSON text rather than
    normalised columns because the engine response shapes are versioned
    contracts owned by the services, not by this schema. Normalising them here
    would duplicate the Pydantic models and guarantee drift. The engine version
    strings are stored alongside so a record stays interpretable when a contract
    changes.
    """

    __tablename__ = "workspace_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_projects.id", ondelete="SET NULL"),
        nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    origin: Mapped[RecordOrigin] = mapped_column(
        Enum(RecordOrigin, native_enum=False, length=16),
        nullable=False, default=RecordOrigin.USER, index=True)

    #: How the study began. Indexed, because the workspace lists filter on it.
    pathway: Mapped[StudyPathway] = mapped_column(
        Enum(StudyPathway, native_enum=False, length=32),
        nullable=False, default=StudyPathway.RESEARCH_DESIGN, index=True)

    #: The second-level research purpose, when the pathway is a research design.
    research_purpose: Mapped[str | None] = mapped_column(String(80),
                                                          nullable=True)

    #: True when the inputs are synthetic. Set for demonstration studies, and
    #: available for a patient assessment built on a synthetic document.
    inputs_are_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True)

    #: Links a patient-assessment study to the report it was established from.
    #: Deliberately NOT a foreign key: deleting the report must not delete the
    #: study, and the study must not keep the report alive past its retention.
    report_assessment_id: Mapped[int | None] = mapped_column(Integer,
                                                              nullable=True,
                                                              index=True)

    #: Slug of the demonstration scenario this run came from, when origin=DEMO.
    #: Null for user work. Lets History and Compare filter by scenario.
    demo_scenario_slug: Mapped[str | None] = mapped_column(String(100),
                                                            nullable=True,
                                                            index=True)
    #: Fixture-set version, so a demo run remains traceable to its exact inputs
    #: even after the scenario set is revised.
    demo_fixture_version: Mapped[str | None] = mapped_column(String(64),
                                                              nullable=True)

    # --- therapeutic context, recorded for traceability only ----------------
    disease: Mapped[str | None] = mapped_column(String(120), nullable=True,
                                                index=True)
    subtype: Mapped[str | None] = mapped_column(String(160), nullable=True)
    drug: Mapped[str | None] = mapped_column(String(160), nullable=True)

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=16),
        nullable=False, default=RunStatus.COMPLETE, index=True)

    #: The exact request bodies sent to each engine.
    design_inputs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pk_inputs_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: The exact engine responses. Written only from a genuine 200 response.
    design_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pk_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Engine version strings, denormalised for fast listing and filtering.
    design_score_version: Mapped[str | None] = mapped_column(String(64),
                                                              nullable=True)
    pk_calculation_version: Mapped[str | None] = mapped_column(String(64),
                                                                nullable=True)

    #: Newline-separated engine names. Recorded per run so a record can never be
    #: misread as having included an engine that did not execute.
    engines_run: Mapped[str] = mapped_column(Text, nullable=False, default="")
    engines_not_run: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow,
                                                 index=True)

    project: Mapped[Project | None] = relationship(back_populates="runs")


class DemoTemplate(Base):
    """A seeded demonstration-scenario template.

    Stores scenario **inputs** and teaching metadata only — never a result.
    Seeded from ``app/demo/scenarios.py`` by an idempotent command, keyed on
    ``slug`` so re-running it updates in place instead of duplicating.

    Templates are global (no owner): they are platform content, not user data,
    which is precisely why the reset command may delete them safely.
    """

    __tablename__ = "workspace_demo_templates"
    __table_args__ = (UniqueConstraint("slug", name="uq_demo_template_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    fixture_version: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)

    disease: Mapped[str] = mapped_column(String(120), nullable=False)
    subtype: Mapped[str] = mapped_column(String(160), nullable=False)
    drug: Mapped[str] = mapped_column(String(160), nullable=False)

    #: JSON payloads of the scenario's inputs and teaching metadata.
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

    technical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, default=utcnow,
                                                 onupdate=utcnow)


Index("ix_workspace_runs_owner_created", StoredRun.owner_id, StoredRun.created_at)
Index("ix_workspace_runs_origin_owner", StoredRun.origin, StoredRun.owner_id)
