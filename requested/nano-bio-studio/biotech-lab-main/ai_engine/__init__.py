# ============================================================
# NanoBio Studio AI Engine
# Multi-objective optimization and analysis framework
# ============================================================

"""
AI Engine Module: Comprehensive nanoparticle design optimization.

This module provides:
- Multi-objective optimization (Pareto optimization)
- Scenario-based design workflows
- Sensitivity & explainability analysis
- Uncertainty quantification
- Audit trail and reporting

Key Classes:
    - NanoDesign: Canonical nanoparticle representation
    - SimulationResult: Simulator output
    - ScoredCandidate: Evaluated design with scores
    - DesignSpace: Parameter search space
    - ObjectiveWeights: Multi-objective weights
    - OptimizationResult: Optimization run results
    - ScenarioPreset: Scenario configuration
    - AIEngine: Unified orchestrator for workflows

Key Functions:
    - run_optimization: Multi-objective Pareto optimization
    - pareto_front: Extract non-dominated solutions
    - explain_design: Sensitivity analysis & explainability
    - toxicity_score_hybrid: Hybrid toxicity model
    - cost_score_proxy: Cost estimation
    - efficacy_proxy: Efficacy scoring
    - get_scenarios: List available scenarios

Usage Example:
    >>> from nanobio_studio.ai_engine import AIEngine, get_scenarios
    >>> engine = AIEngine(simulate_fn=my_simulator)
    >>> scenario = get_scenarios()["Safety-First (Translational)"]
    >>> result = engine.run_scenario(
    ...     scenario_key="safety_first",
    ...     design_space=my_space,
    ...     n_trials=300
    ... )
    >>> best_design = result.best
    >>> pareto = engine.get_pareto_front(result)
    >>> report = engine.get_html_report(engine.get_audit_trail()[0])
"""

# ============================================================
# Core Types (re-exported from core)
# ============================================================
from nanobio_studio.core.types import (
    NanoDesign,
    SimulationResult,
    ScoredCandidate,
)

# ============================================================
# Schema & Configuration
# ============================================================
from nanobio_studio.ai_engine.schema import (
    DesignSpace,
    ObjectiveWeights,
)

# ============================================================
# Optimization Core
# ============================================================
from nanobio_studio.ai_engine.optimizer import (
    OptimizationResult,
    run_optimization,
)

from nanobio_studio.ai_engine.pareto import (
    is_dominated,
    pareto_front,
)

# ============================================================
# Scoring & Evaluation
# ============================================================
from nanobio_studio.ai_engine.objectives import (
    efficacy_proxy,
    scalarized_score,
)

from nanobio_studio.ai_engine.toxicity import (
    toxicity_score_hybrid,
)

from nanobio_studio.ai_engine.cost import (
    cost_score_proxy,
)

from nanobio_studio.ai_engine.uncertainty import (
    simple_confidence_from_rules,
    seed_everything,
)

# ============================================================
# Scenarios & Use Cases
# ============================================================
from nanobio_studio.ai_engine.scenarios import (
    ScenarioPreset,
    get_scenarios,
    get_scenario,
    list_scenario_keys,
    list_scenarios_summary,
    validate_scenario,
)

# ============================================================
# Analysis & Explainability
# ============================================================
from nanobio_studio.ai_engine.explainability import (
    SensitivityResult,
    explain_design,
)

# ============================================================
# Reporting & Audit
# ============================================================
from nanobio_studio.ai_engine.reporting import (
    candidates_to_df,
)

from nanobio_studio.ai_engine.audit import (
    AuditRecord,
    build_audit_record,
    record_outcome,
    audit_to_json,
    audit_to_html,
)

# ============================================================
# Simulation Integration
# ============================================================
from nanobio_studio.ai_engine.simulator_adapter import (
    SimulateFn,
    simulate_design_placeholder,
)

# ============================================================
# Engine Orchestrator
# ============================================================
from nanobio_studio.ai_engine.engine import (
    AIEngine,
    EngineConfig,
    create_engine,
)

# ============================================================
# Public API
# ============================================================

__all__ = [
    # Core Types
    "NanoDesign",
    "SimulationResult",
    "ScoredCandidate",
    
    # Schema
    "DesignSpace",
    "ObjectiveWeights",
    
    # Optimization
    "OptimizationResult",
    "run_optimization",
    "pareto_front",
    "is_dominated",
    
    # Scoring
    "efficacy_proxy",
    "scalarized_score",
    "toxicity_score_hybrid",
    "cost_score_proxy",
    "simple_confidence_from_rules",
    "seed_everything",
    
    # Scenarios
    "ScenarioPreset",
    "get_scenarios",
    "get_scenario",
    "list_scenario_keys",
    "list_scenarios_summary",
    "validate_scenario",
    
    # Explainability
    "SensitivityResult",
    "explain_design",
    
    # Reporting
    "candidates_to_df",
    
    # Audit
    "AuditRecord",
    "build_audit_record",
    "record_outcome",
    "audit_to_json",
    "audit_to_html",
    
    # Simulation
    "SimulateFn",
    "simulate_design_placeholder",
    
    # Engine
    "AIEngine",
    "EngineConfig",
    "create_engine",
]

__version__ = "1.0.0"
__author__ = "Experts Group FZE"
__description__ = "Multi-objective nanoparticle design optimization engine"


