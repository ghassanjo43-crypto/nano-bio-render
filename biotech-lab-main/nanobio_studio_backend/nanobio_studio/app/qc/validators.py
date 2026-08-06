"""
QC validation rules and checkers for LNP records.
"""
from typing import List, Dict, Tuple
from loguru import logger


class QCRule:
    """Base class for QC rules."""
    
    def __init__(self, name: str, severity: str = "warning"):
        """
        Initialize QC rule.
        
        Args:
            name: Rule name
            severity: 'info', 'warning', or 'error'
        """
        self.name = name
        self.severity = severity
    
    def check(self, record: Dict) -> Tuple[bool, str]:
        """
        Check if record passes rule.
        
        Returns:
            Tuple of (pass/fail, message)
        """
        raise NotImplementedError


class LipidRatiosSum(QCRule):
    """Check that lipid ratios sum to 100%."""
    
    def __init__(self):
        super().__init__("Lipid ratios sum to 100%", "error")
    
    def check(self, record: Dict) -> Tuple[bool, str]:
        """Check lipid ratio sum."""
        try:
            ratios = record.get("formulation", {}).get("ratios_molar_percent", {})
            total = sum([
                ratios.get("ionizable", 0),
                ratios.get("helper", 0),
                ratios.get("sterol", 0),
                ratios.get("peg", 0)
            ])
            
            if abs(total - 100.0) > 0.1:  # 0.1% tolerance
                return False, f"Lipid ratios sum to {total}%, expected 100%"
            return True, "Lipid ratios sum to 100%"
        except Exception as e:
            return False, f"Error checking lipid ratios: {e}"


class RequiredLipidClasses(QCRule):
    """Check that all required lipid classes are present."""
    
    REQUIRED_CLASSES = {"ionizable", "helper", "sterol", "peg"}
    
    def __init__(self):
        super().__init__("All required lipid classes present", "error")
    
    def check(self, record: Dict) -> Tuple[bool, str]:
        """Check required lipid classes."""
        try:
            lipids = record.get("formulation", {}).get("lipids", {})
            present = set(lipids.keys())
            
            missing = self.REQUIRED_CLASSES - present
            if missing:
                return False, f"Missing lipid classes: {missing}"
            return True, "All required lipid classes present"
        except Exception as e:
            return False, f"Error checking lipid classes: {e}"


class ParticleSizeRange(QCRule):
    """Check that particle size is within reasonable range."""
    
    def __init__(self, min_nm: float = 1, max_nm: float = 1000):
        super().__init__(f"Particle size {min_nm}-{max_nm} nm", "warning")
        self.min_nm = min_nm
        self.max_nm = max_nm
    
    def check(self, record: Dict) -> Tuple[bool, str]:
        """Check particle size."""
        try:
            size = record.get("characterization", {}).get("particle_size_nm")
            if size is None:
                return True, "Particle size not provided"
            
            if not (self.min_nm <= size <= self.max_nm):
                return False, f"Particle size {size} nm outside {self.min_nm}-{self.max_nm} nm range"
            return True, f"Particle size {size} nm within range"
        except Exception as e:
            return False, f"Error checking particle size: {e}"


class PDIValidation(QCRule):
    """Check that PDI is within valid range (0-1)."""
    
    def __init__(self):
        super().__init__("PDI between 0 and 1", "warning")
    
    def check(self, record: Dict) -> Tuple[bool, str]:
        """Check PDI."""
        try:
            pdi = record.get("characterization", {}).get("pdi")
            if pdi is None:
                return True, "PDI not provided"
            
            if not (0 <= pdi <= 1):
                return False, f"PDI {pdi} outside valid range (0-1)"
            return True, f"PDI {pdi} valid"
        except Exception as e:
            return False, f"Error checking PDI: {e}"


class EncapsulationEfficiency(QCRule):
    """Check that encapsulation efficiency is 0-100%."""
    
    def __init__(self):
        super().__init__("Encapsulation efficiency 0-100%", "warning")
    
    def check(self, record: Dict) -> Tuple[bool, str]:
        """Check encapsulation efficiency."""
        try:
            ee = record.get("characterization", {}).get("encapsulation_efficiency_pct")
            if ee is None:
                return True, "Encapsulation efficiency not provided"
            
            if not (0 <= ee <= 100):
                return False, f"Encapsulation efficiency {ee}% outside 0-100% range"
            return True, f"Encapsulation efficiency {ee}% valid"
        except Exception as e:
            return False, f"Error checking encapsulation efficiency: {e}"


class PHValidation(QCRule):
    """Check that pH is within valid range (0-14)."""
    
    def __init__(self):
        super().__init__("pH between 0 and 14", "warning")
    
    def check(self, record: Dict) -> Tuple[bool, str]:
        """Check pH."""
        try:
            ph = record.get("process_conditions", {}).get("pH")
            if ph is None:
                return True, "pH not provided"
            
            if not (0 <= ph <= 14):
                return False, f"pH {ph} outside valid range (0-14)"
            return True, f"pH {ph} valid"
        except Exception as e:
            return False, f"Error checking pH: {e}"


class TemperatureValidation(QCRule):
    """Check that temperature is physically sensible."""
    
    def __init__(self):
        super().__init__("Temperature -273°C to 500°C", "warning")
    
    def check(self, record: Dict) -> Tuple[bool, str]:
        """Check temperature."""
        try:
            temp = record.get("process_conditions", {}).get("temperature_c")
            if temp is None:
                return True, "Temperature not provided"
            
            if not (-273 <= temp <= 500):
                return False, f"Temperature {temp}°C outside sensible range (-273-500°C)"
            return True, f"Temperature {temp}°C valid"
        except Exception as e:
            return False, f"Error checking temperature: {e}"


class AssayDataComplete(QCRule):
    """Check that assay records have required fields."""
    
    def __init__(self):
        super().__init__("Assay data complete", "warning")
    
    def check(self, record: Dict) -> Tuple[bool, str]:
        """Check assay completeness."""
        try:
            assays = record.get("assays", [])
            if not assays:
                return True, "No assays to validate"
            
            issues = []
            for i, assay in enumerate(assays):
                if not assay.get("assay_type"):
                    issues.append(f"Assay {i}: missing assay_type")
                if not assay.get("result_value") and assay.get("result_value") != 0:
                    issues.append(f"Assay {i}: missing result_value")
            
            if issues:
                return False, "; ".join(issues)
            return True, "All assays have required fields"
        except Exception as e:
            return False, f"Error checking assay data: {e}"


class QCValidator:
    """QC validation engine."""
    
    def __init__(self):
        """Initialize validator with all rules."""
        self.rules = [
            LipidRatiosSum(),
            RequiredLipidClasses(),
            ParticleSizeRange(),
            PDIValidation(),
            EncapsulationEfficiency(),
            PHValidation(),
            TemperatureValidation(),
            AssayDataComplete(),
        ]
    
    def validate(self, record: Dict) -> Dict:
        """
        Validate a record against all rules.
        
        Args:
            record: LNP record to validate
        
        Returns:
            Dict with validation results
        """
        results = {
            "overall_status": "pass",
            "errors": [],
            "warnings": [],
            "infos": [],
            "total_rules": len(self.rules),
            "passed_rules": 0,
        }
        
        for rule in self.rules:
            passed, message = rule.check(record)
            
            result_dict = {
                "rule": rule.name,
                "passed": passed,
                "message": message,
                "severity": rule.severity,
            }
            
            if not passed:
                results["overall_status"] = "fail" if rule.severity == "error" else "warning"
                if rule.severity == "error":
                    results["errors"].append(result_dict)
                elif rule.severity == "warning":
                    results["warnings"].append(result_dict)
            else:
                results["passed_rules"] += 1
            
            if rule.severity == "info" and passed:
                results["infos"].append(result_dict)
        
        return results
