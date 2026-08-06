import plotly.express as px
import pandas as pd
from nanobio_studio.core.types import ScoredCandidate

def pareto_scatter(all_cands: list[ScoredCandidate], pareto: list[ScoredCandidate]):
    rows = []
    pareto_ids = set(id(x) for x in pareto)

    for c in all_cands:
        rows.append({
            "efficacy": c.efficacy,
            "toxicity": c.toxicity,
            "cost": c.cost,
            "confidence": c.confidence,
            "pareto": "Pareto" if id(c) in pareto_ids else "All",
            "label": f"{c.design.material}/{c.design.ligand} size={c.design.size_nm:.0f}"
        })
    df = pd.DataFrame(rows)

    fig = px.scatter(
        df, x="toxicity", y="efficacy",
        color="cost",
        symbol="pareto",
        hover_name="label",
        hover_data=["confidence"]
    )
    fig.update_layout(xaxis_title="Toxicity (lower is better)", yaxis_title="Efficacy (higher is better)")
    return fig
