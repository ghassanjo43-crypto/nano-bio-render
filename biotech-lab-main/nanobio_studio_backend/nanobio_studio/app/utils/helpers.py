"""
Utility functions for the NanoBio Studio backend.
"""
import uuid
from datetime import datetime
import re


def generate_uuid() -> str:
    """Generate a unique UUID."""
    return str(uuid.uuid4())


def generate_experiment_id() -> str:
    """Generate a unique experiment ID."""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique_suffix = str(uuid.uuid4())[:8].upper()
    return f"EXP-{timestamp}-{unique_suffix}"


def generate_formulation_id() -> str:
    """Generate a unique formulation ID."""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique_suffix = str(uuid.uuid4())[:6].upper()
    return f"LNP-{timestamp}-{unique_suffix}"


def normalize_lipid_class(value: str) -> str:
    """Normalize lipid class name."""
    return value.lower().strip() if value else None


def normalize_payload_type(value: str) -> str:
    """Normalize payload type."""
    mapping = {
        "mrna": "mRNA",
        "sirna": "siRNA",
        "dna": "DNA",
        "protein": "protein",
        "small_molecule": "small_molecule",
    }
    normalized = value.lower().strip() if value else None
    return mapping.get(normalized, normalized)


def normalize_whitespace(value: str) -> str:
    """Normalize whitespace in strings."""
    if not value:
        return value
    return " ".join(value.split())


def validate_smiles(smiles: str) -> bool:
    """Basic SMILES validation (very simple check)."""
    if not smiles:
        return True
    # Just check for basic characters - full validation would require rdkit
    valid_chars = set("CNOPSFClBrI()[]=#\\/@+-.")
    return all(c in valid_chars or c.isdigit() for c in smiles)


def parse_flow_rate_ratio(ratio_str: str) -> tuple:
    """
    Parse flow rate ratio string like '3:1' into tuple.
    
    Args:
        ratio_str: String like '3:1'
    
    Returns:
        Tuple of (first, second) or None if invalid
    """
    if not ratio_str:
        return None
    
    try:
        parts = ratio_str.split(":")
        if len(parts) != 2:
            return None
        return (float(parts[0]), float(parts[1]))
    except (ValueError, AttributeError):
        return None


def calculate_total_lipid_amount(ratios: dict) -> float:
    """Calculate total from molar percentages."""
    return sum([
        ratios.get("ionizable", 0),
        ratios.get("helper", 0),
        ratios.get("sterol", 0),
        ratios.get("peg", 0),
    ])
