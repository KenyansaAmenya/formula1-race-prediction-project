from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBearer
from pydantic import BaseModel

from src.utils.config import get_config
from src.utils.logger import get_logger
from src.utils.security import security_manager, get_current_user, UserContext

logger = get_logger(__name__)
router = APIRouter()
config = get_config()

# OAuth2 scheme for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
security = HTTPBearer(auto_error=False)

def get_jwt_expire_minutes():
    if hasattr(config, 'api'):
        if hasattr(config.api, 'jwt'):
            return config.api.jwt.access_token_expire_minutes
        elif isinstance(config.api, dict):
            jwt_config = config.api.get('jwt', {})
            return jwt_config.get('access_token_expire_minutes', 30)
    return 30

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    
    # Simple authentication (in production, check against database)
    if request.username == "admin" and request.password == "admin":
        user_id = "admin"
        role = "admin"
    elif request.username == "user" and request.password == "user":
        user_id = "user"
        role = "user"
    else:
        # Accept any credentials for development (remove in production)
        logger.warning("accepting any credentials for development")
        user_id = request.username
        role = "user"
    
    # Create tokens
    access_token = security_manager.create_access_token(
        user_id=user_id,
        role=role
    )
    refresh_token = security_manager.create_refresh_token(user_id=user_id)
    
    expires_in = get_jwt_expire_minutes() * 60
    
    logger.info("login_success", username=request.username, role=role)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in
    )

@router.post("/refresh")
async def refresh_token(refresh_token: str):
    token_data = security_manager.verify_token(refresh_token)
    
    if token_data.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    new_access_token = security_manager.create_access_token(
        user_id=token_data.sub,
        role=token_data.role
    )
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }

@router.get("/me")
async def get_current_user_info(current_user: UserContext = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "role": current_user.role,
        "authenticated": True
    }

@router.post("/logout")
async def logout(current_user: UserContext = Depends(get_current_user)):
    logger.info("logout", user_id=current_user.user_id)
    return {"message": "Successfully logged out"}
