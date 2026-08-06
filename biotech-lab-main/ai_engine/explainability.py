# nanobio_studio/ai_engine/explainability.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from nanobio_studio.core.types import NanoDesign
from nanobio_studio.ai_engine.schema import ObjectiveWeights
from nanobio_studio.ai_engine.objectives import efficacy_proxy
from nanobio_studio.ai_engine.toxicity import toxicity_score_hybrid
from nanobio_studio.ai_engine.cost import cost_score_proxy


@dataclass
class SensitivityResult:
    param: str
    direction: str  # "+", "-"
    delta: float
    base_score: float
    new_score: float
    score_change: float
    base_eff: float
    new_eff: float
    eff_change: float
    base_tox: float
    new_tox: float
    tox_change: float
    base_cost: float
    new_cost: float
    cost_change: float


def _scalar_score(weights: ObjectiveWeights, eff: float, tox: float, cost: float) -> float:
    w = weights.normalized()
    return float((w.efficacy * eff) - (w.safety * tox) - (w.cost * cost))


def _clip(value: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, value)))


def _clone_design(d: NanoDesign) -> NanoDesign:
    return NanoDesign(
        size_nm=float(d.size_nm),
        zeta_mV=float(d.zeta_mV),
        material=str(d.material),
        ligand=str(d.ligand),
        payload=str(d.payload),
        dose_mg_per_kg=float(d.dose_mg_per_kg),
        pdi=float(d.pdi),
        extra=dict(d.extra or {}),
    )


def explain_design(
    design: NanoDesign,
    weights: ObjectiveWeights,
    simulate_fn,
    space=None,
    deltas: Dict[str, float] | None = None,
) -> Tuple[Dict[str, float], List[str], List[SensitivityResult]]:
    """
    Explain the recommendation using:
    1) Base metrics (eff/tox/cost/score)
    2) Top risk/drivers from toxicity module
    3) Sensitivity analysis (small perturbations) on size/charge/dose

    - simulate_fn: same simulator function used by optimizer (placeholder or real)
    - space: optional DesignSpace, used only to clip perturbations into allowed ranges
    - deltas: optional dict like {"size_nm": 10.0, "zeta_mV": 5.0, "dose_mg_per_kg": 2.0}
    """
    if deltas is None:
        deltas = {"size_nm": 10.0, "zeta_mV": 5.0, "dose_mg_per_kg": 2.0}

    # ---- base evaluation ----
    base_sim = simulate_fn(design)
    base_eff = float(efficacy_proxy(base_sim))
    base_tox, base_drivers = toxicity_score_hybrid(design, base_sim)
    base_tox = float(base_tox)
    base_cost = float(cost_score_proxy(design))
    base_score = _scalar_score(weights, base_eff, base_tox, base_cost)

    base_summary = {
        "score": base_score,
        "efficacy": base_eff,
        "toxicity": base_tox,
        "cost": base_cost,
    }

    # ---- sensitivity analysis ----
    sens: List[SensitivityResult] = []

    def eval_with_mutation(param: str, new_value: float, direction: str, delta: float) -> SensitivityResult:
        d2 = _clone_design(design)

        # apply mutation
        if param == "size_nm":
            d2.size_nm = float(new_value)
        elif param == "zeta_mV":
            d2.zeta_mV = float(new_value)
        elif param == "dose_mg_per_kg":
            d2.dose_mg_per_kg = float(new_value)
        else:
            raise ValueError(f"Unknown parameter: {param}")

        sim2 = simulate_fn(d2)
        eff2 = float(efficacy_proxy(sim2))
        tox2, _ = toxicity_score_hybrid(d2, sim2)
        tox2 = float(tox2)
        cost2 = float(cost_score_proxy(d2))
        score2 = _scalar_score(weights, eff2, tox2, cost2)

        return SensitivityResult(
            param=param,
            direction=direction,
            delta=float(delta),
            base_score=base_score,
            new_score=score2,
            score_change=float(score2 - base_score),
            base_eff=base_eff,
            new_eff=eff2,
            eff_change=float(eff2 - base_eff),
            base_tox=base_tox,
            new_tox=tox2,
            tox_change=float(tox2 - base_tox),
            base_cost=base_cost,
            new_cost=cost2,
            cost_change=float(cost2 - base_cost),
        )

    # optional clipping ranges if DesignSpace provided
    def get_bounds(param: str) -> Tuple[float, float]:
        if space is None:
            # loose bounds (avoid nonsense)
            if param == "size_nm":
                return 1.0, 500.0
            if param == "zeta_mV":
                return -100.0, 100.0
            if param == "dose_mg_per_kg":
                return 0.0, 1000.0
            return -1e9, 1e9

        # DesignSpace is expected to have these attributes
        if param == "size_nm":
            return float(space.size_nm_min), float(space.size_nm_max)
        if param == "zeta_mV":
            return float(space.charge_mV_min), float(space.charge_mV_max)
        if param == "dose_mg_per_kg":
            return float(space.dose_min), float(space.dose_max)
        return -1e9, 1e9

    for p, dlt in deltas.items():
        lo, hi = get_bounds(p)

        # plus
        if p == "size_nm":
            new_val = _clip(float(design.size_nm) + float(dlt), lo, hi)
        elif p == "zeta_mV":
            new_val = _clip(float(design.zeta_mV) + float(dlt), lo, hi)
        elif p == "dose_mg_per_kg":
            new_val = _clip(float(design.dose_mg_per_kg) + float(dlt), lo, hi)
        else:
            continue
        sens.append(eval_with_mutation(p, new_val, "+", float(dlt)))

        # minus
        if p == "size_nm":
            new_val = _clip(float(design.size_nm) - float(dlt), lo, hi)
        elif p == "zeta_mV":
            new_val = _clip(float(design.zeta_mV) - float(dlt), lo, hi)
        elif p == "dose_mg_per_kg":
            new_val = _clip(float(design.dose_mg_per_kg) - float(dlt), lo, hi)
        else:
            continue
        sens.append(eval_with_mutation(p, new_val, "-", float(dlt)))

    return base_summary, list(base_drivers or []), sens
