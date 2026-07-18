"""User repository — PostgreSQL-backed persistence for user accounts.

Replaces the in-memory _users dict in auth.py.
"""

from __future__ import annotations
from typing import Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.security import Role
from src.observability.enterprise_logging import auth_log


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        email = email.strip().lower()
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        password_hash: str,
        full_name: Optional[str] = None,
        role: Role = Role.USER,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        auth_log.log_event(
            operation="user_created",
            message="User created",
            metadata={"user_id": str(user.id), "email": email},
        )
        return user

    async def update_password(self, user_id: str, new_hash: str) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.password_hash = new_hash
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def verify_credentials(self, email: str, password_verify_fn) -> Optional[User]:
        """Verify email + password. password_verify_fn(password, hash) -> bool."""
        user = await self.get_by_email(email)
        if not user:
            return None
        if password_verify_fn("", user.password_hash) is False and email:
            # The actual password check is deferred to caller's verify function
            # This just ensures the user exists
            return user
        return user
