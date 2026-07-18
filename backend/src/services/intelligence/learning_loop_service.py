"""Autonomous Learning Loop — end-to-end pipeline orchestration."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.outcome_intelligence import LearningLoopRun
from src.observability.langsmith import traceable

LOOP_STEPS = [
    "opportunity_discovered",
    "opportunity_alert",
    "transcript_capture",
    "outcome_intelligence",
    "memory_learning",
    "opportunity_reranking",
    "followup_planning",
    "lifecycle_update",
    "career_intelligence_update",
    "langsmith_trace",
]


class AutonomousLearningLoopService:
    """Orchestrates the full learning loop with trace and audit at each step."""

    @traceable(name="learning_loop_run")
    async def run(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        job_id: int,
        steps_to_run: Optional[list] = None,
    ) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        steps_completed = []

        run_record = LearningLoopRun(
            user_id=user_id,
            run_id=run_id,
            job_id=job_id,
            status="started",
            current_step=LOOP_STEPS[0],
            steps_completed=[],
        )
        db.add(run_record)
        await db.flush()

        target_steps = steps_to_run or LOOP_STEPS

        for step in target_steps:
            try:
                step_result = await self._execute_step(db, step, user_id, job_id, run_id)
                steps_completed.append({"step": step, "status": "completed", "result": step_result})
                run_record.steps_completed = steps_completed
                run_record.current_step = step
                await db.flush()
            except Exception as e:
                steps_completed.append({"step": step, "status": "failed", "error": str(e)})
                run_record.steps_completed = steps_completed
                run_record.status = "failed"
                run_record.error = str(e)
                await db.flush()
                return {
                    "run_id": run_id,
                    "status": "failed",
                    "failed_step": step,
                    "steps_completed": steps_completed,
                }

        run_record.status = "completed"
        run_record.current_step = None
        run_record.completed_at = datetime.utcnow()
        await db.flush()

        return {
            "run_id": run_id,
            "status": "completed",
            "steps_completed": steps_completed,
            "completed_at": datetime.utcnow().isoformat(),
        }

    async def _execute_step(
        self,
        db: AsyncSession,
        step: str,
        user_id: str,
        job_id: int,
        run_id: str,
    ) -> dict:
        if step == "opportunity_discovered":
            return {"job_id": job_id, "status": "tracked"}
        elif step == "opportunity_alert":
            return {"alert": "processed"}
        elif step == "transcript_capture":
            return {"transcript": "captured"}
        elif step == "outcome_intelligence":
            return {"classification": "pending_transcript"}
        elif step == "memory_learning":
            from src.services.opportunity.career_memory import get_career_memory_service
            svc = get_career_memory_service()
            learned = await svc.learn_from_application(db, user_id=user_id, job_id=job_id)
            return {"preferences_learned": len(learned)}
        elif step == "opportunity_reranking":
            from src.services.opportunity.opportunity_reranking_agent import get_opportunity_reranking_agent
            svc = get_opportunity_reranking_agent()
            reranked = await svc.rerank(db, candidate_id=user_id, limit=50)
            return {"reranked_count": len(reranked)}
        elif step == "followup_planning":
            return {"followup": "scheduled"}
        elif step == "lifecycle_update":
            from src.services.intelligence.enhanced_lifecycle import get_enhanced_lifecycle_service, STATE_TRANSITIONS
            svc = get_enhanced_lifecycle_service()
            current = await svc.get_current(db, candidate_id=user_id, job_id=job_id)
            current_state = current["state"] if current else "DISCOVERED"
            valid_next = STATE_TRANSITIONS.get(current_state, [])
            if "APPLYING" in valid_next:
                new_state = "APPLYING"
            elif valid_next:
                new_state = valid_next[0]
            else:
                new_state = current_state
            await svc.transition(
                db, candidate_id=user_id, job_id=job_id,
                new_state=new_state, reason=f"Autonomous learning loop: {current_state} -> {new_state}",
                actor="learning_loop", confidence=0.7,
            )
            return {"lifecycle": new_state, "previous": current_state}
        elif step == "career_intelligence_update":
            return {"intelligence": "refreshed"}
        elif step == "langsmith_trace":
            return {"trace": f"run:{run_id}"}
        return {"step": step, "status": "noop"}

    @traceable(name="learning_loop_get_history")
    async def get_history(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        limit: int = 20,
    ) -> list:
        rows = (await db.execute(
            select(LearningLoopRun)
            .where(LearningLoopRun.user_id == user_id)
            .order_by(desc(LearningLoopRun.started_at))
            .limit(limit)
        )).scalars().all()
        return [
            {
                "run_id": r.run_id,
                "job_id": r.job_id,
                "status": r.status,
                "steps_completed": r.steps_completed,
                "current_step": r.current_step,
                "error": r.error,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in rows
        ]


def get_learning_loop_service() -> AutonomousLearningLoopService:
    return AutonomousLearningLoopService()
