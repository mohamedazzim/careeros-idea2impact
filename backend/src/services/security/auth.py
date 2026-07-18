import asyncio
import logging
import jwt
import time
import os
import uuid
from typing import Optional
from src.schemas.security import Token, TokenPayload, Role
from src.services.security.audit import audit_logger
from src.core.config import settings

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET") or settings.SECRET_KEY
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


class AuthService:
    def __init__(self):
        # In-memory revocation list for testing
        self.revoked_tokens = set()
        
    def create_access_token(self, sub: str, role: Role) -> str:
        payload = {
            "sub": sub,
            "role": role,
            "exp": time.time() + (ACCESS_TOKEN_EXPIRE_MINUTES * 60),
            "iat": time.time(),
            "jti": str(uuid.uuid4()),
            "type": "access",
            "iss": "careeros-auth",
            "aud": "careeros-ai"
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def create_refresh_token(self, sub: str) -> str:
        payload = {
            "sub": sub,
            "role": Role.USER, # Refresh tokens shouldn't trust role deeply in rotation, but we set a default
            "exp": time.time() + (REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60),
            "iat": time.time(),
            "jti": str(uuid.uuid4()),
            "type": "refresh",
            "iss": "careeros-auth",
            "aud": "careeros-ai"
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def generate_token_pair(self, sub: str, role: Role = Role.USER) -> Token:
        # Clear any previous revocation for this user (they just authenticated)
        self.revoked_tokens.discard(sub)
        
        access = self.create_access_token(sub, role)
        refresh = self.create_refresh_token(sub)
        
        audit_logger.log_event("LOGIN", "auth", "success", user_id=sub)
        
        return Token(
            access_token=access,
            refresh_token=refresh,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    def decode_token(self, token: str) -> Optional[TokenPayload]:
        if token in self.revoked_tokens:
            raise ValueError("Token has been revoked")
            
        try:
            payload = jwt.decode(
                token, 
                JWT_SECRET, 
                algorithms=[JWT_ALGORITHM], 
                audience="careeros-ai",
                issuer="careeros-auth"
            )
            token_payload = TokenPayload(**payload)
            
            # Check in-memory user-level revocation
            if token_payload.sub in self.revoked_tokens:
                raise ValueError("Token has been revoked (user-level)")
                
            return token_payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")

    def rotate_session(self, old_refresh_token: str) -> Token:
        """
        Refresh token endpoint logic. Validates old refresh token, invalidates it, issues new pair.
        Prevents replay by revocation.
        """
        payload = self.decode_token(old_refresh_token)
        if payload.type != "refresh":
            raise ValueError("Invalid token type")
            
        # Revoke old refresh token (replay protection)
        self.revoke_token(old_refresh_token, payload.jti)
        
        audit_logger.log_event("TOKEN_ROTATION", "auth", "success", user_id=payload.sub)
        
        return self.generate_token_pair(payload.sub, payload.role)

    def revoke_token(self, token: str, jti: str):
        self.revoked_tokens.add(token)
        # Store JTI in Redis for distributed invalidation usually, mock handles via set

    def revoke_all_tokens(self, sub: str):
        """Revoke all tokens for a user. Stores in in-memory set and tries Redis for persistence."""
        self.revoked_tokens.add(sub)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create async task for Redis persistence
                loop.create_task(self._redis_revoke(sub))
            else:
                asyncio.ensure_future(self._redis_revoke(sub))
        except Exception:
            pass  # Redis is best-effort

    async def _redis_revoke(self, sub: str):
        """Persist user revocation timestamp to Redis."""
        try:
            from src.db.redis import redis_client
            revocation_key = f"revoked_user:{sub}"
            ts = str(time.time())
            await redis_client.setex(revocation_key, REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60, ts)
            logger.info("Revoked all tokens for user %s in Redis", sub)
        except Exception as e:
            logger.warning("Redis revocation skipped for user %s: %s", sub, e)

    def create_reset_token(self, sub: str, role: Role = Role.USER) -> str:
        """Create a short-lived password reset token."""
        payload = {
            "sub": sub,
            "role": role,
            "exp": time.time() + (15 * 60),
            "iat": time.time(),
            "jti": str(uuid.uuid4()),
            "type": "reset",
            "iss": "careeros-auth",
            "aud": "careeros-ai"
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
    def check_rbac(self, required_role: Role, user_role: str) -> bool:
        """
        RBAC logic. 
        Admin > Recruiter > Moderator > User
        For simplicity, Admin can do everything, others only match exact.
        """
        if user_role == Role.ADMIN:
            return True
        return user_role == required_role

auth_service = AuthService()
