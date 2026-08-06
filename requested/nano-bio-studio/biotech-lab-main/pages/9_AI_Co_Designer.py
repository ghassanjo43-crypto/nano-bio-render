# pages/9_AI_Co_Designer.py
#
# Phase-3 (UAE reviewer ready):
# ✅ Scenario / Policy Mode (presets + constraints)
# ✅ Audit & Governance Report export (JSON + HTML)
# ✅ Phase-2 proof panels: Exploration Summary, AI vs Manual Baseline, Explainability
#
# NOTE:
# - This page expects these modules to exist:
#   nanobio_studio/ai_engine/explainability.py
#   nanobio_studio/ai_engine/scenarios.py
#   nanobio_studio/ai_engine/audit.py
# - Optimizer must accept `constraints=` and log trial user_attrs (eff/tox/cost/rejected...)

import random
import pandas as pd
import streamlit as st

# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
from nanobio_studio.config import AI_DEFAULTS

from nanobio_studio.ai_engine.schema import DesignSpace, ObjectiveWeights
from nanobio_studio.ai_engine.optimizer import run_optimization
from nanobio_studio.ai_engine.pareto import pareto_front
from nanobio_studio.ai_engine.reporting import candidates_to_df
from nanobio_studio.ui.components.charts import pareto_scatter

from nanobio_studio.ai_engine.simulator_adapter import simulate_design_placeholder
from nanobio_studio.ai_engine.objectives import efficacy_proxy
from nanobio_studio.ai_engine.toxicity import toxicity_score_hybrid
from nanobio_studio.ai_engine.cost import cost_score_proxy

# Phase-2 Explainability
from nanobio_studio.ai_engine.explainability import explain_design

# Phase-3 Scenario Mode + Audit
from nanobio_studio.ai_engine.scenarios import get_scenarios
from nanobio_studio.ai_engine.audit import (
    build_audit_record,
    record_outcome,
    audit_to_json,
    audit_to_html,
)


st.set_page_config(page_title="NanoBio Studio — AI Co-Designer", layout="wide")
st.title("AI Co-Designer — Policy-Aware Optimization (Phase-3)")


# -----------------------------
# Panel 1: Exploration Summary
# -----------------------------
def render_ai_exploration_summary(study):
    rows = []
    for t in study.trials:
        if t.state.name != "COMPLETE":
            continue

        row = {}
        row.update(t.params)
        row["efficacy"] = t.user_attrs.get("efficacy")
        row["toxicity"] = t.user_attrs.get("toxicity")
        row["cost"] = t.user_attrs.get("cost")
        row["confidence"] = t.user_attrs.get("confidence")
        row["rejected"] = bool(t.user_attrs.get("rejected", False))
        row["reject_reason"] = t.user_attrs.get("reject_reason", "")

        if "pdi" not in row:
            row["pdi"] = t.user_attrs.get("pdi")

        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("No exploration data available yet. Run optimization first.")
        return

    n_total = len(df)
    n_rejected = int(df["rejected"].sum()) if "rejected" in df else 0
    n_valid = n_total - n_rejected

    def rng(col):
        if col not in df or df[col].dropna().empty:
            return None
        return float(df[col].min()), float(df[col].max())

    size_rng = rng("size_nm")
    zeta_rng = rng("zeta_mV")
    dose_rng = rng("dose_mg_per_kg")
    pdi_rng = rng("pdi")

    top_materials = df["material"].value_counts().head(3).to_dict() if "material" in df else {}
    top_ligands = df["ligand"].value_counts().head(3).to_dict() if "ligand" in df else {}
    top_payloads = df["payload"].value_counts().head(3).to_dict() if "payload" in df else {}

    with st.expander("✅ AI Exploration Summary (transparency)", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Designs evaluated", f"{n_total}")
        c2.metric("Valid designs", f"{n_valid}")
        c3.metric("Rejected (constraints)", f"{n_rejected}")
        c4.metric("Best trial score", f"{study.best_value:.2f}")

        st.markdown("### What the AI actually explored")
        g1, g2, g3, g4 = st.columns(4)
        g1.write(f"**Size (nm):** {size_rng[0]:.1f} → {size_rng[1]:.1f}" if size_rng else "**Size (nm):** —")
        g2.write(f"**Zeta (mV):** {zeta_rng[0]:.1f} → {zeta_rng[1]:.1f}" if zeta_rng else "**Zeta (mV):** —")
        g3.write(f"**Dose (mg/kg):** {dose_rng[0]:.2f} → {dose_rng[1]:.2f}" if dose_rng else "**Dose (mg/kg):** —")
        g4.write(f"**PDI:** {pdi_rng[0]:.3f} → {pdi_rng[1]:.3f}" if pdi_rng else "**PDI:** —")

        st.markdown("### What the AI tried most (top 3)")
        t1, t2, t3 = st.columns(3)
        t1.write("**Materials:** " + (", ".join([f"{k} ({v})" for k, v in top_materials.items()]) or "—"))
        t2.write("**Ligands:** " + (", ".join([f"{k} ({v})" for k, v in top_ligands.items()]) or "—"))
        t3.write("**Payloads:** " + (", ".join([f"{k} ({v})" for k, v in top_payloads.items()]) or "—"))

        if n_rejected > 0 and "reject_reason" in df:
            reasons = df.loc[df["rejected"] == True, "reject_reason"].value_counts().head(5).to_dict()
            if reasons:
                st.markdown("### Common rejection reasons")
                st.write(", ".join([f"{k} ({v})" for k, v in reasons.items()]))

        st.info(
            "This panel provides evidence that the AI explored many candidate designs, "
            "and applied constraints to filter out non-compliant options."
        )


# ---------------------------------
# Panel 2: AI vs Manual Baseline
# ---------------------------------
def render_ai_vs_manual_baseline(res, space, weights, simulate_fn, n_baseline: int = 80, seed: int = 42):
    w = weights.normalized()
    rng = random.Random(seed)

    ai_rows = []
    for t in res.study.trials:
        if t.state.name != "COMPLETE":
            continue

        eff = t.user_attrs.get("efficacy", None)
        tox = t.user_attrs.get("toxicity", None)
        cost = t.user_attrs.get("cost", None)
        rejected = bool(t.user_attrs.get("rejected", False))

        if eff is None or tox is None or cost is None:
            continue

        score = (w.efficacy * float(eff)) - (w.safety * float(tox)) - (w.cost * float(cost))
        ai_rows.append({"eff": float(eff), "tox": float(tox), "cost": float(cost), "score": float(score), "rejected": rejected})

    ai_df = pd.DataFrame(ai_rows)
    if ai_df.empty:
        st.warning("AI baseline comparison not available yet. Run optimization again.")
        return

    ai_valid = ai_df[~ai_df["rejected"]].copy()
    if ai_valid.empty:
        ai_valid = ai_df.copy()

    def sample_random_design():
        from nanobio_studio.core.types import NanoDesign

        size_nm = rng.uniform(space.size_nm_min, space.size_nm_max)
        zeta_mV = rng.uniform(space.charge_mV_min, space.charge_mV_max)

        material = rng.choice(space.materials) if space.materials else "PLGA"
        ligand = rng.choice(space.ligands) if space.ligands else "PEG"
        payload = rng.choice(space.payloads) if space.payloads else "DrugA"

        dose = rng.uniform(space.dose_min, space.dose_max)
        pdi = rng.uniform(0.12, 0.35)

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

    base_rows = []
    for _ in range(int(n_baseline)):
        d = sample_random_design()
        sim = simulate_fn(d)
        eff = float(efficacy_proxy(sim))
        tox, _ = toxicity_score_hybrid(d, sim)
        tox = float(tox)
        cost = float(cost_score_proxy(d))
        score = (w.efficacy * eff) - (w.safety * tox) - (w.cost * cost)
        base_rows.append({"eff": eff, "tox": tox, "cost": cost, "score": score})

    base_df = pd.DataFrame(base_rows)

    def fmax(df, col):
        return float(df[col].max()) if col in df and not df.empty else float("nan")

    def fmean(df, col):
        return float(df[col].mean()) if col in df and not df.empty else float("nan")

    with st.expander("📊 AI vs Manual Baseline (evidence of added value)", expanded=True):
        st.markdown(
            "This compares **AI-guided optimization** against a **random/manual-like baseline**. "
            "Both use the **same simulator and scoring rules**, so the comparison is fair."
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("AI trials", f"{len(ai_df)}")
        c2.metric("Baseline trials", f"{len(base_df)}")
        c3.metric("AI valid trials", f"{len(ai_valid)}")
        c4.metric("Weights", f"E:{w.efficacy:.2f}  S:{w.safety:.2f}  C:{w.cost:.2f}")

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Best AI score", f"{fmax(ai_valid, 'score'):.2f}")
        b2.metric("Best Baseline score", f"{fmax(base_df, 'score'):.2f}")
        b3.metric("Best AI efficacy", f"{fmax(ai_valid, 'eff'):.2f}")
        b4.metric("Best Baseline efficacy", f"{fmax(base_df, 'eff'):.2f}")

        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Avg AI toxicity", f"{fmean(ai_valid, 'tox'):.2f}")
        a2.metric("Avg Baseline toxicity", f"{fmean(base_df, 'tox'):.2f}")
        a3.metric("Avg AI cost", f"{fmean(ai_valid, 'cost'):.2f}")
        a4.metric("Avg Baseline cost", f"{fmean(base_df, 'cost'):.2f}")

        st.caption(
            "Interpretation: if AI achieves a higher best score and/or better efficacy with lower average "
            "toxicity/cost, it is providing measurable value over manual trial-and-error."
        )

    # Return a small summary for audit record
    baseline_summary = {
        "ai_trials": int(len(ai_df)),
        "baseline_trials": int(len(base_df)),
        "best_ai_score": float(fmax(ai_valid, "score")),
        "best_baseline_score": float(fmax(base_df, "score")),
        "avg_ai_toxicity": float(fmean(ai_valid, "tox")),
        "avg_baseline_toxicity": float(fmean(base_df, "tox")),
        "avg_ai_cost": float(fmean(ai_valid, "cost")),
        "avg_baseline_cost": float(fmean(base_df, "cost")),
    }
    return baseline_summary


# ---------------------------------
# Panel 3: Explainability (WHY)
# ---------------------------------
def render_explainability_panel(best_candidate, space, weights, simulate_fn):
    with st.expander("🧠 Why AI chose this design (Explainable AI)", expanded=True):
        base, drivers, sens = explain_design(
            design=best_candidate.design,
            weights=weights,
            simulate_fn=simulate_fn,
            space=space,
            deltas={"size_nm": 10.0, "zeta_mV": 5.0, "dose_mg_per_kg": 2.0},
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Base Score", f"{base['score']:.2f}")
        c2.metric("Efficacy", f"{base['efficacy']:.2f}")
        c3.metric("Toxicity", f"{base['toxicity']:.2f}")
        c4.metric("Cost", f"{base['cost']:.2f}")

        st.markdown("### Key drivers (risk / decision influences)")
        if drivers:
            st.write("• " + "\n• ".join(drivers[:6]))
        else:
            st.write("No explicit drivers were returned by the current toxicity model.")

        st.markdown("### Sensitivity test (small parameter nudges)")
        rows = []
        for r in sens:
            rows.append(
                {
                    "Parameter": r.param,
                    "Change": f"{r.direction}{r.delta}",
                    "Δ Score": float(r.score_change),
                    "Δ Efficacy": float(r.eff_change),
                    "Δ Toxicity": float(r.tox_change),
                    "Δ Cost": float(r.cost_change),
                    "New Score": float(r.new_score),
                }
            )
        df = pd.DataFrame(rows)
        if df.empty:
            st.warning("No sensitivity results were produced.")
            return {}

        df["abs_Δ Score"] = df["Δ Score"].abs()
        df = df.sort_values("abs_Δ Score", ascending=False).drop(columns=["abs_Δ Score"])
        st.dataframe(df, use_container_width=True, hide_index=True)

        top = df.iloc[0]
        st.success(
            f"Most influential knob (in this model): **{top['Parameter']}** "
            f"({top['Change']} causes Δ Score = {top['Δ Score']:+.2f})."
        )

    # Return a compact summary for audit record
    explain_summary = {
        "base_score": float(base["score"]),
        "base_efficacy": float(base["efficacy"]),
        "base_toxicity": float(base["toxicity"]),
        "base_cost": float(base["cost"]),
        "top_driver": drivers[0] if drivers else None,
        "most_influential_knob": str(top["Parameter"]) if not df.empty else None,
    }
    return explain_summary


# -----------------------------
# Sidebar controls + Scenario Mode
# -----------------------------
with st.sidebar:
    st.header("Scenario / Policy Mode")

    scenarios = get_scenarios()
    scenario_name = st.selectbox("Select scenario", list(scenarios.keys()), index=1)
    scenario = scenarios[scenario_name]
    st.caption(scenario.description)

    use_scenario = st.checkbox("Lock to scenario presets (recommended for reviewers)", value=True)

    st.divider()
    st.header("Design Space")

    size_min = st.number_input("Size min (nm)", value=float(AI_DEFAULTS.size_nm_min), min_value=1.0)
    size_max = st.number_input("Size max (nm)", value=float(AI_DEFAULTS.size_nm_max), min_value=1.0)

    charge_min = st.number_input("Zeta min (mV)", value=float(AI_DEFAULTS.charge_mV_min))
    charge_max = st.number_input("Zeta max (mV)", value=float(AI_DEFAULTS.charge_mV_max))

    default_dose_min = float(getattr(AI_DEFAULTS, "dose_min", 1.0))
    default_dose_max = float(getattr(AI_DEFAULTS, "dose_max", 20.0))
    dose_min = st.number_input("Dose min (mg/kg)", value=default_dose_min, min_value=0.0)
    dose_max = st.number_input("Dose max (mg/kg)", value=default_dose_max, min_value=0.0)

    materials = st.multiselect("Materials", ["PLGA", "Lipid", "Gold"], default=["PLGA", "Lipid"])
    ligands = st.multiselect("Ligands", ["None", "PEG", "Folate"], default=["PEG", "None"])
    payloads = st.multiselect("Payloads", ["DrugA", "DrugB"], default=["DrugA"])

    st.divider()
    st.header("Objective Weights")

    # If scenario is locked, show weights read-only
    if use_scenario:
        st.write(f"**Efficacy:** {scenario.weights.efficacy:.2f}")
        st.write(f"**Safety:** {scenario.weights.safety:.2f}")
        st.write(f"**Cost:** {scenario.weights.cost:.2f}")
    else:
        w_eff = st.slider("Efficacy", 0.0, 1.0, 0.50, 0.05)
        w_safe = st.slider("Safety", 0.0, 1.0, 0.30, 0.05)
        w_cost = st.slider("Cost", 0.0, 1.0, 0.20, 0.05)

    st.divider()
    st.header("Run Settings")

    if use_scenario:
        n_trials = st.number_input("Trials", min_value=20, max_value=2000, value=int(scenario.recommended_trials), step=20)
        top_k = st.number_input("Top K results", min_value=3, max_value=50, value=int(scenario.recommended_top_k), step=1)
    else:
        n_trials = st.number_input("Trials", min_value=20, max_value=2000, value=int(AI_DEFAULTS.n_trials), step=20)
        top_k = st.number_input("Top K results", min_value=3, max_value=50, value=int(AI_DEFAULTS.top_k), step=1)

    st.divider()
    st.header("Baseline Comparison")
    n_baseline = st.number_input("Baseline trials", min_value=20, max_value=500, value=80, step=10)


# -----------------------------
# Build space + weights + constraints
# -----------------------------
space = DesignSpace(
    size_nm_min=float(min(size_min, size_max)),
    size_nm_max=float(max(size_min, size_max)),
    charge_mV_min=float(min(charge_min, charge_max)),
    charge_mV_max=float(max(charge_min, charge_max)),
    dose_min=float(min(dose_min, dose_max)),
    dose_max=float(max(dose_min, dose_max)),
    materials=materials or ["PLGA"],
    ligands=ligands or ["PEG"],
    payloads=payloads or ["DrugA"],
)

if use_scenario:
    weights = scenario.weights
    toxicity_max = scenario.toxicity_max
    cost_max = scenario.cost_max
else:
    weights = ObjectiveWeights(efficacy=float(w_eff), safety=float(w_safe), cost=float(w_cost))
    toxicity_max = None
    cost_max = None

constraints = {
    "toxicity_max": toxicity_max,
    "cost_max": cost_max,
    "scenario_description": scenario.description,
}

colA, colB = st.columns([1, 1], gap="large")

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None
if "last_audit" not in st.session_state:
    st.session_state.last_audit = None

run = st.button("🚀 Run Optimization", type="primary")

if run:
    with st.spinner("Optimizing (policy-aware Bayesian TPE)..."):
        res = run_optimization(
            space=space,
            weights=weights,
            n_trials=int(n_trials),
            seed=int(AI_DEFAULTS.random_seed),
            simulate_fn=simulate_design_placeholder,  # replace with real simulator later
            top_k=int(top_k),
            constraints=constraints,  # ✅ policy constraints
        )
        st.session_state.ai_result = res

        # Create an audit record (configuration first)
        run_settings = {"n_trials": int(n_trials), "top_k": int(top_k), "seed": int(AI_DEFAULTS.random_seed)}
        audit = build_audit_record(
            scenario_name=scenario_name,
            scenario_key=scenario.key,
            space=space,
            weights=weights,
            constraints=constraints,
            run_settings=run_settings,
        )
        st.session_state.last_audit = audit

res = st.session_state.ai_result
if res is None:
    st.info("Select a scenario, configure the design space, then click **Run Optimization**.")
    st.stop()

best = res.best


# -----------------------------
# Evidence panels (and capture summaries for audit)
# -----------------------------
render_ai_exploration_summary(res.study)

baseline_summary = render_ai_vs_manual_baseline(
    res=res,
    space=space,
    weights=weights,
    simulate_fn=simulate_design_placeholder,
    n_baseline=int(n_baseline),
    seed=int(AI_DEFAULTS.random_seed),
)

explainability_summary = render_explainability_panel(
    best_candidate=best,
    space=space,
    weights=weights,
    simulate_fn=simulate_design_placeholder,
)

# Update audit record with outcomes + evidence summaries
audit = st.session_state.get("last_audit", None)
if audit is not None:
    audit = record_outcome(
        audit=audit,
        res=res,
        baseline_summary=baseline_summary,
        explainability_summary=explainability_summary,
    )
    st.session_state.last_audit = audit


# -----------------------------
# Audit & Governance Report export
# -----------------------------
audit = st.session_state.get("last_audit", None)
if audit:
    with st.expander("📄 Audit & Governance Report (UAE-reviewer ready)", expanded=True):
        st.write("Export a reproducible decision record (scenario, constraints, weights, evidence, outcomes).")
        json_str = audit_to_json(audit)
        html_str = audit_to_html(audit)

        st.download_button(
            "⬇️ Download JSON (Audit Record)",
            data=json_str,
            file_name="nanobio_audit.json",
            mime="application/json",
        )
        st.download_button(
            "⬇️ Download HTML (Printable Report)",
            data=html_str,
            file_name="nanobio_audit_report.html",
            mime="text/html",
        )
        st.caption("Tip: Open the HTML file in a browser and print to PDF for formal submission.")


# -----------------------------
# Main outputs
# -----------------------------
cands = res.candidates
df = candidates_to_df(cands)

with colA:
    st.subheader("Top Recommendations")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Best Candidate (policy-aware)")
    st.json(
        {
            "scenario": scenario_name,
            "constraints": constraints,
            "design": {
                "size_nm": best.design.size_nm,
                "zeta_mV": best.design.zeta_mV,
                "material": best.design.material,
                "ligand": best.design.ligand,
                "payload": best.design.payload,
                "dose_mg_per_kg": best.design.dose_mg_per_kg,
                "pdi": best.design.pdi,
            },
            "scores": {
                "efficacy": float(best.efficacy),
                "toxicity": float(best.toxicity),
                "cost": float(best.cost),
                "confidence": float(best.confidence),
            },
            "top_drivers": best.drivers[:5] if best.drivers else [],
        }
    )

with colB:
    st.subheader("Pareto Front (Efficacy vs Toxicity, colored by Cost)")
    pf = pareto_front(cands)
    st.plotly_chart(pareto_scatter(cands, pf), use_container_width=True)

    st.subheader("Study Summary")
    st.write(f"Best trial value: {res.study.best_value:.4f}")
    st.write(f"Best params: {res.study.best_params}")
