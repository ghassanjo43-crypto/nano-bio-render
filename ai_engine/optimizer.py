# nanobio_studio/ai_engine/optimizer.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import optuna

from nanobio_studio.core.types import NanoDesign, ScoredCandidate
from nanobio_studio.ai_engine.schema import DesignSpace, ObjectiveWeights
from nanobio_studio.ai_engine.simulator_adapter import SimulateFn, simulate_design_placeholder
from nanobio_studio.ai_engine.objectives import efficacy_proxy, scalarized_score
from nanobio_studio.ai_engine.toxicity import toxicity_score_hybrid
from nanobio_studio.ai_engine.cost import cost_score_proxy
from nanobio_studio.ai_engine.uncertainty import simple_confidence_from_rules, seed_everything


@dataclass
class OptimizationResult:
    candidates: List[ScoredCandidate]
    best: ScoredCandidate
    study: optuna.Study


def _suggest_design(trial: optuna.Trial, space: DesignSpace) -> NanoDesign:
    """Sample a nanoparticle design from the configured DesignSpace."""
    size_nm = trial.suggest_float("size_nm", space.size_nm_min, space.size_nm_max)
    zeta_mV = trial.suggest_float("zeta_mV", space.charge_mV_min, space.charge_mV_max)

    material = space.fixed.get("material") if getattr(space, "fixed", None) else None
    ligand = space.fixed.get("ligand") if getattr(space, "fixed", None) else None
    payload = space.fixed.get("payload") if getattr(space, "fixed", None) else None

    material = material or trial.suggest_categorical("material", space.materials)
    ligand = ligand or trial.suggest_categorical("ligand", space.ligands)
    payload = payload or trial.suggest_categorical("payload", space.payloads)

    dose = trial.suggest_float("dose_mg_per_kg", space.dose_min, space.dose_max)

    # PDI in Phase-2 is still sampled (can be fixed later).
    pdi = trial.suggest_float("pdi", 0.12, 0.35)

    return NanoDesign(
        size_nm=float(size_nm),
        zeta_mV=float(zeta_mV),
        material=str(material),
        ligand=str(ligand),
        payload=str(payload),
        dose_mg_per_kg=float(dose),
        pdi=float(pdi),
        extra={},
    )


def run_optimization(
    space: DesignSpace,
    weights: ObjectiveWeights,
    n_trials: int = 200,
    seed: int = 42,
    simulate_fn: SimulateFn = simulate_design_placeholder,
    top_k: int = 10,
    constraints: Optional[Dict[str, Any]] = None,  # ✅ NEW (Scenario Mode constraints)
) -> OptimizationResult:
    """
    Phase-2/3 Optimizer:
    - Optuna TPE sampler to search designs efficiently
    - Computes efficacy/toxicity/cost
    - Scalarizes objectives (maximize efficacy, minimize toxicity and cost)
    - Applies scenario/policy constraints (optional), e.g. toxicity_max, cost_max
    - Logs trial attrs for transparency panels (exploration, baseline, audit)

    NOTE: Still uses single-objective scalarization (Phase-2), but supports policy constraints (Phase-3).
    """
    seed_everything(seed)
    w = weights.normalized()

    constraints = constraints or {}
    TOX_MAX = constraints.get("toxicity_max", None)
    COST_MAX = constraints.get("cost_max", None)

    scored: List[ScoredCandidate] = []

    # Hard constraint example (can be adjusted)
    HARD_PDI_REJECT = 0.35

    def objective(trial: optuna.Trial) -> float:
        design = _suggest_design(trial, space)

        # Run simulation (replace simulate_fn with your real simulator later)
        sim = simulate_fn(design)

        # Compute proxies / scores
        eff = float(efficacy_proxy(sim))
        tox, drivers = toxicity_score_hybrid(design, sim)
        tox = float(tox)
        cost = float(cost_score_proxy(design))
        conf = float(simple_confidence_from_rules(tox, cost))

        # Defaults
        rejected = False
        reject_reason = None

        # --- Hard constraint: PDI ---
        if design.pdi > HARD_PDI_REJECT:
            rejected = True
            reject_reason = f"pdi>{HARD_PDI_REJECT}"

        # --- Scenario / Policy constraints ---
        if (not rejected) and (TOX_MAX is not None) and (tox > float(TOX_MAX)):
            rejected = True
            reject_reason = f"toxicity>{TOX_MAX}"

        if (not rejected) and (COST_MAX is not None) and (cost > float(COST_MAX)):
            rejected = True
            reject_reason = f"cost>{COST_MAX}"

        # --- NEW: log what the AI tried (so UI can prove exploration) ---
        trial.set_user_attr("efficacy", eff)
        trial.set_user_attr("toxicity", tox)
        trial.set_user_attr("cost", cost)
        trial.set_user_attr("confidence", conf)
        trial.set_user_attr("pdi", float(design.pdi))
        trial.set_user_attr("drivers", (drivers or [])[:5])

        trial.set_user_attr("rejected", bool(rejected))
        if reject_reason:
            trial.set_user_attr("reject_reason", str(reject_reason))

        # Keep a full scored candidate list for later display
        cand = ScoredCandidate(
            design=design,
            sim=sim,
            efficacy=eff,
            toxicity=tox,
            cost=cost,
            confidence=conf,
            drivers=drivers,
        )
        scored.append(cand)

        # Reject = return very low value
        if rejected:
            return -1e9

        # Scalarized score (Optuna maximizes)
        return float(
            scalarized_score(
                efficacy=eff,
                toxicity=tox,
                cost=cost,
                w_eff=w.efficacy,
                w_safe=w.safety,
                w_cost=w.cost,
            )
        )

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=int(n_trials))

    # Rank candidates by the same scalarization used in the objective
    def scalar(c: ScoredCandidate) -> float:
        return float((w.efficacy * c.efficacy) - (w.safety * c.toxicity) - (w.cost * c.cost))

    # Filter out clearly rejected candidates (extremely low scores), but keep best list robustly
    scored.sort(key=lambda c: (-scalar(c), c.toxicity, c.cost))

    best = scored[0]
    return OptimizationResult(candidates=scored[: int(top_k)], best=best, study=study)
