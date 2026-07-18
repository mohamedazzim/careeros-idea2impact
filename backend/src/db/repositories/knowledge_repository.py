"""Knowledge document repository."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.repositories.base_repository import BaseRepository
from src.models.knowledge import KnowledgeDoc


class KnowledgeRepository(BaseRepository[KnowledgeDoc]):
    def __init__(self, db: AsyncSession):
        super().__init__(KnowledgeDoc, db)

    async def find_by_user(self, user_id: str, limit: int = 50, offset: int = 0):
        return await self.find_paginated(
            KnowledgeDoc.user_id == user_id,
            limit=limit, offset=offset,
            order_by=KnowledgeDoc.created_at.desc(),
        )

    async def find_by_status(self, user_id: str, status: str, limit: int = 50):
        return await self.find_many(
            KnowledgeDoc.user_id == user_id,
            KnowledgeDoc.status == status,
            limit=limit,
        )

    async def get_by_uid(self, doc_uid: str) -> Optional[KnowledgeDoc]:
        return await self.find_one(KnowledgeDoc.doc_uid == doc_uid)
