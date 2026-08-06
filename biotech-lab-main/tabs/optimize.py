# ============================================================
# 🤖 AI Optimization Tab
# Multi-objective optimization with Pareto front visualization
# ============================================================

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from core.scoring import compute_impact
from persistence import save_optimization_run, get_optimization_history
from datetime import datetime

try:
    import optuna
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False


def objective_function(trial, design_template: dict, objective_weights: dict):
    """Define objective function for optimization"""
    
    # Parameters to optimize
    design = design_template.copy()
    design["Size"] = trial.suggest_float("Size", 50, 200)
    design["Charge"] = trial.suggest_float("Charge", -30, 30)
    design["Encapsulation"] = trial.suggest_float("Encapsulation", 40, 100)
    design["PDI"] = trial.suggest_float("PDI", 0.1, 0.3)
    design["Stability"] = trial.suggest_float("Stability", 50, 100)
    design["DegradationTime"] = trial.suggest_float("DegradationTime", 10, 120)
    
    # Compute impact scores
    impact = compute_impact(design)
    
    # Multi-objective optimization
    # Maximize delivery and stability, minimize toxicity and cost
    delivery = impact["Delivery"]
    toxicity = impact["Toxicity"]  # Lower is better
    cost = impact["Cost"]  # Lower is better
    
    # Weighted multi-objective function
    w_delivery = objective_weights.get("delivery", 0.5)
    w_safety = objective_weights.get("safety", 0.3)
    w_cost = objective_weights.get("cost", 0.2)
    
    # Normalize scores to 0-1 range
    delivery_norm = delivery / 100.0
    toxicity_norm = (10 - toxicity) / 10.0  # Invert so higher is better
    cost_norm = (100 - cost) / 100.0  # Invert so higher is better
    
    # Combined objective (higher is better)
    combined_score = (
        delivery_norm * w_delivery +
        toxicity_norm * w_safety +
        cost_norm * w_cost
    )
    
    # Store intermediate results
    trial.set_user_attr("delivery", delivery)
    trial.set_user_attr("toxicity", toxicity)
    trial.set_user_attr("cost", cost)
    trial.set_user_attr("design", design)
    
    return combined_score


def run_optimization(design_template: dict, objective_weights: dict, 
                    n_trials: int = 100, seed: int = 42) -> dict:
    """Run multi-objective optimization using Optuna"""
    
    if not OPTUNA_AVAILABLE:
        st.error("⚠️ Optuna not available. Install with: pip install optuna")
        return None
    
    # Create study
    sampler = TPESampler(seed=seed)
    study = optuna.create_study(
        direction="maximize",
        sampler=sampler
    )
    
    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Optimization callback
    def callback(study, trial):
        progress = (trial.number + 1) / n_trials
        progress_bar.progress(progress)
        status_text.text(f"Optimization progress: {trial.number + 1}/{n_trials}")
    
    # Run optimization
    study.optimize(
        lambda trial: objective_function(trial, design_template, objective_weights),
        n_trials=n_trials,
        callbacks=[callback],
        show_progress_bar=False
    )
    
    progress_bar.empty()
    status_text.empty()
    
    # Extract Pareto front
    trials_df = study.trials_dataframe()
    pareto_designs = []
    
    for trial in study.best_trials:
        pareto_designs.append({
            "delivery": trial.user_attrs.get("delivery", 0),
            "toxicity": trial.user_attrs.get("toxicity", 5),
            "cost": trial.user_attrs.get("cost", 100),
            "score": trial.value,
            "design": trial.user_attrs.get("design", {}),
            "trial_number": trial.number
        })
    
    # Get best overall trial
    best_trial = study.best_trial
    best_design = best_trial.user_attrs.get("design", design_template.copy())
    
    return {
        "study": study,
        "pareto_front": pareto_designs,
        "best_trial": best_trial,
        "best_design": best_design,
        "best_score": best_trial.value,
        "n_trials": n_trials,
        "objective_weights": objective_weights
    }


def plot_pareto_front(pareto_designs: list) -> go.Figure:
    """Plot 3D Pareto front visualization"""
    
    if not pareto_designs:
        return None
    
    df = pd.DataFrame(pareto_designs)
    
    fig = go.Figure(data=[go.Scatter3d(
        x=df["delivery"],
        y=df["toxicity"],
        z=df["cost"],
        mode='markers',
        marker=dict(
            size=8,
            color=df["score"],
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="Optimization<br>Score"),
            opacity=0.8,
            line=dict(color='white', width=1)
        ),
        text=[f"Trial {t}<br>Delivery: {d:.1f}%<br>Toxicity: {tx:.1f}/10<br>Cost: ${c:.1f}"
              for t, d, tx, c in zip(df["trial_number"], df["delivery"], df["toxicity"], df["cost"])],
        hoverinfo='text'
    )])
    
    fig.update_layout(
        title="🎯 Pareto Front - Multi-Objective Optimization",
        scene=dict(
            xaxis_title="Delivery Efficiency (%)",
            yaxis_title="Toxicity (0-10)",
            zaxis_title="Manufacturing Cost ($)"
        ),
        height=600,
        showlegend=False,
        hovermode='closest'
    )
    
    return fig


def plot_convergence(study) -> go.Figure:
    """Plot optimization convergence"""
    
    trials_df = study.trials_dataframe()
    trials_df['best_value'] = trials_df['value'].cummax()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=trials_df['number'],
        y=trials_df['value'],
        mode='markers',
        name='Trial Score',
        marker=dict(size=4, color='lightblue', opacity=0.5)
    ))
    
    fig.add_trace(go.Scatter(
        x=trials_df['number'],
        y=trials_df['best_value'],
        mode='lines',
        name='Best Score',
        line=dict(color='red', width=3)
    ))
    
    fig.update_layout(
        title="📈 Optimization Convergence",
        xaxis_title="Trial Number",
        yaxis_title="Objective Score",
        height=400,
        hovermode='x unified'
    )
    
    return fig


def plot_parameter_importance(study) -> go.Figure:
    """Plot parameter importance in optimization"""
    
    trials_df = study.trials_dataframe()
    
    # Extract parameter columns
    param_cols = [col for col in trials_df.columns if col.startswith('params_')]
    
    if not param_cols:
        return None
    
    # Calculate correlation with objective
    correlations = {}
    for param in param_cols:
        param_name = param.replace('params_', '')
        if trials_df[param].notna().sum() > 0:
            corr = trials_df[param].corr(trials_df['value'])
            correlations[param_name] = abs(corr)
    
    if not correlations:
        return None
    
    df_corr = pd.DataFrame(list(correlations.items()), columns=['Parameter', 'Importance'])
    df_corr = df_corr.sort_values('Importance', ascending=True)
    
    fig = px.barh(df_corr, x='Importance', y='Parameter',
                  title='🔍 Parameter Importance',
                  labels={'Importance': 'Correlation with Objective Score'})
    fig.update_layout(height=400)
    
    return fig


def render(plotly_ok: bool = False):
    """Render the optimization tab"""
    
    st.header("🤖 AI Optimization")
    
    if not OPTUNA_AVAILABLE:
        st.error("⚠️ Optuna library not installed. Install with: `pip install optuna`")
        return
    
    # Initialize session state for optimization
    if "optimization_results" not in st.session_state:
        st.session_state.optimization_results = None
    
    # Configuration section
    st.subheader("⚙️ Optimization Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Objective Weights**")
        delivery_weight = st.slider("Delivery Efficiency", 0.0, 1.0, 0.5, 0.1, key="opt_delivery")
    
    with col2:
        safety_weight = st.slider("Safety (Low Toxicity)", 0.0, 1.0, 0.3, 0.1, key="opt_safety")
    
    with col3:
        cost_weight = st.slider("Cost Efficiency", 0.0, 1.0, 0.2, 0.1, key="opt_cost")
    
    # Normalize weights
    total_weight = delivery_weight + safety_weight + cost_weight
    if total_weight == 0:
        st.error("At least one weight must be > 0")
        return
    
    objective_weights = {
        "delivery": delivery_weight / total_weight,
        "safety": safety_weight / total_weight,
        "cost": cost_weight / total_weight
    }
    
    st.write(f"**Normalized weights:** Delivery {objective_weights['delivery']:.1%} | "
             f"Safety {objective_weights['safety']:.1%} | Cost {objective_weights['cost']:.1%}")
    
    # Optimization parameters
    st.subheader("🎛️ Optimization Parameters")
    
    col1, col2 = st.columns(2)
    with col1:
        n_trials = st.slider("Number of Trials", 10, 500, 100, 10)
        seed = st.number_input("Random Seed (for reproducibility)", value=42, min_value=0)
    
    with col2:
        st.info("💡 More trials = better results but slower optimization")
    
    # Run optimization button
    if st.button("▶️ Start Optimization", width='stretch', type="primary"):
        with st.spinner("🔄 Running optimization..."):
            results = run_optimization(
                design_template=st.session_state.design,
                objective_weights=objective_weights,
                n_trials=n_trials,
                seed=seed
            )
            
            if results:
                st.session_state.optimization_results = results
                st.success("✅ Optimization completed!")
                st.rerun()
    
    # Display results if available
    if st.session_state.optimization_results:
        results = st.session_state.optimization_results
        
        st.subheader("📊 Optimization Results")
        
        # Best design metrics
        best_design = results["best_design"]
        impact = compute_impact(best_design)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🎯 Best Score", f"{results['best_score']:.3f}")
        col2.metric("📤 Delivery", f"{impact['Delivery']:.1f}%")
        col3.metric("☣️ Toxicity", f"{impact['Toxicity']:.2f}/10")
        col4.metric("💰 Cost", f"${impact['Cost']:.1f}")
        
        # Display Pareto front
        if results["pareto_front"]:
            st.markdown("### 🎨 Pareto Front Visualization")
            fig_pareto = plot_pareto_front(results["pareto_front"])
            if fig_pareto:
                st.plotly_chart(fig_pareto, width='stretch')
        
        # Display convergence
        st.markdown("### 📈 Optimization Convergence")
        fig_convergence = plot_convergence(results["study"])
        st.plotly_chart(fig_convergence, width='stretch')
        
        # Display parameter importance
        st.markdown("### 🔍 Parameter Importance")
        fig_importance = plot_parameter_importance(results["study"])
        if fig_importance:
            st.plotly_chart(fig_importance, width='stretch')
        
        # Display best design parameters
        st.subheader("🧬 Optimized Design Parameters")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Size (nm)", f"{best_design.get('Size', 0):.1f}")
            st.metric("PDI", f"{best_design.get('PDI', 0):.3f}")
        
        with col2:
            st.metric("Charge (mV)", f"{best_design.get('Charge', 0):.1f}")
            st.metric("Stability (%)", f"{best_design.get('Stability', 0):.1f}")
        
        with col3:
            st.metric("Encapsulation (%)", f"{best_design.get('Encapsulation', 0):.1f}")
            st.metric("Degradation Time (days)", f"{best_design.get('DegradationTime', 0):.1f}")
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("✅ Accept Best Design", width='stretch'):
                st.session_state.design = best_design
                st.success("Design loaded into main design panel")
                st.rerun()
        
        with col2:
            if st.button("💾 Save Optimization", width='stretch'):
                design_name = st.text_input("Design Name", "Optimized Design - " + datetime.now().strftime("%Y-%m-%d %H:%M"))
                if st.button("Save", width='stretch'):
                    save_optimization_run(
                        design_id=1,  # Would need to be set properly from context
                        objective_weights=objective_weights,
                        pareto_front=results["pareto_front"],
                        best_design=best_design,
                        algorithm="optuna",
                        evaluations=results["n_trials"]
                    )
        
        with col3:
            if st.button("🔄 New Optimization", width='stretch'):
                st.session_state.optimization_results = None
                st.rerun()
    
    # History section
    st.subheader("📜 Optimization History")
    st.info("💡 Track past optimizations to compare different objective weightings and parameter ranges")
    
    if st.button("📂 Load Previous Optimization"):
        st.write("Optimization history would be loaded from database")
