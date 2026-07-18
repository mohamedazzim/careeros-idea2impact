"""Phase 7 — Live Interview API Endpoints.

RESTful endpoints for starting, responding to, pausing, and replaying
real-time AI interview sessions.
"""

import time
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db
from src.db.repositories.domain_repositories import (
    InterviewSessionRepository, InterviewQuestionRepository, InterviewWeaknessRepository,
)

router = APIRouter(prefix="/interview", tags=["Interview"])

logger = logging.getLogger(__name__)


class StartInterviewRequest(BaseModel):
    interview_type: str = Field("technical", description="technical, behavioral, system_design, coding, hr, faang")
    mode: str = Field("voice", description="voice or text")
    resume_context: Optional[Dict[str, Any]] = Field(None)


class InterviewResponseRequest(BaseModel):
    session_uid: str = Field(..., min_length=1)
    transcript: str = Field(..., min_length=1)


class InterviewReplayResponse(BaseModel):
    session_uid: str
    interview_type: str
    transcript: List[Dict[str, Any]]
    evaluations: List[Dict[str, Any]]
    scores: List[float]
    stage: str


@router.post("/start")
async def start_interview(request: StartInterviewRequest, user: dict = Depends(get_current_user)):
    """Start a new live AI interview session."""
    from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator

    orch = get_live_interview_orchestrator()
    session = await orch.create_session(
        user_id=user["sub"],
        interview_type=request.interview_type,
        resume_context=request.resume_context,
        mode=request.mode,
    )
    first_question = await orch.start_interview(session.session_uid)

    return {
        "session_uid": session.session_uid,
        "interview_type": request.interview_type,
        "mode": request.mode,
        "first_question": first_question,
        "total_questions": session.state.total_questions,
        "status": "started",
    }


@router.post("/respond")
async def interview_respond(request: InterviewResponseRequest):
    """Submit user response to the current interview question."""
    from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
    from src.interview_runtime.governance import get_realtime_governance

    # Safety check before processing
    guard = get_realtime_governance()
    safety = await guard.check_message(request.session_uid, request.transcript)
    if not safety.get("allowed", True):
        raise HTTPException(status_code=400, detail={
            "message": "Message flagged by safety system",
            "violations": safety.get("violations", []),
        })

    orch = get_live_interview_orchestrator()
    result = await orch.process_user_response(request.session_uid, request.transcript)

    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result)

    return result


@router.get("/status/{session_uid}")
async def interview_status(session_uid: str):
    """Get current interview session status."""
    from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
    orch = get_live_interview_orchestrator()
    status = await orch.get_status(session_uid)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found")
    return status


@router.post("/pause/{session_uid}")
async def pause_interview(session_uid: str):
    """Pause an active interview session."""
    from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
    orch = get_live_interview_orchestrator()
    ok = await orch.pause_session(session_uid)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found or not active")
    return {"session_uid": session_uid, "status": "paused"}


@router.post("/resume/{session_uid}")
async def resume_interview(session_uid: str):
    """Resume a paused interview session."""
    from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
    orch = get_live_interview_orchestrator()
    ok = await orch.resume_session(session_uid)
    if not ok:
        raise HTTPException(status_code=400, detail="Session not paused or not found")
    return {"session_uid": session_uid, "status": "resumed"}


@router.post("/interrupt/{session_uid}")
async def interrupt_interview(session_uid: str):
    """Handle a user interruption (e.g., barge-in)."""
    from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
    orch = get_live_interview_orchestrator()
    result = await orch.handle_interruption(session_uid)
    return result


@router.get("/replay/{session_uid}")
async def interview_replay(session_uid: str):
    """Get full interview replay data (transcript, scores, timeline)."""
    from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
    orch = get_live_interview_orchestrator()
    replay = await orch.get_replay(session_uid)
    if not replay:
        raise HTTPException(status_code=404, detail="Session not found")
    return replay


@router.post("/kill/{session_uid}")
async def kill_interview(session_uid: str, reason: str = Query("admin_override")):
    """Emergency kill-switch for an interview session."""
    from src.interview_runtime.governance import get_realtime_governance
    guard = get_realtime_governance()
    ok = await guard.kill_session(session_uid, reason)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_uid": session_uid, "status": "killed", "reason": reason}


@router.get("/history")
async def interview_history(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """List past interview sessions for a user."""
    repo = InterviewSessionRepository(db)
    sessions = await repo.find_by_user(user["sub"])
    return {
        "sessions": [
            {
                "session_uid": s.session_uid,
                "interview_type": s.interview_type,
                "status": s.status,
                "difficulty_level": s.difficulty_level,
                "difficulty": s.difficulty_level,
                "total_score": s.total_score,
                "overall_score": s.total_score,
                "current_question_index": s.current_question_index,
                "total_questions": s.current_question_index,
                "job_title": s.metadata_.get("job_title", "Interview Session") if s.metadata_ else "Interview Session",
                "company_name": s.metadata_.get("company_name", "") if s.metadata_ else "",
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "started_at": s.created_at.isoformat() if s.created_at else None,
                "closed_at": s.closed_at.isoformat() if s.closed_at else None,
            }
            for s in sessions
        ],
        "total": len(sessions),
    }


@router.get("/memory")
async def interview_memory(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """Fetch career memory vault — longitudinal weakness patterns and strengths."""
    repo = InterviewWeaknessRepository(db)
    weaknesses = await repo.find_by_user(user["sub"])
    return {
        "user_id": user["sub"],
        "memories": [
            {
                "memory_type": "weakness" if w.severity and w.severity != "low" else "strength",
                "content": f"{w.weakness_type}: {w.pattern_classification or 'identified'} (severity: {w.severity})",
                "weakness_type": w.weakness_type,
                "occurrences": w.occurrences,
                "severity": w.severity,
            }
            for w in weaknesses
        ],
        "events": [
            {
                "event_type": w.weakness_type.replace(" ", "_").lower(),
                "summary": f"Detected {w.weakness_type} pattern with severity {w.severity} across {w.occurrences} sessions",
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w in weaknesses
        ],
        "total_patterns": len(weaknesses),
    }


@router.post("/end")
async def end_interview(session_uid: str, user: dict = Depends(get_current_user)):
    """End active interview session and compute final scores."""
    try:
        from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
        orch = get_live_interview_orchestrator()
        await orch.pause_session(session_uid)
        status = await orch.get_status(session_uid)

        # Force persist to PostgreSQL on manual end
        session = orch._sessions.get(session_uid)
        if session:
            avg_score = sum(session.state.scores)/len(session.state.scores) if session.state.scores else 0
            result = {"session_uid": session_uid, "status": "completed", "average_score": avg_score,
                      "total_score": avg_score, "interview_type": session.interview_type}
            await orch._persist_interview(session, result)
            if hasattr(orch, '_close_interview'):
                await orch._close_interview(session)
            else:
                session.active = False

        return {
            "session_uid": session_uid,
            "status": "ended",
            "final_score": status.get("scores", {}).get("overall", 0) if status else 0,
        }
    except Exception:
        return {"session_uid": session_uid, "status": "ended", "final_score": 0}


@router.get("/report/{session_uid}")
async def interview_report(session_uid: str, db: AsyncSession = Depends(get_db)):
    """Fetch session report."""
    try:
        from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
        orch = get_live_interview_orchestrator()
        replay = await orch.get_replay(session_uid)
        if replay:
            return {
                "session_uid": session_uid,
                "messages": replay.get("transcript", []),
                "feedbacks": replay.get("evaluations", []),
                "overall_score": replay.get("scores", {}).get("overall", 0),
                "job_title": "Interview Session",
                "company_name": "",
                "started_at": None,
                "report_content": "",
            }
    except Exception:
        pass

    repo = InterviewSessionRepository(db)
    session = await repo.get_by_uid(session_uid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    q_repo = InterviewQuestionRepository(db)
    questions = await q_repo.find_by_session(session.id)

    return {
        "session_uid": session_uid,
        "messages": [
            {"id": q.id, "role": "user", "message": q.answer_text, "question": q.question_text,
             "overall_score": q.score, "technical_score": q.score, "communication_score": q.rubric_scores.get("communication", 0) if q.rubric_scores else 0,
             "confidence_score": q.rubric_scores.get("confidence", 0) if q.rubric_scores else 0,
             "relevance_score": q.score}
            for q in questions
        ],
        "feedbacks": [
            {"id": q.id, "question_id": q.id, "score": q.score, "strengths": q.strengths, "weaknesses": q.weaknesses,
             "technical_score": q.score, "communication_score": q.rubric_scores.get("communication", 0) if q.rubric_scores else 0,
             "confidence_score": q.rubric_scores.get("confidence", 0) if q.rubric_scores else 0,
             "relevance_score": q.score}
            for q in questions
        ],
        "overall_score": session.total_score or 0,
        "job_title": session.metadata_.get("job_title", "Interview Session") if session.metadata_ else "Interview Session",
        "company_name": session.metadata_.get("company_name", "") if session.metadata_ else "",
        "started_at": session.created_at.isoformat() if session.created_at else None,
        "report_content": "",
    }


@router.delete("/session/{session_uid}")
async def delete_interview_session(session_uid: str, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """Soft-delete an interview session record."""
    repo = InterviewSessionRepository(db)
    session = await repo.get_by_uid(session_uid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await repo.soft_delete(session.id)
    return {"session_uid": session_uid, "status": "deleted"}


@router.get("/intelligence")
async def interview_intelligence(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """Fetch comprehensive interview intelligence: trends, categories, progression, and improvement score."""
    from src.models.interview import InterviewSession, InterviewQuestion, InterviewWeaknessHistory
    from sqlalchemy import select, desc
    
    user_id = user["sub"]
    
    # 1. Fetch all completed sessions for this user
    sessions_stmt = select(InterviewSession).where(
        InterviewSession.user_id == user_id,
        InterviewSession.status == "completed",
        InterviewSession.deleted_at.is_(None)
    ).order_by(desc(InterviewSession.created_at))
    sessions_result = await db.execute(sessions_stmt)
    sessions = sessions_result.scalars().all()
    
    # 2. Weakness & Strength Trends
    weaknesses_stmt = select(InterviewWeaknessHistory).where(
        InterviewWeaknessHistory.user_id == user_id,
        InterviewWeaknessHistory.deleted_at.is_(None)
    ).order_by(desc(InterviewWeaknessHistory.occurrences))
    weaknesses_result = await db.execute(weaknesses_stmt)
    weaknesses = weaknesses_result.scalars().all()
    
    weakness_trends = [
        {
            "type": w.weakness_type,
            "occurrences": w.occurrences,
            "severity": w.severity,
            "classification": w.pattern_classification,
            "trend": "improving" if w.severity == "low" else "stable" if w.severity == "medium" else "needs_attention"
        }
        for w in weaknesses if w.severity in ["medium", "high"] or w.occurrences > 1
    ]
    
    strength_trends = [
        {
            "type": w.weakness_type,
            "occurrences": w.occurrences,
            "classification": w.pattern_classification,
            "trend": "mastered"
        }
        for w in weaknesses if w.severity == "low" and w.occurrences >= 2
    ]
    
    # 3. Question Categories & Difficulty Progression
    categories = {}
    difficulty_progression = []
    
    for session in sessions:
        q_stmt = select(InterviewQuestion).where(
            InterviewQuestion.session_id == session.id,
            InterviewQuestion.deleted_at.is_(None)
        ).order_by(InterviewQuestion.question_index)
        q_result = await db.execute(q_stmt)
        questions = q_result.scalars().all()
        
        for q in questions:
            # Extract category from question text (simple heuristic)
            q_lower = q.question_text.lower()
            if "system design" in q_lower or "architecture" in q_lower:
                cat = "system_design"
            elif "behavioral" in q_lower or "team" in q_lower or "conflict" in q_lower:
                cat = "behavioral"
            elif "code" in q_lower or "algorithm" in q_lower or "python" in q_lower or "java" in q_lower:
                cat = "coding"
            else:
                cat = "technical"
                
            categories[cat] = categories.get(cat, 0) + 1
            
        if questions:
            avg_difficulty = sum(1 for q in questions if q.difficulty_level == "advanced") / len(questions)
            avg_score = sum(q.score for q in questions) / len(questions)
            difficulty_progression.append({
                "session_uid": session.session_uid,
                "date": session.created_at.isoformat() if session.created_at else "",
                "difficulty_level": session.difficulty_level,
                "advanced_ratio": round(avg_difficulty, 2),
                "avg_score": round(avg_score, 1),
                "total_score": session.total_score or 0
            })
            
    # 4. Session Comparison & Improvement Score
    improvement_score = 0.0
    if len(sessions) >= 2:
        first_session_score = sessions[-1].total_score or 0
        last_session_score = sessions[0].total_score or 0
        if first_session_score > 0:
            improvement_score = round(((last_session_score - first_session_score) / first_session_score) * 100, 1)
            
    session_comparison = [
        {
            "session_uid": s.session_uid,
            "type": s.interview_type,
            "date": s.created_at.isoformat() if s.created_at else "",
            "score": s.total_score or 0,
            "difficulty": s.difficulty_level
        }
        for s in sessions[:5]  # Last 5 sessions
    ]
    
    return {
        "user_id": user_id,
        "total_completed_sessions": len(sessions),
        "weakness_trends": weakness_trends,
        "strength_trends": strength_trends,
        "question_categories": categories,
        "difficulty_progression": difficulty_progression,
        "session_comparison": session_comparison,
        "improvement_score": improvement_score,
        "improvement_trend": "positive" if improvement_score > 0 else "negative" if improvement_score < 0 else "stable"
    }


@router.get("/health")
async def interview_health():
    """Interview subsystem health check."""
    from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
    orch = get_live_interview_orchestrator()
    session_count = len(orch._sessions)
    active_count = sum(1 for s in orch._sessions.values() if s.active)
    return {
        "status": "healthy",
        "active_sessions": active_count,
        "total_sessions": session_count,
        "timestamp": time.time(),
    }
