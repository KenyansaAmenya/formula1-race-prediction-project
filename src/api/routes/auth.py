from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.utils.logger import get_logger
from src.utils.security import SecurityManager, get_current_user

logger = get_logger(__name__)
router = APIRouter()
security = SecurityManager()

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class RefreshRequest(BaseModel):
    refresh_token: str


# Demo user store (replace with database in production)
DEMO_USERS = {
    "analyst": {"password": "demo_password", "role": "analyst"},
    "admin": {"password": "admin_password", "role": "admin"}
}

#  Authenticate user and return JWT tokens.
@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
  
    user = DEMO_USERS.get(credentials.username)
    
    if not user or user["password"] != credentials.password:
        logger.warning("login_failed", username=credentials.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    access_token = security.create_access_token(
        user_id=credentials.username,
        role=user["role"]
    )
    refresh_token = security.create_refresh_token(credentials.username)
    
    logger.info("login_success", username=credentials.username, role=user["role"])
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=security.config.api.jwt.access_token_expire_minutes * 60
    )


@router.post("/refresh")
async def refresh_token(request: RefreshRequest):
    try:
        token_data = security.verify_token(request.refresh_token)
        
        if token_data.type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        new_access = security.create_access_token(
            user_id=token_data.sub,
            role=token_data.role
        )
        
        return {"access_token": new_access, "token_type": "bearer"}
        
    except Exception as e:
        logger.warning("token_refresh_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "role": current_user.role
    }