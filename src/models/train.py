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
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.utils.config import AppConfig, get_config
from src.utils.db import get_db
from src.utils.io_utils import get_io
from src.utils.logger import PipelineMetrics, get_logger

logger = get_logger(__name__)


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
        'driver_performance_index', 'constructor_performance_index',
        'starting_position', 'points'
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
            r.date as race_date
        FROM driver_race_features f
        JOIN races r ON f.race_id = r.race_id
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
            df = df.dropna(subset=['is_winner', 'is_top3', 'points'])
        
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
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
        
        available_features = [c for c in self.FEATURE_COLS if c in df.columns]
        
        X = df[available_features].copy()
        
        # Handle missing values - fill with median or 0
        X = X.fillna(X.median())
        X = X.fillna(0)  # Fill any remaining NaN with 0
        
        # Target variables - ensure 1D arrays
        y_winner = df['is_winner'].values.ravel()
        y_top3 = df['is_top3'].values.ravel()
        y_points = df['points'].values.ravel()
        
        # Time-based split (preserve order for time series)
        split_idx = int(len(df) * (1 - self.config.ml.test_size))
        
        X_train_raw = X.iloc[:split_idx]
        X_test_raw = X.iloc[split_idx:]
        y_train_winner = y_winner[:split_idx]
        y_test_winner = y_winner[split_idx:]
        y_train_top3 = y_top3[:split_idx]
        y_test_top3 = y_top3[split_idx:]
        y_train_points = y_points[:split_idx]
        y_test_points = y_points[split_idx:]
        
        # Scale features
        if fit_scaler:
            X_train = self.scaler.fit_transform(X_train_raw)
        else:
            X_train = self.scaler.transform(X_train_raw)
        
        X_test = self.scaler.transform(X_test_raw)
        
        # Handle class imbalance with SMOTE for winner prediction
        X_train_winner = X_train
        y_train_winner_resampled = y_train_winner
        
        if len(np.unique(y_train_winner)) >= 2 and np.sum(y_train_winner) > 0:
            try:
                minority_count = np.sum(y_train_winner == 1)
                k_neighbors = min(3, minority_count - 1) if minority_count > 1 else 1
                
                if k_neighbors >= 1:
                    smote = SMOTE(random_state=self.random_state, k_neighbors=k_neighbors)
                    X_train_winner, y_train_winner_resampled = smote.fit_resample(X_train, y_train_winner)
                    logger.info(f"SMOTE applied for winner: {len(y_train_winner_resampled)} samples")
                else:
                    logger.warning("Not enough samples for SMOTE (winner)")
            except Exception as e:
                logger.warning(f"SMOTE failed for winner: {e}")
        else:
            logger.warning("Not enough positive samples for winner SMOTE")
        
        # Handle class imbalance for top3 prediction
        X_train_top3 = X_train
        y_train_top3_resampled = y_train_top3
        
        if len(np.unique(y_train_top3)) >= 2 and np.sum(y_train_top3) > 0:
            try:
                minority_count = np.sum(y_train_top3 == 1)
                k_neighbors = min(3, minority_count - 1) if minority_count > 1 else 1
                
                if k_neighbors >= 1:
                    smote = SMOTE(random_state=self.random_state, k_neighbors=k_neighbors)
                    X_train_top3, y_train_top3_resampled = smote.fit_resample(X_train, y_train_top3)
                    logger.info(f"SMOTE applied for top3: {len(y_train_top3_resampled)} samples")
                else:
                    logger.warning("Not enough samples for SMOTE (top3)")
            except Exception as e:
                logger.warning(f"SMOTE failed for top3: {e}")
        else:
            logger.warning("Not enough positive samples for top3 SMOTE")
        
        logger.info(
            "features_prepared",
            train_size=len(X_train),
            test_size=len(X_test),
            features=len(available_features)
        )
        
        return (
            X_train_winner, X_train_top3, X_train,
            X_test,
            y_train_winner_resampled, y_test_winner,
            y_train_top3_resampled, y_test_top3,
            y_train_points, y_test_points,
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
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=self.random_state,
            class_weight='balanced',
            n_jobs=-1
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
            
            # Calculate scale_pos_weight for imbalance
            scale_pos_weight = len(y_train[y_train == 0]) / max(len(y_train[y_train == 1]), 1)
            
            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                random_state=self.random_state,
                scale_pos_weight=scale_pos_weight,
                eval_metric='logloss',
                use_label_encoder=False
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
    
    # Train winner prediction models
    def train_winner_models(
        self,
        X_train: np.ndarray,
        X_test: np.ndarray,
        y_train: np.ndarray,
        y_test: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, Any]:
        results = {}
        
        # Logistic Regression
        lr = self.train_logistic_regression(X_train, y_train, 'winner')
        lr_metrics = self.evaluate_model(lr, X_test, y_test, feature_names, 'winner')
        results['logistic_regression'] = lr_metrics
        
        # Random Forest
        rf = self.train_random_forest(X_train, y_train, 'winner')
        rf_metrics = self.evaluate_model(rf, X_test, y_test, feature_names, 'winner')
        results['random_forest'] = rf_metrics
        
        # XGBoost
        try:
            xgb = self.train_xgboost(X_train, y_train, 'winner')
            xgb_metrics = self.evaluate_model(xgb, X_test, y_test, feature_names, 'winner')
            results['xgboost'] = xgb_metrics
        except Exception as e:
            logger.error("xgboost_training_failed", target='winner', error=str(e))
        
        return results
    
    # Train top3 prediction models
    def train_top3_models(
        self,
        X_train: np.ndarray,
        X_test: np.ndarray,
        y_train: np.ndarray,
        y_test: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, Any]:
        results = {}
        
        # Logistic Regression
        lr = self.train_logistic_regression(X_train, y_train, 'top3')
        lr_metrics = self.evaluate_model(lr, X_test, y_test, feature_names, 'top3')
        results['logistic_regression'] = lr_metrics
        
        # Random Forest
        rf = self.train_random_forest(X_train, y_train, 'top3')
        rf_metrics = self.evaluate_model(rf, X_test, y_test, feature_names, 'top3')
        results['random_forest'] = rf_metrics
        
        # XGBoost
        try:
            xgb = self.train_xgboost(X_train, y_train, 'top3')
            xgb_metrics = self.evaluate_model(xgb, X_test, y_test, feature_names, 'top3')
            results['xgboost'] = xgb_metrics
        except Exception as e:
            logger.error("xgboost_training_failed", target='top3', error=str(e))
        
        return results
    
    # Train points prediction models (regression)
    def train_points_models(
        self,
        X_train: np.ndarray,
        X_test: np.ndarray,
        y_train: np.ndarray,
        y_test: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, Any]:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import LinearRegression
        
        results = {}
        
        # Linear Regression
        lr = LinearRegression()
        lr.fit(X_train, y_train)
        y_pred = lr.predict(X_test)
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        lr_metrics = {
            'mae': mean_absolute_error(y_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
            'r2': r2_score(y_test, y_pred)
        }
        results['linear_regression'] = lr_metrics
        
        # Random Forest Regressor
        rf = RandomForestRegressor(n_estimators=100, random_state=self.random_state, n_jobs=-1)
        rf.fit(X_train, y_train)
        y_pred = rf.predict(X_test)
        rf_metrics = {
            'mae': mean_absolute_error(y_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
            'r2': r2_score(y_test, y_pred)
        }
        results['random_forest'] = rf_metrics
        
        return results
    
    def train_all_models(
        self,
        years: List[int] = [2020, 2021, 2022, 2023, 2024, 2025]
    ) -> Dict[str, Dict[str, Any]]:
        
        self.metrics.start()
        
        # Load data
        df = self.load_training_data(years)
        
        # Prepare features (returns 11 values)
        (X_train_winner, X_train_top3, X_train_points,
         X_test,
         y_train_winner, y_test_winner,
         y_train_top3, y_test_top3,
         y_train_points, y_test_points,
         feature_names) = self.prepare_features(df)
        
        results = {}
        
        # Train winner prediction models
        logger.info("Training winner prediction models...")
        results['is_winner'] = self.train_winner_models(
            X_train_winner, X_test, y_train_winner, y_test_winner, feature_names
        )
        
        # Train top3 prediction models
        logger.info("Training top3 prediction models...")
        results['is_top3'] = self.train_top3_models(
            X_train_top3, X_test, y_train_top3, y_test_top3, feature_names
        )
        
        # Train points prediction models
        logger.info("Training points prediction models...")
        results['points'] = self.train_points_models(
            X_train_points, X_test, y_train_points, y_test_points, feature_names
        )
        
        pipeline_metrics = self.metrics.finalize()
        logger.info("training_pipeline_complete", metrics=pipeline_metrics)
        
        return results