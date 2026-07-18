"""Career conversion metrics learned from lifecycle outcomes."""
from datetime import datetime
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.jobs import Job
from src.models.outcome_intelligence import ApplicationLifecycle,CareerProgressMetric
class CareerProgressAgent:
 async def refresh(self,db:AsyncSession,candidate_id:str):
  rows=(await db.execute(select(Job.title,func.count(ApplicationLifecycle.id),func.count(ApplicationLifecycle.id).filter(ApplicationLifecycle.state.in_(["APPLIED","INTERVIEW_SCHEDULED","OFFER_RECEIVED","OFFER_ACCEPTED"]))).join(ApplicationLifecycle,ApplicationLifecycle.job_id==Job.id).where(ApplicationLifecycle.candidate_id==candidate_id).group_by(Job.title))).all()
  result=[]
  for value,total,converted in rows:
   metric=(await db.execute(select(CareerProgressMetric).where(CareerProgressMetric.candidate_id==candidate_id,CareerProgressMetric.dimension=="ROLE",CareerProgressMetric.dimension_value==value))).scalar_one_or_none()
   if not metric:metric=CareerProgressMetric(candidate_id=candidate_id,dimension="ROLE",dimension_value=value);db.add(metric)
   metric.engagement_count=total;metric.conversion_count=converted;metric.conversion_rate=converted/total if total else 0;metric.calculated_at=datetime.utcnow();result.append(metric)
  await db.flush();return result
def get_career_progress_agent():return CareerProgressAgent()
