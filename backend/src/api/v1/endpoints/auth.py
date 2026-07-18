"""Auth API endpoints — login, register, user profile, account lifecycle.

Phase 17.7 — Hardened: No in-memory fallbacks, JWT-only, account lockout, audit logging.
"""

import hashlib
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, status, HTTPException, Response, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.config import settings
from src.services.security.auth import auth_service, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from src.services.security.audit import audit_logger
from src.core.exceptions import ConflictError, AuthenticationError
from src.observability.enterprise_logging import auth_log
from src.db.session import get_db
from src.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
_limiter = Limiter(key_func=get_remote_address)


# ── Request / Response models ───────────────────────────────────────

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, description="User email")
    password: str = Field(..., min_length=1, description="User password")


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., min_length=5, description="User email")
    password: str = Field(..., min_length=12, description="Password (min 12 chars, 1 upper, 1 lower, 1 digit, 1 special)")
    full_name: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class UserProfile(BaseModel):
    user_id: str
    email: str
    role: str = "User"
    full_name: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=12)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="Registered email address")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Reset token from email")
    new_password: str = Field(..., min_length=12)


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None


LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION_MINUTES = 15


def _safe_audit(action: str, resource: str, result: str, user_id: str | None = None, details: dict | str | None = None) -> None:
    """Log audit event without letting audit failures break auth responses."""
    try:
        audit_logger.log_event(action, resource, result, user_id=user_id, details=details)
    except Exception:
        logger.exception("Audit logging failed for action=%s user=%s", action, user_id)


# ── Password helpers ─────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except ImportError:
        import secrets
        salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return f"pbkdf2:sha256:100000${salt}${dk.hex()}"


def _verify_password(password: str, hashed: str) -> bool:
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        import bcrypt
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    if hashed.startswith("pbkdf2:sha256:"):
        _, algo, salt, dk_hex = hashed.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return dk.hex() == dk_hex
    # Legacy fallback: old format with shared salt from SECRET_KEY
    salt = settings.SECRET_KEY[:16].encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex() == hashed


def _validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")
    if not any(c.isupper() for c in password):
        raise HTTPException(status_code=400, detail="Password must contain an uppercase letter")
    if not any(c.islower() for c in password):
        raise HTTPException(status_code=400, detail="Password must contain a lowercase letter")
    if not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="Password must contain a digit")
    if not any(c in "!@#$%^&*()_+-=[]{}|;:',.<>?/`~" for c in password):
        raise HTTPException(status_code=400, detail="Password must contain a special character")


# ── Register ─────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
@_limiter.limit("5/minute")
async def register(req: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    _validate_password_strength(req.password)
    email = req.email.strip().lower()

    from src.db.repositories.user_repository import UserRepository
    repo = UserRepository(db)

    existing = await repo.get_by_email(email)
    if existing:
        raise ConflictError("Email already registered", error_code="EMAIL_EXISTS", details={"email": req.email})

    try:
        user = await repo.create(
            email=email,
            password_hash=_hash_password(req.password),
            full_name=req.full_name,
        )
    except IntegrityError as exc:
        await db.rollback()
        logger.info("Duplicate registration blocked by database constraint", extra={"operation": "user_register_duplicate"})
        raise ConflictError("Email already registered", error_code="EMAIL_EXISTS", details={"email": req.email}) from exc

    token_pair = auth_service.generate_token_pair(str(user.id), str(user.role) if hasattr(user, 'role') else "User")
    # Set access and refresh tokens as secure HttpOnly cookies to align client/server auth handling
    secure_cookie = not settings.DEBUG
    response.set_cookie(
        key="careeros_token",
        value=token_pair.access_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="careeros_refresh",
        value=token_pair.refresh_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )
    auth_log.log_event(operation="user_register", message="User registered", metadata={"user_id": str(user.id)})
    return token_pair


# ── Login (with lockout) ─────────────────────────────────────────────

@router.post("/login")
@_limiter.limit("10/minute")
async def login(req: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Authenticate and return token pair. Enforces account lockout."""
    email = req.email.strip().lower()

    from src.db.repositories.user_repository import UserRepository
    repo = UserRepository(db)

    user = await repo.get_by_email(email)
    if not user:
        _safe_audit("LOGIN_FAILURE", "auth", "failed", details={"email": email, "reason": "user_not_found"})
        raise AuthenticationError("Invalid email or password", error_code="INVALID_CREDENTIALS")

    if user.locked_until and user.locked_until > datetime.utcnow():
        _safe_audit("LOGIN_BLOCKED", "auth", "failed", user_id=str(user.id), details={"reason": "account_locked"})
        raise HTTPException(status_code=423, detail="Account locked. Try again later.")

    if not _verify_password(req.password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            _safe_audit("ACCOUNT_LOCKED", "auth", "failed", user_id=str(user.id))
        await db.commit()
        _safe_audit("LOGIN_FAILURE", "auth", "failed", user_id=str(user.id), details={"reason": "bad_password"})
        raise AuthenticationError("Invalid email or password", error_code="INVALID_CREDENTIALS")

    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    token_pair = auth_service.generate_token_pair(str(user.id), str(user.role) if hasattr(user, 'role') else "User")
    # Set secure HttpOnly cookies for tokens
    secure_cookie = not settings.DEBUG
    response.set_cookie(
        key="careeros_token",
        value=token_pair.access_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="careeros_refresh",
        value=token_pair.refresh_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )
    auth_log.log_event(operation="user_login", message="User logged in", metadata={"user_id": str(user.id)})
    _safe_audit("LOGIN_SUCCESS", "auth", "success", user_id=str(user.id))
    return token_pair


# ── Profile ──────────────────────────────────────────────────────────

@router.get("/me")
async def get_current_user_profile(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return authenticated user profile."""
    from src.db.repositories.user_repository import UserRepository
    repo = UserRepository(db)

    db_user = await repo.get_by_id(user["sub"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(
        user_id=str(db_user.id),
        email=db_user.email,
        role=str(db_user.role) if hasattr(db_user, 'role') else "User",
        full_name=db_user.full_name,
    )


@router.patch("/me")
async def update_profile(req: UpdateProfileRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Update current user profile."""
    from src.db.repositories.user_repository import UserRepository
    repo = UserRepository(db)

    db_user = await repo.get_by_id(user["sub"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    updates = {}
    if req.full_name is not None:
        updates["full_name"] = req.full_name
    if req.email is not None:
        normalized = req.email.strip().lower()
        existing = await repo.get_by_email(normalized)
        if existing and str(existing.id) != str(db_user.id):
            raise ConflictError("Email already in use")
        updates["email"] = normalized

    if updates:
        from sqlalchemy import update
        await db.execute(update(type(db_user)).where(type(db_user).id == db_user.id).values(**updates))
        await db.commit()
        audit_logger.log_event("PROFILE_UPDATED", "auth", "success", user_id=str(db_user.id))

    return UserProfile(user_id=str(db_user.id), email=updates.get("email", db_user.email), role=str(db_user.role) if hasattr(db_user, 'role') else "User", full_name=updates.get("full_name", db_user.full_name))


# ── Change Password ──────────────────────────────────────────────────

@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Change user password."""
    _validate_password_strength(req.new_password)

    from src.db.repositories.user_repository import UserRepository
    repo = UserRepository(db)

    db_user = await repo.get_by_id(user["sub"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if not _verify_password(req.old_password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    db_user.password_hash = _hash_password(req.new_password)
    await db.commit()

    auth_service.revoke_all_tokens(str(db_user.id))
    audit_logger.log_event("PASSWORD_CHANGED", "auth", "success", user_id=str(db_user.id))
    return {"status": "password_changed"}


# ── Forgot Password ──────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Generate password reset token."""
    email = req.email.strip().lower()

    from src.db.repositories.user_repository import UserRepository
    repo = UserRepository(db)

    user = await repo.get_by_email(email)
    if user:
        reset_token = auth_service.create_reset_token(str(user.id))
        audit_logger.log_event("PASSWORD_RESET_REQUESTED", "auth", "success", user_id=str(user.id))
        return {"status": "reset_token_generated", "reset_token": reset_token if settings.DEBUG else "sent_via_email"}

    return {"status": "reset_token_generated"}


# ── Reset Password ───────────────────────────────────────────────────

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using reset token."""
    _validate_password_strength(req.new_password)

    from src.db.repositories.user_repository import UserRepository
    repo = UserRepository(db)

    try:
        payload = auth_service.decode_token(req.token)
        if payload.type != "reset":
            raise HTTPException(status_code=400, detail="Invalid reset token")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    db_user = await repo.get_by_id(payload.sub)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.password_hash = _hash_password(req.new_password)
    db_user.failed_login_attempts = 0
    db_user.locked_until = None
    await db.commit()

    auth_service.revoke_all_tokens(payload.sub)
    audit_logger.log_event("PASSWORD_RESET", "auth", "success", user_id=payload.sub)
    return {"status": "password_reset"}


# ── Logout ───────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    """Revoke current user tokens."""
    auth_service.revoke_all_tokens(user["sub"])
    audit_logger.log_event("LOGOUT", "auth", "success", user_id=user["sub"])
    # Remove cookies on logout
    response.delete_cookie("careeros_token", path="/")
    response.delete_cookie("careeros_refresh", path="/")
    return {"status": "logged_out"}


# ── Delete Account ───────────────────────────────────────────────────

@router.delete("/account")
async def delete_account(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Soft-delete user account."""
    from src.db.repositories.user_repository import UserRepository
    repo = UserRepository(db)

    db_user = await repo.get_by_id(user["sub"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.deleted_at = datetime.utcnow()
    await db.commit()

    auth_service.revoke_all_tokens(str(db_user.id))
    audit_logger.log_event("ACCOUNT_DELETED", "auth", "success", user_id=str(db_user.id))
    return {"status": "account_deleted"}
