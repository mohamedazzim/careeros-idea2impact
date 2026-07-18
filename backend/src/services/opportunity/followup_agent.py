"""Outcome-driven, idempotent follow-up planning."""
from datetime import datetime,timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.outcome_intelligence import FollowupTask,OpportunityCallOutcome
from src.observability.langsmith import traceable
RULES={"APPLYING":("FOLLOW_UP_EMAIL",48),"INTERESTED":("FOLLOW_UP_SMS",72),"MAYBE_LATER":("WAIT",72),"REQUEST_FOLLOWUP":("FOLLOW_UP_CALL",1),"NOT_INTERESTED":("CLOSE",0),"NOT_QUALIFIED":("CLOSE",0)}
class FollowupAgent:
 @traceable(name="followup_agent",metadata={"candidate_id_masked":True})
 async def plan(self,db:AsyncSession,outcome:OpportunityCallOutcome):
  action,hours=RULES[outcome.outcome]
  existing=(await db.execute(select(FollowupTask).where(FollowupTask.candidate_id==outcome.candidate_id,FollowupTask.conversation_id==outcome.conversation_id,FollowupTask.action==action))).scalar_one_or_none()
  if existing:return existing
  row=FollowupTask(candidate_id=outcome.candidate_id,job_id=outcome.job_id,conversation_id=outcome.conversation_id,action=action,status="CLOSED" if action=="CLOSE" else "PENDING",scheduled_for=datetime.utcnow()+timedelta(hours=hours),result={"reason":outcome.outcome,"priority":"HIGH" if outcome.outcome=="REQUEST_FOLLOWUP" else "NORMAL"})
  db.add(row);await db.flush();return row
def get_followup_agent():return FollowupAgent()
