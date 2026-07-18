"""Application lifecycle transitions driven by real outcomes."""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.outcome_intelligence import ApplicationLifecycle
from src.observability.langsmith import traceable
OUTCOME_STATES={"APPLYING":"APPLYING","INTERESTED":"INTERESTED","NOT_INTERESTED":"CLOSED","NOT_QUALIFIED":"CLOSED"}
class ApplicationLifecycleAgent:
 @traceable(name="application_lifecycle_agent",metadata={"candidate_id_masked":True})
 async def transition(self,db:AsyncSession,*,candidate_id:str,job_id:int,state:str,reason:str,confidence:float=.8):
  row=(await db.execute(select(ApplicationLifecycle).where(ApplicationLifecycle.candidate_id==candidate_id,ApplicationLifecycle.job_id==job_id))).scalar_one_or_none()
  if not row:row=ApplicationLifecycle(candidate_id=candidate_id,job_id=job_id,state=state,reason=reason,confidence=confidence);db.add(row)
  else:row.state=state;row.reason=reason;row.confidence=confidence;row.updated_at=datetime.utcnow()
  await db.flush();return row
def get_application_lifecycle_agent():return ApplicationLifecycleAgent()
