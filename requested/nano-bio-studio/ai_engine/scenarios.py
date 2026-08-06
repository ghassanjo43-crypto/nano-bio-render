# ============================================================
# NanoBio Studio Scenario Presets
# Pre-configured optimization workflows for different use cases
# ============================================================

"""
Scenario Presets Module

Provides pre-configured optimization scenarios for common use cases:
- Academic/Educational: Balanced learning
- Safety-First: Regulatory/translational programs
- Cost-Constrained: Manufacturing and scale-up
- Custom: User-defined

Each scenario includes:
- Objective weights (efficacy, safety, cost)
- Constraints (toxicity_max, cost_max)
- Recommended trial count and top-k
- Clear descriptions for stakeholders
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from nanobio_studio.ai_engine.schema import ObjectiveWeights


@dataclass
class ScenarioPreset:
    """
    Pre-configured scenario for optimization
    
    Attributes:
        key: Unique scenario identifier (lowercase, underscore-separated)
        title: Human-readable scenario name
        description: Clear description of use case and approach
        weights: Multi-objective weights (efficacy, safety, cost)
        toxicity_max: Hard constraint on toxicity (None = no constraint)
        cost_max: Hard constraint on cost (None = no constraint)
        recommended_trials: Suggested number of optimization trials
        recommended_top_k: Suggested number of top candidates to keep
    """
    key: str
    title: str
    description: str

    # weights
    weights: ObjectiveWeights

    # constraints (None = no constraint)
    toxicity_max: Optional[float] = None
    cost_max: Optional[float] = None

    # recommended settings
    recommended_trials: int = 200
    recommended_top_k: int = 10


def validate_scenario(scenario: ScenarioPreset) -> Tuple[bool, str]:
    """
    Validate scenario configuration
    
    Args:
        scenario: ScenarioPreset to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check weights
    w = scenario.weights.normalized()
    total = w.efficacy + w.safety + w.cost
    if abs(total - 1.0) > 0.01:
        return False, f"Weights don't sum to 1.0: {total}"
    
    # Check constraints
    if scenario.toxicity_max is not None and scenario.toxicity_max < 0:
        return False, "toxicity_max must be positive"
    if scenario.cost_max is not None and scenario.cost_max < 0:
        return False, "cost_max must be positive"
    
    # Check trials
    if scenario.recommended_trials < 10:
        return False, "recommended_trials must be >= 10"
    if scenario.recommended_trials > 5000:
        return False, "recommended_trials must be <= 5000"
    
    # Check top-k
    if scenario.recommended_top_k < 1:
        return False, "recommended_top_k must be >= 1"
    
    return True, ""


def get_scenarios() -> Dict[str, ScenarioPreset]:
    """
    Get all available optimization scenarios
    
    Returns:
        Dictionary mapping scenario keys to ScenarioPreset objects
        
    Scenario Reference:
        - "academic": Balanced learning (education/research)
        - "safety_first": Prioritize safety (translational/regulatory)
        - "cost_constrained": Minimize cost (manufacturing/scale-up)
        - "efficacy_driven": Maximize efficacy (early research)
    """
    return {
        "academic": ScenarioPreset(
            key="academic",
            title="Academic / Educational",
            description=(
                "Balanced exploration for teaching and early research. "
                "Encourages learning about trade-offs without strict constraints. "
                "Suitable for: Student projects, proof-of-concept, parameter space exploration."
            ),
            weights=ObjectiveWeights(efficacy=0.45, safety=0.35, cost=0.20),
            toxicity_max=None,
            cost_max=None,
            recommended_trials=200,
            recommended_top_k=10,
        ),
        
        "safety_first": ScenarioPreset(
            key="safety_first",
            title="Safety-First (Translational)",
            description=(
                "Prioritizes safety and risk reduction. "
                "Suitable for translational programs and pre-clinical decision support. "
                "Applies a strict toxicity ceiling. "
                "Suitable for: IND-enabling studies, regulatory submissions, clinical translation."
            ),
            weights=ObjectiveWeights(efficacy=0.30, safety=0.55, cost=0.15),
            toxicity_max=55.0,   # Adjust to your toxicity scale (0-100)
            cost_max=None,
            recommended_trials=300,
            recommended_top_k=12,
        ),
        
        "cost_constrained": ScenarioPreset(
            key="cost_constrained",
            title="Cost-Constrained (Manufacturing)",
            description=(
                "Prioritizes manufacturability and cost discipline while maintaining acceptable safety. "
                "Applies a cost ceiling to avoid unrealistic candidates. "
                "Suitable for: Scale-up planning, GMP process development, commercial optimization."
            ),
            weights=ObjectiveWeights(efficacy=0.35, safety=0.30, cost=0.35),
            toxicity_max=None,
            cost_max=55.0,       # Adjust to your cost scale (0-100)
            recommended_trials=300,
            recommended_top_k=12,
        ),
        
        "efficacy_driven": ScenarioPreset(
            key="efficacy_driven",
            title="Efficacy-Driven (Early Research)",
            description=(
                "Maximizes therapeutic efficacy with reasonable safety margins. "
                "Minimal cost constraints; focus on finding most potent candidates. "
                "Suitable for: Lead optimization, mechanism studies, potency benchmarking."
            ),
            weights=ObjectiveWeights(efficacy=0.60, safety=0.25, cost=0.15),
            toxicity_max=70.0,   # Higher toxicity tolerance in early stage
            cost_max=None,
            recommended_trials=250,
            recommended_top_k=15,
        ),
        
        "balanced": ScenarioPreset(
            key="balanced",
            title="Balanced (General Purpose)",
            description=(
                "Balanced optimization across all three objectives. "
                "No hard constraints; suitable for general design exploration. "
                "Suitable for: Multi-parameter studies, design of experiments, benchmarking."
            ),
            weights=ObjectiveWeights(efficacy=0.40, safety=0.35, cost=0.25),
            toxicity_max=None,
            cost_max=None,
            recommended_trials=250,
            recommended_top_k=12,
        ),
        
        "regulatory_compliant": ScenarioPreset(
            key="regulatory_compliant",
            title="Regulatory Compliant (Strict)",
            description=(
                "Maximum stringency for regulatory submissions. "
                "Strict constraints on both safety and cost. "
                "Focus on reproducible, well-characterized designs. "
                "Suitable for: FDA/EMA submissions, GMP manufacturing, Phase 1 IND."
            ),
            weights=ObjectiveWeights(efficacy=0.35, safety=0.50, cost=0.15),
            toxicity_max=40.0,   # Very strict toxicity limit
            cost_max=50.0,       # Strict cost limit
            recommended_trials=400,
            recommended_top_k=10,
        ),
    }


def get_scenario(scenario_key: str) -> Optional[ScenarioPreset]:
    """
    Get a specific scenario by key
    
    Args:
        scenario_key: Scenario identifier
        
    Returns:
        ScenarioPreset or None if not found
    """
    scenarios = get_scenarios()
    return scenarios.get(scenario_key)


def list_scenario_keys() -> list:
    """Get list of all available scenario keys"""
    return list(get_scenarios().keys())


def list_scenarios_summary() -> Dict[str, str]:
    """Get brief summary of all scenarios"""
    return {
        key: scenario.title
        for key, scenario in get_scenarios().items()
    }

