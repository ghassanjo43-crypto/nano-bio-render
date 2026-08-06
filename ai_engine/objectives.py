from nanobio_studio.core.types import SimulationResult

def efficacy_proxy(sim: SimulationResult) -> float:
    """
    Define 'efficacy' from your simulator outputs (higher is better).
    Keep it simple & explainable in Phase-1.
    """
    # Example: weighted combination
    return (0.5 * sim.auc_target) + (0.3 * sim.cmax_target) + (0.2 * sim.release_stability * 100.0)

def scalarized_score(efficacy: float, toxicity: float, cost: float,
                     w_eff: float, w_safe: float, w_cost: float) -> float:
    """
    Optuna maximizes by default if you return a value and set direction='maximize'.
    We want: maximize efficacy, minimize toxicity and cost.
    """
    # Normalize-ish: toxicity/cost already 0..100; efficacy can be scaled externally if needed.
    # Use negative for minimization parts:
    return (w_eff * efficacy) - (w_safe * toxicity) - (w_cost * cost)
