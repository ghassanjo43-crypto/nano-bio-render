"""
Constants used throughout the NanoBio Studio backend.
"""

# ============================================================
# LIPID CLASSES
# ============================================================
LIPID_CLASS_IONIZABLE = "ionizable"
LIPID_CLASS_HELPER = "helper"
LIPID_CLASS_STEROL = "sterol"
LIPID_CLASS_PEG = "peg"

VALID_LIPID_CLASSES = {
    LIPID_CLASS_IONIZABLE,
    LIPID_CLASS_HELPER,
    LIPID_CLASS_STEROL,
    LIPID_CLASS_PEG,
}

# ============================================================
# PAYLOAD TYPES
# ============================================================
PAYLOAD_TYPE_MRNA = "mRNA"
PAYLOAD_TYPE_SIRNA = "siRNA"
PAYLOAD_TYPE_DNA = "DNA"
PAYLOAD_TYPE_PROTEIN = "protein"
PAYLOAD_TYPE_SMALL_MOLECULE = "small_molecule"

VALID_PAYLOAD_TYPES = {
    PAYLOAD_TYPE_MRNA,
    PAYLOAD_TYPE_SIRNA,
    PAYLOAD_TYPE_DNA,
    PAYLOAD_TYPE_PROTEIN,
    PAYLOAD_TYPE_SMALL_MOLECULE,
}

# ============================================================
# PREPARATION METHODS
# ============================================================
PREP_METHOD_MICROFLUIDIC = "microfluidic"
PREP_METHOD_MANUAL_MIXING = "manual_mixing"
PREP_METHOD_ETHANOL_INJECTION = "ethanol_injection"

VALID_PREP_METHODS = {
    PREP_METHOD_MICROFLUIDIC,
    PREP_METHOD_MANUAL_MIXING,
    PREP_METHOD_ETHANOL_INJECTION,
}

# ============================================================
# ASSAY TYPES
# ============================================================
ASSAY_TYPE_UPTAKE = "uptake"
ASSAY_TYPE_TRANSFECTION = "transfection"
ASSAY_TYPE_TOXICITY = "toxicity"
ASSAY_TYPE_BIODISTRIBUTION = "biodistribution"
ASSAY_TYPE_CYTOKINE_RESPONSE = "cytokine_response"

VALID_ASSAY_TYPES = {
    ASSAY_TYPE_UPTAKE,
    ASSAY_TYPE_TRANSFECTION,
    ASSAY_TYPE_TOXICITY,
    ASSAY_TYPE_BIODISTRIBUTION,
    ASSAY_TYPE_CYTOKINE_RESPONSE,
}

# ============================================================
# BIOLOGICAL MODEL TYPES
# ============================================================
MODEL_TYPE_CELL_LINE = "cell_line"
MODEL_TYPE_ORGANOID = "organoid"
MODEL_TYPE_MOUSE = "mouse"
MODEL_TYPE_RAT = "rat"
MODEL_TYPE_OTHER = "other"

VALID_MODEL_TYPES = {
    MODEL_TYPE_CELL_LINE,
    MODEL_TYPE_ORGANOID,
    MODEL_TYPE_MOUSE,
    MODEL_TYPE_RAT,
    MODEL_TYPE_OTHER,
}

# ============================================================
# SOURCE TYPES
# ============================================================
SOURCE_TYPE_PUBLIC_DATASET = "public_dataset"
SOURCE_TYPE_LITERATURE = "literature"
SOURCE_TYPE_INTERNAL_LAB = "internal_lab"
SOURCE_TYPE_PARTNER_LAB = "partner_lab"

VALID_SOURCE_TYPES = {
    SOURCE_TYPE_PUBLIC_DATASET,
    SOURCE_TYPE_LITERATURE,
    SOURCE_TYPE_INTERNAL_LAB,
    SOURCE_TYPE_PARTNER_LAB,
}

# ============================================================
# QC STATUS
# ============================================================
QC_STATUS_PASS = "pass"
QC_STATUS_FAIL = "fail"
QC_STATUS_WARNING = "warning"
QC_STATUS_PENDING = "pending"

# ============================================================
# MEASUREMENT UNITS
# ============================================================
PARTICLE_SIZE_UNIT = "nm"
ZETA_POTENTIAL_UNIT = "mV"
PDI_UNIT = "dimensionless"
ENCAPSULATION_UNIT = "%"
STABILITY_UNIT = "hours"
