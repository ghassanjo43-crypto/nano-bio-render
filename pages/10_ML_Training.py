"""
ML Training Page
Interactive page for building datasets and training ML models.
"""

import streamlit as st
# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
import pandas as pd
import logging
import os

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="ML Training - NanoBio Studio",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 ML Training")

# ============================================================
# SESSION RESTORATION & TIMEOUT CHECK
# ============================================================

from streamlit_auth import StreamlitAuth

if not StreamlitAuth.require_login_with_persistence("ML Training"):
    st.stop()

st.subheader("Build, Train, and Manage ML Models")

# ============================================================
# TABS FOR ML TRAINING WORKFLOW
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dataset Builder",
    "🧠 Model Training",
    "📈 Training History",
    "🎯 Model Evaluation"
])

# TAB 1: DATASET BUILDER
with tab1:
    st.subheader("📊 Dataset Building Tools")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Create New Dataset")
        
        dataset_name = st.text_input("Dataset Name", value="my_dataset")
        dataset_desc = st.text_area("Dataset Description", height=100)
        
        # Data source selection
        data_source = st.selectbox(
            "Data Source",
            ["Upload CSV", "Database Query", "Generate Synthetic", "External API"]
        )
        
        if data_source == "Upload CSV":
            uploaded_file = st.file_uploader("Upload CSV file", type="csv")
            if uploaded_file:
                df = pd.read_csv(uploaded_file)
                st.success(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
                st.dataframe(df.head())
    
    with col2:
        st.markdown("### Dataset Parameters")
        
        train_split = st.slider("Training/Validation Split", 0.5, 0.95, 0.8)
        normalize = st.checkbox("Normalize features", value=True)
        remove_outliers = st.checkbox("Remove outliers", value=False)
        
        if remove_outliers:
            outlier_threshold = st.slider("Outlier threshold (std dev)", 1.0, 5.0, 3.0)
        
        st.divider()
        
        if st.button("Create Dataset", type="primary", use_container_width=True):
            st.success(f"✅ Dataset '\''{dataset_name}'\'' created successfully!")
            st.info(f"Training samples: ~{int(100 * train_split)}, Validation: ~{int(100 * (1-train_split))}")

# TAB 2: MODEL TRAINING
with tab2:
    st.subheader("🧠 ML Model Training Interface")
    
    # ============================================================
    # MODEL TYPE EXPLANATION & TUTORIAL
    # ============================================================
    with st.expander("❓ What's the difference between Model Types? (Click to learn)", expanded=False):
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            st.markdown("""
            #### 🌳 **Random Forest**
            - **What it is:** Ensemble of decision trees voting together
            - **Best for:** Most nanoparticle prediction tasks
            - **Pros:** 
              - Fast training & prediction
              - Handles non-linear relationships
              - Shows feature importance (what matters?)
              - Robust to outliers
            - **Cons:** Can overfit with too many trees
            - **Time to train:** ⚡ Fast (seconds to minutes)
            - **Typical accuracy:** ⭐⭐⭐⭐
            
            #### 🚀 **Gradient Boosting**
            - **What it is:** Builds trees sequentially, each fixing previous mistakes
            - **Best for:** Maximum prediction accuracy
            - **Pros:**
              - Highest accuracy among traditional models
              - Handles complex patterns
              - Better generalization
            - **Cons:** Slower, more prone to overfitting
            - **Time to train:** ⚡ Medium (minutes to hours)
            - **Typical accuracy:** ⭐⭐⭐⭐⭐
            """)
        
        with col_exp2:
            st.markdown("""
            #### 🧠 **Neural Network (Deep Learning)**
            - **What it is:** Interconnected layers mimicking biological neurons
            - **Best for:** Very complex relationships, large datasets
            - **Pros:**
              - Can learn very complex patterns
              - Highly flexible
              - Best for big data
            - **Cons:** Needs lots of data, slow training, hard to interpret
            - **Time to train:** 🔥 Slow (hours to days)
            - **Typical accuracy:** ⭐⭐⭐⭐⭐
            
            #### 🎯 **Support Vector Machine (SVM)**
            - **What it is:** Finds optimal boundaries between data points
            - **Best for:** Small-to-medium datasets, classification
            - **Pros:**
              - Excellent with limited data
              - Good generalization
              - Works well for high-dimensional data
            - **Cons:** Expensive to predict, harder to tune
            - **Time to train:** ⚡ Medium (seconds to minutes)
            - **Typical accuracy:** ⭐⭐⭐⭐
            
            #### 📈 **Linear Regression**
            - **What it is:** Fits a straight line through data
            - **Best for:** Simple relationships, baseline comparisons
            - **Pros:**
              - Very fast
              - Highly interpretable
              - Good baseline
            - **Cons:** Only for linear relationships
            - **Time to train:** ⚡⚡ Very fast (instant)
            - **Typical accuracy:** ⭐⭐
            """)
        
        st.divider()
        st.info("""
        **🎓 Quick Guide:**
        - **Not sure?** Start with **Random Forest** - it's the best all-rounder
        - **Need best accuracy?** Use **Gradient Boosting**
        - **Have lots of data?** Try **Neural Network**
        - **Small dataset?** Try **SVM**
        - **Just testing?** Use **Linear Regression** as baseline
        """)
        
        st.divider()
        st.markdown("### 📚 Technical Terms Glossary")
        
        glossary_col1, glossary_col2 = st.columns(2)
        
        with glossary_col1:
            st.markdown("""
            **🌳 Tree**
            - A machine learning model that makes decisions like a flowchart
            - Starts with a question, splits data, asks another question, etc.
            - Each "branch" represents a decision rule
            - Example: "Is particle size > 100nm? Yes → predict toxicity high"
            
            **🏘️ Ensemble**
            - Combining multiple models to make better predictions
            - Like asking 100 experts instead of 1 expert
            - Random Forest = ensemble of 100+ trees voting together
            - Better accuracy by averaging multiple opinions
            
            **🔄 Overfitting**
            - When a model learns the training data TOO well
            - It memorizes noise instead of learning real patterns
            - Works great on training data, fails on new data
            - Like studying test answers instead of concepts
            
            **✅ Generalization**
            - When a model works well on NEW, unseen data
            - It learned the real patterns, not just memorized examples
            - The opposite of overfitting
            - What we actually want in a good model
            """)
        
        with glossary_col2:
            st.markdown("""
            **📊 Feature Importance**
            - Measures which factors matter most for predictions
            - Example: "Particle size is 80% important, charge is 20%"
            - Helps you understand WHAT the model is using
            - Random Forest can show this, Neural Networks cannot
            
            **⚖️ Trade-off**
            - When improving one thing makes another thing worse
            - Speed vs. Accuracy: Faster models usually less accurate
            - Complexity vs. Interpretability: More powerful = harder to understand
            - You must choose what matters most to you
            
            **🎯 Validation**
            - Testing the model on data it never saw during training
            - Tells you if the model will work on real new data
            - Different from accuracy (which is tested on training data)
            - More honest measure of model performance
            
            **📈 Hyperparameter**
            - Settings you choose BEFORE training the model
            - Example: "Number of trees", "learning rate", "batch size"
            - You decide these values
            - Different values = different model performance
            """)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("### Training Configuration")
        
        # Model selection
        model_type = st.selectbox(
            "Model Type",
            ["Random Forest", "Gradient Boosting", "Neural Network", "SVM", "Linear Regression"]
        )
        
        # Algorithm-specific parameters
        if model_type == "Random Forest":
            n_estimators = st.slider("Number of trees", 10, 500, 100)
            max_depth = st.slider("Max depth", 5, 50, 10)
            min_samples = st.slider("Min samples per leaf", 1, 10, 2)
        
        elif model_type == "Gradient Boosting":
            n_estimators = st.slider("Number of boosting stages", 10, 500, 100)
            learning_rate = st.slider("Learning rate", 0.001, 0.5, 0.1)
            max_depth = st.slider("Max depth", 2, 20, 3)
        
        elif model_type == "Neural Network":
            hidden_layers = st.number_input("Hidden layers", 1, 10, 2)
            units_per_layer = st.number_input("Units per layer", 16, 1024, 128)
            epochs = st.slider("Training epochs", 10, 500, 100)
        
        # Common parameters
        st.divider()
        st.markdown("### Training Options")
        
        dataset_select = st.selectbox("Select Dataset", ["my_dataset", "toxicity_large", "custom_data"])
        target_var = st.selectbox("Target Variable", ["toxicity_score", "efficacy", "cost"])
        
        validation_metric = st.selectbox(
            "Validation Metric",
            ["Accuracy", "R² Score", "MAE", "RMSE", "F1-Score"]
        )
    
    with col2:
        st.markdown("### Training Progress")
        
        if st.button("Start Training", type="primary", use_container_width=True):
            st.info(f"Training {model_type} on '\''{dataset_select}'\'' dataset...")
            
            # Simulate training progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i in range(100):
                progress_bar.progress(i + 1)
                status_text.text(f"Training... {i + 1}% complete")
                import time
                time.sleep(0.03)
            
            st.success("✅ Training completed!")
            
            # Mock results
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Validation Accuracy", "92.3%", "+2.1%")
            with col_b:
                st.metric("Training Loss", "0.145", "-0.032")
            with col_c:
                st.metric("F1-Score", "0.891", "+0.045")

# TAB 3: TRAINING HISTORY
with tab3:
    st.subheader("📈 Training History & Model Management")
    
    # Mock training history data
    training_data = {
        "Model": ["RF-001", "GB-002", "NN-003", "SVM-004", "RF-005"],
        "Type": ["Random Forest", "Gradient Boosting", "Neural Network", "SVM", "Random Forest"],
        "Dataset": ["toxicity_large", "toxicity_large", "custom_data", "toxicity_large", "my_dataset"],
        "Accuracy": [0.923, 0.915, 0.918, 0.890, 0.945],
        "Status": ["✅ Complete", "✅ Complete", "✅ Complete", "✅ Complete", "✅ Complete"],
        "Date": ["2026-03-17", "2026-03-16", "2026-03-15", "2026-03-14", "2026-03-13"]
    }
    
    df_history = pd.DataFrame(training_data)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### Trained Models")
        st.dataframe(df_history, use_container_width=True)
    
    with col2:
        st.markdown("### Actions")
        selected_model = st.selectbox("Select Model", df_history["Model"])
        
        if st.button("📥 Load Model", use_container_width=True):
            st.success(f"✅ Loaded {selected_model}")
        
        if st.button("📊 Compare Models", use_container_width=True):
            st.info("Comparison view coming soon...")
        
        if st.button("📥 Export Model", use_container_width=True):
            st.info("Export options: ONNX, Pickle, TensorFlow")
        
        if st.button("🗑️ Delete Model", use_container_width=True):
            st.warning(f"Deleted {selected_model}")

# TAB 4: MODEL EVALUATION
with tab4:
    st.subheader("🎯 Model Evaluation & Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Performance Metrics")
        
        selected_model = st.selectbox("Select Model to Evaluate", ["RF-001", "GB-002", "NN-003"])
        
        # Mock metrics
        metrics = {
            "Precision": 0.94,
            "Recall": 0.91,
            "F1-Score": 0.925,
            "Accuracy": 0.923,
            "AUC-ROC": 0.967,
            "Log Loss": 0.142
        }
        
        for metric, value in metrics.items():
            st.metric(metric, f"{value:.3f}")
    
    with col2:
        st.markdown("### Confusion Matrix")
        
        # Mock confusion matrix
        import numpy as np
        conf_matrix = np.array([[450, 30], [25, 495]])
        
        st.write("True vs Predicted:")
        st.dataframe(
            pd.DataFrame(
                conf_matrix,
                columns=["Neg. (pred)", "Pos. (pred)"],
                index=["Neg. (actual)", "Pos. (actual)"]
            )
        )

st.divider()

# Show current design if available
if st.session_state.get("design"):
    st.subheader("Current Design Configuration")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Material", st.session_state.get("design", {}).get("Material", "N/A"))
    with col2:
        st.metric("Size", f"{st.session_state.get('"'"'design'"'"', {}).get('"'"'Size'"'"', '"'"'N/A'"'"')} nm")
    with col3:
        st.metric("Charge", f"{st.session_state.get('"'"'design'"'"', {}).get('"'"'Charge'"'"', '"'"'N/A'"'"')} mV")
