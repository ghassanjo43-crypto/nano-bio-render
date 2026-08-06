"""
Pydantic schemas for Experiment entities.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from nanobio_studio.app.core.constants import VALID_SOURCE_TYPES


class ExperimentBase(BaseModel):
    """Base schema for experiments."""
    
    experiment_name: str = Field(..., min_length=1, max_length=512, description="Experiment name")
    experiment_id: Optional[str] = Field(None, max_length=256, description="External experiment ID")
    source_type: str = Field(..., description="Source: public_dataset, literature, internal_lab, partner_lab")
    source_reference: Optional[str] = Field(None, max_length=1024, description="Source reference or DOI")
    date_run: Optional[datetime] = Field(None, description="Date experiment was performed")
    scientist: Optional[str] = Field(None, max_length=256, description="Scientist or operator name")
    institution: Optional[str] = Field(None, max_length=512, description="Institution name")
    qc_status: Optional[str] = Field("pending", max_length=64, description="QC status: pass, fail, warning, pending")
    comments: Optional[str] = Field(None, max_length=2048, description="General comments or notes")

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        """Validate source type."""
        v_lower = v.lower().strip()
        if v_lower not in VALID_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {VALID_SOURCE_TYPES}")
        return v_lower


class ExperimentCreate(ExperimentBase):
    """Schema for creating experiment."""
    pass


class ExperimentUpdate(BaseModel):
    """Schema for updating experiment."""
    
    experiment_name: Optional[str] = Field(None, min_length=1, max_length=512)
    source_reference: Optional[str] = Field(None, max_length=1024)
    date_run: Optional[datetime] = None
    scientist: Optional[str] = Field(None, max_length=256)
    institution: Optional[str] = Field(None, max_length=512)
    qc_status: Optional[str] = Field(None, max_length=64)
    comments: Optional[str] = Field(None, max_length=2048)


class ExperimentResponse(ExperimentBase):
    """Schema for returning experiment."""
    
    id: int = Field(..., description="Database primary key")

    class Config:
        from_attributes = True
