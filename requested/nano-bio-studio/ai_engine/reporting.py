from typing import List
import pandas as pd
from nanobio_studio.core.types import ScoredCandidate

def candidates_to_df(cands: List[ScoredCandidate]) -> pd.DataFrame:
    rows = []
    for i, c in enumerate(cands, start=1):
        rows.append({
            "Rank": i,
            "Size (nm)": c.design.size_nm,
            "Zeta (mV)": c.design.zeta_mV,
            "Material": c.design.material,
            "Ligand": c.design.ligand,
            "Payload": c.design.payload,
            "Dose (mg/kg)": c.design.dose_mg_per_kg,
            "PDI": c.design.pdi,
            "Efficacy": c.efficacy,
            "Toxicity (0-100)": c.toxicity,
            "Cost (0-100)": c.cost,
            "Confidence (0-1)": c.confidence,
            "Top Drivers": "; ".join(c.drivers[:3]),
        })
    return pd.DataFrame(rows)
