from pydantic import BaseModel, ConfigDict
from typing import Any, Optional
from enum import Enum

class Role(str, Enum):
    ADMIN = "Admin"
    USER = "User"
    RECRUITER = "Recruiter"
    MODERATOR = "Moderator"

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenPayload(BaseModel):
    sub: str
    role: Role
    exp: float
    iat: float
    jti: str
    type: str

class AuditLog(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    user_id: Optional[str]
    action: str
    resource: str
    timestamp: float
    ip_address: Optional[str]
    user_agent: Optional[str]
    result: str
    details: dict[str, Any] | str | None = None
