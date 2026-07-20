"""Async background task for job matching pipeline.

Runs recalculate_matches in the ARQ worker with progress updates
published to orchestration_sessions.
"""
import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.observability.langsmith import traceable
from src.db.session import async_session
from src.models.orchestration import OrchestrationSession
from src.services.opportunity.conversational_outbound_call_service import resolve_outbound_recipient_number

logger = logging.getLogger(__name__)


def _utc_iso(value: datetime | None = None) -> str:
    """Return an explicit UTC ISO-8601 timestamp for client-side rendering."""
    current = value or datetime.utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _clone_metadata(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a detached JSON-safe copy so nested mutations persist to SQLAlchemy JSON columns."""
    return deepcopy(payload or {})


@traceable(name="recalculate_all_jobs_async")
async def recalculate_all_jobs_async(
    ctx: Dict[str, Any],
    session_id: int,
    allow_paid_providers: bool = True,
) -> Dict[str, Any]:
    """Background task to score all jobs against a resume and update session progress.

    Called by ARQ worker via: pool.enqueue_job('recalculate_all_jobs_async', session_id)

    Updates orchestration_sessions row with progress as each job is scored.
    """
    job_id = ctx.get('job_id', 'unknown')
    logger.info(
        "async job matching started",
        extra={
            "task": "recalculate_all_jobs_async",
            "job_id": job_id,
            "session_id": session_id,
            "allow_paid_providers": allow_paid_providers,
        },
    )

    async with async_session() as db:
        result = await db.execute(select(OrchestrationSession).where(OrchestrationSession.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            logger.error("session not found", extra={"session_id": session_id})
            return {"status": "failed", "error": "session not found"}

        async def _emit_refresh_audit_events(final_status: str, *, evaluated: int, failed: int, total: int) -> None:
            try:
                from src.services.events import get_career_event_service

                event_service = get_career_event_service()
                metadata = _clone_metadata(session.metadata_)
                provider_health = metadata.get("provider_health") or {}
                refresh_summary = metadata.get("refresh_summary") or {}
                provider_results = list(metadata.get("provider_results") or [])
                await event_service.emit_event(
                    db,
                    event_type="JobRefreshCompleted",
                    entity_type="job_refresh_session",
                    entity_id=session.session_uid,
                    source_service="workers.job_matching",
                    user_id=user_id,
                    source_table="orchestration_sessions",
                    source_id=session.id,
                    payload={
                        "status": final_status,
                        "evaluated": evaluated,
                        "failed": failed,
                        "total": total,
                        "provider_health": provider_health,
                        "refresh_summary": refresh_summary,
                        "provider_result_count": len(provider_results),
                    },
                    evidence=[
                        event_service.build_evidence_ref(
                            table="orchestration_sessions",
                            source_id=session.id,
                            note="job refresh worker completed the run",
                            extra={
                                "status": final_status,
                                "evaluated": evaluated,
                                "failed": failed,
                            },
                        )
                    ],
                    provider=(provider_health.get("theirstack") or {}).get("provider") if isinstance(provider_health.get("theirstack"), dict) else None,
                    trace_id=session.session_uid,
                    status="success" if final_status == "completed" else "failed",
                )
                if provider_health:
                    await event_service.emit_event(
                        db,
                        event_type="ProviderHealthChanged",
                        entity_type="provider_health_snapshot",
                        entity_id=session.session_uid,
                        source_service="workers.job_matching",
                        user_id=user_id,
                        source_table="orchestration_sessions",
                        source_id=session.id,
                        payload={
                            "provider_health": provider_health,
                            "refresh_summary": refresh_summary,
                            "provider_result_count": len(provider_results),
                        },
                        evidence=[
                            event_service.build_evidence_ref(
                                table="orchestration_sessions",
                                source_id=session.id,
                                note="provider health snapshot captured after job refresh",
                                extra={"provider_result_count": len(provider_results)},
                            )
                        ],
                        provider=(provider_health.get("theirstack") or {}).get("provider") if isinstance(provider_health.get("theirstack"), dict) else None,
                        trace_id=session.session_uid,
                    )
            except Exception:
                logger.warning("Failed to emit job refresh audit events", exc_info=True)

        async def _publish_stage(node: str) -> None:
            session.current_node = node
            metadata = _clone_metadata(session.metadata_)
            metadata["current_stage"] = node
            metadata["updated_at"] = _utc_iso()
            history = list(metadata.get("stage_history") or [])
            history.append({
                "node": node,
                "label": node.replace("_", " ").title(),
                "at": _utc_iso(),
            })
            metadata["stage_history"] = history[-20:]
            session.metadata_ = metadata
            await db.commit()

        session.status = "running"
        session.current_node = "match_jobs"
        metadata = _clone_metadata(session.metadata_)
        metadata["progress"] = {"processed": 0, "total": 0, "failed": 0}
        session.metadata_ = metadata
        await db.commit()

        try:
            from src.models.jobs import Job
            from src.models.knowledge import KnowledgeDoc
            from src.services.opportunity.job_intelligence_service import get_job_intelligence_service

            svc = get_job_intelligence_service()

            metadata = _clone_metadata(session.metadata_)
            resume_doc_uid = metadata.get("resume_doc_uid")
            user_id = session.user_id

            resume_result = await db.execute(
                select(KnowledgeDoc).where(
                    KnowledgeDoc.doc_uid == resume_doc_uid,
                    KnowledgeDoc.deleted_at.is_(None),
                )
            )
            resume = resume_result.scalar_one_or_none()
            profile = svc.resume_profile(resume) if resume else {}

            await _publish_stage("fetch_jobs")
            preferences = metadata.get("preferences", {})

            from src.services.jobs import get_job_ingestion_engine
            sync_result = await get_job_ingestion_engine().sync_jobs(
                admin_initiated=allow_paid_providers,
                resume_profile=profile or None,
                preferences=preferences,
                stage_callback=_publish_stage,
            )
            metadata = _clone_metadata(session.metadata_)
            metadata["provider_health"] = {
                "theirstack": sync_result.get("theirstack", {}).get("provider_health"),
                "sync_status": sync_result.get("theirstack", {}).get("provider_health", {}).get("status")
                if isinstance(sync_result.get("theirstack", {}).get("provider_health"), dict)
                else None,
                "summary": {
                    "found": sync_result.get("theirstack", {}).get("found", 0),
                    "normalized": sync_result.get("theirstack", {}).get("normalized", 0),
                    "added": sync_result.get("theirstack", {}).get("added", 0),
                    "updated": sync_result.get("theirstack", {}).get("updated", 0),
                    "errors": list(sync_result.get("theirstack", {}).get("errors", [])),
                },
            }
            provider_results = list(sync_result.get("provider_results", []))
            provider_query_contexts = list(sync_result.get("provider_query_contexts", []))
            sample_updated_jobs = list(sync_result.get("sample_updated_jobs", []))
            refresh_summary = dict(sync_result.get("refresh_summary") or {})
            diagnostics = {
                "status": "running" if session.status == "running" else session.status,
                "reason_code": (sync_result.get("visibility_reason") or {}).get("code", "unknown"),
                "reason": (sync_result.get("visibility_reason") or {}).get("message", "Refresh diagnostics unavailable."),
                "summary": refresh_summary or {
                    "found": sync_result.get("found", 0),
                    "added": sync_result.get("added", 0),
                    "updated": sync_result.get("updated", 0),
                    "duplicates_removed": sync_result.get("duplicates_removed", 0),
                    "expired_removed": sync_result.get("expired_removed", 0),
                    "errors": sync_result.get("errors", 0),
                    "embedded": sync_result.get("embedded", 0),
                },
                "provider_results": provider_results,
                "visibility_reason": sync_result.get("visibility_reason", {}),
                "provider_query_contexts": provider_query_contexts,
                "sample_updated_jobs": sample_updated_jobs,
            }
            metadata["provider_results"] = provider_results
            metadata["provider_query_contexts"] = provider_query_contexts
            metadata["sample_updated_jobs"] = sample_updated_jobs
            metadata["refresh_summary"] = diagnostics["summary"]
            metadata["visibility_reason"] = sync_result.get("visibility_reason", {})
            metadata["diagnostics"] = diagnostics
            session.metadata_ = metadata
            await db.commit()

            if not resume:
                session.status = "completed"
                session.current_node = "completed"
                session.completion_pct = 100.0
                metadata = _clone_metadata(session.metadata_)
                diagnostics = dict(metadata.get("diagnostics") or {})
                diagnostics["status"] = session.status
                metadata["diagnostics"] = diagnostics
                session.metadata_ = metadata
                await db.commit()
                await _emit_refresh_audit_events("completed", evaluated=0, failed=0, total=0)
                logger.info("Provider ingestion completed (no resume for matching)", extra={"session_id": session_id})
                return {"status": "completed", "mode": "provider_only", "evaluated": 0}

            await _publish_stage("get_profile")

            from src.services.resume_experience_extractor import extract_resume_experience
            candidate_exp = extract_resume_experience(
                resume_text=resume.raw_text if hasattr(resume, 'raw_text') else None,
                analysis_results=resume.analysis_results if hasattr(resume, 'analysis_results') else None,
            )
            candidate_years = candidate_exp.get("years_of_experience")
            candidate_level = candidate_exp.get("experience_level", "unknown")

            await _publish_stage("match_jobs")
            jobs_result = await db.execute(
                select(Job).where(
                    Job.status == "active",
                    Job.deleted_at.is_(None),
                    Job.is_india_eligible == True,
                    Job.is_tech_role == True,
                    Job.apply_url.is_not(None),
                    Job.apply_url != "",
                    Job.lifecycle_state.notin_(["APPLIED", "INTERVIEWING", "OFFERED", "HIRED", "EXPIRED"]),
                    (Job.freshness_bucket.is_(None) | (Job.freshness_bucket != "stale")),
                ).limit(600)
            )
            jobs = jobs_result.scalars().all()

            metadata = _clone_metadata(session.metadata_)
            progress = dict(metadata.get("progress") or {})
            progress["total"] = len(jobs)
            metadata["progress"] = progress
            session.metadata_ = metadata
            await db.commit()

            evaluated = 0
            failed = 0

            for i, job in enumerate(jobs):
                try:
                    details = svc.score_job(profile, job)
                    from src.models.jobs import JobMatch

                    source_job_id = job.source_job_id or job.job_uid
                    existing = await db.execute(
                        select(JobMatch).where(
                            JobMatch.user_id == user_id,
                            JobMatch.source_job_id == source_job_id,
                            JobMatch.resume_doc_uid == resume.doc_uid,
                        )
                    )
                    match = existing.scalar_one_or_none()

                    from src.services.job_role_filter import is_job_eligible_for_candidate
                    exp_compat = is_job_eligible_for_candidate(
                        job_min_years=job.experience_min_years,
                        job_max_years=job.experience_max_years,
                        job_seniority=job.seniority_level,
                        candidate_years=candidate_years,
                        candidate_level=candidate_level,
                    )
                    if not exp_compat["eligible"]:
                        logger.info("job excluded by experience filter", extra={
                            "job_uid": job.job_uid,
                            "reason": exp_compat["reason"],
                        })
                        continue

                    exp_penalty = 0
                    if exp_compat["match_type"] == "overqualified":
                        exp_penalty = 10
                    elif candidate_level != "unknown" and job.seniority_level:
                        level_order = {"entry": 0, "junior": 1, "mid": 2, "senior": 3, "lead": 4}
                        diff = level_order.get(candidate_level, 2) - level_order.get(job.seniority_level, 2)
                        exp_penalty = max(0, min(20, diff * -5))
                    details["overall_match"] = max(0, details["overall_match"] - exp_penalty)

                    strengths = [
                        {"id": f"{job.job_uid}-{c['key']}", "title": c["label"], "impact": "high" if c["score"] >= 80 else "medium", "description": c["reason"]}
                        for c in details.get("components", [])
                        if c["score"] >= 70
                    ][:6]
                    gaps = [
                        {"id": f"{job.job_uid}-{c['key']}", "category": c["label"], "severity": "high" if c["score"] < 40 else "medium", "description": ", ".join(c.get("missing", [])) or c["reason"], "suggestion": c.get("suggestion", "")}
                        for c in details.get("components", [])
                        if c["score"] < 70 or c.get("missing")
                    ][:6]
                    if exp_penalty > 0:
                        gaps.append({"id": f"{job.job_uid}-experience", "category": "Experience Fit", "severity": "medium", "description": exp_compat["reason"], "suggestion": ""})

                    if match:
                        match.job_id = job.id
                        match.source_provider = job.source
                        match.source_url = job.source_url
                        match.ingested_at = job.ingested_at
                        match.overall_score = details["overall_match"]
                        match.skill_match = details["dimensions"]["skill_match"]
                        match.experience_match = details["dimensions"]["experience_match"]
                        match.education_match = details["dimensions"]["education_match"]
                        match.gap_score = 100.0 - details["overall_match"]
                        match.strengths = strengths
                        match.gaps = gaps
                        match.recommendation = details["reason"]
                        match.match_details = details
                        match.resume_doc_uid = resume.doc_uid
                        match.resume_name = resume.title
                    else:
                        db.add(JobMatch(
                            user_id=user_id,
                            job_id=job.id,
                            source_job_id=source_job_id,
                            source_provider=job.source,
                            source_url=job.source_url,
                            ingested_at=job.ingested_at,
                            overall_score=details["overall_match"],
                            skill_match=details["dimensions"]["skill_match"],
                            experience_match=details["dimensions"]["experience_match"],
                            education_match=details["dimensions"]["education_match"],
                            gap_score=100.0 - details["overall_match"],
                            strengths=strengths,
                            gaps=gaps,
                            recommendation=details["reason"],
                            match_details=details,
                            resume_doc_uid=resume.doc_uid,
                            resume_name=resume.title,
                        ))
                    evaluated += 1
                except Exception as e:
                    logger.warning("job scoring failed for single job", extra={"job_uid": job.job_uid, "error": str(e)})
                    failed += 1

                if (i + 1) % 10 == 0 or (i + 1) == len(jobs):
                    metadata = _clone_metadata(session.metadata_)
                    progress = dict(metadata.get("progress") or {})
                    progress["processed"] = evaluated
                    progress["failed"] = failed
                    metadata["progress"] = progress
                    session.metadata_ = metadata
                    session.completion_pct = round(((i + 1) / len(jobs)) * 100, 1)
                    await db.commit()

            await _publish_stage("rank_jobs")
            session.status = "completed"
            session.completion_pct = 100.0
            session.current_node = "completed"
            metadata = _clone_metadata(session.metadata_)
            diagnostics = dict(metadata.get("diagnostics") or {})
            diagnostics["status"] = session.status
            metadata["diagnostics"] = diagnostics
            session.metadata_ = metadata
            await db.commit()
            await _emit_refresh_audit_events("completed", evaluated=evaluated, failed=failed, total=len(jobs))

            try:
                from src.models.jobs import JobMatch, Job
                top_match_result = await db.execute(
                    select(JobMatch, Job).join(Job, Job.id == JobMatch.job_id).where(
                        JobMatch.user_id == user_id,
                        JobMatch.resume_doc_uid == resume.doc_uid,
                        JobMatch.deleted_at.is_(None),
                        Job.deleted_at.is_(None),
                        Job.status == "active",
                        Job.is_india_eligible == True,
                        Job.is_tech_role == True,
                        Job.apply_url.is_not(None),
                        Job.apply_url != "",
                        JobMatch.overall_score.is_not(None),
                    ).order_by(JobMatch.overall_score.desc()).limit(1)
                )
                top_row = top_match_result.first()
                if top_row:
                    match, job = top_row
                    score_value = float(match.overall_score or 0)
                    logger.info(
                        "top match selected for alert dispatch",
                        extra={
                            "session_id": session_id,
                            "job_id": job.id,
                            "job_uid": job.job_uid,
                            "match_score": score_value,
                            "threshold": settings.CALL_ALERT_MIN_MATCH_SCORE,
                            "resume_doc_uid": resume.doc_uid if resume else None,
                            "phone_number_present": bool(resolve_outbound_recipient_number().phone_number),
                        },
                    )
                    if score_value >= settings.CALL_ALERT_MIN_MATCH_SCORE:
                        from src.agents.opportunity_alert_agent import get_opportunity_alert_agent
                        recipient_resolution = resolve_outbound_recipient_number()
                        opportunity = {
                            "id": str(match.id),
                            "job_id": job.id,
                            "source_job_id": match.source_job_id or job.job_uid,
                            "title": job.title,
                            "company": job.company,
                            "company_description": job.original_provider_metadata.get("company_description") if job.original_provider_metadata else None,
                            "source": match.source_provider or job.source,
                            "source_url": job.apply_url,
                            "apply_url": job.apply_url,
                            "description": job.description,
                            "location": job.location,
                            "employment_type": job.original_provider_metadata.get("employment_type") if job.original_provider_metadata else None,
                            "experience_level": job.seniority_level,
                            "overall_score": score_value,
                            "freshness_score": float(job.freshness_score or 0.0),
                            "opportunity_priority_score": float(job.opportunity_priority_score or 0.0),
                            "urgency_score": float(job.freshness_score or 0.0),
                            "lifecycle_state": job.lifecycle_state,
                            "salary_range": job.salary_range,
                            "skills_required": job.skills_required or [],
                            "matched_skills": (match.strengths or []),
                            "missing_skills": (match.gaps or []),
                            "resume_strengths": (match.strengths or []),
                            "resume_gaps": (match.gaps or []),
                            "interview_focus_areas": [],
                            "confidence": float(match.confidence or 0.5) if hasattr(match, "confidence") else 0.5,
                            "deadline": None,
                        }
                        alert_state = await get_opportunity_alert_agent().evaluate_and_alert(
                            user_id=user_id,
                            opportunity=opportunity,
                            phone_number=recipient_resolution.phone_number,
                        )
                        logger.info(
                            "top match alert dispatch completed",
                            extra={
                                "session_id": session_id,
                                "job_id": job.id,
                                "alert_id": alert_state.alert_id,
                                "decision": alert_state.channel,
                                "delivery_status": alert_state.delivery_status,
                                "failure_reason": alert_state.failure_reason,
                                "call_sid": alert_state.call_sid,
                            },
                        )
                    else:
                        logger.info(
                            "top match below call threshold",
                            extra={
                                "session_id": session_id,
                                "job_id": job.id,
                                "match_score": score_value,
                                "threshold": settings.CALL_ALERT_MIN_MATCH_SCORE,
                            },
                        )
                else:
                    logger.info(
                        "no top match found for alert dispatch",
                        extra={"session_id": session_id, "resume_doc_uid": resume.doc_uid if resume else None},
                    )
            except Exception as alert_exc:
                logger.exception("Top-match alert dispatch skipped", extra={"session_id": session_id})

            logger.info("async job matching completed", extra={
                "session_id": session_id,
                "evaluated": evaluated,
                "failed": failed,
                "total": len(jobs),
            })
            return {"status": "completed", "evaluated": evaluated, "failed": failed}

        except Exception as e:
            logger.exception("async job matching failed", extra={"session_id": session_id, "error": str(e)})
            session.status = "failed"
            session.errors = {"message": str(e)}
            metadata = _clone_metadata(session.metadata_)
            diagnostics = dict(metadata.get("diagnostics") or {})
            diagnostics["status"] = session.status
            diagnostics["reason_code"] = diagnostics.get("reason_code") or "worker_failed"
            diagnostics["reason"] = diagnostics.get("reason") or str(e)
            metadata["diagnostics"] = diagnostics
            session.metadata_ = metadata
            await db.commit()
            return {"status": "failed", "error": str(e)}
