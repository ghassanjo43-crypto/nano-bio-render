"""
Training dataframe builder

Constructs ML-ready training dataframes from extracted features and encodings
"""

from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from loguru import logger

from .features import FeatureExtractor, ExtractedFeatures
from .encoders import CategoricalEncoder, NumericEncoder, EncodingMetadata

logger = logger.bind(module="ml.dataframe_builder")


class TrainingDataframeBuilder:
    """Build ML-ready training dataframes from LNP records"""
    
    # Numeric features to include
    NUMERIC_FEATURES = [
        "ionizable_ratio",
        "helper_ratio",
        "sterol_ratio",
        "peg_ratio",
        "lipid_ratio_variance",
        "ionizable_helper_ratio",
        "sterol_peg_ratio",
        "particle_size_nm",
        "pdi",
        "zeta_potential_mv",
        "encapsulation_efficiency_pct",
        "temperature_c",
        "buffer_ph",
    ]
    
    # Categorical features to encode
    CATEGORICAL_FEATURES = [
        "payload_type",
    ]
    
    # Target variables for different prediction tasks
    TARGET_VARIABLES = {
        "particle_size": "particle_size_nm",
        "toxicity": "toxicity_score",
        "uptake": "uptake_score",
    }
    
    def __init__(self, scaler_type: str = "minmax"):
        """
        Initialize dataframe builder
        
        Args:
            scaler_type: 'minmax' or 'standard' for numeric scaling
        """
        self.logger = logger
        self.feature_extractor = FeatureExtractor()
        self.categorical_encoder = CategoricalEncoder()
        self.numeric_encoder = NumericEncoder(scaler_type=scaler_type)
        self.encoding_metadata: Optional[EncodingMetadata] = None
        self.df: Optional[pd.DataFrame] = None
    
    def build_from_records(
        self,
        records: List[Dict[str, Any]],
        fit_scalers: bool = True,
        target_task: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Build training dataframe from complete LNP records
        
        Args:
            records: List of LNP record dictionaries
            fit_scalers: Whether to fit scalers on this data (True for training data)
            target_task: 'particle_size', 'toxicity', 'uptake', or None for all
            
        Returns:
            ML-ready pandas DataFrame
        """
        try:
            # Extract features
            self.logger.info(f"Extracting features from {len(records)} records")
            features_list = self.feature_extractor.extract_batch(records)
            
            if not features_list:
                raise ValueError("No features extracted from records")
            
            # Prepare data for encoding
            feature_dicts = [f.to_dict() for f in features_list]
            
            # Encode categorical features
            self.logger.info("Encoding categorical features")
            for row in feature_dicts:
                if row.get("payload_type_encoded") is None:
                    payload_type = records[feature_dicts.index(row)].get("formulation", {}).get("payload_info", {}).get("payload_type")
                    row["payload_type_encoded"] = self.categorical_encoder.encode_payload_type(payload_type)
            
            # Fit and transform numeric features
            self.logger.info(f"Processing {len(self.NUMERIC_FEATURES)} numeric features")
            if fit_scalers:
                self.numeric_encoder.fit(feature_dicts, self.NUMERIC_FEATURES)
            
            feature_dicts = self.numeric_encoder.transform(feature_dicts)
            
            # Create DataFrame
            self.df = pd.DataFrame(feature_dicts)
            
            # Drop rows with missing targets if specific task
            if target_task and target_task in self.TARGET_VARIABLES:
                target_col = self.TARGET_VARIABLES[target_task]
                initial_count = len(self.df)
                self.df = self.df.dropna(subset=[target_col])
                final_count = len(self.df)
                self.logger.info(f"Dropped {initial_count - final_count} rows with missing {target_col}")
            else:
                # Drop rows with any NaN in target columns
                self.df = self.df.dropna(subset=["toxicity_score", "uptake_score", "particle_size_nm"], how="all")
            
            # Store encoding metadata
            self.encoding_metadata = self._get_combined_metadata()
            
            self.logger.info(f"Built dataframe with shape {self.df.shape}")
            return self.df
        
        except Exception as e:
            self.logger.error(f"Error building training dataframe: {e}")
            raise
    
    def build_from_features(
        self,
        features: List[ExtractedFeatures],
        fit_scalers: bool = False,
    ) -> pd.DataFrame:
        """
        Build dataframe from pre-extracted features
        
        Args:
            features: List of ExtractedFeatures objects
            fit_scalers: Whether to fit scalers
            
        Returns:
            ML-ready DataFrame
        """
        feature_dicts = [f.to_dict() for f in features]
        
        # Encode categorical features
        for row in feature_dicts:
            # Note: This assumes payload_type_encoded would be set during encoding
            pass
        
        # Transform numeric features
        if fit_scalers:
            self.numeric_encoder.fit(feature_dicts, self.NUMERIC_FEATURES)
        
        feature_dicts = self.numeric_encoder.transform(feature_dicts)
        self.df = pd.DataFrame(feature_dicts)
        self.encoding_metadata = self._get_combined_metadata()
        
        return self.df
    
    def get_features_for_task(self, task: str) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Get features and target for a specific prediction task
        
        Args:
            task: 'particle_size', 'toxicity', or 'uptake'
            
        Returns:
            Tuple of (X features DataFrame, y target Series)
        """
        if self.df is None:
            raise ValueError("Dataframe not built yet - call build_from_records first")
        
        if task not in self.TARGET_VARIABLES:
            raise ValueError(f"Unknown task: {task}. Choose from {list(self.TARGET_VARIABLES.keys())}")
        
        target_col = self.TARGET_VARIABLES[task]
        
        # Get rows with valid target
        valid_rows = self.df.dropna(subset=[target_col])
        
        # Feature columns (exclude ID and target variables)
        exclude_cols = {"formulation_id", "toxicity_score", "uptake_score", "transfection_efficiency"}
        feature_cols = [c for c in self.df.columns if c not in exclude_cols]
        
        X = valid_rows[feature_cols]
        y = valid_rows[target_col]
        
        self.logger.info(f"Dataset for {task}: {len(X)} samples, {len(feature_cols)} features")
        return X, y
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about the built dataframe"""
        if self.df is None:
            return {"status": "not_built"}
        
        return {
            "shape": self.df.shape,
            "columns": list(self.df.columns),
            "numeric_features": self.NUMERIC_FEATURES,
            "categorical_features": self.CATEGORICAL_FEATURES,
            "missing_values": self.df.isnull().sum().to_dict(),
            "summary_stats": self.df.describe().to_dict(),
        }
    
    def _get_combined_metadata(self) -> EncodingMetadata:
        """Combine categorical and numeric encoder metadata"""
        cat_meta = self.categorical_encoder.get_metadata()
        num_meta = self.numeric_encoder.get_metadata()
        
        return EncodingMetadata(
            lipid_class_encoder=cat_meta.lipid_class_encoder,
            payload_type_encoder=cat_meta.payload_type_encoder,
            assay_type_encoder=cat_meta.assay_type_encoder,
            preparation_method_encoder=cat_meta.preparation_method_encoder,
            numeric_scaler_type=num_meta.numeric_scaler_type,
            feature_stats=num_meta.feature_stats,
        )
