"""Generated report repository."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.base_repository import BaseRepository
from src.models.report import GeneratedReport


class GeneratedReportRepository(BaseRepository[GeneratedReport]):
    def __init__(self, db: AsyncSession):
        super().__init__(GeneratedReport, db)

    async def get_by_uid(self, report_uid: str) -> Optional[GeneratedReport]:
        return await self.find_one(GeneratedReport.report_uid == report_uid)

    async def find_by_user(self, user_id: str, limit: int = 50, offset: int = 0):
        return await self.find_paginated(
            GeneratedReport.user_id == user_id,
            limit=limit,
            offset=offset,
            order_by=GeneratedReport.created_at.desc(),
        )
