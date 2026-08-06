"""
Feature extraction service for LNP formulations

Extracts and derives ML-ready features from formulation data
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

from loguru import logger

logger = logger.bind(module="ml.features")


@dataclass
class ExtractedFeatures:
    """Container for extracted features"""
    
    formulation_id: str
    
    # Lipid composition features
    ionizable_ratio: float
    helper_ratio: float
    sterol_ratio: float
    peg_ratio: float
    
    # Derived features
    lipid_ratio_variance: float
    ionizable_helper_ratio: float
    sterol_peg_ratio: float
    
    # Payload features
    payload_type_encoded: Optional[int] = None
    
    # Physical properties
    particle_size_nm: Optional[float] = None
    pdi: Optional[float] = None
    zeta_potential_mv: Optional[float] = None
    encapsulation_efficiency_pct: Optional[float] = None
    
    # Process features
    temperature_c: Optional[float] = None
    buffer_ph: Optional[float] = None
    
    # Target variables (for supervised learning)
    toxicity_score: Optional[float] = None
    uptake_score: Optional[float] = None
    transfection_efficiency: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame construction"""
        return {
            "formulation_id": self.formulation_id,
            "ionizable_ratio": self.ionizable_ratio,
            "helper_ratio": self.helper_ratio,
            "sterol_ratio": self.sterol_ratio,
            "peg_ratio": self.peg_ratio,
            "lipid_ratio_variance": self.lipid_ratio_variance,
            "ionizable_helper_ratio": self.ionizable_helper_ratio,
            "sterol_peg_ratio": self.sterol_peg_ratio,
            "payload_type_encoded": self.payload_type_encoded,
            "particle_size_nm": self.particle_size_nm,
            "pdi": self.pdi,
            "zeta_potential_mv": self.zeta_potential_mv,
            "encapsulation_efficiency_pct": self.encapsulation_efficiency_pct,
            "temperature_c": self.temperature_c,
            "buffer_ph": self.buffer_ph,
            "toxicity_score": self.toxicity_score,
            "uptake_score": self.uptake_score,
            "transfection_efficiency": self.transfection_efficiency,
        }


class FeatureExtractor:
    """Extract ML-ready features from LNP formulation data"""
    
    def __init__(self):
        """Initialize feature extractor"""
        self.logger = logger
    
    def extract_from_record(self, record: Dict[str, Any]) -> ExtractedFeatures:
        """
        Extract features from a complete LNP record
        
        Args:
            record: Complete LNP record dict from API/database
            
        Returns:
            ExtractedFeatures object with all extracted features
        """
        try:
            # Extract formulation ID
            formulation_id = record.get("formulation", {}).get("formulation_id", "unknown")
            
            # Extract lipid ratios
            ratios = record.get("formulation", {}).get("lipid_composition", {}).get("molar_ratios", {})
            ionizable_ratio = float(ratios.get("ionizable_pct", 0.0)) / 100.0
            helper_ratio = float(ratios.get("helper_pct", 0.0)) / 100.0
            sterol_ratio = float(ratios.get("sterol_pct", 0.0)) / 100.0
            peg_ratio = float(ratios.get("peg_pct", 0.0)) / 100.0
            
            # Derived lipid features
            lipid_ratio_variance = self._calculate_ratio_variance(
                [ionizable_ratio, helper_ratio, sterol_ratio, peg_ratio]
            )
            ionizable_helper_ratio = ionizable_ratio / (helper_ratio + 1e-6)
            sterol_peg_ratio = sterol_ratio / (peg_ratio + 1e-6)
            
            # Payload features
            payload_type = record.get("formulation", {}).get("payload_info", {}).get("payload_type")
            
            # Physical properties (from characterization)
            char = record.get("characterization", {})
            particle_size_nm = char.get("particle_size_nm")
            pdi = char.get("pdi")
            zeta_potential_mv = char.get("zeta_potential_mv")
            encapsulation_efficiency_pct = char.get("encapsulation_efficiency_pct")
            
            # Process features
            process = record.get("process_conditions", {})
            temperature_c = process.get("temperature_c")
            buffer_ph = process.get("buffer_ph")
            
            # Target variables (from assays)
            toxicity_score = self._extract_target_from_assays(record, "toxicity")
            uptake_score = self._extract_target_from_assays(record, "uptake")
            transfection_efficiency = self._extract_target_from_assays(record, "transfection")
            
            return ExtractedFeatures(
                formulation_id=formulation_id,
                ionizable_ratio=ionizable_ratio,
                helper_ratio=helper_ratio,
                sterol_ratio=sterol_ratio,
                peg_ratio=peg_ratio,
                lipid_ratio_variance=lipid_ratio_variance,
                ionizable_helper_ratio=ionizable_helper_ratio,
                sterol_peg_ratio=sterol_peg_ratio,
                payload_type_encoded=None,  # Will be encoded separately
                particle_size_nm=particle_size_nm,
                pdi=pdi,
                zeta_potential_mv=zeta_potential_mv,
                encapsulation_efficiency_pct=encapsulation_efficiency_pct,
                temperature_c=temperature_c,
                buffer_ph=buffer_ph,
                toxicity_score=toxicity_score,
                uptake_score=uptake_score,
                transfection_efficiency=transfection_efficiency,
            )
        except Exception as e:
            self.logger.error(f"Error extracting features from record: {e}")
            raise
    
    @staticmethod
    def _calculate_ratio_variance(ratios: List[float]) -> float:
        """Calculate variance in lipid ratios (measure of balance)"""
        if not ratios:
            return 0.0
        mean = sum(ratios) / len(ratios)
        variance = sum((x - mean) ** 2 for x in ratios) / len(ratios)
        return float(variance)
    
    @staticmethod
    def _extract_target_from_assays(record: Dict[str, Any], assay_type: str) -> Optional[float]:
        """Extract target value from assays by type"""
        assays = record.get("assays", [])
        for assay in assays:
            if assay.get("assay_type") == assay_type:
                score = assay.get("normalized_score")
                if score is not None:
                    return float(score)
        return None
    
    def extract_batch(self, records: List[Dict[str, Any]]) -> List[ExtractedFeatures]:
        """
        Extract features from multiple records
        
        Args:
            records: List of LNP record dicts
            
        Returns:
            List of ExtractedFeatures objects
        """
        features_list = []
        for i, record in enumerate(records):
            try:
                features = self.extract_from_record(record)
                features_list.append(features)
            except Exception as e:
                self.logger.warning(f"Failed to extract features from record {i}: {e}")
        
        self.logger.info(f"Extracted features from {len(features_list)}/{len(records)} records")
        return features_list
