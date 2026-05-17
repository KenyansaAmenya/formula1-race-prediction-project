import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score,
    mean_absolute_error, mean_squared_error, r2_score
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
        'starting_position'
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
    
    def load_training_data(self, years: List[int]) -> pd.DataFrame:
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
        
        available_features = [c for c in self.FEATURE_COLS if c in df.columns]
        missing = set(self.FEATURE_COLS) - set(available_features)
        if missing:
            logger.warning("missing_features", features=list(missing))
        
        logger.info(
            "training_data_loaded",
            rows=len(df),
            years=years,
            features=len(available_features)
        )
        
        return df
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
    
        available_features = [c for c in self.FEATURE_COLS if c in df.columns]
        
        X = df[available_features].copy()
        X = X.fillna(X.median())
        X = X.fillna(0)
        
        y_winner = df['is_winner'].values.ravel()
        y_top3 = df['is_top3'].values.ravel()
        y_points = df['points'].values.ravel()
        
        # Split data (preserve time order)
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
        X_train = self.scaler.fit_transform(X_train_raw)
        X_test = self.scaler.transform(X_test_raw)
        
        # Apply SMOTE for class imbalance
        X_train_winner, y_train_winner = self._apply_smote(X_train, y_train_winner, 'winner')
        X_train_top3, y_train_top3 = self._apply_smote(X_train, y_train_top3, 'top3')
        
        logger.info(
            "features_prepared",
            train_size=len(X_train),
            test_size=len(X_test),
            features=len(available_features)
        )
        
        return (
            X_train_winner, X_train_top3, X_train,
            X_test,
            y_train_winner, y_test_winner,
            y_train_top3, y_test_top3,
            y_train_points, y_test_points,
            available_features
        )
    
    def _apply_smote(self, X: np.ndarray, y: np.ndarray, name: str) -> Tuple[np.ndarray, np.ndarray]:
        
        if len(np.unique(y)) >= 2 and np.sum(y) > 0:
            try:
                minority_count = np.sum(y == 1)
                k_neighbors = min(3, minority_count - 1) if minority_count > 1 else 1
                
                if k_neighbors >= 1:
                    smote = SMOTE(random_state=self.random_state, k_neighbors=k_neighbors)
                    X_resampled, y_resampled = smote.fit_resample(X, y)
                    logger.info(f"SMOTE applied for {name}: {len(y_resampled)} samples")
                    return X_resampled, y_resampled
            except Exception as e:
                logger.warning(f"SMOTE failed for {name}: {e}")
        
        return X, y
    
    def train_logistic_regression(self, X_train: np.ndarray, y_train: np.ndarray, target: str) -> LogisticRegression:
    
        model = LogisticRegression(
            random_state=self.random_state,
            max_iter=1000,
            class_weight='balanced'
        )
        model.fit(X_train, y_train)
        logger.info("logistic_regression_trained", target=target)
        return model
    
    def train_random_forest(self, X_train: np.ndarray, y_train: np.ndarray, target: str) -> RandomForestClassifier:
        
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
    
    def train_xgboost(self, X_train: np.ndarray, y_train: np.ndarray, target: str) -> Any:
        
        try:
            import xgboost as xgb
            
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
            logger.error("xgboost_not_installed")
            raise
    
    def train_linear_regression(self, X_train: np.ndarray, y_train: np.ndarray) -> LinearRegression:
        
        model = LinearRegression()
        model.fit(X_train, y_train)
        logger.info("linear_regression_trained")
        return model
    
    def train_random_forest_regressor(self, X_train: np.ndarray, y_train: np.ndarray) -> RandomForestRegressor:
        
        model = RandomForestRegressor(
            n_estimators=100,
            random_state=self.random_state,
            n_jobs=-1
        )
        model.fit(X_train, y_train)
        logger.info("random_forest_regressor_trained")
        return model
    
    def evaluate_classifier(self, model: Any, X_test: np.ndarray, y_test: np.ndarray, feature_names: List[str], target: str) -> Dict[str, Any]:
        
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
        
        if hasattr(model, 'feature_importances_'):
            importance = dict(zip(feature_names, model.feature_importances_.tolist()))
            metrics['feature_importance'] = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10])
        elif hasattr(model, 'coef_'):
            importance = dict(zip(feature_names, np.abs(model.coef_[0]).tolist()))
            metrics['feature_importance'] = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return metrics
    
    def evaluate_regressor(self, model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
    
        y_pred = model.predict(X_test)
        return {
            'mae': mean_absolute_error(y_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
            'r2': r2_score(y_test, y_pred)
        }
    
    def save_model(self, model: Any, model_name: str, target: str, metrics: Dict[str, Any]) -> str:
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{model_name}_{target}_{timestamp}.pkl"
        path = self.model_dir / filename
        
        with open(path, 'wb') as f:
            pickle.dump({
                'model': model,
                'scaler': self.scaler,
                'feature_names': self.FEATURE_COLS,
                'metrics': metrics,
                'timestamp': timestamp,
                'version': '2.0.0'
            }, f)
        
        # Save metrics separately
        metrics_path = self.metrics_dir / f"{model_name}_{target}_{timestamp}.json"
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)
        
        logger.info("model_saved", path=str(path), model=model_name, target=target)
        return str(path)
    
    def train_winner_models(self, X_train: np.ndarray, X_test: np.ndarray, y_train: np.ndarray, y_test: np.ndarray, feature_names: List[str]) -> Dict[str, Any]:
        
        results = {}
        
        # Logistic Regression
        lr = self.train_logistic_regression(X_train, y_train, 'winner')
        lr_metrics = self.evaluate_classifier(lr, X_test, y_test, feature_names, 'winner')
        lr_path = self.save_model(lr, 'logistic_regression', 'winner', lr_metrics)
        results['logistic_regression'] = {'model': lr, 'metrics': lr_metrics, 'path': lr_path}
        
        # Random Forest
        rf = self.train_random_forest(X_train, y_train, 'winner')
        rf_metrics = self.evaluate_classifier(rf, X_test, y_test, feature_names, 'winner')
        rf_path = self.save_model(rf, 'random_forest', 'winner', rf_metrics)
        results['random_forest'] = {'model': rf, 'metrics': rf_metrics, 'path': rf_path}
        
        # XGBoost
        try:
            xgb = self.train_xgboost(X_train, y_train, 'winner')
            xgb_metrics = self.evaluate_classifier(xgb, X_test, y_test, feature_names, 'winner')
            xgb_path = self.save_model(xgb, 'xgboost', 'winner', xgb_metrics)
            results['xgboost'] = {'model': xgb, 'metrics': xgb_metrics, 'path': xgb_path}
        except Exception as e:
            logger.error("xgboost_training_failed", target='winner', error=str(e))
        
        return results
    
    def train_top3_models(self, X_train: np.ndarray, X_test: np.ndarray, y_train: np.ndarray, y_test: np.ndarray, feature_names: List[str]) -> Dict[str, Any]:
        
        results = {}
        
        lr = self.train_logistic_regression(X_train, y_train, 'top3')
        lr_metrics = self.evaluate_classifier(lr, X_test, y_test, feature_names, 'top3')
        lr_path = self.save_model(lr, 'logistic_regression', 'top3', lr_metrics)
        results['logistic_regression'] = {'model': lr, 'metrics': lr_metrics, 'path': lr_path}
        
        rf = self.train_random_forest(X_train, y_train, 'top3')
        rf_metrics = self.evaluate_classifier(rf, X_test, y_test, feature_names, 'top3')
        rf_path = self.save_model(rf, 'random_forest', 'top3', rf_metrics)
        results['random_forest'] = {'model': rf, 'metrics': rf_metrics, 'path': rf_path}
        
        try:
            xgb = self.train_xgboost(X_train, y_train, 'top3')
            xgb_metrics = self.evaluate_classifier(xgb, X_test, y_test, feature_names, 'top3')
            xgb_path = self.save_model(xgb, 'xgboost', 'top3', xgb_metrics)
            results['xgboost'] = {'model': xgb, 'metrics': xgb_metrics, 'path': xgb_path}
        except Exception as e:
            logger.error("xgboost_training_failed", target='top3', error=str(e))
        
        return results
    
    def train_points_models(self, X_train: np.ndarray, X_test: np.ndarray, y_train: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        
        results = {}
        
        lr = self.train_linear_regression(X_train, y_train)
        lr_metrics = self.evaluate_regressor(lr, X_test, y_test)
        lr_path = self.save_model(lr, 'linear_regression', 'points', lr_metrics)
        results['linear_regression'] = {'model': lr, 'metrics': lr_metrics, 'path': lr_path}
        
        rf = self.train_random_forest_regressor(X_train, y_train)
        rf_metrics = self.evaluate_regressor(rf, X_test, y_test)
        rf_path = self.save_model(rf, 'random_forest', 'points', rf_metrics)
        results['random_forest'] = {'model': rf, 'metrics': rf_metrics, 'path': rf_path}
        
        return results
    
    def train_all_models(self, years: List[int] = [2020, 2021, 2022, 2023, 2024, 2025]) -> Dict[str, Dict[str, Any]]:
        
        self.metrics.start()
        
        df = self.load_training_data(years)
        
        (X_train_winner, X_train_top3, X_train_points,
         X_test,
         y_train_winner, y_test_winner,
         y_train_top3, y_test_top3,
         y_train_points, y_test_points,
         feature_names) = self.prepare_features(df)
        
        results = {}
        
        logger.info("Training winner prediction models...")
        results['is_winner'] = self.train_winner_models(
            X_train_winner, X_test, y_train_winner, y_test_winner, feature_names
        )
        
        logger.info("Training top3 prediction models...")
        results['is_top3'] = self.train_top3_models(
            X_train_top3, X_test, y_train_top3, y_test_top3, feature_names
        )
        
        logger.info("Training points prediction models...")
        results['points'] = self.train_points_models(
            X_train_points, X_test, y_train_points, y_test_points
        )
        
        self.metrics.finalize()
        logger.info("training_pipeline_complete")
        
        return results