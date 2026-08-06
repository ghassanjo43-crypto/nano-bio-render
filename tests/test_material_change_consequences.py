"""What each material-field change actually demands, cell by cell.

Why a table and not a set of prose assertions
---------------------------------------------
The brief names six consequences — recalculation, scientific reassessment,
safety reassessment, new approval, new report, new CRO package — and asks that
each be verified. Written as prose, "a dose change needs a safety opinion"
tests one cell and quietly leaves the other five to whatever the implementation
happens to do. Written as a table, every field pins all six, and a change to
the escalation rule fails at the exact cell it moved.

The escalation is monotonic, and that is a claim worth testing rather than
assuming: a safety reassessment implies everything a scientific one does,
which implies a recalculation. An implementation that got the ordering
backwards would still pass a per-field spot check.

The 14 classifications
----------------------
These are the fields the brief enumerates. `MATERIAL_FIELDS` classifies more
than fourteen — synonyms and neighbouring inputs — and that is deliberate:
covering more than the list is safe, covering less is not. So the fourteen are
pinned by name here, and the wider set is checked for internal consistency.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.services import candidate_versioning as cv  # noqa: E402

#: The brief's fourteen, each with the classification it must carry.
#:
#: Restated here rather than read from `MATERIAL_FIELDS`, on purpose. Reading
#: the table under test and asserting it equals itself proves nothing; this is
#: the independent statement of what the classification should be.
THE_FOURTEEN: dict[str, str] = {
    # Formulation and physical identity — a different material.
    "material": "safety_review",
    "coating": "safety_review",
    "size_nm": "scientific_review",
    "charge_mv": "scientific_review",

    # Targeting and payload — what it is aimed at and what it carries.
    "targeting_ligand": "safety_review",
    "payload": "safety_review",
    "biological_target": "safety_review",
    "sequence": "safety_review",

    # Exposure — the two that most directly decide harm.
    "dose_mg_kg": "safety_review",
    "administration_route": "safety_review",

    # Pharmacokinetics.
    "pk_model": "scientific_review",

    # The rules themselves. A threshold change can flip a conclusion without
    # touching a single measurement, which is why these are on the list.
    "model_version": "scientific_review",
    "ruleset_version": "scientific_review",
    "decision_threshold": "scientific_review",
}

#: demand level -> the six consequences it carries.
#:
#: Every cell stated. A blank would be a cell nobody decided.
EXPECTED: dict[str, dict[str, bool]] = {
    "none": {
        "recalculation": False, "scientific_reassessment": False,
        "safety_reassessment": False, "new_approval": False,
        "new_report": False, "new_cro_package": False,
    },
    "recalculation": {
        "recalculation": True, "scientific_reassessment": False,
        "safety_reassessment": False,
        # True even here. The approval was granted against numbers that no
        # longer describe this formulation, whatever produced the change.
        "new_approval": True,
        "new_report": True, "new_cro_package": False,
    },
    "scientific_review": {
        "recalculation": True, "scientific_reassessment": True,
        "safety_reassessment": False, "new_approval": True,
        "new_report": True, "new_cro_package": False,
    },
    "safety_review": {
        "recalculation": True, "scientific_reassessment": True,
        "safety_reassessment": True, "new_approval": True,
        "new_report": True, "new_cro_package": True,
    },
}


# ===========================================================================
# 1. The fourteen classifications
# ===========================================================================

class TestTheFourteenClassifications:

    def test_there_are_fourteen_of_them(self):
        assert len(THE_FOURTEEN) == 14

    @pytest.mark.parametrize("field,classification",
                             sorted(THE_FOURTEEN.items()))
    def test_each_field_carries_its_classification(self, field,
                                                   classification):
        assert cv.MATERIAL_FIELDS.get(field) == classification, (
            f"{field} is classified {cv.MATERIAL_FIELDS.get(field)!r}, not "
            f"{classification!r}")

    @pytest.mark.parametrize("field", sorted(THE_FOURTEEN))
    def test_none_of_them_is_an_identity_field(self, field):
        """An identity field is correctable in place on a locked version.

        A scientific input on that list would be editable after a simulation
        had run against it, which is the whole failure this prevents.
        """
        assert field not in cv.IDENTITY_FIELDS


# ===========================================================================
# 2. Every consequence of every classification
# ===========================================================================

class TestEveryConsequenceIsStated:

    @pytest.mark.parametrize("field,classification",
                             sorted(THE_FOURTEEN.items()))
    def test_each_field_produces_the_full_consequence_set(self, field,
                                                          classification):
        result = cv.consequence_of_change({field})

        assert result["requires"] == classification, field
        assert result["consequences"] == EXPECTED[classification], field
        assert result["field_classifications"] == {field: classification}

    @pytest.mark.parametrize("demanded", sorted(EXPECTED))
    def test_the_consequence_set_is_complete(self, demanded):
        """No key missing, no key invented."""
        consequences = cv._consequences(demanded)
        assert set(consequences) == set(cv.CONSEQUENCE_KEYS)
        assert consequences == EXPECTED[demanded]

    def test_an_identity_only_change_demands_nothing(self):
        result = cv.consequence_of_change({"name", "description", "label"})
        assert result["requires"] == "none"
        assert result["identity_only"] is True
        assert result["approval_may_carry_forward"] is True
        assert result["consequences"] == EXPECTED["none"]
        assert not any(result["consequences"].values())

    def test_an_unclassified_field_defaults_to_recalculation_not_nothing(self):
        """Default-deny. Treating an unrecognised input as harmless because it
        is not on a list is how a new field silently inherits an approval."""
        result = cv.consequence_of_change({"a_field_added_next_year"})

        assert result["requires"] == "recalculation"
        assert result["consequences"] == EXPECTED["recalculation"]
        assert result["consequences"]["new_approval"] is True
        assert result["field_classifications"] == {
            "a_field_added_next_year": "recalculation"}


# ===========================================================================
# 3. The escalation is monotonic
# ===========================================================================

class TestEscalationIsMonotonic:

    def test_each_level_demands_everything_the_one_below_does(self):
        """A safety reassessment implies a scientific one implies a recalc.

        An implementation with the ordering reversed would still pass a
        per-field spot check, which is why this is asserted as an ordering
        rather than as three unrelated rows.
        """
        order = ["none", "recalculation", "scientific_review", "safety_review"]
        for lower, higher in zip(order, order[1:]):
            for key in cv.CONSEQUENCE_KEYS:
                if EXPECTED[lower][key]:
                    assert EXPECTED[higher][key], (
                        f"{higher} demands less than {lower} for {key}")
                    assert cv._consequences(higher)[key], (
                        f"the implementation lets {higher} demand less than "
                        f"{lower} for {key}")

    def test_the_strongest_demand_wins_in_a_mixed_change(self):
        result = cv.consequence_of_change({"size_nm", "dose_mg_kg"})
        assert result["requires"] == "safety_review"
        assert result["consequences"] == EXPECTED["safety_review"]
        assert result["field_classifications"] == {
            "size_nm": "scientific_review", "dose_mg_kg": "safety_review"}

    def test_a_mixed_identity_and_scientific_change_is_not_identity_only(self):
        """Renaming a candidate while changing its dose is a dose change."""
        result = cv.consequence_of_change({"name", "dose_mg_kg"})
        assert result["identity_only"] is False
        assert result["requires"] == "safety_review"
        assert result["changed_scientific_fields"] == ["dose_mg_kg"]


# ===========================================================================
# 4. The wider classification table is internally consistent
# ===========================================================================

class TestTheWiderTable:

    def test_every_classification_is_a_known_level(self):
        for field, classification in cv.MATERIAL_FIELDS.items():
            assert classification in cv.CONSEQUENCE_ORDER, (
                f"{field} is classified {classification!r}, which is not one "
                f"of {cv.CONSEQUENCE_ORDER}")

    def test_no_field_is_both_identity_and_material(self):
        overlap = set(cv.MATERIAL_FIELDS) & set(cv.IDENTITY_FIELDS)
        assert overlap == set(), (
            f"{overlap} are classified as both correctable labels and "
            f"scientific inputs, so whether they may be edited on a locked "
            f"version depends on which table a caller reads")

    def test_the_table_covers_more_than_the_fourteen(self):
        """Covering more than the brief's list is safe; covering less is not."""
        assert set(THE_FOURTEEN) <= set(cv.MATERIAL_FIELDS)
        assert len(cv.MATERIAL_FIELDS) > len(THE_FOURTEEN)

    @pytest.mark.parametrize("pair", [
        ("coating", "surface_coating"),
        ("ligand", "targeting_ligand"),
        ("dose", "dose_mg_kg"),
        ("route", "administration_route"),
    ])
    def test_synonyms_are_classified_identically(self, pair):
        """A formulation stored under either spelling must demand the same
        thing. Two spellings with two answers is a way through the gate."""
        left, right = pair
        assert cv.MATERIAL_FIELDS[left] == cv.MATERIAL_FIELDS[right], pair


# ===========================================================================
# 5. The consequence travels with the comparison, not just the calculation
# ===========================================================================

class TestConsequenceReachesTheStructuredComparison:

    def test_a_comparison_reports_the_consequence_of_what_changed(self):
        before = cv.canonical_snapshot(
            {"size_nm": 90.0, "dose_mg_kg": 2.0, "coating": "PEG"})
        after = cv.canonical_snapshot(
            {"size_nm": 90.0, "dose_mg_kg": 9.0, "coating": "PEG"})

        changes = cv.compare_snapshots(before, after)
        result = cv.consequence_of_change({c.field for c in changes})

        assert [c.field for c in changes] == ["dose_mg_kg"]
        assert changes[0].is_scientific is True
        assert result["requires"] == "safety_review"
        assert result["consequences"]["new_cro_package"] is True

    def test_a_label_only_comparison_reports_no_consequence(self):
        before = cv.canonical_snapshot({"name": "Alpha", "size_nm": 90.0})
        after = cv.canonical_snapshot({"name": "Alpha revised",
                                       "size_nm": 90.0})

        changes = cv.compare_snapshots(before, after)
        result = cv.consequence_of_change({c.field for c in changes})

        assert [c.field for c in changes] == ["name"]
        assert changes[0].is_scientific is False
        assert result["identity_only"] is True
        assert not any(result["consequences"].values())

    def test_an_added_scientific_field_counts_as_a_change(self):
        """Recording a measurement that was previously absent is a change to
        what the formulation says about itself."""
        before = cv.canonical_snapshot({"size_nm": 90.0})
        after = cv.canonical_snapshot({"size_nm": 90.0, "pdi": 0.18})

        changes = cv.compare_snapshots(before, after)
        assert [(c.field, c.kind) for c in changes] == [("pdi", "added")]

        result = cv.consequence_of_change({c.field for c in changes})
        assert result["requires"] == "scientific_review"
        assert result["consequences"]["new_approval"] is True
