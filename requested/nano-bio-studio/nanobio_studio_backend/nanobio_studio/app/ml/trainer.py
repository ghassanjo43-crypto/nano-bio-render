"""
Machine learning trainer module

Placeholder trainers for predicting particle_size_nm, toxicity, and uptake
"""

from typing import Dict, Optional, Any, Tuple
from pathlib import Path
import json
import joblib
import pandas as pd
from loguru import logger

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

from .dataframe_builder import TrainingDataframeBuilder

logger = logger.bind(module="ml.trainer")


class MLTrainer:
    """Trainer for LNP prediction models"""
    
    # Model registry
    AVAILABLE_TASKS = {
        "particle_size": "Predict particle size (nm)",
        "toxicity": "Predict toxicity score",
        "uptake": "Predict uptake efficiency",
    }
    
    def __init__(self, model_dir: str = "models"):
        """
        Initialize ML trainer
        
        Args:
            model_dir: Directory to save trained models
        """
        self.logger = logger
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.models: Dict[str, Any] = {}
        self.model_metrics: Dict[str, Dict[str, float]] = {}
        self.dataframe_builder: Optional[TrainingDataframeBuilder] = None
    
    def train(
        self,
        records: list,
        task: str,
        test_size: float = 0.2,
        random_state: int = 42,
        save_model: bool = True,
    ) -> Dict[str, Any]:
        """
        Train a model for specific task
        
        Args:
            records: List of LNP records
            task: 'particle_size', 'toxicity', or 'uptake'
            test_size: Test set fraction
            random_state: Random seed
            save_model: Whether to save trained model
            
        Returns:
            Dictionary with training results and metrics
        """
        try:
            if task not in self.AVAILABLE_TASKS:
                raise ValueError(f"Unknown task: {task}")
            
            self.logger.info(f"Training {task} model on {len(records)} records")
            
            # Build training dataframe
            self.dataframe_builder = TrainingDataframeBuilder()
            self.dataframe_builder.build_from_records(records, fit_scalers=True, target_task=task)
            
            # Get features and target for task
            X, y = self.dataframe_builder.get_features_for_task(task)
            
            if len(X) < 10:
                self.logger.warning(f"Only {len(X)} samples for training - model may not generalize well")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state
            )
            
            self.logger.info(f"Train set: {len(X_train)}, Test set: {len(X_test)}")
            
            # Train model (ensemble methods for robustness)
            model = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=random_state,
                verbose=0,
            )
            
            model.fit(X_train, y_train)
            
            # Evaluate
            y_pred_train = model.predict(X_train)
            y_pred_test = model.predict(X_test)
            
            train_r2 = r2_score(y_train, y_pred_train)
            test_r2 = r2_score(y_test, y_pred_test)
            train_rmse = mean_squared_error(y_train, y_pred_train, squared=False)
            test_rmse = mean_squared_error(y_test, y_pred_test, squared=False)
            test_mae = mean_absolute_error(y_test, y_pred_test)
            
            # Cross-validation
            cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="r2")
            
            metrics = {
                "train_r2": float(train_r2),
                "test_r2": float(test_r2),
                "train_rmse": float(train_rmse),
                "test_rmse": float(test_rmse),
                "test_mae": float(test_mae),
                "cv_r2_mean": float(cv_scores.mean()),
                "cv_r2_std": float(cv_scores.std()),
                "n_features": len(X.columns),
                "n_train_samples": len(X_train),
                "n_test_samples": len(X_test),
            }
            
            # Feature importance
            feature_importance = {
                name: float(imp) for name, imp in zip(X.columns, model.feature_importances_)
            }
            feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))
            
            # Store model
            self.models[task] = model
            self.model_metrics[task] = metrics
            
            # Save model and metadata
            if save_model:
                self._save_model(task, model, metrics, feature_importance)
            
            self.logger.info(f"Training complete for {task}: R² = {test_r2:.4f}")
            
            return {
                "task": task,
                "status": "success",
                "metrics": metrics,
                "top_features": dict(list(feature_importance.items())[:10]),
            }
        
        except Exception as e:
            self.logger.error(f"Error training {task} model: {e}")
            raise
    
    def predict(self, task: str, X: pd.DataFrame) -> pd.Series:
        """
        Make predictions with trained model
        
        Args:
            task: Model task name
            X: Features dataframe
            
        Returns:
            Predictions series
        """
        if task not in self.models:
            # Try loading from disk
            model_path = self.model_dir / f"{task}_model.pkl"
            if model_path.exists():
                self.models[task] = joblib.load(str(model_path))
                self.logger.info(f"Loaded {task} model from disk")
            else:
                raise ValueError(f"Model not trained for task: {task}")
        
        predictions = self.models[task].predict(X)
        return pd.Series(predictions, index=X.index)
    
    def batch_train(
        self,
        records: list,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        """
        Train models for all available tasks
        
        Args:
            records: List of LNP records
            random_state: Random seed
            
        Returns:
            Dictionary with results for all tasks
        """
        results = {}
        for task in self.AVAILABLE_TASKS.keys():
            try:
                result = self.train(records, task, random_state=random_state)
                results[task] = result
            except Exception as e:
                self.logger.warning(f"Failed to train {task} model: {e}")
                results[task] = {"status": "failed", "error": str(e)}
        
        return results
    
    def _save_model(
        self,
        task: str,
        model: Any,
        metrics: Dict[str, float],
        feature_importance: Dict[str, float],
    ) -> None:
        """Save model and metadata to disk"""
        # Save model
        model_path = self.model_dir / f"{task}_model.pkl"
        joblib.dump(model, str(model_path))
        
        # Save metadata
        metadata = {
            "task": task,
            "metrics": metrics,
            "feature_importance": feature_importance,
            "encoder_metadata": self.dataframe_builder.encoding_metadata.to_dict() if self.dataframe_builder else {},
        }
        
        metadata_path = self.model_dir / f"{task}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"Saved {task} model to {model_path}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about trained models"""
        return {
            "available_tasks": self.AVAILABLE_TASKS,
            "trained_models": list(self.models.keys()),
            "metrics": self.model_metrics,
        }
