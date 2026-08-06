"""
JSON importer for LNP records.
"""
import json
from typing import List, Dict, Any
from loguru import logger
from nanobio_studio.app.schemas.lnp_record import LNPRecord
from nanobio_studio.app.qc.validators import QCValidator


class JSONImporter:
    """Import and validate JSON LNP records."""
    
    def __init__(self):
        """Initialize importer."""
        self.validator = QCValidator()
        self.logger = logger.bind(module="JSONImporter")
    
    def import_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Import JSON file containing LNP records.
        
        Args:
            file_path: Path to JSON file
        
        Returns:
            List of validated records
        """
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            
            return self.import_file_from_data(data)
        
        except Exception as e:
            self.logger.error(f"Failed to import JSON file {file_path}: {e}")
            raise
    
    def import_file_from_data(self, data: Any) -> List[Dict[str, Any]]:
        """
        Import JSON data containing LNP records (from dict or list).
        
        Args:
            data: Dictionary or list of LNP records
        
        Returns:
            List of validated records
        """
        # Handle both single record and list of records
        records = data if isinstance(data, list) else [data]
        
        validated_records = []
        for i, record in enumerate(records):
            try:
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
                self.logger.info(f"Record {i} validated: {qc_result['overall_status']}")
            
            except Exception as e:
                self.logger.error(f"Record {i} validation failed: {e}")
                validated_records.append({
                    "original": record,
                    "validation_error": str(e),
                    "qc_status": "fail",
                })
        
        self.logger.info(f"Imported {len(validated_records)} records")
        return validated_records
