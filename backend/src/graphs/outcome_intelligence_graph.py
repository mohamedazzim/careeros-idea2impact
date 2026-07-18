"""Retry-safe LangGraph workflow for post-call outcome intelligence."""

from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from src.db.session import async_session
from src.models.outcome_intelligence import ConversationSession, OpportunityCallOutcome
from src.services.checkpoint import get_checkpoint_saver
from src.services.opportunity.candidate_memory_agent import get_candidate_memory_agent
from src.services.opportunity.conversation_retrieval_agent import get_conversation_retrieval_agent
from src.services.opportunity.outcome_intelligence_agent import get_outcome_intelligence_agent
from src.observability.langsmith import traceable


@traceable(name="outcome_graph_conversation_retrieval")
async def retrieve_conversation(state: Dict[str, Any]) -> Dict[str, Any]:
    async with async_session() as db:
        transcript = await get_conversation_retrieval_agent().retrieve_and_store(
            db, conversation_id=state["conversation_id"], candidate_id=state["candidate_id"]
        )
        await db.commit()
        return {**state, "raw_transcript": transcript.raw_transcript, "speaker_turns": transcript.speaker_turns or []}


@traceable(name="outcome_graph_classification")
async def classify_outcome(state: Dict[str, Any]) -> Dict[str, Any]:
    outcome = await get_outcome_intelligence_agent().classify(state["raw_transcript"])
    return {**state, "classification": outcome.model_dump()}


@traceable(name="outcome_graph_concern_extraction")
async def extract_concerns(state: Dict[str, Any]) -> Dict[str, Any]:
    async with async_session() as db:
        concerns = await get_candidate_memory_agent().extract_concerns(
            db, candidate_id=state["candidate_id"], conversation_id=state["conversation_id"],
            transcript=state["raw_transcript"],
        )
        await db.commit()
        return {**state, "concerns": [row.concern_type for row in concerns]}


@traceable(name="outcome_graph_memory_update")
async def update_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    from src.services.intelligence.enhanced_candidate_memory import get_enhanced_candidate_memory_agent
    async with async_session() as db:
        session = (await db.execute(select(ConversationSession).where(
            ConversationSession.conversation_id == state["conversation_id"]
        ))).scalar_one()
        candidate_transcript = "\n".join(
            f"{turn.get('speaker', 'user')}: {turn.get('text', '')}"
            for turn in state.get("speaker_turns", [])
            if str(turn.get("speaker", "")).lower() in {"user", "candidate"}
        )
        rows = await get_enhanced_candidate_memory_agent().extract_preferences_from_transcript(
            db, candidate_id=state["candidate_id"], conversation_id=state["conversation_id"],
            transcript=candidate_transcript,
            job_title=session.job_title, company=session.company,
        )
        await db.commit()
        return {**state, "memory_updates": len(rows)}


@traceable(name="outcome_graph_persistence")
async def persist_outcome(state: Dict[str, Any]) -> Dict[str, Any]:
    async with async_session() as db:
        existing = (await db.execute(select(OpportunityCallOutcome).where(
            OpportunityCallOutcome.conversation_id == state["conversation_id"]
        ))).scalar_one_or_none()
        if not existing:
            session = (await db.execute(select(ConversationSession).where(
                ConversationSession.conversation_id == state["conversation_id"]
            ))).scalar_one()
            data = state["classification"]
            existing = OpportunityCallOutcome(
                candidate_id=state["candidate_id"], job_id=session.job_id, conversation_id=state["conversation_id"],
                call_sid=session.call_sid, outcome=data["outcome"], interest_level=data["interest_level"],
                primary_concern=data.get("primary_concern"), followup_required=data["followup_required"],
                summary=data["summary"], confidence=data["confidence"],
            )
            db.add(existing)
        await db.flush()
        from src.services.opportunity.followup_agent import get_followup_agent
        from src.services.opportunity.application_lifecycle_agent import get_application_lifecycle_agent, OUTCOME_STATES
        from src.services.opportunity.career_progress_agent import get_career_progress_agent
        from src.services.opportunity.opportunity_reranking_agent import get_opportunity_reranking_agent
        followup = await get_followup_agent().plan(db, existing)
        if existing.job_id and existing.outcome in OUTCOME_STATES:
            await get_application_lifecycle_agent().transition(db,candidate_id=existing.candidate_id,job_id=existing.job_id,state=OUTCOME_STATES[existing.outcome],reason=f"Conversation outcome: {existing.outcome}",confidence=existing.confidence)
        await get_career_progress_agent().refresh(db,existing.candidate_id)
        await get_opportunity_reranking_agent().rerank(db,existing.candidate_id)
        await db.commit()
        return {**state, "status": "completed", "followup_task_id": followup.id}


def build_outcome_intelligence_graph():
    workflow = StateGraph(dict)
    nodes = [
        ("conversation_retrieval", retrieve_conversation), ("outcome_classification", classify_outcome),
        ("concern_extraction", extract_concerns), ("memory_update", update_memory), ("persistence", persist_outcome),
    ]
    for name, function in nodes:
        workflow.add_node(name, function)
    workflow.add_edge(START, "conversation_retrieval")
    workflow.add_edge("conversation_retrieval", "outcome_classification")
    workflow.add_edge("outcome_classification", "concern_extraction")
    workflow.add_edge("concern_extraction", "memory_update")
    workflow.add_edge("memory_update", "persistence")
    workflow.add_edge("persistence", END)
    return workflow.compile(checkpointer=get_checkpoint_saver())


_graph = None


def get_outcome_intelligence_graph():
    global _graph
    if _graph is None:
        _graph = build_outcome_intelligence_graph()
    return _graph
