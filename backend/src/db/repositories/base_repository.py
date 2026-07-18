"""
Base repository pattern for all domain repositories.
Provides common CRUD operations with AsyncSession dependency.
"""

from __future__ import annotations
from typing import Generic, Optional, Type, TypeVar
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sa_delete, update as sa_update

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic async repository with common CRUD operations."""

    def __init__(self, model: Type[T], db: AsyncSession):
        self.model = model
        self.db = db

    def _active_query(self):
        q = select(self.model)
        if hasattr(self.model, 'deleted_at'):
            q = q.where(self.model.deleted_at == None)
        return q

    async def get_by_id(self, id: int) -> Optional[T]:
        q = select(self.model).where(self.model.id == id)
        if hasattr(self.model, 'deleted_at'):
            q = q.where(self.model.deleted_at == None)
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[T]:
        q = self._active_query().offset(offset).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def count(self, *filters) -> int:
        q = select(func.count()).select_from(self.model)
        if hasattr(self.model, 'deleted_at'):
            q = q.where(self.model.deleted_at == None)
        for f in filters:
            q = q.where(f)
        result = await self.db.execute(q)
        return result.scalar() or 0

    async def create(self, **kwargs) -> T:
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update(self, id: int, **kwargs) -> Optional[T]:
        if not kwargs:
            return None
        await self.db.execute(
            sa_update(self.model).where(self.model.id == id).values(**kwargs)
        )
        await self.db.commit()
        return await self.get_by_id(id)

    async def delete(self, id: int) -> bool:
        """Hard delete. Prefer soft_delete() for business entities."""
        result = await self.db.execute(
            sa_delete(self.model).where(self.model.id == id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def soft_delete(self, id: int) -> bool:
        """Set deleted_at timestamp instead of hard delete."""
        if not hasattr(self.model, 'deleted_at'):
            return await self.delete(id)
        return await self.update(id, deleted_at=datetime.utcnow()) is not None

    async def find_one(self, *filters) -> Optional[T]:
        q = select(self.model)
        if hasattr(self.model, 'deleted_at'):
            q = q.where(self.model.deleted_at == None)
        for f in filters:
            q = q.where(f)
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def find_many(self, *filters, limit: int = 50, offset: int = 0, order_by=None) -> list[T]:
        q = select(self.model)
        if hasattr(self.model, 'deleted_at'):
            q = q.where(self.model.deleted_at == None)
        for f in filters:
            q = q.where(f)
        if order_by is not None:
            q = q.order_by(order_by)
        q = q.offset(offset).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def find_paginated(self, *filters, limit: int = 50, offset: int = 0, order_by=None) -> tuple[list[T], int]:
        count_q = select(func.count()).select_from(self.model)
        data_q = select(self.model)
        if hasattr(self.model, 'deleted_at'):
            count_q = count_q.where(self.model.deleted_at == None)
            data_q = data_q.where(self.model.deleted_at == None)
        for f in filters:
            count_q = count_q.where(f)
            data_q = data_q.where(f)
        if order_by is not None:
            data_q = data_q.order_by(order_by)
        data_q = data_q.offset(offset).limit(limit)

        count_result = await self.db.execute(count_q)
        total = count_result.scalar() or 0
        data_result = await self.db.execute(data_q)
        return list(data_result.scalars().all()), total

    async def exists(self, *filters) -> bool:
        q = select(func.count()).select_from(self.model)
        if hasattr(self.model, 'deleted_at'):
            q = q.where(self.model.deleted_at == None)
        for f in filters:
            q = q.where(f)
        result = await self.db.execute(q)
        return (result.scalar() or 0) > 0
