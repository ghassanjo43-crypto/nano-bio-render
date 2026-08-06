"""
Master LNPRecord schema - unified nested schema for complete experiment records.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from nanobio_studio.app.core.constants import QC_STATUS_PASS, QC_STATUS_FAIL, QC_STATUS_WARNING, QC_STATUS_PENDING


class LipidInfo(BaseModel):
    """Simplified lipid info in nested structure."""
    
    name: str = Field(..., description="Lipid name")
    lipid_class: str = Field(..., description="Class: ionizable, helper, sterol, peg")


class LipidComposition(BaseModel):
    """Lipids and their molar ratios in formulation."""
    
    ionizable: LipidInfo
    helper: LipidInfo
    sterol: LipidInfo
    peg: LipidInfo


class LipidRatios(BaseModel):
    """Molar percentages of each lipid class."""
    
    ionizable: float = Field(..., ge=0, le=100)
    helper: float = Field(..., ge=0, le=100)
    sterol: float = Field(..., ge=0, le=100)
    peg: float = Field(..., ge=0, le=100)

    @field_validator("*")
    @classmethod
    def validate_sum(cls, v):
        """Ratios must sum to approximately 100."""
        return v


class PayloadInfo(BaseModel):
    """Payload information."""
    
    payload_type: str = Field(..., description="mRNA, siRNA, DNA, protein, small_molecule")
    name: str = Field(..., description="Payload name")
    target_gene: Optional[str] = None


class FormulationInfo(BaseModel):
    """Complete formulation information."""
    
    formulation_id: Optional[str] = None
    lipids: LipidComposition
    ratios_molar_percent: LipidRatios
    ligand: Optional[str] = None
    payload: PayloadInfo
    intended_target: Optional[str] = None
    formulation_version: Optional[str] = None


class ProcessConditions(BaseModel):
    """Process conditions for formulation preparation."""
    
    method: str = Field(..., description="microfluidic, manual_mixing, ethanol_injection")
    flow_rate_ratio: Optional[str] = None
    total_flow_rate_ml_min: Optional[float] = None
    buffer: Optional[str] = None
    pH: Optional[float] = Field(None, ge=0, le=14)
    temperature_c: Optional[float] = None
    mixing_chip_type: Optional[str] = None
    operator_or_robot: Optional[str] = None
    batch_id: Optional[str] = None


class CharacterizationData(BaseModel):
    """Particle characterization results."""
    
    particle_size_nm: Optional[float] = None
    pdi: Optional[float] = None
    zeta_potential_mv: Optional[float] = None
    encapsulation_efficiency_pct: Optional[float] = None
    stability_hours: Optional[float] = None
    morphology: Optional[str] = None
    measurement_method: Optional[str] = None
    measurement_date: Optional[datetime] = None


class BiologicalModelInfo(BaseModel):
    """Biological model information."""
    
    model_type: str = Field(..., description="cell_line, organoid, mouse, rat, other")
    name: str = Field(..., description="Model name")
    species: Optional[str] = None
    disease_context: Optional[str] = None
    receptor_profile: Optional[str] = None


class AssayResult(BaseModel):
    """Single assay result."""
    
    assay_type: str = Field(..., description="uptake, transfection, toxicity, biodistribution, cytokine_response")
    dose: Optional[float] = None
    route_of_administration: Optional[str] = None
    timepoint_hours: Optional[float] = None
    result_value: Optional[float] = None
    result_unit: Optional[str] = None
    normalized_score: Optional[float] = None
    outcome_label: Optional[str] = None
    notes: Optional[str] = None


class ExperimentMetadata(BaseModel):
    """Experiment metadata."""
    
    experiment_id: Optional[str] = None
    experiment_name: str = Field(..., description="Name of experiment")
    source_type: str = Field(..., description="public_dataset, literature, internal_lab, partner_lab")
    source_reference: Optional[str] = None
    date_run: Optional[datetime] = None
    scientist: Optional[str] = None
    institution: Optional[str] = None


class LNPRecord(BaseModel):
    """
    Master LNP Record Schema - Complete nested structure for one full experiment.
    This is the universal schema for ingest and query.
    """
    
    # Experiment metadata
    experiment: ExperimentMetadata
    
    # Formulation design
    formulation: FormulationInfo
    
    # Process conditions
    process_conditions: ProcessConditions
    
    # Characterization results
    characterization: CharacterizationData
    
    # Biological testing
    biological_model: BiologicalModelInfo
    assays: List[AssayResult] = Field(default_factory=list, description="List of assay results")
    
    # QC status
    qc_status: str = Field(default=QC_STATUS_PENDING, description="pass, fail, warning, pending")
    qc_notes: Optional[str] = Field(None, description="QC validation notes")

    class Config:
        """Pydantic model config."""
        json_schema_extra = {
            "example": {
                "experiment": {
                    "experiment_id": "EXP-2026-0001",
                    "experiment_name": "LNP optimization study",
                    "source_type": "internal_lab",
                    "source_reference": "Lab notebook 123",
                    "date_run": "2026-03-10T10:00:00",
                    "scientist": "Dr. Smith",
                    "institution": "Research Institute"
                },
                "formulation": {
                    "formulation_id": "LNP-0001",
                    "lipids": {
                        "ionizable": {"name": "SM-102", "lipid_class": "ionizable"},
                        "helper": {"name": "DSPC", "lipid_class": "helper"},
                        "sterol": {"name": "Cholesterol", "lipid_class": "sterol"},
                        "peg": {"name": "PEG-lipid", "lipid_class": "peg"}
                    },
                    "ratios_molar_percent": {
                        "ionizable": 50.0,
                        "helper": 10.0,
                        "sterol": 38.5,
                        "peg": 1.5
                    },
                    "payload": {
                        "payload_type": "mRNA",
                        "name": "Firefly luciferase mRNA",
                        "target_gene": "LACZ"
                    },
                    "intended_target": "Liver cells"
                },
                "process_conditions": {
                    "method": "microfluidic",
                    "temperature_c": 25,
                    "pH": 4.0
                },
                "characterization": {
                    "particle_size_nm": 78.0,
                    "pdi": 0.12,
                    "zeta_potential_mv": -4.3,
                    "encapsulation_efficiency_pct": 93.0
                },
                "biological_model": {
                    "model_type": "cell_line",
                    "name": "HepG2",
                    "species": "human"
                },
                "assays": [
                    {
                        "assay_type": "uptake",
                        "timepoint_hours": 24,
                        "result_value": 0.74
                    }
                ],
                "qc_status": "pass"
            }
        }
