from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

@dataclass
class NanoDesign:
    """Canonical representation of a nanoparticle design."""
    size_nm: float
    zeta_mV: float
    material: str
    ligand: str
    payload: str
    dose_mg_per_kg: float
    pdi: float = 0.2
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SimulationResult:
    """What your simulator returns (proxies are fine in Phase-1)."""
    # Example PK/PD-lite proxies:
    auc_target: float
    cmax_target: float
    t_half_proxy: float
    release_stability: float  # higher = more stable
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ScoredCandidate:
    design: NanoDesign
    sim: SimulationResult
    efficacy: float
    toxicity: float
    cost: float
    confidence: float
    drivers: List[str] = field(default_factory=list)
