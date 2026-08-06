"""
Unit tests for NanoBio Studio backend.
"""
import json
import pytest
from pydantic import ValidationError
from nanobio_studio.app.schemas.lnp_record import LNPRecord
from nanobio_studio.app.qc.validators import (
    QCValidator, LipidRatiosSum, ParticleSizeRange, PDIValidation
)
from nanobio_studio.app.utils.helpers import (
    normalize_lipid_class, parse_flow_rate_ratio, calculate_total_lipid_amount
)


@pytest.fixture
def valid_lnp_record():
    """Fixture with valid LNP record."""
    return {
        "experiment": {
            "experiment_id": "EXP-2026-0001",
            "experiment_name": "Test experiment",
            "source_type": "internal_lab",
        },
        "formulation": {
            "lipids": {
                "ionizable": {"name": "SM-102", "lipid_class": "ionizable"},
                "helper": {"name": "DSPC", "lipid_class": "helper"},
                "sterol": {"name": "Cholesterol", "lipid_class": "sterol"},
                "peg": {"name": "DMG-PEG", "lipid_class": "peg"},
            },
            "ratios_molar_percent": {
                "ionizable": 50.0,
                "helper": 10.0,
                "sterol": 38.5,
                "peg": 1.5,
            },
            "payload": {
                "payload_type": "mRNA",
                "name": "Test mRNA",
            }
        },
        "process_conditions": {"method": "microfluidic"},
        "characterization": {
            "particle_size_nm": 80.0,
            "pdi": 0.12,
            "encapsulation_efficiency_pct": 90.0,
        },
        "biological_model": {
            "model_type": "cell_line",
            "name": "HepG2",
        },
        "assays": [],
    }


class TestSchemaValidation:
    """Test Pydantic schema validation."""
    
    def test_valid_lnp_record(self, valid_lnp_record):
        """Test that valid record passes Pydantic validation."""
        record = LNPRecord(**valid_lnp_record)
        assert record.experiment.experiment_name == "Test experiment"
    
    def test_missing_required_field(self, valid_lnp_record):
        """Test that missing required fields raise ValidationError."""
        del valid_lnp_record["experiment"]["experiment_name"]
        with pytest.raises(ValidationError):
            LNPRecord(**valid_lnp_record)
    
    def test_invalid_source_type(self, valid_lnp_record):
        """Test that invalid source_type raises ValidationError."""
        valid_lnp_record["experiment"]["source_type"] = "invalid_type"
        with pytest.raises(ValidationError):
            LNPRecord(**valid_lnp_record)


class TestQCValidation:
    """Test QC validation rules."""
    
    def test_lipid_ratios_sum_valid(self, valid_lnp_record):
        """Test that valid lipid ratios pass."""
        validator = LipidRatiosSum()
        passed, msg = validator.check(valid_lnp_record)
        assert passed
    
    def test_lipid_ratios_sum_invalid(self, valid_lnp_record):
        """Test that invalid lipid ratios fail."""
        valid_lnp_record["formulation"]["ratios_molar_percent"]["ionizable"] = 60.0
        validator = LipidRatiosSum()
        passed, msg = validator.check(valid_lnp_record)
        assert not passed
    
    def test_particle_size_valid(self, valid_lnp_record):
        """Test that valid particle size passes."""
        validator = ParticleSizeRange()
        passed, msg = validator.check(valid_lnp_record)
        assert passed
    
    def test_particle_size_too_large(self, valid_lnp_record):
        """Test that too-large particle size fails."""
        valid_lnp_record["characterization"]["particle_size_nm"] = 1500.0
        validator = ParticleSizeRange()
        passed, msg = validator.check(valid_lnp_record)
        assert not passed
    
    def test_pdi_valid(self, valid_lnp_record):
        """Test that valid PDI passes."""
        validator = PDIValidation()
        passed, msg = validator.check(valid_lnp_record)
        assert passed
    
    def test_pdi_invalid(self, valid_lnp_record):
        """Test that invalid PDI fails."""
        valid_lnp_record["characterization"]["pdi"] = 1.5
        validator = PDIValidation()
        passed, msg = validator.check(valid_lnp_record)
        assert not passed
    
    def test_full_validation(self, valid_lnp_record):
        """Test complete QC validation."""
        validator = QCValidator()
        results = validator.validate(valid_lnp_record)
        assert results["overall_status"] in ["pass", "warning", "fail"]
        assert results["total_rules"] > 0


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_normalize_lipid_class(self):
        """Test lipid class normalization."""
        assert normalize_lipid_class("IONIZABLE") == "ionizable"
        assert normalize_lipid_class("Helper") == "helper"
        assert normalize_lipid_class("  sterol  ") == "sterol"
    
    def test_parse_flow_rate_ratio(self):
        """Test flow rate ratio parsing."""
        result = parse_flow_rate_ratio("3:1")
        assert result == (3.0, 1.0)
        
        result = parse_flow_rate_ratio("invalid")
        assert result is None
    
    def test_calculate_total_lipid_amount(self):
        """Test lipid amount calculation."""
        ratios = {
            "ionizable": 50.0,
            "helper": 10.0,
            "sterol": 38.5,
            "peg": 1.5,
        }
        total = calculate_total_lipid_amount(ratios)
        assert abs(total - 100.0) < 0.01


class TestAPIHealth:
    """Test API endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health check endpoint (basic structure test)."""
        # This would require mounting the app and using TestClient
        # Placeholder for integration tests
        pass
