"""Authenticated Phase 2 outcome intelligence dashboard APIs."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db
from src.models.outcome_intelligence import (
    CandidateConcern, CandidatePreferenceMemory, ConversationSession, ConversationTranscript, OpportunityCallOutcome,
)
from src.schemas.outcome_intelligence import ProcessConversationRequest

router = APIRouter(tags=["Outcome Intelligence"])


def _assert_owner(candidate_id: str, user: dict) -> None:
    if candidate_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Candidate access denied")


@router.get("/outcomes")
async def list_outcomes(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                        user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(OpportunityCallOutcome).where(
        OpportunityCallOutcome.candidate_id == user["sub"]
    ).order_by(desc(OpportunityCallOutcome.created_at)).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [_outcome(row) for row in rows], "page": page, "page_size": page_size}


@router.get("/outcomes/{candidate_id}")
async def candidate_outcomes(candidate_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                             user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _assert_owner(candidate_id, user)
    return await list_outcomes(page, page_size, user, db)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = (await db.execute(select(ConversationSession).where(
        ConversationSession.conversation_id == conversation_id, ConversationSession.candidate_id == user["sub"]
    ))).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found")
    transcript = (await db.execute(select(ConversationTranscript).where(
        ConversationTranscript.conversation_id == conversation_id
    ))).scalar_one_or_none()
    return {"session": _session(session), "transcript": transcript.raw_transcript if transcript else None,
            "speaker_turns": transcript.speaker_turns if transcript else []}


@router.post("/conversations/process")
async def process_conversation(request: ProcessConversationRequest, user: dict = Depends(get_current_user),
                               db: AsyncSession = Depends(get_db)):
    session = (await db.execute(select(ConversationSession).where(
        ConversationSession.conversation_id == request.conversation_id,
        ConversationSession.candidate_id == user["sub"],
    ))).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found")
    from src.graphs.outcome_intelligence_graph import get_outcome_intelligence_graph
    result = await get_outcome_intelligence_graph().ainvoke(
        {"conversation_id": request.conversation_id, "candidate_id": user["sub"]},
        config={"configurable": {"thread_id": f"outcome:{request.conversation_id}"}},
    )
    return {"conversation_id": request.conversation_id, "status": result.get("status"), "classification": result.get("classification")}


@router.get("/candidate-memory/{candidate_id}")
async def candidate_memory(candidate_id: str, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
                           user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _assert_owner(candidate_id, user)
    rows = (await db.execute(select(CandidatePreferenceMemory).where(
        CandidatePreferenceMemory.candidate_id == candidate_id
    ).order_by(desc(CandidatePreferenceMemory.confidence)).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [{"type": r.preference_type, "value": r.preference_value, "confidence": r.confidence,
                       "evidence": r.evidence, "updated_at": r.updated_at.isoformat()} for r in rows]}


@router.get("/candidate-concerns/{candidate_id}")
async def candidate_concerns(candidate_id: str, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
                             user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _assert_owner(candidate_id, user)
    rows = (await db.execute(select(CandidateConcern).where(
        CandidateConcern.candidate_id == candidate_id
    ).order_by(desc(CandidateConcern.created_at)).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [{"conversation_id": r.conversation_id, "type": r.concern_type, "confidence": r.confidence,
                       "evidence": r.evidence, "created_at": r.created_at.isoformat()} for r in rows]}


def _outcome(row: OpportunityCallOutcome) -> dict:
    return {"id": row.id, "job_id": row.job_id, "conversation_id": row.conversation_id, "outcome": row.outcome,
            "interest_level": row.interest_level, "primary_concern": row.primary_concern,
            "followup_required": row.followup_required, "summary": row.summary, "confidence": row.confidence,
            "created_at": row.created_at.isoformat()}


def _session(row: ConversationSession) -> dict:
    return {"conversation_id": row.conversation_id, "call_sid": row.call_sid, "job_id": row.job_id,
            "job_title": row.job_title, "company": row.company, "status": row.status,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "ended_at": row.ended_at.isoformat() if row.ended_at else None, "duration_seconds": row.duration_seconds}
