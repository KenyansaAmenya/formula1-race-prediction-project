import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel

from src.utils.config import AppConfig, get_config
from src.utils.db import get_db
from src.utils.logger import PipelineMetrics, get_logger

logger = get_logger(__name__)

class PredictionRequest(BaseModel):
    race_id: int
    driver_id: int
    model_type: str = "xgboost"  # logistic_regression, random_forest, xgboost
    target: str = "is_winner"    # is_winner, is_top3


class PredictionResponse(BaseModel):
    race_id: int
    driver_id: int
    driver_name: str
    model_type: str
    target: str
    prediction: int
    probability: float
    confidence_tier: str  # 'high', 'medium', 'low'
    feature_contributions: Dict[str, float]
    top_features: List[Dict[str, Any]]
    timestamp: str


class PredictionService:
    
    # Feature columns (must match training)
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
    
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or get_config()
        self.db = get_db()
        self.metrics = PipelineMetrics("prediction_service")
        
        self.model_dir = Path(self.config.ml.model_dir)
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.feature_names: List[str] = []
        
        self._load_latest_models()
    
    def _load_latest_models(self) -> None:
        if not self.model_dir.exists():
            logger.warning(f"Model directory not found: {self.model_dir}")
            return
        
        # Group files by model type and target
        model_files = {}
        for model_file in self.model_dir.glob("*.pkl"):
            name_parts = model_file.stem.split('_')
            
            # Handle different naming conventions
            if len(name_parts) >= 2:
                model_type = name_parts[0]
                target = name_parts[1]
                
                # Skip if target contains numbers (timestamp part)
                if target not in ['is_winner', 'is_top3', 'winner', 'top3', 'points']:
                    # Try alternative parsing: modeltype_target_timestamp
                    if len(name_parts) >= 3:
                        model_type = name_parts[0]
                        target = name_parts[1]
                        if target == 'is':
                            # Format: xgboost_is_winner_timestamp
                            target = name_parts[2] if len(name_parts) > 2 else target
                            model_type = name_parts[0]
                
                # Normalize target names
                if target == 'winner':
                    target = 'is_winner'
                elif target == 'top3':
                    target = 'is_top3'
                
                key = f"{model_type}_{target}"
                
                # Keep the most recent file for each key
                if key not in model_files or model_file.stat().st_mtime > model_files[key].stat().st_mtime:
                    model_files[key] = model_file
        
        # Load the models
        for key, model_file in model_files.items():
            try:
                with open(model_file, 'rb') as f:
                    bundle = pickle.load(f)
                
                if isinstance(bundle, dict) and 'model' in bundle:
                    model_obj = bundle['model']
                    if hasattr(model_obj, 'predict'):
                        self.models[key] = model_obj
                        
                        # Store scaler if present
                        if 'scaler' in bundle:
                            self.scalers[key] = bundle['scaler']
                        
                        # Store feature names from first model
                        if not self.feature_names and 'feature_names' in bundle:
                            self.feature_names = bundle['feature_names']
                        
                        logger.info(f"Loaded model: {key} from {model_file.name}")
                    else:
                        logger.warning(f"Invalid model for {key}: no predict method")
                else:
                    logger.warning(f"Invalid bundle for {key}: {type(bundle)}")
                    
            except Exception as e:
                logger.error(f"Failed to load model {model_file}: {e}")
        
        if not self.feature_names:
            self.feature_names = self.FEATURE_COLS
        
        valid_models = len([k for k, v in self.models.items() if hasattr(v, 'predict')])
        logger.info(f"Loaded {valid_models} valid models")
    
    def get_driver_features(
        self,
        race_id: int,
        driver_id: int
    ) -> Optional[pd.DataFrame]:
        # Convert numpy types to Python native types
        race_id = int(race_id) if hasattr(race_id, 'item') else race_id
        driver_id = int(driver_id) if hasattr(driver_id, 'item') else driver_id
        
        query = """
        SELECT * FROM driver_race_features
        WHERE race_id = :race_id AND driver_id = :driver_id
        """
        df = self.db.execute_dataframe(query, {
            "race_id": race_id,
            "driver_id": driver_id
        })
        
        if df.empty:
            logger.warning(
                "features_not_found",
                race_id=race_id,
                driver_id=driver_id
            )
            return None
        
        return df
    
    def get_driver_name(self, driver_id: int) -> str:
        driver_id = int(driver_id) if hasattr(driver_id, 'item') else driver_id
        query = "SELECT forename, surname FROM drivers WHERE driver_id = :driver_id"
        result = self.db.execute_query(query, {"driver_id": driver_id})
        if result:
            return f"{result[0]['forename']} {result[0]['surname']}"
        return "Unknown"
    
    def preprocess(
        self,
        features_df: pd.DataFrame,
        model_key: str
    ) -> np.ndarray:
        # Select only features used during training
        available_features = [c for c in self.feature_names if c in features_df.columns]
        X = features_df[available_features].copy()
        
        # Handle missing values
        X = X.fillna(0)
        
        # Apply scaler
        scaler = self.scalers.get(model_key)
        if scaler:
            X_scaled = scaler.transform(X)
        else:
            X_scaled = X.values
        
        return X_scaled
    
    def _calculate_feature_contributions(
        self,
        model: Any,
        X: np.ndarray,
        features_df: pd.DataFrame
    ) -> Dict[str, float]:
        contributions = {}
        
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
        elif hasattr(model, 'coef_'):
            importances = np.abs(model.coef_[0])
        else:
            return {}
        
        available_features = [c for c in self.feature_names if c in features_df.columns]
        
        for i, feature in enumerate(available_features):
            if i < len(importances):
                contributions[feature] = round(
                    float(importances[i] * X[i]), 6
                )
        
        return contributions
    
    def _get_top_features(
        self,
        contributions: Dict[str, float],
        n: int = 5
    ) -> List[Dict[str, Any]]:
        sorted_contrib = sorted(
            contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:n]
        
        return [
            {"feature": k, "contribution": round(v, 6)}
            for k, v in sorted_contrib
        ]
    
    def predict(
        self,
        race_id: int,
        driver_id: int,
        model_type: str = "xgboost",
        target: str = "is_winner"
    ) -> PredictionResponse:
        # Convert to native Python types
        race_id = int(race_id) if hasattr(race_id, 'item') else race_id
        driver_id = int(driver_id) if hasattr(driver_id, 'item') else driver_id
        
        self.metrics.start()
        
        model_key = f"{model_type}_{target}"
        
        if model_key not in self.models:
            raise ValueError(f"Model {model_key} not loaded")
        
        # Fetch features
        features_df = self.get_driver_features(race_id, driver_id)
        if features_df is None:
            raise ValueError(f"No features found for race {race_id}, driver {driver_id}")
        
        # Preprocess
        X = self.preprocess(features_df, model_key)
        
        # Predict
        model = self.models[model_key]
        prediction = int(model.predict(X)[0])
        
        probability = 0.5
        if hasattr(model, 'predict_proba'):
            probability = float(model.predict_proba(X)[0][1])
        
        # Confidence tier
        if probability > 0.8 or probability < 0.2:
            confidence = 'high'
        elif probability > 0.65 or probability < 0.35:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        # Feature contributions
        feature_contributions = self._calculate_feature_contributions(
            model, X[0], features_df
        )
        
        # Get driver name
        driver_name = self.get_driver_name(driver_id)
        
        self.metrics.record_success()
        
        return PredictionResponse(
            race_id=race_id,
            driver_id=driver_id,
            driver_name=driver_name,
            model_type=model_type,
            target=target,
            prediction=prediction,
            probability=round(probability, 4),
            confidence_tier=confidence,
            feature_contributions=feature_contributions,
            top_features=self._get_top_features(feature_contributions, 5),
            timestamp=pd.Timestamp.now(tz='UTC').isoformat()
        )
    
    def predict_race(
        self,
        race_id: int,
        model_type: str = "xgboost",
        target: str = "is_winner"
    ) -> List[PredictionResponse]:
        # Convert race_id to native int
        race_id = int(race_id) if hasattr(race_id, 'item') else race_id
        
        # Get all drivers in race
        query = """
        SELECT DISTINCT driver_id
        FROM results
        WHERE race_id = :race_id
        """
        drivers = self.db.execute_dataframe(query, {"race_id": race_id})
        
        predictions = []
        for _, row in drivers.iterrows():
            # Convert driver_id to native int
            driver_id = int(row['driver_id']) if hasattr(row['driver_id'], 'item') else row['driver_id']
            
            try:
                pred = self.predict(
                    race_id=race_id,
                    driver_id=driver_id,
                    model_type=model_type,
                    target=target
                )
                predictions.append(pred)
            except Exception as e:
                logger.error(
                    "prediction_failed",
                    race_id=race_id,
                    driver_id=driver_id,
                    error=str(e)
                )
        
        # Sort by probability (descending for winners)
        predictions.sort(key=lambda x: x.probability, reverse=True)
        
        return predictions