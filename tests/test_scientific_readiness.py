"""The Scientific Readiness Framework.

Two invariants dominate these tests:

1. **A completeness percentage never satisfies a blocking requirement.** A study
   can be 78% populated and still ``BLOCKED``.
2. **Evidence level comes from records, not from form completeness.** Filling in
   more fields raises the percentage; only recorded experimental evidence raises
   the evidence level.

Everything else follows from those: assumed and illustrative values score zero,
an ambiguous ligand density is refused rather than resolved, and absent evidence
is reported as absent rather than as a negative result.
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
from nanobio_studio.app.db.migrations import (  # noqa: E402
    EXPECTED_TABLES, apply_additive_migrations, tables_awaiting_creation,
)
from nanobio_studio.app.db.workspace_models import (  # noqa: E402
    RecordOrigin, RunStatus, StoredRun,
)
from nanobio_studio.app.science.data_dictionary import (  # noqa: E402
    DATA_DICTIONARY, DICTIONARY_VERSION, blocking_fields_for_area,
    field_definition, fields_for_area, method_class,
)
from nanobio_studio.app.science.records import (  # noqa: E402
    MeasurementConditions, ScientificRecord, validate_record,
)
from nanobio_studio.app.science.rules import evaluate_study  # noqa: E402
from nanobio_studio.app.science.statuses import (  # noqa: E402
    EVIDENCE_BEARING_STATUSES, NON_CONTRIBUTING_STATUSES,
    RULES_ENGINE_VERSION, EvidenceLevel, ReadinessArea, ReadinessStatus,
    Requirement, ScientificStatus,
)
from nanobio_studio.app.services import readiness_service as svc  # noqa: E402

S = ScientificStatus
A = ReadinessArea


def rec(field_id: str, value=None, status=S.MEASURED, **kw) -> ScientificRecord:
    return ScientificRecord(field_id=field_id, status=status, value=value, **kw)


async def _fresh_db():
    """In-memory database with the current schema and one owner row."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    session = maker()
    await session.execute(text(
        "INSERT INTO auth_users (id, username, email, password_hash, role, "
        "is_active, created_at) VALUES "
        "(1, 'u', 'u@x.invalid', 'x', 'RESEARCHER', 1, '2026-08-01'), "
        "(2, 'other', 'o@x.invalid', 'x', 'RESEARCHER', 1, '2026-08-01')"))
    await session.commit()
    return engine, session


async def _make_study(session, owner_id=1, design_inputs_json=None,
                      origin=RecordOrigin.USER) -> StoredRun:
    run = StoredRun(owner_id=owner_id, name="Test study",
                    origin=origin, status=RunStatus.BLOCKED,
                    design_inputs_json=design_inputs_json)
    session.add(run)
    await session.flush()
    return run


# =========================================================================
class TestVocabularyIntegrity:

    def test_six_areas_assessed_independently(self):
        report = evaluate_study([])
        assert len(report.areas) == 6
        assert {a.area for a in report.areas} == set(ReadinessArea)

    def test_there_is_no_combined_score(self):
        report = evaluate_study([])
        # A single overall number would let one strong area mask a weak one.
        assert not hasattr(report, "overall_percent")
        assert not hasattr(report, "overall_status")

    def test_assumed_and_illustrative_are_never_evidence(self):
        assert S.ASSUMED_DEFAULT not in EVIDENCE_BEARING_STATUSES
        assert S.ILLUSTRATIVE not in EVIDENCE_BEARING_STATUSES
        assert S.USER_SUPPLIED not in EVIDENCE_BEARING_STATUSES
        assert S.ASSUMED_DEFAULT in NON_CONTRIBUTING_STATUSES
        assert S.ILLUSTRATIVE in NON_CONTRIBUTING_STATUSES

    def test_every_area_has_at_least_one_blocking_field(self):
        for area in ReadinessArea:
            assert blocking_fields_for_area(area), f"{area} has no blocking field"

    def test_every_conditional_field_states_its_condition(self):
        for spec in DATA_DICTIONARY.values():
            if Requirement.CONDITIONAL in spec.area_requirements.values():
                assert spec.condition, f"{spec.id} is conditional with no condition"

    def test_no_invented_normal_ranges(self):
        """Ranges must be definitional, not invented plausibility windows."""
        for spec in DATA_DICTIONARY.values():
            if spec.valid_range is None:
                continue
            low, high = spec.valid_range
            # Every declared range starts at zero (a physical impossibility
            # bound) or is a percentage/fraction bound.
            assert low == 0.0, f"{spec.id} has a non-zero lower bound {low}"
            assert high in (1.0, 100.0, float("inf")), (
                f"{spec.id} declares an invented upper bound {high}")


# =========================================================================
class TestBlockingOverridesPercentage:

    def test_high_percentage_still_blocks(self):
        records = [
            rec("nanoparticle_class", "lipid"), rec("architecture", "liposome"),
            rec("core_material", "DSPC"),
            rec("manufacturing_method", "thin-film hydration"),
            rec("physical_diameter", "100", unit="nm",
                measurement_method="cryo-TEM"),
            rec("encapsulation_efficiency", "85", unit="%",
                measurement_method="HPLC"),
            rec("density", "1.02", unit="g/cm3"),
            rec("crystallinity", "amorphous"),
            rec("pdi", "0.12", unit=""),
            rec("size_distribution_basis", "intensity_weighted"),
            rec("aggregation_state", "stable"), rec("stability_evidence", "7d"),
            rec("payload_identity", "doxorubicin"), rec("coating", "PEG2000"),
            rec("functional_groups", "-COOH"), rec("batch_identifier", "B-01"),
            rec("material_purity", "99", unit="%"),
            # zeta_potential (BLOCKING) deliberately absent.
        ]
        area = evaluate_study(records).area(A.FORMULATION_ASSESSMENT)
        assert area.readiness_percent >= 60
        assert area.status is ReadinessStatus.BLOCKED
        assert any(b.code == "blocking_missing_zeta_potential"
                   for b in area.blocking_issues)

    def test_empty_study_blocks_every_area(self):
        for area in evaluate_study([]).areas:
            assert area.status is ReadinessStatus.BLOCKED
            assert area.readiness_percent == 0
            assert area.evidence_level is EvidenceLevel.E0

    def test_a_blocking_field_filled_with_an_assumption_still_blocks(self):
        records = [rec("zeta_potential", "-5", unit="mV",
                       status=S.ASSUMED_DEFAULT)]
        area = evaluate_study(records).area(A.FORMULATION_ASSESSMENT)
        assert area.status is ReadinessStatus.BLOCKED
        blocking = next(b for b in area.blocking_issues
                        if b.code == "blocking_missing_zeta_potential")
        assert "not evidence about this material" in blocking.message

    def test_every_blocking_issue_explains_itself(self):
        for area in evaluate_study([]).areas:
            for finding in area.blocking_issues:
                assert len(finding.message) > 40, finding.code
                assert finding.message.endswith(".")


# =========================================================================
class TestReadinessPercentage:

    def test_assumed_and_illustrative_score_zero(self):
        records = [
            ScientificRecord("architecture", S.ILLUSTRATIVE, value="liposome"),
            ScientificRecord("physical_diameter", S.ASSUMED_DEFAULT,
                             value="100", unit="nm"),
        ]
        area = evaluate_study(records).area(A.STRUCTURAL_VISUALIZATION)
        assert area.readiness_percent == 0
        assert area.evidence_level is EvidenceLevel.E0
        assert len(area.assumptions) == 2

    def test_blocking_fields_weigh_more_than_optional_ones(self):
        only_optional = evaluate_study([
            rec("coating", "PEG"), rec("functional_groups", "-COOH"),
        ]).area(A.STRUCTURAL_VISUALIZATION).readiness_percent
        one_blocking = evaluate_study([
            rec("nanoparticle_class", "lipid"),
        ]).area(A.STRUCTURAL_VISUALIZATION).readiness_percent
        assert one_blocking > only_optional

    def test_not_applicable_is_excluded_from_the_denominator(self):
        base = evaluate_study([
            rec("nanoparticle_class", "metallic"),
        ]).area(A.STRUCTURAL_VISUALIZATION).readiness_percent
        with_na = evaluate_study([
            rec("nanoparticle_class", "metallic"),
            rec("porosity", None, status=S.NOT_APPLICABLE),
            rec("payload_location", None, status=S.NOT_APPLICABLE),
        ]).area(A.STRUCTURAL_VISUALIZATION).readiness_percent
        assert with_na > base


# =========================================================================
class TestEvidenceLevel:

    def test_form_completeness_does_not_raise_evidence(self):
        """Every required field present, but all user-supplied: still E0."""
        records = [rec(spec.id, "x", status=S.USER_SUPPLIED)
                   for spec in fields_for_area(A.FORMULATION_ASSESSMENT)]
        area = evaluate_study(records).area(A.FORMULATION_ASSESSMENT)
        assert area.readiness_percent == 100
        assert area.evidence_level is EvidenceLevel.E0

    def test_measurements_alone_do_not_reach_e3(self):
        """A measurement is an observation, not a validation of anything.

        This test previously asserted the opposite. E3 asserts that a
        prediction was checked against an independent result; recording that a
        diameter was measured by TEM says nothing was checked against anything.
        """
        records = [rec(spec.id, "1", unit=(spec.accepted_units[0]
                                           if spec.accepted_units else None),
                       measurement_method="TEM", status=S.MEASURED)
                   for spec in fields_for_area(A.STRUCTURAL_VISUALIZATION)]
        area = evaluate_study(records).area(A.STRUCTURAL_VISUALIZATION)
        assert area.evidence_level is EvidenceLevel.E2

    def test_literature_only_gives_e1(self):
        records = [rec(spec.id, "1", status=S.LITERATURE_DERIVED,
                       source_citation="Doe 2020")
                   for spec in fields_for_area(A.FORMULATION_ASSESSMENT)]
        assert evaluate_study(records).area(
            A.FORMULATION_ASSESSMENT).evidence_level is EvidenceLevel.E1

    def test_evidence_is_the_weakest_required_link(self):
        """One assumed field drags the whole area back to E0."""
        specs = fields_for_area(A.FORMULATION_ASSESSMENT)
        records = [rec(s.id, "1", measurement_method="TEM") for s in specs[1:]]
        records.append(rec(specs[0].id, "1", status=S.ASSUMED_DEFAULT))
        assert evaluate_study(records).area(
            A.FORMULATION_ASSESSMENT).evidence_level is EvidenceLevel.E0

    def test_a_populated_in_vivo_field_does_not_reach_e5(self):
        """Populating an evidence field is not an in-vivo validation.

        Also previously asserted the opposite. ``in_vivo_evidence`` holding
        text records the claim that a study exists; it does not record that a
        prediction was registered, tested against it, and found to hold.
        """
        records = [rec(s.id, "1", measurement_method="assay")
                   for s in fields_for_area(A.SAFETY_ASSESSMENT)]
        area = evaluate_study(records).area(A.SAFETY_ASSESSMENT)
        assert area.evidence_level is EvidenceLevel.E2


# =========================================================================
class TestAmbiguousLigandDensity:

    def test_bare_percentage_is_refused(self):
        area = evaluate_study([
            rec("ligand_identity", "folate"),
            rec("target_disease", "Ovarian cancer"),
            rec("target_receptor", "FRalpha"),
            rec("ligand_density_value", "5", unit="%"),
            rec("ligand_density_unit", "ambiguous_percent"),
        ]).area(A.BIOLOGICAL_TARGETING)
        blocking = {b.code for b in area.blocking_issues}
        assert "ligand_density_ambiguous" in blocking
        message = next(b.message for b in area.blocking_issues
                       if b.code == "ligand_density_ambiguous")
        for meaning in ("surface coverage", "molar percent", "mass percent"):
            assert meaning in message

    def test_missing_unit_is_refused(self):
        area = evaluate_study([
            rec("ligand_density_value", "5", unit="%"),
        ]).area(A.BIOLOGICAL_TARGETING)
        assert any(b.code == "ligand_density_unit_missing"
                   for b in area.blocking_issues)

    def test_per_area_density_is_accepted(self):
        area = evaluate_study([
            rec("ligand_density_value", "0.05", unit="per_nm2"),
            rec("ligand_density_unit", "per_nm2"),
        ]).area(A.BIOLOGICAL_TARGETING)
        codes = {b.code for b in area.blocking_issues}
        assert "ligand_density_ambiguous" not in codes
        assert "ligand_density_unit_missing" not in codes

    def test_coverage_fraction_needs_a_footprint(self):
        area = evaluate_study([
            rec("ligand_density_value", "0.4", unit="per_nm2"),
            rec("ligand_density_unit", "surface_coverage_fraction"),
        ]).area(A.BIOLOGICAL_TARGETING)
        assert any(b.code == "footprint_missing" for b in area.blocking_issues)


# =========================================================================
class TestMolecularPopulationInputs:

    def test_missing_molecular_weight_blocks(self):
        area = evaluate_study([
            rec("payload_identity", "doxorubicin"),
        ]).area(A.PHARMACOKINETIC_MODELLING)
        block = next(b for b in area.blocking_issues
                     if b.code == "payload_molecular_weight_missing")
        assert "Encapsulation efficiency does not supply one" in block.message

    def test_missing_quantity_blocks(self):
        area = evaluate_study([
            rec("payload_identity", "doxorubicin"),
            rec("payload_molecular_weight", "543.5", unit="g/mol"),
        ]).area(A.PHARMACOKINETIC_MODELLING)
        assert any(b.code == "payload_quantity_missing"
                   for b in area.blocking_issues)

    def test_weight_based_dose_without_a_weight_blocks(self):
        area = evaluate_study([
            rec("dose_amount", "6", unit="mg/kg"),
        ]).area(A.PHARMACOKINETIC_MODELLING)
        block = next(b for b in area.blocking_issues
                     if b.code == "body_weight_missing")
        assert "No default weight is applied" in block.message


# =========================================================================
class TestMeasurementCompatibility:

    def test_dls_recorded_as_physical_diameter_is_flagged(self):
        area = evaluate_study([
            rec("physical_diameter", "95", unit="nm", measurement_method="DLS"),
        ]).area(A.STRUCTURAL_VISUALIZATION)
        assert any(i.code == "physical_diameter_from_scattering"
                   for i in area.incompatible_inputs)

    def test_microscopy_recorded_as_hydrodynamic_is_flagged(self):
        area = evaluate_study([
            rec("hydrodynamic_diameter", "95", unit="nm",
                measurement_method="cryo-TEM"),
        ]).area(A.FORMULATION_ASSESSMENT)
        assert any(i.code == "hydrodynamic_diameter_from_microscopy"
                   for i in area.incompatible_inputs)

    def test_hydrodynamic_smaller_than_physical_is_impossible(self):
        area = evaluate_study([
            rec("physical_diameter", "100", unit="nm", measurement_method="TEM"),
            rec("hydrodynamic_diameter", "80", unit="nm",
                measurement_method="DLS"),
        ]).area(A.FORMULATION_ASSESSMENT)
        assert any(i.code == "hydrodynamic_smaller_than_physical"
                   for i in area.incompatible_inputs)

    def test_conflicting_conditions_are_detected(self):
        area = evaluate_study([
            rec("physical_diameter", "100", unit="nm", measurement_method="TEM",
                conditions=MeasurementConditions(medium="water", ph=7.4)),
            rec("hydrodynamic_diameter", "120", unit="nm",
                measurement_method="DLS",
                conditions=MeasurementConditions(medium="serum", ph=7.4)),
            rec("size_distribution_basis", "intensity_weighted"),
        ]).area(A.FORMULATION_ASSESSMENT)
        assert any(i.code == "diameter_conditions_differ"
                   for i in area.incompatible_inputs)

    def test_distribution_basis_is_required(self):
        area = evaluate_study([
            rec("hydrodynamic_diameter", "120", unit="nm",
                measurement_method="DLS"),
        ]).area(A.FORMULATION_ASSESSMENT)
        assert any(i.code == "distribution_basis_missing"
                   for i in area.incompatible_inputs)

    def test_impossible_coating_geometry_is_detected(self):
        area = evaluate_study([
            rec("physical_diameter", "100", unit="nm", measurement_method="TEM"),
            rec("coating_thickness", "60", unit="nm", measurement_method="TEM"),
        ]).area(A.STRUCTURAL_VISUALIZATION)
        assert any(i.code == "coating_exceeds_diameter"
                   for i in area.incompatible_inputs)

    def test_method_classification(self):
        assert method_class("DLS") == "scattering"
        assert method_class("cryo-TEM") == "microscopy"
        assert method_class("BET") == "adsorption"
        # An unrecognised method is not forced into a family.
        assert method_class("in-house protocol") is None
        assert method_class(None) is None


# =========================================================================
class TestArchitectureModelMatch:

    def test_liposome_assumptions_are_not_applied_to_metallic(self):
        area = evaluate_study([
            rec("architecture", "metallic"), rec("payload_location", "bilayer"),
        ]).area(A.STRUCTURAL_VISUALIZATION)
        finding = next(i for i in area.incompatible_inputs
                       if i.code == "bilayer_assumption_misapplied")
        assert "not applied to metallic, silica or polymeric" in finding.message

    def test_unsupported_architecture_is_outside_the_model_domain(self):
        area = evaluate_study([
            rec("architecture", "dendrimer"),
        ]).area(A.STRUCTURAL_VISUALIZATION)
        assert area.status is ReadinessStatus.OUTSIDE_MODEL_DOMAIN

    def test_class_and_architecture_conflict_is_detected(self):
        area = evaluate_study([
            rec("architecture", "liposome"), rec("nanoparticle_class", "metallic"),
        ]).area(A.STRUCTURAL_VISUALIZATION)
        assert any(i.code == "class_architecture_conflict"
                   for i in area.incompatible_inputs)


# =========================================================================
class TestBiologicalEvidence:

    def test_receptor_expression_is_required(self):
        area = evaluate_study([
            rec("ligand_identity", "trastuzumab"),
            rec("target_disease", "Breast cancer"),
            rec("target_receptor", "HER2"),
        ]).area(A.BIOLOGICAL_TARGETING)
        block = next(b for b in area.blocking_issues
                     if b.code == "receptor_expression_missing")
        assert "hypothesis" in block.message

    def test_expression_needs_a_unit_and_a_method(self):
        area = evaluate_study([
            rec("receptor_expression_value", "3", unit="IHC_score"),
        ]).area(A.BIOLOGICAL_TARGETING)
        codes = {b.code for b in area.blocking_issues}
        assert "expression_unit_missing" in codes
        assert "expression_method_missing" in codes

    def test_absent_evidence_is_not_a_negative_result(self):
        area = evaluate_study([]).area(A.BIOLOGICAL_TARGETING)
        note = next(w for w in area.warnings
                    if w.code == "absent_evidence_cellular_uptake_evidence")
        assert "not a finding that the effect is absent" in note.message

    def test_binding_affinity_needs_its_assay(self):
        area = evaluate_study([
            rec("binding_affinity", "12", unit="nM"),
        ]).area(A.BIOLOGICAL_TARGETING)
        assert any(b.code == "binding_assay_missing" for b in area.blocking_issues)


# =========================================================================
class TestRecordValidation:

    def test_invalid_unit_is_rejected(self):
        issues = validate_record(
            rec("physical_diameter", "100", unit="furlongs"))
        assert any(i.code == "invalid_unit" for i in issues)

    def test_missing_unit_is_rejected_where_one_is_required(self):
        issues = validate_record(rec("physical_diameter", "100"))
        assert any(i.code == "missing_unit" for i in issues)

    def test_non_numeric_value_is_rejected(self):
        issues = validate_record(
            rec("physical_diameter", "large", unit="nm"))
        assert any(i.code == "not_a_number" for i in issues)

    def test_definitional_range_is_enforced(self):
        issues = validate_record(
            rec("encapsulation_efficiency", "140", unit="%"))
        assert any(i.code == "out_of_range" for i in issues)

    def test_invalid_enum_choice_is_rejected(self):
        issues = validate_record(rec("architecture", "dendrimer"))
        assert any(i.code == "invalid_choice" for i in issues)

    def test_measured_without_a_method_warns(self):
        issues = validate_record(
            rec("physical_diameter", "100", unit="nm"))
        warn = next(i for i in issues if i.code == "method_not_recorded")
        assert warn.severity == "warning"

    def test_literature_value_without_a_citation_is_rejected(self):
        issues = validate_record(
            rec("physical_diameter", "100", unit="nm",
                status=S.LITERATURE_DERIVED, measurement_method="TEM"))
        assert any(i.code == "citation_missing" for i in issues)

    def test_unsupported_status_is_rejected(self):
        issues = validate_record(
            rec("physical_diameter", "100", unit="nm", status=S.ILLUSTRATIVE))
        assert any(i.code == "unsupported_status" for i in issues)

    def test_unknown_field_is_rejected(self):
        issues = validate_record(rec("not_a_real_field", "1"))
        assert issues and issues[0].code == "unknown_field"


# =========================================================================
class TestDeterminismAndVersioning:

    def test_same_records_give_the_same_assessment(self):
        records = [rec("nanoparticle_class", "lipid"),
                   rec("architecture", "liposome")]
        a = evaluate_study(records)
        b = evaluate_study(records)
        assert [x.to_dict() for x in a.areas] == [x.to_dict() for x in b.areas]

    def test_the_report_records_its_versions(self):
        report = evaluate_study([])
        assert report.rules_engine_version == RULES_ENGINE_VERSION
        assert report.dictionary_version == DICTIONARY_VERSION
        assert "not regulatory approval" in report.notice


# =========================================================================
class TestPersistenceAndLegacy:

    def test_an_upgrade_reports_the_new_tables_before_they_are_created(self):
        """An existing database gaining these tables is news; a fresh one is not.

        The report is an observation made *before* ``create_all``, not a claim
        that the migration created anything. Keeping the two apart is what lets
        ``apply_additive_migrations`` still return [] once it has nothing left
        to do.
        """
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                # An existing database: the old table is there, the new ones
                # are not.
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "CREATE TABLE workspace_runs ("
                        " id INTEGER PRIMARY KEY, owner_id INTEGER,"
                        " name VARCHAR(200), origin VARCHAR(16),"
                        " status VARCHAR(16))"))

                assert sorted(await tables_awaiting_creation(engine))                     == sorted(EXPECTED_TABLES)

                # Observing does not create; create_all does.
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                assert await tables_awaiting_creation(engine) == []
            finally:
                await engine.dispose()
        run_async(scenario())

    def test_a_fresh_database_reports_nothing(self):
        """Every table is absent; naming each one would be noise, not news."""
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                assert await tables_awaiting_creation(engine) == []
            finally:
                await engine.dispose()
        run_async(scenario())

    def test_the_migration_never_claims_to_create_these_tables(self):
        """The regression this pair of functions was split to prevent.

        ``apply_additive_migrations`` adds columns. It does not create tables,
        so it must not report them — and must stay idempotent on a database
        where these tables are still absent.
        """
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(
                        "CREATE TABLE workspace_runs ("
                        " id INTEGER PRIMARY KEY, owner_id INTEGER,"
                        " name VARCHAR(200), origin VARCHAR(16),"
                        " status VARCHAR(16))"))
                first = await apply_additive_migrations(engine)
                second = await apply_additive_migrations(engine)
                for table in EXPECTED_TABLES:
                    assert not any(table in entry for entry in first)
                assert second == []
            finally:
                await engine.dispose()
        run_async(scenario())

    def test_the_science_tables_are_declared_so_an_upgrade_is_visible(self):
        assert "science_data_records" in EXPECTED_TABLES
        assert "science_readiness_snapshots" in EXPECTED_TABLES


    def test_records_round_trip(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                await svc.upsert_record(
                    session, owner_id=1, study_id=run.id,
                    field_id="physical_diameter",
                    payload={"status": "measured", "value": "100",
                             "unit": "nm", "measurement_method": "cryo-TEM",
                             "conditions": {"medium": "water", "ph": 7.4}})
                await session.commit()

                loaded = await svc.load_records(session, study_id=run.id)
                assert len(loaded) == 1
                assert loaded[0].value == "100"
                assert loaded[0].conditions.medium == "water"
                assert loaded[0].is_evidence
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_invalid_record_is_refused_and_not_stored(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                with pytest.raises(svc.ReadinessError) as exc:
                    await svc.upsert_record(
                        session, owner_id=1, study_id=run.id,
                        field_id="physical_diameter",
                        payload={"status": "measured", "value": "100",
                                 "unit": "furlongs"})
                assert exc.value.code == "validation_failed"
                assert await svc.load_records(session, study_id=run.id) == []
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_unknown_field_is_refused(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                with pytest.raises(svc.ReadinessError) as exc:
                    await svc.upsert_record(
                        session, owner_id=1, study_id=run.id,
                        field_id="made_up", payload={"status": "measured"})
                assert exc.value.code == "unknown_field"
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_legacy_study_loads_as_user_supplied(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session, design_inputs_json=(
                    '{"size_nm": 100, "charge_mv": -5, '
                    '"encapsulation_percent": 85}'))
                report, records = await svc.assess_study(
                    session, owner_id=1, study_id=run.id)
                by_id = {r.field_id: r for r in records}
                assert by_id["physical_diameter"].status is S.USER_SUPPLIED
                assert by_id["zeta_potential"].value == "-5"
                # A legacy value carries no evidence, so evidence stays at E0.
                assert report.area(
                    A.FORMULATION_ASSESSMENT).evidence_level is EvidenceLevel.E0
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_legacy_ligand_percentage_is_marked_ambiguous(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session, design_inputs_json=(
                    '{"ligand_density_percent": 40}'))
                report, _ = await svc.assess_study(session, owner_id=1,
                                                   study_id=run.id)
                area = report.area(A.BIOLOGICAL_TARGETING)
                assert any(b.code == "ligand_density_ambiguous"
                           for b in area.blocking_issues)
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_a_demonstration_study_is_illustrative_not_user_supplied(self):
        """Nobody supplied a demo value, so nobody may be credited with it.

        The same design inputs that read as USER_SUPPLIED on a real study must
        read as ILLUSTRATIVE on a seeded one. Otherwise a demonstration looks
        like someone's data.
        """
        async def scenario():
            engine, session = await _fresh_db()
            try:
                inputs = ('{"size_nm": 100, "charge_mv": -5, '
                          '"encapsulation_percent": 85}')
                demo = await _make_study(session, design_inputs_json=inputs,
                                         origin=RecordOrigin.DEMO)
                real = await _make_study(session, design_inputs_json=inputs,
                                         origin=RecordOrigin.USER)

                _, demo_records = await svc.assess_study(
                    session, owner_id=1, study_id=demo.id)
                _, real_records = await svc.assess_study(
                    session, owner_id=1, study_id=real.id)

                assert all(r.status is S.ILLUSTRATIVE for r in demo_records)
                assert all(r.status is S.USER_SUPPLIED for r in real_records)
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_a_seeded_study_never_shows_a_successful_outcome(self):
        """Seeded data must not manufacture readiness.

        This is the property that stops a demonstration database from looking
        like a validated one: every area stays at zero, at E0, and blocked.
        """
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session, origin=RecordOrigin.DEMO,
                                        design_inputs_json=(
                                            '{"size_nm": 100, "charge_mv": -5, '
                                            '"encapsulation_percent": 85, '
                                            '"pdi": 0.12, '
                                            '"coating_thickness_nm": 5, '
                                            '"surface_area_nm2": 31415, '
                                            '"hydrodynamic_size_nm": 120}'))
                report, records = await svc.assess_study(
                    session, owner_id=1, study_id=run.id)

                assert records, "the fixture should produce records"
                for area in report.areas:
                    assert area.readiness_percent == 0, area.area
                    assert area.evidence_level is EvidenceLevel.E0, area.area
                    assert area.status is ReadinessStatus.BLOCKED, area.area
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_the_demo_note_does_not_claim_a_researcher_entered_it(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session, origin=RecordOrigin.DEMO,
                                        design_inputs_json='{"size_nm": 100}')
                records = svc.legacy_records_for_study(run)
                note = records[0].notes or ""
                assert "demonstration" in note.lower()
                assert "no real material" in note.lower()
                assert "supplied by a researcher" not in note.lower() or                     "not measured" in note.lower()
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_legacy_study_with_no_inputs_is_safe(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session, design_inputs_json=None)
                report, records = await svc.assess_study(session, owner_id=1,
                                                         study_id=run.id)
                assert records == []
                assert len(report.areas) == 6
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_corrupt_legacy_json_does_not_crash(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session,
                                        design_inputs_json="{not json")
                _, records = await svc.assess_study(session, owner_id=1,
                                                    study_id=run.id)
                assert records == []
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())


# =========================================================================
class TestAuthorization:

    def test_another_users_study_is_not_found(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session, owner_id=1)
                with pytest.raises(svc.ReadinessError) as exc:
                    await svc.get_owned_study(session, owner_id=2,
                                              study_id=run.id)
                # Ownership is checked before existence is revealed, so this
                # cannot be used to probe for other users' study ids.
                assert exc.value.code == "study_not_found"
                assert "does not exist" in exc.value.message
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_a_missing_study_reports_the_same_error(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                with pytest.raises(svc.ReadinessError) as exc:
                    await svc.get_owned_study(session, owner_id=1,
                                              study_id=9999)
                assert exc.value.code == "study_not_found"
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())


# =========================================================================
class TestSnapshots:

    def test_snapshot_records_inputs_rules_and_time(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                await svc.upsert_record(
                    session, owner_id=1, study_id=run.id,
                    field_id="zeta_potential",
                    payload={"status": "measured", "value": "-5", "unit": "mV",
                             "measurement_method": "ELS",
                             "conditions": {"medium": "PBS", "ph": 7.4}})
                report, records = await svc.assess_study(session, owner_id=1,
                                                         study_id=run.id)
                snap = await svc.create_snapshot(
                    session, owner_id=1, study_id=run.id, report=report,
                    records=records, trigger="test",
                    model_version="pk-route-aware-two-compartment-0.1.0")
                await session.commit()

                assert snap.rules_engine_version == RULES_ENGINE_VERSION
                assert snap.dictionary_version == DICTIONARY_VERSION
                assert snap.model_version.startswith("pk-route-aware")
                assert "zeta_potential" in snap.input_records_json

                rows = await svc.list_snapshots(session, study_id=run.id)
                assert len(rows) == 1
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_snapshots_are_traceable_after_data_changes(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                run = await _make_study(session)
                report, records = await svc.assess_study(session, owner_id=1,
                                                         study_id=run.id)
                snap = await svc.create_snapshot(
                    session, owner_id=1, study_id=run.id, report=report,
                    records=records)
                original = snap.report_json

                # Change the data afterwards.
                await svc.upsert_record(
                    session, owner_id=1, study_id=run.id,
                    field_id="zeta_potential",
                    payload={"status": "measured", "value": "-30",
                             "unit": "mV", "measurement_method": "ELS"})
                await session.commit()

                rows = await svc.list_snapshots(session, study_id=run.id)
                # The historical snapshot is unchanged: it records what was
                # assessed then, not what the data says now.
                assert rows[0].report_json == original
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())


# =========================================================================
class TestScientificEquationsUntouched:

    def test_pk_golden_vector_is_unchanged(self):
        from utils.pk_model import two_compartment_model

        _, cp, ct = two_compartment_model(
            dose=3.0, kabs=0.5, kel=0.1, k12=0.2, k21=0.05,
            duration=48.0, dt=0.1)
        assert cp[0] == 0.0
        assert repr(float(cp.max())) == repr(1.4411129411755834)
        assert repr(float(ct.max())) == repr(1.5287460434185478)

    def test_the_framework_imports_no_scientific_engine(self):
        """The rules engine must not reach into the calculation modules."""
        from nanobio_studio.app.science import rules
        source = Path(rules.__file__).read_text(encoding="utf-8")
        for forbidden in ("pk_model", "compute_impact", "design_scoring",
                          "simulate_pk"):
            assert forbidden not in source
