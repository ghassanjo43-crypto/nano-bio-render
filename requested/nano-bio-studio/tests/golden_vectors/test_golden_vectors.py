"""Scientific regression tests against the golden-vector baseline.

How this works
--------------
``capture.build_baseline()`` is re-run in-process and compared field-by-field
against the committed ``baseline.json``. Re-using the capture harness rather than
re-implementing the calls means a vector can never be captured one way and
asserted another.

Two test classes, deliberately different in meaning
---------------------------------------------------
``TestIntendedBehaviour``
    Strict equality. These are the scientific results the migrated backend MUST
    reproduce. A failure here means numerical behaviour changed and must be
    explained before any feature is called migrated.

``TestKnownDefects``
    Marked ``known_defect``. These record current *wrong* behaviour so that its
    removal is detectable. **A failure here is expected and good** once the
    corresponding DECISION is implemented -- it means a defect was fixed, and the
    vector must then be deliberately retired with a note in
    docs/GOLDEN_VECTOR_BASELINE.md. They are NOT target behaviour.

Run only the contract that must hold:

    python -m pytest tests/golden_vectors -m "not known_defect"
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.golden_vectors import capture
from tests.golden_vectors.capture import BASELINE_PATH

# --------------------------------------------------------------------------
# Session-level fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def stored_baseline() -> dict:
    assert BASELINE_PATH.exists(), (
        f"{BASELINE_PATH} is missing. Regenerate with:\n"
        "    python -m tests.golden_vectors.capture"
    )
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def current_baseline() -> dict:
    """Re-capture every vector from the live code, in-process."""
    return capture.build_baseline()


@pytest.fixture(scope="module")
def stored_by_id(stored_baseline) -> dict:
    return {v["id"]: v for v in stored_baseline["vectors"]}


@pytest.fixture(scope="module")
def current_by_id(current_baseline) -> dict:
    return {v["id"]: v for v in current_baseline["vectors"]}


def _ids(baseline_path: Path, classification: str) -> list[str]:
    """Read vector ids straight off disk for collection-time parametrisation."""
    if not baseline_path.exists():  # pragma: no cover
        return []
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    return [v["id"] for v in data["vectors"] if v["classification"] == classification]


INTENDED_IDS = _ids(BASELINE_PATH, "intended")
DEFECT_IDS = _ids(BASELINE_PATH, "known_defect")


def _compare(vector_id: str, stored: dict, current: dict) -> None:
    """Assert one vector reproduces its stored status, exception and output."""
    assert vector_id in current, (
        f"vector {vector_id!r} disappeared: the function it covers no longer runs"
    )
    cur, exp = current[vector_id], stored[vector_id]

    assert cur["status"] == exp["status"], (
        f"{vector_id}: status changed {exp['status']!r} -> {cur['status']!r}\n"
        f"  stored exception: {exp.get('exception')}\n"
        f"  current exception: {cur.get('exception')}"
    )

    if exp["status"] == "raised":
        assert cur["exception"]["type"] == exp["exception"]["type"], (
            f"{vector_id}: exception type changed "
            f"{exp['exception']['type']} -> {cur['exception']['type']}"
        )
        return

    assert cur["output"] == exp["output"], (
        f"{vector_id}: OUTPUT CHANGED.\n"
        f"  expected: {json.dumps(exp['output'], indent=2)[:1200]}\n"
        f"  actual:   {json.dumps(cur['output'], indent=2)[:1200]}"
    )


# --------------------------------------------------------------------------
# The contract that must hold through migration
# --------------------------------------------------------------------------


class TestIntendedBehaviour:
    """Strict scientific equivalence. Failures block a migration claim."""

    def test_baseline_has_intended_vectors(self):
        assert INTENDED_IDS, "no intended vectors collected -- baseline missing?"

    @pytest.mark.parametrize("vector_id", INTENDED_IDS)
    def test_vector_matches_baseline(self, vector_id, stored_by_id, current_by_id):
        _compare(vector_id, stored_by_id, current_by_id)

    def test_no_capture_errors(self, current_baseline):
        assert current_baseline["capture_errors"] == [], (
            "capture reported errors:\n  - "
            + "\n  - ".join(current_baseline["capture_errors"])
        )

    def test_every_section_captured(self, current_baseline):
        failed = {k: v for k, v in current_baseline["sections"].items()
                  if v["status"] != "ok"}
        assert not failed, f"sections failed to capture: {failed}"

    def test_vector_set_is_stable(self, stored_by_id, current_by_id):
        missing = sorted(set(stored_by_id) - set(current_by_id))
        added = sorted(set(current_by_id) - set(stored_by_id))
        assert not missing and not added, (
            f"vector set drifted.\n  missing: {missing[:15]}\n  added: {added[:15]}\n"
            "Regenerate deliberately with: python -m tests.golden_vectors.capture"
        )


class TestDeterminism:
    """The baseline is only meaningful if the functions are reproducible."""

    def test_compute_impact_is_deterministic(self):
        from core.scoring import compute_impact
        from tests.golden_vectors.inputs import APP_DEFAULT_DESIGN

        runs = [compute_impact(dict(APP_DEFAULT_DESIGN)) for _ in range(5)]
        assert all(r == runs[0] for r in runs), f"non-deterministic: {runs}"

    def test_pk_model_is_deterministic(self):
        import numpy as np

        from tests.golden_vectors.inputs import PK_PARAM_SETS
        from utils.pk_model import two_compartment_model

        p = PK_PARAM_SETS["nominal_48h"]
        a = two_compartment_model(**p)
        b = two_compartment_model(**p)
        for x, y in zip(a, b):
            assert np.array_equal(x, y)

    def test_pk_euler_step_is_unchanged(self):
        """dt=0.1 forward Euler IS the model's numerical identity (see audit)."""
        import inspect

        from utils import pk_model

        sig = inspect.signature(pk_model.two_compartment_model)
        assert sig.parameters["dt"].default == 0.1, (
            "The default PK time step changed. Any solver or step-size change is a "
            "versioned scientific change, not an equivalence migration."
        )
        assert sig.parameters["duration"].default == 48.0
        src = inspect.getsource(pk_model.two_compartment_model)
        assert "scipy" not in src, (
            "An ODE solver was introduced into the PK model. This changes results "
            "and must be a separately versioned scientific change."
        )


class TestScoringInvariants:
    """Structural guarantees relied on by the migration, asserted explicitly."""

    def test_compute_impact_output_shape(self):
        from core.scoring import compute_impact
        from tests.golden_vectors.inputs import APP_DEFAULT_DESIGN

        out = compute_impact(dict(APP_DEFAULT_DESIGN))
        assert set(out) == {"Delivery", "Toxicity", "Cost"}
        assert 0.0 <= out["Delivery"] <= 100.0
        assert 0.0 <= out["Toxicity"] <= 10.0
        assert 0.0 <= out["Cost"] <= 100.0

    def test_canonical_weight_set_is_twelve_components(self):
        """DECISION 3A pins compute_impact as the Principal Design Score."""
        import inspect

        from core import scoring

        src = inspect.getsource(scoring.compute_impact)
        for key in ("size", "charge", "encap", "pdi", "hydro", "stability",
                    "targeting", "release", "surface_area", "hydrophobicity",
                    "crystallinity", "coating"):
            assert f"'{key}'" in src, f"weight component {key!r} vanished"

    def test_weights_are_renormalised_when_they_do_not_sum_to_one(self):
        from core.scoring import compute_impact
        from tests.golden_vectors.inputs import (APP_DEFAULT_DESIGN,
                                                 SCORING_WEIGHTS)

        normalised = compute_impact(dict(APP_DEFAULT_DESIGN),
                                    SCORING_WEIGHTS["already_normalised"])
        doubled = compute_impact(dict(APP_DEFAULT_DESIGN),
                                 SCORING_WEIGHTS["unnormalised_sums_to_2"])
        assert normalised == doubled, (
            "core/scoring.py:167-170 re-normalises weights; doubling every weight "
            "must not change the result."
        )

    def test_missing_required_keys_raise_rather_than_silently_default(self):
        from core.scoring import compute_impact
        from tests.golden_vectors.inputs import SCORING_ERROR_DESIGNS

        for name, design in SCORING_ERROR_DESIGNS.items():
            with pytest.raises(KeyError):
                compute_impact(dict(design))


class TestDatabaseIsolation:
    """Prove the suite never touched a real application database."""

    def test_no_real_database_was_touched(self, repo_db_snapshot, current_baseline):
        from tests.conftest import REPO_ROOT, _snapshot_databases

        after = _snapshot_databases(REPO_ROOT)
        changed = {name: (repo_db_snapshot[name], after[name])
                   for name in after if repo_db_snapshot[name] != after[name]}
        assert not changed, (
            "a real database was created or modified by the test run: "
            f"{ {k: ('absent' if v[0] is None else 'changed') for k, v in changed.items()} }"
        )

    def test_leak_detector_actually_detects_a_leak(self, tmp_path):
        """Self-test for the guard above.

        An earlier version of this fixture was lazily evaluated and snapshotted
        *after* a leak had occurred, reporting a false pass. This proves the
        comparison logic flags both a newly created and a mutated database.
        """
        from tests.conftest import _snapshot_databases

        before = _snapshot_databases(tmp_path)
        assert before["nano_bio.db"] is None

        (tmp_path / "nano_bio.db").write_bytes(b"leaked")
        after_create = _snapshot_databases(tmp_path)
        assert after_create["nano_bio.db"] is not None
        assert after_create != before, "detector missed a newly created database"

        (tmp_path / "nano_bio.db").write_bytes(b"leaked-and-then-modified")
        after_modify = _snapshot_databases(tmp_path)
        assert after_modify != after_create, "detector missed a content change"

    def test_snapshot_is_taken_at_import_time_not_lazily(self):
        """The snapshot must predate every test, or it proves nothing."""
        from tests import conftest

        assert hasattr(conftest, "_DB_SNAPSHOT_AT_SESSION_START"), (
            "the session-start snapshot must be a module-level constant; a "
            "lazily-evaluated fixture cannot detect a leak that already happened"
        )

    def test_trial_registry_writes_only_to_isolated_path(self, patch_legacy_db_paths):
        import modules.trial_registry as tr

        tid = tr.TrialIDGenerator.generate_trial_id("hcc_s", 100)
        assert tid.startswith("TRIAL-HCC-S-NP100-")
        created = list(patch_legacy_db_paths.glob("*.db"))
        assert created, "expected the isolated directory to receive the db file"
        assert all(p.parent == patch_legacy_db_paths for p in created)


# --------------------------------------------------------------------------
# Known defects: recorded, NOT endorsed
# --------------------------------------------------------------------------


@pytest.mark.known_defect
class TestKnownDefects:
    """Current wrong behaviour, pinned so its removal is visible.

    A failure in this class is the *expected* outcome of implementing DECISION 1
    or DECISION 2. When one fails because it was fixed, retire the vector
    deliberately and record it in docs/GOLDEN_VECTOR_BASELINE.md.
    """

    def test_baseline_has_defect_vectors(self):
        assert DEFECT_IDS

    @pytest.mark.parametrize("vector_id", DEFECT_IDS)
    def test_defect_still_present(self, vector_id, stored_by_id, current_by_id):
        _compare(vector_id, stored_by_id, current_by_id)

    def test_d1_disease_fallback_is_silent(self):
        """DEFECT-D1: unsupported codes return HCC-S with no error or flag."""
        from config.disease_profiles import get_disease_profile

        for code in ("Triple-Negative (ER-, PR-, HER2-)", "Lung Cancer", "", "HCC-L"):
            p = get_disease_profile(code)
            assert p.disease_code == "HCC-S", (
                "DEFECT-D1 changed. If DECISION 1 was implemented, this vector "
                "should now be retired and replaced by an unsupported-model "
                "assertion."
            )

    def test_d5_no_ml_model_loads(self):
        """DEFECT-D5: heuristics are returned under an ML label."""
        import logging

        logging.disable(logging.CRITICAL)
        try:
            from components.ml_predictor import MLPredictor

            status = MLPredictor(model_dir="models").load_models()
        finally:
            logging.disable(logging.NOTSET)
        assert status == {"toxicity": False, "uptake": False,
                          "particle_size": False}, (
            "DEFECT-D5 changed -- a model now loads. Update the baseline and "
            "re-examine every prediction vector, which was heuristic-derived."
        )

    def test_d7_ai_engine_unimportable(self):
        """DEFECT-D7: the optimiser package cannot be imported."""
        with pytest.raises(ModuleNotFoundError):
            import ai_engine  # noqa: F401

    # RETIRED 2026-07-30 (Phase 2 Step 1): test_d8_regulatory_engine_always_raises
    # -------------------------------------------------------------------------
    # This asserted that RegulatoryEngine.assess_regulatory_position() raises
    # TypeError unconditionally. DECISION 5 corrected DEFECT-D8, so the assertion
    # became false -- the desired outcome. It is retired rather than deleted
    # silently; the replacement coverage lives in
    # tests/test_step1_corrections.py::TestDecision5ManufacturingComplexity and
    # ::TestRestoredExecution, and the pre-correction evidence is preserved in
    # tests/golden_vectors/baseline_step0_2026-07-30_legacy.json.
    # See docs/GOLDEN_VECTOR_BASELINE.md section 6.

    def test_d10_disease_fit_cannot_exceed_seventy(self):
        """DEFECT-D10: the '> 70' regulatory branch is unreachable."""
        from config.disease_profiles import get_disease_profile
        from engine.disease_fit import DiseaseFilEngine
        from models.scientific_assessment import TrialDesignInputs

        best = 0.0
        for code in ("HCC-S", "PDAC-I"):
            prof = get_disease_profile(code)
            for size in (60.0, 80.0, 100.0, 120.0):
                for charge in (-10.0, 0.0, 5.0):
                    for peg in (True, False):
                        for lig in ("GalNAc", "Transferrin", "None"):
                            di = TrialDesignInputs(
                                case_id="d10", disease_code=code,
                                nanoparticle_size_nm=size,
                                surface_charge_mv=charge,
                                peg_surface_coating=peg,
                                peg_density_percent=5.0,
                                targeting_ligand=lig,
                                payload_loading_percent=85.0)
                            best = max(best, DiseaseFilEngine.assess_disease_fit(
                                di, prof).overall_fit_score)
        assert best <= 70.0, (
            f"disease fit now reaches {best}, so regulatory_engine.py:216 becomes "
            "reachable and will raise AttributeError on disease_profile.name."
        )

    # RETIRED 2026-07-30 (Phase 2 Step 1):
    # test_d9_get_recommendations_rejects_none_that_compute_impact_accepts
    # -------------------------------------------------------------------------
    # This asserted that get_recommendations() raises TypeError on an input that
    # compute_impact() accepts. DEFECT-D9 was corrected: the two functions now
    # share one null contract, so the assertion became false -- the desired
    # outcome. Replacement coverage, which is strictly stronger (21 optional keys
    # x 3 functions), lives in
    # tests/test_step1_corrections.py::TestDefectD9NullContract.
    # See docs/GOLDEN_VECTOR_BASELINE.md section 6.
