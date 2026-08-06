"""
Pydantic schemas for Lipid entities.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from nanobio_studio.app.core.constants import VALID_LIPID_CLASSES


class LipidBase(BaseModel):
    """Base schema for lipid data."""
    
    lipid_name: str = Field(..., min_length=1, max_length=256, description="Name of the lipid")
    lipid_class: str = Field(..., description="Lipid class: ionizable, helper, sterol, peg")
    structure_smiles: Optional[str] = Field(None, max_length=2048, description="SMILES string for lipid structure")
    molecular_weight: Optional[float] = Field(None, gt=0, description="Molecular weight in g/mol")
    pka: Optional[float] = Field(None, description="pKa value for ionizable lipids")
    notes: Optional[str] = Field(None, max_length=1024, description="Additional notes")

    @field_validator("lipid_class")
    @classmethod
    def validate_lipid_class(cls, v: str) -> str:
        """Validate that lipid_class is one of allowed values."""
        v_lower = v.lower().strip()
        if v_lower not in VALID_LIPID_CLASSES:
            raise ValueError(f"lipid_class must be one of {VALID_LIPID_CLASSES}")
        return v_lower


class LipidCreate(LipidBase):
    """Schema for creating a new lipid."""
    pass


class LipidUpdate(BaseModel):
    """Schema for updating lipid fields."""
    
    lipid_name: Optional[str] = Field(None, min_length=1, max_length=256)
    lipid_class: Optional[str] = Field(None)
    structure_smiles: Optional[str] = Field(None, max_length=2048)
    molecular_weight: Optional[float] = Field(None, gt=0)
    pka: Optional[float] = None
    notes: Optional[str] = Field(None, max_length=1024)

    @field_validator("lipid_class")
    @classmethod
    def validate_lipid_class(cls, v: Optional[str]) -> Optional[str]:
        """Validate that lipid_class is one of allowed values."""
        if v is None:
            return None
        v_lower = v.lower().strip()
        if v_lower not in VALID_LIPID_CLASSES:
            raise ValueError(f"lipid_class must be one of {VALID_LIPID_CLASSES}")
        return v_lower


class LipidResponse(LipidBase):
    """Schema for returning lipid data."""
    
    lipid_id: int = Field(..., description="Unique lipid identifier")

    class Config:
        from_attributes = True
