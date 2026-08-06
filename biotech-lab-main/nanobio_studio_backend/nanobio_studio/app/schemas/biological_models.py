"""
Pydantic schemas for Biological Model entities.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from nanobio_studio.app.core.constants import VALID_MODEL_TYPES


class BiologicalModelBase(BaseModel):
    """Base schema for biological models."""
    
    model_type: str = Field(..., description="Type: cell_line, organoid, mouse, rat, other")
    model_name: str = Field(..., min_length=1, max_length=256, description="Name of the model")
    species: Optional[str] = Field(None, max_length=64, description="Species name")
    disease_context: Optional[str] = Field(None, max_length=512, description="Disease context or reference")
    receptor_profile: Optional[str] = Field(None, max_length=1024, description="Receptor expression profile")
    notes: Optional[str] = Field(None, max_length=1024, description="Additional notes")

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, v: str) -> str:
        """Validate model type."""
        v_lower = v.lower().strip()
        if v_lower not in VALID_MODEL_TYPES:
            raise ValueError(f"model_type must be one of {VALID_MODEL_TYPES}")
        return v_lower


class BiologicalModelCreate(BiologicalModelBase):
    """Schema for creating biological model."""
    pass


class BiologicalModelUpdate(BaseModel):
    """Schema for updating biological model."""
    
    model_name: Optional[str] = Field(None, min_length=1, max_length=256)
    species: Optional[str] = Field(None, max_length=64)
    disease_context: Optional[str] = Field(None, max_length=512)
    receptor_profile: Optional[str] = Field(None, max_length=1024)
    notes: Optional[str] = Field(None, max_length=1024)


class BiologicalModelResponse(BiologicalModelBase):
    """Schema for returning biological model."""
    
    id: int = Field(..., description="Database primary key")

    class Config:
        from_attributes = True
