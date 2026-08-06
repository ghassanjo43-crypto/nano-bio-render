"""
Pydantic schemas for Formulation entities.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class LipidRatios(BaseModel):
    """Molar percentages of lipids in formulation."""
    
    ionizable_percent: float = Field(..., ge=0, le=100, description="Ionizable lipid molar %")
    helper_percent: float = Field(..., ge=0, le=100, description="Helper lipid molar %")
    sterol_percent: float = Field(..., ge=0, le=100, description="Sterol molar %")
    peg_percent: float = Field(..., ge=0, le=100, description="PEG lipid molar %")

    @field_validator("*")
    @classmethod
    def validate_positive(cls, v):
        """Ensure all percentages are non-negative."""
        if v < 0:
            raise ValueError("Lipid percentages must be non-negative")
        return v


class FormulationBase(BaseModel):
    """Base schema for formulation data."""
    
    formulation_id: Optional[str] = Field(None, max_length=256, description="External formulation ID")
    ionizable_lipid_id: int = Field(..., description="ID of ionizable lipid")
    helper_lipid_id: int = Field(..., description="ID of helper lipid")
    sterol_lipid_id: int = Field(..., description="ID of sterol lipid")
    peg_lipid_id: int = Field(..., description="ID of PEG lipid")
    lipid_ratios: LipidRatios = Field(..., description="Molar percentages")
    ligand_name: Optional[str] = Field(None, max_length=256, description="Targeting ligand name")
    payload_id: int = Field(..., description="ID of payload")
    intended_target: Optional[str] = Field(None, max_length=256, description="Intended target tissue/cell")
    formulation_version: Optional[str] = Field(None, max_length=64, description="Version identifier")

    @field_validator("lipid_ratios", mode="before")
    @classmethod
    def validate_ratios_sum(cls, v):
        """Ensure lipid ratios sum to 100."""
        if isinstance(v, dict):
            total = v.get("ionizable_percent", 0) + v.get("helper_percent", 0) + \
                   v.get("sterol_percent", 0) + v.get("peg_percent", 0)
            if abs(total - 100.0) > 0.1:  # Allow 0.1% tolerance
                raise ValueError(f"Lipid ratios must sum to 100%, got {total}%")
        return v


class FormulationCreate(FormulationBase):
    """Schema for creating a new formulation."""
    pass


class FormulationUpdate(BaseModel):
    """Schema for updating formulation fields."""
    
    ligand_name: Optional[str] = Field(None, max_length=256)
    intended_target: Optional[str] = Field(None, max_length=256)
    formulation_version: Optional[str] = Field(None, max_length=64)
    lipid_ratios: Optional[LipidRatios] = None


class FormulationResponse(FormulationBase):
    """Schema for returning formulation data."""
    
    id: int = Field(..., description="Database primary key")

    class Config:
        from_attributes = True
