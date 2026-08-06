from nanobio_studio.core.types import NanoDesign, SimulationResult

def toxicity_score_hybrid(design: NanoDesign, sim: SimulationResult) -> tuple[float, list[str]]:
    """
    Phase-1: Transparent hybrid toxicity score (0..100).
    Return score + top driver strings (for explainability).
    Replace/extend later with ML model.
    """
    drivers = []
    score = 0.0

    # Size risk (very small can increase cellular uptake & toxicity)
    if design.size_nm < 50:
        score += 20; drivers.append("Small size (<50nm)")
    elif design.size_nm > 180:
        score += 10; drivers.append("Large size (>180nm)")

    # Charge risk (high magnitude can disrupt membranes)
    if abs(design.zeta_mV) > 25:
        score += 25; drivers.append("High |zeta| (>25mV)")
    elif abs(design.zeta_mV) > 15:
        score += 10; drivers.append("Moderate |zeta| (>15mV)")

    # Dose risk
    if design.dose_mg_per_kg > 10:
        score += 20; drivers.append("High dose (>10 mg/kg)")
    elif design.dose_mg_per_kg > 5:
        score += 10; drivers.append("Moderate dose (>5 mg/kg)")

    # PDI / aggregation proxy
    if design.pdi > 0.25:
        score += 20; drivers.append("High PDI (>0.25)")
    elif design.pdi > 0.2:
        score += 10; drivers.append("Moderate PDI (>0.20)")

    # Material priors (simple)
    material_priors = {"Gold": 10, "Lipid": 5, "PLGA": 3}
    score += material_priors.get(design.material, 5)

    # Clamp 0..100
    score = max(0.0, min(100.0, score))
    return score, drivers
