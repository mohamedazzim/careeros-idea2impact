"""
Opportunity discovery and matching endpoints.

Exposes:
- POST /api/v1/opportunities/discover — Run full discovery pipeline
- GET  /api/v1/opportunities/list    — List persisted matches
- GET  /api/v1/opportunities/{job_id} — Single match detail

NOTE: Provider ingestion (sync_jobs) belongs to POST /api/v1/jobs/refresh.
The /discover endpoint calls sync_jobs inline as a convenience fallback,
but the canonical refresh path is the Jobs Pipeline (/jobs page).
"""

import asyncio
import logging
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


class DiscoverRequest(BaseModel):
    candidate_context: dict = Field(default_factory=dict, description="Optional candidate profile overrides")


class OpportunityAlertRequest(BaseModel):
    match_id: int = Field(..., ge=1)
    phone_number: Optional[str] = None
    urgency_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class OutcomeEventRequest(BaseModel):
    job_id: int = Field(..., ge=1)
    status: str
    channel: Optional[str] = None
    communication_request_id: Optional[int] = None
    data: dict = Field(default_factory=dict)


class OpportunityItem(BaseModel):
    id: str
    title: str
    company: str
    provider: Optional[str] = None
    source_url: Optional[str] = None
    source_job_id: Optional[str] = None
    overall_score: float
    confidence: float
    skill_overlap: float
    dimension_scores: dict
    missing_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    salary_range: Optional[str] = None
    deadline: Optional[str] = None
    source: Optional[str] = None
    freshness_score: Optional[float] = None
    opportunity_priority_score: Optional[float] = None
    lifecycle_state: Optional[str] = None


class DiscoverResponse(BaseModel):
    run_id: str
    opportunities: List[OpportunityItem]
    resume_status: str
    market_signals_count: int
    pipeline_elapsed_ms: float


def _score_val(dim_scores: dict, key: str, default: float = 0.0) -> float:
    v = dim_scores.get(key)
    if isinstance(v, dict):
        score = v.get("score", default)
        return float(score) if score is not None else float(default)
    if isinstance(v, (int, float)):
        return float(v)
    return float(default)


def _evidence_labels(items: list | None) -> list[str]:
    labels: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            label = item
        elif isinstance(item, dict):
            label = str(
                item.get("title")
                or item.get("category")
                or item.get("description")
                or item.get("id")
                or ""
            )
        else:
            label = str(item)
        if label.strip():
            labels.append(label.strip())
    return labels


@router.post("/discover", response_model=DiscoverResponse, summary="Run full opportunity discovery pipeline")
async def discover_opportunities(
    request: DiscoverRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import time
    from sqlalchemy import select, desc
    from src.models.jobs import Job, JobMatch
    from src.services.jobs import get_job_ingestion_engine
    from src.services.opportunity.job_intelligence_service import get_job_intelligence_service

    t0 = time.monotonic()
    try:
        await asyncio.wait_for(
            get_job_ingestion_engine().sync_jobs(admin_initiated=True),
            timeout=20.0,
        )
    except TimeoutError:
        # Existing rows are still real provider records; discovery can safely
        # recalculate them while the upstream provider is unavailable.
        pass
    intelligence = get_job_intelligence_service()
    resume = await intelligence.get_active_resume(db, user["sub"])
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No indexed resume selected. Upload and index a resume before discovering opportunities.",
        )
    await intelligence.recalculate_matches(db, user["sub"], resume)

    result = await db.execute(
        select(JobMatch, Job)
        .join(Job, Job.id == JobMatch.job_id)
        .where(
            JobMatch.user_id == user["sub"],
            JobMatch.deleted_at.is_(None),
            Job.status == "active",
            Job.deleted_at.is_(None),
            Job.apply_url.is_not(None),
            Job.apply_url != "",
        )
        .order_by(desc(JobMatch.overall_score))
        .limit(50)
    )

    opportunities = []
    for match, job in result.all():
        dim_scores = {
            "skill_overlap": {"score": float(match.skill_match or 0), "confidence": 0.8, "citations": []},
            "seniority_fit": {"score": float(match.experience_match or 0), "confidence": 0.7, "citations": []},
            "domain_alignment": {"score": float(match.education_match or 0), "confidence": 0.7, "citations": []},
        }
        opportunities.append(OpportunityItem(
            id=str(match.id),
            title=job.title,
            company=job.company,
            provider=match.source_provider or job.source_provider or job.source,
            source_url=job.apply_url,
            source_job_id=match.source_job_id or job.source_job_id or job.job_uid,
            overall_score=float(match.overall_score or 0),
            confidence=float(getattr(match, "confidence", 0.5) or 0.5),
            skill_overlap=float(match.skill_match or 0),
            dimension_scores=dim_scores,
            missing_skills=_evidence_labels(match.gaps),
            matched_skills=_evidence_labels(match.strengths),
            salary_range=job.salary_range,
            deadline=None,
            source=job.source,
            freshness_score=job.freshness_score,
            opportunity_priority_score=job.opportunity_priority_score,
            lifecycle_state=job.lifecycle_state,
        ))

    elapsed_ms = round((time.monotonic() - t0) * 1000, 2)

    return DiscoverResponse(
        run_id=str(uuid.uuid4()),
        opportunities=opportunities,
        resume_status="matched_against_active_resume",
        market_signals_count=len(opportunities),
        pipeline_elapsed_ms=elapsed_ms,
    )


@router.get("/list", summary="List persisted opportunity matches")
async def list_opportunities(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.models.jobs import Job, JobMatch
    from sqlalchemy import select, desc

    q = select(JobMatch, Job).join(Job, Job.id == JobMatch.job_id).where(
        JobMatch.user_id == user["sub"],
        JobMatch.deleted_at.is_(None),
        Job.status == "active",
        Job.deleted_at.is_(None),
        Job.apply_url.is_not(None),
        Job.apply_url != "",
    ).order_by(desc(JobMatch.overall_score)).offset(offset).limit(limit)

    result = await db.execute(q)
    rows = result.all()

    count_q = select(JobMatch).join(Job, Job.id == JobMatch.job_id).where(
        JobMatch.user_id == user["sub"],
        JobMatch.deleted_at.is_(None),
        Job.status == "active",
        Job.deleted_at.is_(None),
        Job.apply_url.is_not(None),
        Job.apply_url != "",
    )
    count_result = await db.execute(count_q)
    total = len(count_result.scalars().all())

    items = []
    for match, job in rows:
        items.append({
            "id": match.id,
            "job_id": match.job_id,
            "title": job.title,
            "company": job.company,
            "provider": match.source_provider or job.source_provider or job.source,
            "source_url": job.apply_url,
            "source_job_id": match.source_job_id or job.job_uid,
            "overall_score": match.overall_score,
            "skill_match": match.skill_match,
            "experience_match": match.experience_match,
            "education_match": match.education_match,
            "gap_score": match.gap_score,
            "strengths": match.strengths or [],
            "gaps": match.gaps or [],
            "recommendation": match.recommendation,
            "freshness_score": job.freshness_score,
            "freshness_bucket": job.freshness_bucket,
            "provider_quality_score": job.provider_quality_score,
            "opportunity_priority_score": job.opportunity_priority_score,
            "lifecycle_state": job.lifecycle_state,
            "created_at": match.created_at.isoformat(),
            "ingested_at": match.ingested_at.isoformat() if match.ingested_at else (job.ingested_at.isoformat() if job.ingested_at else None),
        })

    return {"opportunities": items, "total": total}


@router.get("/rc3/intelligence", summary="RC3 opportunity intelligence and communication timeline")
async def rc3_opportunity_intelligence(
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import desc, select
    from src.models.jobs import (
        AlertDecisionAudit,
        ApplicationTimelineEvent,
        CareerMemory,
        CommunicationRequest,
        OpportunityConversationContext,
        OpportunityOutcomeEvent,
        OpportunityOutcomeMetric,
        OpportunityConversionMetric,
        VoiceOutcome,
        VoiceSession,
    )

    communications = (await db.execute(
        select(CommunicationRequest)
        .where(CommunicationRequest.user_id == user["sub"])
        .order_by(desc(CommunicationRequest.created_at))
        .limit(limit)
    )).scalars().all()
    contexts = (await db.execute(
        select(OpportunityConversationContext)
        .where(OpportunityConversationContext.user_id == user["sub"])
        .order_by(desc(OpportunityConversationContext.created_at))
        .limit(limit)
    )).scalars().all()
    outcomes = (await db.execute(
        select(OpportunityOutcomeEvent)
        .where(OpportunityOutcomeEvent.user_id == user["sub"])
        .order_by(desc(OpportunityOutcomeEvent.created_at))
        .limit(limit)
    )).scalars().all()
    decisions = (await db.execute(
        select(AlertDecisionAudit)
        .where(AlertDecisionAudit.user_id == user["sub"])
        .order_by(desc(AlertDecisionAudit.created_at))
        .limit(limit)
    )).scalars().all()
    memory = (await db.execute(
        select(CareerMemory)
        .where(CareerMemory.user_id == user["sub"])
        .order_by(desc(CareerMemory.created_at))
        .limit(limit)
    )).scalars().all()
    timeline = (await db.execute(
        select(ApplicationTimelineEvent)
        .where(ApplicationTimelineEvent.user_id == user["sub"])
        .order_by(desc(ApplicationTimelineEvent.created_at))
        .limit(limit)
    )).scalars().all()
    voice_sessions = (await db.execute(
        select(VoiceSession)
        .where(VoiceSession.user_id == user["sub"])
        .order_by(desc(VoiceSession.created_at))
        .limit(limit)
    )).scalars().all()
    voice_outcomes = (await db.execute(
        select(VoiceOutcome)
        .join(VoiceSession, VoiceSession.id == VoiceOutcome.voice_session_id)
        .where(VoiceSession.user_id == user["sub"])
        .order_by(desc(VoiceOutcome.created_at))
        .limit(limit)
    )).scalars().all()
    metrics = (await db.execute(
        select(OpportunityOutcomeMetric)
        .where(OpportunityOutcomeMetric.user_id == user["sub"])
        .order_by(desc(OpportunityOutcomeMetric.calculated_at))
        .limit(limit)
    )).scalars().all()
    conversions = (await db.execute(
        select(OpportunityConversionMetric)
        .where(OpportunityConversionMetric.user_id == user["sub"])
        .order_by(desc(OpportunityConversionMetric.calculated_at))
        .limit(limit)
    )).scalars().all()

    return {
        "communications": [
            {
                "id": row.id,
                "correlation_id": row.correlation_id,
                "job_id": row.job_id,
                "channel": row.channel,
                "status": row.communication_status,
                "provider": row.communication_provider,
                "delivery_attempts": row.delivery_attempts,
                "webhook_status": row.webhook_status,
                "decision_reason": row.decision_reason,
                "decision_factors": row.decision_factors,
                "decision_confidence": row.decision_confidence,
                "created_at": row.created_at.isoformat(),
            }
            for row in communications
        ],
        "conversation_contexts": [
            {
                "context_uid": row.context_uid,
                "job_id": row.job_id,
                "context_confidence": row.context_confidence,
                "context_sources": row.context_sources,
                "conversation_context": row.conversation_context,
                "created_at": row.created_at.isoformat(),
            }
            for row in contexts
        ],
        "outcomes": [
            {
                "id": row.id,
                "job_id": row.job_id,
                "status": row.status,
                "channel": row.channel,
                "created_at": row.created_at.isoformat(),
            }
            for row in outcomes
        ],
        "decisions": [
            {
                "id": row.id,
                "job_id": row.job_id,
                "decision": row.decision,
                "channel": row.channel,
                "reason": row.reason,
                "scores": row.scores,
                "decision_factors": row.decision_factors,
                "decision_confidence": row.decision_confidence,
                "created_at": row.created_at.isoformat(),
            }
            for row in decisions
        ],
        "voice_sessions": [
            {
                "id": row.id,
                "session_uid": row.session_uid,
                "job_id": row.job_id,
                "status": row.status,
                "voice_provider": row.voice_provider,
                "created_at": row.created_at.isoformat(),
            }
            for row in voice_sessions
        ],
        "voice_outcomes": [
            {
                "id": row.id,
                "outcome": row.outcome,
                "provider_status": row.provider_status,
                "call_sid_present": bool(row.call_sid),
                "created_at": row.created_at.isoformat(),
            }
            for row in voice_outcomes
        ],
        "memory": [
            {"id": row.id, "event_type": row.event_type, "title": row.title, "created_at": row.created_at.isoformat()}
            for row in memory
        ],
        "application_timeline": [
            {"id": row.id, "job_id": row.job_id, "status": row.status, "event_type": row.event_type, "created_at": row.created_at.isoformat()}
            for row in timeline
        ],
        "outcome_metrics": [
            {"metric_name": row.metric_name, "metric_value": row.metric_value, "dimensions": row.dimensions, "calculated_at": row.calculated_at.isoformat()}
            for row in metrics
        ],
        "conversion_metrics": [
            {"channel": row.channel, "notified_count": row.notified_count, "conversion_rate": row.conversion_rate, "calculated_at": row.calculated_at.isoformat()}
            for row in conversions
        ],
    }


@router.get("/rc3/timeline/{job_id}", summary="Communication timeline for a specific opportunity")
async def communication_timeline(
    job_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full communication timeline for one opportunity: decisions, deliveries, voice sessions, outcomes."""
    from sqlalchemy import desc, select
    from src.models.jobs import (
        AlertDecisionAudit,
        CommunicationRequest,
        VoiceConversation,
        VoiceOutcome,
        VoiceSession,
        OpportunityOutcomeEvent,
    )

    decisions = (await db.execute(
        select(AlertDecisionAudit)
        .where(AlertDecisionAudit.user_id == user["sub"], AlertDecisionAudit.job_id == job_id)
        .order_by(desc(AlertDecisionAudit.created_at))
    )).scalars().all()

    communications = (await db.execute(
        select(CommunicationRequest)
        .where(CommunicationRequest.user_id == user["sub"], CommunicationRequest.job_id == job_id)
        .order_by(desc(CommunicationRequest.created_at))
    )).scalars().all()

    sessions = (await db.execute(
        select(VoiceSession)
        .where(VoiceSession.user_id == user["sub"], VoiceSession.job_id == job_id)
        .order_by(desc(VoiceSession.created_at))
    )).scalars().all()

    session_ids = [s.id for s in sessions]
    outcomes = []
    conversations = []
    if session_ids:
        outcomes = (await db.execute(
            select(VoiceOutcome)
            .where(VoiceOutcome.voice_session_id.in_(session_ids))
            .order_by(desc(VoiceOutcome.created_at))
        )).scalars().all()
        conversations = (await db.execute(
            select(VoiceConversation)
            .where(VoiceConversation.voice_session_id.in_(session_ids))
            .order_by(VoiceConversation.created_at.asc())
        )).scalars().all()

    outcome_events = (await db.execute(
        select(OpportunityOutcomeEvent)
        .where(OpportunityOutcomeEvent.user_id == user["sub"], OpportunityOutcomeEvent.job_id == job_id)
        .order_by(desc(OpportunityOutcomeEvent.created_at))
    )).scalars().all()

    timeline = []
    for d in decisions:
        timeline.append({"type": "decision", "decision": d.decision, "channel": d.channel, "reason": d.reason, "confidence": d.decision_confidence, "created_at": d.created_at.isoformat()})
    for c in communications:
        timeline.append({"type": "communication", "channel": c.channel, "status": c.communication_status, "provider": c.communication_provider, "delivery_attempts": c.delivery_attempts, "webhook_status": c.webhook_status, "created_at": c.created_at.isoformat()})
    for s in sessions:
        timeline.append({"type": "voice_session", "session_uid": s.session_uid, "status": s.status, "voice_provider": s.voice_provider, "created_at": s.created_at.isoformat()})
    for o in outcomes:
        timeline.append({"type": "voice_outcome", "outcome": o.outcome, "call_sid": o.call_sid, "created_at": o.created_at.isoformat()})
    for e in outcome_events:
        timeline.append({"type": "outcome_event", "status": e.status, "channel": e.channel, "created_at": e.created_at.isoformat()})

    timeline.sort(key=lambda x: x["created_at"])

    return {
        "job_id": job_id,
        "timeline": timeline,
        "summary": {
            "decisions_count": len(decisions),
            "communications_count": len(communications),
            "voice_sessions_count": len(sessions),
            "voice_outcomes_count": len(outcomes),
            "conversation_turns_count": len(conversations),
            "outcome_events_count": len(outcome_events),
        },
        "conversations": [
            {"role": c.role, "content": c.content[:500], "created_at": c.created_at.isoformat()}
            for c in conversations
        ],
    }


@router.post("/rc3/outcomes", summary="Record RC3 opportunity outcome event")
async def rc3_record_outcome(
    request: OutcomeEventRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.opportunity.outcome_intelligence import get_outcome_intelligence_service

    event = await get_outcome_intelligence_service().record_event(
        db,
        user_id=user["sub"],
        job_id=request.job_id,
        communication_request_id=request.communication_request_id,
        status=request.status,
        channel=request.channel,
        data=request.data,
    )
    await get_outcome_intelligence_service().refresh_metrics(db, user_id=user["sub"])
    await db.commit()
    return {"event_uid": event.event_uid, "status": event.status}


@router.post("/rc3/lifecycle/run", summary="Run RC3 opportunity lifecycle agent")
async def rc3_run_lifecycle(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from src.services.opportunity.lifecycle_agent import get_opportunity_lifecycle_agent

    run = await get_opportunity_lifecycle_agent().monitor(db, user_id=user["sub"])
    await db.commit()
    return {
        "run_uid": run.run_uid,
        "status": run.status,
        "monitored_counts": run.monitored_counts,
        "triggered_actions": run.triggered_actions,
    }


@router.post("/alert", summary="Trigger Opportunity Alert Agent for a persisted match")
async def trigger_opportunity_alert(
    request: OpportunityAlertRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from src.models.jobs import Job, JobMatch
    from src.agents.deadline_urgency_agent import get_deadline_urgency_agent
    from src.agents.opportunity_alert_agent import get_opportunity_alert_agent
    from src.db.repositories.domain_repositories import (
        OrchestrationSessionRepository,
        OrchestrationEventRepository,
        GovernanceDecisionRepository,
        AutonomousActionRepository,
    )
    from src.db.repositories.troubleshoot_repository import AuditLogRepository
    from src.services.opportunity.conversational_outbound_call_service import resolve_outbound_recipient_number

    q = select(JobMatch, Job).join(Job, Job.id == JobMatch.job_id).where(
        JobMatch.id == request.match_id,
        JobMatch.user_id == user["sub"],
        JobMatch.deleted_at.is_(None),
        Job.deleted_at.is_(None),
        Job.status == "active",
        Job.apply_url.is_not(None),
        Job.apply_url != "",
    )
    result = await db.execute(q)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Opportunity match not found")

    match, job = row
    source_url = job.apply_url
    if not source_url:
        raise HTTPException(status_code=409, detail="Opportunity lacks provider URL; alert blocked")

    opportunity = {
        "id": str(match.id),
        "job_id": job.id,
        "source_job_id": match.source_job_id or job.job_uid,
        "title": job.title,
        "company": job.company,
        "source": match.source_provider or job.source,
        "source_url": source_url,
        "overall_score": float(match.overall_score or 0.0),
        "freshness_score": float(job.freshness_score or 0.0),
        "provider_quality_score": float(job.provider_quality_score or 0.0),
        "salary_quality_score": float(job.salary_quality_score or 0.0),
        "opportunity_priority_score": float(job.opportunity_priority_score or 0.0),
        "apply_url_valid": bool(job.apply_url_valid),
        "lifecycle_state": job.lifecycle_state,
        "confidence": float(match.confidence or 0.5) if hasattr(match, "confidence") else 0.5,
        "deadline": None,
        "application_urgency": 0,
        "market_demand": 0,
    }

    if request.urgency_score is None:
        urgency_agent = get_deadline_urgency_agent()
        urgency_state = await urgency_agent.evaluate(user["sub"], [opportunity])
        opportunity["urgency_score"] = urgency_state.urgency_scores.get(str(match.id), 0.0)
        urgency_source = "deadline_urgency_agent"
    else:
        opportunity["urgency_score"] = request.urgency_score
        urgency_source = "request_runtime_input"

    session_uid = str(uuid.uuid4())
    session_repo = OrchestrationSessionRepository(db)
    event_repo = OrchestrationEventRepository(db)
    governance_repo = GovernanceDecisionRepository(db)
    action_repo = AutonomousActionRepository(db)
    audit_repo = AuditLogRepository(db)

    session = await session_repo.create(
        session_uid=session_uid,
        user_id=user["sub"],
        graph_name="opportunity_alert_agent",
        status="active",
        current_node="opportunity_alert_agent",
        completion_pct=0.0,
        metadata_={
            "match_id": request.match_id,
            "job_id": job.id,
            "source_url": source_url,
            "urgency_source": urgency_source,
        },
    )
    recipient_resolution = resolve_outbound_recipient_number(request.phone_number)

    await event_repo.create(
        session_id=session.id,
        event_type="alert_started",
        node_name="opportunity_alert_agent",
        agent_name="opportunity_alert",
        payload={
            "match_id": request.match_id,
            "job_id": job.id,
            "source_url": source_url,
            "urgency_score": opportunity["urgency_score"],
            "urgency_source": urgency_source,
            "phone_number_present": bool(recipient_resolution.phone_number),
        },
        status="completed",
    )

    alert_agent = get_opportunity_alert_agent()
    alert_state = await alert_agent.evaluate_and_alert(
        user_id=user["sub"],
        opportunity=opportunity,
        phone_number=recipient_resolution.phone_number,
    )

    verdict = "passed" if alert_state.should_alert else "suppressed"
    action_status = "completed" if alert_state.delivery_status else "failed"
    action = await action_repo.create(
        action_uid=f"alert_action_{alert_state.alert_id}",
        session_id=session.id,
        user_id=user["sub"],
        action_type="opportunity_alert",
        status=action_status,
        confidence=float(opportunity.get("confidence", 0.5)),
        reasoning_chain=[
            f"match_score={alert_state.match_score}",
            f"urgency_score={alert_state.urgency_score}",
            f"delivery_status={alert_state.delivery_status}",
        ],
        evidence_chain={
            "source_url": source_url,
            "source_job_id": opportunity.get("source_job_id"),
            "provider": opportunity.get("source"),
        },
        governance_verdict=verdict,
        suppressed=not alert_state.should_alert,
        suppression_reason=None if alert_state.should_alert else "below_alert_threshold",
        mcp_tool_used="twilio.make_call" if recipient_resolution.phone_number else None,
        mcp_result=alert_state.twilio_result,
        trace_id=alert_state.alert_id,
    )
    governance = await governance_repo.create(
        session_id=session.id,
        action_id=action.id,
        decision_type="opportunity_alert",
        verdict=verdict,
        confidence_before=float(opportunity.get("confidence", 0.5)),
        confidence_after=float(opportunity.get("confidence", 0.5)),
        penalty_applied=0.0,
        reason=f"score={alert_state.match_score}; urgency={alert_state.urgency_score}; status={alert_state.delivery_status}",
        evidence={
            "match_id": request.match_id,
            "job_id": job.id,
            "source_url": source_url,
            "urgency_source": urgency_source,
        },
    )
    audit = await audit_repo.create(
        user_id=user["sub"],
        action="OPPORTUNITY_ALERT_TRIGGERED",
        resource="opportunity_alert_agent",
        resource_id=alert_state.alert_id,
        severity="warning" if alert_state.delivery_status == "blocked_by_credentials" else "info",
        details={
            "session_uid": session_uid,
            "match_id": request.match_id,
            "job_id": job.id,
            "delivery_status": alert_state.delivery_status,
            "failure_reason": alert_state.failure_reason,
            "call_sid": alert_state.call_sid,
            "source_url": source_url,
            "urgency_source": urgency_source,
            "recipient_phone_source": recipient_resolution.source,
        },
    )
    await event_repo.create(
        session_id=session.id,
        event_type="alert_completed",
        node_name="opportunity_alert_agent",
        agent_name="opportunity_alert",
        payload={
            "alert_id": alert_state.alert_id,
            "delivery_status": alert_state.delivery_status,
            "should_alert": alert_state.should_alert,
            "call_sid": alert_state.call_sid,
            "failure_reason": alert_state.failure_reason,
        },
        status="completed",
        duration_ms=int(alert_state.latency_ms),
    )
    try:
        from src.services.events import get_career_event_service

        await get_career_event_service().emit_event(
            db,
            event_type="OpportunityAlertDecided",
            entity_type="opportunity_alert",
            entity_id=str(job.id),
            source_service="api.v1.opportunities.alert",
            user_id=user["sub"],
            source_table="autonomous_actions",
            source_id=action.id,
            payload={
                "match_id": request.match_id,
                "job_id": job.id,
                "alert_id": alert_state.alert_id,
                "decision": verdict,
                "should_alert": alert_state.should_alert,
                "delivery_status": alert_state.delivery_status,
                "call_sid_present": bool(alert_state.call_sid),
                "failure_reason": alert_state.failure_reason,
                "urgency_score": opportunity["urgency_score"],
                "urgency_source": urgency_source,
            },
            evidence=[
                get_career_event_service().build_evidence_ref(
                    table="autonomous_actions",
                    source_id=action.id,
                    note="opportunity alert decision recorded",
                    extra={
                        "verdict": verdict,
                        "delivery_status": alert_state.delivery_status,
                    },
                ),
                get_career_event_service().build_evidence_ref(
                    table="governance_decisions",
                    source_id=governance.id,
                    note="governance verdict applied to the alert",
                    extra={"reason": f"score={alert_state.match_score}; urgency={alert_state.urgency_score}"},
                ),
                get_career_event_service().build_evidence_ref(
                    table="audit_logs",
                    source_id=audit.id,
                    note="audit trail for opportunity alert dispatch",
                ),
            ],
            provider="elevenlabs_convai" if alert_state.call_sid else "career_os",
            status="success" if alert_state.should_alert and alert_state.delivery_status not in {"blocked_by_credentials", "failed"} else ("skipped" if not alert_state.should_alert else "failed"),
            trace_id=alert_state.alert_id,
        )
    except Exception:
        logger.warning("Failed to emit OpportunityAlertDecided audit event", exc_info=True)
    await session_repo.update(
        session.id,
        status="success",
        current_node="end",
        completion_pct=100.0,
        errors={"twilio": alert_state.failure_reason} if alert_state.failure_reason else None,
    )

    return {
        "session_uid": session_uid,
        "alert_id": alert_state.alert_id,
        "status": "success",
        "delivery_status": alert_state.delivery_status,
        "should_alert": alert_state.should_alert,
        "call_sid": alert_state.call_sid,
        "source_url": source_url,
        "urgency_score": alert_state.urgency_score,
        "urgency_source": urgency_source,
        "failure_reason": alert_state.failure_reason,
    }


class SkillGapResponse(BaseModel):
    job_id: int
    job_title: str
    company: str
    resume_skills: list[str]
    job_skills: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    gap_score: float
    recommendation: str


@router.get("/skill-gap/{job_id}", response_model=SkillGapResponse, summary="Compute and persist skill gap analysis")
async def compute_skill_gap(
    job_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute skill gap between user's resume and a specific job, persist the result."""
    from src.models.jobs import Job, JobMatch
    from src.db.repositories.knowledge_repository import KnowledgeRepository
    from sqlalchemy import select
    
    # 1. Get Job
    job_stmt = select(Job).where(Job.id == job_id, Job.deleted_at.is_(None))
    job_result = await db.execute(job_stmt)
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # 2. Get User's latest resume skills
    knowledge_repo = KnowledgeRepository(db)
    docs, _ = await knowledge_repo.find_by_user(user["sub"])
    resume_skills = []
    for doc in docs:
        if doc.analysis_results:
            # Extract skills from analysis results if available, else use a default set
            # For simplicity, we'll assume skills are in the document content or we extract them
            text = doc.content or ""
            # Simple keyword extraction matching the job ingestion logic
            skill_keywords = [
                "python", "javascript", "typescript", "react", "node", "sql", "aws",
                "docker", "kubernetes", "java", "golang", "rust", "c++", "ruby",
                "postgresql", "mongodb", "redis", "graphql", "rest", "api", "linux",
                "git", "ci/cd", "terraform", "ansible", "machine learning", "data",
            ]
            text_lower = text.lower()
            resume_skills.extend([kw for kw in skill_keywords if kw in text_lower])
    
    resume_skills = list(set(resume_skills))
    job_skills = [s.lower() for s in (job.skills_required or [])]
    
    # 3. Skill Comparison
    matched = list(set(resume_skills) & set(job_skills))
    missing = list(set(job_skills) - set(resume_skills))
    
    # 4. Gap Score Calculation (0-100, where 100 is no gap)
    if not job_skills:
        gap_score = 100.0
    else:
        gap_score = round((len(matched) / len(job_skills)) * 100, 1)
        
    recommendation = f"Focus on acquiring: {', '.join(missing[:3])}" if missing else "Excellent skill alignment!"
    
    # 5. Persist Results
    match_stmt = select(JobMatch).where(
        JobMatch.user_id == user["sub"],
        JobMatch.job_id == job_id,
        JobMatch.deleted_at.is_(None)
    )
    match_result = await db.execute(match_stmt)
    match = match_result.scalar_one_or_none()
    
    if match:
        match.gap_score = gap_score
        match.gaps = missing
        match.strengths = matched
        match.recommendation = recommendation
    else:
        # Create new match record if it doesn't exist
        new_match = JobMatch(
            user_id=user["sub"],
            job_id=job_id,
            overall_score=0.0,
            skill_match=len(matched) / max(len(job_skills), 1) * 100,
            gap_score=gap_score,
            strengths=matched,
            gaps=missing,
            recommendation=recommendation
        )
        db.add(new_match)
        
    await db.commit()
    
    return SkillGapResponse(
        job_id=job.id,
        job_title=job.title,
        company=job.company or "Unknown",
        resume_skills=resume_skills,
        job_skills=job_skills,
        matched_skills=matched,
        missing_skills=missing,
        gap_score=gap_score,
        recommendation=recommendation
    )
