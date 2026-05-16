import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

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
        targets = ['is_winner', 'is_top3']
        model_types = ['logistic_regression', 'random_forest', 'xgboost']
        
        for target in targets:
            for model_type in model_types:
                key = f"{model_type}_{target}"
                
                # Find latest model file
                pattern = f"{model_type}_{target}_*.pkl"
                files = sorted(self.model_dir.glob(pattern))
                
                if files:
                    latest = files[-1]
                    try:
                        with open(latest, 'rb') as f:
                            bundle = pickle.load(f)
                        
                        self.models[key] = bundle['model']
                        self.scalers[key] = bundle['scaler']
                        self.feature_names = bundle.get('feature_names', [])
                        
                        logger.info(
                            "model_loaded",
                            model_type=model_type,
                            target=target,
                            path=str(latest)
                        )
                    except Exception as e:
                        logger.error(
                            "model_load_failed",
                            model_type=model_type,
                            target=target,
                            error=str(e)
                        )
    
    def get_driver_features(
        self,
        race_id: int,
        driver_id: int
    ) -> Optional[pd.DataFrame]:
        
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
    
    def preprocess(
        self,
        features_df: pd.DataFrame,
        model_key: str
    ) -> np.ndarray:
        # Select only features used during training
        available_features = [c for c in self.feature_names if c in features_df.columns]
        X = features_df[available_features].fillna(0)
        
        # Apply scaler
        scaler = self.scalers.get(model_key)
        if scaler:
            X_scaled = scaler.transform(X)
        else:
            X_scaled = X.values
        
        return X_scaled
    
    # Generate prediction for a driver in a race
    def predict(
        self,
        race_id: int,
        driver_id: int,
        model_type: str = "xgboost",
        target: str = "is_winner"
    ) -> PredictionResponse:
    
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
        
        # Feature contributions (simplified SHAP-like)
        feature_contributions = self._calculate_feature_contributions(
            model, X[0], features_df
        )
        
        # Get driver name
        driver_query = "SELECT forename, surname FROM drivers WHERE driver_id = :driver_id"
        driver_result = self.db.execute_query(driver_query, {"driver_id": driver_id})
        driver_name = (
            f"{driver_result[0]['forename']} {driver_result[0]['surname']}"
            if driver_result else "Unknown"
        )
        
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
    
    # Generate predictions for all drivers in a race
    def predict_race(
        self,
        race_id: int,
        model_type: str = "xgboost",
        target: str = "is_winner"
    ) -> List[PredictionResponse]:
        # Get all drivers in race
        query = """
        SELECT DISTINCT driver_id
        FROM results
        WHERE race_id = :race_id
        """
        drivers = self.db.execute_dataframe(query, {"race_id": race_id})
        
        predictions = []
        for _, row in drivers.iterrows():
            try:
                pred = self.predict(
                    race_id=race_id,
                    driver_id=row['driver_id'],
                    model_type=model_type,
                    target=target
                )
                predictions.append(pred)
            except Exception as e:
                logger.error(
                    "prediction_failed",
                    race_id=race_id,
                    driver_id=row['driver_id'],
                    error=str(e)
                )
        
        # Sort by probability (descending for winners)
        predictions.sort(key=lambda x: x.probability, reverse=True)
        
        return predictions