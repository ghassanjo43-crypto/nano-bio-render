"""
Adapter layer so you can plug your existing NanoBio Studio simulation
without rewriting anything.
"""
from typing import Callable
from nanobio_studio.core.types import NanoDesign, SimulationResult

# ---- YOU WILL WIRE THESE 3 in your project ----
SimulateFn = Callable[[NanoDesign], SimulationResult]

def simulate_design_placeholder(design: NanoDesign) -> SimulationResult:
    """
    Placeholder. Replace by calling your real PK/PD-lite simulator.
    """
    # Simple toy proxies (REMOVE when you integrate your real simulator)
    auc = (design.dose_mg_per_kg * 10.0) / (1.0 + abs(design.zeta_mV)/25.0)
    cmax = design.dose_mg_per_kg * (200.0 / max(design.size_nm, 1.0))
    t_half = 2.0 + (design.size_nm / 100.0)
    stability = max(0.0, 1.0 - design.pdi)
    return SimulationResult(
        auc_target=auc,
        cmax_target=cmax,
        t_half_proxy=t_half,
        release_stability=stability,
        extra={}
    )
