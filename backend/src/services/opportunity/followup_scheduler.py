"""Executes due follow-up tasks through the existing communication orchestrator."""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.outcome_intelligence import FollowupTask
from src.models.jobs import CommunicationRequest
import uuid
class FollowupScheduler:
 async def execute(self,db:AsyncSession,task:FollowupTask):
  if task.status in {"COMPLETED","CLOSED"}:return task
  channel={"FOLLOW_UP_CALL":"VOICE_CALL","FOLLOW_UP_SMS":"SMS","FOLLOW_UP_EMAIL":"EMAIL","WAIT":"DASHBOARD_ONLY"}.get(task.action,"DASHBOARD_ONLY")
  request=CommunicationRequest(correlation_id=str(uuid.uuid4()),user_id=task.candidate_id,job_id=task.job_id,opportunity_id=task.conversation_id,channel=channel,communication_status="queued",communication_provider="career_os_followup",decision_reason=f"Scheduled follow-up: {task.action}",decision_factors={"conversation_id":task.conversation_id,"scheduled_for":task.scheduled_for.isoformat()},decision_confidence=.9)
  db.add(request);await db.flush()
  task.status="COMPLETED";task.executed_at=datetime.utcnow();task.result={**(task.result or {}),"executed":True,"communication_request_id":request.id,"delivery":"queued_for_existing_communication_orchestrator"}
  await db.flush();return task
 async def run_due(self,db:AsyncSession,limit=50):
  rows=(await db.execute(select(FollowupTask).where(FollowupTask.status=="PENDING",FollowupTask.scheduled_for<=datetime.utcnow()).limit(limit))).scalars().all()
  return [await self.execute(db,r) for r in rows]
def get_followup_scheduler():return FollowupScheduler()
