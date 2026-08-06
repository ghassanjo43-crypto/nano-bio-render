"""
Pydantic schemas for Process Conditions entities.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from nanobio_studio.app.core.constants import VALID_PREP_METHODS


class ProcessConditionsBase(BaseModel):
    """Base schema for process conditions."""
    
    formulation_id: int = Field(..., description="ID of formulation")
    preparation_method: str = Field(..., description="Method: microfluidic, manual_mixing, ethanol_injection")
    flow_rate_ratio: Optional[str] = Field(None, max_length=64, description="Flow rate ratio e.g. '3:1'")
    total_flow_rate_ml_min: Optional[float] = Field(None, gt=0, description="Total flow rate in mL/min")
    buffer_type: Optional[str] = Field(None, max_length=256, description="Type of buffer used")
    buffer_ph: Optional[float] = Field(None, ge=0, le=14, description="pH value")
    temperature_c: Optional[float] = Field(None, description="Temperature in Celsius")
    mixing_chip_type: Optional[str] = Field(None, max_length=256, description="Type of microfluidic chip")
    operator_or_robot: Optional[str] = Field(None, max_length=256, description="Operator name or robot ID")
    batch_id: Optional[str] = Field(None, max_length=256, description="Batch identifier")

    @field_validator("preparation_method")
    @classmethod
    def validate_preparation_method(cls, v: str) -> str:
        """Validate preparation method."""
        v_lower = v.lower().strip()
        if v_lower not in VALID_PREP_METHODS:
            raise ValueError(f"preparation_method must be one of {VALID_PREP_METHODS}")
        return v_lower


class ProcessConditionsCreate(ProcessConditionsBase):
    """Schema for creating process conditions."""
    pass


class ProcessConditionsUpdate(BaseModel):
    """Schema for updating process conditions."""
    
    flow_rate_ratio: Optional[str] = Field(None, max_length=64)
    total_flow_rate_ml_min: Optional[float] = Field(None, gt=0)
    buffer_type: Optional[str] = Field(None, max_length=256)
    buffer_ph: Optional[float] = Field(None, ge=0, le=14)
    temperature_c: Optional[float] = None
    mixing_chip_type: Optional[str] = Field(None, max_length=256)
    operator_or_robot: Optional[str] = Field(None, max_length=256)
    batch_id: Optional[str] = Field(None, max_length=256)


class ProcessConditionsResponse(ProcessConditionsBase):
    """Schema for returning process conditions."""
    
    id: int = Field(..., description="Database primary key")

    class Config:
        from_attributes = True
