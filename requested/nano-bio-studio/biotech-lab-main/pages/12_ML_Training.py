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
from nanobio_studio.app.services.ml_service import MLService
from nanobio_studio.app.ml.schemas import (
    MLTaskConfig,
    TaskType,
    DatasetBuildRequest,
    TrainRequest,
)
from nanobio_studio.app.ml.task_profiles import (
    get_profile_choices,
    get_profile_descriptions,
    apply_profile,
)
from streamlit_auth import (
    require_login,
    require_permission,
    show_user_info,
    StreamlitAuth,
)

# Stub Permission for compatibility
class Permission:
    MODEL_TRAIN = "model_train"
    MODEL_READ = "model_read"
    MODEL_DELETE = "model_delete"
    DATASET_READ = "dataset_read"
    DATASET_CREATE = "dataset_create"
from components.branding import (
    render_brand_header, render_brand_footer, render_sidebar_branding,
    render_page_title_with_branding, render_research_disclaimer
)

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="ML Training - NanoBio Studio™",
    page_icon="🤖",
    layout="wide",
)


@st.cache_data(ttl=30)  # Cache for 30 seconds
def load_training_history_cached():
    """Load training history data from database - cached to execute immediately"""
    try:
        from nanobio_studio.app.db.database import get_db, ModelRepository
        
        db = get_db()
        session = db.get_session()
        model_repo = ModelRepository(session)
        trained_models = model_repo.get_all()
        
        # Important: Detach objects from session before closing
        session.expunge_all()
        session.close()
        
        return trained_models
    except Exception as e:
        logger.error(f"Error loading training history: {e}")
        return []


def load_training_history():
    """Load training history data from database - executed once per session"""
    if "training_history_cache" not in st.session_state:
        st.session_state.training_history_cache = load_training_history_cached()
    
    return st.session_state.training_history_cache


def main():
    """Main page content"""

    # Add branding
    render_sidebar_branding()
    render_brand_header()
    render_page_title_with_branding("🤖 ML Model Training", 
                                     "Train toxicity prediction models with your datasets")

    # ===== DATABASE INITIALIZATION FIX =====
    # Ensure ML module database tables exist before any tabs are loaded
    try:
        import sqlite3
        from pathlib import Path
        
        # Find ml_module.db
        current_dir = Path(__file__).parent
        possible_paths = [
            current_dir.parent / "ml_module.db",  # biotech-lab-main/ml_module.db
            Path("ml_module.db"),  # Current working directory
            current_dir / "ml_module.db",
        ]
        
        db_path = None
        for path in possible_paths:
            if path.exists():
                db_path = str(path)
                break
        
        if db_path:
            # Connect and create tables if they don't exist
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create trained_models table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trained_models (
                    id TEXT PRIMARY KEY,
                    task_name TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    target_variable TEXT NOT NULL,
                    created_at TIMESTAMP,
                    n_training_samples INTEGER,
                    n_features INTEGER,
                    train_score REAL,
                    validation_score REAL,
                    model_path TEXT NOT NULL,
                    preprocessing_path TEXT,
                    task_config TEXT,
                    evaluation_summary TEXT,
                    metadata_json TEXT
                )
            """)
            
            # Create other tables if needed
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS formulations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    payload_type TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    components TEXT NOT NULL,
                    properties TEXT,
                    metadata_json TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assays (
                    id TEXT PRIMARY KEY,
                    formulation_id TEXT NOT NULL,
                    assay_type TEXT NOT NULL,
                    target TEXT,
                    value REAL NOT NULL,
                    created_at TIMESTAMP,
                    conditions TEXT,
                    metadata_json TEXT,
                    FOREIGN KEY (formulation_id) REFERENCES formulations (id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_predictions (
                    id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    formulation_id TEXT,
                    prediction REAL NOT NULL,
                    confidence REAL,
                    created_at TIMESTAMP,
                    metadata_json TEXT,
                    FOREIGN KEY (model_id) REFERENCES trained_models (id),
                    FOREIGN KEY (formulation_id) REFERENCES formulations (id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ranking_results (
                    id TEXT PRIMARY KEY,
                    ranking_session_id TEXT NOT NULL,
                    formulation_id TEXT,
                    rank INTEGER NOT NULL,
                    score REAL NOT NULL,
                    created_at TIMESTAMP,
                    ranking_criteria TEXT,
                    method TEXT,
                    FOREIGN KEY (formulation_id) REFERENCES formulations (id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    artifact_type TEXT NOT NULL,
                    task_name TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    path TEXT NOT NULL,
                    size_bytes INTEGER,
                    description TEXT,
                    version TEXT,
                    metadata_json TEXT,
                    is_favorite INTEGER DEFAULT 0,
                    tags TEXT
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info("✅ Database tables initialized/verified at startup")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    # ===== END DATABASE INITIALIZATION =====

    # Check authentication
    is_logged_in = require_login("ML Training")
    has_permission = require_permission(Permission.MODEL_TRAIN, "Model training") if is_logged_in else False
    
    # If auth checks fail, show warning but still render tabs
    if not is_logged_in or not has_permission:
        st.warning("⚠️ You may not have access to all features")

    # Show user info
    if is_logged_in:
        show_user_info()

    st.divider()
    
    # IMPORTANT: Load and cache training history BEFORE tabs are created
    # This ensures data is available immediately when tab3 is viewed
    @st.cache_data(ttl=30)
    def _load_trained_models():
        """Load training history with direct SQL queries - more reliable"""
        try:
            import sqlite3
            import json
            from datetime import datetime
            
            logger.info("🔄 _load_trained_models: Starting with direct SQL...")
            
            # Get the directory where this file is located
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Try multiple possible paths
            possible_paths = [
                os.path.join(current_file_dir, "../ml_module.db"),
                os.path.join(current_file_dir, "../../ml_module.db"),
                "ml_module.db",
                os.path.join(current_file_dir, "ml_module.db"),
            ]
            
            db_path = None
            for path in possible_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    db_path = abs_path
                    logger.info(f"✅ Found database at: {db_path}")
                    break
            
            if db_path is None:
                logger.error("❌ Database file not found in any location")
                return []
            
            # Connect with sqlite3
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query trained_models table
            cursor.execute("SELECT * FROM trained_models ORDER BY created_at DESC")
            rows = cursor.fetchall()
            logger.info(f"✅ Query returned {len(rows)} rows")
            
            # Convert rows to dict objects with proper column names
            trained_models = []
            for row in rows:
                model_dict = dict(row)
                
                # Parse created_at if it's a string
                if model_dict.get('created_at'):
                    try:
                        # Handle different datetime formats
                        created_at_str = model_dict['created_at']
                        if isinstance(created_at_str, str):
                            # Try parsing ISO format
                            model_dict['created_at'] = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        # Keep as is if parsing fails
                        pass
                
                # Parse JSON fields
                json_fields = ['task_config', 'evaluation_summary', 'metadata_json']
                for field in json_fields:
                    if model_dict.get(field):
                        try:
                            if isinstance(model_dict[field], str):
                                model_dict[field] = json.loads(model_dict[field])
                        except (json.JSONDecodeError, TypeError):
                            pass
                
                trained_models.append(model_dict)
            
            conn.close()
            logger.info(f"✅ Loaded {len(trained_models)} models successfully")
            
            return trained_models
            
        except Exception as e:
            logger.error(f"❌ Error loading training history: {e}", exc_info=True)
            return []
    
    # Load and store in session state
    trained_models = _load_trained_models()
    st.session_state.training_models_data = trained_models
    
    logger.info(f"📊 Total models in session_state.training_models_data: {len(st.session_state.training_models_data)}")
    
    # Show quick stats above tabs (only if data loaded)
    if trained_models:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📚 Total Trainings", len(trained_models))
        with col2:
            latest = max(trained_models, key=lambda m: m.created_at) if trained_models else None
            last_date = latest.created_at.strftime("%Y-%m-%d") if latest else "N/A"
            st.metric("📅 Latest", last_date)
        with col3:
            unique_tasks = len(set(m.task_name for m in trained_models))
            st.metric("🎯 Tasks", unique_tasks)

    # Create tabs - these render regardless of auth status
    tab1, tab2, tab3 = st.tabs(["Dataset Builder", "Train Models", "Training History"])

    # Tab 1: Dataset Builder
    with tab1:
        st.header("📊 Dataset Builder")

        uploaded_file = st.file_uploader(
            "Upload formulation data (CSV)",
            type=["csv"],
            key="dataset_upload",
        )

        if uploaded_file:
            # Load and preview data
            df = pd.read_csv(uploaded_file)

            st.subheader("Data Preview")
            st.dataframe(df.head(10), width='stretch')

            st.info(f"Rows: {len(df)} | Columns: {len(df.columns)}")

            # Quick Start with Profiles
            st.subheader("⚡ Quick Start with Predefined Profiles")
            
            profile_names = get_profile_choices()
            profile_descriptions = get_profile_descriptions()
            
            # Create selectbox with descriptions
            selected_profile = st.selectbox(
                "Select a Task Profile",
                options=profile_names,
                index=0,  # Default to toxicity_prediction
                format_func=lambda x: f"{x.replace('_', ' ').title()} - {profile_descriptions[x]}",
                help="Choose a predefined configuration for your ML task",
                key="profile_selector"
            )
            
            # Show profile details
            with st.expander("📋 Profile Information", expanded=False):
                profile_desc = profile_descriptions[selected_profile]
                st.write(f"**Description:** {profile_desc}")
            
            # Apply profile button
            if st.button("Apply Profile Settings", key="apply_profile_btn", type="primary"):
                try:
                    config, excludes, target = apply_profile(selected_profile, df)
                    st.session_state.profile_config = config
                    st.session_state.profile_excludes = excludes
                    st.session_state.profile_target = target
                    st.success(f"✅ Applied profile: **{selected_profile}**")
                    st.info(f"Target: **{target}** | Excluding: **{', '.join(excludes) if excludes else 'None'}**")
                except Exception as e:
                    st.error(f"Error applying profile: {str(e)}")
            
            st.divider()
            
            # Dataset configuration
            st.subheader("📊 Dataset Configuration")
            
            # Use profile settings if available, otherwise defaults
            use_profile = "profile_config" in st.session_state
            profile_config = st.session_state.get("profile_config")
            
            if use_profile:
                st.info("🎯 Using settings from applied profile")
                col1, col2 = st.columns(2)
                with col1:
                    task_name = st.text_input(
                        "Task Name",
                        value=profile_config.task_name,
                        help="Unique identifier for this task",
                    )
                with col2:
                    task_type = profile_config.task_type.value
                    st.selectbox(
                        "Task Type",
                        options=[profile_config.task_type.value],
                        disabled=True,
                        help="Auto-set from profile",
                    )
            else:
                col1, col2 = st.columns(2)
                with col1:
                    task_name = st.text_input(
                        "Task Name",
                        value="custom_task",
                        help="Unique identifier for this task",
                    )
                with col2:
                    task_type = st.selectbox(
                        "Task Type",
                        options=[
                            "predict_particle_size",
                            "predict_pdi",
                            "predict_toxicity",
                            "predict_uptake",
                            "predict_transfection",
                            "classify_toxicity_band",
                            "classify_uptake_band",
                            "classify_qc_pass",
                        ],
                        help="Select the specific ML prediction task",
                    )

            col1, col2 = st.columns(2)

            with col1:
                if use_profile:
                    # Convert columns to list to avoid pandas Index issues
                    columns_list = list(df.columns)
                    target_idx = 0
                    try:
                        if "profile_target" in st.session_state and st.session_state.profile_target in columns_list:
                            target_idx = columns_list.index(st.session_state.profile_target)
                    except (ValueError, KeyError):
                        target_idx = 0
                    
                    target_variable = st.selectbox(
                        "Target Variable",
                        options=columns_list,
                        index=target_idx,
                        help="Column to predict (auto-set from profile)",
                    )
                else:
                    target_variable = st.selectbox(
                        "Target Variable",
                        options=list(df.columns),
                        help="Column to predict",
                    )

            with col2:
                test_split = st.slider(
                    "Test Split Ratio",
                    min_value=0.1,
                    max_value=0.5,
                    value=0.2 if not use_profile else profile_config.test_split,
                    step=0.05,
                )

            # Feature selection
            st.subheader("Feature Selection")

            default_excludes = []
            if "profile_excludes" in st.session_state:
                default_excludes = st.session_state.profile_excludes
                st.info(f"✓ Profile recommends excluding: **{', '.join(default_excludes)}**")

            exclude_columns = st.multiselect(
                "Columns to Exclude",
                options=df.columns,
                default=default_excludes,
                help="Columns to exclude from training (profile recommendations shown above)",
            )

            # Build button
            if st.button("Build Dataset", key="build_dataset_btn"):
                try:
                    with st.spinner("Building dataset..."):
                        ml_service = MLService()

                        config = MLTaskConfig(
                            task_name=task_name,
                            task_type=TaskType(task_type),
                            target_variable=target_variable,
                            test_split=test_split,
                            exclude_features=exclude_columns,
                        )

                        request = DatasetBuildRequest(task_config=config)

                        dataset = ml_service.build_dataset(df, request)

                        st.success("✅ Dataset built successfully!")

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric("Total Samples", dataset["n_samples"])

                        with col2:
                            st.metric("Features", dataset["n_features"])

                        with col3:
                            st.metric("Train/Validation Split", f"{len(dataset['X_train'])}/{len(dataset['X_valid'])}")

                        # Store in session state
                        st.session_state.dataset = dataset
                        st.session_state.dataset_config = config
                        st.session_state.raw_dataframe = df  # Store original dataframe for training
                        
                        # Show dataset summary
                        with st.expander("📊 Dataset Summary", expanded=True):
                            st.write("**Features Used:**")
                            st.write(dataset.get("feature_names", []))

                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    logger.error(f"Dataset build error: {e}")

    # Tab 2: Train Models
    with tab2:
        st.header("🤖 Train Models")

        if "dataset" not in st.session_state:
            st.warning("⚠️ No dataset found!")
            st.info("👈 Please build a dataset first in the **Dataset Builder** tab, then come back here to train models.")
            st.stop()

        # Use the dataset from session_state
        dataset = st.session_state.dataset
        dataset_config = st.session_state.dataset_config
        raw_dataframe = st.session_state.raw_dataframe  # Get original dataframe for training
        
        st.success(f"✅ Using dataset: **{dataset_config.task_name}**")
        st.info(f"📊 Data: {dataset['n_samples']} samples, {dataset['n_features']} features | Train: {len(dataset['X_train'])}, Validation: {len(dataset['X_valid'])}")
        
        with st.expander("📋 Dataset Details", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Task Name", dataset_config.task_name)
                st.metric("Target Variable", dataset_config.target_variable)
            with col2:
                st.metric("Total Samples", dataset['n_samples'])
                st.metric("Features Used", dataset['n_features'])
        
        st.divider()
        st.subheader("🎛️ Training Configuration")

        col1, col2 = st.columns(2)

        with col1:
            model_types = st.multiselect(
                "Select Model Types",
                options=["linear_regression", "random_forest", "gradient_boosting", "svm"],
                default=["linear_regression", "random_forest"],
                help="Models to train",
                )

            with col2:
                test_split = st.slider(
                    "Test Split",
                    min_value=0.1,
                    max_value=0.5,
                    value=0.2,
                    step=0.05,
                )

            col1, col2 = st.columns(2)

            with col1:
                save_artifacts = st.checkbox(
                    "Save Model Artifacts",
                    value=True,
                    help="Save trained models to disk",
                )

            with col2:
                artifact_name = st.text_input(
                    "Artifact Name",
                    value=st.session_state.dataset_config.task_name,
                    help="Name for saved artifacts",
                )

            if st.button("Start Training", key="start_training_btn"):
                try:
                    st.info("🔄 Starting training process...")
                    logger.info("TRAINING UI: Start Training button clicked")
                    
                    with st.spinner("🔄 Training models... This may take a few minutes"):
                        ml_service = MLService()
                        logger.info("TRAINING UI: MLService instantiated")

                        config = st.session_state.dataset_config
                        config.model_types = model_types

                        request = TrainRequest(
                            dataset_build_request=DatasetBuildRequest(task_config=config),
                            save_artifacts=save_artifacts,
                            artifact_name=artifact_name,
                        )

                        logger.info(f"TRAINING UI: TrainRequest created for task: {config.task_name}")

                        # Use the built dataset from session_state
                        logger.info(f"TRAINING UI: About to call ml_service.train_models() with {len(raw_dataframe)} rows")
                        response = ml_service.train_models(raw_dataframe, request)
                        logger.info(f"TRAINING UI: Training returned successfully, response type: {type(response)}")

                        st.success("✅ Training complete!")
                        logger.info("TRAINING UI: Displayed success message")

                        # Display results
                        col1, col2 = st.columns(2)

                        with col1:
                            st.metric("Best Model", response.best_model_type)

                        with col2:
                            st.metric("Total Samples", response.n_samples)

                        # Evaluation metrics
                        st.subheader("📈 Model Evaluation")

                        for summary in response.evaluation_summaries:
                            with st.expander(
                                f"{summary.model_type} {'⭐ BEST' if summary.best_model else ''}",
                                expanded=summary.best_model,
                            ):
                                col1, col2 = st.columns(2)

                                with col1:
                                    st.write("**Training Metrics**")
                                    for metric, value in summary.train_metrics.model_dump().items():
                                        if value is not None:
                                            st.write(f"  {metric}: {value:.4f}")
                                        else:
                                            st.write(f"  {metric}: N/A")

                                with col2:
                                    st.write("**Validation Metrics**")
                                    for metric, value in summary.validation_metrics.model_dump().items():
                                        if value is not None:
                                            st.write(f"  {metric}: {value:.4f}")
                                        else:
                                            st.write(f"  {metric}: N/A")

                        if response.artifact_path:
                            st.success(f"📦 Model saved to: {response.artifact_path}")

                        # Store in session
                        st.session_state.last_training = response
                        
                        # 🔄 Clear ALL caches after training completes
                        logger.info("🔄 Clearing all caches after successful training...")
                        st.cache_data.clear()  # Clear all cached data functions
                        if "training_models_data" in st.session_state:
                            del st.session_state["training_models_data"]
                        logger.info("✅ Caches cleared")
                        
                        # Show success message
                        st.success("✅ Training complete and saved! Go to Training History tab to view results.")

                except Exception as e:
                    import traceback
                    error_msg = f"Training Error: {str(e)}"
                    error_detail = traceback.format_exc()
                    st.error(f"❌ {error_msg}")
                    st.error(f"**Details:**\n```\n{error_detail}\n```")
                    logger.error(f"❌ Training error: {e}", exc_info=True)
                    logger.error(f"Full traceback:\n{error_detail}")

    # Tab 3: Training History
    with tab3:
        st.header("📚 Training History")
        
        # CRITICAL FIX: Connect to ml_module.db, NOT nanobio_studio.db
        # Training saves to ml_module.db, but we were trying to load from nanobio_studio.db
        
        try:
            import sqlite3
            import os
            import json
            from datetime import datetime
            
            # Find the correct ml_module.db path
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            possible_paths = [
                os.path.join(current_file_dir, "..", "ml_module.db"),  # pages/../ml_module.db
                os.path.join(current_file_dir, "..", "..", "ml_module.db"),  # pages/../../ml_module.db
                os.path.join(os.getcwd(), "ml_module.db"),  # Current working directory
                os.path.join(os.path.dirname(current_file_dir), "ml_module.db"),  # biotech-lab-main/ml_module.db
            ]
            
            # Find the first existing database
            db_path = None
            for path in possible_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    db_path = abs_path
                    logger.info(f"Found ml_module.db at: {db_path}")
                    break
            
            if not db_path:
                st.error(f"❌ Could not find ml_module.db")
                st.write("**Tried paths:**")
                for path in possible_paths:
                    abs_path = os.path.abspath(path)
                    st.write(f"- {abs_path} (exists: {os.path.exists(abs_path)})")
            else:
                # Show database status
                with st.expander("📁 Database Status", expanded=False):
                    st.info(f"📁 Database: `{db_path}`")
                    st.write(f"**Exists:** ✅")
                    st.write(f"**Size:** {os.path.getsize(db_path) / 1024:.1f} KB")
                
                # Connect to ml_module.db
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Check if table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trained_models'")
                table_exists = cursor.fetchone()
                
                if not table_exists:
                    st.warning("⚠️ trained_models table not found in ml_module.db")
                else:
                    # Get all trained models from ml_module.db
                    cursor.execute("SELECT * FROM trained_models ORDER BY created_at DESC")
                    rows = cursor.fetchall()
                    
                    if rows:
                        st.success(f"✅ Found {len(rows)} trained model(s) in ml_module.db")
                        
                        # Convert rows to list of dicts and parse JSON/datetime fields
                        trained_models = []
                        for row in rows:
                            model_dict = dict(row)
                            
                            # Parse JSON fields
                            for field in ['task_config', 'evaluation_summary', 'metadata_json']:
                                if model_dict.get(field) and isinstance(model_dict[field], str):
                                    try:
                                        model_dict[field] = json.loads(model_dict[field])
                                    except:
                                        pass
                            
                            # Parse datetime
                            if model_dict.get('created_at'):
                                try:
                                    if isinstance(model_dict['created_at'], str):
                                        model_dict['created_at'] = datetime.fromisoformat(
                                            model_dict['created_at'].replace('Z', '+00:00')
                                        )
                                except:
                                    pass
                            
                            trained_models.append(model_dict)
                        
                        # Display as table first
                        with st.expander("📋 All Trained Models", expanded=True):
                            try:
                                models_data = []
                                for model in trained_models:
                                    # Check if this is a versioned model
                                    task_name = model.get('task_name', 'N/A')
                                    is_versioned = '_v' in task_name and task_name.split('_v')[-1].isdigit()
                                    
                                    # Get version info from metadata if available
                                    metadata = model.get('metadata_json', {})
                                    version = metadata.get('version', '')
                                    
                                    train_r2 = model.get('train_score')
                                    valid_r2 = model.get('validation_score')
                                    
                                    models_data.append({
                                        "Task": task_name,
                                        "Ver.": version if version else ('v' + task_name.split('_v')[-1] if is_versioned else '1'),
                                        "Model": model.get('model_type', 'N/A'),
                                        "Samples": model.get('n_training_samples', 'N/A'),
                                        "Features": model.get('n_features', 'N/A'),
                                        "Train R²": f"{train_r2:.4f}" if train_r2 is not None else "N/A",
                                        "Valid R²": f"{valid_r2:.4f}" if valid_r2 is not None else "N/A",
                                        "Created": model.get('created_at', 'N/A').strftime("%Y-%m-%d %H:%M") if hasattr(model.get('created_at'), 'strftime') else str(model.get('created_at', 'N/A')),
                                    })
                                
                                if models_data:
                                    models_df = pd.DataFrame(models_data)
                                    st.dataframe(models_df, width='stretch', height=300)
                                else:
                                    st.info("No model data to display")
                                    
                            except Exception as e:
                                logger.error(f"Error displaying models table: {e}")
                                st.error(f"Error displaying table: {e}")
                        
                        # Show detailed view for each model - grouped by base name
                        st.subheader("📊 Model Details")
                        
                        # Group models by base name for better organization
                        from collections import defaultdict
                        models_by_base = defaultdict(list)
                        
                        for model in trained_models:
                            task_name = model.get('task_name', 'Unknown')
                            # Extract base name (remove version suffix)
                            if '_v' in task_name and task_name.split('_v')[-1].isdigit():
                                base_name = '_v'.join(task_name.split('_v')[:-1])
                            else:
                                base_name = task_name
                            models_by_base[base_name].append(model)
                        
                        # Display models grouped by base name
                        for base_name, model_versions in sorted(models_by_base.items()):
                            # Sort versions by created_at (newest first)
                            from datetime import datetime
                            model_versions.sort(key=lambda x: x.get('created_at', datetime.min) if isinstance(x.get('created_at'), datetime) else datetime.fromisoformat(str(x.get('created_at')).replace('Z', '+00:00')) if x.get('created_at') else datetime.min, reverse=True)
                            
                            st.write(f"### 📁 {base_name} ({len(model_versions)} versions)")
                            
                            for model in model_versions:
                                task_name = model.get('task_name', 'Unknown')
                                model_type = model.get('model_type', 'Unknown')
                                
                                # Extract version info
                                if '_v' in task_name and task_name.split('_v')[-1].isdigit():
                                    version_display = f" (Version {task_name.split('_v')[-1]})"
                                else:
                                    version_display = " (Version 1)"
                                
                                created_str = model.get('created_at', 'Unknown')
                                if hasattr(created_str, 'strftime'):
                                    created_str = created_str.strftime('%Y-%m-%d %H:%M')
                                
                                with st.expander(f"{model_type}{version_display} - {created_str}", expanded=False):
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        st.metric("Samples", model.get('n_training_samples', 'N/A'))
                                        st.metric("Features", model.get('n_features', 'N/A'))
                                    
                                    with col2:
                                        st.metric("Model Type", model.get('model_type', 'N/A'))
                                        task_type = model.get('task_type', 'N/A')
                                        if isinstance(task_type, str):
                                            task_type = task_type.replace('predict_', '').replace('classify_', '').replace('TaskType.', '')
                                        st.metric("Task Type", task_type)
                                    
                                    with col3:
                                        train_r2 = model.get('train_score')
                                        valid_r2 = model.get('validation_score')
                                        st.metric("Train R²", f"{train_r2:.4f}" if train_r2 is not None else "N/A")
                                        st.metric("Valid R²", f"{valid_r2:.4f}" if valid_r2 is not None else "N/A")
                                    
                                    # Show evaluation details
                                    eval_summary = model.get('evaluation_summary')
                                    if eval_summary and isinstance(eval_summary, dict):
                                        st.write("**Detailed Metrics:**")
                                        
                                        if 'train' in eval_summary and eval_summary['train']:
                                            st.write("*Training Metrics:*")
                                            for key, value in eval_summary['train'].items():
                                                if value is not None:
                                                    st.write(f"  • {key}: {value:.4f}" if isinstance(value, (int, float)) else f"  • {key}: {value}")
                                        
                                        if 'validation' in eval_summary and eval_summary['validation']:
                                            st.write("*Validation Metrics:*")
                                            for key, value in eval_summary['validation'].items():
                                                if value is not None:
                                                    st.write(f"  • {key}: {value:.4f}" if isinstance(value, (int, float)) else f"  • {key}: {value}")
                                    
                                    created_at = model.get('created_at', 'Unknown')
                                    st.caption(f"Created: {created_at}")
                    else:
                        st.info("No training history yet. Train a model in the **Train Models** tab to get started!")
                
                conn.close()
        
        except Exception as e:
            st.error(f"❌ Error loading training history: {str(e)}")
            logger.error(f"Training history error: {e}", exc_info=True)
            with st.expander("📋 Error Details"):
                import traceback
                st.code(traceback.format_exc())
        st.write("**🔧 Database Status:**")
        
        try:
            import sqlite3
            import os
            
            # Get the directory where this file is located
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Find the correct database path
            possible_paths = [
                os.path.join(current_file_dir, "../ml_module.db"),  # biotech-lab-main
                os.path.join(current_file_dir, "../../ml_module.db"),  # root
                "ml_module.db",
                "biotech-lab-main/ml_module.db",
            ]
            
            db_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    db_path = os.path.abspath(path)
                    break
            
            if db_path:
                st.info(f"📁 Database location: `{db_path}`")
                
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM trained_models")
                db_count = cursor.fetchone()[0]
                conn.close()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 DB Records", db_count)
                with col2:
                    st.metric("💾 DB File", f"{os.path.getsize(db_path)} bytes")
                with col3:
                    st.metric("✅ Status", "Connected")
                
                logger.info(f"✅ Database connected: {db_path} ({db_count} records)")
            else:
                st.error(f"❌ Database not found. Searched in:")
                for p in possible_paths:
                    st.code(os.path.abspath(p), language="text")
        except Exception as e:
            st.error(f"DB Status Error: {str(e)}")
            import traceback
            st.code(traceback.format_exc(), language="python")
        
        st.session_state.setdefault("_training_history_loaded", False)
        
        # Add cache clearing button
        col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
        with col2:
            if st.button("🔄 Refresh", key="refresh_history_btn"):
                st.session_state.pop("training_models_data", None)
                _load_trained_models.clear()
                logger.info("🔄 Manual refresh triggered - clearing cache and rerunning")
                st.rerun()
        
        # Show if training was just completed
        with col3:
            if "last_training" in st.session_state:
                st.success("✨ Just trained!")

        # Get training data directly from pre-loaded session state
        trained_models = st.session_state.get("training_models_data", [])
        
        # Debug info
        st.info(f"📊 **Session State Keys:** {len(st.session_state)} total | **Training Models Loaded:** {len(trained_models)}")
        
        if not trained_models:
            st.warning(f"⚠️ No training models in session state. Trying to load directly from database...")
            
            # Try loading directly
            try:
                import sqlite3
                db_path = "ml_module.db"
                
                # Check if file exists
                if not os.path.exists(db_path):
                    st.error(f"❌ Database file not found: {db_path}")
                    st.stop()
                
                # Connect and query
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM trained_models")
                count = cursor.fetchone()[0]
                conn.close()
                
                st.warning(f"⚠️ Database file found with **{count} records**, but loading function returned 0 models")
                st.error("**Debugging needed:** Check logs or contact support")
                
            except Exception as e:
                st.error(f"❌ Error checking database: {str(e)}")
        
        if trained_models:
            st.success(f"✅ Found {len(trained_models)} trained model(s)")
            
            # Display as table first
            with st.expander("📋 All Trained Models", expanded=True):
                try:
                    models_data = []
                    for model in trained_models:
                        models_data.append({
                            "Task": model.get('task_name', 'N/A'),
                            "Model Type": model.get('model_type', 'N/A'),
                            "Samples": model.get('n_training_samples', 'N/A'),
                            "Features": model.get('n_features', 'N/A'),
                            "Train R²": f"{model.get('train_score', 0):.4f}" if model.get('train_score') else "N/A",
                            "Valid R²": f"{model.get('validation_score', 0):.4f}" if model.get('validation_score') else "N/A",
                            "Created": model.get('created_at', 'N/A'),
                        })
                    
                    models_df = pd.DataFrame(models_data)
                    st.dataframe(models_df, width='stretch', height=300)
                except Exception as e:
                    logger.error(f"Error displaying models table: {e}")
                    st.error(f"Error displaying table: {e}")
            
            # Show detailed view for each model
            st.subheader("📊 Model Details")
            
            for model in trained_models:
                task_name = model.get('task_name', 'Unknown')
                model_type = model.get('model_type', 'Unknown')
                
                with st.expander(f"{task_name} - {model_type}", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Samples", model.get('n_training_samples', 'N/A'))
                        st.metric("Features", model.get('n_features', 'N/A'))
                    
                    with col2:
                        st.metric("Model Type", model.get('model_type', 'N/A'))
                        task_type = model.get('task_type', 'N/A')
                        if isinstance(task_type, str):
                            task_type = task_type.replace('predict_', '').replace('classify_', '').replace('TaskType.', '')
                        st.metric("Task Type", task_type)
                    
                    with col3:
                        train_r2 = model.get('train_score')
                        valid_r2 = model.get('validation_score')
                        st.metric("Train R²", f"{train_r2:.4f}" if train_r2 else "N/A")
                        st.metric("Valid R²", f"{valid_r2:.4f}" if valid_r2 else "N/A")
                    
                    # Show evaluation details if available
                    eval_summary = model.get('evaluation_summary')
                    if eval_summary and isinstance(eval_summary, dict):
                        st.write("**Detailed Metrics:**")
                        if 'train' in eval_summary and eval_summary['train']:
                            st.write("*Training Metrics:*")
                            for key, value in eval_summary['train'].items():
                                if value is not None:
                                    st.write(f"  • {key}: {value:.4f}" if isinstance(value, float) else f"  • {key}: {value}")
                        
                        if 'validation' in eval_summary and eval_summary['validation']:
                            st.write("*Validation Metrics:*")
                            for key, value in eval_summary['validation'].items():
                                if value is not None:
                                    st.write(f"  • {key}: {value:.4f}" if isinstance(value, float) else f"  • {key}: {value}")
                    
                    created_at = model.get('created_at', 'Unknown')
                    st.caption(f"Created: {created_at}")
        else:
            st.info("No training history yet. Train a model in the **Train Models** tab to get started!")
        
        # 🔧 DEBUG SECTION: Show raw database content
        st.divider()
        with st.expander("🔧 **DEBUG: Raw Database Content**", expanded=False):
            st.warning("⚠️ This shows the actual database file content for debugging purposes")
            st.write("**Attempting to connect to database...**")
            
            try:
                import sqlite3
                import os
                
                # Check if database file exists
                db_path = "ml_module.db"
                db_exists = os.path.exists(db_path)
                st.info(f"📁 Database file 'ml_module.db' exists: **{db_exists}**")
                
                if db_exists:
                    st.info(f"📊 File size: **{os.path.getsize(db_path)} bytes**")
                
                # Connect directly with sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                st.write(f"**Tables in database:** {len(tables)} found")
                for table in tables:
                    st.write(f"  • `{table[0]}`")
                
                # Query trained_models table specifically
                st.write("---")
                st.write("**Querying `trained_models` table...**")
                cursor.execute("SELECT COUNT(*) FROM trained_models")
                count = cursor.fetchone()[0]
                st.success(f"✅ **Total records: {count}**")
                
                if count > 0:
                    # Get all data
                    cursor.execute("SELECT * FROM trained_models")
                    columns = [description[0] for description in cursor.description]
                    rows = cursor.fetchall()
                    
                    df = pd.DataFrame(rows, columns=columns)
                    st.dataframe(df, width='stretch', height=400)
                    
                    # Download button
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Download as CSV",
                        data=csv,
                        file_name="trained_models_export.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("❌ **No records in trained_models table**")
                
                conn.close()
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                import traceback
                st.code(traceback.format_exc(), language="python")



if __name__ == "__main__":
    main()

# Add branded footer at the absolute end
render_brand_footer()
