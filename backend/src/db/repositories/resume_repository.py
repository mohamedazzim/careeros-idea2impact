"""Resume repository for career document management."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.repositories.base_repository import BaseRepository
from src.models.resume import Resume


class ResumeRepository(BaseRepository[Resume]):
    def __init__(self, db: AsyncSession):
        super().__init__(Resume, db)

    async def find_by_user(self, user_id: str, limit: int = 50, offset: int = 0):
        return await self.find_paginated(
            Resume.user_id == user_id,
            limit=limit, offset=offset,
            order_by=Resume.created_at.desc(),
        )

    async def find_by_status(self, user_id: str, status: str, limit: int = 50):
        return await self.find_many(
            Resume.user_id == user_id,
            Resume.status == status,
            limit=limit,
            order_by=Resume.created_at.desc(),
        )

    async def get_by_task_id(self, task_id: str) -> Optional[Resume]:
        return await self.find_one(Resume.task_id == task_id)
