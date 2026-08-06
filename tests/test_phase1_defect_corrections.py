"""Regression tests for the two Phase 1 defects.

**DEFECT-P1-A — evidence level asserted validation that nothing established.**
``_evidence_level`` returned E3 for any required field marked ``measured``, and
promoted an area to E4 or E5 whenever an in-vitro or in-vivo evidence *field*
was populated. Both are category errors. E3–E6 assert that a prediction was
checked against an independent result or an experiment; a value's provenance and
a populated free-text field establish neither. The engine was therefore
publishing "prospectively validated in vitro" for studies with no validation of
any kind, which is the single most consequential thing a readiness framework can
get wrong — it is exactly the overclaim the framework exists to prevent.

**DEFECT-P1-B — ``measured_on`` was unvalidated free text.** The API accepted
any string up to 32 characters, and both loading paths then called
``date.fromisoformat`` on it unguarded. So ``"13/05/2026"`` stored happily and
every subsequent read of that study raised ``ValueError`` — one bad keystroke
made a study permanently unopenable, including unopenable for correction.

The two halves are tested separately because they fail separately: rejecting bad
input does nothing for rows already written, and tolerating stored rubbish does
nothing to stop more arriving.

These tests state intent rather than restating the implementation. A future
change that satisfies the letter of the code but re-permits an unearned E3, or
re-introduces a crash on load, must fail here.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if _p in sys.path:
        sys.path.remove(_p)
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(REPO_ROOT))

import json  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker, create_async_engine,
)

from tests.conftest import run_async  # noqa: E402

from nanobio_studio.app.db.base import Base  # noqa: E402
from nanobio_studio.app.db import auth_models  # noqa: E402,F401
from nanobio_studio.app.db import report_models  # noqa: E402,F401
from nanobio_studio.app.db import science_models  # noqa: E402,F401
from nanobio_studio.app.db import workspace_models  # noqa: E402,F401
from nanobio_studio.app.db import validation_models  # noqa: E402,F401
from nanobio_studio.app.db.science_models import (  # noqa: E402
    ScienceDataRecord,
)
from nanobio_studio.app.db.workspace_models import (  # noqa: E402
    RecordOrigin, RunStatus, StoredRun,
)
from nanobio_studio.app.schemas.readiness import (  # noqa: E402
    ScienceRecordUpsertRequest,
)
from nanobio_studio.app.science import rules as rules_module  # noqa: E402
from nanobio_studio.app.science.data_dictionary import (  # noqa: E402
    fields_for_area,
)
from nanobio_studio.app.science.records import (  # noqa: E402
    InvalidMeasurementDate, ScientificRecord, parse_iso_date,
    parse_stored_date, record_from_dict, validate_record,
)
from nanobio_studio.app.science.rules import evaluate_study  # noqa: E402
from nanobio_studio.app.science.statuses import (  # noqa: E402
    EVIDENCE_LABEL, EVIDENCE_LEVEL_REQUIREMENT, EVIDENCE_ORDER,
    EXPERIMENTAL_VALIDATION_LEVELS, VALIDATION_KIND_LEVEL,
    VALIDATION_REGISTRY_AVAILABLE, EvidenceLevel, ReadinessArea, Requirement,
    ScientificStatus, ValidationKind, cap_to_attainable_evidence_level,
    evidence_level_is_attainable, max_attainable_evidence_level,
)
from nanobio_studio.app.services import readiness_service as svc  # noqa: E402

S = ScientificStatus
A = ReadinessArea


def rec(field_id: str, value=None, status=S.MEASURED, **kw) -> ScientificRecord:
    return ScientificRecord(field_id=field_id, status=status, value=value, **kw)


def fully_populate(area: ReadinessArea, status=S.MEASURED,
                   **kw) -> list[ScientificRecord]:
    """Every field the area consumes, populated at one provenance."""
    return [rec(spec.id, "1",
                unit=(spec.accepted_units[0] if spec.accepted_units else None),
                status=status, **kw)
            for spec in fields_for_area(area)]


async def _fresh_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    session = maker()
    await session.execute(text(
        "INSERT INTO auth_users (id, username, email, password_hash, role, "
        "is_active, created_at) VALUES "
        "(1, 'u', 'u@x.invalid', 'x', 'RESEARCHER', 1, '2026-08-01')"))
    await session.commit()
    return engine, session


async def _make_study(session, owner_id=1, design_inputs_json=None,
                      origin=RecordOrigin.USER) -> StoredRun:
    run = StoredRun(owner_id=owner_id, name="Defect study", origin=origin,
                    status=RunStatus.BLOCKED,
                    design_inputs_json=design_inputs_json)
    session.add(run)
    await session.flush()
    return run


# ===========================================================================
# DEFECT-P1-A -- evidence level
# ===========================================================================


class TestMeasuredDataDoesNotReachE3:
    """"Measured" describes how a value was obtained, not what it validated."""

    @pytest.mark.parametrize("area", list(ReadinessArea))
    def test_no_area_reaches_e3_from_measurement_alone(self, area):
        """The defect, stated once per area so none can regress alone."""
        assessment = evaluate_study(
            fully_populate(area, measurement_method="cryo-TEM")
        ).area(area)
        assert assessment.evidence_level is EvidenceLevel.E2, (
            f"{area.value} reached {assessment.evidence_level.value} from "
            "measured values with no validation recorded")

    @pytest.mark.parametrize("status",
                             [S.MEASURED, S.EXPERIMENTALLY_DERIVED])
    def test_neither_evidence_bearing_status_promotes(self, status):
        """Both halves of EVIDENCE_BEARING_STATUSES stop at E2."""
        area = evaluate_study(
            fully_populate(A.FORMULATION_ASSESSMENT, status=status,
                           measurement_method="HPLC")
        ).area(A.FORMULATION_ASSESSMENT)
        assert area.evidence_level is EvidenceLevel.E2

    def test_a_fully_measured_study_reaches_e2_in_every_area(self):
        """The ceiling is reached, so the cap is not hiding a broken engine.

        A test that only asserts "not E3" would also pass if the engine had
        stopped working and returned E0 everywhere. This pins the level from
        both sides.
        """
        records: list[ScientificRecord] = []
        seen: set[str] = set()
        for area in ReadinessArea:
            for record in fully_populate(area, measurement_method="cryo-TEM"):
                if record.field_id not in seen:
                    seen.add(record.field_id)
                    records.append(record)
        for area in evaluate_study(records).areas:
            assert area.evidence_level is EvidenceLevel.E2, area.area


class TestEvidenceFieldsDoNotPromote:
    """Populating an evidence field records a claim, not a validation."""

    IN_VITRO = ("cellular_uptake_evidence", "cytotoxicity_evidence",
                "release_profile_evidence", "selectivity_evidence",
                "trafficking_evidence")
    IN_VIVO = ("in_vivo_evidence", "clearance_evidence")

    #: (evidence field, area) pairs where the field is OPTIONAL, so its
    #: presence or absence cannot legitimately move the area's level at all.
    #:
    #: Restricted to optional pairs on purpose. Where a field is blocking —
    #: ``cytotoxicity_evidence`` for safety, say — removing it *does* change the
    #: level, correctly, because a required field went missing. Including such a
    #: pair would test the weakest-link rule, not the promotion this defect was.
    OPTIONAL_PAIRS = [
        (field_id, area)
        for field_id in (*IN_VITRO, *IN_VIVO)
        for area in ReadinessArea
        if any(spec.id == field_id
               and spec.area_requirements[area] is Requirement.OPTIONAL
               for spec in fields_for_area(area))
    ]

    def test_the_optional_pairs_cover_both_kinds_of_evidence(self):
        """Guards the fixture: an empty or one-sided sweep would prove nothing."""
        fields = {field_id for field_id, _ in self.OPTIONAL_PAIRS}
        assert fields & set(self.IN_VITRO)
        assert fields & set(self.IN_VIVO)

    @pytest.mark.parametrize("field_id, area", OPTIONAL_PAIRS)
    def test_populating_one_evidence_field_changes_no_level(self, field_id,
                                                            area):
        """Adding the field must not move the level it used to promote."""
        base = [r for r in fully_populate(area, measurement_method="assay")
                if r.field_id != field_id]
        without = evaluate_study(base).area(area).evidence_level
        with_field = evaluate_study(
            [*base, rec(field_id, "study on file",
                        measurement_method="assay")]).area(area).evidence_level
        assert without == with_field

    @pytest.mark.parametrize(
        "area", [A.BIOLOGICAL_TARGETING, A.SAFETY_ASSESSMENT,
                 A.PHARMACOKINETIC_MODELLING])
    def test_the_three_previously_promotable_areas_stay_at_e2(self, area):
        """These are precisely the areas the old code promoted to E4/E5."""
        records = [*fully_populate(area, measurement_method="assay"),
                   rec("in_vivo_evidence", "murine xenograft, 28 d",
                       measurement_method="in-vivo study"),
                   rec("cellular_uptake_evidence", "flow cytometry",
                       measurement_method="flow cytometry"),
                   rec("cytotoxicity_evidence", "MTT, 48 h",
                       measurement_method="MTT assay")]
        assessment = evaluate_study(records).area(area)
        assert assessment.evidence_level is EvidenceLevel.E2
        assert assessment.evidence_level not in EXPERIMENTAL_VALIDATION_LEVELS

    def test_the_report_says_why_a_populated_field_is_not_a_validation(self):
        area = evaluate_study([
            *fully_populate(A.SAFETY_ASSESSMENT, measurement_method="assay"),
            rec("in_vivo_evidence", "rat, IV, 14 d",
                measurement_method="in-vivo study"),
        ]).area(A.SAFETY_ASSESSMENT)
        note = next(w for w in area.warnings
                    if w.code == "evidence_field_is_not_validation")
        assert "does not raise this area to E4 or E5" in note.message
        assert "in_vivo_evidence" in note.field_ids

    def test_the_report_says_a_measurement_is_not_a_validation(self):
        area = evaluate_study(
            fully_populate(A.FORMULATION_ASSESSMENT,
                           measurement_method="cryo-TEM")
        ).area(A.FORMULATION_ASSESSMENT)
        note = next(w for w in area.warnings
                    if w.code == "measurement_is_not_validation")
        assert "not a check of any prediction" in note.message

    def test_neither_note_appears_when_nothing_is_recorded(self):
        """A rule that fires on everything is as useless as one that never does."""
        for area in evaluate_study([]).areas:
            codes = {w.code for w in area.warnings}
            assert "measurement_is_not_validation" not in codes
            assert "evidence_field_is_not_validation" not in codes


class TestWeakProvenanceNeverPromotes:
    """User-supplied, literature, predicted, assumed and illustrative."""

    @pytest.mark.parametrize(
        "status, ceiling",
        [(S.LITERATURE_DERIVED, EvidenceLevel.E1),
         (S.CALCULATED, EvidenceLevel.E2),
         (S.COMPUTATIONALLY_PREDICTED, EvidenceLevel.E2),
         (S.USER_SUPPLIED, EvidenceLevel.E0),
         (S.ASSUMED_DEFAULT, EvidenceLevel.E0),
         (S.ILLUSTRATIVE, EvidenceLevel.E0),
         (S.MISSING, EvidenceLevel.E0)])
    def test_each_status_stops_at_its_own_level(self, status, ceiling):
        area = evaluate_study(
            fully_populate(A.FORMULATION_ASSESSMENT, status=status,
                           source_citation="Doe 2020")
        ).area(A.FORMULATION_ASSESSMENT)
        assert area.evidence_level is ceiling
        assert area.evidence_level not in EXPERIMENTAL_VALIDATION_LEVELS

    @pytest.mark.parametrize("status", list(ScientificStatus))
    def test_no_status_whatsoever_can_assert_validation(self, status):
        """Enumerated over the whole vocabulary, including any added later."""
        for area in evaluate_study(
                fully_populate(A.BIOLOGICAL_TARGETING, status=status,
                               source_citation="Doe 2020")).areas:
            assert area.evidence_level not in EXPERIMENTAL_VALIDATION_LEVELS, (
                f"{status.value} reached {area.evidence_level.value} in "
                f"{area.area.value}")

    def test_every_status_has_an_explicit_basis_level_at_or_below_e2(self):
        """No status may default into a validation level by omission.

        The lookup is enumerated rather than defaulted, so a status added to the
        vocabulary without a decision about what it supports fails here instead
        of silently landing wherever ``.get`` sends it.
        """
        for status in ScientificStatus:
            if status is ScientificStatus.NOT_APPLICABLE:
                continue    # excluded from the assessment entirely
            assert status in rules_module._BASIS_LEVEL, (
                f"{status.value} has no declared basis level")
            level = rules_module._BASIS_LEVEL[status]
            assert EVIDENCE_ORDER.index(level) <= EVIDENCE_ORDER.index(
                EvidenceLevel.E2), (
                f"{status.value} declares {level.value}, which asserts a "
                "validation that provenance alone cannot establish")

    def test_a_mixed_study_still_takes_its_weakest_required_link(self):
        """The weakest-link rule survives the correction."""
        specs = [d for d in fields_for_area(A.FORMULATION_ASSESSMENT)
                 if d.area_requirements[A.FORMULATION_ASSESSMENT]
                 is not Requirement.OPTIONAL]
        records = [rec(s.id, "1", measurement_method="cryo-TEM")
                   for s in specs[1:]]
        records.append(rec(specs[0].id, "1", status=S.USER_SUPPLIED))
        assert evaluate_study(records).area(
            A.FORMULATION_ASSESSMENT).evidence_level is EvidenceLevel.E0


class TestValidationLevelsAreUnreachableInPhase1:
    """What survived Phase 2, Milestone 1, and what deliberately changed.

    Milestone 1 delivered the Experimental Validation Registry, so **E3 became
    reachable** — through the registry, and only through it. That is a
    capability landing together with the thing it depends on, which is exactly
    the condition the Phase 1 flag documented.

    What must NOT have changed is the defect this file was written for: a value
    marked ``measured``, or a populated evidence field, still promotes nothing.
    Those tests live in the classes above and are unchanged. The tests here
    track the ceiling, which moved by one rung on purpose.
    """

    def test_the_registry_is_now_available(self):
        # Phase 1 asserted False. Milestone 1 implements the lookup behind it.
        assert VALIDATION_REGISTRY_AVAILABLE is True

    def test_the_ceiling_is_e3_and_is_derived_not_hard_coded(self):
        """E3, because E3 is all the registry can grant.

        Derived from REGISTRY_GRANTABLE_LEVELS rather than written down, so
        the ceiling cannot rise without the registry gaining the capability
        behind it.
        """
        assert max_attainable_evidence_level() is EvidenceLevel.E3
        for level in (EvidenceLevel.E0, EvidenceLevel.E1, EvidenceLevel.E2,
                      EvidenceLevel.E3):
            assert evidence_level_is_attainable(level) is True

    @pytest.mark.parametrize("level", [EvidenceLevel.E4, EvidenceLevel.E5,
                                       EvidenceLevel.E6])
    def test_the_cap_still_holds_e4_e5_and_e6(self, level):
        """The last line of defence, still armed for the levels not delivered.

        A rule that computed E5 from something that is not an in-vivo
        validation is stopped here rather than published — unchanged from
        Phase 1 for every level Milestone 1 did not implement.
        """
        assert not evidence_level_is_attainable(level)
        assert cap_to_attainable_evidence_level(level) is EvidenceLevel.E3

    def test_the_cap_leaves_attainable_levels_alone(self):
        for level in (EvidenceLevel.E0, EvidenceLevel.E1, EvidenceLevel.E2,
                      EvidenceLevel.E3):
            assert cap_to_attainable_evidence_level(level) is level

    def test_the_registry_grants_e3_and_nothing_else(self):
        from nanobio_studio.app.science.statuses import (
            REGISTRY_GRANTABLE_LEVELS,
        )
        from nanobio_studio.app.validation.vocabulary import GRANTABLE_LEVELS

        assert REGISTRY_GRANTABLE_LEVELS == frozenset({EvidenceLevel.E3})
        # The registry's own view must agree with the engine's.
        assert GRANTABLE_LEVELS == REGISTRY_GRANTABLE_LEVELS

    def test_e6_is_declared_unreachable_and_says_why(self):
        assert not evidence_level_is_attainable(EvidenceLevel.E6)
        requirement = EVIDENCE_LEVEL_REQUIREMENT[EvidenceLevel.E6]
        assert "clinical" in requirement.lower()
        assert "never emits" in requirement

    def test_each_validation_kind_supports_exactly_one_level(self):
        """A registry record of one kind never establishes a higher level."""
        assert VALIDATION_KIND_LEVEL == {
            ValidationKind.RETROSPECTIVE_INDEPENDENT: EvidenceLevel.E3,
            ValidationKind.PROSPECTIVE_IN_VITRO: EvidenceLevel.E4,
            ValidationKind.IN_VIVO: EvidenceLevel.E5,
            ValidationKind.CLINICAL: EvidenceLevel.E6,
        }
        assert EXPERIMENTAL_VALIDATION_LEVELS == frozenset(
            VALIDATION_KIND_LEVEL.values())

    def test_each_validation_level_states_what_it_requires(self):
        """The requirement is recorded, so Phase 2 implements it rather than
        re-deciding it."""
        wording = {
            EvidenceLevel.E3: ("retrospective", "independent"),
            EvidenceLevel.E4: ("prospective", "in-vitro"),
            EvidenceLevel.E5: ("in-vivo",),
            EvidenceLevel.E6: ("clinical",),
        }
        for level, expected in wording.items():
            requirement = EVIDENCE_LEVEL_REQUIREMENT[level].lower()
            for word in expected:
                assert word in requirement, (level.value, word)

    def test_validation_levels_originate_in_exactly_one_function(self):
        """Confines the Phase 2 change and stops a level leaking in elsewhere."""
        assert rules_module._recorded_validations({}) == []
        source = Path(rules_module.__file__).read_text(encoding="utf-8")
        body = source.split("def _recorded_validations", 1)[1]
        rest = body.split("\ndef ", 2)[-1]
        for token in ("EvidenceLevel.E3", "EvidenceLevel.E4",
                      "EvidenceLevel.E5", "EvidenceLevel.E6"):
            assert token not in rest, (
                f"{token} is assigned outside _recorded_validations; a "
                "validation level must have exactly one origin")


class TestEvidenceLevelIsExplained:
    """A level shown without its reason invites the misreading."""

    def test_every_area_states_why_its_level_is_what_it_is(self):
        for area in evaluate_study([]).areas:
            assert len(area.evidence_level_rationale) > 60, area.area
            assert area.evidence_level_rationale.endswith(".")

    def test_the_rationale_names_the_field_that_set_the_level(self):
        area = evaluate_study(
            fully_populate(A.STRUCTURAL_VISUALIZATION,
                           measurement_method="cryo-TEM")
        ).area(A.STRUCTURAL_VISUALIZATION)
        assert "weakest required field" in area.evidence_level_rationale

    def test_the_rationale_says_why_it_is_not_higher(self):
        """Measured data with no approved experiment still stops at E2.

        The ceiling moved to E3, but reaching it needs a registry approval.
        A study with none is held at E2 and told why — which is the Phase 1
        behaviour this file exists to protect, unchanged.
        """
        area = evaluate_study(
            fully_populate(A.SAFETY_ASSESSMENT, measurement_method="assay")
        ).area(A.SAFETY_ASSESSMENT)
        assert area.evidence_level is EvidenceLevel.E2
        assert "no level above E3 is asserted" in area.evidence_level_rationale
        assert "Experimental Validation Registry" in (
            area.evidence_level_rationale)

    def test_the_rationale_is_deterministic(self):
        records = fully_populate(A.FORMULATION_ASSESSMENT,
                                 measurement_method="HPLC")
        first = [a.evidence_level_rationale for a in evaluate_study(records).areas]
        second = [a.evidence_level_rationale for a in evaluate_study(records).areas]
        assert first == second

    def test_each_area_reports_the_ceiling_alongside_its_level(self):
        for area in evaluate_study([]).areas:
            assert area.max_attainable_evidence_level is EvidenceLevel.E3
            assert area.to_dict()["max_attainable_evidence_level"] == "E3"
            assert area.to_dict()["evidence_level_rationale"]

    def test_the_report_declares_the_ceiling_on_every_assessment(self):
        payload = evaluate_study([]).to_dict()
        assert payload["validation_registry_available"] is True
        assert payload["max_attainable_evidence_level"] == "E3"
        assert "E4 to E6" in payload["evidence_ceiling_notice"]

    def test_the_e2_label_no_longer_implies_a_prediction_only(self):
        """A measurement lands on E2, so the label must cover it."""
        assert "measurement" in EVIDENCE_LABEL[EvidenceLevel.E2].lower()

    def test_the_rules_version_records_the_behaviour_change(self):
        """Snapshots record the version that produced them.

        Leaving it at 1.0.0 would make an assessment taken under the old,
        overclaiming rules indistinguishable from one taken under these.
        """
        report = evaluate_study([])
        assert report.rules_engine_version == "readiness-rules-1.1.0"


# ===========================================================================
# DEFECT-P1-B -- measured_on validation
# ===========================================================================


#: Every one of these reached the database before this correction.
BAD_DATES = [
    "13/05/2026",        # day-first, ambiguous with month-first
    "05-13-2026",        # month-first
    "2026-13-01",        # month 13
    "2026-02-30",        # a day February never has
    "2026-8-1",          # unpadded
    "20260801",          # ISO basic form, not the extended form
    "2026-W01-1",        # ISO week date: silently resolves to 2025-12-29
    "2026-08-01T09:30",  # a datetime, not a date
    "last Tuesday",
    "n/a",
    "0000-00-00",
    "-",
]

GOOD_DATES = ["2026-08-01", "1999-12-31", "2024-02-29"]


class TestMeasuredOnIsValidatedAtTheSchema:
    """Rejected at entry, where the person who typed it can still correct it."""

    @pytest.mark.parametrize("bad", BAD_DATES)
    def test_the_schema_rejects_it(self, bad):
        with pytest.raises(ValueError) as exc:
            ScienceRecordUpsertRequest(status="measured", value="100",
                                       unit="nm", measured_on=bad)
        assert "measured_on" in str(exc.value)

    @pytest.mark.parametrize("good", GOOD_DATES)
    def test_the_schema_accepts_a_real_iso_date(self, good):
        request = ScienceRecordUpsertRequest(status="measured", value="100",
                                             unit="nm", measured_on=good)
        assert request.measured_on == good

    def test_absence_stays_legitimate(self):
        """Not recording a date is not an error; recording a bad one is."""
        for value in (None, "", "   "):
            request = ScienceRecordUpsertRequest(status="measured",
                                                 measured_on=value)
            assert request.measured_on is None

    def test_a_valid_date_is_normalised(self):
        request = ScienceRecordUpsertRequest(status="measured",
                                             measured_on="  2026-08-01  ")
        assert request.measured_on == "2026-08-01"

    def test_the_message_names_the_expected_form(self):
        with pytest.raises(ValueError) as exc:
            ScienceRecordUpsertRequest(status="measured",
                                       measured_on="13/05/2026")
        message = str(exc.value)
        assert "YYYY-MM-DD" in message
        assert "2026-08-01" in message

    def test_the_week_date_is_refused_rather_than_reinterpreted(self):
        """'2026-W01-1' parses to 2025-12-29 — a different year.

        Accepting it would store a date the person who typed it did not mean,
        which is worse than rejecting it.
        """
        with pytest.raises(InvalidMeasurementDate):
            parse_iso_date("2026-W01-1")


class TestMeasuredOnIsValidatedAtTheService:
    """The schema is not the only door into the column."""

    @pytest.mark.parametrize("bad", ["13/05/2026", "2026-02-30", "not a date"])
    def test_a_direct_call_is_refused_and_nothing_is_stored(self, bad):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                with pytest.raises(svc.ReadinessError) as exc:
                    await svc.upsert_record(
                        session, owner_id=1, study_id=run.id,
                        field_id="physical_diameter",
                        payload={"status": "measured", "value": "100",
                                 "unit": "nm",
                                 "measurement_method": "cryo-TEM",
                                 "measured_on": bad})
                assert exc.value.code == "invalid_measured_on"
                assert "YYYY-MM-DD" in exc.value.message
                # A refused write leaves nothing behind.
                assert await svc.load_records(session, study_id=run.id) == []
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_a_valid_date_round_trips_normalised(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                await svc.upsert_record(
                    session, owner_id=1, study_id=run.id,
                    field_id="physical_diameter",
                    payload={"status": "measured", "value": "100",
                             "unit": "nm", "measurement_method": "cryo-TEM",
                             "measured_on": "  2026-08-01 "})
                await session.commit()
                loaded = await svc.load_records(session, study_id=run.id)
                assert loaded[0].measured_on.isoformat() == "2026-08-01"
                assert loaded[0].measured_on_raw is None
                assert loaded[0].to_dict()["measured_on"] == "2026-08-01"
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_an_invalid_date_does_not_block_a_correction(self):
        """The record can still be written once the date is fixed."""
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                with pytest.raises(svc.ReadinessError):
                    await svc.upsert_record(
                        session, owner_id=1, study_id=run.id,
                        field_id="zeta_potential",
                        payload={"status": "measured", "value": "-30",
                                 "unit": "mV", "measurement_method": "ELS",
                                 "measured_on": "31/12/2026"})
                await svc.upsert_record(
                    session, owner_id=1, study_id=run.id,
                    field_id="zeta_potential",
                    payload={"status": "measured", "value": "-30",
                             "unit": "mV", "measurement_method": "ELS",
                             "measured_on": "2026-12-31"})
                await session.commit()
                loaded = await svc.load_records(session, study_id=run.id)
                assert len(loaded) == 1
                assert loaded[0].measured_on.isoformat() == "2026-12-31"
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())


class TestMalformedStoredDatesDoNotCrashLoading:
    """A row written before the validation existed must stay loadable.

    This is the half that matters most in practice. Rejecting new bad input does
    nothing for the rows already in the column, and a study that raises on load
    cannot be opened to correct the value that makes it raise.
    """

    @pytest.mark.parametrize("bad", BAD_DATES)
    def test_a_legacy_row_loads_instead_of_raising(self, bad):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                # Written directly, as a row predating the validation would be.
                session.add(ScienceDataRecord(
                    study_id=run.id, owner_id=1, field_id="physical_diameter",
                    status=S.MEASURED, value_text="100", unit="nm",
                    measurement_method="cryo-TEM", measured_on=bad))
                await session.commit()

                loaded = await svc.load_records(session, study_id=run.id)
                assert len(loaded) == 1
                assert loaded[0].value == "100"
                # The date is treated as absent, and the raw text is kept.
                assert loaded[0].measured_on is None
                assert loaded[0].measured_on_raw == bad
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_a_full_assessment_still_runs_over_a_malformed_date(self):
        """Loading is not enough; the study must remain assessable."""
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                session.add(ScienceDataRecord(
                    study_id=run.id, owner_id=1, field_id="zeta_potential",
                    status=S.MEASURED, value_text="-30", unit="mV",
                    measurement_method="ELS", measured_on="13/05/2026"))
                await session.commit()

                report, records = await svc.assess_study(
                    session, owner_id=1, study_id=run.id)
                assert len(report.areas) == 6
                assert records[0].measured_on_raw == "13/05/2026"

                # And a snapshot of it can still be taken and re-read.
                snapshot = await svc.create_snapshot(
                    session, owner_id=1, study_id=run.id, report=report,
                    records=records)
                await session.commit()
                stored = json.loads(snapshot.input_records_json)
                assert stored[0]["measured_on"] is None
                assert stored[0]["measured_on_unparsable"] == "13/05/2026"
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_malformed_conditions_json_also_survives_loading(self):
        """The same availability argument applies to every stored column."""
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                session.add(ScienceDataRecord(
                    study_id=run.id, owner_id=1, field_id="physical_diameter",
                    status=S.MEASURED, value_text="100", unit="nm",
                    conditions_json="{not json"))
                await session.commit()
                loaded = await svc.load_records(session, study_id=run.id)
                assert loaded[0].conditions.is_empty()
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    @pytest.mark.parametrize("bad", BAD_DATES)
    def test_the_tolerant_parser_never_raises(self, bad):
        parsed, raw = parse_stored_date(bad)
        assert parsed is None
        assert raw == bad

    @pytest.mark.parametrize("good", GOOD_DATES)
    def test_the_tolerant_parser_still_parses_a_good_date(self, good):
        parsed, raw = parse_stored_date(good)
        assert parsed is not None and parsed.isoformat() == good
        assert raw is None

    def test_absence_is_reported_as_absence_not_as_malformed(self):
        for value in (None, ""):
            assert parse_stored_date(value) == (None, None)

    def test_a_snapshot_round_trips_through_record_from_dict(self):
        """Re-reading history must not be able to fail."""
        record = record_from_dict({
            "field_id": "physical_diameter", "status": "measured",
            "value": "100", "unit": "nm", "measured_on": "13/05/2026"})
        assert record.measured_on is None
        assert record.measured_on_raw == "13/05/2026"

        # And a snapshot written by the corrected code, which splits the two.
        rebuilt = record_from_dict(record.to_dict())
        assert rebuilt.measured_on is None
        assert rebuilt.measured_on_raw == "13/05/2026"

        good = record_from_dict({
            "field_id": "physical_diameter", "status": "measured",
            "value": "100", "unit": "nm", "measured_on": "2026-08-01"})
        assert good.measured_on.isoformat() == "2026-08-01"
        assert good.measured_on_raw is None

    def test_the_bad_value_is_reported_rather_than_silently_dropped(self):
        """Shown as a correctable error, not as an absence of data."""
        record = ScientificRecord(
            field_id="physical_diameter", status=S.MEASURED, value="100",
            unit="nm", measurement_method="cryo-TEM",
            measured_on_raw="13/05/2026")
        issue = next(i for i in validate_record(record)
                     if i.code == "measured_on_unparsable")
        assert issue.severity == "warning"
        assert "13/05/2026" in issue.message
        assert "YYYY-MM-DD" in issue.message
