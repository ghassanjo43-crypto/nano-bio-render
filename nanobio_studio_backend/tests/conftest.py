"""
Pytest configuration and fixtures.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_lnp_data():
    """Fixture providing mock LNP data for testing."""
    return {
        "experiment": {
            "experiment_id": "TEST-001",
            "experiment_name": "Test experiment",
            "source_type": "internal_lab",
            "scientist": "Test Scientist",
        },
        "formulation": {
            "formulation_id": "TEST-LNP-001",
            "lipids": {
                "ionizable": {"name": "TEST-ION", "lipid_class": "ionizable"},
                "helper": {"name": "TEST-HELP", "lipid_class": "helper"},
                "sterol": {"name": "TEST-STEROL", "lipid_class": "sterol"},
                "peg": {"name": "TEST-PEG", "lipid_class": "peg"},
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
                "target_gene": "TEST",
            },
            "intended_target": "Test tissue",
        },
        "process_conditions": {
            "method": "microfluidic",
            "temperature_c": 25.0,
            "buffer": "acetate",
            "pH": 4.0,
        },
        "characterization": {
            "particle_size_nm": 80.0,
            "pdi": 0.12,
            "zeta_potential_mv": -4.0,
            "encapsulation_efficiency_pct": 90.0,
            "stability_hours": 168,
        },
        "biological_model": {
            "model_type": "cell_line",
            "name": "HepG2",
            "species": "human",
        },
        "assays": [
            {
                "assay_type": "uptake",
                "timepoint_hours": 24,
                "result_value": 0.75,
                "result_unit": "normalized",
            }
        ],
        "qc_status": "pass",
    }
