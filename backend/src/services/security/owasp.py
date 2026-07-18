import os
from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.services.security.auth import auth_service, Role
from src.services.security.rate_limit import rate_limiter, RATE_LIMITS
from src.services.security.audit import audit_logger

security_scheme = HTTPBearer()

def apply_security_headers(response: JSONResponse):
    """A05 Security Misconfiguration - Apply secure headers"""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    """Extracts JWT token and validates signature, expiration, and checks revocation"""
    try:
        # Check if environment disables auth for initial tests
        if os.getenv("MOCK_AUTH") == "true":
            return {"sub": "mock_user", "role": Role.USER}
            
        payload = auth_service.decode_token(credentials.credentials)
        if payload.type != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return {"sub": payload.sub, "role": payload.role}
    except Exception as e:
        audit_logger.log_event("AUTH_FAILED", "api", "failed", details=str(e))
        raise HTTPException(status_code=401, detail=str(e))

class RoleChecker:
    def __init__(self, required_role: Role):
        self.required_role = required_role

    def __call__(self, user: dict = Depends(get_current_user)):
        if os.getenv("MOCK_AUTH") == "true":
            return user
            
        if not auth_service.check_rbac(self.required_role, user["role"]):
            audit_logger.log_event("RBAC_VIOLATION", "api", "failed", user_id=user["sub"])
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return user

class RateLimitChecker:
    def __init__(self, limit_type: str):
        self.limit_type = limit_type
        
    async def __call__(self, request: Request, user: dict = Depends(get_current_user)):
        if os.getenv("MOCK_REDIS") == "true":
            return True
            
        settings = RATE_LIMITS.get(self.limit_type, {"limit": 100, "window": 60})
        key = f"rate_limit:{self.limit_type}:{user['sub']}"
        
        is_allowed, _ = await rate_limiter.check_rate_limit(key, settings["limit"], settings["window"])
        if not is_allowed:
            audit_logger.log_event("RATE_LIMIT_EXCEEDED", self.limit_type, "failed", user_id=user["sub"])
            raise HTTPException(status_code=429, detail="Too many requests")
        return True
