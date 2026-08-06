"""
Ingestion routes for JSON and CSV imports.
"""
import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from loguru import logger
from nanobio_studio.app.ingestion.json_importer import JSONImporter
from nanobio_studio.app.ingestion.csv_importer import CSVImporter
from nanobio_studio.app.core.logging import get_logger

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
log = get_logger("ingestion.routes")


@router.post("/json-upload")
async def upload_json(file: UploadFile = File(...)) -> dict:
    """
    Upload and import JSON file with LNP records.
    
    Args:
        file: JSON file to upload
    
    Returns:
        Import results with validation status
    """
    try:
        contents = await file.read()
        data = json.loads(contents)
        
        importer = JSONImporter()
        records = importer.import_file_from_data(data)
        
        return {
            "status": "success",
            "total_records": len(records),
            "passed": sum(1 for r in records if r.get("qc_status") == "pass"),
            "warnings": sum(1 for r in records if r.get("qc_status") == "warning"),
            "failed": sum(1 for r in records if r.get("qc_status") == "fail"),
            "records": records,
        }
    except Exception as e:
        log.error(f"JSON import error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/csv-upload")
async def upload_csv(file: UploadFile = File(...)) -> dict:
    """
    Upload and import CSV file with LNP records (flat format).
    
    Args:
        file: CSV file to upload
    
    Returns:
        Import results with validation status
    """
    try:
        import tempfile
        import os
        
        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            contents = await file.read()
            tmp.write(contents)
            temp_path = tmp.name
        
        try:
            importer = CSVImporter()
            records = importer.import_file(temp_path)
            
            return {
                "status": "success",
                "total_records": len(records),
                "passed": sum(1 for r in records if r.get("qc_status") == "pass"),
                "warnings": sum(1 for r in records if r.get("qc_status") == "warning"),
                "failed": sum(1 for r in records if r.get("qc_status") == "fail"),
                "records": records,
            }
        finally:
            os.unlink(temp_path)
    
    except Exception as e:
        log.error(f"CSV import error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
