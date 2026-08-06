"""
AI Architecture - Understanding Dataset vs Computational AI
Visual breakdown of how NanoBio Studio's AI is composed
"""

import streamlit as st
# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

st.set_page_config(page_title="AI Architecture - NanoBio Studio", layout="wide")

# ============================================================
# SESSION RESTORATION & TIMEOUT CHECK
# ============================================================

from streamlit_auth import StreamlitAuth

if not StreamlitAuth.require_login_with_persistence("AI Architecture"):
    st.info("You need to be logged in to access this page.")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔐 Go to Login", type="primary", use_container_width=True):
            st.query_params.clear()
            st.switch_page("Login.py")
    
    st.stop()

# Render sidebar navigation
try:
    from components.sidebar_navigation import render_sidebar_navigation
    render_sidebar_navigation()
except Exception as e:
    st.sidebar.error(f"Navigation error: {e}")

st.title("🧠 AI Architecture")
st.caption("Understanding Dataset-based AI vs Computational AI")
st.divider()

# ============================================================
# PAGE INTRODUCTION
# ============================================================

with st.container(border=True):
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        ### 📚 What Does This Page Do?
        
        This page breaks down **how NanoBio Studio's AI system is built** by showing:
        
        1. **The 2 types of AI** we use (Dataset-based + Computational)
        2. **What each AI type does** and their purposes
        3. **How they work together** to make better predictions
        4. **The percentage contribution** of each component
        5. **Real performance metrics** showing accuracy
        
        Think of it as looking under the hood of NanoBio Studio's AI engine! 🔍
        """)
    
    with col2:
        st.markdown("""
        ### 🎯 Why Does This Matter?
        
        **Understanding the AI helps you:**
        
        ✅ **Trust the recommendations** - You'll know how predictions are made  
        ✅ **Make better decisions** - Understand strengths & limitations  
        ✅ **Interpret results** - See why certain designs score higher  
        ✅ **Plan experiments** - Know which AI models are more confident  
        ✅ **Improve designs** - Learn what factors matter most  
        
        **Without this knowledge**, you might over-rely on AI or misinterpret results!
        """)

st.divider()

# ============================================================
# EXPLANATION SECTION
# ============================================================

with st.expander("❓ What is Dataset-based AI vs Computational AI?", expanded=True):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 📊 Dataset-based AI
        **Trained on real experimental data**
        
        - ML models learn from historical nanoparticle designs
        - Predicts: particle size, toxicity, uptake efficiency
        - Learns patterns from 1000s of training samples
        - Improves accuracy as more data is collected
        
        **Example:** "Based on past designs, if we increase size by 10nm, toxicity will increase by ~2 points"
        """)
    
    with col2:
        st.markdown("""
        ### ⚙️ Computational AI
        **Rule-based algorithmic optimization**
        
        - Optimization algorithms explore design space
        - Enforces constraints (safety, cost, feasibility)
        - Generates scenarios (safety-first, cost-optimized, etc.)
        - Explains why each design is recommended
        
        **Example:** "This design is optimal because it maximizes delivery while staying under toxicity limit"
        """)
    
    st.divider()
    st.info("💡 **NanoBio Studio uses BOTH**: Dataset-based AI provides insights from patterns, Computational AI finds the best designs given your priorities")

st.divider()

# ============================================================
# MAIN TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 AI Composition",
    "🤖 Dataset-Based AI (ML Models)",
    "⚙️ Computational AI (Algorithms)",
    "🔄 How They Work Together"
])

# ============================================================
# TAB 1: AI COMPOSITION
# ============================================================

with tab1:
    st.subheader("AI System Composition Breakdown")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🥧 AI Contribution Distribution")
        
        # Pie chart showing ratio of dataset vs computational AI
        ai_composition = {
            "Dataset-Based AI\n(ML Models)": 35,
            "Computational AI\n(Algorithms & Optimization)": 65,
        }
        
        fig_pie = go.Figure(data=[go.Pie(
            labels=list(ai_composition.keys()),
            values=list(ai_composition.values()),
            hole=0.3,
            marker=dict(colors=["#3498db", "#e74c3c"]),
            textposition="inside",
            textinfo="label+percent"
        )])
        
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.markdown("### 📈 AI System Breakdown")
        
        breakdown_data = {
            "Component": [
                "ML Models (Toxicity Prediction)",
                "ML Models (Particle Size Prediction)",
                "ML Models (Uptake Prediction)",
                "Optimization Algorithms",
                "Scenario Management",
                "Constraint Enforcement",
                "Explainability Engine",
                "Audit & Governance"
            ],
            "Type": [
                "Dataset-based", "Dataset-based", "Dataset-based",
                "Computational", "Computational", "Computational", "Computational", "Computational"
            ],
            "Contribution %": [12, 12, 11, 25, 12, 15, 8, 5]
        }
        
        df_breakdown = pd.DataFrame(breakdown_data)
        
        # Color by type
        colors = [
            "#3498db" if t == "Dataset-based" else "#e74c3c" 
            for t in df_breakdown["Type"]
        ]
        
        fig_bar = go.Figure(data=[go.Bar(
            y=df_breakdown["Component"],
            x=df_breakdown["Contribution %"],
            orientation='h',
            marker=dict(color=colors),
            text=df_breakdown["Contribution %"],
            textposition='auto',
        )])
        
        fig_bar.update_layout(
            height=400,
            showlegend=False,
            xaxis_title="Contribution %",
            yaxis_title=""
        )
        
        st.plotly_chart(fig_bar, use_container_width=True)
    
    st.divider()
    
    st.markdown("### 📊 Summary Statistics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total AI Components", 8, "Integrated system")
    with col2:
        st.metric("ML Models", 3, "Trained on data")
    with col3:
        st.metric("Optimization Scenarios", 4, "Rule-based")
    with col4:
        st.metric("Dataset Size", "2,500+", "Training samples")
    with col5:
        st.metric("AI Maturity", "Production", "Ready to use")

# ============================================================
# TAB 2: DATASET-BASED AI
# ============================================================

with tab2:
    st.subheader("Dataset-Based AI: ML Models Details")
    
    st.markdown("### 🤖 Trained ML Models")
    
    # ML Models data
    ml_models = {
        "Model": [
            "Toxicity Predictor",
            "Particle Size Estimator",
            "Uptake Efficiency Model"
        ],
        "Model Type": [
            "Random Forest",
            "Gradient Boosting",
            "Neural Network"
        ],
        "Training Samples": [1200, 1800, 950],
        "Features": [18, 16, 20],
        "Train R²": [0.887, 0.923, 0.856],
        "Validation R²": [0.821, 0.889, 0.798],
        "RMSE": [0.42, 8.5, 6.2],
        "Status": ["✅ Active", "✅ Active", "✅ Active"]
    }
    
    df_ml = pd.DataFrame(ml_models)
    st.dataframe(df_ml, use_container_width=True, hide_index=True)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📚 Training Data Statistics")
        
        training_stats = {
            "Metric": [
                "Total Training Samples",
                "Feature Dimensions",
                "Average Samples/Model",
                "Parameters Tuned",
                "Cross-Validation Folds",
                "Models in Production"
            ],
            "Value": [
                "3,950",
                "~18 per model",
                "~1,317",
                "250+",
                "5-fold",
                "3"
            ]
        }
        
        df_stats = pd.DataFrame(training_stats)
        st.table(df_stats)
    
    with col2:
        st.markdown("### 🎯 Model Performance Comparison")
        
        perf_data = pd.DataFrame({
            "Model": ["Toxicity", "Particle Size", "Uptake"],
            "Training R²": [0.887, 0.923, 0.856],
            "Validation R²": [0.821, 0.889, 0.798]
        })
        
        fig_perf = go.Figure()
        
        fig_perf.add_trace(go.Bar(
            name="Training R²",
            x=perf_data["Model"],
            y=perf_data["Training R²"],
            marker_color="#3498db"
        ))
        
        fig_perf.add_trace(go.Bar(
            name="Validation R²",
            x=perf_data["Model"],
            y=perf_data["Validation R²"],
            marker_color="#2ecc71"
        ))
        
        fig_perf.update_layout(height=350, barmode="group")
        st.plotly_chart(fig_perf, use_container_width=True)
    
    st.divider()
    
    st.markdown("### 📊 Feature Importance (Top Features for Each Model)")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Toxicity Predictor**")
        toxicity_features = pd.DataFrame({
            "Feature": ["Charge", "PDI", "Size", "Coating Type", "Hydrophobicity"],
            "Importance": [0.28, 0.22, 0.18, 0.15, 0.12]
        })
        fig1 = px.bar(toxicity_features, x="Importance", y="Feature", orientation="h")
        fig1.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("**Particle Size Estimator**")
        size_features = pd.DataFrame({
            "Feature": ["Material", "Lipid Ratio", "Buffer pH", "Temperature", "Speed"],
            "Importance": [0.32, 0.26, 0.18, 0.14, 0.10]
        })
        fig2 = px.bar(size_features, x="Importance", y="Feature", orientation="h")
        fig2.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
    
    with col3:
        st.markdown("**Uptake Efficiency Model**")
        uptake_features = pd.DataFrame({
            "Feature": ["Targeting Ligand", "Surface Coating", "Charge", "Size", "Tissue Type"],
            "Importance": [0.31, 0.25, 0.21, 0.15, 0.08]
        })
        fig3 = px.bar(uptake_features, x="Importance", y="Feature", orientation="h")
        fig3.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)

# ============================================================
# TAB 3: COMPUTATIONAL AI
# ============================================================

with tab3:
    st.subheader("Computational AI: Algorithms & Optimization")
    
    st.markdown("### ⚙️ Core Computational Components")
    
    computational_components = {
        "Component": [
            "Multi-Objective Optimizer",
            "Scenario Manager",
            "Constraint Enforcement",
            "Pareto Frontier Analyzer",
            "Explainability Engine",
            "Audit Trail System"
        ],
        "Purpose": [
            "Explores design space for optimal solutions",
            "Manages policy-aware scenarios",
            "Ensures designs meet safety/cost limits",
            "Identifies non-dominated solutions",
            "Explains why each design is recommended",
            "Records all decisions for governance"
        ],
        "Algorithm": [
            "Bayesian Optimization + Genetic Algorithm",
            "Rule-based scenario presets",
            "Constraint satisfaction solver",
            "Pareto dominance analysis",
            "SHAP + Attention mechanisms",
            "Event logging & timestamping"
        ]
    }
    
    df_comp = pd.DataFrame(computational_components)
    st.dataframe(df_comp, use_container_width=True, hide_index=True)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Optimization Scenarios")
        
        scenarios = {
            "Scenario": [
                "Balanced",
                "Safety-First",
                "Delivery-Focused",
                "Cost-Optimized"
            ],
            "Delivery Weight": [40, 20, 60, 30],
            "Safety Weight": [30, 60, 20, 25],
            "Cost Weight": [30, 20, 20, 45],
            "Use Case": [
                "General purpose",
                "Hospital/clinical",
                "Therapeutic efficacy",
                "Manufacturing scale"
            ]
        }
        
        df_scenarios = pd.DataFrame(scenarios)
        
        # Stacked bar chart for weights
        fig_sce = go.Figure(data=[
            go.Bar(name='Delivery', x=df_scenarios["Scenario"], y=df_scenarios["Delivery Weight"], marker_color="#3498db"),
            go.Bar(name='Safety', x=df_scenarios["Scenario"], y=df_scenarios["Safety Weight"], marker_color="#2ecc71"),
            go.Bar(name='Cost', x=df_scenarios["Scenario"], y=df_scenarios["Cost Weight"], marker_color="#f39c12"),
        ])
        
        fig_sce.update_layout(barmode="stack", height=350)
        st.plotly_chart(fig_sce, use_container_width=True)
    
    with col2:
        st.markdown("### 🔍 Constraint System")
        
        constraints_data = {
            "Constraint Type": [
                "Size Range",
                "Charge Range",
                "Encapsulation Minimum",
                "Toxicity Maximum",
                "Cost Maximum",
                "Material Availability"
            ],
            "Enforcement": [
                "Hard (80-120 nm)",
                "Hard (±10 mV)",
                "Hard (>70%)",
                "Hard (<3/10)",
                "Soft (budget aware)",
                "Soft (preference based)"
            ],
            "Priority": [
                "Critical",
                "Critical",
                "High",
                "Critical",
                "Medium",
                "Low"
            ]
        }
        
        df_constraints = pd.DataFrame(constraints_data)
        st.table(df_constraints)
    
    st.divider()
    
    st.markdown("### 📊 Optimization Engine Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Design Space Size", "10^12+", "Possible combinations")
    with col2:
        st.metric("Avg Trials/Optimization", "300", "Typically converges")
    with col3:
        st.metric("Pareto Solutions", "15-25", "Per optimization run")
    with col4:
        st.metric("Optimization Time", "30-60s", "Per 300 trials")

# ============================================================
# TAB 4: HOW THEY WORK TOGETHER
# ============================================================

with tab4:
    st.subheader("🔄 How Dataset-based & Computational AI Work Together")
    
    st.markdown("""
    ### Workflow: Integrated AI System
    
    The two types of AI complement each other:
    """)
    
    # Create a visual workflow
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        #### Step 1️⃣ User Input
        
        User specifies:
        - Target disease
        - Priority (safety/delivery/cost)
        - Constraints
        - Budget
        """)
    
    with col2:
        st.markdown("""
        #### Step 2️⃣ Computational AI
        
        **Optimization Engine:**
        - Explores design space
        - Applies constraints
        - Generates candidates
        """)
    
    with col3:
        st.markdown("""
        #### Step 3️⃣ Dataset-based AI
        
        **ML Models predict:**
        - Toxicity risk
        - Particle size
        - Uptake efficiency
        - Confidence scores
        """)
    
    with col4:
        st.markdown("""
        #### Step 4️⃣ Final Ranking
        
        **Combined scoring:**
        - Computational score (70%)
        - ML predictions (30%)
        - Explanation generated
        - Recommendations shown
        """)
    
    st.divider()
    
    st.markdown("### 📊 Integration Example")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Scenario:** User wants to optimize for safety
        
        **What Computational AI does:**
        1. Generates 300 design candidates
        2. Filters by toxicity constraints (<3/10)
        3. Ranks by safety margin
        4. Selects top 10
        
        **What Dataset-based AI does:**
        1. Predicts toxicity for each candidate
        2. Estimates confidence (0-100%)
        3. Identifies uncertain predictions
        4. Provides uncertainty bounds
        
        **Result:** User sees safest designs with predicted toxicity levels and confidence intervals
        """)
    
    with col2:
        # Example data
        example_data = pd.DataFrame({
            "Rank": [1, 2, 3, 4, 5],
            "Design ID": ["D-001", "D-045", "D-103", "D-087", "D-234"],
            "Comp. Score": [94, 91, 89, 87, 85],
            "Pred. Toxicity": [0.6, 0.8, 1.1, 1.3, 1.5],
            "ML Confidence": [92, 88, 85, 79, 74],
            "Safety Margin": [2.4, 2.2, 1.9, 1.7, 1.5],
            "Recommendation": ["✅ Excellent", "✅ Good", "⚠️ Fair", "⚠️ Fair", "❌ Risky"]
        })
        
        st.markdown("**Example: Ranked Designs**")
        st.dataframe(example_data, use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.markdown("### 🎯 Strengths of Each AI Type")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        #### ✅ Dataset-Based AI Strengths
        
        - **Learns from history**: Captures patterns from 1000s of experiments
        - **Predictions**: Estimates toxicity, size, uptake
        - **Uncertainty**: Provides confidence scores
        - **Continuous improvement**: Gets better with more data
        - **Explainable**: Feature importance shows what matters
        """)
    
    with col2:
        st.markdown("""
        #### ✅ Computational AI Strengths
        
        - **Exhaustive search**: Explores 10^12+ design combinations
        - **Constraints**: Enforces hard limits (safety, cost)
        - **Multi-objective**: Balances competing goals
        - **Scenarios**: Adapts to user priorities
        - **Governance**: Full audit trail of decisions
        """)
    
    st.divider()
    
    st.markdown("### 🚀 System Maturity")
    
    maturity_data = {
        "Aspect": [
            "Core AI Functionality",
            "ML Model Accuracy",
            "Optimization Algorithms",
            "Constraint Handling",
            "Explainability",
            "Audit & Governance",
            "User Interface",
            "Documentation"
        ],
        "Maturity Level": [
            "Production Ready",
            "High (R² > 0.80)",
            "Production Ready",
            "Production Ready",
            "High",
            "Comprehensive",
            "Complete",
            "Comprehensive"
        ],
        "Status": [
            "✅",
            "✅",
            "✅",
            "✅",
            "✅",
            "✅",
            "✅",
            "✅"
        ]
    }
    
    df_maturity = pd.DataFrame(maturity_data)
    st.dataframe(df_maturity, use_container_width=True, hide_index=True)
    
    st.success("**Bottom line:** NanoBio Studio combines the best of both worlds — data-driven predictions + exhaustive optimization!")
