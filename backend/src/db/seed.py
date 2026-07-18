"""Startup seed logic — creates default admin user if no users exist."""

import hashlib
import os

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.user_repository import UserRepository
from src.models.user import User
from src.schemas.security import Role
from src.core.config import settings
from src.observability.enterprise_logging import auth_log

def _hash_password(password: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except ImportError:
        salt = settings.SECRET_KEY[:16].encode("utf-8")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return dk.hex()


async def seed_default_user(db: AsyncSession) -> None:
    """Create an explicitly configured development user. Never called at startup."""
    email = os.getenv("SEED_ADMIN_EMAIL")
    password = os.getenv("SEED_ADMIN_PASSWORD")
    name = os.getenv("SEED_ADMIN_NAME", "CareerOS Administrator")
    if not email or not password:
        raise RuntimeError("SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD are required")

    count_result = await db.execute(select(func.count()).select_from(User))
    user_count = count_result.scalar()

    if user_count > 0:
        return

    repo = UserRepository(db)
    existing = await repo.get_by_email(email)
    if existing:
        return

    # Seed role from environment or default to non-admin User
    seed_role_str = os.getenv("SEED_ADMIN_ROLE", "User")
    try:
        seed_role = Role(seed_role_str)
    except ValueError:
        seed_role = Role.USER

    password_hash = _hash_password(password)
    user = await repo.create(
        email=email,
        password_hash=password_hash,
        full_name=name,
        role=seed_role,
    )
    auth_log.log_event(
        operation="seed_default_user",
        message="Default admin user created",
        metadata={"user_id": str(user.id), "email": email},
    )
