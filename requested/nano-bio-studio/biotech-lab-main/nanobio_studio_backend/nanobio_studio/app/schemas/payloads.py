"""
Pydantic schemas for Payload entities.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from nanobio_studio.app.core.constants import VALID_PAYLOAD_TYPES


class PayloadBase(BaseModel):
    """Base schema for payload data."""
    
    payload_type: str = Field(..., description="Type: mRNA, siRNA, DNA, protein, small_molecule")
    payload_name: str = Field(..., min_length=1, max_length=256, description="Name of the payload")
    sequence_or_description: Optional[str] = Field(None, description="Sequence or description of payload")
    target_gene: Optional[str] = Field(None, max_length=256, description="Target gene name")
    payload_length: Optional[int] = Field(None, ge=0, description="Length in nucleotides or amino acids")
    notes: Optional[str] = Field(None, max_length=1024, description="Additional notes")

    @field_validator("payload_type")
    @classmethod
    def validate_payload_type(cls, v: str) -> str:
        """Validate that payload_type is one of allowed values."""
        v_lower = v.lower().strip()
        if v_lower not in VALID_PAYLOAD_TYPES:
            raise ValueError(f"payload_type must be one of {VALID_PAYLOAD_TYPES}")
        return v_lower


class PayloadCreate(PayloadBase):
    """Schema for creating a new payload."""
    pass


class PayloadUpdate(BaseModel):
    """Schema for updating payload fields."""
    
    payload_type: Optional[str] = None
    payload_name: Optional[str] = Field(None, min_length=1, max_length=256)
    sequence_or_description: Optional[str] = None
    target_gene: Optional[str] = Field(None, max_length=256)
    payload_length: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=1024)

    @field_validator("payload_type")
    @classmethod
    def validate_payload_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate that payload_type is one of allowed values."""
        if v is None:
            return None
        v_lower = v.lower().strip()
        if v_lower not in VALID_PAYLOAD_TYPES:
            raise ValueError(f"payload_type must be one of {VALID_PAYLOAD_TYPES}")
        return v_lower


class PayloadResponse(PayloadBase):
    """Schema for returning payload data."""
    
    payload_id: int = Field(..., description="Unique payload identifier")

    class Config:
        from_attributes = True
