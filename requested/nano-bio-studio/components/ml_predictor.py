"""
ML Predictor Component - Integrates trained ML models with nanoparticle designs
Converts design parameters to ML features and generates predictions
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional, List
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DesignToFeatureConverter:
    """Convert nanoparticle design parameters to ML-ready features"""
    
    # Feature names expected by ML models
    # Sprint 1: Added osmolarity, hemolysis, improved_half_life, isoelectric_point
    NUMERIC_FEATURES = [
        # Original 12 features
        "size_nm",
        "charge_mv",
        "peg_density_pct",
        "coating_thickness_nm",
        "encapsulation_pct",
        "zeta_potential_mv",
        "pdi",
        "surface_area_nm2",
        "drug_loading_pct",
        "stability_score",
        "biodegradation_days",
        "targeting_strength",
        # Sprint 1: New features (4 critical parameters)
        "osmolarity_mosm_kg",
        "hemolysis_score",
        "blood_half_life_hours",
        "isoelectric_point_ph",
    ]
    
    # Feature normalization ranges (min, max)
    FEATURE_RANGES = {
        # Original ranges
        "size_nm": (50, 200),
        "charge_mv": (-50, 50),
        "peg_density_pct": (0, 100),
        "coating_thickness_nm": (0, 20),
        "encapsulation_pct": (50, 100),
        "zeta_potential_mv": (-50, 0),
        "pdi": (0.1, 0.5),
        "surface_area_nm2": (500, 5000),
        "drug_loading_pct": (0, 100),
        "stability_score": (0, 100),
        "biodegradation_days": (7, 365),
        "targeting_strength": (0, 100),
        # Sprint 1: New ranges
        "osmolarity_mosm_kg": (200, 500),        # Safe: 250-350, acceptable: 200-400
        "hemolysis_score": (0, 100),             # 0 = none, 100 = severe
        "blood_half_life_hours": (0.1, 48),      # 0.1 hours to 48 hours
        "isoelectric_point_ph": (3, 9),          # pH range for biological systems
    }
    
    @staticmethod
    def design_to_features(design: Dict) -> pd.DataFrame:
        """
        Convert design dictionary to ML features DataFrame
        
        Args:
            design: Design parameters dictionary from session state
            
        Returns:
            DataFrame with single row of normalized features
        """
        try:
            # ================================================================
            # ORIGINAL 12 FEATURES
            # ================================================================
            features = {
                "size_nm": float(design.get("Size", 100)),
                "charge_mv": float(design.get("Charge", -30)),
                "peg_density_pct": float(design.get("PEG_Density", 50)),
                "coating_thickness_nm": float(design.get("CoatingThickness") or design.get("Coating_Thickness") or 5),
                "encapsulation_pct": float(design.get("Encapsulation", 85)),
                "zeta_potential_mv": float(design.get("Zeta", -30)),
                "pdi": float(design.get("PDI", 0.15)),
                "surface_area_nm2": float(design.get("Surface_Area", 2000)),
                "drug_loading_pct": float(design.get("Drug", 50)) if isinstance(design.get("Drug"), (int, float)) else 50.0,
                "stability_score": float(design.get("Stability", 80)),
                "biodegradation_days": float(design.get("Biodegradation_Days", 90)),
                "targeting_strength": float(design.get("Targeting_Strength", 70)),
            }
            
            # ================================================================
            # SPRINT 1: NEW FEATURES (4 critical parameters)
            # ================================================================
            
            # Import Sprint 1 calculators
            from components.osmolarity_calculator import calculate_osmolarity
            from components.blood_safety_assessor import calculate_hemolysis_risk
            from components.charge_predictors import predict_improved_blood_half_life, calculate_isoelectric_point
            
            # 1. Osmolarity (0-500 mOsm/kg)
            osmolarity_result = calculate_osmolarity(design)
            features["osmolarity_mosm_kg"] = float(osmolarity_result.get("osmolarity_mosm_kg", 300))
            
            # 2. Hemolysis Score (0-100, higher = worse)
            hemolysis_result = calculate_hemolysis_risk(design)
            features["hemolysis_score"] = float(hemolysis_result.get("hemolysis_score", 0))
            
            # 3. Blood Half-Life (0.1-48 hours)
            halflife_result = predict_improved_blood_half_life(design)
            features["blood_half_life_hours"] = float(halflife_result.get("blood_half_life_hours", 2.0))
            
            # 4. Isoelectric Point (pH 3-9)
            pI_result = calculate_isoelectric_point(design)
            features["isoelectric_point_ph"] = float(pI_result.get("isoelectric_point_pH", 7.4))
            
            # ================================================================
            # NORMALIZE FEATURES
            # ================================================================
            
            # Normalize features to 0-1 range
            normalized_features = {}
            for feature_name, value in features.items():
                if feature_name in DesignToFeatureConverter.FEATURE_RANGES:
                    min_val, max_val = DesignToFeatureConverter.FEATURE_RANGES[feature_name]
                    normalized = (value - min_val) / (max_val - min_val)
                    # Clamp to [0, 1]
                    normalized_features[feature_name] = max(0, min(1, normalized))
                else:
                    normalized_features[feature_name] = value
            
            # Create DataFrame with single row
            df = pd.DataFrame([normalized_features])
            
            logger.info(f"✅ Converted design to {len(df.columns)} features (12 original + 4 Sprint 1)")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error converting design to features: {e}")
            # Return empty/default features on error
            default_features = {f: 0.5 for f in DesignToFeatureConverter.NUMERIC_FEATURES}
            return pd.DataFrame([default_features])


class MLPredictor:
    """Load and use trained ML models for predictions"""
    
    def __init__(self, model_dir: str = "models"):
        """Initialize ML predictor"""
        self.model_dir = Path(model_dir)
        self.models = {}
        self.feature_converter = DesignToFeatureConverter()
        self.available_tasks = ["toxicity", "uptake", "particle_size"]
        
        logger.info(f"🤖 ML Predictor initialized. Model dir: {self.model_dir}")
    
    def load_models(self) -> Dict[str, bool]:
        """
        Load trained models from disk
        
        Returns:
            Dictionary with task names and load status
        """
        status = {}
        
        for task in self.available_tasks:
            try:
                model_path = self.model_dir / f"{task}_model.pkl"
                
                if model_path.exists():
                    import joblib
                    self.models[task] = joblib.load(str(model_path))
                    status[task] = True
                    logger.info(f"✅ Loaded {task} model")
                else:
                    status[task] = False
                    logger.warning(f"⚠️ {task} model not found at {model_path}")
                    
            except Exception as e:
                status[task] = False
                logger.error(f"❌ Error loading {task} model: {e}")
        
        return status
    
    def predict_toxicity(self, design: Dict) -> Tuple[float, str]:
        """
        Predict toxicity score for nanoparticle design
        
        Args:
            design: Design parameters dictionary
            
        Returns:
            Tuple of (toxicity_score_0_to_10, risk_level_str)
        """
        try:
            # Convert to features
            features_df = self.feature_converter.design_to_features(design)
            
            # Use heuristic if model not available
            if "toxicity" not in self.models:
                return self._estimate_toxicity_heuristic(design)
            
            # Get model prediction (assuming 0-1 scale)
            model = self.models["toxicity"]
            predictions = model.predict(features_df)
            
            # Scale to 0-10
            toxicity_score = float(predictions[0]) * 10
            
            # Determine risk level
            if toxicity_score < 2:
                risk_level = "Very Low"
            elif toxicity_score < 4:
                risk_level = "Low"
            elif toxicity_score < 6:
                risk_level = "Moderate"
            elif toxicity_score < 8:
                risk_level = "High"
            else:
                risk_level = "Very High"
            
            logger.info(f"📊 Toxicity prediction: {toxicity_score:.1f}/10 ({risk_level})")
            return toxicity_score, risk_level
            
        except Exception as e:
            logger.warning(f"⚠️ Toxicity prediction failed: {e}. Using heuristic.")
            return self._estimate_toxicity_heuristic(design)
    
    def predict_uptake(self, design: Dict) -> Tuple[float, str]:
        """
        Predict cellular uptake efficiency for nanoparticle design
        
        Args:
            design: Design parameters dictionary
            
        Returns:
            Tuple of (uptake_efficiency_percentage, quality_str)
        """
        try:
            # Convert to features
            features_df = self.feature_converter.design_to_features(design)
            
            # Use heuristic if model not available
            if "uptake" not in self.models:
                return self._estimate_uptake_heuristic(design)
            
            # Get model prediction (assuming 0-1 scale)
            model = self.models["uptake"]
            predictions = model.predict(features_df)
            
            # Scale to percentage
            uptake_pct = float(predictions[0]) * 100
            
            # Determine quality
            if uptake_pct > 85:
                quality = "Excellent"
            elif uptake_pct > 75:
                quality = "Good"
            elif uptake_pct > 65:
                quality = "Satisfactory"
            elif uptake_pct > 50:
                quality = "Acceptable"
            else:
                quality = "Poor"
            
            logger.info(f"🎯 Uptake prediction: {uptake_pct:.1f}% ({quality})")
            return uptake_pct, quality
            
        except Exception as e:
            logger.warning(f"⚠️ Uptake prediction failed: {e}. Using heuristic.")
            return self._estimate_uptake_heuristic(design)
    
    def predict_particle_size(self, design: Dict) -> float:
        """
        Predict particle size for nanoparticle design
        
        Args:
            design: Design parameters dictionary
            
        Returns:
            Predicted particle size in nm
        """
        try:
            # Convert to features
            features_df = self.feature_converter.design_to_features(design)
            
            # Use design value if model not available
            if "particle_size" not in self.models:
                return float(design.get("Size", 100))
            
            # Get model prediction
            model = self.models["particle_size"]
            predictions = model.predict(features_df)
            
            predicted_size = float(predictions[0])
            logger.info(f"📏 Particle size prediction: {predicted_size:.1f} nm")
            return predicted_size
            
        except Exception as e:
            logger.warning(f"⚠️ Particle size prediction failed: {e}")
            return float(design.get("Size", 100))
    
    @staticmethod
    def _estimate_toxicity_heuristic(design: Dict) -> Tuple[float, str]:
        """Fallback toxicity estimation using rules-based heuristic"""
        score = 0.0
        
        # Size risk
        size = float(design.get("Size", 100))
        if size < 50:
            score += 2.5
        elif size > 150:
            score += 1.5
        
        # Charge risk
        charge = abs(float(design.get("Charge", -30)))
        if charge > 35:
            score += 2.5
        elif charge > 20:
            score += 1.0
        
        # PEG density (high PEG = lower toxicity)
        peg = float(design.get("PEG_Density", 50))
        score += max(0, (100 - peg) / 50)  # Lower PEG = higher toxicity risk
        
        # Encapsulation (high encapsulation = lower toxicity)
        encap = float(design.get("Encapsulation", 85))
        score += max(0, (100 - encap) / 20)
        
        # Clamp to 0-10
        score = max(0, min(10, score))
        
        # Risk level
        if score < 2:
            risk = "Very Low"
        elif score < 4:
            risk = "Low"
        elif score < 6:
            risk = "Moderate"
        elif score < 8:
            risk = "High"
        else:
            risk = "Very High"
        
        return score, risk
    
    @staticmethod
    def _estimate_uptake_heuristic(design: Dict) -> Tuple[float, str]:
        """Fallback uptake estimation using rules-based heuristic"""
        uptake = 50.0  # Base uptake
        
        # Optimal size is 80-120 nm
        size = float(design.get("Size", 100))
        if 80 <= size <= 120:
            uptake += 25
        elif 60 <= size <= 150:
            uptake += 15
        
        # PEG density enhances stealth but reduces targeting
        peg = float(design.get("PEG_Density", 50))
        if peg >= 50:
            uptake += 10
        
        # Targeting ligand presence
        ligand = design.get("Surface Functionalization (Ligand)", "None")
        if ligand != "None":
            uptake += 15
        
        # Encapsulation efficiency
        encap = float(design.get("Encapsulation", 85))
        uptake += (encap - 50) / 5
        
        # Clamp to 0-100
        uptake = max(0, min(100, uptake))
        
        # Quality
        if uptake > 85:
            quality = "Excellent"
        elif uptake > 75:
            quality = "Good"
        elif uptake > 65:
            quality = "Satisfactory"
        elif uptake > 50:
            quality = "Acceptable"
        else:
            quality = "Poor"
        
        return uptake, quality
    
    def get_model_status(self) -> Dict[str, bool]:
        """Get status of all available models"""
        if not self.models:
            self.load_models()
        
        return {task: task in self.models for task in self.available_tasks}
    
    def get_predictions_summary(self, design: Dict) -> Dict:
        """Get all predictions for a design in one call"""
        try:
            tox_score, tox_level = self.predict_toxicity(design)
            uptake_pct, uptake_quality = self.predict_uptake(design)
            size_nm = self.predict_particle_size(design)
            
            return {
                "toxicity_score": tox_score,
                "toxicity_level": tox_level,
                "uptake_efficiency": uptake_pct,
                "uptake_quality": uptake_quality,
                "predicted_size_nm": size_nm,
                "timestamp": pd.Timestamp.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Error getting predictions summary: {e}")
            return {}
