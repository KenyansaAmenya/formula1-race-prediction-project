import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from src.api.middleware import LoggingMiddleware, RateLimitMiddleware
from src.api.routes import auth, predictions, data, health
from src.services.prediction_service import PredictionService
from src.utils.config import get_config
from src.utils.db import get_db
from src.utils.logger import get_logger
from src.utils.security import get_current_user, rate_limit_dependency

logger = get_logger(__name__)

# Global service instances
prediction_service: Optional[PredictionService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
   
    # Startup
    logger.info("api_startup", environment=get_config().environment)
    
    global prediction_service
    try:
        prediction_service = PredictionService()
        logger.info("prediction_service_initialized")
    except Exception as e:
        logger.error("prediction_service_init_failed", error=str(e))
    
    yield
    
    # Shutdown
    logger.info("api_shutdown")
    get_db().close()


# Initialize FastAPI app
app = FastAPI(
    title="F1 Race Prediction API",
    description="Enterprise AI platform for Formula 1 analytics",
    version="1.0.0",
    docs_url="/docs" if get_config().environment != "production" else None,
    redoc_url="/redoc" if get_config().environment != "production" else None,
    lifespan=lifespan
)

# CORS configuration
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(predictions.router, prefix="/predict", tags=["Predictions"])
app.include_router(data.router, prefix="/data", tags=["Data"])
app.include_router(health.router, prefix="/health", tags=["Health"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc)
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred" if config.environment == "production" else str(exc)
        }
    )


@app.get("/")
async def root():
    return {
        "service": "F1 Race Prediction API",
        "version": "2.0.0",
        "status": "operational",
        "environment": config.environment
    }