"""Phase 6 — Career Intelligence, Coach, Lifecycle, and Learning Loop APIs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db

router = APIRouter(tags=["Phase 6 — Career Intelligence & Coach"])


# ── Candidate Memory ────────────────────────────────────────────

@router.get("/candidate-memory")
async def candidate_memory_preferences(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.models.outcome_intelligence import CandidatePreferenceMemory
    from sqlalchemy import desc, select

    rows = (await db.execute(
        select(CandidatePreferenceMemory)
        .where(CandidatePreferenceMemory.candidate_id == user["sub"])
        .order_by(desc(CandidatePreferenceMemory.confidence))
    )).scalars().all()
    return {
        "preferences": [
            {
                "type": r.preference_type,
                "value": r.preference_value,
                "confidence": r.confidence,
                "evidence": r.evidence,
                "source_conversation_id": r.source_conversation_id,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/candidate-memory/history")
async def candidate_memory_history(
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.models.outcome_intelligence import CandidatePreferenceHistory
    from sqlalchemy import desc, select

    rows = (await db.execute(
        select(CandidatePreferenceHistory)
        .where(CandidatePreferenceHistory.candidate_id == user["sub"])
        .order_by(desc(CandidatePreferenceHistory.created_at))
        .limit(limit)
    )).scalars().all()
    return {
        "history": [
            {
                "preference_type": r.preference_type,
                "preference_value": r.preference_value,
                "confidence": r.confidence,
                "evidence": r.evidence,
                "action": r.action,
                "source_conversation_id": r.source_conversation_id,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": len(rows),
    }


# ── Opportunity Re-Ranking ──────────────────────────────────────

@router.get("/opportunities/reranked")
async def reranked_opportunities(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.models.outcome_intelligence import OpportunityRerankingRecord
    from src.models.jobs import Job
    from sqlalchemy import desc, select

    rows = (await db.execute(
        select(OpportunityRerankingRecord, Job)
        .join(Job, Job.id == OpportunityRerankingRecord.job_id)
        .where(OpportunityRerankingRecord.candidate_id == user["sub"])
        .order_by(desc(OpportunityRerankingRecord.final_opportunity_ranking))
        .limit(limit)
    )).all()

    return {
        "reranked": [
            {
                "job_id": rec.job_id,
                "title": job.title,
                "company": job.company,
                "base_score": rec.existing_match_score,
                "memory_score": rec.memory_affinity_score,
                "urgency_score": rec.outcome_success_score,
                "final_score": rec.final_opportunity_ranking,
                "explanation": rec.explanation,
                "source_url": job.apply_url,
            }
            for rec, job in rows
        ],
        "total": len(rows),
    }


@router.get("/opportunities/reranked/{job_id}")
async def reranked_detail(
    job_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.models.outcome_intelligence import OpportunityRerankingRecord
    from src.models.jobs import Job
    from sqlalchemy import select

    rec = (await db.execute(
        select(OpportunityRerankingRecord, Job)
        .join(Job, Job.id == OpportunityRerankingRecord.job_id)
        .where(
            OpportunityRerankingRecord.candidate_id == user["sub"],
            OpportunityRerankingRecord.job_id == job_id,
        )
    )).first()
    if not rec:
        raise HTTPException(404, "No reranking record for this job")

    record, job = rec
    return {
        "job_id": record.job_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "salary_range": job.salary_range,
        "base_score": record.existing_match_score,
        "memory_score": record.memory_affinity_score,
        "urgency_score": record.outcome_success_score,
        "final_score": record.final_opportunity_ranking,
        "explanation": record.explanation,
        "source_url": job.apply_url,
        "why_this_opportunity": _generate_why_this(record, job),
    }


def _generate_why_this(record, job) -> dict:
    reasons = []
    if record.memory_affinity_score > 0.6:
        reasons.append(f"Strong memory affinity ({record.memory_affinity_score:.0%}) — matches your preferences")
    if record.existing_match_score > 70:
        reasons.append(f"High skill match ({record.existing_match_score:.0f}%)")
    for pref in (record.explanation or {}).get("matched_preferences", []):
        reasons.append(f"Matches learned {pref.get('type', 'preference').replace('_', ' ').lower()}: {pref.get('value')}")
    if record.outcome_success_score > 0.6:
        reasons.append(f"Good historical success rate ({record.outcome_success_score:.0%})")
    return {
        "reasons": reasons,
        "formula": "final = base_match × (0.5 + memory/2) × (0.5 + success/2)",
        "score_breakdown": {
            "base_match": record.existing_match_score,
            "memory_multiplier": round(0.5 + record.memory_affinity_score / 2, 3),
            "success_multiplier": round(0.5 + record.outcome_success_score / 2, 3),
        },
    }


# ── Application Lifecycle ───────────────────────────────────────

class LifecycleUpdateRequest(BaseModel):
    job_id: int
    new_state: str
    reason: str = ""
    actor: str = "user"
    confidence: float = Field(0.8, ge=0.0, le=1.0)


@router.post("/application-lifecycle/update")
async def update_lifecycle(
    request: LifecycleUpdateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.enhanced_lifecycle import get_enhanced_lifecycle_service
    svc = get_enhanced_lifecycle_service()
    try:
        result = await svc.transition(
            db,
            candidate_id=user["sub"],
            job_id=request.job_id,
            new_state=request.new_state,
            reason=request.reason or f"Updated to {request.new_state}",
            actor=request.actor,
            confidence=request.confidence,
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/application-lifecycle/history")
async def lifecycle_history(
    job_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.enhanced_lifecycle import get_enhanced_lifecycle_service
    svc = get_enhanced_lifecycle_service()
    history = await svc.get_history(db, candidate_id=user["sub"], job_id=job_id, limit=limit)
    return {"history": history, "total": len(history)}


@router.get("/application-lifecycle/current/{job_id}")
async def lifecycle_current(
    job_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.enhanced_lifecycle import get_enhanced_lifecycle_service
    svc = get_enhanced_lifecycle_service()
    current = await svc.get_current(db, candidate_id=user["sub"], job_id=job_id)
    if not current:
        raise HTTPException(404, "No lifecycle record for this job")
    return current


# ── Career Intelligence ─────────────────────────────────────────

@router.get("/career-intelligence")
async def career_intelligence(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.career_coach_service import get_career_intelligence_service
    svc = get_career_intelligence_service()
    return await svc.compute(db, user["sub"])


@router.get("/career-intelligence/weekly-summary")
async def career_intelligence_weekly(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.career_coach_service import get_career_intelligence_service
    svc = get_career_intelligence_service()
    return await svc.generate_weekly_summary(db, user["sub"])


# ── Career Coach ────────────────────────────────────────────────

@router.get("/career-coach")
async def career_coach_dashboard(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.career_coach_service import get_career_coach_service
    from src.services.intelligence.career_coach_service import get_career_intelligence_service
    coach_svc = get_career_coach_service()
    intel_svc = get_career_intelligence_service()

    plans = await coach_svc.generate_plans(db, user["sub"])
    goals = await coach_svc.generate_goals(db, user["sub"])
    recommendations = await coach_svc.generate_recommendations(db, user["sub"])
    intelligence = await intel_svc.compute(db, user["sub"])

    await db.commit()

    return {
        "intelligence": intelligence,
        "plans": [
            {
                "id": p.id,
                "type": p.plan_type,
                "title": p.title,
                "description": p.description,
                "items": p.items,
                "status": p.status,
                "generated_at": p.generated_at.isoformat(),
            }
            for p in plans
        ],
        "goals": [
            {
                "id": g.id,
                "type": g.goal_type,
                "title": g.title,
                "description": g.description,
                "target_value": g.target_value,
                "current_value": g.current_value,
                "unit": g.unit,
                "status": g.status,
                "priority": g.priority,
            }
            for g in goals
        ],
        "recommendations": [
            {
                "id": r.id,
                "category": r.category,
                "title": r.title,
                "description": r.description,
                "priority": r.priority,
                "status": r.status,
            }
            for r in recommendations
        ],
    }


@router.get("/career-coach/plans")
async def career_coach_plans(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.career_coach_service import get_career_coach_service
    svc = get_career_coach_service()
    plans = await svc.generate_plans(db, user["sub"])
    await db.commit()
    return {
        "plans": [
            {"id": p.id, "type": p.plan_type, "title": p.title, "description": p.description, "items": p.items, "status": p.status}
            for p in plans
        ]
    }


@router.get("/career-coach/goals")
async def career_coach_goals(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.career_coach_service import get_career_coach_service
    svc = get_career_coach_service()
    goals = await svc.generate_goals(db, user["sub"])
    await db.commit()
    return {
        "goals": [
            {"id": g.id, "type": g.goal_type, "title": g.title, "target": g.target_value, "current": g.current_value, "unit": g.unit, "status": g.status}
            for g in goals
        ]
    }


@router.get("/career-coach/recommendations")
async def career_coach_recommendations(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.career_coach_service import get_career_coach_service
    svc = get_career_coach_service()
    recs = await svc.generate_recommendations(db, user["sub"])
    await db.commit()
    return {
        "recommendations": [
            {"id": r.id, "category": r.category, "title": r.title, "description": r.description, "priority": r.priority, "status": r.status}
            for r in recs
        ]
    }


# ── Autonomous Learning Loop ────────────────────────────────────

class LearningLoopRequest(BaseModel):
    job_id: int
    steps: Optional[list] = None


@router.post("/learning-loop/run")
async def run_learning_loop(
    request: LearningLoopRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.learning_loop_service import get_learning_loop_service
    svc = get_learning_loop_service()
    result = await svc.run(db, user_id=user["sub"], job_id=request.job_id, steps_to_run=request.steps)
    await db.commit()
    return result


@router.get("/learning-loop/history")
async def learning_loop_history(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.intelligence.learning_loop_service import get_learning_loop_service
    svc = get_learning_loop_service()
    history = await svc.get_history(db, user_id=user["sub"], limit=limit)
    return {"runs": history, "total": len(history)}
