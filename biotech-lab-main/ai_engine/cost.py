from nanobio_studio.core.types import NanoDesign

def cost_score_proxy(design: NanoDesign) -> float:
    """
    Phase-1: proxy cost/complexity index (0..100).
    Replace with your real NanoBio Studio cost model.
    """
    base = {"PLGA": 30, "Lipid": 40, "Gold": 60}.get(design.material, 45)
    ligand = {"None": 0, "PEG": 10, "Folate": 20}.get(design.ligand, 10)
    payload = {"DrugA": 10, "DrugB": 20}.get(design.payload, 15)
    scale = 0.1 * design.dose_mg_per_kg
    pdi_penalty = 100 * max(0.0, design.pdi - 0.2)
    score = base + ligand + payload + scale + pdi_penalty
    return float(max(0.0, min(100.0, score)))
