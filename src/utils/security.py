import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, OAuth2PasswordBearer
from pydantic import BaseModel

from src.utils.config import get_config
from src.utils.logger import SensitiveDataMasker, get_logger

logger = get_logger(__name__)

# Security schemes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

# JWT token payload structure
class TokenPayload(BaseModel):
    sub: str                         # subject (user_id)
    exp: datetime
    iat: datetime
    type: str                        # 'access' or 'refresh'
    role: str = "user"               # 'user', 'analyst', 'admin'

# Authenticated user context
class UserContext(BaseModel):
    user_id: str
    role: str
    api_key: Optional[str] = None

class SecurityManager:
    
    def __init__(self):
        self.config = get_config()
        
        # Helper function to get nested config values
        def get_nested_config(*keys, default=None):
            """Get value from config regardless of dict or object structure"""
            current = self.config
            for key in keys:
                if hasattr(current, key):
                    current = getattr(current, key)
                elif isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current
        
        # Get JWT config values
        self.secret_key = get_nested_config('api', 'jwt', 'secret_key')
        if not self.secret_key:
            # Fallback to environment variable
            import os
            self.secret_key = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')
            logger.warning("Using fallback JWT secret key from environment")
        
        self.algorithm = get_nested_config('api', 'jwt', 'algorithm', default='HS256')
        self.access_expire_minutes = get_nested_config('api', 'jwt', 'access_token_expire_minutes', default=30)
        self.refresh_expire_days = get_nested_config('api', 'jwt', 'refresh_token_expire_days', default=7)
        
        self.access_expire = timedelta(minutes=self.access_expire_minutes)
        self.refresh_expire = timedelta(days=self.refresh_expire_days)
        
        # Get API key header
        self.api_key_header_value = get_nested_config('api', 'api_key_header', default='X-API-Key')
        
        logger.info("SecurityManager initialized")
    
    def create_access_token(
        self,
        user_id: str,
        role: str = "user",
        extra_claims: Optional[Dict] = None
    ) -> str:

        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "exp": now + self.access_expire,
            "iat": now,
            "type": "access",
            "role": role,
            **(extra_claims or {})
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info("access_token_created", user_id=user_id, role=role)
        return token
    
    def create_refresh_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "exp": now + self.refresh_expire,
            "iat": now,
            "type": "refresh"
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info("refresh_token_created", user_id=user_id)
        return token
    
    def verify_token(self, token: str) -> TokenPayload:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            token_data = TokenPayload(**payload)
            
            # Check expiration explicitly
            if datetime.now(timezone.utc) > token_data.exp:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            return token_data
            
        except jwt.ExpiredSignatureError:
            logger.warning("token_expired", token_preview=token[:20])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except jwt.InvalidTokenError as e:
            logger.warning("invalid_token", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    def verify_api_key(self, api_key: str) -> bool:
        # Get expected API key from config
        def get_config_value():
            if hasattr(self.config.api, 'api_key'):
                return self.config.api.api_key
            elif isinstance(self.config.api, dict):
                return self.config.api.get('api_key', '')
            return ''
        
        expected = get_config_value()
        
        if not expected:
            # No API key configured - allow for development
            logger.warning("No API key configured, accepting any key")
            return True
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(
            hashlib.sha256(api_key.encode()).hexdigest(),
            hashlib.sha256(expected.encode()).hexdigest()
        )
    
    def generate_api_key(self) -> str:
        return secrets.token_urlsafe(32)

# Helper function to get config value safely
def get_config_value(config, *keys, default=None):
    """Safely get nested config value from dict or object"""
    current = config
    for key in keys:
        if hasattr(current, key):
            current = getattr(current, key)
        elif isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current

# Dependency injection functions
security_manager = SecurityManager()

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    api_key: Optional[str] = Security(api_key_header)
) -> UserContext:
    # Try API key first (service-to-service)
    if api_key:
        if security_manager.verify_api_key(api_key):
            return UserContext(user_id="service", role="service", api_key=api_key)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    # Fall back to JWT
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token_data = security_manager.verify_token(token)
    return UserContext(
        user_id=token_data.sub,
        role=token_data.role
    )

async def require_role(required_role: str):
    async def role_checker(user: UserContext = Depends(get_current_user)):
        role_hierarchy = {
            "user": 1,
            "analyst": 2,
            "admin": 3,
            "service": 3
        }
        
        user_level = role_hierarchy.get(user.role, 0)
        required_level = role_hierarchy.get(required_role, 3)
        
        if user_level < required_level:
            logger.warning(
                "insufficient_permissions",
                user_id=user.user_id,
                user_role=user.role,
                required=required_role
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role"
            )
        return user
    return role_checker

class RateLimiter:
    
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = {}
    
    # Check if request is within rate limit
    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - 60
        
        # Clean old requests
        if key in self.requests:
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if req_time > window_start
            ]
        else:
            self.requests[key] = []
        
        if len(self.requests[key]) >= self.requests_per_minute:
            return False
        
        self.requests[key].append(now)
        return True

rate_limiter = RateLimiter()

async def rate_limit_dependency(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    endpoint = request.url.path
    
    key = f"{client_ip}:{endpoint}"
    
    if not rate_limiter.is_allowed(key):
        logger.warning("rate_limit_exceeded", client=client_ip, endpoint=endpoint)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )