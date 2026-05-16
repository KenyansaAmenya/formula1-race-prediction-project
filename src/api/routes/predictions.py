from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.main import prediction_service
from src.services.prediction_service import PredictionResponse
from src.utils.logger import get_logger
from src.utils.security import UserContext, get_current_user, require_role

logger = get_logger(__name__)
router = APIRouter()

@router.post("/driver", response_model=PredictionResponse)
async def predict_driver(
    race_id: int = Query(..., description="Race identifier"),
    driver_id: int = Query(..., description="Driver identifier"),
    model_type: str = Query("xgboost", enum=["logistic_regression", "random_forest", "xgboost"]),
    target: str = Query("is_winner", enum=["is_winner", "is_top3"]),
    current_user: UserContext = Depends(get_current_user)
):
   
    if not prediction_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction service not initialized"
        )
    
    try:
        result = prediction_service.predict(
            race_id=race_id,
            driver_id=driver_id,
            model_type=model_type,
            target=target
        )
        
        logger.info(
            "prediction_generated",
            race_id=race_id,
            driver_id=driver_id,
            user=current_user.user_id,
            probability=result.probability
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("prediction_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed"
        )


@router.get("/race/{race_id}", response_model=List[PredictionResponse])
async def predict_race(
    race_id: int,
    model_type: str = Query("xgboost", enum=["logistic_regression", "random_forest", "xgboost"]),
    target: str = Query("is_winner", enum=["is_winner", "is_top3"]),
    current_user: UserContext = Depends(get_current_user)
):
    
    if not prediction_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction service not initialized"
        )
    
    try:
        results = prediction_service.predict_race(
            race_id=race_id,
            model_type=model_type,
            target=target
        )
        
        logger.info(
            "race_predictions_generated",
            race_id=race_id,
            predictions=len(results),
            user=current_user.user_id
        )
        
        return results
        
    except Exception as e:
        logger.error("race_prediction_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Race prediction failed"
        )


@router.get("/leaderboard/{race_id}")
async def get_leaderboard(
    race_id: int,
    current_user: UserContext = Depends(get_current_user)
):
    
    predictions = await predict_race(
        race_id=race_id,
        model_type="xgboost",
        target="is_winner",
        current_user=current_user
    )
    
    return {
        "race_id": race_id,
        "predictions": [
            {
                "position": i + 1,
                "driver_id": p.driver_id,
                "driver_name": p.driver_name,
                "win_probability": p.probability,
                "confidence": p.confidence_tier
            }
            for i, p in enumerate(predictions[:3])
        ]
    }