"""
Categorical and numeric encoding for ML preparation

Encodes categorical variables and normalizes numeric features
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
from pathlib import Path

from sklearn.preprocessing import LabelEncoder, StandardScaler, MinMaxScaler
from loguru import logger

logger = logger.bind(module="ml.encoders")


@dataclass
class EncodingMetadata:
    """Metadata about encoding schemes"""
    
    lipid_class_encoder: Optional[Dict[str, int]] = None
    payload_type_encoder: Optional[Dict[str, int]] = None
    assay_type_encoder: Optional[Dict[str, int]] = None
    preparation_method_encoder: Optional[Dict[str, int]] = None
    
    numeric_scaler_type: str = "minmax"  # 'minmax' or 'standard'
    feature_stats: Dict[str, Dict[str, float]] = None  # min, max, mean, std per feature
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return {
            "lipid_class_encoder": self.lipid_class_encoder,
            "payload_type_encoder": self.payload_type_encoder,
            "assay_type_encoder": self.assay_type_encoder,
            "preparation_method_encoder": self.preparation_method_encoder,
            "numeric_scaler_type": self.numeric_scaler_type,
            "feature_stats": self.feature_stats or {},
        }


class CategoricalEncoder:
    """Encode categorical variables for ML models"""
    
    # Standard categories based on domain model
    LIPID_CLASSES = ["ionizable", "helper", "sterol", "peg"]
    PAYLOAD_TYPES = ["mRNA", "siRNA", "DNA", "protein", "small_molecule"]
    ASSAY_TYPES = ["uptake", "transfection", "toxicity", "biodistribution", "cytokine_response"]
    PREPARATION_METHODS = ["microfluidic", "manual_mixing", "ethanol_injection"]
    
    def __init__(self):
        """Initialize categorical encoder with domain knowledge"""
        self.logger = logger
        self.encoders: Dict[str, Dict[str, int]] = {}
        self._initialize_encoders()
    
    def _initialize_encoders(self) -> None:
        """Initialize standard encoders for known categorical variables"""
        self.encoders["lipid_class"] = {name: idx for idx, name in enumerate(self.LIPID_CLASSES)}
        self.encoders["payload_type"] = {name: idx for idx, name in enumerate(self.PAYLOAD_TYPES)}
        self.encoders["assay_type"] = {name: idx for idx, name in enumerate(self.ASSAY_TYPES)}
        self.encoders["preparation_method"] = {name: idx for idx, name in enumerate(self.PREPARATION_METHODS)}
    
    def encode_payload_type(self, payload_type: Optional[str]) -> Optional[int]:
        """
        Encode payload type to integer
        
        Args:
            payload_type: Payload type string (e.g., 'mRNA')
            
        Returns:
            Integer encoding or None if unknown
        """
        if not payload_type:
            return None
        
        encoded = self.encoders["payload_type"].get(payload_type)
        if encoded is None:
            self.logger.warning(f"Unknown payload type: {payload_type}")
            return None
        return encoded
    
    def encode_assay_type(self, assay_type: Optional[str]) -> Optional[int]:
        """Encode assay type to integer"""
        if not assay_type:
            return None
        
        encoded = self.encoders["assay_type"].get(assay_type)
        if encoded is None:
            self.logger.warning(f"Unknown assay type: {assay_type}")
            return None
        return encoded
    
    def encode_preparation_method(self, method: Optional[str]) -> Optional[int]:
        """Encode preparation method to integer"""
        if not method:
            return None
        
        encoded = self.encoders["preparation_method"].get(method)
        if encoded is None:
            self.logger.warning(f"Unknown preparation method: {method}")
            return None
        return encoded
    
    def get_metadata(self) -> EncodingMetadata:
        """Get encoding metadata"""
        return EncodingMetadata(
            lipid_class_encoder=self.encoders["lipid_class"],
            payload_type_encoder=self.encoders["payload_type"],
            assay_type_encoder=self.encoders["assay_type"],
            preparation_method_encoder=self.encoders["preparation_method"],
        )


class NumericEncoder:
    """Normalize and scale numeric features for ML models"""
    
    def __init__(self, scaler_type: str = "minmax"):
        """
        Initialize numeric encoder
        
        Args:
            scaler_type: 'minmax' for MinMaxScaler or 'standard' for StandardScaler
        """
        self.logger = logger
        self.scaler_type = scaler_type
        self.scaler = MinMaxScaler() if scaler_type == "minmax" else StandardScaler()
        self.fitted = False
        self.feature_names: List[str] = []
        self.feature_stats: Dict[str, Dict[str, float]] = {}
    
    def fit(self, data: List[Dict[str, float]], features: List[str]) -> None:
        """
        Fit the scaler to training data
        
        Args:
            data: List of feature dictionaries
            features: List of numeric feature names to fit
        """
        import numpy as np
        
        self.feature_names = features
        
        # Extract feature columns
        feature_matrix = np.array(
            [[row.get(feat, 0.0) for feat in features] for row in data]
        )
        
        # Fit scaler
        self.scaler.fit(feature_matrix)
        self.fitted = True
        
        # Compute statistics
        for i, feat_name in enumerate(features):
            self.feature_stats[feat_name] = {
                "min": float(feature_matrix[:, i].min()),
                "max": float(feature_matrix[:, i].max()),
                "mean": float(feature_matrix[:, i].mean()),
                "std": float(feature_matrix[:, i].std()),
            }
        
        self.logger.info(f"Fitted {self.scaler_type} scaler for {len(features)} features")
    
    def transform(self, data: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """
        Transform numeric features using fitted scaler
        
        Args:
            data: List of feature dictionaries
            
        Returns:
            List of scaled feature dictionaries
        """
        if not self.fitted:
            self.logger.warning("Scaler not fitted - returning original data")
            return data
        
        import numpy as np
        
        # Extract and scale
        feature_matrix = np.array(
            [[row.get(feat, 0.0) for feat in self.feature_names] for row in data]
        )
        scaled_matrix = self.scaler.transform(feature_matrix)
        
        # Convert back to list of dicts
        result = []
        for i, row in enumerate(data):
            scaled_row = dict(row)
            for j, feat_name in enumerate(self.feature_names):
                scaled_row[feat_name] = float(scaled_matrix[i, j])
            result.append(scaled_row)
        
        return result
    
    def transform_single(self, row: Dict[str, float]) -> Dict[str, float]:
        """Transform a single row of features"""
        return self.transform([row])[0]
    
    def get_metadata(self) -> EncodingMetadata:
        """Get encoding metadata including feature statistics"""
        return EncodingMetadata(
            numeric_scaler_type=self.scaler_type,
            feature_stats=self.feature_stats,
        )
