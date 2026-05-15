# Machine Learning training pipeline for F1 race prediction.
import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score
)
from sklearn.model_selection import TimeSeriesSplit, train_test_split
from sklearn.preprocessing import StandardScaler

from src.utils.config import AppConfig, get_config
from src.utils.db import get_db
from src.utils.io_utils import get_io
from src.utils.logger import PipelineMetrics, get_logger

logger = get_logger(__name__)

# Class structure & configuration
class F1ModelTrainer:
    # Feature columns for training (must match feature engineering output)
    FEATURE_COLS = [
        'rolling_avg_points_5r', 'rolling_avg_finish_pos_5r', 'rolling_points_trend',
        'recent_form_points', 'recent_form_finish_pos', 'recent_form_quali_pos',
        'constructor_avg_points_5r', 'constructor_reliability_score',
        'track_avg_points', 'track_avg_finish_pos', 'track_best_finish_pos', 'track_experience_races',
        'lap_consistency_std', 'avg_lap_time_ms', 'fastest_lap_time_ms',
        'dnf_probability', 'consecutive_finishes', 'mechanical_dnf_rate',
        'quali_position', 'quali_gap_to_pole_ms', 'grid_position_gain_potential',
        'wet_race_experience', 'wet_race_avg_points',
        'driver_performance_index', 'constructor_performance_index'
    ]
    
    TARGET_COLS = ['is_winner', 'is_top3', 'points']
    
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or get_config()
        self.db = get_db()
        self.io = get_io()
        self.metrics = PipelineMetrics("model_training")
        self.random_state = self.config.ml.random_state
        
        # Paths
        self.model_dir = Path(self.config.ml.model_dir)
        self.metrics_dir = Path(self.config.ml.metrics_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        self.scaler = StandardScaler()
    
    # Load feature data with time-based filtering
    def load_training_data(
        self,
        years: List[int],
        require_targets: bool = True
    ) -> pd.DataFrame:

        placeholders = ', '.join([f":year_{i}" for i in range(len(years))])
        params = {f"year_{i}": year for i, year in enumerate(years)}
        
        query = f"""
        SELECT 
            f.*,
            r.year,
            r.round,
            r.date as race_date,
            res.position_order,
            res.points as actual_points,
            CASE WHEN res.position_order = 1 THEN 1 ELSE 0 END as is_winner,
            CASE WHEN res.position_order <= 3 THEN 1 ELSE 0 END as is_top3
        FROM driver_race_features f
        JOIN races r ON f.race_id = r.race_id
        JOIN results res ON f.race_id = res.race_id AND f.driver_id = res.driver_id
        WHERE r.year IN ({placeholders})
        ORDER BY r.date ASC
        """
        
        df = self.db.execute_dataframe(query, params)
        
        # Handle missing features
        available_features = [c for c in self.FEATURE_COLS if c in df.columns]
        missing = set(self.FEATURE_COLS) - set(available_features)
        if missing:
            logger.warning("missing_features", features=list(missing))
        
        # Drop rows with missing targets if required
        if require_targets:
            df = df.dropna(subset=['is_winner', 'is_top3'])
        
        logger.info(
            "training_data_loaded",
            rows=len(df),
            years=years,
            features=len(available_features)
        )
        
        return df
    
    # Prepare feature matrix with scaling and imputation
    def prepare_features(
        self,
        df: pd.DataFrame,
        fit_scaler: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
        
        available_features = [c for c in self.FEATURE_COLS if c in df.columns]
        
        X = df[available_features].copy()
        y_winner = df['is_winner'].values
        y_top3 = df['is_top3'].values
        
        # Time-based split (critical: no random shuffle)
        split_idx = int(len(df) * (1 - self.config.ml.test_size))
        
        X_train_raw = X.iloc[:split_idx]
        X_test_raw = X.iloc[split_idx:]
        y_train_winner = y_winner[:split_idx]
        y_test_winner = y_winner[split_idx:]
        y_train_top3 = y_top3[:split_idx]
        y_test_top3 = y_top3[split_idx:]
        
        # Scale features
        if fit_scaler:
            X_train = self.scaler.fit_transform(X_train_raw)
        else:
            X_train = self.scaler.transform(X_train_raw)
        
        X_test = self.scaler.transform(X_test_raw)
        
        # Handle class imbalance with SMOTE for winner prediction
        smote = SMOTE(random_state=self.random_state)
        X_train_winner, y_train_winner = smote.fit_resample(X_train, y_train_winner)
        
        logger.info(
            "features_prepared",
            train_size=len(X_train),
            test_size=len(X_test),
            features=len(available_features)
        )
        
        return (
            X_train_winner, X_test,
            y_train_winner, y_test_winner,
            available_features
        )
    
    # Training baseline logistic regression model
    def train_logistic_regression(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        target: str
    ) -> LogisticRegression:

        model = LogisticRegression(
            random_state=self.random_state,
            max_iter=1000,
            class_weight='balanced'
        )
        model.fit(X_train, y_train)
        
        logger.info("logistic_regression_trained", target=target)
        return model
    
    # Random forest (ensemble)
    def train_random_forest(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        target: str
    ) -> RandomForestClassifier:
        model = RandomForestClassifier(
            n_estimators=200,                 # Number of trees
            max_depth=10,                     # Prevent overfitting
            min_samples_split=5,              # Minimum sample to split node
            random_state=self.random_state,   
            class_weight='balanced',          # Handle imbalance
            n_jobs=-1                         # Use all CPU cores
        )
        model.fit(X_train, y_train)
        
        logger.info("random_forest_trained", target=target)
        return model
    
    # XGBoost training
    def train_xgboost(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        target: str
    ) -> Any:
        try:
            import xgboost as xgb
            
            model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                random_state=self.random_state,
                scale_pos_weight=5,  # Handle imbalance
                eval_metric='logloss'
            )
            model.fit(X_train, y_train)
            
            logger.info("xgboost_trained", target=target)
            return model
            
        except ImportError:
            logger.warning("xgboost_not_installed")
            raise
    
    # Comprehensive model evaluation
    def evaluate_model(
        self,
        model: Any,
        X_test: np.ndarray,
        y_test: np.ndarray,
        feature_names: List[str],
        target: str
    ) -> Dict[str, Any]:
       
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else None
        
        metrics = {
            'target': target,
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1_score': f1_score(y_test, y_pred, zero_division=0),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'classification_report': classification_report(y_test, y_pred, output_dict=True)
        }
        
        if y_prob is not None:
            try:
                metrics['roc_auc'] = roc_auc_score(y_test, y_prob)
            except ValueError:
                metrics['roc_auc'] = None
        
        # Feature importance
        if hasattr(model, 'feature_importances_'):
            importance = dict(zip(feature_names, model.feature_importances_.tolist()))
            metrics['feature_importance'] = dict(
                sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
            )
        elif hasattr(model, 'coef_'):
            importance = dict(zip(feature_names, np.abs(model.coef_[0]).tolist()))
            metrics['feature_importance'] = dict(
                sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
            )
        
        return metrics
    
    # Model versioning & storage
    def save_model(
        self,
        model: Any,
        model_name: str,
        target: str,
        metrics: Dict[str, Any]
    ) -> str:
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{model_name}_{target}_{timestamp}.pkl"
        path = self.model_dir / filename
        
        # Save model
        with open(path, 'wb') as f:
            pickle.dump({
                'model': model,
                'scaler': self.scaler,
                'feature_names': self.FEATURE_COLS,
                'metrics': metrics,
                'timestamp': timestamp,
                'version': '1.0.0'
            }, f)
        
        # Save metrics separately
        metrics_path = self.metrics_dir / f"{model_name}_{target}_{timestamp}.json"
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)
        
        logger.info(
            "model_saved",
            path=str(path),
            model=model_name,
            target=target,
            accuracy=metrics.get('accuracy')
        )
        
        return str(path)
    
    def train_all_models(
        self,
        years: List[int] = [2021, 2022, 2023, 2024, 2025]
    ) -> Dict[str, Dict[str, str]]:
        
        self.metrics.start()
        
        # Load data
        df = self.load_training_data(years)
        
        # Prepare features
        X_train, X_test, y_train_winner, y_test_winner, feature_names = self.prepare_features(df)
        
        # Also prepare top3 targets
        split_idx = int(len(df) * (1 - self.config.ml.test_size))
        y_top3 = df['is_top3'].values
        y_train_top3 = y_top3[:split_idx]
        y_test_top3 = y_top3[split_idx:]
        
        # Apply SMOTE for top3
        smote = SMOTE(random_state=self.random_state)
        X_train_top3, y_train_top3 = smote.fit_resample(X_train, y_train_top3)
        
        results = {}
        
        # Train models for each target
        targets = {
            'is_winner': (y_train_winner, y_test_winner),
            'is_top3': (y_train_top3, y_test_top3)
        }
        
        for target, (y_tr, y_te) in targets.items():
            results[target] = {}
            
            # Logistic Regression
            lr = self.train_logistic_regression(X_train, y_tr, target)
            lr_metrics = self.evaluate_model(lr, X_test, y_te, feature_names, target)
            results[target]['logistic_regression'] = self.save_model(
                lr, 'logistic_regression', target, lr_metrics
            )
            
            # Random Forest
            rf = self.train_random_forest(X_train, y_tr, target)
            rf_metrics = self.evaluate_model(rf, X_test, y_te, feature_names, target)
            results[target]['random_forest'] = self.save_model(
                rf, 'random_forest', target, rf_metrics
            )
            
            # XGBoost
            try:
                xgb = self.train_xgboost(X_train, y_tr, target)
                xgb_metrics = self.evaluate_model(xgb, X_test, y_te, feature_names, target)
                results[target]['xgboost'] = self.save_model(
                    xgb, 'xgboost', target, xgb_metrics
                )
            except Exception as e:
                logger.error("xgboost_training_failed", target=target, error=str(e))
        
        pipeline_metrics = self.metrics.finalize()
        logger.info("training_pipeline_complete", models=results, metrics=pipeline_metrics)
        
        return results