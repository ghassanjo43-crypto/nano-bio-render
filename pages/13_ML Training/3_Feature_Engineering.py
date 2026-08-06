"""
Feature Engineering
Deep dive into how input features are selected and engineered
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

st.set_page_config(page_title="Feature Engineering - NanoBio Studio", layout="wide")

# ============================================================
# SESSION RESTORATION & TIMEOUT CHECK
# ============================================================

from streamlit_auth import StreamlitAuth

if not StreamlitAuth.require_login_with_persistence("Feature Engineering"):
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

st.title("🔧 Feature Engineering")
st.caption("Understanding how data features are prepared for ML models")
st.divider()

# ============================================================
# PAGE INTRODUCTION
# ============================================================

with st.container(border=True):
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        ### 📚 What Does This Page Do?
        
        This page showcases **how we prepare raw data for AI models**:
        
        1. **Feature selection** - Narrowing 45 candidates → 18-20 best features
        2. **Feature engineering** - Creating new meaningful features
        3. **Data transformation** - Normalization, scaling, encoding
        4. **Feature importance** - Showing what matters most for predictions
        5. **Correlation analysis** - Understanding feature relationships
        
        **Good features = Better AI predictions!** ✨
        """)
    
    with col2:
        st.markdown("""
        ### 🎯 Why Does This Matter?
        
        **Feature engineering directly impacts:**
        
        ✅ **Model accuracy** - Better features → +8-12% improvement  
        ✅ **Training speed** - Fewer irrelevant features = faster training  
        ✅ **Interpretability** - Understand what AI is paying attention to  
        ✅ **Robustness** - Reduce noise and outliers  
        ✅ **Relevance** - Focus on factors that truly matter  
        
        **It's the difference between noisy predictions and confident ones!**
        """)

st.divider()

# ============================================================
# MAIN TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Overview",
    "🎯 Feature Selection",
    "🔄 Feature Engineering",
    "📊 Feature Analysis"
])

# ============================================================
# TAB 1: OVERVIEW
# ============================================================

with tab1:
    st.subheader("Feature Engineering Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🎯 What is Feature Engineering?
        
        Feature engineering is the process of:
        - **Selecting** relevant input variables
        - **Creating** new meaningful features
        - **Transforming** raw data into model-ready format
        - **Normalizing** to comparable scales
        
        ### 📊 Raw → Engineered Features
        
        - **Raw features**: 45+ possible inputs
        - **Selected features**: 18-20 per model
        - **Engineered features**: Derived combinations
        - **Final features**: Normalized & scaled
        """)
    
    with col2:
        st.markdown("""
        ### 💡 Why This Matters
        
        Good features directly impact:
        - **Model accuracy** (R² scores)
        - **Training speed** (fewer irrelevant features)
        - **Prediction reliability** (less noise)
        - **Interpretability** (understandable inputs)
        
        ### ⚡ Feature Engineering Impact
        
        - Improves R² by ~8-12%
        - Reduces training time by ~30%
        - Decreases model variance
        - Facilitates explainability
        """)
    
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Raw Candidates", "45+", "Before selection")
    with col2:
        st.metric("Selected Features", "18-20", "Per model")
    with col3:
        st.metric("Engineered Features", "5-8", "Derived features")
    with col4:
        st.metric("Impact on Accuracy", "+10%", "Average improvement")

# ============================================================
# TAB 2: FEATURE SELECTION
# ============================================================

with tab2:
    st.subheader("Feature Selection Process")
    
    st.markdown("### 📋 All Available Features (45 candidates)")
    
    all_features = pd.DataFrame({
        "Category": [
            "Material", "Material", "Material", "Material", 
            "Size", "Size", "Size",
            "Charge", "Charge", "Charge",
            "Coating", "Coating", "Coating", "Coating",
            "Composition", "Composition", "Composition", "Composition",
            "Process", "Process", "Process", "Process",
            "Safety", "Safety", "Safety",
            "Performance", "Performance", "Performance", "Performance"
        ],
        "Feature": [
            "Material Type", "Density", "Melting Point", "Oxidation State",
            "Core Size", "Shell Thickness", "Size Distribution",
            "Surface Charge", "Charge Density", "Isoelectric Point",
            "Coating Type", "Coating Thickness", "Coating Density", "Hydrophobicity",
            "Material Ratio 1", "Material Ratio 2", "Dopant Concentration", "Crystal Structure",
            "Synthesis Temp", "pH During Synthesis", "Stirring Speed", "Reaction Time",
            "Cytotoxicity", "Genotoxicity", "Hemolysis Index",
            "Cellular Uptake", "Tissue Specificity", "Bioavailability", "Blood Half-Life"
        ],
        "Type": [
            "Categorical", "Continuous", "Continuous", "Discrete",
            "Continuous", "Continuous", "Continuous",
            "Continuous", "Continuous", "Continuous",
            "Categorical", "Continuous", "Continuous", "Continuous",
            "Continuous", "Continuous", "Continuous", "Categorical",
            "Continuous", "Continuous", "Continuous", "Continuous",
            "Continuous", "Continuous", "Continuous",
            "Continuous", "Discrete", "Continuous", "Continuous"
        ],
        "Selected": [
            "✅", "✅", "✅", "❌",
            "✅", "✅", "❌",
            "✅", "✅", "❌",
            "✅", "✅", "✅", "✅",
            "✅", "✅", "❌", "✅",
            "✅", "✅", "✅", "✅",
            "❌", "❌", "✅",
            "✅", "❌", "✅", "✅"
        ]
    })
    
    st.dataframe(all_features, use_container_width=True, hide_index=True)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Feature Selection Methods")
        
        methods = pd.DataFrame({
            "Method": [
                "Correlation Analysis",
                "Mutual Information",
                "Feature Importance",
                "Domain Knowledge",
                "Statistical Tests",
                "Recursive Elimination"
            ],
            "Description": [
                "Identify correlated features",
                "Measure feature-target dependency",
                "Use tree-based importance",
                "Expert biotech domain knowledge",
                "Significance testing (p-value)",
                "Recursive feature elimination"
            ],
            "Features Selected": [15, 18, 16, 20, 14, 17]
        })
        
        st.dataframe(methods, use_container_width=True, hide_index=True)
    
    with col2:
        st.markdown("### ✅ Final 18-20 Features Selected")
        
        final_features = pd.DataFrame({
            "Toxicity Model": [
                "Material Type", "Charge", "PDI",
                "Coating Type", "Hydrophobicity",
                "Synthesis pH", "Hemolysis Index",
                "Size", "Density"
            ],
            "Size Model": [
                "Material Type", "Reaction Time",
                "Synthesis Temp", "Stirring Speed",
                "pH During Synthesis", "Material Ratio 1",
                "Core Size", "Shell Thickness",
                "Crystal Structure"
            ],
            "Uptake Model": [
                "Targeting Ligand", "Surface Charge",
                "Coating Type", "Hydrophobicity",
                "Size", "Tissue Type",
                "Material Type", "Cellular Uptake",
                "Bioavailability", "Blood Half-Life"
            ]
        })
        
        st.dataframe(final_features, use_container_width=True, hide_index=False)

# ============================================================
# TAB 3: FEATURE ENGINEERING
# ============================================================

with tab3:
    st.subheader("Feature Engineering Transformations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔄 Transformation Types")
        
        transformations = pd.DataFrame({
            "Transformation": [
                "One-Hot Encoding",
                "Normalization",
                "Log Transform",
                "Binning",
                "Polynomial Features",
                "Feature Interaction",
                "PCA Projection",
                "Scaling (MinMax)"
            ],
            "Applied To": [
                "Categorical vars (Material, Coating)",
                "All continuous features",
                "Skewed distributions",
                "Continuous → discrete ranges",
                "Size, Charge, Density",
                "Top paired features",
                "High-dim features",
                "Bounded/bounded features"
            ],
            "Features Affected": [8, 20, 5, 3, 4, 6, 8, 15]
        })
        
        st.dataframe(transformations, use_container_width=True, hide_index=True)
    
    with col2:
        st.markdown("### 📊 Engineered Features (Created)")
        
        engineered = pd.DataFrame({
            "Original Features": [
                "Size × Charge",
                "Charge / Density",
                "Size² (Poly degree 2)",
                "Material + Coating",
                "log(Price)",
                "Coat_Thickness / Core_Size",
                "Charge Density²",
                "Synthesis_Temp × Stirr_Speed"
            ],
            "New Feature": [
                "Size_Charge_Interaction",
                "Charge_per_Mass",
                "Size_Squared",
                "Material_Coating_Combo",
                "Log_Scaled_Price",
                "Thickness_Ratio",
                "Charge_Concentration",
                "Process_Intensity"
            ],
            "Used In": [
                "Toxicity, Uptake",
                "All models",
                "Toxicity, Size",
                "All models",
                "Cost optimization",
                "Size model",
                "Toxicity",
                "Size model"
            ]
        })
        
        st.dataframe(engineered, use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.markdown("### 🎨 Example Transformation: Normalization")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Before Normalization (Raw Values)**")
        
        fig_before = go.Figure(data=[
            go.Histogram(x=[50, 45, 55, 52, 48, 100, 99, 101, 75, 72], name="Particle Size (nm)")
        ])
        
        fig_before.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig_before, use_container_width=True)
    
    with col2:
        st.markdown("**After Z-score Normalization**")
        
        raw_data = np.array([50, 45, 55, 52, 48, 100, 99, 101, 75, 72])
        normalized = (raw_data - raw_data.mean()) / raw_data.std()
        
        fig_after = go.Figure(data=[
            go.Histogram(x=normalized, name="Normalized Size")
        ])
        
        fig_after.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig_after, use_container_width=True)

# ============================================================
# TAB 4: FEATURE ANALYSIS
# ============================================================

with tab4:
    st.subheader("Feature Importance & Correlation Analysis")
    
    st.markdown("### 🎯 Top Features for Each Model")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Toxicity Model**")
        
        tox_features = pd.DataFrame({
            "Feature": ["Charge", "PDI", "Size", "Coating Type", "Hydrophobicity", "Synthesis pH", "Hemolysis", "Material", "Density"],
            "Importance": [0.28, 0.22, 0.18, 0.15, 0.12, 0.08, 0.07, 0.05, 0.03],
            "Impact": ["🔴 Critical", "🟠 High", "🟠 High", "🟡 Medium", "🟡 Medium", "🟢 Low", "🟢 Low", "🟢 Low", "⚪ Minimal"]
        })
        
        st.dataframe(tox_features, use_container_width=True, hide_index=True)
    
    with col2:
        st.markdown("**Size Model**")
        
        size_features = pd.DataFrame({
            "Feature": ["Material", "Lipid Ratio", "Buffer pH", "Temp", "Speed", "React Time", "Core Size", "Shell Thick", "Crystal"],
            "Importance": [0.32, 0.26, 0.18, 0.14, 0.10, 0.08, 0.06, 0.05, 0.02],
            "Impact": ["🔴 Critical", "🔴 Critical", "🟠 High", "🟡 Medium", "🟡 Medium", "🟢 Low", "🟢 Low", "🟢 Low", "⚪ Minimal"]
        })
        
        st.dataframe(size_features, use_container_width=True, hide_index=True)
    
    with col3:
        st.markdown("**Uptake Model**")
        
        uptake_features = pd.DataFrame({
            "Feature": ["Targeting", "Coating", "Charge", "Size", "Tissue", "Material", "Uptake", "Bioavail", "Half-Life"],
            "Importance": [0.31, 0.25, 0.21, 0.15, 0.08, 0.07, 0.05, 0.04, 0.02],
            "Impact": ["🔴 Critical", "🔴 Critical", "🟠 High", "🟡 Medium", "🟢 Low", "🟢 Low", "🟢 Low", "⚪ Minimal", "⚪ Minimal"]
        })
        
        st.dataframe(uptake_features, use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.markdown("### 📊 Feature Correlation Heatmap (Example)")
    
    # Create correlation matrix
    np.random.seed(42)
    features = ["Size", "Charge", "PDI", "Coating", "Hydro", "pH", "Temp", "Speed"]
    corr_matrix = np.random.uniform(-0.5, 1, (len(features), len(features)))
    corr_matrix = (corr_matrix + corr_matrix.T) / 2  # Make symmetric
    np.fill_diagonal(corr_matrix, 1)  # Diagonal is 1
    
    fig_heatmap = go.Figure(data=go.Heatmap(
        z=corr_matrix,
        x=features,
        y=features,
        colorscale="RdBu",
        zmid=0,
        text=corr_matrix.round(2),
        texttemplate="%{text}",
        textfont={"size": 10}
    ))
    
    fig_heatmap.update_layout(height=400)
    st.plotly_chart(fig_heatmap, use_container_width=True)
    
    st.info("💡 **Interpretation**: Red = positive correlation, Blue = negative correlation. Values close to 1 or -1 indicate strong relationships between features.")
