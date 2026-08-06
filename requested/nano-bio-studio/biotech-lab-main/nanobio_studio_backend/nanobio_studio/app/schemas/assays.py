"""
Pydantic schemas for Assay entities.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from nanobio_studio.app.core.constants import VALID_ASSAY_TYPES


class AssayBase(BaseModel):
    """Base schema for assay results."""
    
    formulation_id: int = Field(..., description="ID of formulation")
    model_id: int = Field(..., description="ID of biological model")
    assay_type: str = Field(..., description="Assay type: uptake, transfection, toxicity, biodistribution, cytokine_response")
    dose: Optional[float] = Field(None, gt=0, description="Dose administered")
    route_of_administration: Optional[str] = Field(None, max_length=128, description="Route e.g. IV, IP, oral")
    timepoint_hours: Optional[float] = Field(None, ge=0, description="Timepoint in hours")
    result_value: Optional[float] = Field(None, description="Measured result value")
    result_unit: Optional[str] = Field(None, max_length=128, description="Unit of measurement")
    normalized_score: Optional[float] = Field(None, ge=0, le=1, description="Normalized score (0-1)")
    outcome_label: Optional[str] = Field(None, max_length=256, description="Outcome label")
    notes: Optional[str] = Field(None, max_length=1024, description="Additional notes")

    @field_validator("assay_type")
    @classmethod
    def validate_assay_type(cls, v: str) -> str:
        """Validate assay type."""
        v_lower = v.lower().strip()
        if v_lower not in VALID_ASSAY_TYPES:
            raise ValueError(f"assay_type must be one of {VALID_ASSAY_TYPES}")
        return v_lower


class AssayCreate(AssayBase):
    """Schema for creating assay result."""
    pass


class AssayUpdate(BaseModel):
    """Schema for updating assay result."""
    
    dose: Optional[float] = Field(None, gt=0)
    route_of_administration: Optional[str] = Field(None, max_length=128)
    timepoint_hours: Optional[float] = Field(None, ge=0)
    result_value: Optional[float] = None
    result_unit: Optional[str] = Field(None, max_length=128)
    normalized_score: Optional[float] = Field(None, ge=0, le=1)
    outcome_label: Optional[str] = Field(None, max_length=256)
    notes: Optional[str] = Field(None, max_length=1024)


class AssayResponse(AssayBase):
    """Schema for returning assay result."""
    
    id: int = Field(..., description="Database primary key")

    class Config:
        from_attributes = True
