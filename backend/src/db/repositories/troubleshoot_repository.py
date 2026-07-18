"""Troubleshoot/ops repositories for circuits, audit logs, and pending jobs."""

from sqlalchemy.ext.asyncio import AsyncSession
from src.db.repositories.base_repository import BaseRepository
from src.models.troubleshoot import CircuitState, AuditLog, PendingJob


class CircuitStateRepository(BaseRepository[CircuitState]):
    def __init__(self, db: AsyncSession):
        super().__init__(CircuitState, db)

    async def find_by_service(self, service: str):
        return await self.find_many(CircuitState.service == service)

    async def find_by_state(self, state: str):
        return await self.find_many(CircuitState.state == state)


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(AuditLog, db)

    async def find_by_user(self, user_id: str, limit: int = 50, offset: int = 0):
        return await self.find_paginated(
            AuditLog.user_id == user_id,
            limit=limit, offset=offset,
            order_by=AuditLog.created_at.desc(),
        )

    async def find_by_action(self, action: str, limit: int = 50, offset: int = 0):
        return await self.find_paginated(
            AuditLog.action == action,
            limit=limit, offset=offset,
            order_by=AuditLog.created_at.desc(),
        )

    async def find_by_resource(self, resource: str, limit: int = 50, offset: int = 0):
        return await self.find_paginated(
            AuditLog.resource == resource,
            limit=limit, offset=offset,
            order_by=AuditLog.created_at.desc(),
        )


class PendingJobRepository(BaseRepository[PendingJob]):
    def __init__(self, db: AsyncSession):
        super().__init__(PendingJob, db)

    async def find_pending(self, limit: int = 50):
        return await self.find_many(
            PendingJob.status == "pending",
            limit=limit,
            order_by=PendingJob.priority.desc(),
        )

    async def find_by_type(self, job_type: str, limit: int = 50):
        return await self.find_many(
            PendingJob.job_type == job_type,
            limit=limit,
            order_by=PendingJob.created_at.desc(),
        )
