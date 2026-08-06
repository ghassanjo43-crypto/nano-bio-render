"""Deterministic tests for the Phase 2 Step 1 corrections.

Covers DECISION 5 (DEFECT-D8), DECISION 6 (DEFECT-D10), DECISION 7 (DEFECT-D6/D7),
DEFECT-D9 and DEFECT-D11.

These are hand-written behavioural assertions, complementary to the golden-vector
diff in ``tests/golden_vectors/``. They state the *intent* of each decision, so a
future change that satisfies the vector diff but violates the decision still fails.

Nothing here writes to a real application database.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ===========================================================================
# DECISION 5 / DEFECT-D8 -- manufacturing_complexity
# ===========================================================================


class TestDecision5ManufacturingComplexity:
    """0-2 integer count over normalised inputs; never raw string truthiness."""

    @pytest.mark.parametrize(
        "peg, ligand, expected",
        [
            (False, "None", 0),      # neither modification
            (True, "None", 1),       # PEG only
            (False, "GalNAc", 1),    # ligand only
            (True, "GalNAc", 2),     # both
        ],
    )
    def test_all_four_presence_combinations(self, peg, ligand, expected):
        """DECISION 5 requirement 4: cover all four PEG/ligand combinations."""
        from engine.input_normalization import manufacturing_complexity_count

        assert manufacturing_complexity_count(peg, ligand) == expected

    def test_result_is_always_an_int_in_range(self):
        from engine.input_normalization import (MANUFACTURING_COMPLEXITY_RANGE,
                                                manufacturing_complexity_count)

        lo, hi = MANUFACTURING_COMPLEXITY_RANGE
        for peg in (True, False, None, "", "PEG (Stealth)", ["PEG (Stealth)"], []):
            for lig in ("GalNAc", "None", "", None, "n/a", "  Transferrin  "):
                v = manufacturing_complexity_count(peg, lig)
                assert isinstance(v, int) and not isinstance(v, bool)
                assert lo <= v <= hi

    @pytest.mark.parametrize(
        "sentinel", ["None", "none", "NONE", " None ", "", "   ", "n/a", "NA", "-"]
    )
    def test_string_sentinels_are_absent_not_truthy(self, sentinel):
        """The exact hazard DECISION 5 forbids: bool("None") is True."""
        from engine.input_normalization import (has_targeting_ligand,
                                                normalise_ligand)

        assert bool(sentinel) or sentinel == "", "sanity: these are truthy strings"
        assert normalise_ligand(sentinel) is None
        assert has_targeting_ligand(sentinel) is False

    @pytest.mark.parametrize("ligand", ["GalNAc", " Transferrin ", "RGD Peptide"])
    def test_real_ligands_are_present_and_trimmed(self, ligand):
        from engine.input_normalization import (has_targeting_ligand,
                                                normalise_ligand)

        assert has_targeting_ligand(ligand) is True
        assert normalise_ligand(ligand) == ligand.strip()

    def test_none_is_the_canonical_absent_representation(self):
        """DECISION 5 requirement 2: canonical null, not the string 'None'."""
        from engine.input_normalization import normalise_ligand

        assert normalise_ligand(None) is None
        assert normalise_ligand("None") is None
        assert normalise_ligand("None") is normalise_ligand(None)

    def test_indicator_is_described_without_overclaiming(self):
        """DECISION 5: must not be described as validated/approval/success."""
        from engine.input_normalization import (MANUFACTURING_COMPLEXITY_BASIS,
                                                manufacturing_complexity_count)

        assert MANUFACTURING_COMPLEXITY_BASIS == (
            "Rule-based manufacturing complexity indicator")
        text = (MANUFACTURING_COMPLEXITY_BASIS + " "
                + (manufacturing_complexity_count.__doc__ or "")).lower()
        for forbidden in ("experimentally validated", "clinically validated",
                          "approval probability", "guarantees"):
            assert forbidden not in text.replace("not a probability", "")

    def test_regulatory_engine_no_longer_raises(self):
        """DEFECT-D8 was an unconditional TypeError."""
        from config.disease_profiles import get_disease_profile
        from engine.disease_fit import DiseaseFilEngine
        from engine.mechanistic_engine import MechanisticEngine
        from engine.regulatory_engine import RegulatoryEngine
        from engine.safety_engine import SafetyEngine
        from models.scientific_assessment import TrialDesignInputs

        for peg in (True, False):
            for lig in ("GalNAc", "None"):
                di = TrialDesignInputs(case_id="t", disease_code="HCC-S",
                                       peg_surface_coating=peg,
                                       targeting_ligand=lig)
                prof = get_disease_profile("HCC-S")
                mech = MechanisticEngine.compute_all_predictions(di, prof)
                saf = SafetyEngine.assess_safety_profile(di)
                fit = DiseaseFilEngine.assess_disease_fit(di, prof)
                reg = RegulatoryEngine.assess_regulatory_position(
                    di, prof, mech, saf, fit)
                assert reg.manufacturing_complexity == (
                    int(peg) + int(lig != "None"))

    def test_calculation_is_versioned(self):
        """DECISION 5 requirement 5."""
        from engine.regulatory_engine import RegulatoryEngine

        assert RegulatoryEngine.CALCULATION_VERSION == "2.0.0"

    def test_regulatory_category_uses_normalised_ligand_presence(self):
        """Documented language change under DECISION 5 requirement 8.

        Previously used raw truthiness, so an untargeted design was classified as
        a Combination Product because the string "None" is truthy.
        """
        from engine.regulatory_engine import RegulatoryEngine
        from models.scientific_assessment import TrialDesignInputs

        untargeted = TrialDesignInputs(case_id="t", disease_code="HCC-S",
                                       targeting_ligand="None")
        targeted = TrialDesignInputs(case_id="t", disease_code="HCC-S",
                                     targeting_ligand="GalNAc")

        assert "Combination Product" not in (
            RegulatoryEngine._determine_regulatory_category(untargeted))
        assert "Combination Product" in (
            RegulatoryEngine._determine_regulatory_category(targeted))


# ===========================================================================
# DECISION 6 / DEFECT-D10 -- disease-fit ceiling and withheld verdict
# ===========================================================================


class TestDecision6DiseaseFitVerdict:

    def test_field_name_error_is_fixed_everywhere(self):
        """DECISION 6.4. Five live occurrences existed, not one."""
        for rel in ("engine/regulatory_engine.py", "engine/mechanistic_engine.py",
                    "reports/scientific_report_generator.py"):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            live = [ln for ln in text.splitlines()
                    if "disease_profile.name" in ln
                    and not ln.lstrip().startswith("#")]
            assert not live, f"{rel} still reads disease_profile.name: {live}"

    def test_disease_profile_has_no_name_attribute(self):
        """Guards the assumption behind the fix."""
        from config.disease_profiles import get_disease_profile

        p = get_disease_profile("HCC-S")
        assert hasattr(p, "disease_name")
        assert not hasattr(p, "name")

    def test_favourable_verdict_is_disabled(self):
        """DECISION 6.5: stays disabled pending scientific calibration."""
        from engine.regulatory_engine import RegulatoryEngine

        assert RegulatoryEngine.FAVOURABLE_VERDICT_ENABLED is False

    def test_threshold_was_not_lowered(self):
        """DECISION 6.2: do not silently lower the threshold."""
        from engine.disease_fit import DiseaseFilEngine
        from engine.regulatory_engine import RegulatoryEngine

        assert RegulatoryEngine.DISEASE_FIT_FAVOURABLE_THRESHOLD == 70.0
        assert DiseaseFilEngine.FAVOURABLE_VERDICT_THRESHOLD == 70.0

    def test_ceiling_still_below_threshold_reachability_sweep(self):
        """DECISION 6.9: boundary and reachability test.

        Re-runs the sweep. If a future change raises fit above the threshold, the
        favourable branch becomes reachable and this must be reviewed rather than
        silently accepted.
        """
        from config.disease_profiles import get_disease_profile
        from engine.disease_fit import DiseaseFilEngine
        from models.scientific_assessment import TrialDesignInputs

        best = 0.0
        best_at = None
        for code in ("HCC-S", "PDAC-I"):
            prof = get_disease_profile(code)
            for size in (60.0, 70.0, 80.0, 90.0, 100.0, 120.0, 150.0):
                for charge in (-10.0, -5.0, 0.0, 5.0):
                    for peg in (True, False):
                        for pegd in (0.0, 5.0, 10.0, 20.0):
                            for lig in ("GalNAc", "Transferrin", "RGD Peptide",
                                        "None"):
                                di = TrialDesignInputs(
                                    case_id="sweep", disease_code=code,
                                    nanoparticle_size_nm=size,
                                    surface_charge_mv=charge,
                                    peg_surface_coating=peg,
                                    peg_density_percent=pegd,
                                    targeting_ligand=lig,
                                    payload_loading_percent=85.0)
                                s = DiseaseFilEngine.assess_disease_fit(
                                    di, prof).overall_fit_score
                                if s > best:
                                    best, best_at = s, (code, size, charge, peg,
                                                        pegd, lig)

        assert best == pytest.approx(DiseaseFilEngine.OBSERVED_MODEL_CEILING,
                                     abs=0.01), (
            f"documented ceiling changed: now {best} at {best_at}")
        assert best < DiseaseFilEngine.FAVOURABLE_VERDICT_THRESHOLD, (
            "the favourable branch became reachable; a calibration review is "
            "required before enabling it")

    def test_scores_are_still_returned_while_verdict_is_withheld(self):
        """DECISION 6.7: separate valid scores from the verdict."""
        from config.disease_profiles import get_disease_profile
        from engine.disease_fit import DiseaseFilEngine
        from models.scientific_assessment import TrialDesignInputs

        di = TrialDesignInputs(case_id="t", disease_code="HCC-S",
                               nanoparticle_size_nm=80.0,
                               peg_surface_coating=True,
                               targeting_ligand="GalNAc")
        fit = DiseaseFilEngine.assess_disease_fit(di, get_disease_profile("HCC-S"))

        assert isinstance(fit.overall_fit_score, float)
        assert 0.0 <= fit.overall_fit_score <= 100.0
        assert fit.barrier_mitigation_scores, "component scores must remain"
        assert fit.verdict_available is False
        assert fit.verdict_status == "calibration_required"
        assert fit.favourable_verdict_threshold == 70.0
        assert fit.observed_model_ceiling == 68.33

    def test_regulatory_assessment_reports_structured_status(self):
        """DECISION 6.6."""
        from config.disease_profiles import get_disease_profile
        from engine.disease_fit import DiseaseFilEngine
        from engine.mechanistic_engine import MechanisticEngine
        from engine.regulatory_engine import RegulatoryEngine
        from engine.safety_engine import SafetyEngine
        from models.scientific_assessment import TrialDesignInputs

        di = TrialDesignInputs(case_id="t", disease_code="HCC-S")
        prof = get_disease_profile("HCC-S")
        reg = RegulatoryEngine.assess_regulatory_position(
            di, prof,
            MechanisticEngine.compute_all_predictions(di, prof),
            SafetyEngine.assess_safety_profile(di),
            DiseaseFilEngine.assess_disease_fit(di, prof))

        assert reg.verdict_available is False
        assert reg.verdict_status == "calibration_required"
        assert "uncalibrated" in reg.verdict_status_detail.lower()

    def test_no_regulatory_approval_likelihood_language(self):
        """DECISION 6.10."""
        from config.disease_profiles import get_disease_profile
        from engine.disease_fit import DiseaseFilEngine
        from engine.mechanistic_engine import MechanisticEngine
        from engine.regulatory_engine import RegulatoryEngine
        from engine.safety_engine import SafetyEngine
        from models.scientific_assessment import TrialDesignInputs

        di = TrialDesignInputs(case_id="t", disease_code="HCC-S")
        prof = get_disease_profile("HCC-S")
        reg = RegulatoryEngine.assess_regulatory_position(
            di, prof,
            MechanisticEngine.compute_all_predictions(di, prof),
            SafetyEngine.assess_safety_profile(di),
            DiseaseFilEngine.assess_disease_fit(di, prof))

        blob = " ".join([reg.verdict_status_detail,
                         reg.detailed_regulatory_narrative or "",
                         reg.manufacturing_complexity_basis]).lower()
        for forbidden in ("approval probability", "likelihood of approval",
                          "will be approved", "guaranteed approval"):
            assert forbidden not in blob


# ===========================================================================
# Step 1 item 7 -- restored execution
# ===========================================================================


class TestRestoredExecution:
    """RegulatoryEngine, ConfidenceEngine and ScientificReportGenerator run."""

    @pytest.fixture(scope="class")
    def chain(self):
        from config.disease_profiles import get_disease_profile
        from engine.disease_fit import DiseaseFilEngine
        from engine.manufacturing_engine import ManufacturingEngine
        from engine.mechanistic_engine import MechanisticEngine
        from engine.safety_engine import SafetyEngine
        from models.scientific_assessment import TrialDesignInputs

        di = TrialDesignInputs(case_id="chain", disease_code="HCC-S",
                               nanoparticle_size_nm=100.0,
                               peg_surface_coating=True,
                               peg_density_percent=5.0,
                               targeting_ligand="GalNAc",
                               payload_loading_percent=85.0)
        prof = get_disease_profile("HCC-S")
        return {
            "di": di, "prof": prof,
            "mech": MechanisticEngine.compute_all_predictions(di, prof),
            "saf": SafetyEngine.assess_safety_profile(di),
            "fit": DiseaseFilEngine.assess_disease_fit(di, prof),
            "mfg": ManufacturingEngine.assess_manufacturability(di),
        }

    def test_regulatory_engine_executes(self, chain):
        from engine.regulatory_engine import RegulatoryEngine
        from models.scientific_assessment import RegulatoryAssessment

        reg = RegulatoryEngine.assess_regulatory_position(
            chain["di"], chain["prof"], chain["mech"], chain["saf"], chain["fit"])
        assert isinstance(reg, RegulatoryAssessment)
        assert reg.key_regulatory_assertions

    def test_confidence_engine_executes(self, chain):
        from engine.confidence_engine import ConfidenceEngine
        from engine.regulatory_engine import RegulatoryEngine
        from models.scientific_assessment import ConfidenceEvidenceProfile

        reg = RegulatoryEngine.assess_regulatory_position(
            chain["di"], chain["prof"], chain["mech"], chain["saf"], chain["fit"])
        conf = ConfidenceEngine.calculate_confidence_profile(
            chain["mech"], chain["saf"], chain["fit"], chain["mfg"], reg)
        assert isinstance(conf, ConfidenceEvidenceProfile)
        assert 0.0 <= conf.overall_scientific_confidence <= 1.0

    def test_scientific_report_generator_executes(self, chain):
        from models.scientific_assessment import ScientificReport
        from reports.scientific_report_generator import ScientificReportGenerator

        rep = ScientificReportGenerator().generate_full_report(
            chain["di"], disease_code="HCC-S", trial_id="TEST-1")
        assert isinstance(rep, ScientificReport)

    def test_investor_summary_executes(self, chain):
        from reports.scientific_report_generator import ScientificReportGenerator

        gen = ScientificReportGenerator()
        rep = gen.generate_full_report(chain["di"], disease_code="HCC-S",
                                       trial_id="TEST-1")
        summary = gen.generate_investor_summary(rep)
        assert "COMPUTATIONAL RESEARCH-PLANNING ESTIMATES" in summary.upper()

    def test_no_basis_is_invented_for_modules_that_declare_none(self, chain):
        from reports.scientific_report_generator import ScientificReportGenerator

        rep = ScientificReportGenerator().generate_full_report(
            chain["di"], disease_code="HCC-S", trial_id="TEST-1")
        entries = rep.ai_model_transparency.prediction_basis_for_each_module
        assert len(entries) == 6
        undeclared = [e for e in entries if "not declared" in e]
        assert len(undeclared) == 4, (
            "only PredictionBasis declares a basis; the other four must report "
            "absence rather than an invented one")


# ===========================================================================
# DEFECT-D9 -- shared null contract
# ===========================================================================


class TestDefectD9NullContract:

    def test_absent_and_none_are_equivalent_for_every_optional_key(self):
        from core import scoring
        from tests.golden_vectors.inputs import APP_DEFAULT_DESIGN

        base = dict(APP_DEFAULT_DESIGN)
        optional = [k for k in base if k not in scoring.REQUIRED_DESIGN_KEYS]
        assert optional, "sanity"

        for key in optional:
            absent = {k: v for k, v in base.items() if k != key}
            none_valued = dict(base)
            none_valued[key] = None
            for fn in (scoring.compute_impact, scoring.get_recommendations,
                       scoring.regulatory_checklist):
                assert fn(dict(absent)) == fn(dict(none_valued)), (
                    f"{fn.__name__} treats absent {key!r} differently from None")

    def test_the_original_failing_input_no_longer_raises(self):
        from core.scoring import compute_impact, get_recommendations
        from tests.golden_vectors.inputs import SCORING_DESIGNS

        design = SCORING_DESIGNS["none_valued_optionals"]
        compute_impact(dict(design))
        get_recommendations(dict(design))  # used to raise TypeError

    @pytest.mark.parametrize("key", ["Size", "Charge", "Encapsulation"])
    def test_required_keys_still_raise_and_are_not_defaulted(self, key):
        """DEFECT-D9: never silently substitute favourable defaults."""
        from core.scoring import compute_impact
        from tests.golden_vectors.inputs import APP_DEFAULT_DESIGN

        d = {k: v for k, v in APP_DEFAULT_DESIGN.items() if k != key}
        with pytest.raises(KeyError):
            compute_impact(d)

    def test_none_ligand_is_treated_as_absent_not_present(self):
        """A present-but-None ligand used to count as a PRESENT ligand."""
        from core.scoring import compute_impact
        from tests.golden_vectors.inputs import APP_DEFAULT_DESIGN

        no_key = {k: v for k, v in APP_DEFAULT_DESIGN.items() if k != "Ligand"}
        none_val = dict(APP_DEFAULT_DESIGN)
        none_val["Ligand"] = None
        explicit = dict(APP_DEFAULT_DESIGN)
        explicit["Ligand"] = "None"

        assert compute_impact(dict(no_key)) == compute_impact(dict(none_val))
        assert compute_impact(dict(none_val)) == compute_impact(dict(explicit))


# ===========================================================================
# DEFECT-D11 -- import-time database writes
# ===========================================================================


class TestDefectD11ImportSideEffects:

    @pytest.mark.parametrize(
        "module_file, call",
        [
            ("auth.py", "init_db()"),
            ("auth.py", "_reset_admin_session()"),
            ("design_persistence.py", "init_design_db()"),
        ],
    )
    def test_no_module_level_initialisation_calls(self, module_file, call):
        """Import-side-effect regression test (DEFECT-D11 requirement)."""
        text = (REPO_ROOT / module_file).read_text(encoding="utf-8",
                                                   errors="replace")
        offenders = [i for i, ln in enumerate(text.splitlines(), 1)
                     if ln.rstrip() == call]
        assert not offenders, (
            f"{module_file} calls {call} at module scope on line(s) {offenders}; "
            "initialisation must be explicit, not an import side effect")

    def test_importing_auth_does_not_touch_the_real_database(self):
        db = REPO_ROOT / "users.db"
        before = hashlib.sha256(db.read_bytes()).hexdigest() if db.exists() else None
        import auth  # noqa: F401
        after = hashlib.sha256(db.read_bytes()).hexdigest() if db.exists() else None
        assert before == after

    def test_importing_design_persistence_creates_no_database(self, tmp_path,
                                                              monkeypatch):
        monkeypatch.chdir(tmp_path)
        import design_persistence  # noqa: F401

        assert not list(tmp_path.glob("*.db")), (
            "importing design_persistence created a database")

    def test_explicit_initialisation_works_and_is_idempotent(self, tmp_path):
        import auth

        original = auth.DB_PATH
        try:
            auth.DB_PATH = str(tmp_path / "iso_users.db")
            auth.reset_initialization_state()
            auth.initialize_database()
            assert (tmp_path / "iso_users.db").exists()
            auth.initialize_database()  # must not raise
        finally:
            auth.DB_PATH = original
            auth.reset_initialization_state()

    def test_design_persistence_lazy_init_uses_the_configured_path(self, tmp_path):
        import design_persistence as dp

        original = dp.DB_PATH
        try:
            dp.DB_PATH = tmp_path / "iso_designs.db"
            dp.reset_initialization_state()
            assert dp.get_user_designs("nobody") == []
            assert (tmp_path / "iso_designs.db").exists()
        finally:
            dp.DB_PATH = original
            dp.reset_initialization_state()


# ===========================================================================
# DECISION 7 -- AI Co-Designer quarantine
# ===========================================================================


class TestDecision7AiCoDesignerQuarantine:

    LIVE_PAGE = REPO_ROOT / "pages" / "7_AI_Co_Designer.py"
    QUARANTINED = (REPO_ROOT / "legacy_streamlit" / "quarantined"
                   / "7_AI_Co_Designer.legacy.py")

    def _executable_source(self) -> str:
        """Page source minus comments and the module docstring."""
        import ast

        text = self.LIVE_PAGE.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
        if (tree.body and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)):
            start = tree.body[0].end_lineno
        else:
            start = 0
        lines = text.splitlines()[start:]
        return "\n".join(ln for ln in lines if not ln.lstrip().startswith("#"))

    @pytest.mark.parametrize(
        "value", ["94.2", "91.5", "89.8", "87.3", "84.9"])
    def test_fabricated_candidate_scores_are_gone(self, value):
        """DECISION 7.1/7.2."""
        assert value not in self._executable_source(), (
            f"fabricated optimisation score {value} is still rendered")

    @pytest.mark.parametrize(
        "value", ["387 / 500", "387/500", "2026-03-17 15:30:45 UTC"])
    def test_fabricated_audit_trail_values_are_gone(self, value):
        """The fabricated audit trail is the most serious of these."""
        assert value not in self._executable_source()

    def test_page_renders_no_result_tables_or_metrics(self):
        src = self._executable_source()
        for token in ("pd.DataFrame", "st.metric", "st.bar_chart",
                      "st.line_chart", "st.dataframe"):
            assert token not in src, f"page still renders results via {token}"

    def test_page_declares_itself_not_operational(self):
        """DECISION 7.5."""
        text = self.LIVE_PAGE.read_text(encoding="utf-8", errors="replace")
        assert "not yet operational" in text.lower()

    def test_no_rationale_is_generated(self):
        """DECISION 7.3: no 'why suggested' text without a real run."""
        src = self._executable_source()
        assert "Why these materials" not in src
        assert "why these were suggested" not in src.lower()

    def test_original_is_preserved_as_labelled_synthetic_data(self):
        """DECISION 7.4/7.6: preserved, labelled, and never routable."""
        assert self.QUARANTINED.exists(), "original page must be preserved"
        head = self.QUARANTINED.read_text(encoding="utf-8",
                                          errors="replace")[:2500].upper()
        assert "QUARANTINED SYNTHETIC DEMONSTRATION DATA" in head
        assert "DO NOT EXECUTE" in head
        assert "pages" not in self.QUARANTINED.parts[:-1], (
            "quarantined copy must live outside pages/ so Streamlit cannot route "
            "to it")

    def test_ai_engine_is_still_unimportable_so_the_status_is_accurate(self):
        """The page claims the engine is unavailable; verify that is true."""
        with pytest.raises(ModuleNotFoundError):
            import ai_engine  # noqa: F401
