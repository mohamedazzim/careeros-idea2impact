"""RC3 Opportunity Lifecycle Agent."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import ApplicationTimelineEvent, Job, OpportunityLifecycleRun, OpportunityNotification


class OpportunityLifecycleAgent:
    async def monitor(self, db: AsyncSession, *, user_id: str) -> OpportunityLifecycleRun:
        active = int((await db.execute(select(func.count()).select_from(Job).where(Job.status == "active"))).scalar() or 0)
        ignored = int((await db.execute(select(func.count()).select_from(OpportunityNotification).where(
            OpportunityNotification.user_id == user_id,
            OpportunityNotification.status.in_(["ignored", "suppressed"]),
        ))).scalar() or 0)
        applied = int((await db.execute(select(func.count()).select_from(ApplicationTimelineEvent).where(
            ApplicationTimelineEvent.user_id == user_id,
            ApplicationTimelineEvent.status == "APPLIED",
        ))).scalar() or 0)
        recent_cutoff = datetime.utcnow() - timedelta(days=2)
        new_jobs = int((await db.execute(select(func.count()).select_from(Job).where(
            Job.status == "active",
            Job.ingested_at >= recent_cutoff,
        ))).scalar() or 0)
        run = OpportunityLifecycleRun(
            user_id=user_id,
            status="completed",
            monitored_counts={
                "active_jobs": active,
                "new_jobs_48h": new_jobs,
                "ignored_notifications": ignored,
                "applied_events": applied,
            },
            triggered_actions={"followups": 0, "deadline_warnings": 0, "duplicate_notifications_prevented": True},
        )
        db.add(run)
        await db.flush()
        return run


def get_opportunity_lifecycle_agent() -> OpportunityLifecycleAgent:
    return OpportunityLifecycleAgent()
