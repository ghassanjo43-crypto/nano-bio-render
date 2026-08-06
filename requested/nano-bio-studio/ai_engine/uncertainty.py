import random

def simple_confidence_from_rules(toxicity: float, cost: float) -> float:
    """
    Phase-1 quick confidence heuristic (0..1):
    lower risk/cost => higher confidence.
    Replace later with ensemble variance.
    """
    # Keep in 0..1
    conf = 1.0 - (0.005 * toxicity) - (0.003 * cost)
    return float(max(0.05, min(0.95, conf)))

def seed_everything(seed: int) -> None:
    random.seed(seed)
