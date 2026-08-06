"""
Quick start guide and example usage.
"""
import asyncio
import json
from pathlib import Path


def example_create_record():
    """Example: Create a valid LNP record."""
    from nanobio_studio.app.schemas.lnp_record import LNPRecord
    
    record_dict = {
        "experiment": {
            "experiment_id": "EXP-EXAMPLE-001",
            "experiment_name": "Example LNP Study",
            "source_type": "internal_lab",
            "scientist": "Your Name",
        },
        "formulation": {
            "lipids": {
                "ionizable": {"name": "SM-102", "lipid_class": "ionizable"},
                "helper": {"name": "DSPC", "lipid_class": "helper"},
                "sterol": {"name": "Cholesterol", "lipid_class": "sterol"},
                "peg": {"name": "DMG-PEG2000", "lipid_class": "peg"},
            },
            "ratios_molar_percent": {
                "ionizable": 50.0,
                "helper": 10.0,
                "sterol": 38.5,
                "peg": 1.5,
            },
            "payload": {
                "payload_type": "mRNA",
                "name": "Protein X mRNA",
            },
            "intended_target": "Cancer cells",
        },
        "process_conditions": {
            "method": "microfluidic",
            "temperature_c": 25,
            "buffer": "acetate",
            "pH": 4.0,
        },
        "characterization": {
            "particle_size_nm": 78.0,
            "pdi": 0.12,
            "encapsulation_efficiency_pct": 92.0,
        },
        "biological_model": {
            "model_type": "cell_line",
            "name": "A549",
            "species": "human",
        },
        "assays": [],
    }
    
    # Create and validate using Pydantic
    record = LNPRecord(**record_dict)
    print("✓ Record created and validated successfully!")
    print(f"  Experiment: {record.experiment.experiment_name}")
    print(f"  Formulation: {record.formulation.formulation_id}")
    print(f"  Payload: {record.formulation.payload.name}")
    return record


def example_validate_record():
    """Example: Validate a record with QC engine."""
    from nanobio_studio.app.qc.validators import QCValidator
    
    record = {
        "experiment": {
            "experiment_id": "EXP-001",
            "experiment_name": "Test",
            "source_type": "internal_lab",
        },
        "formulation": {
            "lipids": {
                "ionizable": {"name": "X", "lipid_class": "ionizable"},
                "helper": {"name": "X", "lipid_class": "helper"},
                "sterol": {"name": "X", "lipid_class": "sterol"},
                "peg": {"name": "X", "lipid_class": "peg"},
            },
            "ratios_molar_percent": {
                "ionizable": 50,
                "helper": 10,
                "sterol": 38.5,
                "peg": 1.5,
            },
            "payload": {"payload_type": "mRNA", "name": "Test"},
        },
        "process_conditions": {"method": "microfluidic"},
        "characterization": {
            "particle_size_nm": 85.0,
            "pdi": 0.13,
        },
        "biological_model": {"model_type": "cell_line", "name": "Test"},
        "assays": [],
    }
    
    validator = QCValidator()
    results = validator.validate(record)
    
    print(f"QC Status: {results['overall_status']}")
    print(f"Passed Rules: {results['passed_rules']}/{results['total_rules']}")
    if results["errors"]:
        print("Errors:")
        for error in results["errors"]:
            print(f"  ✗ {error['rule']}: {error['message']}")
    if results["warnings"]:
        print("Warnings:")
        for warning in results["warnings"]:
            print(f"  ⚠ {warning['rule']}: {warning['message']}")
    
    return results


def example_import_json():
    """Example: Import JSON records."""
    from nanobio_studio.app.ingestion.json_importer import JSONImporter
    
    importer = JSONImporter()
    try:
        records = importer.import_file("data/sample_lnp_records.json")
        print(f"✓ Imported {len(records)} records")
        
        passed = sum(1 for r in records if r["qc_status"] == "pass")
        warnings = sum(1 for r in records if r["qc_status"] == "warning")
        failed = sum(1 for r in records if r["qc_status"] == "fail")
        
        print(f"  ✓ Passed: {passed}")
        print(f"  ⚠ Warnings: {warnings}")
        print(f"  ✗ Failed: {failed}")
        return records
    except FileNotFoundError:
        print("✗ Sample data file not found. Run from project root.")
        return []


if __name__ == "__main__":
    print("=" * 60)
    print("NanoBio Studio Backend - Example Usage")
    print("=" * 60)
    
    print("\n1. Creating and validating a record...")
    example_create_record()
    
    print("\n2. QC validation...")
    example_validate_record()
    
    print("\n3. Importing JSON data...")
    example_import_json()
    
    print("\n" + "=" * 60)
    print("✓ Examples complete!")
    print("=" * 60)
