"""Idempotent ElevenLabs conversation and transcript retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.outcome_intelligence import ConversationSession, ConversationTranscript
from src.observability.langsmith import traceable


class ConversationRetrievalAgent:
    async def capture_session(
        self, db: AsyncSession, *, candidate_id: str, job_id: int | None, job_title: str,
        company: str, conversation_id: str | None, call_sid: str | None, agent_id: str | None = None,
    ) -> ConversationSession:
        existing = None
        if conversation_id:
            existing = (await db.execute(select(ConversationSession).where(
                ConversationSession.conversation_id == conversation_id
            ))).scalar_one_or_none()
        if not existing and call_sid:
            existing = (await db.execute(select(ConversationSession).where(
                ConversationSession.call_sid == call_sid
            ))).scalars().first()
        if existing:
            existing.conversation_id = existing.conversation_id or conversation_id
            existing.call_sid = existing.call_sid or call_sid
            return existing
        row = ConversationSession(
            candidate_id=candidate_id, job_id=job_id, conversation_id=conversation_id, call_sid=call_sid,
            agent_id=agent_id, job_title=job_title, company=company, started_at=datetime.utcnow(), status="INITIATED",
        )
        db.add(row)
        await db.flush()
        return row

    @traceable(name="elevenlabs_transcript_sync", metadata={"provider": "elevenlabs"})
    async def retrieve_and_store(
        self, db: AsyncSession, *, conversation_id: str, candidate_id: str,
    ) -> ConversationTranscript:
        existing = (await db.execute(select(ConversationTranscript).where(
            ConversationTranscript.conversation_id == conversation_id
        ))).scalar_one_or_none()
        if existing:
            return existing

        payload = await self._retrieve(conversation_id)
        turns = self._speaker_turns(payload)
        raw = "\n".join(f"{turn['speaker']}: {turn['text']}" for turn in turns)
        transcript = ConversationTranscript(
            conversation_id=conversation_id, candidate_id=candidate_id,
            raw_transcript=raw, speaker_turns=turns, provider_metadata=self._safe_metadata(payload),
        )
        db.add(transcript)
        session = (await db.execute(select(ConversationSession).where(
            ConversationSession.conversation_id == conversation_id
        ))).scalar_one_or_none()
        if session:
            metadata = payload.get("metadata") or {}
            session.status = str(payload.get("status") or "COMPLETED").upper()
            session.ended_at = datetime.utcnow()
            session.duration_seconds = metadata.get("call_duration_secs") or metadata.get("duration_seconds")
        await db.flush()
        return transcript

    async def _retrieve(self, conversation_id: str) -> Dict[str, Any]:
        if not settings.ELEVENLABS_API_KEY:
            raise RuntimeError("ELEVENLABS_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}",
                headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _speaker_turns(payload: Dict[str, Any]) -> list[Dict[str, str]]:
        source = payload.get("transcript") or payload.get("conversation", {}).get("transcript") or []
        turns = []
        for item in source:
            if not isinstance(item, dict):
                continue
            text = str(item.get("message") or item.get("text") or "").strip()
            if text:
                turns.append({"speaker": str(item.get("role") or item.get("speaker") or "unknown"), "text": text})
        return turns

    @staticmethod
    def _safe_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "conversation_id": payload.get("conversation_id"),
            "agent_id": payload.get("agent_id"),
            "status": payload.get("status"),
            "metadata": payload.get("metadata"),
            "analysis": payload.get("analysis"),
        }


def get_conversation_retrieval_agent() -> ConversationRetrievalAgent:
    return ConversationRetrievalAgent()
