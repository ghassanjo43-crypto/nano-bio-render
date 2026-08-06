# ============================================================
# NanoBio Studio AI Engine Orchestrator
# Unified interface for design optimization workflows
# ============================================================

"""
Engine Orchestrator Module

Provides a unified interface to run complete optimization workflows
with scenario selection, validation, and comprehensive reporting.

Usage:
    >>> from nanobio_studio.ai_engine.engine import AIEngine
    >>> engine = AIEngine(simulate_fn=my_simulator)
    >>> result = engine.run_scenario(
    ...     scenario_key="safety_first",
    ...     design_space=my_space,
    ...     n_trials=300
    ... )
    >>> engine.get_report(result)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Any, List, Callable

from nanobio_studio.ai_engine.schema import DesignSpace, ObjectiveWeights
from nanobio_studio.ai_engine.optimizer import run_optimization, OptimizationResult
from nanobio_studio.ai_engine.scenarios import get_scenarios, ScenarioPreset
from nanobio_studio.ai_engine.audit import (
    build_audit_record,
    record_outcome,
    audit_to_json,
    audit_to_html,
    AuditRecord,
)
from nanobio_studio.ai_engine.explainability import explain_design
from nanobio_studio.ai_engine.reporting import candidates_to_df
from nanobio_studio.ai_engine.pareto import pareto_front
from nanobio_studio.ai_engine.simulator_adapter import SimulateFn

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class EngineConfig:
    """Configuration for AI Engine"""
    log_level: str = "INFO"
    enable_audit: bool = True
    enable_sensitivity: bool = True
    seed: int = 42
    default_n_trials: int = 200
    max_n_trials: int = 1000


class AIEngine:
    """
    Unified orchestrator for design optimization workflows.
    
    Manages:
    - Scenario selection and validation
    - Optimization runs with constraints
    - Audit trail generation
    - Explainability analysis
    - Report generation
    """
    
    def __init__(
        self,
        simulate_fn: SimulateFn,
        config: Optional[EngineConfig] = None
    ):
        """
        Initialize AI Engine
        
        Args:
            simulate_fn: Function that takes NanoDesign and returns SimulationResult
            config: Engine configuration (uses defaults if None)
        """
        self.simulate_fn = simulate_fn
        self.config = config or EngineConfig()
        self._setup_logging()
        self.audit_trail: List[AuditRecord] = []
        
    def _setup_logging(self):
        """Configure logging"""
        logger.setLevel(getattr(logging, self.config.log_level))
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    
    def get_available_scenarios(self) -> Dict[str, ScenarioPreset]:
        """Get all available optimization scenarios"""
        return get_scenarios()
    
    def validate_scenario(self, scenario_key: str) -> bool:
        """Validate that scenario exists"""
        scenarios = self.get_available_scenarios()
        exists = scenario_key in scenarios
        if not exists:
            logger.warning(f"Scenario '{scenario_key}' not found")
        return exists
    
    def validate_design_space(self, space: DesignSpace) -> bool:
        """Validate design space configuration"""
        try:
            if space.size_nm_min >= space.size_nm_max:
                logger.error("Invalid size range: min >= max")
                return False
            if space.charge_mV_min >= space.charge_mV_max:
                logger.error("Invalid charge range: min >= max")
                return False
            if space.dose_min >= space.dose_max:
                logger.error("Invalid dose range: min >= max")
                return False
            if not space.materials or len(space.materials) == 0:
                logger.error("No materials defined")
                return False
            logger.info(f"Design space validated: {len(space.materials)} materials")
            return True
        except Exception as e:
            logger.error(f"Design space validation failed: {str(e)}")
            return False
    
    def run_scenario(
        self,
        scenario_key: str,
        design_space: DesignSpace,
        n_trials: Optional[int] = None,
        top_k: int = 10,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[OptimizationResult]:
        """
        Run optimization with predefined scenario
        
        Args:
            scenario_key: Key of scenario preset
            design_space: DesignSpace configuration
            n_trials: Number of optimization trials (uses scenario default if None)
            top_k: Keep top k candidates
            project_id: Optional project ID for audit
            user_id: Optional user ID for audit
            
        Returns:
            OptimizationResult or None if validation fails
        """
        logger.info(f"Starting optimization: scenario='{scenario_key}'")
        
        # Validate
        if not self.validate_scenario(scenario_key):
            logger.error(f"Invalid scenario: {scenario_key}")
            return None
        
        if not self.validate_design_space(design_space):
            logger.error("Invalid design space")
            return None
        
        # Get scenario
        scenarios = self.get_available_scenarios()
        scenario = scenarios[scenario_key]
        
        # Use scenario defaults if not overridden
        n_trials = n_trials or scenario.recommended_trials
        n_trials = min(n_trials, self.config.max_n_trials)
        
        logger.info(f"Using {n_trials} trials, scenario: {scenario.title}")
        
        # Build constraints
        constraints = {}
        if scenario.toxicity_max is not None:
            constraints["toxicity_max"] = scenario.toxicity_max
        if scenario.cost_max is not None:
            constraints["cost_max"] = scenario.cost_max
        
        # Create audit record
        audit = None
        if self.config.enable_audit:
            audit = build_audit_record(
                scenario_name=scenario.title,
                scenario_key=scenario_key,
                space=design_space,
                weights=scenario.weights,
                constraints=constraints,
                run_settings={
                    "n_trials": n_trials,
                    "seed": self.config.seed,
                    "top_k": top_k,
                },
            )
            audit.project_id = project_id
            audit.user_id = user_id
        
        # Run optimization
        try:
            result = run_optimization(
                space=design_space,
                weights=scenario.weights,
                n_trials=n_trials,
                seed=self.config.seed,
                simulate_fn=self.simulate_fn,
                top_k=top_k,
                constraints=constraints,
            )
            
            # Record outcome
            if audit and self.config.enable_audit:
                audit = record_outcome(
                    audit,
                    result,
                    baseline_summary={
                        "n_candidates": len(result.candidates),
                        "best_score": float(result.best.efficacy),
                        "worst_toxicity": max(c.toxicity for c in result.candidates),
                    },
                    explainability_summary={
                        "top_driver": result.best.drivers[0] if result.best.drivers else "N/A",
                        "confidence": float(result.best.confidence),
                    }
                )
                self.audit_trail.append(audit)
            
            logger.info(
                f"Optimization completed: "
                f"best_score={result.best.efficacy:.2f}, "
                f"toxicity={result.best.toxicity:.2f}, "
                f"cost={result.best.cost:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}", exc_info=True)
            return None
    
    def run_custom(
        self,
        design_space: DesignSpace,
        weights: ObjectiveWeights,
        n_trials: Optional[int] = None,
        constraints: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[OptimizationResult]:
        """
        Run optimization with custom weights (not tied to a scenario)
        
        Args:
            design_space: DesignSpace configuration
            weights: ObjectiveWeights (custom)
            n_trials: Number of trials
            constraints: Optional constraint dictionary
            project_id: Optional project ID for audit
            user_id: Optional user ID for audit
            
        Returns:
            OptimizationResult or None if validation fails
        """
        logger.info("Starting custom optimization (no scenario)")
        
        if not self.validate_design_space(design_space):
            logger.error("Invalid design space")
            return None
        
        n_trials = n_trials or self.config.default_n_trials
        n_trials = min(n_trials, self.config.max_n_trials)
        constraints = constraints or {}
        
        try:
            result = run_optimization(
                space=design_space,
                weights=weights,
                n_trials=n_trials,
                seed=self.config.seed,
                simulate_fn=self.simulate_fn,
                constraints=constraints,
            )
            
            logger.info(
                f"Custom optimization completed: "
                f"best_score={result.best.efficacy:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Custom optimization failed: {str(e)}", exc_info=True)
            return None
    
    def get_pareto_front(self, result: OptimizationResult) -> List:
        """
        Extract Pareto-optimal solutions from optimization result
        
        Args:
            result: OptimizationResult from run_scenario or run_custom
            
        Returns:
            List of non-dominated ScoredCandidate objects
        """
        front = pareto_front(result.candidates)
        logger.info(f"Extracted Pareto front with {len(front)} solutions")
        return front
    
    def explain_best(
        self,
        result: OptimizationResult,
        design_space: Optional[DesignSpace] = None,
    ) -> Optional[Dict]:
        """
        Generate explainability analysis for best design
        
        Args:
            result: OptimizationResult
            design_space: Optional DesignSpace for clipping perturbations
            
        Returns:
            Dictionary with metrics, drivers, and sensitivity analysis
        """
        if not self.config.enable_sensitivity:
            logger.warning("Sensitivity analysis disabled")
            return None
        
        try:
            best = result.best
            
            # Run sensitivity analysis
            metrics, drivers, sensitivity = explain_design(
                design=best.design,
                weights=ObjectiveWeights(
                    efficacy=0.5,  # Would come from optimization weights
                    safety=0.3,
                    cost=0.2,
                ),
                simulate_fn=self.simulate_fn,
                space=design_space,
            )
            
            logger.info(f"Explainability analysis completed for best design")
            
            return {
                "design": best.design,
                "metrics": metrics,
                "drivers": drivers[:5],  # Top 5 drivers
                "sensitivity": [
                    {
                        "parameter": s.param,
                        "direction": s.direction,
                        "impact": float(s.score_change),
                    }
                    for s in sensitivity[:10]  # Top 10 sensitivities
                ],
            }
            
        except Exception as e:
            logger.error(f"Explainability analysis failed: {str(e)}", exc_info=True)
            return None
    
    def get_dataframe_report(self, result: OptimizationResult):
        """Get pandas DataFrame with all candidates for spreadsheet export"""
        try:
            df = candidates_to_df(result.candidates)
            logger.info(f"Generated DataFrame with {len(df)} candidates")
            return df
        except Exception as e:
            logger.error(f"DataFrame generation failed: {str(e)}")
            return None
    
    def get_json_audit(self, audit: AuditRecord) -> str:
        """Get JSON audit record"""
        return audit_to_json(audit)
    
    def get_html_report(self, audit: AuditRecord) -> str:
        """Get HTML audit report (suitable for printing)"""
        return audit_to_html(audit)
    
    def get_audit_trail(self) -> List[AuditRecord]:
        """Get all audit records from this session"""
        return self.audit_trail
    
    def clear_audit_trail(self):
        """Clear audit trail"""
        self.audit_trail.clear()
        logger.info("Audit trail cleared")


# ============================================================
# Convenience Factory Functions
# ============================================================

def create_engine(
    simulate_fn: SimulateFn,
    log_level: str = "INFO",
) -> AIEngine:
    """
    Factory function to create an AIEngine
    
    Args:
        simulate_fn: Simulation function
        log_level: Logging level (INFO, DEBUG, WARNING, ERROR)
        
    Returns:
        Configured AIEngine instance
    """
    config = EngineConfig(log_level=log_level)
    return AIEngine(simulate_fn=simulate_fn, config=config)
