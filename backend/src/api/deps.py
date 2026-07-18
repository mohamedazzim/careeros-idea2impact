"""
Canonical authentication and authorization dependencies for all API endpoints.

Provides single source of truth for:
- JWT validation (get_current_user)
- Role-based access control (require_role)
- Audit logging integration

All routers MUST use these dependencies instead of:
- demo_user defaults
- user_id query parameters
- Raw JWT decode
- Custom get_current_user implementations
"""
import logging
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.services.security.auth import auth_service
from src.services.security.audit import audit_logger

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> dict:
    """
    Canonical JWT authentication dependency.
    Returns {"sub": user_id, "role": role} for all authenticated requests.
    Raises 401 if token is missing, expired, invalid, or revoked.
    """
    token = None
    if credentials:
        token = credentials.credentials
    else:
        # Fallback to cookie (used by Next middleware and SSR flows)
        token = request.cookies.get("careeros_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = auth_service.decode_token(token)
        if payload.type != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return {"sub": payload.sub, "role": payload.role}
    except HTTPException:
        raise
    except Exception as e:
        audit_logger.log_event("AUTH_FAILED", "api", "failed", details=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(user: dict = Depends(get_current_user)) -> str:
    """Convenience dependency that returns just the user_id (sub)."""
    return user["sub"]


def require_role(*allowed_roles: str) -> Callable:
    """
    Role-based access control dependency factory.
    Usage: @router.post("/admin")(dependencies=[Depends(require_role("Admin"))])
    """

    async def role_checker(user: dict = Depends(get_current_user)):
        user_role = user.get("role", "User")
        if user_role not in allowed_roles:
            audit_logger.log_event(
                "RBAC_VIOLATION", "api", "failed",
                user_id=user["sub"],
                details={"user_role": user_role, "required_roles": list(allowed_roles)},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return role_checker
