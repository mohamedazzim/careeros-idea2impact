"""Phase 17.5 — Jobs Intelligence Endpoints.

Endpoints: GET /jobs, GET /jobs/stats, GET /jobs/:id, POST /jobs/refresh
Phase 17.7 — Hardened: Uses JobRepository, no in-memory fallbacks, no demo data.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.session import get_db
from src.db.repositories.domain_repositories import JobRepository
from src.api.deps import get_current_user
from src.observability.logger import structured_logger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs"])
JOB_SORT_OPTIONS = {
    "best_match",
    "posted_at_desc",
    "fetched_at_desc",
    "freshness_desc",
    "company_asc",
}


def _utc_iso(value: datetime | None) -> str | None:
    """Serialize job timestamps as explicit UTC to avoid browser timezone drift."""
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


REAL_PROVIDER_CATALOG = [
    {"name": name, "display_name": name.title(), "supported_mode": "direct_provider_api"}
    for name in ["theirstack", "remoteok", "arbeitnow", "adzuna", "usajobs", "greenhouse", "lever"]
]


class JobResponse(BaseModel):
    id: int = 0
    job_uid: str = ""
    title: str = ""
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    full_description: Optional[str] = None
    source: str = "linkedin"
    source_provider: Optional[str] = None
    source_job_id: Optional[str] = None
    source_url: Optional[str] = None
    apply_url: Optional[str] = None
    url_type: str = "direct"
    posted_date: Optional[str] = None
    fetched_at: Optional[str] = None
    salary_range: Optional[str] = None
    salary: Optional[str] = None
    skills_required: Optional[list] = None
    extracted_skills: Optional[list] = None
    freshness_score: Optional[float] = None
    freshness_bucket: Optional[str] = None
    provider_quality_score: Optional[float] = None
    salary_quality_score: Optional[float] = None
    opportunity_priority_score: Optional[float] = None
    lifecycle_state: Optional[str] = None
    apply_url_valid: Optional[bool] = None
    is_india_eligible: Optional[bool] = None
    is_tech_role: Optional[bool] = None
    tech_role_category: Optional[str] = None
    tech_role_confidence: Optional[float] = None
    seniority_level: Optional[str] = None
    experience_min_years: Optional[float] = None
    experience_max_years: Optional[float] = None
    experience_filter_status: Optional[str] = None
    match_score: Optional[float] = None
    match_details: Optional[Dict[str, Any]] = None
    match: Optional[Dict[str, Any]] = None
    status: str = "active"
    ingested_at: Optional[str] = None
    posted_at: Optional[str] = None


class JobsListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int = 0
    matched_count: int = 0
    unscored_count: int = 0
    limit: int = 50
    offset: int = 0
    alignment_summary: Dict[str, Any] = {}
    provider_catalog: List[Dict[str, Any]] = []


class JobStatsResponse(BaseModel):
    total_jobs: int = 0
    raw_total_jobs: int = 0
    by_source: Dict[str, int] = {}
    avg_match_score: float = 0.0
    last_ingested: Optional[str] = None
    active_jobs: int = 0
    filtered_out_jobs: int = 0
    non_india_filtered_jobs: int = 0
    non_tech_filtered_jobs: int = 0
    stale_or_closed_jobs: int = 0
    alignment_summary: Dict[str, Any] = {}
    provider_catalog: List[Dict[str, Any]] = []
    provider_health: Dict[str, Any] = {}


class AlertRecordJobResponse(BaseModel):
    id: int = 0
    job_uid: str = ""
    title: str = ""
    company: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    source_provider: Optional[str] = None
    source_job_id: Optional[str] = None
    source_url: Optional[str] = None
    apply_url: Optional[str] = None
    match_score: Optional[float] = None
    freshness_score: Optional[float] = None
    lifecycle_state: Optional[str] = None
    posted_date: Optional[str] = None
    fetched_at: Optional[str] = None


class AlertRecordResponse(BaseModel):
    id: int = 0
    decision: str = ""
    channel: str = ""
    reason: str = ""
    created_at: Optional[str] = None
    scores: Optional[Dict[str, Any]] = None
    decision_factors: Optional[Dict[str, Any]] = None
    decision_confidence: Optional[float] = None
    job: Optional[AlertRecordJobResponse] = None


class AlertRecordsResponse(BaseModel):
    records: List[AlertRecordResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0
    decision: Optional[str] = None


class RefreshJobsRequest(BaseModel):
    resume_id: Optional[str] = None
    target_role: Optional[str] = None
    target_location: Optional[str] = None
    salary_preference: Optional[str] = None


def _job_match_payload(match, job) -> Optional[Dict[str, Any]]:
    if not match:
        return None
    details = match.match_details or {}
    strengths = match.strengths or []
    gaps = match.gaps or []
    score = round(float(match.overall_score or 0), 1)
    reason = match.recommendation or details.get("reason") or "Resume-centric match calculated."
    return {
        "match_score": score,
        "overall_match": score,
        "confidence": 0.86 if details else 0.5,
        "summary": reason,
        "reason": reason,
        "strengths": strengths,
        "gaps": gaps,
        "matched_skills": details.get("matched_skills", []),
        "missing_skills": details.get("missing_skills", []),
        "components": details.get("components", []),
        "dimensions": details.get("dimensions", {}),
        "resume_extraction": details.get("resume_extraction", {}),
        "job_extraction": details.get("job_extraction", {}),
        "semantic_similarity": details.get("semantic_similarity"),
        "estimated_score_improvement": details.get("estimated_score_improvement", {}),
        "below_40_explanation": details.get("below_40_explanation"),
        "freshness_score": details.get("freshness_score"),
        "freshness_bucket": details.get("freshness_bucket"),
        "provider_quality_score": details.get("provider_quality_score"),
        "salary_quality_score": details.get("salary_quality_score"),
        "opportunity_priority_score": details.get("opportunity_priority_score"),
        "estimated_learning_time": details.get("estimated_learning_time"),
        "confidence": details.get("confidence", 0.86 if details else 0.5),
        "active_resume": details.get("active_resume") or {
            "doc_id": match.resume_doc_uid,
            "name": match.resume_name,
        },
        "calculated_at": details.get("calculated_at"),
    }


def _response_from_job(job, match=None) -> JobResponse:
    match_payload = _job_match_payload(match, job)
    match_details = match.match_details if match and match.match_details else job.match_details
    return JobResponse(
        id=job.id,
        job_uid=job.job_uid,
        title=job.title,
        company=job.company,
        location=job.location,
        description=job.description[:500] if job.description else None,
        full_description=job.description,
        source=job.source,
        source_provider=job.source_provider or job.source,
        source_job_id=job.source_job_id,
        source_url=job.source_url,
        apply_url=job.apply_url or job.source_url,
        url_type="direct",
        posted_date=_utc_iso(getattr(job, "posted_date", None)),
        fetched_at=_utc_iso(job.fetched_at) if getattr(job, "fetched_at", None) else _utc_iso(job.ingested_at),
        salary_range=job.salary_range,
        salary=job.salary_range,
        skills_required=job.skills_required,
        extracted_skills=job.skills_required,
        freshness_score=job.freshness_score,
        freshness_bucket=job.freshness_bucket,
        provider_quality_score=job.provider_quality_score,
        salary_quality_score=job.salary_quality_score,
        opportunity_priority_score=job.opportunity_priority_score,
        lifecycle_state=job.lifecycle_state,
        apply_url_valid=job.apply_url_valid,
        is_india_eligible=getattr(job, "is_india_eligible", None),
        is_tech_role=getattr(job, "is_tech_role", None),
        tech_role_category=getattr(job, "tech_role_category", None),
        tech_role_confidence=getattr(job, "tech_role_confidence", None),
        seniority_level=getattr(job, "seniority_level", None),
        experience_min_years=getattr(job, "experience_min_years", None),
        experience_max_years=getattr(job, "experience_max_years", None),
        experience_filter_status=getattr(job, "experience_filter_status", None),
        match_score=match_payload["match_score"] if match_payload else job.match_score,
        match_details=match_details,
        match=match_payload,
        status=job.status,
        ingested_at=_utc_iso(job.ingested_at),
        posted_at=_utc_iso(getattr(job, "posted_date", None)),
    )


def _job_order_by_clause(sort: str, *, has_match_join: bool, Job, JobMatch, func):
    normalized = (sort or "best_match").strip().lower()
    if normalized == "best_match":
        if has_match_join:
            return [
                JobMatch.overall_score.desc().nullslast(),
                Job.posted_date.desc().nullslast(),
                Job.fetched_at.desc().nullslast(),
                Job.id.desc(),
            ]
        return [
            Job.fetched_at.desc().nullslast(),
            Job.posted_date.desc().nullslast(),
            Job.id.desc(),
        ]
    if normalized == "posted_at_desc":
        return [
            Job.posted_date.desc().nullslast(),
            Job.fetched_at.desc().nullslast(),
            Job.id.desc(),
        ]
    if normalized == "fetched_at_desc":
        return [
            Job.fetched_at.desc().nullslast(),
            Job.posted_date.desc().nullslast(),
            Job.id.desc(),
        ]
    if normalized == "freshness_desc":
        return [
            Job.freshness_score.desc().nullslast(),
            Job.posted_date.desc().nullslast(),
            Job.fetched_at.desc().nullslast(),
            Job.id.desc(),
        ]
    if normalized == "company_asc":
        return [
            func.lower(Job.company).asc().nullslast(),
            Job.title.asc().nullslast(),
            Job.posted_date.desc().nullslast(),
            Job.id.desc(),
        ]
    raise HTTPException(
        status_code=400,
        detail=f"Invalid sort option '{sort}'. Allowed values: {', '.join(sorted(JOB_SORT_OPTIONS))}",
    )


@router.get("", response_model=JobsListResponse)
async def list_jobs(
    source: Optional[str] = Query(None),
    score: Optional[str] = Query(None),
    resume_id: Optional[str] = Query(None),
    sort: Optional[str] = Query("best_match", description="best_match, posted_at_desc, fetched_at_desc, freshness_desc, company_asc"),
    include_unmatched: bool = Query(False, description="Include jobs without a match record"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List job postings ranked by match score. Default shows only matched jobs."""
    from sqlalchemy import desc, func, select
    from src.models.jobs import Job, JobMatch
    from src.services.opportunity.job_intelligence_service import get_job_intelligence_service

    svc = get_job_intelligence_service()
    resume = await svc.get_active_resume(db, user["sub"], resume_id)
    resume_profile = svc.resume_profile(resume)

    if include_unmatched:
        filters = [
            Job.apply_url.is_not(None),
            Job.apply_url != "",
        ]
    else:
        filters = [
            Job.status == "active",
            Job.deleted_at.is_(None),
            Job.is_india_eligible == True,
            Job.is_tech_role == True,
            Job.apply_url.is_not(None),
            Job.apply_url != "",
            Job.lifecycle_state.notin_(["APPLIED", "INTERVIEWING", "OFFERED", "HIRED", "EXPIRED"]),
            ((Job.freshness_bucket.is_(None)) | (Job.freshness_bucket != "stale")),
            Job.location.notlike("%United States%"),
            Job.location.notlike("%United Kingdom%"),
            Job.location.notlike("%Germany%"),
            Job.location.notlike("%Canada%"),
            Job.location.notlike("%London%"),
            Job.location.notlike("%San Francisco%"),
            Job.location.notlike("%Ontario%"),
            Job.location.notlike("%Berlin%"),
            Job.location.notlike("%New York%"),
        ]
    if source:
        filters.append(Job.source == source)

    from sqlalchemy import and_
    join_on = and_(
        JobMatch.job_id == Job.id,
        JobMatch.user_id == user["sub"],
        JobMatch.deleted_at.is_(None),
    )
    if resume:
        join_on = and_(join_on, JobMatch.resume_doc_uid == resume.doc_uid)

    if resume is None:
        if include_unmatched:
            q = select(Job, JobMatch).outerjoin(JobMatch, join_on).where(*filters)
        else:
            q = select(Job).where(*filters)
    elif include_unmatched:
        q = select(Job, JobMatch).outerjoin(JobMatch, join_on).where(*filters)
    else:
        q = select(Job, JobMatch).join(JobMatch, join_on).where(*filters).where(
            JobMatch.overall_score.is_not(None),
        )

    if score:
        try:
            q = q.where(JobMatch.overall_score >= float(score))
        except ValueError:
            pass

    has_match_join = resume is not None or include_unmatched
    q = q.order_by(*_job_order_by_clause(sort or "best_match", has_match_join=has_match_join, Job=Job, JobMatch=JobMatch, func=func))
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    rows = result.all()

    if resume:
        matched_q = select(func.count(JobMatch.id)).join(
            Job, Job.id == JobMatch.job_id,
        ).where(
            *filters,
            JobMatch.user_id == user["sub"],
            JobMatch.deleted_at.is_(None),
            JobMatch.overall_score.is_not(None),
            JobMatch.resume_doc_uid == resume.doc_uid,
        )
        matched_count = int((await db.execute(matched_q)).scalar() or 0)
    else:
        matched_count = 0

    total_q = select(func.count(Job.id)).where(*filters)
    total = int((await db.execute(total_q)).scalar() or 0)

    match_filters_for_summary = [
        JobMatch.user_id == user["sub"],
        JobMatch.deleted_at.is_(None),
        Job.status == "active",
        Job.deleted_at.is_(None),
        Job.is_india_eligible == True,
        Job.apply_url.is_not(None),
        Job.apply_url != "",
        Job.lifecycle_state.notin_(["APPLIED", "INTERVIEWING", "OFFERED", "HIRED", "EXPIRED"]),
        ((Job.freshness_bucket.is_(None)) | (Job.freshness_bucket != "stale")),
    ]
    if resume:
        match_filters_for_summary.append(JobMatch.resume_doc_uid == resume.doc_uid)
    matches = list((await db.execute(
        select(JobMatch).join(Job, Job.id == JobMatch.job_id).where(*match_filters_for_summary)
    )).scalars().all())
    alignment_summary = svc.summary(resume_profile, matches)

    response_jobs = []
    unscored_count = 0
    for row in rows:
        if resume is None:
            job = row[0]
            match = None
        else:
            job, match = row
        resp = _response_from_job(job, match)
        if match and match.overall_score is not None:
            score_val = float(match.overall_score)
            if score_val <= 1.0:
                resp.match_score = round(score_val * 100, 1)
            else:
                resp.match_score = round(score_val, 1)
            resp.match = resp.match or {}
            resp.match["score_source"] = "job_match"
            resp.match["match_score"] = resp.match_score
        else:
            resp.match_score = None
            if resp.match:
                resp.match["match_score"] = None
                resp.match["score_source"] = "unscored"
            else:
                resp.match = {"score_source": "unscored", "match_score": None}
            unscored_count += 1

        response_jobs.append(resp)

    return JobsListResponse(
        jobs=response_jobs,
        total=total,
        matched_count=matched_count,
        unscored_count=unscored_count,
        limit=limit,
        offset=offset,
        alignment_summary=alignment_summary,
        provider_catalog=REAL_PROVIDER_CATALOG,
    )


@router.get("/stats", response_model=JobStatsResponse)
async def job_stats(
    resume_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Job feed statistics."""
    from sqlalchemy import select
    from src.integrations.theirstack.credential_resolver import resolve_keys
    from src.models.orchestration import OrchestrationSession
    from src.models.jobs import Job, JobMatch
    from src.services.opportunity.job_intelligence_service import get_job_intelligence_service

    repo = JobRepository(db)
    stats = await repo.get_stats()
    svc = get_job_intelligence_service()
    resume = await svc.get_active_resume(db, user["sub"], resume_id)
    resume_profile = svc.resume_profile(resume)
    match_filters = [
        JobMatch.user_id == user["sub"],
        JobMatch.deleted_at.is_(None),
        Job.status == "active",
        Job.deleted_at.is_(None),
        Job.is_india_eligible == True,
        Job.apply_url.is_not(None),
        Job.apply_url != "",
        Job.lifecycle_state.notin_(["APPLIED", "INTERVIEWING", "OFFERED", "HIRED", "EXPIRED"]),
        ((Job.freshness_bucket.is_(None)) | (Job.freshness_bucket != "stale")),
    ]
    if resume:
        match_filters.append(JobMatch.resume_doc_uid == resume.doc_uid)
    else:
        match_filters.append(JobMatch.id.is_(None))
    matches = list((await db.execute(
        select(JobMatch).join(Job, Job.id == JobMatch.job_id).where(*match_filters)
    )).scalars().all())
    resolver = resolve_keys()
    latest_refresh_result = await db.execute(
        select(OrchestrationSession)
        .where(
            OrchestrationSession.user_id == user["sub"],
            OrchestrationSession.graph_name == "job_refresh",
            OrchestrationSession.deleted_at.is_(None),
        )
        .order_by(OrchestrationSession.created_at.desc())
        .limit(1)
    )
    latest_refresh = latest_refresh_result.scalar_one_or_none()
    latest_refresh_meta = latest_refresh.metadata_ if latest_refresh and latest_refresh.metadata_ else {}
    latest_provider_health = latest_refresh_meta.get("provider_health") or {}
    latest_provider_results = latest_refresh_meta.get("provider_results") or []
    latest_provider_query_contexts = latest_refresh_meta.get("provider_query_contexts") or []
    latest_sample_updated_jobs = latest_refresh_meta.get("sample_updated_jobs") or []
    latest_visibility_reason = latest_refresh_meta.get("visibility_reason") or {}
    latest_refresh_summary = latest_refresh_meta.get("refresh_summary") or {}
    if latest_provider_results and latest_refresh_summary and latest_visibility_reason.get("code") in {"provider_billing_required", "provider_blocked"}:
        from src.services.job_refresh import JobRefreshService

        latest_visibility_reason = JobRefreshService._build_visibility_reason(
            resume_doc_uid=latest_refresh_meta.get("resume_doc_uid"),
            provider_results=list(latest_provider_results),
            refresh_summary=dict(latest_refresh_summary),
        )
    theirstack_health = {
        "provider": "theirstack",
        "configured": resolver.has_keys,
        "key_slots_configured": resolver.total_slots,
        "key_slots": [slot.slot_name for slot in resolver.slots],
        "status": latest_provider_health.get("theirstack", {}).get("status") if isinstance(latest_provider_health.get("theirstack"), dict) else ("configured" if resolver.has_keys else "not_configured"),
        "billing_required": bool(latest_provider_health.get("theirstack", {}).get("billing_required")) if isinstance(latest_provider_health.get("theirstack"), dict) else False,
        "provider_blocked": bool(latest_provider_health.get("theirstack", {}).get("provider_blocked")) if isinstance(latest_provider_health.get("theirstack"), dict) else False,
        "last_refresh": latest_provider_health.get("theirstack"),
        "last_refresh_summary": latest_provider_health.get("summary"),
        "latest_refresh_summary": latest_refresh_summary,
        "latest_refresh_reason": latest_visibility_reason,
        "latest_provider_results": latest_provider_results,
        "latest_provider_query_contexts": latest_provider_query_contexts,
        "latest_sample_updated_jobs": latest_sample_updated_jobs,
    }
    return JobStatsResponse(
        **stats,
        alignment_summary=svc.summary(resume_profile, matches),
        provider_catalog=REAL_PROVIDER_CATALOG,
        provider_health={"theirstack": theirstack_health},
    )


class ApplicationStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class Phase2RunRequest(BaseModel):
    resume_id: Optional[str] = None
    limit: int = Field(default=120, ge=1, le=600)


@router.get("/alert-stats")
async def alert_decision_stats(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Real-time alert decision counts and actual communication delivery status."""
    from sqlalchemy import select, func
    from src.models.jobs import AlertDecisionAudit, CommunicationRequest, Job

    decision_counts = (await db.execute(
        select(
            AlertDecisionAudit.decision,
            func.count(AlertDecisionAudit.id).label("count"),
        )
        .where(AlertDecisionAudit.user_id == user["sub"])
        .group_by(AlertDecisionAudit.decision)
    )).all()

    delivered_counts = (await db.execute(
        select(
            CommunicationRequest.channel,
            func.count(CommunicationRequest.id).label("count"),
        )
        .where(
            CommunicationRequest.user_id == user["sub"],
            CommunicationRequest.communication_status.in_(
                ["sent", "delivered", "sent_to_provider", "call_attempted"]
            ),
        )
        .group_by(CommunicationRequest.channel)
    )).all()

    dashboard_items = (await db.execute(
        select(AlertDecisionAudit, Job)
        .join(Job, Job.id == AlertDecisionAudit.job_id)
        .where(
            AlertDecisionAudit.user_id == user["sub"],
            AlertDecisionAudit.decision == "DASHBOARD_ONLY",
        )
        .order_by(AlertDecisionAudit.created_at.desc())
        .limit(10)
    )).all()

    return {
        "decisions": {row.decision: row.count for row in decision_counts},
        "pending_approvals": 0,
        "delivered_communications": {row.channel: row.count for row in delivered_counts},
        "dashboard_items": [
            {
                "job_id": job.id,
                "job_uid": job.job_uid,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "match_score": float(audit.scores.get("match_score", 0) if audit.scores else 0),
                "reason": audit.reason,
                "created_at": audit.created_at.isoformat() if audit.created_at else None,
            }
            for audit, job in dashboard_items
        ],
    }


@router.get("/alerts", response_model=AlertRecordsResponse)
async def alert_records(
    decision: Optional[str] = Query("DASHBOARD_ONLY"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Browse the persisted alert decision records behind the dashboard counts."""
    from sqlalchemy import func, select
    from src.models.jobs import AlertDecisionAudit, Job

    filters = [AlertDecisionAudit.user_id == user["sub"]]
    if decision:
        filters.append(AlertDecisionAudit.decision == decision)

    total = int((await db.execute(
        select(func.count(AlertDecisionAudit.id)).where(*filters)
    )).scalar() or 0)

    rows = (await db.execute(
        select(AlertDecisionAudit, Job)
        .join(Job, Job.id == AlertDecisionAudit.job_id)
        .where(*filters)
        .order_by(AlertDecisionAudit.created_at.desc())
        .offset(offset)
        .limit(limit)
    )).all()

    def _safe_dt(value):
        return value.isoformat() if value else None

    records = []
    for audit, job in rows:
        records.append(
            AlertRecordResponse(
                id=audit.id,
                decision=audit.decision,
                channel=audit.channel,
                reason=audit.reason,
                created_at=_safe_dt(audit.created_at),
                scores=audit.scores,
                decision_factors=audit.decision_factors,
                decision_confidence=audit.decision_confidence,
                job=AlertRecordJobResponse(
                    id=job.id,
                    job_uid=job.job_uid,
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    source=job.source,
                    source_provider=job.source_provider,
                    source_job_id=job.source_job_id,
                    source_url=job.source_url,
                    apply_url=job.apply_url,
                    match_score=job.match_score,
                    freshness_score=job.freshness_score,
                    lifecycle_state=job.lifecycle_state,
                    posted_date=_safe_dt(job.posted_date),
                    fetched_at=_safe_dt(job.fetched_at or job.ingested_at),
                ),
            )
        )

    return AlertRecordsResponse(records=records, total=total, limit=limit, offset=offset, decision=decision)


@router.get("/applications")
async def get_applications(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all applications for the current user."""
    from src.services.opportunity.application_memory import get_application_memory

    svc = get_application_memory()
    applications = await svc.get_user_applications(db, user["sub"])
    return {"applications": applications, "total": len(applications)}


@router.post("/phase2/run")
async def run_phase2_intelligence(
    request: Phase2RunRequest = Phase2RunRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate persisted autonomous opportunity intelligence for real matched jobs."""
    from src.services.opportunity.phase2_opportunity_intelligence import get_phase2_opportunity_intelligence_service

    result = await get_phase2_opportunity_intelligence_service().generate_for_user(
        db,
        user["sub"],
        resume_doc_uid=request.resume_id,
        limit=request.limit,
    )
    return result


@router.get("/phase2/dashboard")
async def get_phase2_dashboard(
    days: int = Query(90, ge=1, le=365),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analytics dashboard for opportunity funnel, skills, applications, and trends."""
    from src.services.opportunity.phase2_opportunity_intelligence import get_phase2_opportunity_intelligence_service

    return await get_phase2_opportunity_intelligence_service().dashboard(db, user["sub"], days=days)


@router.get("/phase2/jobs/{job_id}")
async def get_phase2_job_intelligence(
    job_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the persisted Phase 2 intelligence pack for one real job."""
    from src.services.opportunity.phase2_opportunity_intelligence import get_phase2_opportunity_intelligence_service

    return await get_phase2_opportunity_intelligence_service().get_job_intelligence(db, user["sub"], job_id)


@router.get("/providers/twilio/health")
async def twilio_health(
    user: dict = Depends(get_current_user),
):
    """Expose Twilio provider readiness without leaking credentials."""
    from src.services.opportunity.twilio_reconciliation import get_twilio_account_health

    health = await get_twilio_account_health()
    return {"provider": "twilio", **health}


@router.get("/providers/twilio/reconcile")
async def reconcile_twilio_calls(
    max_age_hours: int = Query(default=24, ge=1, le=168),
    user: dict = Depends(get_current_user),
):
    """Reconcile pending voice sessions with final Twilio call status."""
    from src.services.opportunity.twilio_reconciliation import reconcile_pending_calls

    result = await reconcile_pending_calls(max_age_hours=max_age_hours)
    return {"provider": "twilio", "reconciliation": result}


@router.get("/providers/elevenlabs/health")
async def elevenlabs_health(
    user: dict = Depends(get_current_user),
):
    """Expose ElevenLabs provider readiness."""
    api_key = (settings.ELEVENLABS_API_KEY or "").strip()
    configured = bool(api_key) and api_key != "your_elevenlabs_api_key_here"
    return {
        "provider": "elevenlabs",
        "configured": configured,
        "api_key_present": bool(api_key),
        "voice_id": (settings.VOICE_ELEVENLABS_VOICE_ID or "default"),
    }


@router.get("/providers/pipedream/health")
async def pipedream_health(
    user: dict = Depends(get_current_user),
):
    """Expose Pipedream provider readiness."""
    webhook_url = (settings.PIPEDREAM_WEBHOOK_URL or "").strip()
    return {
        "provider": "pipedream",
        "configured": bool(webhook_url),
        "webhook_url_present": bool(webhook_url),
    }


@router.get("/providers/theirstack/health")
async def theirstack_health(
    user: dict = Depends(get_current_user),
):
    """Expose TheirStack provider readiness without leaking credentials."""
    from src.integrations.theirstack.sync_service import TheirStackSyncService

    health = await TheirStackSyncService().health_check()
    return {
        "provider": "theirstack",
        "configured": bool(settings.THEIRSTACK_API_KEY),
        "health": health,
    }


@router.get("/voice-sessions")
async def get_voice_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get voice sessions for current user."""
    from src.services.opportunity.voice_opportunity_agent import get_voice_opportunity_agent

    agent = get_voice_opportunity_agent()
    sessions = await agent.get_user_sessions(db, user["sub"], limit=limit)
    return {
        "sessions": [
            {
                "id": s.id,
                "session_uid": s.session_uid,
                "job_id": s.job_id,
                "status": s.status,
                "voice_provider": s.voice_provider,
                "voice_metadata": s.voice_metadata,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ],
        "total": len(sessions),
    }


@router.get("/voice-sessions/{session_id}")
async def get_voice_session(
    session_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get voice session detail with conversation turns."""
    from src.services.opportunity.voice_opportunity_agent import get_voice_opportunity_agent

    agent = get_voice_opportunity_agent()
    session = await agent.get_session(db, session_id)
    if not session or session.user_id != user["sub"]:
        raise HTTPException(status_code=404, detail="Voice session not found")

    conversations = await agent.get_session_conversations(db, session_id)
    outcomes = await agent.get_session_outcomes(db, session_id)
    return {
        "session": {
            "id": session.id,
            "session_uid": session.session_uid,
            "job_id": session.job_id,
            "status": session.status,
            "voice_provider": session.voice_provider,
            "voice_metadata": session.voice_metadata,
            "created_at": session.created_at.isoformat() if session.created_at else None,
        },
        "conversations": [
            {"role": c.role, "content": c.content, "created_at": c.created_at.isoformat() if c.created_at else None}
            for c in conversations
        ],
        "outcomes": [
            {"outcome": o.outcome, "call_sid": o.call_sid, "provider_status": o.provider_status, "created_at": o.created_at.isoformat() if o.created_at else None}
            for o in outcomes
        ],
    }


@router.get("/voice-sessions/{session_id}/transition")
async def transition_voice_session(
    session_id: int,
    target_state: str = Query(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Transition a voice session to a new state."""
    from src.services.opportunity.voice_opportunity_agent import get_voice_opportunity_agent

    agent = get_voice_opportunity_agent()
    try:
        session = await agent.transition_session(db, voice_session_id=session_id, target_state=target_state.upper())
        return {"session_id": session.id, "status": session.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/career-memory")
async def get_career_memory(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get career memory preferences."""
    from src.services.opportunity.career_memory import get_career_memory_service

    svc = get_career_memory_service()
    preferences = await svc.get_preferences(db, user_id=user["sub"])
    return {"preferences": preferences}


@router.get("/outcome-intelligence")
async def get_outcome_intelligence(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get outcome intelligence — conversion funnel, channel, provider, and role family performance."""
    from src.services.opportunity.outcome_intelligence import get_outcome_intelligence_service

    svc = get_outcome_intelligence_service()
    funnel = await svc.get_conversion_funnel(db, user_id=user["sub"])
    channels = await svc.get_channel_performance(db, user_id=user["sub"])
    providers = await svc.get_provider_performance(db, user_id=user["sub"])
    role_families = await svc.get_role_family_performance(db, user_id=user["sub"])
    events = await svc.get_outcome_events(db, user_id=user["sub"], limit=20)
    return {
        "funnel": funnel,
        "channel_performance": channels,
        "provider_performance": providers,
        "role_family_performance": role_families,
        "recent_events": events,
    }


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    resume_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single job by UID or ID."""
    from sqlalchemy import select
    from src.models.jobs import JobMatch
    from src.services.opportunity.job_intelligence_service import get_job_intelligence_service

    repo = JobRepository(db)
    svc = get_job_intelligence_service()
    resume = await svc.get_active_resume(db, user["sub"], resume_id)
    job = await repo.get_by_uid(job_id)
    if not job:
        try:
            id_int = int(job_id)
            job = await repo.get_by_id(id_int)
        except ValueError:
            pass
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not (job.apply_url or "").strip() or job.status != "active" or job.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Real direct job posting not found")
    match_query = select(JobMatch).where(
        JobMatch.user_id == user["sub"],
        JobMatch.job_id == job.id,
        JobMatch.deleted_at.is_(None),
        JobMatch.resume_doc_uid == resume.doc_uid if resume else JobMatch.id.is_(None),
    ).order_by(
        JobMatch.created_at.desc(),
        JobMatch.id.desc(),
    ).limit(1)
    match = (await db.execute(match_query)).scalars().first()
    response = _response_from_job(job, match)
    response.description = job.description
    return response


@router.post("/refresh")
async def refresh_jobs(
    request: RefreshJobsRequest = RefreshJobsRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enqueue background job refresh and return immediately with session id."""
    from src.services.opportunity.job_intelligence_service import get_job_intelligence_service
    from src.services.job_refresh import get_job_refresh_service
    from src.workers.arq_worker import enqueue_job_refresh

    svc = get_job_intelligence_service()
    resume = await svc.get_active_resume(db, user["sub"], request.resume_id)
    if request.resume_id and not resume:
        return {
            "status": "setup_required",
            "message": "Selected resume is not indexed with extractable content. Re-upload the original file or choose a valid resume.",
            "active_resume": None,
            "provider_catalog": REAL_PROVIDER_CATALOG,
        }
    profile = svc.resume_profile(resume) if resume else {}
    preferences = {
        "target_role": request.target_role,
        "target_location": request.target_location,
        "salary_preference": request.salary_preference,
    }

    refresh_svc = get_job_refresh_service()
    session = await refresh_svc.start_refresh(
        db,
        user["sub"],
        resume.doc_uid if resume else None,
        profile,
        preferences,
    )

    try:
        from src.services.events import get_career_event_service

        await get_career_event_service().emit_event(
            db,
            event_type="JobRefreshStarted",
            entity_type="job_refresh_session",
            entity_id=session.session_uid,
            source_service="api.v1.jobs.refresh",
            user_id=user["sub"],
            source_table="orchestration_sessions",
            source_id=session.id,
            payload={
                "session_id": session.id,
                "session_uid": session.session_uid,
                "status": session.status,
                "resume_doc_uid": session.metadata_.get("resume_doc_uid") if session.metadata_ else None,
                "preferences": preferences,
            },
            evidence=[
                get_career_event_service().build_evidence_ref(
                    table="orchestration_sessions",
                    source_id=session.id,
                    note="job refresh started",
                )
            ],
            provider=(refresh_svc.build_diagnostics_payload(session).get("provider_health") or {}).get("theirstack", {}).get("provider"),
            trace_id=session.session_uid,
        )
    except Exception:
        logger.warning("Failed to emit JobRefreshStarted audit event", exc_info=True)

    reused_existing_refresh = bool((session.metadata_ or {}).get("reused_existing_refresh"))
    if not reused_existing_refresh:
        await enqueue_job_refresh(session.id)

    message = "Job matching enqueued." if resume else "Provider ingestion enqueued (no resume for matching)."
    return {
        "session_uid": session.session_uid,
        "session_id": session.id,
        "status": session.status,
        "message": (
            f"{message} Poll GET /jobs/refresh/{session.id} for progress."
            if not reused_existing_refresh
            else f"Recent matching run reused. Poll GET /jobs/refresh/{session.id} for progress."
        ),
        "reused_existing_refresh": reused_existing_refresh,
        "next_refresh_at": (session.metadata_ or {}).get("next_refresh_at"),
        "started_at": _utc_iso(session.created_at),
        "active_resume": {k: v for k, v in profile.items() if k != "content"} if profile else None,
        "provider_catalog": REAL_PROVIDER_CATALOG,
        "diagnostics": refresh_svc.build_diagnostics_payload(session),
    }


@router.get("/refresh/{session_id}")
async def get_refresh_status(
    session_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll the status of a background job refresh session."""
    from src.services.job_refresh import get_job_refresh_service

    svc = get_job_refresh_service()
    result = await svc.get_status(db, session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Refresh session not found")
    return result


@router.post("/{job_id}/application")
async def update_application(
    job_id: int,
    request: ApplicationStatusRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update application status for a job."""
    from src.services.opportunity.application_memory import get_application_memory, ApplicationStatus

    svc = get_application_memory()

    try:
        status = ApplicationStatus(request.status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    result = await svc.update_application_status(
        db, user["sub"], job_id, status, request.notes
    )
    return result


@router.get("/{job_id}/application")
async def get_application_status(
    job_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get application status for a specific job."""
    from src.services.opportunity.application_memory import get_application_memory

    svc = get_application_memory()
    status = await svc.get_application_status(db, user["sub"], job_id)
    return {"job_id": job_id, "status": status.value}
