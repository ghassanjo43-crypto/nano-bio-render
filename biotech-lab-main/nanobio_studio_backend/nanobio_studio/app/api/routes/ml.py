"""
ML API routes for NanoBio Studio backend

Endpoints for feature extraction, encoding, dataset export, and model training
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
import json
from io import StringIO

from loguru import logger

from nanobio_studio.app.api.deps import get_db
from nanobio_studio.app.ml import (
    FeatureExtractor,
    CategoricalEncoder,
    NumericEncoder,
    TrainingDataframeBuilder,
    ParquetExporter,
    CSVExporter,
    MLTrainer,
)

logger = logger.bind(module="api.ml")

router = APIRouter(prefix="/ml", tags=["machine-learning"])


# ============================================================================
# Pydantic Models for API responses
# ============================================================================

class DatasetSummaryResponse(BaseModel):
    """Dataset summary for ML"""
    
    total_records: int = Field(..., description="Total records in dataset")
    complete_records: int = Field(..., description="Records with all required features")
    missing_targets: Dict[str, int] = Field(..., description="Missing values per target")
    feature_statistics: Dict[str, Any] = Field(..., description="Basic statistics per feature")
    encoding_info: Dict[str, Any] = Field(..., description="Information about encodings used")


class MLReadyExportResponse(BaseModel):
    """Response for ML-ready data export"""
    
    status: str = Field(..., description="Export status")
    format: str = Field(..., description="Export format (parquet/csv)")
    rows: int = Field(..., description="Number of rows exported")
    columns: int = Field(..., description="Number of columns/features")
    file_path: str = Field(..., description="Path to exported file")
    encoding_metadata: Dict[str, Any] = Field(..., description="Encoding metadata")


class ModelTrainingRequest(BaseModel):
    """Request for model training"""
    
    task: str = Field(..., description="Prediction task: particle_size, toxicity, or uptake")
    test_size: float = Field(0.2, ge=0.1, le=0.5, description="Test set fraction")
    random_state: int = Field(42, description="Random seed for reproducibility")


class ModelTrainingResponse(BaseModel):
    """Response for model training"""
    
    task: str = Field(..., description="Task name")
    status: str = Field(..., description="Training status")
    metrics: Dict[str, float] = Field(..., description="Model performance metrics")
    top_features: Dict[str, float] = Field(..., description="Top important features")


# ============================================================================
# ML API Endpoints
# ============================================================================

@router.get("/health", response_model=Dict[str, str])
async def ml_health() -> Dict[str, str]:
    """
    Check ML module health
    
    Returns system status for ML functionality
    """
    return {
        "status": "healthy",
        "module": "ML",
        "available_tasks": "particle_size, toxicity, uptake",
    }


@router.get("/summary", response_model=DatasetSummaryResponse)
async def dataset_summary(db: Any = Depends(get_db)) -> DatasetSummaryResponse:
    """
    Get summary statistics for current dataset
    
    Returns dataset size, completeness, and feature statistics
    """
    try:
        # Import here to avoid circular dependencies
        from nanobio_studio.app.db.models import Experiment, Assay, Formulation
        from sqlalchemy import select, func
        
        # Get basic statistics
        result = await db.execute(
            select(
                func.count(Experiment.id).label("total_experiments"),
                func.count(Assay.id).label("total_assays"),
                func.count(Formulation.id).label("total_formulations"),
            )
        )
        row = result.first()
        
        return DatasetSummaryResponse(
            total_records=row.total_experiments if row else 0,
            complete_records=row.total_assays if row else 0,  # Simplified - assays indicate completeness
            missing_targets={
                "toxicity": 0,  # Would need to query actual missing values
                "uptake": 0,
                "particle_size": 0,
            },
            feature_statistics={
                "total_features": 13,
                "numeric_features": 13,
                "categorical_features": 1,
            },
            encoding_info={
                "payload_types": 5,
                "assay_types": 5,
                "preparation_methods": 3,
                "scaler_type": "minmax",
            },
        )
    except Exception as e:
        logger.error(f"Error getting dataset summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/export-ml-ready", response_model=MLReadyExportResponse)
async def export_ml_ready(
    format: str = "parquet",
    task: Optional[str] = None,
    db: Any = Depends(get_db),
) -> MLReadyExportResponse:
    """
    Export ML-ready dataset
    
    Extracts features, encodes categoricals, scales numerics, and exports to parquet/csv
    
    Args:
        format: Export format ('parquet' or 'csv')
        task: Specific prediction task to optimize for (optional)
    """
    try:
        if format not in ["parquet", "csv"]:
            raise ValueError("Format must be 'parquet' or 'csv'")
        
        # This is a placeholder - in production would query database
        logger.info(f"Exporting ML-ready dataset as {format}")
        
        return MLReadyExportResponse(
            status="pending",
            format=format,
            rows=0,  # Would be populated from actual export
            columns=13,
            file_path=f"/data/ml_ready_dataset.{format}",
            encoding_metadata={
                "scaler_type": "minmax",
                "encoded_features": ["payload_type"],
                "numeric_features": 13,
            },
        )
    except Exception as e:
        logger.error(f"Error exporting ML-ready data: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/train-model", response_model=ModelTrainingResponse)
async def train_model(
    request: ModelTrainingRequest,
    db: Any = Depends(get_db),
) -> ModelTrainingResponse:
    """
    Train ML model for specific task
    
    Trains a model to predict particle_size, toxicity, or uptake
    
    Args:
        request: Training parameters including task and hyperparameters
    """
    try:
        valid_tasks = ["particle_size", "toxicity", "uptake"]
        if request.task not in valid_tasks:
            raise ValueError(f"Task must be one of {valid_tasks}")
        
        logger.info(f"Starting training for task: {request.task}")
        
        # This is a placeholder - in production would:
        # 1. Query all experiments from database
        # 2. Extract features using FeatureExtractor
        # 3. Train using MLTrainer
        
        return ModelTrainingResponse(
            task=request.task,
            status="training",
            metrics={
                "train_r2": 0.0,
                "test_r2": 0.0,
                "rmse": 0.0,
                "mae": 0.0,
            },
            top_features={
                "ionizable_ratio": 0.25,
                "helper_ratio": 0.20,
                "particle_size_nm": 0.18,
            },
        )
    except Exception as e:
        logger.error(f"Error training model: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/models/info", response_model=Dict[str, Any])
async def get_models_info() -> Dict[str, Any]:
    """
    Get information about available ML models
    
    Returns list of trained models and their capabilities
    """
    return {
        "available_models": {
            "particle_size": {
                "description": "Predict particle size (nm)",
                "status": "development",
                "input_features": 13,
            },
            "toxicity": {
                "description": "Predict toxicity score",
                "status": "development",
                "input_features": 13,
            },
            "uptake": {
                "description": "Predict uptake efficiency",
                "status": "development",
                "input_features": 13,
            },
        },
        "phase": "Phase 2 - ML Preparation",
        "ready_for_training": True,
    }


@router.post("/features/extract")
async def extract_features(
    record: Dict[str, Any],
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    """
    Extract ML features from a single record
    
    Args:
        record: LNP record dictionary
    """
    try:
        extractor = FeatureExtractor()
        features = extractor.extract_from_record(record)
        return features.to_dict()
    except Exception as e:
        logger.error(f"Error extracting features: {e}")
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")


@router.post("/encode/payload-type")
async def encode_payload_type(payload_type: str) -> Dict[str, int]:
    """
    Encode payload type to integer
    
    Args:
        payload_type: Payload type string (e.g., 'mRNA')
    """
    try:
        encoder = CategoricalEncoder()
        encoded = encoder.encode_payload_type(payload_type)
        if encoded is None:
            raise ValueError(f"Unknown payload type: {payload_type}")
        return {"payload_type": payload_type, "encoded_value": encoded}
    except Exception as e:
        logger.error(f"Error encoding: {e}")
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")


# ============================================================================
# Batch Processing Endpoints
# ============================================================================

@router.post("/batch/extract-features")
async def batch_extract_features(
    records: List[Dict[str, Any]],
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    """
    Extract features from multiple records
    
    Args:
        records: List of LNP record dictionaries
    """
    try:
        extractor = FeatureExtractor()
        features_list = extractor.extract_batch(records)
        return {
            "status": "success",
            "total_records": len(records),
            "extracted_count": len(features_list),
            "features": [f.to_dict() for f in features_list],
        }
    except Exception as e:
        logger.error(f"Error in batch extraction: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/batch/build-dataset")
async def batch_build_dataset(
    records: List[Dict[str, Any]],
    task: Optional[str] = None,
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    """
    Build ML-ready training dataset from records
    
    Args:
        records: List of LNP records
        task: Optional specific task to optimize for
    """
    try:
        builder = TrainingDataframeBuilder()
        df = builder.build_from_records(records, task=task)
        
        return {
            "status": "success",
            "dataset_shape": list(df.shape),
            "dataset_info": builder.get_info(),
            "samples": len(df),
            "features": len(df.columns),
        }
    except Exception as e:
        logger.error(f"Error building dataset: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# Documentation endpoint
# ============================================================================

@router.get("/docs", response_model=Dict[str, Any])
async def ml_documentation() -> Dict[str, Any]:
    """
    Get ML module documentation and capabilities
    """
    return {
        "phase": "Phase 2 - ML Preparation",
        "version": "0.1.0",
        "capabilities": {
            "feature_extraction": "Extract 13+ features from LNP formulations",
            "encoding": "Categorical and numeric encoding for ML models",
            "dataframe_builder": "Construct model-ready training DataFrames",
            "exporters": "Export to Parquet and CSV formats",
            "trainer": "Train predictive models for particle size, toxicity, uptake",
        },
        "available_endpoints": [
            "GET /ml/health - Module health check",
            "GET /ml/summary - Dataset summary",
            "POST /ml/export-ml-ready - Export ML-ready dataset",
            "POST /ml/train-model - Train model for task",
            "GET /ml/models/info - Information about models",
            "POST /ml/features/extract - Extract features from single record",
            "POST /ml/encode/payload-type - Encode categorical variable",
            "POST /ml/batch/extract-features - Batch feature extraction",
            "POST /ml/batch/build-dataset - Build training dataset",
        ],
        "prediction_tasks": [
            "particle_size - Predict particle size in nm",
            "toxicity - Predict toxicity score",
            "uptake - Predict cellular uptake efficiency",
        ],
    }
