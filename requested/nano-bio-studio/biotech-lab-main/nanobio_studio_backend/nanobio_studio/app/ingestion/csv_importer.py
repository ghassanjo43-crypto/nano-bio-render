"""
CSV importer for LNP records.
"""
import pandas as pd
from typing import List, Dict, Any
from loguru import logger
from nanobio_studio.app.schemas.lnp_record import LNPRecord
from nanobio_studio.app.qc.validators import QCValidator


class CSVImporter:
    """Import and validate CSV LNP records."""
    
    def __init__(self):
        """Initialize importer."""
        self.validator = QCValidator()
        self.logger = logger.bind(module="CSVImporter")
    
    def import_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Import CSV file containing LNP records (flattened format).
        
        Args:
            file_path: Path to CSV file
        
        Returns:
            List of validated records
        """
        try:
            df = pd.read_csv(file_path)
            self.logger.info(f"Loaded CSV with {len(df)} rows")
            
            validated_records = []
            for idx, row in df.iterrows():
                try:
                    # Reconstruct nested structure from flat CSV
                    record = self._flatten_row_to_nested(row)
                    
                    # Validate with Pydantic
                    lnp_record = LNPRecord(**record)
                    
                    # QC validation
                    qc_result = self.validator.validate(record)
                    
                    validated_record = {
                        "original": record,
                        "validated": lnp_record.model_dump(),
                        "qc_result": qc_result,
                        "qc_status": qc_result.get("overall_status", "fail"),
                    }
                    
                    validated_records.append(validated_record)
                    self.logger.info(f"Row {idx} validated: {qc_result['overall_status']}")
                
                except Exception as e:
                    self.logger.error(f"Row {idx} validation failed: {e}")
                    validated_records.append({
                        "original": dict(row),
                        "validation_error": str(e),
                        "qc_status": "fail",
                    })
            
            self.logger.info(f"Imported {len(validated_records)} records from {file_path}")
            return validated_records
        
        except Exception as e:
            self.logger.error(f"Failed to import CSV file {file_path}: {e}")
            raise
    
    def _flatten_row_to_nested(_, row: pd.Series) -> Dict:
        """
        Convert flattened CSV row to nested LNPRecord structure.
        Handles prefixed column names like 'lipid_ionizable_name'.
        """
        record = {
            "experiment": {},
            "formulation": {
                "lipids": {},
                "ratios_molar_percent": {},
                "payload": {},
            },
            "process_conditions": {},
            "characterization": {},
            "biological_model": {},
            "assays": [],
        }
        
        # Map CSV columns to nested structure
        for col, value in row.items():
            if pd.isna(value):
                continue
            
            # Experiment fields
            if col.startswith("exp_"):
                key = col.replace("exp_", "")
                record["experiment"][key] = value
            
            # Formulation lipids
            elif col.startswith("lipid_"):
                parts = col.split("_", 2)
                if len(parts) >= 3:
                    lipid_type = parts[1]  # ionizable, helper, sterol, peg
                    field = "_".join(parts[2:])  # name, class, etc
                    
                    if lipid_type not in record["formulation"]["lipids"]:
                        record["formulation"]["lipids"][lipid_type] = {}
                    record["formulation"]["lipids"][lipid_type][field] = value
            
            # Ratios
            elif col.startswith("ratio_"):
                key = col.replace("ratio_", "")
                record["formulation"]["ratios_molar_percent"][key] = float(value)
            
            # Payload
            elif col.startswith("payload_"):
                key = col.replace("payload_", "")
                record["formulation"]["payload"][key] = value
            
            # Process
            elif col.startswith("process_"):
                key = col.replace("process_", "")
                record["process_conditions"][key] = value
            
            # Characterization
            elif col.startswith("char_"):
                key = col.replace("char_", "")
                record["characterization"][key] = value
            
            # Model
            elif col.startswith("model_"):
                key = col.replace("model_", "")
                record["biological_model"][key] = value
            
            # QC
            elif col == "qc_status":
                record["qc_status"] = value
        
        return record
