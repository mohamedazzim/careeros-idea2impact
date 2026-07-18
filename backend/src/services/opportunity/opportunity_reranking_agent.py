"""Memory and outcome-informed opportunity reranking."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.jobs import Job,JobMatch
from src.models.outcome_intelligence import CandidatePreferenceMemory,CareerProgressMetric,OpportunityRerankingRecord
from src.observability.langsmith import traceable
class OpportunityRerankingAgent:
 @traceable(name="opportunity_memory_reranking")
 async def rerank(self,db:AsyncSession,candidate_id:str,limit=100):
  prefs=(await db.execute(select(CandidatePreferenceMemory).where(CandidatePreferenceMemory.candidate_id==candidate_id))).scalars().all()
  progress=(await db.execute(select(CareerProgressMetric).where(CareerProgressMetric.candidate_id==candidate_id))).scalars().all()
  rows=(await db.execute(select(JobMatch,Job).join(Job,Job.id==JobMatch.job_id).where(JobMatch.user_id==candidate_id).limit(limit))).all();out=[]
  for match,job in rows:
   searchable=f"{job.title} {job.company} {job.location}".lower()
   matched_prefs=[p for p in prefs if p.preference_value.lower() in searchable]
   memory=max([p.confidence for p in matched_prefs] or [.5])
   success=max([p.conversion_rate for p in progress if p.dimension_value.lower() in (job.title or "").lower()] or [.5])
   final=round(float(match.overall_score or 0)*(0.5+memory/2)*(0.5+success/2),2)
   rec=(await db.execute(select(OpportunityRerankingRecord).where(OpportunityRerankingRecord.candidate_id==candidate_id,OpportunityRerankingRecord.job_id==job.id))).scalar_one_or_none()
   if not rec:rec=OpportunityRerankingRecord(candidate_id=candidate_id,job_id=job.id,existing_match_score=match.overall_score,memory_affinity_score=memory,outcome_success_score=success,final_opportunity_ranking=final);db.add(rec)
   else:rec.memory_affinity_score=memory;rec.outcome_success_score=success;rec.final_opportunity_ranking=final
   rec.explanation={"formula":"existing_match_score * (0.5 + memory/2) * (0.5 + success/2)","matched_preferences":[{"type":p.preference_type,"value":p.preference_value,"confidence":p.confidence} for p in matched_prefs],"memory_reason":"Matched stored candidate preferences" if matched_prefs else "Neutral memory affinity; no stored preference matched this job"};out.append(rec)
  await db.flush();return out
def get_opportunity_reranking_agent():return OpportunityRerankingAgent()
