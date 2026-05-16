from fastapi import APIRouter

from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/")
async def health_check():
    return {
        "status": "healthy",
        "service": "f1-prediction-api",
        "version": "2.0.0"
    }


@router.get("/live")
# Kubernetes liveness probe
async def liveness():
    return {"status": "alive"}


@router.get("/ready")
# Kubernetes readiness probe
async def readiness():
    try:
        db = get_db()
        if db.test_connection():
            return {
                "status": "ready",
                "database": "connected"
            }
        else:
            return {
                "status": "not_ready",
                "database": "disconnected"
            }
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        return {
            "status": "not_ready",
            "database": "error"
        }


@router.get("/metrics")
# Prometheus metrics
async def metrics():
    return {
        "requests_total": 0,
        "requests_duration_seconds": 0,
        "predictions_total": 0,
        "model_load_errors_total": 0
    }