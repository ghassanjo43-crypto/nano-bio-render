"""The Scientific Data Dictionary.

One definition per field, in one place. The rules engine, the API, the frontend
dashboard and the tests all read this module, so a field's units, its accepted
provenance and the areas that depend on it cannot drift apart.

On "valid ranges"
-----------------
Ranges are given **only where a defensible bound exists**, and almost all of
them are definitional rather than empirical: an encapsulation efficiency cannot
exceed 100% because of what a percentage of a whole means; a diameter cannot be
negative. Where no universal scientific range exists — and for most
nanomaterial properties none does — ``valid_range`` is ``None`` and validation
checks type, unit and internal consistency only.

Inventing a "normal" size range for nanoparticles would be worse than useless:
it would reject genuine formulations and lend false authority to the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from .statuses import ReadinessArea, Requirement, ScientificStatus

__all__ = [
    "FieldType",
    "FieldDefinition",
    "DATA_DICTIONARY",
    "DICTIONARY_VERSION",
    "field_definition",
    "fields_for_area",
    "blocking_fields_for_area",
    "all_field_ids",
    "MEASUREMENT_METHOD_CLASSES",
    "method_class",
]

#: Bump when a field is added, removed, or its requirement level changes.
DICTIONARY_VERSION = "data-dictionary-1.0.0"

FieldType = str  # "number" | "text" | "enum" | "boolean"

#: Provenance sets used repeatedly below.
_ANY_STATUS = frozenset(ScientificStatus)
_NO_ILLUSTRATIVE = frozenset(s for s in ScientificStatus
                             if s is not ScientificStatus.ILLUSTRATIVE)
_MEASURABLE = frozenset({
    ScientificStatus.MEASURED, ScientificStatus.EXPERIMENTALLY_DERIVED,
    ScientificStatus.LITERATURE_DERIVED, ScientificStatus.USER_SUPPLIED,
    ScientificStatus.MISSING, ScientificStatus.NOT_APPLICABLE,
})


@dataclass(frozen=True)
class FieldDefinition:
    """Everything the framework knows about one scientific field."""

    id: str
    label: str
    definition: str
    group: str
    data_type: FieldType
    #: Accepted unit strings. Empty for unitless or free-text fields.
    accepted_units: tuple[str, ...] = ()
    #: Inclusive bounds, only where defensible. None means "no universal range".
    valid_range: tuple[float, float] | None = None
    #: Enum members, for enumerated fields.
    choices: tuple[str, ...] = ()
    #: Measurement conditions that materially change the value.
    relevant_conditions: tuple[str, ...] = ()
    #: Provenance types that make sense for this field.
    supported_statuses: frozenset[ScientificStatus] = _ANY_STATUS
    #: Areas that consume this field, and how strongly.
    area_requirements: dict[ReadinessArea, Requirement] = dc_field(
        default_factory=dict)
    #: When a CONDITIONAL requirement applies. Plain language.
    condition: str | None = None
    #: Field ids this one must be consistent with.
    compatibility_rules: tuple[str, ...] = ()
    #: Researcher-facing explanation of why it matters.
    researcher_note: str = ""


def _f(**kwargs) -> FieldDefinition:
    return FieldDefinition(**kwargs)


A = ReadinessArea
R = Requirement

DATA_DICTIONARY: dict[str, FieldDefinition] = {d.id: d for d in [

    # ---------------------------------------------------------------- identity
    _f(id="nanoparticle_class", label="Nanoparticle class",
       definition="The broad materials class the particle belongs to.",
       group="identity", data_type="enum",
       choices=("lipid", "polymeric", "metallic", "inorganic_oxide",
                "protein", "hybrid", "other"),
       supported_statuses=_NO_ILLUSTRATIVE,
       area_requirements={A.STRUCTURAL_VISUALIZATION: R.BLOCKING,
                          A.FORMULATION_ASSESSMENT: R.BLOCKING,
                          A.SAFETY_ASSESSMENT: R.BLOCKING,
                          A.CINEMATIC_ANIMATION: R.BLOCKING},
       researcher_note=
           "Without a recorded class the software cannot tell which physical "
           "model applies. It will not infer one from the picture."),

    _f(id="architecture", label="Architecture",
       definition="Internal organisation of the particle.",
       group="identity", data_type="enum",
       choices=("solid", "core_shell", "liposome", "polymeric", "metallic",
                "silica", "hybrid"),
       supported_statuses=_NO_ILLUSTRATIVE,
       area_requirements={A.STRUCTURAL_VISUALIZATION: R.BLOCKING,
                          A.CINEMATIC_ANIMATION: R.BLOCKING},
       compatibility_rules=("nanoparticle_class",),
       researcher_note=
           "Architecture decides which internal structures may be drawn. A "
           "liposome has a bilayer and an aqueous core; a metallic particle "
           "has neither, and the software must not assume one for the other."),

    _f(id="core_material", label="Core material", group="identity",
       definition="Chemical identity of the particle core.",
       data_type="text", supported_statuses=_NO_ILLUSTRATIVE,
       area_requirements={A.STRUCTURAL_VISUALIZATION: R.OPTIONAL,
                          A.FORMULATION_ASSESSMENT: R.BLOCKING,
                          A.SAFETY_ASSESSMENT: R.BLOCKING}),

    _f(id="shell_material", label="Shell or membrane material",
       group="identity", definition="Chemical identity of the shell or "
       "membrane enclosing the core.", data_type="text",
       supported_statuses=_NO_ILLUSTRATIVE,
       area_requirements={A.STRUCTURAL_VISUALIZATION: R.CONDITIONAL,
                          A.FORMULATION_ASSESSMENT: R.CONDITIONAL},
       condition="Required when the architecture has a distinct shell "
                 "(core–shell, liposome, silica, hybrid, metallic).",
       compatibility_rules=("architecture",)),

    _f(id="coating", label="Coating", group="identity",
       definition="Surface coating applied to the particle.",
       data_type="text",
       area_requirements={A.STRUCTURAL_VISUALIZATION: R.OPTIONAL,
                          A.FORMULATION_ASSESSMENT: R.OPTIONAL,
                          A.PHARMACOKINETIC_MODELLING: R.OPTIONAL}),

    _f(id="functional_groups", label="Functional groups", group="identity",
       definition="Chemical groups presented on the surface.",
       data_type="text",
       area_requirements={A.FORMULATION_ASSESSMENT: R.OPTIONAL}),

    _f(id="peg_linker_identity", label="PEG or linker identity",
       group="identity", definition="Identity of the PEG or linker chemistry.",
       data_type="text",
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required when a targeting ligand is attached via a linker."),

    _f(id="peg_molecular_weight", label="PEG/linker molecular weight",
       group="identity", definition="Molar mass of the PEG or linker.",
       data_type="number", accepted_units=("g/mol", "kDa"),
       valid_range=(0.0, float("inf")),
       area_requirements={A.BIOLOGICAL_TARGETING: R.OPTIONAL}),

    _f(id="manufacturing_method", label="Manufacturing or formulation method",
       group="identity", definition="How the particle was produced.",
       data_type="text",
       area_requirements={A.FORMULATION_ASSESSMENT: R.BLOCKING,
                          A.SAFETY_ASSESSMENT: R.OPTIONAL},
       researcher_note=
           "Two particles with identical dimensions made by different methods "
           "are not interchangeable."),

    _f(id="material_purity", label="Material purity", group="identity",
       definition="Purity of the starting material or final product.",
       data_type="number", accepted_units=("%",), valid_range=(0.0, 100.0),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.OPTIONAL,
                          A.SAFETY_ASSESSMENT: R.CONDITIONAL},
       condition="Required for a safety assessment of a metallic or inorganic "
                 "particle, where residual precursors matter."),

    _f(id="batch_identifier", label="Batch identifier", group="identity",
       definition="Batch or lot the recorded measurements belong to.",
       data_type="text",
       area_requirements={A.FORMULATION_ASSESSMENT: R.OPTIONAL},
       researcher_note=
           "Measurements from different batches are different materials. "
           "Recording the batch is what makes them comparable."),

    # ------------------------------------------------------ characterization
    _f(id="physical_diameter", label="Primary physical diameter",
       group="characterization",
       definition="Core physical diameter measured by imaging (TEM, SEM, AFM).",
       data_type="number", accepted_units=("nm", "um"),
       valid_range=(0.0, float("inf")),
       relevant_conditions=("imaging method", "sample preparation", "n counted"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.STRUCTURAL_VISUALIZATION: R.BLOCKING,
                          A.FORMULATION_ASSESSMENT: R.BLOCKING,
                          A.CINEMATIC_ANIMATION: R.BLOCKING},
       compatibility_rules=("hydrodynamic_diameter",),
       researcher_note=
           "A physical diameter from microscopy and a hydrodynamic diameter "
           "from DLS are different quantities. They are stored separately and "
           "are never substituted for one another."),

    _f(id="hydrodynamic_diameter", label="Hydrodynamic diameter",
       group="characterization",
       definition="Diameter including the solvation layer, from DLS or NTA.",
       data_type="number", accepted_units=("nm", "um"),
       valid_range=(0.0, float("inf")),
       relevant_conditions=("medium", "pH", "temperature", "ionic strength",
                            "weighting basis"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.CONDITIONAL,
                          A.PHARMACOKINETIC_MODELLING: R.OPTIONAL},
       condition="Required when a dispersion-dependent property is claimed.",
       compatibility_rules=("physical_diameter", "size_distribution_basis"),
       researcher_note=
           "A hydrodynamic diameter is meaningless without its medium and "
           "weighting basis. The same sample gives different numbers in water "
           "and in serum."),

    _f(id="size_distribution_basis", label="Size-distribution basis",
       group="characterization",
       definition="Whether the reported distribution is intensity-, volume- or "
                  "number-weighted.",
       data_type="enum",
       choices=("intensity_weighted", "volume_weighted", "number_weighted"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.CONDITIONAL},
       condition="Required whenever a hydrodynamic diameter or PDI is recorded.",
       compatibility_rules=("hydrodynamic_diameter", "pdi"),
       researcher_note=
           "Intensity-, volume- and number-weighted distributions of the same "
           "sample differ, often substantially. Comparing them without the "
           "basis recorded is not a comparison."),

    _f(id="pdi", label="Polydispersity index", group="characterization",
       definition="Breadth of the size distribution.", data_type="number",
       accepted_units=("",), valid_range=(0.0, 1.0),
       relevant_conditions=("medium", "weighting basis"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.OPTIONAL},
       compatibility_rules=("size_distribution_basis",)),

    _f(id="morphology", label="Morphology and shape",
       group="characterization",
       definition="Observed particle shape.", data_type="text",
       relevant_conditions=("imaging method",),
       supported_statuses=_MEASURABLE,
       area_requirements={A.STRUCTURAL_VISUALIZATION: R.CONDITIONAL,
                          A.CINEMATIC_ANIMATION: R.BLOCKING},
       condition="Required before a non-spherical geometry may be drawn.",
       researcher_note=
           "With no recorded morphology the builder draws a sphere and labels "
           "it illustrative. It will not infer a shape."),

    _f(id="surface_area", label="Surface area", group="characterization",
       definition="Specific or accessible surface area.", data_type="number",
       accepted_units=("nm2", "m2/g"), valid_range=(0.0, float("inf")),
       relevant_conditions=("method (BET, geometric)",),
       supported_statuses=_MEASURABLE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required to convert a per-area ligand density into a count."),

    _f(id="coating_thickness", label="Shell or coating thickness",
       group="characterization",
       definition="Thickness of the shell or coating layer.",
       data_type="number", accepted_units=("nm",),
       valid_range=(0.0, float("inf")),
       supported_statuses=_MEASURABLE,
       area_requirements={A.STRUCTURAL_VISUALIZATION: R.CONDITIONAL},
       condition="Required to draw a core and shell at their true relative "
                 "dimensions.",
       compatibility_rules=("physical_diameter",),
       researcher_note=
           "Twice the coating thickness must be less than the total diameter, "
           "or no core remains."),

    _f(id="density", label="Density", group="characterization",
       definition="Material density.", data_type="number",
       accepted_units=("g/cm3", "kg/m3"), valid_range=(0.0, float("inf")),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.OPTIONAL}),

    _f(id="porosity", label="Porosity", group="characterization",
       definition="Pore volume or porous fraction.", data_type="number",
       accepted_units=("%", "cm3/g", "nm3"), valid_range=(0.0, float("inf")),
       relevant_conditions=("method",), supported_statuses=_MEASURABLE,
       area_requirements={A.STRUCTURAL_VISUALIZATION: R.CONDITIONAL},
       condition="Required before a mesoporous structure may be drawn.",
       researcher_note=
           "Porosity is never inferred from the material. A silica particle is "
           "drawn solid unless porosity is recorded."),

    _f(id="aggregation_state", label="Aggregation or agglomeration",
       group="characterization",
       definition="Observed aggregation behaviour in a stated medium.",
       data_type="text",
       relevant_conditions=("medium", "time", "temperature"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.OPTIONAL,
                          A.PHARMACOKINETIC_MODELLING: R.OPTIONAL}),

    _f(id="crystallinity", label="Crystallinity", group="characterization",
       definition="Crystalline phase or degree of crystallinity.",
       data_type="text", relevant_conditions=("method (XRD, SAED)",),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.OPTIONAL}),

    _f(id="zeta_potential", label="Zeta potential",
       group="characterization",
       definition="Electrokinetic potential at the slipping plane.",
       data_type="number", accepted_units=("mV",),
       relevant_conditions=("medium", "pH", "ionic strength", "temperature"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.BLOCKING,
                          A.STRUCTURAL_VISUALIZATION: R.OPTIONAL},
       researcher_note=
           "A zeta potential without its medium and pH cannot be compared with "
           "any other measurement, including a later one of the same sample."),

    # ------------------------------------------------------ payload & surface
    _f(id="payload_identity", label="Payload identity", group="payload",
       definition="Chemical identity of the encapsulated or conjugated agent.",
       data_type="text", supported_statuses=_NO_ILLUSTRATIVE,
       area_requirements={A.PHARMACOKINETIC_MODELLING: R.BLOCKING,
                          A.SAFETY_ASSESSMENT: R.BLOCKING,
                          A.FORMULATION_ASSESSMENT: R.CONDITIONAL},
       condition="Required whenever the particle carries a payload."),

    _f(id="payload_molecular_weight", label="Payload molecular weight",
       group="payload", definition="Molar mass of the payload.",
       data_type="number", accepted_units=("g/mol", "kDa"),
       valid_range=(0.0, float("inf")), supported_statuses=_MEASURABLE,
       area_requirements={A.PHARMACOKINETIC_MODELLING: R.CONDITIONAL},
       condition="Required to convert a payload mass into a molecule count.",
       researcher_note=
           "Encapsulation efficiency alone cannot give a molecule count. It is "
           "the fraction of offered drug that was encapsulated, and says "
           "nothing about how much was offered or what it weighs."),

    _f(id="loading_capacity", label="Loading capacity", group="payload",
       definition="Mass of payload per mass of carrier.", data_type="number",
       accepted_units=("%", "mg/mg", "ug/mg"), valid_range=(0.0, float("inf")),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.OPTIONAL,
                          A.PHARMACOKINETIC_MODELLING: R.CONDITIONAL},
       condition="Required, with the molecular weight, to estimate a payload "
                 "population."),

    _f(id="encapsulation_efficiency", label="Encapsulation efficiency",
       group="payload",
       definition="Fraction of the offered payload that ended up encapsulated.",
       data_type="number", accepted_units=("%",), valid_range=(0.0, 100.0),
       relevant_conditions=("separation method", "assay"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.BLOCKING},
       researcher_note=
           "This is a process yield, not a quantity of drug per particle."),

    _f(id="drug_to_carrier_ratio", label="Drug-to-carrier ratio",
       group="payload", definition="Molar or mass ratio of drug to carrier.",
       data_type="number", accepted_units=("mol/mol", "mg/mg", ""),
       valid_range=(0.0, float("inf")), supported_statuses=_MEASURABLE,
       area_requirements={A.PHARMACOKINETIC_MODELLING: R.CONDITIONAL},
       condition="An alternative route to a payload population."),

    _f(id="free_vs_encapsulated", label="Free versus encapsulated payload",
       group="payload",
       definition="Fraction of payload unencapsulated after purification.",
       data_type="number", accepted_units=("%",), valid_range=(0.0, 100.0),
       supported_statuses=_MEASURABLE,
       area_requirements={A.PHARMACOKINETIC_MODELLING: R.OPTIONAL,
                          A.SAFETY_ASSESSMENT: R.OPTIONAL}),

    _f(id="payload_location", label="Payload location", group="payload",
       definition="Where the payload sits within the carrier.",
       data_type="enum",
       choices=("aqueous_core", "bilayer", "polymer_matrix", "surface_bound",
                "pore_bound", "unspecified"),
       area_requirements={A.STRUCTURAL_VISUALIZATION: R.CONDITIONAL,
                          A.CINEMATIC_ANIMATION: R.BLOCKING},
       condition="Required before payload placement is drawn as fact rather "
                 "than as an illustrative distribution.",
       compatibility_rules=("architecture",)),

    _f(id="release_mechanism", label="Release mechanism", group="payload",
       definition="Mechanism by which payload is released.", data_type="text",
       area_requirements={A.PHARMACOKINETIC_MODELLING: R.OPTIONAL,
                          A.CINEMATIC_ANIMATION: R.CONDITIONAL},
       condition="Required to animate release."),

    _f(id="release_profile_evidence", label="Release-profile evidence",
       group="payload",
       definition="Recorded release kinetics under stated conditions.",
       data_type="text",
       relevant_conditions=("medium", "pH", "temperature", "sink conditions"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.PHARMACOKINETIC_MODELLING: R.OPTIONAL}),

    _f(id="stability_evidence", label="Stability evidence", group="payload",
       definition="Recorded colloidal or chemical stability data.",
       data_type="text",
       relevant_conditions=("medium", "temperature", "duration"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.FORMULATION_ASSESSMENT: R.OPTIONAL,
                          A.SAFETY_ASSESSMENT: R.OPTIONAL}),

    _f(id="degradation_evidence", label="Degradation evidence",
       group="payload", definition="Recorded degradation behaviour.",
       data_type="text", relevant_conditions=("medium", "duration"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.SAFETY_ASSESSMENT: R.BLOCKING},
       researcher_note=
           "Absence of degradation data is missing evidence. It is not "
           "evidence that the material does not degrade."),

    _f(id="ligand_identity", label="Ligand identity", group="surface",
       definition="Identity of the targeting ligand.", data_type="text",
       supported_statuses=_NO_ILLUSTRATIVE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.BLOCKING},
       condition=None),

    _f(id="ligand_density_value", label="Ligand-density value",
       group="surface", definition="Numeric ligand density.",
       data_type="number",
       accepted_units=("per_nm2", "per_particle", "%", "mol_percent",
                       "mass_percent"),
       valid_range=(0.0, float("inf")), supported_statuses=_MEASURABLE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required, with an unambiguous unit, to estimate a ligand "
                 "population.",
       compatibility_rules=("ligand_density_unit",)),

    _f(id="ligand_density_unit", label="Ligand-density unit and denominator",
       group="surface",
       definition="The unit AND the denominator the density is expressed "
                  "against.",
       data_type="enum",
       choices=("per_nm2", "per_particle", "mol_percent_of_lipid",
                "mass_percent_of_carrier", "surface_coverage_fraction",
                "ambiguous_percent"),
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required whenever a ligand-density value is recorded.",
       compatibility_rules=("ligand_density_value",),
       researcher_note=
           "A bare percentage is not a density. It could mean surface "
           "coverage, molar percent of lipid, mass percent of carrier, or "
           "molecules per unit area, and these give different counts. Until "
           "the denominator is recorded no population is estimated."),

    _f(id="ligand_molecular_weight", label="Ligand molecular weight",
       group="surface", definition="Molar mass of the ligand.",
       data_type="number", accepted_units=("g/mol", "kDa"),
       valid_range=(0.0, float("inf")), supported_statuses=_MEASURABLE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required to convert a mass-based density into a count."),

    _f(id="molecular_footprint", label="Molecular footprint", group="surface",
       definition="Cross-sectional area occupied by one ligand.",
       data_type="number", accepted_units=("nm2",),
       valid_range=(0.0, float("inf")), supported_statuses=_MEASURABLE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required to convert fractional surface coverage into a "
                 "count."),

    _f(id="surface_coverage", label="Surface coverage", group="surface",
       definition="Fraction of the surface occupied by grafted species.",
       data_type="number", accepted_units=("%", "fraction"),
       valid_range=(0.0, 100.0), supported_statuses=_MEASURABLE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.OPTIONAL}),

    # ------------------------------------------------------ biological target
    _f(id="target_disease", label="Target cancer or disease",
       group="biological", definition="Disease the study targets.",
       data_type="text", supported_statuses=_NO_ILLUSTRATIVE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.BLOCKING,
                          A.SAFETY_ASSESSMENT: R.OPTIONAL}),

    _f(id="target_tissue", label="Target tissue", group="biological",
       definition="Tissue or organ targeted.", data_type="text",
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required for a tissue-level targeting claim."),

    _f(id="target_receptor", label="Target receptor", group="biological",
       definition="Receptor or antigen the ligand binds.", data_type="text",
       supported_statuses=_NO_ILLUSTRATIVE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.BLOCKING}),

    _f(id="receptor_expression_value", label="Receptor-expression value",
       group="biological",
       definition="Measured expression of the target receptor.",
       data_type="number",
       accepted_units=("receptors_per_cell", "H_score", "IHC_score",
                       "TPM", "fold_change"),
       relevant_conditions=("model system", "assay"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.BLOCKING},
       compatibility_rules=("receptor_expression_unit",),
       researcher_note=
           "A targeting claim without recorded receptor expression is a "
           "hypothesis. The framework will not report targeting readiness "
           "without it."),

    _f(id="receptor_expression_unit", label="Receptor-expression unit",
       group="biological", definition="Unit of the expression measurement.",
       data_type="enum",
       choices=("receptors_per_cell", "H_score", "IHC_score", "TPM",
                "fold_change"),
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required whenever an expression value is recorded.",
       compatibility_rules=("receptor_expression_value",)),

    _f(id="expression_method", label="Expression measurement method",
       group="biological",
       definition="How receptor expression was measured.", data_type="text",
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required whenever an expression value is recorded.",
       researcher_note=
           "An IHC score and a flow-cytometry receptor count are not "
           "interchangeable, and neither converts to the other."),

    _f(id="biological_model", label="Cell line, tissue or biological model",
       group="biological",
       definition="The biological system the evidence comes from.",
       data_type="text", supported_statuses=_NO_ILLUSTRATIVE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.BLOCKING,
                          A.SAFETY_ASSESSMENT: R.CONDITIONAL},
       condition="Required whenever in-vitro or in-vivo evidence is recorded."),

    _f(id="binding_affinity", label="Binding affinity", group="biological",
       definition="Measured affinity of the ligand for its target.",
       data_type="number", accepted_units=("nM", "uM", "pM", "M"),
       valid_range=(0.0, float("inf")),
       relevant_conditions=("assay", "temperature", "buffer"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required for a quantitative targeting claim.",
       compatibility_rules=("binding_assay",)),

    _f(id="binding_assay", label="Binding assay", group="biological",
       definition="Assay used to measure affinity.", data_type="text",
       area_requirements={A.BIOLOGICAL_TARGETING: R.CONDITIONAL},
       condition="Required whenever a binding affinity is recorded."),

    _f(id="cellular_uptake_evidence", label="Cellular-uptake evidence",
       group="biological", definition="Recorded uptake data.",
       data_type="text", relevant_conditions=("model system", "assay", "time"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.OPTIONAL},
       researcher_note=
           "Absent uptake data means no uptake experiment is recorded. It is "
           "not a finding that uptake does not occur."),

    _f(id="trafficking_evidence", label="Intracellular-trafficking evidence",
       group="biological", definition="Recorded trafficking or fate data.",
       data_type="text", supported_statuses=_MEASURABLE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.OPTIONAL,
                          A.CINEMATIC_ANIMATION: R.CONDITIONAL},
       condition="Required to animate intracellular fate."),

    _f(id="selectivity_evidence", label="Selectivity evidence",
       group="biological",
       definition="Comparison against a non-target control.",
       data_type="text", supported_statuses=_MEASURABLE,
       area_requirements={A.BIOLOGICAL_TARGETING: R.OPTIONAL}),

    _f(id="protein_corona", label="Protein-corona evidence or assumption",
       group="biological",
       definition="Recorded corona composition, or the declared assumption "
                  "that corona effects are not modelled.",
       data_type="text",
       relevant_conditions=("medium", "serum concentration", "time"),
       area_requirements={A.BIOLOGICAL_TARGETING: R.OPTIONAL,
                          A.PHARMACOKINETIC_MODELLING: R.OPTIONAL},
       researcher_note=
           "No connected model represents corona formation. Recording the "
           "assumption explicitly is more honest than leaving it unstated."),

    # ------------------------------------------------------- pharmacokinetics
    _f(id="administration_route", label="Administration route",
       group="pharmacokinetics",
       definition="Route by which the dose enters the body.",
       data_type="enum",
       choices=("iv_bolus", "iv_infusion", "subcutaneous", "oral",
                "intraperitoneal"),
       supported_statuses=_NO_ILLUSTRATIVE,
       area_requirements={A.PHARMACOKINETIC_MODELLING: R.BLOCKING},
       researcher_note=
           "The route decides which input function applies. An intravenous "
           "dose has no absorption phase, so an absorption rate constant is "
           "meaningless for it."),

    _f(id="dose_amount", label="Dose amount", group="pharmacokinetics",
       definition="Administered dose.", data_type="number",
       accepted_units=("mg", "mg/kg", "mg/m2"),
       valid_range=(0.0, float("inf")),
       area_requirements={A.PHARMACOKINETIC_MODELLING: R.BLOCKING},
       compatibility_rules=("body_weight",)),

    _f(id="body_weight", label="Body weight", group="pharmacokinetics",
       definition="Body weight, required to resolve a weight-based dose.",
       data_type="number", accepted_units=("kg",),
       valid_range=(0.0, float("inf")), supported_statuses=_MEASURABLE,
       area_requirements={A.PHARMACOKINETIC_MODELLING: R.CONDITIONAL},
       condition="Required when the dose is expressed per kilogram.",
       researcher_note=
           "No default weight is applied. Assuming one would invent a patient "
           "characteristic that scales every reported concentration."),

    _f(id="pk_parameter_set", label="Pharmacokinetic parameter set",
       group="pharmacokinetics",
       definition="Reviewed parameter set (CL, Vc, Q, Vp and any nonlinear "
                  "terms) for this therapeutic and route.",
       data_type="text",
       supported_statuses=frozenset({
           ScientificStatus.LITERATURE_DERIVED,
           ScientificStatus.EXPERIMENTALLY_DERIVED,
           ScientificStatus.MEASURED, ScientificStatus.MISSING,
           ScientificStatus.NOT_APPLICABLE}),
       area_requirements={A.PHARMACOKINETIC_MODELLING: R.BLOCKING},
       compatibility_rules=("administration_route",),
       researcher_note=
           "A parameter set estimated for one route cannot be used for "
           "another: the absorption and bioavailability terms do not "
           "transfer."),

    # ---------------------------------------------------------------- safety
    _f(id="cytotoxicity_evidence", label="Cytotoxicity evidence",
       group="safety", definition="Recorded cytotoxicity data.",
       data_type="text",
       relevant_conditions=("model system", "assay", "exposure time"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.SAFETY_ASSESSMENT: R.BLOCKING},
       researcher_note=
           "This platform performs no safety determination. The area reports "
           "which evidence exists, and absence is reported as absence."),

    _f(id="in_vivo_evidence", label="In-vivo evidence", group="safety",
       definition="Recorded in-vivo study data.", data_type="text",
       relevant_conditions=("species", "route", "duration"),
       supported_statuses=_MEASURABLE,
       area_requirements={A.SAFETY_ASSESSMENT: R.OPTIONAL,
                          A.BIOLOGICAL_TARGETING: R.OPTIONAL}),

    _f(id="clearance_evidence", label="Clearance or elimination evidence",
       group="safety",
       definition="Recorded clearance, excretion or accumulation data.",
       data_type="text", supported_statuses=_MEASURABLE,
       area_requirements={A.SAFETY_ASSESSMENT: R.OPTIONAL}),
]}


def field_definition(field_id: str) -> FieldDefinition:
    """Look up a field, failing loudly on an unknown id."""
    try:
        return DATA_DICTIONARY[field_id]
    except KeyError as exc:
        raise KeyError(
            f"{field_id!r} is not in the scientific data dictionary. Add it "
            "there rather than referencing an undefined field.") from exc


def all_field_ids() -> list[str]:
    return list(DATA_DICTIONARY)


def fields_for_area(area: ReadinessArea) -> list[FieldDefinition]:
    return [d for d in DATA_DICTIONARY.values() if area in d.area_requirements]


def blocking_fields_for_area(area: ReadinessArea) -> list[FieldDefinition]:
    return [d for d in DATA_DICTIONARY.values()
            if d.area_requirements.get(area) is Requirement.BLOCKING]


# ---------------------------------------------------------------------------
# Measurement-method compatibility
# ---------------------------------------------------------------------------

#: Method families whose results are not interchangeable. Used to detect a
#: study that mixes, say, a DLS diameter and a TEM diameter as if they were the
#: same quantity.
MEASUREMENT_METHOD_CLASSES: dict[str, tuple[str, ...]] = {
    "scattering": ("dls", "dynamic light scattering", "nta",
                   "nanoparticle tracking", "sls", "static light scattering"),
    "microscopy": ("tem", "sem", "cryo-tem", "cryotem", "afm", "stem",
                   "transmission electron", "scanning electron",
                   "atomic force"),
    "spectroscopy": ("uv-vis", "uv/vis", "ftir", "nmr", "raman", "icp-ms",
                     "icp-oes"),
    "chromatography": ("hplc", "uplc", "sec", "gpc"),
    "electrophoretic": ("els", "electrophoretic light scattering",
                        "laser doppler"),
    "adsorption": ("bet", "bjh"),
    "diffraction": ("xrd", "saed", "saxs"),
}


def method_class(method: str | None) -> str | None:
    """Classify a free-text method string, or None when unrecognised.

    Returning None is deliberate: an unrecognised method is not forced into a
    family, and the engine treats an unclassifiable method as unknown rather
    than as compatible.
    """
    if not method:
        return None
    lowered = method.strip().lower()
    for family, markers in MEASUREMENT_METHOD_CLASSES.items():
        if any(marker in lowered for marker in markers):
            return family
    return None
