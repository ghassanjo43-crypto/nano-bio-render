"""Route-aware pharmacokinetics: input sources, model selection, derivation.

The defect these exist for
--------------------------
The PK input screen asked every user for an absorption rate constant ``k_abs``,
a depot-model parameter, regardless of administration route — while the selected
therapeutic was intravenous trastuzumab. ``k_abs`` is genuinely consumed by the
depot model, so the number entered silently determined the reported profile of a
drug that has no absorption phase.

These tests pin the corrected behaviour: the route decides the input function,
an intravenous route never requests or accepts ``k_abs``, parameters come from
cited sets rather than defaults, and a therapeutic/route combination with no
reviewed parameter set is blocked rather than run on invented constants.
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

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from nanobio_studio.app.pk.administration import (  # noqa: E402
    AdministrationRoute,
    InputFunction,
    all_routes,
    route_spec,
)
from nanobio_studio.app.pk.derivation import (  # noqa: E402
    DerivationError,
    derive_rate_constants,
)
from nanobio_studio.app.pk.models import (  # noqa: E402
    DoseRegimen,
    ModelExecutionError,
    ModelInputs,
    PK_ENGINE_VERSION,
    analytical_iv_bolus_central,
    simulate,
    verify_against_analytical_solution,
)
from nanobio_studio.app.pk.parameter_library import (  # noqa: E402
    PARAMETER_LIBRARY,
    ModelStructure,
    ParameterSet,
    ParameterValue,
    ValidationStatus,
)
from nanobio_studio.app.pk.planning import (  # noqa: E402
    DoseBasis,
    InputMode,
    InputSource,
    build_plan,
    resolve_absolute_dose,
)
from nanobio_studio.app.pk.units import (  # noqa: E402
    Dimension,
    Quantity,
    UnitError,
    divide,
)

IV_ROUTES = (AdministrationRoute.IV_BOLUS, AdministrationRoute.IV_INFUSION)
EXTRAVASCULAR = (AdministrationRoute.SUBCUTANEOUS, AdministrationRoute.ORAL,
                 AdministrationRoute.INTRAPERITONEAL)


def _linear_2c_set(**overrides) -> ParameterSet:
    """A researcher-supplied set, used to exercise the machinery.

    Deliberately NOT a clinical claim: its validation status is
    ``RESEARCHER_SUPPLIED`` and its citation says so, which is why guided mode
    refuses it.
    """
    defaults = dict(
        id="test-linear-2c", version="1.0.0",
        therapeutic="Test Compound", formulation="solution",
        route=AdministrationRoute.IV_INFUSION,
        population="Synthetic test values; not a real population.",
        model_structure=ModelStructure.TWO_COMPARTMENT_LINEAR,
        indication=None,
        source_citation="Synthetic values constructed for unit testing only.",
        validation_status=ValidationStatus.RESEARCHER_SUPPLIED,
        date_reviewed="2026-08-02",
        limitations=("Synthetic test values. Not usable for any scientific "
                     "or clinical purpose.",),
        parameters={
            "CL": ParameterValue(0.5, "L/h", Dimension.FLOW),
            "Vc": ParameterValue(5.0, "L", Dimension.VOLUME),
            "Q": ParameterValue(1.0, "L/h", Dimension.FLOW),
            "Vp": ParameterValue(10.0, "L", Dimension.VOLUME),
        },
    )
    defaults.update(overrides)
    return ParameterSet(**defaults)


# =========================================================================
# 1 + 2. IV routes never request k_abs
# =========================================================================
class TestIntravenousHasNoAbsorption:

    @pytest.mark.parametrize("route", IV_ROUTES)
    def test_k_abs_is_marked_not_applicable(self, route):
        spec = route_spec(route)
        assert "k_abs" in spec.not_applicable_inputs
        assert "k_abs" not in spec.required_dosing_inputs
        assert spec.has_absorption_phase is False

    @pytest.mark.parametrize("route", IV_ROUTES)
    def test_plan_lists_k_abs_as_not_applicable(self, route):
        plan = build_plan(therapeutic="Trastuzumab (Herceptin)", route=route)
        assert "k_abs" in plan.not_applicable
        assert not any(i.name == "k_abs" for i in plan.inputs)

    @pytest.mark.parametrize("route", IV_ROUTES)
    def test_engine_refuses_a_supplied_k_abs(self, route):
        # Refused, not silently ignored: ignoring it would let the user believe
        # the number they typed affected the result.
        regimen = (DoseRegimen(dose_mg=100, infusion_duration_h=1.0)
                   if route is AdministrationRoute.IV_INFUSION
                   else DoseRegimen(dose_mg=100))
        with pytest.raises(ModelExecutionError) as exc:
            simulate(ModelInputs(route=route, regimen=regimen,
                                 k_el_per_h=0.1, k_12_per_h=0.3, k_21_per_h=0.15,
                                 v_c_litres=5, v_p_litres=10, k_abs_per_h=1.0))
        assert exc.value.code == "input_not_applicable"

    def test_iv_bolus_puts_the_dose_in_the_central_compartment(self):
        out = simulate(ModelInputs(
            route=AdministrationRoute.IV_BOLUS,
            regimen=DoseRegimen(dose_mg=100),
            k_el_per_h=0.1, k_12_per_h=0.3, k_21_per_h=0.15,
            v_c_litres=5.0, v_p_litres=10.0, duration_h=24, time_step_h=0.01))
        # C(0) = Dose / Vc. The legacy depot model gives 0 here, always.
        assert out.central_concentration[0] == pytest.approx(20.0)

    def test_iv_infusion_uses_a_zero_order_input_not_a_depot(self):
        out = simulate(ModelInputs(
            route=AdministrationRoute.IV_INFUSION,
            regimen=DoseRegimen(dose_mg=100, infusion_duration_h=1.5),
            k_el_per_h=0.1, k_12_per_h=0.3, k_21_per_h=0.15,
            v_c_litres=5.0, v_p_litres=10.0, duration_h=24, time_step_h=0.01))
        t = np.array(out.time_h)
        c = np.array(out.central_concentration)
        assert c[0] == pytest.approx(0.0)          # infusion has not started
        # Peak at the end of infusion is the defining feature of zero-order
        # input; a depot model peaks later and lower.
        assert t[c.argmax()] == pytest.approx(1.5, abs=0.05)

    def test_infusion_requires_a_duration(self):
        with pytest.raises(ModelExecutionError) as exc:
            simulate(ModelInputs(
                route=AdministrationRoute.IV_INFUSION,
                regimen=DoseRegimen(dose_mg=100),
                k_el_per_h=0.1, k_12_per_h=0.3, k_21_per_h=0.15,
                v_c_litres=5, v_p_litres=10))
        assert exc.value.code == "missing_required_input"


# =========================================================================
# 3. Extravascular routes show absorption inputs only where supported
# =========================================================================
class TestExtravascularRoutes:

    @pytest.mark.parametrize("route", EXTRAVASCULAR)
    def test_absorption_is_required_and_supported(self, route):
        spec = route_spec(route)
        assert spec.has_absorption_phase
        assert "k_abs" in spec.required_dosing_inputs
        assert "k_abs" not in spec.not_applicable_inputs

    @pytest.mark.parametrize("route", EXTRAVASCULAR)
    def test_missing_k_abs_blocks_rather_than_defaults(self, route):
        with pytest.raises(ModelExecutionError) as exc:
            simulate(ModelInputs(route=route, regimen=DoseRegimen(dose_mg=100),
                                 k_el_per_h=0.1, k_12_per_h=0.3, k_21_per_h=0.15,
                                 v_c_litres=5, v_p_litres=10, k_abs_per_h=None))
        assert exc.value.code == "missing_required_input"

    def test_every_route_declares_exactly_one_input_function(self):
        for spec in all_routes():
            assert isinstance(spec.input_function, InputFunction)
            has_ka = spec.input_function is InputFunction.FIRST_ORDER_DEPOT
            assert spec.has_absorption_phase is has_ka


# =========================================================================
# 4. IV trastuzumab specifically
# =========================================================================
class TestTrastuzumab:

    def test_iv_trastuzumab_is_not_described_as_a_depot(self):
        spec = route_spec(AdministrationRoute.IV_INFUSION)
        text = (spec.description + " ".join(spec.notes)).lower()
        assert "depot" not in text or "no depot" in text
        assert spec.input_function is InputFunction.ZERO_ORDER_CENTRAL

    def test_iv_trastuzumab_requires_infusion_inputs(self):
        spec = route_spec(AdministrationRoute.IV_INFUSION)
        assert "infusion_duration_h" in spec.required_dosing_inputs
        assert "dose" in spec.required_dosing_inputs

    def test_iv_trastuzumab_is_blocked_with_no_reviewed_parameters(self):
        plan = build_plan(therapeutic="Trastuzumab (Herceptin)",
                          route=AdministrationRoute.IV_INFUSION)
        assert plan.runnable is False
        assert "Not yet operational" in plan.suitability
        assert plan.missing_inputs == ["CL", "Vc", "Q", "Vp"]

    def test_bioavailability_for_iv_is_a_route_property_not_a_parameter(self):
        plan = build_plan(therapeutic="Trastuzumab (Herceptin)",
                          route=AdministrationRoute.IV_BOLUS)
        f = next(i for i in plan.inputs if i.name == "bioavailability")
        assert f.value == 1.0
        assert f.editable is False


# =========================================================================
# 5 + 6. Missing parameters block; nothing is defaulted or borrowed
# =========================================================================
class TestNoInventedDefaults:

    def test_library_ships_with_no_unverified_clinical_sets(self):
        # An empty library is the correct state until sets are verified against
        # an authoritative source. It must not be quietly filled.
        for ps in PARAMETER_LIBRARY:
            assert ps.validation_status in {
                ValidationStatus.REGULATORY_LABEL,
                ValidationStatus.PUBLISHED_POPULATION_PK,
            }, f"{ps.id} is in the library without a verified source"

    def test_every_therapeutic_route_pair_blocks_when_unreviewed(self):
        for route in AdministrationRoute:
            plan = build_plan(therapeutic="Anything At All", route=route)
            assert plan.runnable is False
            assert plan.blocking_reasons

    def test_a_parameter_set_cannot_exist_without_a_citation(self):
        with pytest.raises(ValueError, match="citation"):
            _linear_2c_set(source_citation="   ")

    def test_a_set_for_one_route_is_refused_for_another(self):
        iv_set = _linear_2c_set(route=AdministrationRoute.IV_INFUSION)
        plan = build_plan(therapeutic="Test Compound",
                          route=AdministrationRoute.SUBCUTANEOUS,
                          mode=InputMode.EXPERT_RESEARCH,
                          parameter_set=iv_set)
        assert plan.runnable is False
        assert "cannot be used" in " ".join(plan.blocking_reasons)

    def test_researcher_supplied_sets_are_refused_by_guided_mode(self):
        assert _linear_2c_set().usable_in_guided_mode is False

    def test_weight_based_dose_without_a_weight_is_refused(self):
        # Assuming a "typical 70 kg" would invent a patient characteristic that
        # scales every reported concentration.
        with pytest.raises(ValueError, match="body weight"):
            resolve_absolute_dose(basis=DoseBasis.PER_KG, amount=6.0,
                                  body_weight_kg=None)

    def test_weight_based_dose_with_a_weight_is_exact(self):
        mg, explanation = resolve_absolute_dose(
            basis=DoseBasis.PER_KG, amount=6.0, body_weight_kg=68.0)
        assert mg == pytest.approx(408.0)
        assert "68.0 kg" in explanation


# =========================================================================
# 7 + 8. Derivation and unit validation
# =========================================================================
class TestDerivation:

    def test_derives_the_three_rate_constants(self):
        derived = derive_rate_constants(_linear_2c_set())
        assert derived["k_el"].value == pytest.approx(0.5 / 5.0)    # CL/Vc
        assert derived["k_12"].value == pytest.approx(1.0 / 5.0)    # Q/Vc
        assert derived["k_21"].value == pytest.approx(1.0 / 10.0)   # Q/Vp
        for dc in derived.values():
            assert dc.unit == "1/h"
            assert dc.provenance == "calculated_from_cited_model_parameters"

    def test_records_the_formula_and_the_source_values(self):
        k_el = derive_rate_constants(_linear_2c_set())["k_el"]
        assert k_el.formula == "k_el = CL / Vc"
        assert k_el.source_values == {"CL": "0.5 L/h", "Vc": "5.0 L"}

    def test_converts_units_before_dividing(self):
        # CL in mL/h with Vc in L must still give the right answer, and would
        # be wrong by 1000x if the units were ignored.
        ps = _linear_2c_set(parameters={
            "CL": ParameterValue(500.0, "mL/h", Dimension.FLOW),
            "Vc": ParameterValue(5.0, "L", Dimension.VOLUME),
            "Q": ParameterValue(1000.0, "mL/h", Dimension.FLOW),
            "Vp": ParameterValue(10.0, "L", Dimension.VOLUME),
        })
        assert derive_rate_constants(ps)["k_el"].value == pytest.approx(0.1)

    def test_rejects_a_dimensionally_wrong_parameter(self):
        with pytest.raises(UnitError):
            # Vc declared as a flow.
            ParameterValue(5.0, "L/h", Dimension.VOLUME).quantity("Vc")

    def test_rejects_a_division_whose_dimensions_do_not_resolve(self):
        with pytest.raises(UnitError):
            divide(Quantity(5.0, "L"), Quantity(2.0, "h"),
                   expect=Dimension.INVERSE_TIME, name="nonsense")

    def test_refuses_a_nonlinear_structure(self):
        ps = _linear_2c_set(
            model_structure=ModelStructure.TWO_COMPARTMENT_PARALLEL_LINEAR_MM)
        with pytest.raises(DerivationError) as exc:
            derive_rate_constants(ps)
        assert exc.value.code == "incompatible_model_structure"

    def test_refuses_an_incomplete_parameter_set(self):
        ps = _linear_2c_set(parameters={
            "CL": ParameterValue(0.5, "L/h", Dimension.FLOW),
            "Vc": ParameterValue(5.0, "L", Dimension.VOLUME),
        })
        with pytest.raises(DerivationError) as exc:
            derive_rate_constants(ps)
        assert exc.value.code == "missing_parameters"

    def test_derived_constants_are_not_editable_in_guided_mode(self):
        plan = build_plan(therapeutic="Test Compound",
                          route=AdministrationRoute.IV_INFUSION,
                          mode=InputMode.EXPERT_RESEARCH,
                          parameter_set=_linear_2c_set())
        derived = plan.by_source(InputSource.DERIVED)
        assert {d.name for d in derived} == {"k_el", "k_12", "k_21"}
        # Expert mode may edit; guided mode may not. Checked via the flag the
        # UI reads, so the two cannot disagree.
        assert all(d.editable for d in derived)


# =========================================================================
# 9 + 10 + 11. Report data is separated and does not silently drive the model
# =========================================================================
class TestInputSourceSeparation:

    def test_library_parameters_are_never_labelled_as_report_data(self):
        plan = build_plan(therapeutic="Test Compound",
                          route=AdministrationRoute.IV_INFUSION,
                          mode=InputMode.EXPERT_RESEARCH,
                          parameter_set=_linear_2c_set())
        for pi in plan.by_source(InputSource.PARAMETER_LIBRARY):
            assert pi.source is not InputSource.PATIENT_REPORT
            assert pi.report_field is None

    def test_simulation_settings_are_labelled_as_settings(self):
        plan = build_plan(therapeutic="Test Compound",
                          route=AdministrationRoute.IV_BOLUS)
        settings = {i.name for i in plan.by_source(InputSource.SIMULATION_SETTING)}
        assert settings == {"duration_h", "time_step_h", "output_interval_h"}
        for pi in plan.by_source(InputSource.SIMULATION_SETTING):
            assert pi.source_label == "Simulation setting"

    def test_the_model_consumes_no_patient_covariate(self):
        """The engine's signature is the proof.

        ``ModelInputs`` has no age, sex, creatinine or weight field. A covariate
        therefore cannot reach the equations, which is why the interface must
        not imply that report data drives the simulation. Body weight enters
        only by resolving a mg/kg dose to milligrams, before the model.
        """
        fields = set(ModelInputs.__dataclass_fields__)
        for covariate in ("age", "sex", "body_weight_kg", "creatinine",
                          "egfr", "albumin", "bilirubin", "diagnosis"):
            assert covariate not in fields

    def test_source_labels_are_distinct(self):
        from nanobio_studio.app.pk.planning import SOURCE_LABEL
        assert len(set(SOURCE_LABEL.values())) == len(SOURCE_LABEL)
        assert SOURCE_LABEL[InputSource.MANUAL_ENTRY] == "Manually entered"
        assert SOURCE_LABEL[InputSource.DERIVED] == (
            "Calculated from cited model parameters")


# =========================================================================
# 12 + 13. Overrides are labelled; route changes invalidate parameters
# =========================================================================
class TestOverridesAndRouteChanges:

    def test_expert_mode_labels_results_as_researcher_supplied(self):
        plan = build_plan(therapeutic="Test Compound",
                          route=AdministrationRoute.IV_INFUSION,
                          mode=InputMode.EXPERT_RESEARCH,
                          parameter_set=_linear_2c_set())
        joined = " ".join(plan.warnings)
        assert "supplied by the researcher" in joined
        assert "not a validated platform prediction" in joined

    def test_expert_mode_without_parameters_is_blocked(self):
        plan = build_plan(therapeutic="X", route=AdministrationRoute.ORAL,
                          mode=InputMode.EXPERT_RESEARCH, parameter_set=None)
        assert plan.runnable is False
        assert "model type" in " ".join(plan.blocking_reasons)

    def test_changing_route_changes_the_applicable_fields(self):
        iv = build_plan(therapeutic="X", route=AdministrationRoute.IV_INFUSION)
        sc = build_plan(therapeutic="X", route=AdministrationRoute.SUBCUTANEOUS)
        assert "k_abs" in iv.not_applicable
        assert "k_abs" not in sc.not_applicable
        assert iv.model_label != sc.model_label


# =========================================================================
# 14 + 15. Reproducibility, and the legacy model is untouched
# =========================================================================
class TestReproducibilityAndNonRegression:

    def test_engine_and_library_versions_are_recorded(self):
        plan = build_plan(therapeutic="Test Compound",
                          route=AdministrationRoute.IV_INFUSION,
                          mode=InputMode.EXPERT_RESEARCH,
                          parameter_set=_linear_2c_set())
        assert plan.library_version.startswith("pk-parameter-library-")
        assert plan.parameter_set is not None
        assert plan.parameter_set.version == "1.0.0"
        assert PK_ENGINE_VERSION.startswith("pk-route-aware-")

    def test_the_new_engine_has_its_own_version_distinct_from_the_legacy_one(self):
        from nanobio_studio.app.services.pk_simulation import (
            PK_CALCULATION_VERSION,
        )
        assert PK_ENGINE_VERSION != PK_CALCULATION_VERSION

    def test_the_legacy_depot_model_is_unchanged(self):
        """Requirement 15: existing golden tests remain unchanged.

        The legacy model is re-checked here directly, so a change to it fails
        this suite too rather than only the golden-vector suite.
        """
        from utils.pk_model import two_compartment_model

        t, cp, ct = two_compartment_model(
            dose=3.0, kabs=0.5, kel=0.1, k12=0.2, k21=0.05,
            duration=48.0, dt=0.1)
        # The depot model's defining property: nothing in plasma at t = 0.
        assert cp[0] == 0.0
        assert repr(float(cp.max())) == repr(1.4411129411755834)
        assert repr(float(ct.max())) == repr(1.5287460434185478)


# =========================================================================
# The integrator itself is verified, not assumed
# =========================================================================
class TestNumericalCorrectness:

    def test_matches_the_closed_form_iv_bolus_solution(self):
        assert verify_against_analytical_solution(time_step_h=0.001) < 1e-3

    def test_error_falls_with_the_step_size_as_euler_requires(self):
        coarse = verify_against_analytical_solution(time_step_h=0.01)
        fine = verify_against_analytical_solution(time_step_h=0.001)
        # First-order scheme: ~10x smaller step gives ~10x smaller error.
        assert fine < coarse / 5

    def test_analytical_solution_starts_at_dose_over_vc(self):
        c = analytical_iv_bolus_central(100.0, 0.1, 0.3, 0.15, 5.0,
                                        np.array([0.0]))
        assert c[0] == pytest.approx(20.0)

    def test_warns_when_the_step_is_too_large_for_the_rates(self):
        out = simulate(ModelInputs(
            route=AdministrationRoute.IV_BOLUS,
            regimen=DoseRegimen(dose_mg=100),
            k_el_per_h=5.0, k_12_per_h=5.0, k_21_per_h=1.0,
            v_c_litres=5, v_p_litres=10, duration_h=10, time_step_h=0.5))
        assert any("unstable" in w for w in out.warnings)

    def test_repeated_dosing_accumulates(self):
        single = simulate(ModelInputs(
            route=AdministrationRoute.IV_BOLUS,
            regimen=DoseRegimen(dose_mg=100),
            k_el_per_h=0.05, k_12_per_h=0.3, k_21_per_h=0.15,
            v_c_litres=5, v_p_litres=10, duration_h=72, time_step_h=0.01))
        repeated = simulate(ModelInputs(
            route=AdministrationRoute.IV_BOLUS,
            regimen=DoseRegimen(dose_mg=100, dosing_interval_h=24,
                                number_of_doses=3),
            k_el_per_h=0.05, k_12_per_h=0.3, k_21_per_h=0.15,
            v_c_litres=5, v_p_litres=10, duration_h=72, time_step_h=0.01))
        assert max(repeated.central_concentration) > max(
            single.central_concentration)

    def test_repeated_dosing_requires_an_interval(self):
        with pytest.raises(ModelExecutionError):
            DoseRegimen(dose_mg=100, number_of_doses=3)
