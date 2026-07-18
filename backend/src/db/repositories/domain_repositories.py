"""Domain repositories for Jobs, Approvals, Roadmaps, Evaluation,
Knowledge, Interview, Orchestration, Preferences, Packages.

Each repository extends BaseRepository for its domain model.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.base_repository import BaseRepository
from src.models.jobs import Job, JobMatch, OpportunityNotification
from src.models.approvals import Approval, ApprovalItem, ApprovalComment, ApprovalNotification
from src.models.roadmap import Roadmap, RoadmapGoal, RoadmapTask
from src.models.evaluation_prefs import EvaluationRun, HallucinationAudit, UserPreferences
from src.models.interview import InterviewSession, InterviewQuestion, InterviewWeaknessHistory
from src.models.orchestration import (
    OrchestrationSession, OrchestrationEvent, GovernanceDecision,
    AutonomousAction, OpportunityScore, NotificationHistory, MCPExecutionLog,
)


# ── Jobs Repository ─────────────────────────────────────────────────

class JobRepository(BaseRepository[Job]):
    def __init__(self, db: AsyncSession):
        super().__init__(Job, db)

    async def find_by_source(self, source: str, limit: int = 50, offset: int = 0) -> tuple[list[Job], int]:
        return await self.find_paginated(
            Job.source == source,
            limit=limit, offset=offset,
            order_by=Job.ingested_at.desc(),
        )

    async def find_by_score_min(self, min_score: float, limit: int = 50, offset: int = 0) -> tuple[list[Job], int]:
        return await self.find_paginated(
            Job.match_score >= min_score,
            limit=limit, offset=offset,
            order_by=Job.match_score.desc(),
        )

    async def get_stats(self) -> dict:
        inventory_filters = (
            Job.deleted_at.is_(None),
            Job.apply_url.is_not(None),
            Job.apply_url != "",
        )
        active_filters = (
            Job.status == "active",
            Job.deleted_at.is_(None),
            Job.is_tech_role == True,
            Job.is_india_eligible == True,
            Job.apply_url.is_not(None),
            Job.apply_url != "",
            Job.lifecycle_state.notin_(["APPLIED", "INTERVIEWING", "OFFERED", "HIRED", "EXPIRED"]),
            ((Job.freshness_bucket.is_(None)) | (Job.freshness_bucket != "stale")),
        )
        total = await self.count(*active_filters)
        active = total
        raw_total = await self.count(*inventory_filters)
        avg_score_result = await self.db.execute(select(func.avg(Job.match_score)).where(*active_filters))
        avg_score = avg_score_result.scalar() or 0.0
        sources_result = await self.db.execute(
            select(Job.source, func.count(Job.id)).where(*active_filters).group_by(Job.source)
        )
        by_source = {str(r[0]): int(r[1]) for r in sources_result.all()}
        last_result = await self.db.execute(select(func.max(Job.fetched_at)).where(*active_filters))
        last_ingested = last_result.scalar()

        india_eligible_result = await self.db.execute(
            select(func.count(Job.id)).where(*active_filters, Job.is_india_eligible == True)
        )
        india_eligible = india_eligible_result.scalar() or 0
        excluded_non_india = total - india_eligible

        india_by_source_result = await self.db.execute(
            select(Job.source, func.count(Job.id))
            .where(*active_filters, Job.is_india_eligible == True)
            .group_by(Job.source)
        )
        india_by_source = {str(r[0]): int(r[1]) for r in india_by_source_result.all()}

        filtered_out_result = raw_total - total
        non_india_filtered = int((await self.db.execute(
            select(func.count(Job.id)).where(
                *inventory_filters,
                Job.status == "active",
                Job.is_india_eligible == False,
            )
        )).scalar() or 0)
        non_tech_filtered = int((await self.db.execute(
            select(func.count(Job.id)).where(
                *inventory_filters,
                Job.status == "active",
                Job.is_tech_role == False,
            )
        )).scalar() or 0)
        stale_or_closed_filtered = int((await self.db.execute(
            select(func.count(Job.id)).where(
                *inventory_filters,
                (
                    (Job.status != "active") |
                    (Job.lifecycle_state.in_(["APPLIED", "INTERVIEWING", "OFFERED", "HIRED", "EXPIRED"])) |
                    (Job.freshness_bucket == "stale")
                ),
            )
        )).scalar() or 0)

        return {
            "total_jobs": total,
            "raw_total_jobs": raw_total,
            "active_jobs": active,
            "india_eligible_jobs": india_eligible,
            "excluded_non_india": excluded_non_india,
            "filtered_out_jobs": filtered_out_result,
            "non_india_filtered_jobs": non_india_filtered,
            "non_tech_filtered_jobs": non_tech_filtered,
            "stale_or_closed_jobs": stale_or_closed_filtered,
            "avg_match_score": round(float(avg_score), 2),
            "by_source": by_source,
            "india_by_source": india_by_source,
            "last_ingested": last_ingested.isoformat() if last_ingested else None,
        }

    async def get_by_uid(self, job_uid: str) -> Optional[Job]:
        return await self.find_one(Job.job_uid == job_uid)

    async def exists_by_hash(self, job_hash: str) -> bool:
        return await self.exists(Job.job_uid == job_hash)

    async def find_active(self, limit: int = 100) -> list[Job]:
        return await self.find_many(
            Job.status == "active",
            Job.apply_url.is_not(None),
            Job.apply_url != "",
            Job.lifecycle_state.notin_(["APPLIED", "INTERVIEWING", "OFFERED", "HIRED", "EXPIRED"]),
            ((Job.freshness_bucket.is_(None)) | (Job.freshness_bucket != "stale")),
            limit=limit,
            order_by=Job.ingested_at.desc(),
        )

    async def get_last_fetched_at_for_source(self, source: str) -> Optional[datetime]:
        result = await self.db.execute(
            select(func.max(Job.fetched_at)).where(
                Job.source == source,
                Job.source_job_id.is_not(None),
            )
        )
        return result.scalar()

    async def find_recent_source_job_ids(self, source: str, limit: int = 250) -> list[str]:
        result = await self.db.execute(
            select(Job.source_job_id)
            .where(
                Job.source == source,
                Job.source_job_id.is_not(None),
            )
            .order_by(desc(Job.fetched_at), desc(Job.ingested_at), desc(Job.id))
            .limit(limit)
        )
        return [str(job_id) for job_id in result.scalars().all() if str(job_id).strip()]


class JobMatchRepository(BaseRepository[JobMatch]):
    def __init__(self, db: AsyncSession):
        super().__init__(JobMatch, db)

    async def find_by_user(self, user_id: str, limit: int = 50) -> list[JobMatch]:
        return await self.find_many(
            JobMatch.user_id == user_id,
            limit=limit,
            order_by=JobMatch.created_at.desc(),
        )

    async def find_by_user_and_job(self, user_id: str, job_id: int) -> Optional[JobMatch]:
        return await self.find_one(
            JobMatch.user_id == user_id,
            JobMatch.job_id == job_id,
        )


class OpportunityNotificationRepository(BaseRepository[OpportunityNotification]):
    def __init__(self, db: AsyncSession):
        super().__init__(OpportunityNotification, db)

    async def find_for_user_job_channel(self, user_id: str, job_id: int, channel: str) -> Optional[OpportunityNotification]:
        return await self.find_one(
            OpportunityNotification.user_id == user_id,
            OpportunityNotification.job_id == job_id,
            OpportunityNotification.channel == channel,
        )

    async def channel_send_count(self, user_id: str, job_id: int, channel: str) -> int:
        record = await self.find_for_user_job_channel(user_id, job_id, channel)
        return int(record.send_count or 0) if record else 0

    async def has_applied(self, user_id: str, job_id: int) -> bool:
        result = await self.db.execute(select(OpportunityNotification).where(
            OpportunityNotification.user_id == user_id,
            OpportunityNotification.job_id == job_id,
            OpportunityNotification.applied_at.is_not(None),
        ).limit(1))
        return result.scalar_one_or_none() is not None


# ── Approvals Repository ────────────────────────────────────────────

class ApprovalRepository(BaseRepository[Approval]):
    def __init__(self, db: AsyncSession):
        super().__init__(Approval, db)

    async def find_by_user(self, user_id: str, status: Optional[str] = None,
                           limit: int = 50, offset: int = 0) -> tuple[list[Approval], int]:
        filters = [Approval.user_id == user_id]
        if status:
            filters.append(Approval.status == status)
        return await self.find_paginated(*filters, limit=limit, offset=offset,
                                          order_by=Approval.created_at.desc())

    async def get_stats(self, user_id: str) -> dict:
        total = await self.count(Approval.user_id == user_id)
        pending = await self.count(Approval.user_id == user_id, Approval.status == "pending")
        approved = await self.count(Approval.user_id == user_id, Approval.status == "approved")
        rejected = await self.count(Approval.user_id == user_id, Approval.status == "rejected")
        executed = await self.count(Approval.user_id == user_id, Approval.status == "executed")
        return {"total": total, "pending": pending, "approved": approved,
                "rejected": rejected, "executed": executed}

    async def get_by_uid(self, approval_uid: str) -> Optional[Approval]:
        return await self.find_one(Approval.approval_uid == approval_uid)


class ApprovalItemRepository(BaseRepository[ApprovalItem]):
    def __init__(self, db: AsyncSession):
        super().__init__(ApprovalItem, db)

    async def find_by_approval(self, approval_id: int) -> list[ApprovalItem]:
        return await self.find_many(
            ApprovalItem.approval_id == approval_id,
            order_by=ApprovalItem.order_index,
        )


class ApprovalCommentRepository(BaseRepository[ApprovalComment]):
    def __init__(self, db: AsyncSession):
        super().__init__(ApprovalComment, db)

    async def find_by_approval(self, approval_id: int) -> list[ApprovalComment]:
        return await self.find_many(
            ApprovalComment.approval_id == approval_id,
            order_by=ApprovalComment.created_at,
        )


class ApprovalNotificationRepository(BaseRepository[ApprovalNotification]):
    def __init__(self, db: AsyncSession):
        super().__init__(ApprovalNotification, db)

    async def find_unread_by_user(self, user_id: str) -> list[ApprovalNotification]:
        return await self.find_many(
            ApprovalNotification.user_id == user_id,
            ApprovalNotification.read == False,
            order_by=ApprovalNotification.created_at.desc(),
        )

    async def find_by_user(self, user_id: str, limit: int = 50) -> list[ApprovalNotification]:
        return await self.find_many(
            ApprovalNotification.user_id == user_id,
            limit=limit,
            order_by=ApprovalNotification.created_at.desc(),
        )

    async def mark_all_read(self, user_id: str) -> int:
        from sqlalchemy import update
        result = await self.db.execute(
            update(ApprovalNotification)
            .where(ApprovalNotification.user_id == user_id, ApprovalNotification.read == False)
            .values(read=True)
        )
        await self.db.commit()
        return result.rowcount


# ── Roadmap Repository ──────────────────────────────────────────────

class RoadmapRepository(BaseRepository[Roadmap]):
    def __init__(self, db: AsyncSession):
        super().__init__(Roadmap, db)

    async def find_by_user(self, user_id: str, limit: int = 10) -> list[Roadmap]:
        return await self.find_many(
            Roadmap.user_id == user_id,
            limit=limit,
            order_by=Roadmap.created_at.desc(),
        )

    async def get_by_uid(self, roadmap_uid: str) -> Optional[Roadmap]:
        return await self.find_one(Roadmap.roadmap_uid == roadmap_uid)


class RoadmapGoalRepository(BaseRepository[RoadmapGoal]):
    def __init__(self, db: AsyncSession):
        super().__init__(RoadmapGoal, db)

    async def find_by_roadmap(self, roadmap_id: int) -> list[RoadmapGoal]:
        return await self.find_many(
            RoadmapGoal.roadmap_id == roadmap_id,
            order_by=RoadmapGoal.order_index,
        )


class RoadmapTaskRepository(BaseRepository[RoadmapTask]):
    def __init__(self, db: AsyncSession):
        super().__init__(RoadmapTask, db)

    async def find_by_goal(self, goal_id: int) -> list[RoadmapTask]:
        return await self.find_many(
            RoadmapTask.goal_id == goal_id,
            order_by=RoadmapTask.order_index,
        )

    async def get_by_uid(self, task_uid: str) -> Optional[RoadmapTask]:
        return await self.find_one(RoadmapTask.task_uid == task_uid)

    async def toggle_completion(self, task_uid: str, completed: bool) -> Optional[RoadmapTask]:
        task = await self.get_by_uid(task_uid)
        if not task:
            return None
        task.completed = completed
        task.updated_at = datetime.utcnow()
        await self.db.commit()
        return task


# ── Evaluation Repository ───────────────────────────────────────────

class EvaluationRunRepository(BaseRepository[EvaluationRun]):
    def __init__(self, db: AsyncSession):
        super().__init__(EvaluationRun, db)

    async def find_recent(self, limit: int = 20) -> list[EvaluationRun]:
        return await self.find_many(
            limit=limit,
            order_by=EvaluationRun.created_at.desc(),
        )

    async def get_by_uid(self, run_uid: str) -> Optional[EvaluationRun]:
        return await self.find_one(EvaluationRun.run_uid == run_uid)

    async def find_in_progress(self) -> list[EvaluationRun]:
        return await self.find_many(EvaluationRun.status == "in_progress")


class HallucinationAuditRepository(BaseRepository[HallucinationAudit]):
    def __init__(self, db: AsyncSession):
        super().__init__(HallucinationAudit, db)

    async def find_by_run(self, run_id: str) -> list[HallucinationAudit]:
        return await self.find_many(
            HallucinationAudit.run_id == run_id,
            order_by=HallucinationAudit.created_at.desc(),
        )


# ── Preferences Repository ──────────────────────────────────────────

class PreferencesRepository(BaseRepository[UserPreferences]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserPreferences, db)

    async def get_by_user(self, user_id: str) -> Optional[UserPreferences]:
        return await self.find_one(UserPreferences.user_id == user_id)

    async def upsert(self, user_id: str, **kwargs) -> UserPreferences:
        from sqlalchemy.dialects.postgresql import insert
        stmt = insert(UserPreferences).values(user_id=user_id, **kwargs).on_conflict_do_update(
            index_elements=[UserPreferences.user_id],
            set_={k: v for k, v in kwargs.items() if v is not None},
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return await self.get_by_user(user_id)


# ── Interview Repository ────────────────────────────────────────────

class InterviewSessionRepository(BaseRepository[InterviewSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(InterviewSession, db)

    async def find_by_user(self, user_id: str, limit: int = 50) -> list[InterviewSession]:
        return await self.find_many(
            InterviewSession.user_id == user_id,
            limit=limit,
            order_by=InterviewSession.created_at.desc(),
        )

    async def get_by_uid(self, session_uid: str) -> Optional[InterviewSession]:
        return await self.find_one(InterviewSession.session_uid == session_uid)


class InterviewQuestionRepository(BaseRepository[InterviewQuestion]):
    def __init__(self, db: AsyncSession):
        super().__init__(InterviewQuestion, db)

    async def find_by_session(self, session_id: int) -> list[InterviewQuestion]:
        return await self.find_many(
            InterviewQuestion.session_id == session_id,
            order_by=InterviewQuestion.question_index,
        )


class InterviewWeaknessRepository(BaseRepository[InterviewWeaknessHistory]):
    def __init__(self, db: AsyncSession):
        super().__init__(InterviewWeaknessHistory, db)

    async def find_by_user(self, user_id: str) -> list[InterviewWeaknessHistory]:
        return await self.find_many(
            InterviewWeaknessHistory.user_id == user_id,
        )


# ── Orchestration Repository ────────────────────────────────────────

class OrchestrationSessionRepository(BaseRepository[OrchestrationSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(OrchestrationSession, db)

    async def find_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> tuple[list[OrchestrationSession], int]:
        return await self.find_paginated(
            OrchestrationSession.user_id == user_id,
            limit=limit, offset=offset,
            order_by=OrchestrationSession.created_at.desc(),
        )

    async def get_by_uid(self, session_uid: str) -> Optional[OrchestrationSession]:
        return await self.find_one(OrchestrationSession.session_uid == session_uid)


class OrchestrationEventRepository(BaseRepository[OrchestrationEvent]):
    def __init__(self, db: AsyncSession):
        super().__init__(OrchestrationEvent, db)

    async def find_by_session(self, session_id: int, limit: int = 100) -> list[OrchestrationEvent]:
        return await self.find_many(
            OrchestrationEvent.session_id == session_id,
            limit=limit,
            order_by=OrchestrationEvent.created_at.desc(),
        )


class GovernanceDecisionRepository(BaseRepository[GovernanceDecision]):
    def __init__(self, db: AsyncSession):
        super().__init__(GovernanceDecision, db)

    async def find_recent(self, limit: int = 50, offset: int = 0) -> tuple[list[GovernanceDecision], int]:
        return await self.find_paginated(
            limit=limit, offset=offset,
            order_by=GovernanceDecision.created_at.desc(),
        )

    async def get_stats(self) -> dict:
        total = await self.count()
        passed = await self.count(GovernanceDecision.verdict == "passed")
        suppressed = await self.count(GovernanceDecision.verdict == "suppressed")
        return {"total": total, "passed": passed, "suppressed": suppressed}


class AutonomousActionRepository(BaseRepository[AutonomousAction]):
    def __init__(self, db: AsyncSession):
        super().__init__(AutonomousAction, db)

    async def find_recent(self, limit: int = 20, offset: int = 0) -> tuple[list[AutonomousAction], int]:
        return await self.find_paginated(
            limit=limit, offset=offset,
            order_by=AutonomousAction.created_at.desc(),
        )


class OpportunityScoreRepository(BaseRepository[OpportunityScore]):
    def __init__(self, db: AsyncSession):
        super().__init__(OpportunityScore, db)

    async def find_by_user(self, user_id: str, limit: int = 20) -> list[OpportunityScore]:
        return await self.find_many(
            OpportunityScore.user_id == user_id,
            limit=limit,
            order_by=OpportunityScore.created_at.desc(),
        )


class NotificationHistoryRepository(BaseRepository[NotificationHistory]):
    def __init__(self, db: AsyncSession):
        super().__init__(NotificationHistory, db)

    async def find_by_user(self, user_id: str, limit: int = 50) -> list[NotificationHistory]:
        return await self.find_many(
            NotificationHistory.user_id == user_id,
            limit=limit,
            order_by=NotificationHistory.created_at.desc(),
        )


class MCPExecutionLogRepository(BaseRepository[MCPExecutionLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(MCPExecutionLog, db)

    async def find_by_session(self, session_id: int, limit: int = 50) -> list[MCPExecutionLog]:
        return await self.find_many(
            MCPExecutionLog.session_id == session_id,
            limit=limit,
            order_by=MCPExecutionLog.created_at.desc(),
        )
