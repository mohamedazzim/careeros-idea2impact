"""Generated package repository."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.repositories.base_repository import BaseRepository
from src.models.package import GeneratedPackage


class PackageRepository(BaseRepository[GeneratedPackage]):
    def __init__(self, db: AsyncSession):
        super().__init__(GeneratedPackage, db)

    async def find_by_user(self, user_id: str, limit: int = 50, offset: int = 0):
        return await self.find_paginated(
            GeneratedPackage.user_id == user_id,
            limit=limit, offset=offset,
            order_by=GeneratedPackage.created_at.desc(),
        )

    async def find_by_job(self, user_id: str, job_id: int):
        return await self.find_many(
            GeneratedPackage.user_id == user_id,
            GeneratedPackage.job_id == job_id,
            order_by=GeneratedPackage.created_at.desc(),
        )

    async def get_by_uid(self, package_uid: str) -> Optional[GeneratedPackage]:
        return await self.find_one(GeneratedPackage.package_uid == package_uid)

    async def get_by_uid_for_user(
        self,
        package_uid: str,
        user_id: str,
    ) -> Optional[GeneratedPackage]:
        """Return a package only when it belongs to the requesting user."""
        return await self.find_one(
            GeneratedPackage.package_uid == package_uid,
            GeneratedPackage.user_id == user_id,
        )
