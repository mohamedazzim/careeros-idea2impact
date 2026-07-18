"""Authenticated autonomous engagement APIs."""
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import desc,select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_current_user
from src.db.session import get_db
from src.models.outcome_intelligence import FollowupTask,ApplicationLifecycle,CareerProgressMetric,OpportunityRerankingRecord
router=APIRouter(tags=["Autonomous Engagement"])
@router.get("/followups")
async def followups(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),user:dict=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 rows=(await db.execute(select(FollowupTask).where(FollowupTask.candidate_id==user["sub"]).order_by(desc(FollowupTask.scheduled_for)).offset((page-1)*page_size).limit(page_size))).scalars().all()
 return {"items":[{"id":r.id,"job_id":r.job_id,"action":r.action,"status":r.status,"scheduled_for":r.scheduled_for.isoformat(),"result":r.result} for r in rows]}
@router.post("/followups/{task_id}/execute")
async def execute_followup(task_id:int,user:dict=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 row=(await db.execute(select(FollowupTask).where(FollowupTask.id==task_id,FollowupTask.candidate_id==user["sub"]))).scalar_one_or_none()
 if not row:raise HTTPException(404,"Follow-up task not found")
 from src.services.opportunity.followup_scheduler import get_followup_scheduler
 await get_followup_scheduler().execute(db,row);await db.commit();return {"id":row.id,"status":row.status}
@router.get("/application-lifecycle")
async def lifecycles(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),user:dict=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 rows=(await db.execute(select(ApplicationLifecycle).where(ApplicationLifecycle.candidate_id==user["sub"]).order_by(desc(ApplicationLifecycle.updated_at)).offset((page-1)*page_size).limit(page_size))).scalars().all()
 return {"items":[_life(r) for r in rows]}
@router.get("/application-lifecycle/{job_id}")
async def lifecycle(job_id:int,user:dict=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 row=(await db.execute(select(ApplicationLifecycle).where(ApplicationLifecycle.candidate_id==user["sub"],ApplicationLifecycle.job_id==job_id))).scalar_one_or_none()
 if not row:raise HTTPException(404,"Lifecycle not found")
 return _life(row)
@router.get("/career-progress")
async def progress(user:dict=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 rows=(await db.execute(select(CareerProgressMetric).where(CareerProgressMetric.candidate_id==user["sub"]).order_by(desc(CareerProgressMetric.conversion_rate)))).scalars().all()
 return {"items":[{"dimension":r.dimension,"value":r.dimension_value,"engagements":r.engagement_count,"conversions":r.conversion_count,"conversion_rate":r.conversion_rate} for r in rows]}
@router.get("/opportunity-reranking")
async def reranking(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),user:dict=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 rows=(await db.execute(select(OpportunityRerankingRecord).where(OpportunityRerankingRecord.candidate_id==user["sub"]).order_by(desc(OpportunityRerankingRecord.final_opportunity_ranking)).offset((page-1)*page_size).limit(page_size))).scalars().all()
 return {"items":[{"job_id":r.job_id,"match_score":r.existing_match_score,"memory_affinity":r.memory_affinity_score,"outcome_success":r.outcome_success_score,"final_ranking":r.final_opportunity_ranking,"explanation":r.explanation} for r in rows]}
def _life(r):return {"job_id":r.job_id,"state":r.state,"reason":r.reason,"confidence":r.confidence,"updated_at":r.updated_at.isoformat()}
