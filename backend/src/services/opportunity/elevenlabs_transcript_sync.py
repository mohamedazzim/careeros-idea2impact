"""Production ElevenLabs transcript synchronization with delayed retries."""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.outcome_intelligence import ConversationSession, ConversationSyncJob, ConversationTranscript
from src.services.opportunity.conversation_retrieval_agent import get_conversation_retrieval_agent

class ElevenLabsTranscriptSync:
    MAX_RETRIES=6
    async def sync_one(self, db:AsyncSession, conversation_id:str):
        job=(await db.execute(select(ConversationSyncJob).where(ConversationSyncJob.conversation_id==conversation_id))).scalar_one_or_none()
        if not job: job=ConversationSyncJob(conversation_id=conversation_id); db.add(job); await db.flush()
        if job.status=="COMPLETED": return job
        job.last_attempt_at=datetime.utcnow(); job.retry_count+=1; job.status="RUNNING"
        try:
            session=(await db.execute(select(ConversationSession).where(ConversationSession.conversation_id==conversation_id))).scalar_one()
            await get_conversation_retrieval_agent().retrieve_and_store(db,conversation_id=conversation_id,candidate_id=session.candidate_id)
            job.status="COMPLETED"; job.completed_at=datetime.utcnow(); job.error_message=None
        except Exception as exc:
            job.error_message=str(exc)[:2000]; job.status="PERMANENTLY_FAILED" if job.retry_count>=self.MAX_RETRIES else "RETRY"
        await db.flush(); return job
    async def scan(self,db:AsyncSession,limit:int=50):
        sessions=(await db.execute(select(ConversationSession).outerjoin(ConversationTranscript,ConversationTranscript.conversation_id==ConversationSession.conversation_id).where(ConversationSession.conversation_id.is_not(None),ConversationTranscript.id.is_(None)).limit(limit))).scalars().all()
        return [await self.sync_one(db,s.conversation_id) for s in sessions]
def get_elevenlabs_transcript_sync(): return ElevenLabsTranscriptSync()
