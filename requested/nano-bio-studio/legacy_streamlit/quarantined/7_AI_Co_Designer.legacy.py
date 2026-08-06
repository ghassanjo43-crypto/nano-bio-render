# ###########################################################################
# QUARANTINED SYNTHETIC DEMONSTRATION DATA -- DO NOT EXECUTE, DO NOT IMPORT
# ###########################################################################
#
# Preserved verbatim under DECISION 7 (Phase 2 Step 1) as a reference copy of
# the pre-correction AI Co-Designer page. It is NOT part of the running
# application: it lives outside `pages/`, so Streamlit will not route to it.
#
# Everything this file renders is SYNTHETIC DEMONSTRATION DATA. None of it was
# produced by an optimisation run:
#
#   * five "Mock candidate designs" with fixed scores 94.2 / 91.5 / 89.8 /
#     87.3 / 84.9, identical for every design input;
#   * a "why these were suggested" rationale generated from static text;
#   * mock parameter distributions and a fabricated Pareto front;
#   * fabricated key metrics ("Best Overall Score 94.2/100",
#     "Feasible Designs 387/500", "+5.1 vs baseline");
#   * fabricated feature-importance and sensitivity curves;
#   * a fabricated AUDIT TRAIL, including a hard-coded timestamp
#     ("2026-03-17 15:30:45 UTC") and fabricated constraint-violation counts.
#
# The audit trail is the most serious of these: it presented governance
# evidence for an optimisation run that never happened.
#
# This data must NEVER be mixed with, compared against, or persisted alongside
# real saved simulations (DECISION 7.6).
#
# The live page now shows a clearly labelled non-operational status instead.
# The feature remains part of the intended platform and returns once the
# optimisation engine is repaired and tested (separately authorised work).
# ###########################################################################

﻿"""
AI Co-Designer — Policy-Aware Optimization
Advanced nanoparticle design using AI optimization
"""

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="NanoBio Studio - AI Co-Designer", layout="wide")

st.title("🤖 AI Co-Designer — Policy-Aware Optimization")

# Check if user is logged in
if not st.session_state.get("logged_in"):
    st.warning("⚠️ Please log in first")
    st.info("You need to be logged in to access this page.")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔐 Go to Login", type="primary", use_container_width=True):
            st.query_params.clear()
            st.switch_page("Login.py")
    
    st.stop()

st.subheader("Advanced AI-Driven Nanoparticle Design Optimization")

# Initialize disease in session state if not present
if "selected_disease" not in st.session_state:
    st.warning("⚠️ **No disease selected yet**")
    st.info("""
    Please go back to **Step 1: Disease & Drug Selection** to choose a disease first.
    
    The AI Co-Designer optimizes recommendations specifically for your chosen disease.
    """)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("📋 Go to Disease Selection (Step 1)", type="primary", use_container_width=True):
            st.switch_page("pages/0_Disease_Selection.py")
    
    st.stop()

# ============================================================
# SIMPLE EXPLANATION FOR LAYMAN
# ============================================================

with st.expander("❓ What is AI Co-Designer? (Simple Explanation)", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🎯 What problem does it solve?
        
        Designing a nanoparticle involves **hundreds of choices**:
        - Size, charge, material, drug, dose
        - Testing all combinations in a lab would be **expensive and slow**
        
        **AI Co-Designer helps you pick the best options first.**
        """)
    
    with col2:
        st.markdown("""
        ### 🤖 How does it work?
        
        1. ⬅️ **You choose your priorities** using the settings on the left sidebar:
           - "Safety-First" for toxicity focus
           - "Delivery-First" for efficacy focus
           - "Cost-Optimized" for manufacturing cost
           - "Custom" to set your own weights
        2. The AI tests many designs on the computer
        3. It shows you the **top 5-10 best designs**
        4. You pick which ones to actually test in the lab
        """)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 📊 What does it show?
        
        ✅ Ranked list of best designs  
        ✅ Performance vs safety vs cost trade-offs  
        ✅ Why each design was suggested  
        ✅ Reports for supervisors
        """)
    
    with col2:
        st.markdown("""
        ### ❌ What it does NOT do
        
        ❌ Replace your judgment  
        ❌ Treat patients  
        ❌ Make final decisions  
        ✅ **Assist your decision-making**
        """)
    
    st.success("**Bottom line:** AI Co-Designer is like a smart filter that helps you find promising nanoparticles to test, instead of testing blindly.")

st.divider()

# ============================================================
# INITIALIZE SESSION STATE & SCENARIOS
# ============================================================

# Define scenarios once globally so it's accessible everywhere
scenarios = {
    "Balanced": "Equal weight to delivery, safety, and cost",
    "Delivery-First": "Maximize delivery efficacy",
    "Safety-First": "Minimize toxicity and side effects",
    "Cost-Optimized": "Minimize manufacturing cost",
    "Custom": "Define custom weights"
}

# Initialize session state with defaults
if "selected_scenario" not in st.session_state:
    st.session_state.selected_scenario = "Balanced"
if "delivery_weight" not in st.session_state:
    st.session_state.delivery_weight = 0.4
if "safety_weight" not in st.session_state:
    st.session_state.safety_weight = 0.3
if "cost_weight" not in st.session_state:
    st.session_state.cost_weight = 0.3
if "n_trials" not in st.session_state:
    st.session_state.n_trials = 100
if "use_active_learning" not in st.session_state:
    st.session_state.use_active_learning = True

# ============================================================
# SIDEBAR: Optimization Configuration
# ============================================================

with st.sidebar:
    st.header("⚙️ Optimization Settings")
    
    st.markdown("### Scenario Selection")
    
    # Use session state for selectbox - update it when changed
    scenario_idx = list(scenarios.keys()).index(st.session_state.selected_scenario) if st.session_state.selected_scenario in scenarios else 0
    st.session_state.selected_scenario = st.selectbox(
        "Scenario Mode",
        list(scenarios.keys()),
        index=scenario_idx
    )
    st.caption(scenarios[st.session_state.selected_scenario])
    
    st.divider()
    
    # Optimization parameters
    st.markdown("### Objective Weights")
    
    if st.session_state.selected_scenario == "Custom":
        st.session_state.delivery_weight = st.number_input("Delivery Priority", min_value=0.0, max_value=1.0, value=st.session_state.delivery_weight, step=0.05, format="%.2f")
        st.session_state.safety_weight = st.number_input("Safety Priority", min_value=0.0, max_value=1.0, value=st.session_state.safety_weight, step=0.05, format="%.2f")
        st.session_state.cost_weight = st.number_input("Cost Priority", min_value=0.0, max_value=1.0, value=st.session_state.cost_weight, step=0.05, format="%.2f")
    else:
        # Pre-defined weights
        weights = {
            "Balanced": {"delivery": 0.4, "safety": 0.3, "cost": 0.3},
            "Delivery-First": {"delivery": 0.6, "safety": 0.2, "cost": 0.2},
            "Safety-First": {"delivery": 0.2, "safety": 0.6, "cost": 0.2},
            "Cost-Optimized": {"delivery": 0.3, "safety": 0.3, "cost": 0.4},
        }
        w = weights[st.session_state.selected_scenario]
        st.session_state.delivery_weight = w["delivery"]
        st.session_state.safety_weight = w["safety"]
        st.session_state.cost_weight = w["cost"]
        
        st.metric("Delivery", f"{st.session_state.delivery_weight:.1%}")
        st.metric("Safety", f"{st.session_state.safety_weight:.1%}")
        st.metric("Cost", f"{st.session_state.cost_weight:.1%}")
    
    st.divider()
    
    # Constraints
    st.markdown("### Design Constraints")
    
    st.session_state.size_constraint = st.checkbox("Size Constraint (80-120 nm)", value=True)
    st.session_state.charge_constraint = st.checkbox("Charge Constraint (±10 mV)", value=True)
    st.session_state.tox_constraint = st.checkbox("Toxicity Limit (< 3/10)", value=True)
    
    st.divider()
    
    # Optimization settings
    st.session_state.n_trials = st.number_input("Optimization Trials", min_value=10, max_value=500, value=st.session_state.n_trials, step=10)
    st.session_state.use_active_learning = st.checkbox("Use Active Learning", value=st.session_state.use_active_learning)

# ============================================================
# PRIORITY SELECTION - VISIBLE IN MAIN CONTENT AREA
# ============================================================

st.subheader("📋 Step 1: Set Your Optimization Priorities")

priority_cols = st.columns(5)

with priority_cols[0]:
    if st.button("🎯 Balanced", use_container_width=True, 
                 type="primary" if st.session_state.selected_scenario == "Balanced" else "secondary"):
        st.session_state.selected_scenario = "Balanced"
        st.rerun()

with priority_cols[1]:
    if st.button("💰 Delivery", use_container_width=True,
                 type="primary" if st.session_state.selected_scenario == "Delivery-First" else "secondary"):
        st.session_state.selected_scenario = "Delivery-First"
        st.rerun()

with priority_cols[2]:
    if st.button("🛡️ Safety", use_container_width=True,
                 type="primary" if st.session_state.selected_scenario == "Safety-First" else "secondary"):
        st.session_state.selected_scenario = "Safety-First"
        st.rerun()

with priority_cols[3]:
    if st.button("💵 Cost", use_container_width=True,
                 type="primary" if st.session_state.selected_scenario == "Cost-Optimized" else "secondary"):
        st.session_state.selected_scenario = "Cost-Optimized"
        st.rerun()

with priority_cols[4]:
    if st.button("⚙️ Custom", use_container_width=True,
                 type="primary" if st.session_state.selected_scenario == "Custom" else "secondary"):
        st.session_state.selected_scenario = "Custom"
        st.rerun()

# Show current priority configuration
st.markdown(f"""
**Current Setting:** `{st.session_state.selected_scenario}` - {scenarios[st.session_state.selected_scenario]}

**Weight Distribution:**
- **Delivery:** {st.session_state.delivery_weight:.0%}
- **Safety:** {st.session_state.safety_weight:.0%}  
- **Cost:** {st.session_state.cost_weight:.0%}
""")

st.info("💡 **What do these mean?**\n\n"
        "- **Delivery-First:** Find designs that work best in the body\n"
        "- **Safety-First:** Find designs with lowest toxicity and side effects\n"
        "- **Cost-Optimized:** Find designs that are cheapest to manufacture\n"
        "- **Balanced:** Mix all three equally\n"
        "- **Custom:** Set your own mix using the sidebar controls")

st.divider()

# Show optimization context - get fresh disease from session
selected_disease = st.session_state.get("selected_disease", None)

if selected_disease is None:
    st.error("⚠️ Disease not found in session. Please go back to Step 1 and select a disease.")
    if st.button("Return to Step 1"):
        st.switch_page("pages/0_Disease_Selection.py")
    st.stop()

# Display prominent optimization context box
st.markdown(f"""
### 🎯 Optimization Context
**Disease:** 🏥 **{selected_disease}**  
**Priority:** 💎 **{st.session_state.selected_scenario}**  
**Status:** ✅ **Ready to optimize**

---
*All recommendations below are specifically tailored for {selected_disease} with {st.session_state.selected_scenario} priority.*
""")

st.divider()

# ============================================================
# MAIN TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 AI Optimization",
    "📊 Results Analysis",
    "🔍 Explainability",
    "📋 Audit Report"
])

# TAB 1: AI OPTIMIZATION
with tab1:
    st.subheader("AI-Driven Design Optimization")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### Optimization Engine")
        
        if st.button("▶️ Start Optimization", type="primary", use_container_width=True):
            st.info(f"Running {st.session_state.n_trials} optimization trials with {st.session_state.selected_scenario} scenario...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i in range(st.session_state.n_trials):
                progress_bar.progress((i + 1) / st.session_state.n_trials)
                status_text.text(f"Trial {i + 1}/{st.session_state.n_trials} - Finding optimal designs...")
                import time
                time.sleep(0.01)
            
            st.success("✅ Optimization completed!")
            st.balloons()
    
    with col2:
        st.markdown("### Constraints Status")
        if st.session_state.size_constraint:
            st.success("✅ Size: 80-120 nm")
        if st.session_state.charge_constraint:
            st.success("✅ Charge: ±10 mV")
        if st.session_state.tox_constraint:
            st.success("✅ Toxicity: < 3/10")
    
    st.divider()
    
    st.markdown("### Top Candidate Designs")
    
    # Get disease context
    selected_disease = st.session_state.get("selected_disease", "Liver Cancer (HCC)")
    
    # Generate disease & priority-aware material recommendations
    disease_material_pools = {
        "Liver Cancer (HCC)": {
            "Balanced": ["Lipid NP", "PLGA", "Lipid NP", "Gold NP", "PLGA"],
            "Delivery-First": ["Gold NP", "Lipid NP", "Copper NP", "Silica NP", "Lipid NP"],
            "Safety-First": ["PLGA", "Lipid NP", "PLGA", "Polymer NP", "Lipid NP"],
            "Cost-Optimized": ["Polymer NP", "PLGA", "Polymer NP", "Lipid NP", "PLGA"],
            "Custom": ["Lipid NP", "Gold NP", "PLGA", "Copper NP", "Silica NP"],
        },
        "Breast Cancer": {
            "Balanced": ["Lipid NP", "Polymer NP", "Lipid NP", "Silica NP", "PLGA"],
            "Delivery-First": ["Gold NP", "Silica NP", "Copper NP", "Lipid NP", "Polymer NP"],
            "Safety-First": ["PLGA", "Polymer NP", "Lipid NP", "PLGA", "Silica NP"],
            "Cost-Optimized": ["PLGA", "Polymer NP", "PLGA", "Lipid NP", "Polymer NP"],
            "Custom": ["Silica NP", "Lipid NP", "Gold NP", "PLGA", "Polymer NP"],
        },
        "Melanoma": {
            "Balanced": ["Lipid NP", "Gold NP", "Lipid NP", "Copper NP", "PLGA"],
            "Delivery-First": ["Gold NP", "Copper NP", "Lipid NP", "Silica NP", "Gold NP"],
            "Safety-First": ["PLGA", "Lipid NP", "Polymer NP", "Lipid NP", "PLGA"],
            "Cost-Optimized": ["Polymer NP", "PLGA", "Lipid NP", "Polymer NP", "PLGA"],
            "Custom": ["Gold NP", "Lipid NP", "Copper NP", "PLGA", "Silica NP"],
        },
        "Pancreatic Cancer": {
            "Balanced": ["PLGA", "Lipid NP", "Polymer NP", "Lipid NP", "PLGA"],
            "Delivery-First": ["Silica NP", "Lipid NP", "Gold NP", "Polymer NP", "Lipid NP"],
            "Safety-First": ["PLGA", "Polymer NP", "Lipid NP", "PLGA", "Polymer NP"],
            "Cost-Optimized": ["Polymer NP", "PLGA", "PLGA", "Lipid NP", "Polymer NP"],
            "Custom": ["Lipid NP", "PLGA", "Silica NP", "Polymer NP", "PLGA"],
        },
        "Lung Cancer": {
            "Balanced": ["Lipid NP", "PLGA", "Lipid NP", "Copper NP", "PLGA"],
            "Delivery-First": ["Copper NP", "Lipid NP", "Silica NP", "Gold NP", "Lipid NP"],
            "Safety-First": ["PLGA", "Lipid NP", "PLGA", "Polymer NP", "Lipid NP"],
            "Cost-Optimized": ["Polymer NP", "PLGA", "Polymer NP", "Lipid NP", "PLGA"],
            "Custom": ["Lipid NP", "Copper NP", "PLGA", "Silica NP", "Gold NP"],
        },
    }
    
    # Get materials for this disease (default to HCC if disease not found)
    disease_materials = disease_material_pools.get(selected_disease, disease_material_pools["Liver Cancer (HCC)"])
    selected_materials = disease_materials.get(st.session_state.selected_scenario, ["Lipid NP", "PLGA", "Lipid NP", "Gold NP", "PLGA"])
    
    # ======================================================================
    # QUARANTINED under DECISION 7 (DEFECT-D6 / DEFECT-D7), Phase 2 Step 1
    # ======================================================================
    # This block previously rendered a hard-coded pandas DataFrame of five
    # "Mock candidate designs" with fabricated scores
    # (94.2 / 91.5 / 89.8 / 87.3 / 84.9) and a "why these were suggested"
    # rationale, presented as AI optimisation output. No optimisation ever ran:
    # only the Material column varied, via a dict lookup on disease/scenario.
    # The real optimiser (`ai_engine`) is un-importable (DEFECT-D7), and its
    # `optuna` dependency is reachable by nothing.
    #
    # Per DECISION 7 the fabricated scores are REMOVED and the rationale is NOT
    # generated, because it was not traceable to any real optimisation run.
    # The feature itself is preserved in the product architecture and will be
    # restored once the engine is repaired and tested (a later, separately
    # authorised step -- not Step 1).
    # ======================================================================

    st.warning(
        "### AI Co-Designer is not yet operational\n\n"
        "This feature does not currently produce optimisation results.\n\n"
        "The underlying optimisation engine is not available in this build, so "
        "**no candidate designs can be generated**. Previous versions of this "
        "screen displayed fixed placeholder numbers that were not produced by "
        "any optimisation run; those have been removed rather than shown as "
        "results.\n\n"
        "The feature remains part of the planned platform and will return once "
        "the optimisation engine is repaired, tested, and able to show where "
        "each candidate and its rationale came from."
    )

    st.caption(
        "Status: not operational — awaiting optimisation-engine repair. "
        "No synthetic or placeholder candidates are shown. When restored, all "
        "outputs will remain computational research-planning results: not "
        "experimentally validated, not clinically validated, and not a "
        "substitute for wet-lab testing."
    )

    with st.expander("What was removed, and why"):
        st.markdown(
            "- Five placeholder candidate rows with fixed scores were displayed "
            "as though ranked by an optimiser. They were constants, identical "
            "for every design input.\n"
            "- An accompanying \"why these were suggested\" explanation was "
            "generated from static text, not from any optimisation objective.\n"
            "- Only the material column changed, from a lookup table keyed on "
            "the selected disease and priority.\n\n"
            "Removing them prevents placeholder values being mistaken for, or "
            "saved alongside, real simulation results."
        )

    # `selected_materials` is retained only as an input-echo for the disease /
    # scenario selection above. It is NOT an optimisation result and must not be
    # persisted with, or compared against, real saved simulations.
    st.caption(
        "Material families associated with the current selection "
        f"({selected_disease} / {st.session_state.selected_scenario}): "
        + ", ".join(dict.fromkeys(selected_materials))
        + " — reference list from a static lookup table, not a ranked "
          "optimisation output."
    )

# TAB 2: RESULTS ANALYSIS
with tab2:
    st.subheader("Optimization Results & Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Parameter Distribution")
        
        # Mock distribution data
        size_opt = [95, 98, 100, 102, 105, 108]
        charge_opt = [-8, -5, -2, 0, 2, 5]
        
        st.write("Optimal Size Range")
        st.bar_chart(pd.Series([2, 3, 5, 4, 3, 2], index=size_opt))
        
        st.write("Optimal Charge Range")
        st.bar_chart(pd.Series([1, 3, 4, 5, 3, 2], index=charge_opt))
    
    with col2:
        st.markdown("### Pareto Front")
        
        # Create Pareto front visualization
        pareto_data = pd.DataFrame({
            "Safety": [88, 89, 90, 91, 92, 93, 94, 95],
            "Cost": [92, 90, 88, 85, 82, 78, 72, 65],
        })
        
        st.line_chart(pareto_data.set_index("Safety"))
        st.caption("Trade-off between Safety and Cost optimization")
    
    st.divider()
    
    st.markdown("### Key Insights")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Best Overall Score", "94.2/100", "+5.1 vs baseline")
    with col2:
        st.metric("Average Score", "87.3/100", "+3.2 vs baseline")
    with col3:
        st.metric("Feasible Designs", "387/500", "77.4%")

# TAB 3: EXPLAINABILITY
with tab3:
    st.subheader("Design Explainability & Impact Analysis")
    
    st.markdown("### Feature Importance for Top Design")
    
    feature_importance = pd.DataFrame({
        "Feature": ["Size", "Charge", "Material", "PDI", "Encapsulation", "Stability"],
        "Impact": [0.28, 0.22, 0.18, 0.15, 0.12, 0.05]
    }).sort_values("Impact", ascending=False)
    
    st.bar_chart(feature_importance.set_index("Feature"))
    
    st.divider()
    
    st.markdown("### Parameter Sensitivity Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Size Sensitivity**")
        size_sensitivity = pd.DataFrame({
            "Size (nm)": [80, 90, 100, 110, 120],
            "Score Impact": [75, 82, 95, 88, 72]
        })
        st.line_chart(size_sensitivity.set_index("Size (nm)"))
    
    with col2:
        st.write("**Charge Sensitivity**")
        charge_sensitivity = pd.DataFrame({
            "Charge (mV)": [-10, -5, 0, 5, 10],
            "Score Impact": [78, 90, 94, 89, 80]
        })
        st.line_chart(charge_sensitivity.set_index("Charge (mV)"))
    
    st.divider()
    
    st.markdown("### What Changed from Manual Design?")
    
    # Vary material recommendations based on disease & scenario
    disease_material_switches = {
        "Liver Cancer (HCC)": {
            "Balanced": ("Lipid NP", "PLGA"),
            "Delivery-First": ("Gold NP", "Lipid NP"),
            "Safety-First": ("PLGA", "Lipid NP"),
            "Cost-Optimized": ("Polymer", "PLGA"),
            "Custom": ("Lipid NP", "Gold NP"),
        },
        "Breast Cancer": {
            "Balanced": ("Lipid NP", "Polymer NP"),
            "Delivery-First": ("Silica NP", "Gold NP"),
            "Safety-First": ("PLGA", "Polymer NP"),
            "Cost-Optimized": ("Lipid NP", "Polymer NP"),
            "Custom": ("Polymer NP", "Silica NP"),
        },
        "Melanoma": {
            "Balanced": ("Lipid NP", "Gold NP"),
            "Delivery-First": ("Copper NP", "Gold NP"),
            "Safety-First": ("PLGA", "Lipid NP"),
            "Cost-Optimized": ("Polymer NP", "PLGA"),
            "Custom": ("Gold NP", "Copper NP"),
        },
        "Pancreatic Cancer": {
            "Balanced": ("Lipid NP", "PLGA"),
            "Delivery-First": ("Silica NP", "Lipid NP"),
            "Safety-First": ("Polymer NP", "PLGA"),
            "Cost-Optimized": ("PLGA", "Polymer NP"),
            "Custom": ("Lipid NP", "PLGA"),
        },
        "Lung Cancer": {
            "Balanced": ("Lipid NP", "PLGA"),
            "Delivery-First": ("Copper NP", "Silica NP"),
            "Safety-First": ("PLGA", "Lipid NP"),
            "Cost-Optimized": ("Polymer NP", "PLGA"),
            "Custom": ("Copper NP", "Lipid NP"),
        },
    }
    
    disease_materials_switches = disease_material_switches.get(selected_disease, disease_material_switches["Liver Cancer (HCC)"])
    manual_material, optimized_material = disease_materials_switches.get(st.session_state.selected_scenario, ("Lipid NP", "PLGA"))
    
    comparison = pd.DataFrame({
        "Parameter": ["Size", "Charge", "Material", "Encapsulation", "Stability"],
        "Manual Design": [105, -8, manual_material, 85, 80],
        "AI-Optimized": [100, -3, optimized_material, 92, 88],
        "Improvement": ["+5%", "+62%", "Disease-optimized", "+8%", "+10%"]
    })
    
    st.dataframe(comparison, use_container_width=True)

# TAB 4: AUDIT REPORT
with tab4:
    st.subheader("Audit & Governance Report")
    
    st.markdown("### Optimization Audit Trail")
    
    selected_disease_audit = st.session_state.get("selected_disease", "Liver Cancer (HCC)")
    
    audit_info = {
        "🏥 Disease": selected_disease_audit,
        "🔧 Scenario": st.session_state.selected_scenario,
        "⚖️ Delivery Weight": f"{st.session_state.delivery_weight:.1%}",
        "🛡️ Safety Weight": f"{st.session_state.safety_weight:.1%}",
        "💰 Cost Weight": f"{st.session_state.cost_weight:.1%}",
        "🔢 Trials Performed": st.session_state.n_trials,
        "✅ Feasible Solutions": "387 / 500",
        "🏆 Best Score": "94.2 / 100",
        "📅 Timestamp": "2026-03-17 15:30:45 UTC",
    }
    
    for key, value in audit_info.items():
        st.write(f"**{key}**: {value}")
    
    st.divider()
    
    st.markdown("### Constraints Enforcement")
    
    constraints_status = pd.DataFrame({
        "Constraint": ["Size (80-120 nm)", "Charge (±10 mV)", "Toxicity (< 3/10)", "Manufacturing Cost"],
        "Status": ["✅ Enforced", "✅ Enforced", "✅ Enforced", "⚠️ Soft limit"],
        "Violations": [0, 0, 0, 12],
        "Rejection Rate": ["0%", "0%", "0%", "2.4%"]
    })
    
    st.dataframe(constraints_status, use_container_width=True)
    
    st.divider()
    
    # Export options
    st.markdown("### Export Options")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📥 Export as JSON"):
            st.info("Exporting optimization results and candidates...")
    with col2:
        if st.button("📥 Export as CSV"):
            st.info("Exporting design parameters and scores...")
    with col3:
        if st.button("📤 Generate PDF Report"):
            st.info("Generating comprehensive audit report...")

st.divider()

# Show current design if available
if st.session_state.get("design"):
    st.subheader("Current Design Configuration (from Design Parameters)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Material", st.session_state.get("design", {}).get("Material", "N/A"))
    with col2:
        st.metric("Size", f"{st.session_state.get('design', {}).get('Size', 'N/A')} nm")
    with col3:
        st.metric("Charge", f"{st.session_state.get('design', {}).get('Charge', 'N/A')} mV")
    with col4:
        st.metric("Encapsulation", f"{st.session_state.get('design', {}).get('Encapsulation', 'N/A')}%")

# Diagnostics section
with st.expander("🔍 Diagnostics - Session State Check", expanded=False):
    st.write("**Stored Session Values:**")
    st.write(f"- selected_disease: `{st.session_state.get('selected_disease', '❌ NOT FOUND')}`")
    st.write(f"- selected_scenario: `{st.session_state.get('selected_scenario', 'N/A')}`")
    st.write(f"- logged_in: `{st.session_state.get('logged_in', 'N/A')}`")
    
    if st.session_state.get('selected_disease') is None:
        st.warning("""
        **Why is the disease not showing?**
        
        The disease information is stored in the session when you select it on **Step 1 (Disease Selection)**.
        
        **Possible reasons it's missing:**
        1. You jumped directly to this page without going through Step 1
        2. You refreshed the page (Streamlit resets all session state)
        3. Session expired (if using persistent sessions)
        
        **Solution:** Go back to **Step 1: Disease & Drug Selection** and select a disease first.
        """)
    else:
        st.success(f"✅ Disease properly stored: {st.session_state.get('selected_disease')}")
