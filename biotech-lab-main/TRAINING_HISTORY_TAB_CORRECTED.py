# ============================================================
# CORRECTED TRAINING HISTORY TAB - Replace lines 550-800 in 12_ML_Training.py
# ============================================================

    # Tab 3: Training History
    with tab3:
        st.header("📚 Training History")
        
        # Add refresh button and status
        col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
        with col2:
            if st.button("🔄 Refresh", key="refresh_history_btn"):
                st.cache_data.clear()
                if "training_models_data" in st.session_state:
                    del st.session_state["training_models_data"]
                st.rerun()
        
        with col3:
            if "last_training" in st.session_state:
                st.success("✨ New training completed!")
        
        # Load training data directly instead of from session state
        trained_models = _load_trained_models()
        
        # Display database status
        with st.expander("📁 Database Status", expanded=False):
            try:
                import sqlite3
                import os
                
                # Find database path
                current_file_dir = os.path.dirname(os.path.abspath(__file__))
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
                        break
                
                if db_path:
                    st.info(f"📁 Database: `{db_path}`")
                    
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM trained_models")
                    db_count = cursor.fetchone()[0]
                    conn.close()
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📊 Records in DB", db_count)
                    with col2:
                        st.metric("💾 Size", f"{os.path.getsize(db_path) / 1024:.1f} KB")
                    with col3:
                        st.metric("📦 Loaded in UI", len(trained_models))
                else:
                    st.error("❌ Database file not found")
            except Exception as e:
                st.error(f"Error checking database: {str(e)}")
        
        # Display training history
        if trained_models:
            st.success(f"✅ Found {len(trained_models)} trained model(s)")
            
            # Display as table
            with st.expander("📋 All Trained Models", expanded=True):
                try:
                    models_data = []
                    for model in trained_models:
                        # Safely get values with defaults
                        train_score = model.get('train_score')
                        valid_score = model.get('validation_score')
                        
                        models_data.append({
                            "Task": model.get('task_name', 'N/A'),
                            "Model Type": model.get('model_type', 'N/A'),
                            "Samples": model.get('n_training_samples', 'N/A'),
                            "Features": model.get('n_features', 'N/A'),
                            "Train R²": f"{train_score:.4f}" if train_score is not None else "N/A",
                            "Valid R²": f"{valid_score:.4f}" if valid_score is not None else "N/A",
                            "Created": model.get('created_at', 'N/A').strftime("%Y-%m-%d %H:%M") if hasattr(model.get('created_at'), 'strftime') else str(model.get('created_at', 'N/A')),
                        })
                    
                    if models_data:
                        models_df = pd.DataFrame(models_data)
                        st.dataframe(models_df, use_container_width=True, height=300)
                    else:
                        st.info("No model data to display")
                        
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
                        st.metric("Train R²", f"{train_r2:.4f}" if train_r2 is not None else "N/A")
                        st.metric("Valid R²", f"{valid_r2:.4f}" if valid_r2 is not None else "N/A")
                    
                    # Show evaluation details if available
                    eval_summary = model.get('evaluation_summary')
                    if eval_summary and isinstance(eval_summary, dict):
                        st.write("**Detailed Metrics:**")
                        
                        # Handle different evaluation summary formats
                        if 'train' in eval_summary and eval_summary['train']:
                            st.write("*Training Metrics:*")
                            train_metrics = eval_summary['train']
                            if isinstance(train_metrics, dict):
                                for key, value in train_metrics.items():
                                    if value is not None:
                                        st.write(f"  • {key}: {value:.4f}" if isinstance(value, (int, float)) else f"  • {key}: {value}")
                        
                        if 'validation' in eval_summary and eval_summary['validation']:
                            st.write("*Validation Metrics:*")
                            valid_metrics = eval_summary['validation']
                            if isinstance(valid_metrics, dict):
                                for key, value in valid_metrics.items():
                                    if value is not None:
                                        st.write(f"  • {key}: {value:.4f}" if isinstance(value, (int, float)) else f"  • {key}: {value}")
                    
                    created_at = model.get('created_at', 'Unknown')
                    st.caption(f"Created: {created_at}")
        else:
            st.info("No training history yet. Train a model in the **Train Models** tab to get started!")
