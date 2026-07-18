"""Rerank run repository for persistence and analytics."""

from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rerank import RerankRun
from src.db.repositories.base_repository import BaseRepository


class RerankRepository(BaseRepository[RerankRun]):
    def __init__(self, db: AsyncSession):
        super().__init__(RerankRun, db)

    async def create_run(self, **kwargs) -> RerankRun:
        return await self.create(**kwargs)

    async def get_run(self, run_id: UUID) -> Optional[RerankRun]:
        return await self.get_by_id(run_id)

    async def list_runs(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RerankRun]:
        filters = []
        if user_id:
            filters.append(RerankRun.user_id == user_id)
        return (await self.find_paginated(
            *filters,
            limit=limit,
            offset=offset,
            order_by=RerankRun.created_at.desc(),
        ))[0]

    async def get_stats(self) -> Dict[str, Any]:
        total = await self.count()

        q = select(
            func.count().label("total"),
            func.avg(RerankRun.primary_latency_ms).label("avg_latency"),
            func.avg(RerankRun.confidence_avg).label("avg_confidence"),
            func.sum(func.cast(RerankRun.primary_success, Integer)).label("success_count"),
            func.sum(func.cast(RerankRun.fallback_used, Integer)).label("fallback_count"),
            func.sum(func.cast(RerankRun.circuit_breaker_open, Integer)).label("cb_open_count"),
            func.avg(RerankRun.chunks_submitted).label("avg_chunks_in"),
            func.avg(RerankRun.chunks_returned).label("avg_chunks_out"),
        )
        result = await self.db.execute(q)
        row = result.one_or_none()

        if row is None or row.total == 0:
            return {
                "total_runs": 0,
                "success_rate": 1.0,
                "fallback_rate": 0.0,
                "avg_latency_ms": 0,
                "avg_confidence": 0,
                "avg_chunks_submitted": 0,
                "avg_chunks_returned": 0,
                "circuit_breaker_opens": 0,
            }

        t = max(row.total, 1)
        return {
            "total_runs": row.total,
            "success_rate": round((row.success_count or 0) / t, 4),
            "fallback_rate": round((row.fallback_count or 0) / t, 4),
            "avg_latency_ms": round(row.avg_latency or 0, 2),
            "avg_confidence": round(row.avg_confidence or 0, 4),
            "avg_chunks_submitted": round(row.avg_chunks_in or 0, 1),
            "avg_chunks_returned": round(row.avg_chunks_out or 0, 1),
            "circuit_breaker_opens": row.cb_open_count or 0,
        }
