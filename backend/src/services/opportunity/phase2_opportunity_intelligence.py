"""Phase 2 autonomous opportunity intelligence services.

This layer only enriches real persisted jobs and existing resume/job matches.
It does not create opportunities or seed market data.
"""

from __future__ import annotations

import re
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import (
    AlertDecisionAudit,
    ApplicationTimelineEvent,
    CareerMemory,
    InterviewPreparationPlan,
    Job,
    JobMatch,
    OpportunityIntelligenceReport,
    SalaryIntelligence,
)
from src.services.opportunity.job_intelligence_service import get_job_intelligence_service
from src.core.config import settings
from src.services.opportunity.conversational_outbound_call_service import resolve_outbound_recipient_number

logger = logging.getLogger(__name__)


class SalaryIntelligenceEngine:
    """Extract and normalize salary signals from provider fields and descriptions."""

    def analyze(self, job: Job) -> Dict[str, Any]:
        raw = " ".join([job.salary_range or "", job.description or ""])
        values, currency, period, evidence = self._extract(raw)
        if not values:
            estimate = self._market_estimate(job)
            return {
                **estimate,
                "source": "market_estimation",
                "evidence": {"provider_salary": job.salary_range, "description_matches": [], "estimation_basis": estimate["evidence"]},
            }

        salary_min = min(values)
        salary_max = max(values)
        normalized = self._normalize(salary_min, salary_max, currency, period)
        confidence = 0.85 if job.salary_range else 0.65
        return {
            **normalized,
            "salary_confidence": confidence,
            "source": "provider_supplied" if job.salary_range else "description_extraction",
            "evidence": {"provider_salary": job.salary_range, "description_matches": evidence},
        }

    def _extract(self, text: str) -> Tuple[List[float], str, str, List[str]]:
        evidence: List[str] = []
        values: List[float] = []
        currency = "USD"
        period = "year"
        lowered = text.lower()
        if "₹" in text or "inr" in lowered or "lpa" in lowered or "lakhs" in lowered:
            currency = "INR"
        elif "€" in text or "eur" in lowered:
            currency = "EUR"
        elif "£" in text or "gbp" in lowered:
            currency = "GBP"
        if any(term in lowered for term in ["per month", "/month", "monthly", "month"]):
            period = "month"
        if any(term in lowered for term in ["per hour", "/hour", "hourly"]):
            period = "hour"

        for match in re.finditer(r"(?i)(?:₹|\$|€|£|inr|usd|eur|gbp)?\s*(\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)\s*(lpa|lakhs|k|000|per month|monthly|per year|yearly|per hour|hourly)?", text):
            left = float(match.group(1))
            right = float(match.group(2))
            suffix = (match.group(3) or "").lower()
            values.extend([self._scale(left, suffix, currency), self._scale(right, suffix, currency)])
            evidence.append(match.group(0).strip()[:120])
        for match in re.finditer(r"(?i)(?:₹|\$|€|£|inr|usd|eur|gbp)\s*(\d{4,7})(?:\s*(?:per|/)\s*(year|month|hour))?", text):
            values.append(float(match.group(1)))
            evidence.append(match.group(0).strip()[:120])
        return values[:8], currency, period, evidence[:5]

    def _scale(self, value: float, suffix: str, currency: str) -> float:
        if suffix in {"lpa", "lakhs"}:
            return value * 100000
        if suffix in {"k"}:
            return value * 1000
        if currency == "INR" and value < 1000:
            return value * 100000
        return value

    def _normalize(self, salary_min: float, salary_max: float, currency: str, period: str) -> Dict[str, Any]:
        if period == "month":
            monthly_min, monthly_max = salary_min, salary_max
            yearly_min, yearly_max = salary_min * 12, salary_max * 12
        elif period == "hour":
            yearly_min, yearly_max = salary_min * 2080, salary_max * 2080
            monthly_min, monthly_max = yearly_min / 12, yearly_max / 12
        else:
            yearly_min, yearly_max = salary_min, salary_max
            monthly_min, monthly_max = salary_min / 12, salary_max / 12
        return {
            "salary_min": round(salary_min, 2),
            "salary_max": round(salary_max, 2),
            "salary_currency": currency,
            "salary_period": period,
            "monthly_min": round(monthly_min, 2),
            "monthly_max": round(monthly_max, 2),
            "yearly_min": round(yearly_min, 2),
            "yearly_max": round(yearly_max, 2),
        }

    def _market_estimate(self, job: Job) -> Dict[str, Any]:
        text = f"{job.title} {job.description}".lower()
        currency = "INR" if "india" in text or "kerala" in text or "bengaluru" in text else "USD"
        if any(term in text for term in ["intern", "trainee", "junior"]):
            salary_min, salary_max = ((15000, 35000) if currency == "INR" else (30000, 55000))
            period = "month" if currency == "INR" and salary_max < 100000 else "year"
        elif any(term in text for term in ["senior", "lead", "principal"]):
            salary_min, salary_max = ((1200000, 3000000) if currency == "INR" else (90000, 160000))
            period = "year"
        else:
            salary_min, salary_max = ((400000, 1200000) if currency == "INR" else (55000, 110000))
            period = "year"
        normalized = self._normalize(float(salary_min), float(salary_max), currency, period)
        return {
            **normalized,
            "salary_confidence": 0.35,
            "evidence": {
                "role_title": job.title,
                "provider": job.source_provider or job.source,
                "note": "Market estimate used because provider did not supply a parseable salary.",
            },
        }


class Phase2OpportunityIntelligenceService:
    def __init__(self) -> None:
        self.salary_engine = SalaryIntelligenceEngine()

    async def generate_for_user(
        self,
        db: AsyncSession,
        user_id: str,
        resume_doc_uid: Optional[str] = None,
        limit: int = 120,
    ) -> Dict[str, Any]:
        resume = await get_job_intelligence_service().get_active_resume(db, user_id, resume_doc_uid)
        resume_uid = resume.doc_uid if resume else resume_doc_uid
        stmt = (
            select(JobMatch, Job)
            .join(Job, Job.id == JobMatch.job_id)
            .where(
                JobMatch.user_id == user_id,
                JobMatch.deleted_at.is_(None),
                Job.status == "active",
                Job.deleted_at.is_(None),
                Job.apply_url.is_not(None),
                Job.apply_url != "",
            )
            .order_by(desc(JobMatch.overall_score), desc(Job.opportunity_priority_score))
            .limit(limit)
        )
        if resume_uid:
            stmt = stmt.where(JobMatch.resume_doc_uid == resume_uid)
        rows = (await db.execute(stmt)).all()

        reports = 0
        salaries = 0
        interviews = 0
        decisions = 0
        memories = 0
        for match, job in rows:
            salary = await self._upsert_salary(db, job)
            salaries += 1
            report_payload = self._build_report(match, job, salary)
            await self._upsert_report(db, user_id, job, resume_uid, report_payload)
            reports += 1
            if float(match.overall_score or 0) >= 60:
                await self._upsert_interview_prep(db, user_id, job, resume_uid, match)
                interviews += 1
            await self._record_alert_decision(db, user_id, job, report_payload)
            decisions += 1
            created = await self._remember(db, user_id, "OPPORTUNITY_RANKED", job, "opportunity_intelligence_reports", str(job.id), {
                "rank_score": report_payload["opportunity_rank_score"],
                "decision": report_payload["recommended_priority"],
            })
            memories += 1 if created else 0

        await db.commit()

        top_report = reports and (await db.execute(
            select(OpportunityIntelligenceReport, Job)
            .join(Job, Job.id == OpportunityIntelligenceReport.job_id)
            .where(OpportunityIntelligenceReport.user_id == user_id)
            .order_by(desc(OpportunityIntelligenceReport.opportunity_rank_score))
            .limit(1)
        )).first()
        if top_report:
            report, job = top_report
            try:
                score = float(report.opportunity_rank_score or 0)
                if score >= settings.CALL_ALERT_MIN_MATCH_SCORE:
                    from src.agents.opportunity_alert_agent import get_opportunity_alert_agent
                    logger.info(
                        "phase2 top opportunity selected for alert dispatch",
                        extra={
                            "user_id": user_id,
                            "job_id": job.id,
                            "score": score,
                            "threshold": settings.CALL_ALERT_MIN_MATCH_SCORE,
                        },
                    )
                    recipient_resolution = resolve_outbound_recipient_number()
                    await get_opportunity_alert_agent().evaluate_and_alert(
                        user_id=user_id,
                        opportunity={
                            "id": str(job.id),
                            "job_id": job.id,
                            "source_job_id": job.source_job_id or job.job_uid,
                            "title": job.title,
                            "company": job.company,
                            "company_description": job.original_provider_metadata.get("company_description") if job.original_provider_metadata else None,
                            "source": job.source,
                            "source_url": job.apply_url or job.source_url,
                            "apply_url": job.apply_url or job.source_url,
                            "description": job.description,
                            "location": job.location,
                            "employment_type": job.original_provider_metadata.get("employment_type") if job.original_provider_metadata else None,
                            "experience_level": job.seniority_level,
                            "overall_score": score,
                            "freshness_score": float(job.freshness_score or 0.0),
                            "opportunity_priority_score": float(job.opportunity_priority_score or 0.0),
                            "urgency_score": float(job.freshness_score or 0.0),
                            "lifecycle_state": job.lifecycle_state,
                            "salary_range": job.salary_range,
                            "skills_required": job.skills_required or [],
                            "matched_skills": (report.report or {}).get("matched_skills", []),
                            "missing_skills": (report.report or {}).get("missing_skills", []),
                            "resume_strengths": (report.report or {}).get("matched_skills", []),
                            "resume_gaps": (report.report or {}).get("missing_skills", []),
                            "interview_focus_areas": (report.report or {}).get("interview_focus_areas", []),
                            "confidence": float(report.confidence or 0.5) if hasattr(report, "confidence") else 0.5,
                            "deadline": None,
                        },
                        phone_number=recipient_resolution.phone_number,
                    )
            except Exception as exc:
                logger.exception("phase2 alert dispatch failed", extra={"user_id": user_id, "error": str(exc)})

        return {
            "status": "completed",
            "resume_doc_uid": resume_uid,
            "jobs_analyzed": len(rows),
            "reports_written": reports,
            "salary_records": salaries,
            "interview_plans": interviews,
            "alert_decisions": decisions,
            "career_memory_events": memories,
        }

    async def dashboard(self, db: AsyncSession, user_id: str, days: int = 90) -> Dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=days)
        reports = (await db.execute(
            select(OpportunityIntelligenceReport, Job)
            .join(Job, Job.id == OpportunityIntelligenceReport.job_id)
            .where(OpportunityIntelligenceReport.user_id == user_id)
            .order_by(desc(OpportunityIntelligenceReport.opportunity_rank_score))
            .limit(20)
        )).all()
        timeline = (await db.execute(
            select(CareerMemory).where(CareerMemory.user_id == user_id, CareerMemory.created_at >= since).order_by(desc(CareerMemory.created_at)).limit(50)
        )).scalars().all()
        app_events = (await db.execute(
            select(ApplicationTimelineEvent).where(ApplicationTimelineEvent.user_id == user_id).order_by(desc(ApplicationTimelineEvent.created_at)).limit(100)
        )).scalars().all()
        alert_rows = (await db.execute(
            select(AlertDecisionAudit.decision, func.count(AlertDecisionAudit.id))
            .where(AlertDecisionAudit.user_id == user_id)
            .group_by(AlertDecisionAudit.decision)
        )).all()
        skills = self._aggregate_skills([r.evidence or {} for r, _ in reports])
        return {
            "opportunity_funnel": {
                "ranked": len(reports),
                "applied": len({e.job_id for e in app_events if e.status in {"APPLIED", "INTERVIEWING", "OFFER", "OFFERED", "REJECTED"}}),
                "interview": len({e.job_id for e in app_events if e.status == "INTERVIEWING"}),
                "offer": len({e.job_id for e in app_events if e.status in {"OFFER", "OFFERED", "HIRED"}}),
            },
            "skills_dashboard": skills,
            "application_analytics": self._application_analytics(app_events),
            "opportunity_trends": self._opportunity_trends(reports),
            "alert_decisions": {decision: int(count) for decision, count in alert_rows},
            "career_timeline": [
                {
                    "event_type": item.event_type,
                    "job_id": item.job_id,
                    "title": item.title,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "data": item.data or {},
                }
                for item in timeline
            ],
            "top_opportunities": [self._report_summary(report, job) for report, job in reports[:10]],
        }

    async def get_job_intelligence(self, db: AsyncSession, user_id: str, job_id: int) -> Dict[str, Any]:
        report_row = (await db.execute(
            select(OpportunityIntelligenceReport).where(
                OpportunityIntelligenceReport.user_id == user_id,
                OpportunityIntelligenceReport.job_id == job_id,
            ).order_by(desc(OpportunityIntelligenceReport.updated_at)).limit(1)
        )).scalar_one_or_none()
        salary = (await db.execute(select(SalaryIntelligence).where(SalaryIntelligence.job_id == job_id))).scalar_one_or_none()
        prep = (await db.execute(
            select(InterviewPreparationPlan).where(InterviewPreparationPlan.user_id == user_id, InterviewPreparationPlan.job_id == job_id).order_by(desc(InterviewPreparationPlan.updated_at)).limit(1)
        )).scalar_one_or_none()
        timeline = (await db.execute(
            select(ApplicationTimelineEvent).where(ApplicationTimelineEvent.user_id == user_id, ApplicationTimelineEvent.job_id == job_id).order_by(ApplicationTimelineEvent.created_at)
        )).scalars().all()
        decisions = (await db.execute(
            select(AlertDecisionAudit).where(AlertDecisionAudit.user_id == user_id, AlertDecisionAudit.job_id == job_id).order_by(desc(AlertDecisionAudit.created_at)).limit(5)
        )).scalars().all()
        return {
            "report": self._serialize_report(report_row) if report_row else None,
            "salary": self._serialize_salary(salary) if salary else None,
            "interview_prep": self._serialize_prep(prep) if prep else None,
            "application_timeline": [
                {
                    "status": e.status,
                    "event_type": e.event_type,
                    "notes": e.notes,
                    "metadata": e.metadata_ or {},
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in timeline
            ],
            "alert_decisions": [
                {
                    "decision": d.decision,
                    "channel": d.channel,
                    "reason": d.reason,
                    "scores": d.scores or {},
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in decisions
            ],
        }

    async def record_application_event(
        self,
        db: AsyncSession,
        user_id: str,
        job_id: int,
        status: str,
        notes: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        job = await db.get(Job, job_id)
        event = ApplicationTimelineEvent(
            user_id=user_id,
            job_id=job_id,
            status=status,
            event_type="STATUS_CHANGE",
            notes=notes,
            metadata_=metadata or {},
        )
        db.add(event)
        if job:
            await self._remember(db, user_id, f"APPLICATION_{status}", job, "application_timeline_events", "", {"notes": notes})

    async def _upsert_salary(self, db: AsyncSession, job: Job) -> Dict[str, Any]:
        payload = self.salary_engine.analyze(job)
        existing = (await db.execute(select(SalaryIntelligence).where(SalaryIntelligence.job_id == job.id))).scalar_one_or_none()
        if not existing:
            existing = SalaryIntelligence(job_id=job.id)
            db.add(existing)
        for key, value in payload.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        return payload

    async def _upsert_report(
        self,
        db: AsyncSession,
        user_id: str,
        job: Job,
        resume_doc_uid: Optional[str],
        payload: Dict[str, Any],
    ) -> None:
        existing = (await db.execute(select(OpportunityIntelligenceReport).where(
            OpportunityIntelligenceReport.user_id == user_id,
            OpportunityIntelligenceReport.job_id == job.id,
            OpportunityIntelligenceReport.resume_doc_uid == resume_doc_uid,
        ))).scalar_one_or_none()
        if not existing:
            existing = OpportunityIntelligenceReport(user_id=user_id, job_id=job.id, resume_doc_uid=resume_doc_uid)
            db.add(existing)
        for key in [
            "match_score", "skill_gap_score", "learning_effort_score", "application_urgency",
            "competition_risk", "domain_alignment", "career_growth_potential", "salary_potential",
            "remote_compatibility", "opportunity_rank_score", "recommended_priority", "report", "evidence",
        ]:
            setattr(existing, key, payload[key])
        existing.updated_at = datetime.utcnow()

    async def _upsert_interview_prep(
        self,
        db: AsyncSession,
        user_id: str,
        job: Job,
        resume_doc_uid: Optional[str],
        match: JobMatch,
    ) -> None:
        details = match.match_details or {}
        missing = details.get("missing_skills", [])[:8]
        matched = details.get("matched_skills", [])[:8]
        title = job.title or "this role"
        existing = (await db.execute(select(InterviewPreparationPlan).where(
            InterviewPreparationPlan.user_id == user_id,
            InterviewPreparationPlan.job_id == job.id,
            InterviewPreparationPlan.resume_doc_uid == resume_doc_uid,
        ))).scalar_one_or_none()
        if not existing:
            existing = InterviewPreparationPlan(user_id=user_id, job_id=job.id, resume_doc_uid=resume_doc_uid)
            db.add(existing)
        existing.technical_questions = [
            f"Explain how you used {skill} in a project relevant to {title}." for skill in (matched or missing or ["the core role requirements"])[:5]
        ]
        existing.hr_questions = [
            f"Why are you interested in {title} at {job.company or 'this company'}?",
            "Describe a time you learned a missing skill quickly for a deadline.",
            "How would you communicate your current skill gaps honestly?",
        ]
        existing.system_design_questions = [
            f"Design a small production workflow that uses {', '.join((matched or missing)[:3]) or 'the role stack'}.",
            "How would you monitor and debug this system after deployment?",
        ]
        existing.coding_topics = matched[:5] + [skill for skill in missing[:5] if skill not in matched]
        existing.preparation_plan = {
            "focus_gaps": missing,
            "review_strengths": matched,
            "estimated_learning_time": details.get("estimated_learning_time", "unknown"),
            "recommended_sequence": ["review job description", "prepare project stories", "practice technical gaps", "mock HR round"],
        }
        existing.evidence = {"match_id": match.id, "source_job_id": job.source_job_id, "generated_from": "resume_job_match"}
        existing.updated_at = datetime.utcnow()

    async def _record_alert_decision(self, db: AsyncSession, user_id: str, job: Job, report: Dict[str, Any]) -> None:
        decision = report["recommended_priority"]
        channel = {"CALL": "voice", "WHATSAPP": "whatsapp", "EMAIL": "email", "DASHBOARD_ONLY": "dashboard", "IGNORE": "none"}.get(decision, "none")
        db.add(AlertDecisionAudit(
            user_id=user_id,
            job_id=job.id,
            decision=decision,
            channel=channel,
            reason=report["report"]["recommended_application_priority"],
            scores={
                "match": report["match_score"],
                "urgency": report["application_urgency"],
                "growth": report["career_growth_potential"],
                "competition": report["competition_risk"],
                "salary": report["salary_potential"],
            },
            evidence=report["evidence"],
        ))

    async def _remember(
        self,
        db: AsyncSession,
        user_id: str,
        event_type: str,
        job: Job,
        source_table: str,
        source_id: str,
        data: Dict[str, Any],
    ) -> bool:
        exists = (await db.execute(select(CareerMemory).where(
            CareerMemory.user_id == user_id,
            CareerMemory.event_type == event_type,
            CareerMemory.job_id == job.id,
            CareerMemory.source_table == source_table,
        ).limit(1))).scalar_one_or_none()
        if exists:
            return False
        db.add(CareerMemory(
            user_id=user_id,
            event_type=event_type,
            job_id=job.id,
            source_table=source_table,
            source_id=source_id,
            title=f"{event_type}: {job.title} at {job.company or 'Unknown'}",
            data=data,
        ))
        return True

    def _build_report(self, match: JobMatch, job: Job, salary: Dict[str, Any]) -> Dict[str, Any]:
        details = match.match_details or {}
        missing = details.get("missing_skills", []) or []
        matched = details.get("matched_skills", []) or []
        match_score = float(match.overall_score or 0)
        skill_gap_score = round(min(100.0, len(missing) * 18.0 + max(0, 100 - float(match.skill_match or 0)) * 0.4), 1)
        learning_effort = round(min(100.0, len(missing) * 16.0 + (0 if not missing else 20)), 1)
        freshness = float(details.get("freshness_score") or job.freshness_score or 50)
        deadline_status = str(details.get("deadline_status") or "unknown")
        urgency = self._urgency(freshness, deadline_status)
        competition = self._competition_risk(job, matched, missing)
        domain_alignment = float(details.get("domain_alignment_score") or details.get("dimensions", {}).get("semantic_similarity", 50))
        growth = self._growth_potential(job, matched, missing)
        salary_potential = self._salary_potential(salary)
        remote_compatibility = 100.0 if "remote" in f"{job.location} {job.description}".lower() else 55.0
        rank = round(
            match_score * 0.30
            + (100 - skill_gap_score) * 0.12
            + (100 - learning_effort) * 0.08
            + urgency * 0.12
            + (100 - competition) * 0.08
            + domain_alignment * 0.12
            + growth * 0.10
            + salary_potential * 0.05
            + remote_compatibility * 0.03,
            1,
        )
        priority = self._decision(match_score, urgency, rank, salary_potential, growth, competition)
        evidence = {
            "source_provider": job.source_provider or job.source,
            "source_job_id": job.source_job_id,
            "apply_url": job.apply_url,
            "matched_skills": matched,
            "missing_skills": missing,
            "salary_source": salary.get("source"),
            "freshness_bucket": job.freshness_bucket,
            "deadline_status": deadline_status,
        }
        report = {
            "why_this_job_matters": self._why_matters(job, matched, growth, salary),
            "why_ranked_here": f"Rank score {rank} combines match, gap effort, urgency, domain fit, salary and competition.",
            "skills_missing": missing,
            "estimated_preparation_effort": details.get("estimated_learning_time") or f"{int(max(1, learning_effort // 20))} weeks",
            "recommended_application_priority": self._priority_reason(priority, match_score, urgency, rank),
        }
        return {
            "match_score": match_score,
            "skill_gap_score": skill_gap_score,
            "learning_effort_score": learning_effort,
            "application_urgency": urgency,
            "competition_risk": competition,
            "domain_alignment": domain_alignment,
            "career_growth_potential": growth,
            "salary_potential": salary_potential,
            "remote_compatibility": remote_compatibility,
            "opportunity_rank_score": rank,
            "recommended_priority": priority,
            "report": report,
            "evidence": evidence,
        }

    def _urgency(self, freshness: float, deadline_status: str) -> float:
        if deadline_status in {"closing_soon", "urgent"}:
            return 95.0
        if freshness >= 100:
            return 85.0
        if freshness >= 85:
            return 75.0
        if freshness >= 70:
            return 55.0
        return 30.0

    def _competition_risk(self, job: Job, matched: List[str], missing: List[str]) -> float:
        text = f"{job.title} {job.description}".lower()
        risk = 55.0
        if "remote" in text:
            risk += 20
        if any(term in text for term in ["senior", "lead", "principal"]):
            risk += 10
        if matched:
            risk -= min(20, len(matched) * 5)
        risk += min(20, len(missing) * 6)
        return round(max(10, min(100, risk)), 1)

    def _growth_potential(self, job: Job, matched: List[str], missing: List[str]) -> float:
        text = f"{job.title} {job.description}".lower()
        growth = 55.0
        if any(term in text for term in ["ai", "machine learning", "data", "platform", "cloud", "product"]):
            growth += 20
        if any(term in text for term in ["training", "growth", "mentor", "learning"]):
            growth += 10
        growth += min(10, len(matched) * 2)
        growth -= min(15, len(missing) * 3)
        return round(max(10, min(100, growth)), 1)

    def _salary_potential(self, salary: Dict[str, Any]) -> float:
        confidence = float(salary.get("salary_confidence") or 0)
        yearly_max = float(salary.get("yearly_max") or 0)
        currency = salary.get("salary_currency", "USD")
        if currency == "INR":
            base = min(100, yearly_max / 2000000 * 100) if yearly_max else 45
        else:
            base = min(100, yearly_max / 150000 * 100) if yearly_max else 45
        return round(base * (0.5 + confidence / 2), 1)

    def _decision(self, match: float, urgency: float, rank: float, salary: float, growth: float, competition: float) -> str:
        if match >= 80 and urgency >= 80 and rank >= 85 and competition <= 75:
            return "CALL"
        if rank >= 82 and (salary >= 60 or growth >= 75):
            return "WHATSAPP"
        if rank >= 72 and match >= 60:
            return "EMAIL"
        if rank >= 45:
            return "DASHBOARD_ONLY"
        return "IGNORE"

    def _why_matters(self, job: Job, matched: List[str], growth: float, salary: Dict[str, Any]) -> str:
        skills = ", ".join(matched[:3]) if matched else "your current profile"
        salary_text = "salary is provider supplied" if salary.get("source") == "provider_supplied" else "salary is estimated"
        return f"{job.title} matters because it connects {skills} to a role with growth score {growth}. The {salary_text}."

    def _priority_reason(self, priority: str, match: float, urgency: float, rank: float) -> str:
        return f"{priority}: match={match:.1f}, urgency={urgency:.1f}, rank={rank:.1f}."

    def _aggregate_skills(self, evidence_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        matched: Dict[str, int] = {}
        missing: Dict[str, int] = {}
        for evidence in evidence_rows:
            for skill in evidence.get("matched_skills", []):
                matched[skill] = matched.get(skill, 0) + 1
            for skill in evidence.get("missing_skills", []):
                missing[skill] = missing.get(skill, 0) + 1
        return {
            "top_matched_skills": sorted(matched.items(), key=lambda item: item[1], reverse=True)[:10],
            "top_missing_skills": sorted(missing.items(), key=lambda item: item[1], reverse=True)[:10],
            "learning_priorities": [skill for skill, _ in sorted(missing.items(), key=lambda item: item[1], reverse=True)[:5]],
        }

    def _application_analytics(self, events: List[ApplicationTimelineEvent]) -> Dict[str, Any]:
        applied = len({e.job_id for e in events if e.status in {"APPLIED", "INTERVIEWING", "OFFER", "OFFERED", "REJECTED"}})
        interviews = len({e.job_id for e in events if e.status == "INTERVIEWING"})
        offers = len({e.job_id for e in events if e.status in {"OFFER", "OFFERED", "HIRED"}})
        return {
            "applications": applied,
            "interview_rate": round(interviews / max(applied, 1) * 100, 1),
            "offer_rate": round(offers / max(applied, 1) * 100, 1),
        }

    def _opportunity_trends(self, reports: List[Tuple[OpportunityIntelligenceReport, Job]]) -> Dict[str, Any]:
        providers: Dict[str, int] = {}
        freshness: Dict[str, int] = {}
        roles: Dict[str, int] = {}
        for _, job in reports:
            providers[job.source_provider or job.source] = providers.get(job.source_provider or job.source, 0) + 1
            freshness[job.freshness_bucket or "unknown"] = freshness.get(job.freshness_bucket or "unknown", 0) + 1
            role = (job.title or "Unknown").split(" - ")[0][:40]
            roles[role] = roles.get(role, 0) + 1
        return {
            "provider_performance": providers,
            "freshness_trends": freshness,
            "role_trends": sorted(roles.items(), key=lambda item: item[1], reverse=True)[:10],
        }

    def _report_summary(self, report: OpportunityIntelligenceReport, job: Job) -> Dict[str, Any]:
        return {
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "rank_score": report.opportunity_rank_score,
            "priority": report.recommended_priority,
            "match_score": report.match_score,
            "why": (report.report or {}).get("why_ranked_here"),
        }

    def _serialize_report(self, report: OpportunityIntelligenceReport) -> Dict[str, Any]:
        return {
            "match_score": report.match_score,
            "skill_gap_score": report.skill_gap_score,
            "learning_effort_score": report.learning_effort_score,
            "application_urgency": report.application_urgency,
            "competition_risk": report.competition_risk,
            "domain_alignment": report.domain_alignment,
            "career_growth_potential": report.career_growth_potential,
            "salary_potential": report.salary_potential,
            "remote_compatibility": report.remote_compatibility,
            "opportunity_rank_score": report.opportunity_rank_score,
            "recommended_priority": report.recommended_priority,
            "report": report.report or {},
            "evidence": report.evidence or {},
            "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        }

    def _serialize_salary(self, salary: SalaryIntelligence) -> Dict[str, Any]:
        return {
            "salary_min": salary.salary_min,
            "salary_max": salary.salary_max,
            "salary_currency": salary.salary_currency,
            "salary_period": salary.salary_period,
            "monthly_min": salary.monthly_min,
            "monthly_max": salary.monthly_max,
            "yearly_min": salary.yearly_min,
            "yearly_max": salary.yearly_max,
            "salary_confidence": salary.salary_confidence,
            "source": salary.source,
            "evidence": salary.evidence or {},
        }

    def _serialize_prep(self, prep: InterviewPreparationPlan) -> Dict[str, Any]:
        return {
            "technical_questions": prep.technical_questions or [],
            "hr_questions": prep.hr_questions or [],
            "system_design_questions": prep.system_design_questions or [],
            "coding_topics": prep.coding_topics or [],
            "preparation_plan": prep.preparation_plan or {},
            "evidence": prep.evidence or {},
        }


_phase2_service: Optional[Phase2OpportunityIntelligenceService] = None


def get_phase2_opportunity_intelligence_service() -> Phase2OpportunityIntelligenceService:
    global _phase2_service
    if _phase2_service is None:
        _phase2_service = Phase2OpportunityIntelligenceService()
    return _phase2_service
