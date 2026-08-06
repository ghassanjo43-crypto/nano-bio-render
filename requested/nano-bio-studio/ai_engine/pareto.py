from typing import List
from nanobio_studio.core.types import ScoredCandidate

def is_dominated(a: ScoredCandidate, b: ScoredCandidate) -> bool:
    """
    b dominates a if:
    - b.efficacy >= a.efficacy
    - b.toxicity <= a.toxicity
    - b.cost <= a.cost
    and at least one strict.
    """
    better_or_equal = (b.efficacy >= a.efficacy) and (b.toxicity <= a.toxicity) and (b.cost <= a.cost)
    strictly_better = (b.efficacy > a.efficacy) or (b.toxicity < a.toxicity) or (b.cost < a.cost)
    return bool(better_or_equal and strictly_better)

def pareto_front(cands: List[ScoredCandidate]) -> List[ScoredCandidate]:
    front = []
    for a in cands:
        dominated = any(is_dominated(a, b) for b in cands if b is not a)
        if not dominated:
            front.append(a)
    # sort: high efficacy first, then low toxicity, then low cost
    front.sort(key=lambda x: (-x.efficacy, x.toxicity, x.cost))
    return front
