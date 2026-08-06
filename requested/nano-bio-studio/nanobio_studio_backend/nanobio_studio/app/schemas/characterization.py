"""
Pydantic schemas for Characterization entities.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class CharacterizationBase(BaseModel):
    """Base schema for particle characterization."""
    
    formulation_id: int = Field(..., description="ID of formulation")
    process_id: Optional[int] = Field(None, description="ID of process conditions")
    particle_size_nm: Optional[float] = Field(None, gt=0, le=1000, description="Particle size in nm")
    pdi: Optional[float] = Field(None, ge=0, le=1, description="Polydispersity index (0-1)")
    zeta_potential_mv: Optional[float] = Field(None, description="Zeta potential in mV")
    encapsulation_efficiency_pct: Optional[float] = Field(None, ge=0, le=100, description="Encapsulation efficiency %")
    stability_hours: Optional[float] = Field(None, gt=0, description="Stability in hours")
    morphology: Optional[str] = Field(None, max_length=256, description="Particle morphology description")
    measurement_method: Optional[str] = Field(None, max_length=256, description="Measurement method used")
    measurement_date: Optional[datetime] = Field(None, description="Date of measurement")

    @field_validator("particle_size_nm")
    @classmethod
    def validate_particle_size(cls, v: Optional[float]) -> Optional[float]:
        """Ensure particle size is reasonable."""
        if v is not None and (v < 1 or v > 1000):
            raise ValueError("Particle size should typically be between 1-1000 nm")
        return v


class CharacterizationCreate(CharacterizationBase):
    """Schema for creating characterization record."""
    pass


class CharacterizationUpdate(BaseModel):
    """Schema for updating characterization."""
    
    particle_size_nm: Optional[float] = Field(None, gt=0, le=1000)
    pdi: Optional[float] = Field(None, ge=0, le=1)
    zeta_potential_mv: Optional[float] = None
    encapsulation_efficiency_pct: Optional[float] = Field(None, ge=0, le=100)
    stability_hours: Optional[float] = Field(None, gt=0)
    morphology: Optional[str] = Field(None, max_length=256)
    measurement_method: Optional[str] = Field(None, max_length=256)
    measurement_date: Optional[datetime] = None


class CharacterizationResponse(CharacterizationBase):
    """Schema for returning characterization data."""
    
    id: int = Field(..., description="Database primary key")

    class Config:
        from_attributes = True
