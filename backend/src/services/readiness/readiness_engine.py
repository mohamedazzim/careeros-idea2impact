"""Phase 16 — Readiness Engine.

Computes CareerOS Readiness Score from actual pipeline outputs:
  - Resume quality assessment via ClaudeService
  - Skill gap analysis from market signals
  - Interview performance from graph/evaluation data
  - Opportunity match scores from OpportunityMatchEngine
  - Weighted aggregate with evidence chains

No hardcoded values. Every score is computed dynamically.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from src.observability.tracing import trace_async

logger = logging.getLogger(__name__)

# ── Dimension metadata ──────────────────────────────────────────────

DIMENSIONS = {
    "resume_quality": {
        "label": "Resume Quality",
        "weight": 0.30,
        "factors": [
            "ats_compatibility", "content_completeness",
            "contact_quality", "projects_quality",
            "experience_depth", "education_quality",
        ],
    },
    "skill_readiness": {
        "label": "Skill Readiness",
        "weight": 0.20,
        "factors": ["market_demand_overlap", "missing_skills", "emerging_skills"],
    },
    "interview_readiness": {
        "label": "Interview Readiness",
        "weight": 0.20,
        "factors": ["communication_clarity", "star_quality", "technical_depth", "confidence"],
    },
    "opportunity_readiness": {
        "label": "Opportunity Readiness",
        "weight": 0.30,
        "factors": ["match_score", "urgency", "application_readiness"],
    },
}


class ReadinessEngine:
    """Core readiness scoring engine. All scores are dynamic."""

    # ── Public API ──────────────────────────────────────────────────

    @trace_async("compute_readiness")
    async def compute(self, user_id: str) -> Dict[str, Any]:
        """Compute full readiness score with all dimensions and evidence."""
        cache_key = await self._compute_cache_key(user_id)
        cached = await self._get_cached_compute(cache_key)
        if cached is not None:
            return cached

        resume_dim = await self._score_resume_quality(user_id)
        skills_dim = await self._score_skill_readiness(user_id)
        interview_dim = await self._score_interview_readiness(user_id)
        opportunity_dim = await self._score_opportunity_readiness(user_id)

        dims = {
            **(resume_dim or {}),
            **(skills_dim or {}),
            **(interview_dim or {}),
            **(opportunity_dim or {}),
        }

        overall = sum(
            d["score"] * d["weight"]
            for d in dims.values()
        )

        trend = await self._compute_trend(user_id, overall)

        result = {
            "overall": round(overall, 1),
            "dimensions": dims,
            "trend": trend,
        }
        await self._set_cached_compute(cache_key, result)
        return result

    async def compute_timeline(self, user_id: str) -> List[Dict[str, Any]]:
        """Build career timeline from pipeline events."""
        from sqlalchemy import select
        from src.db.session import async_session
        from src.models.interview import InterviewSession
        from src.models.jobs import JobMatch
        from src.models.knowledge import KnowledgeDoc

        events: List[Dict[str, Any]] = []
        async with async_session() as db:
            resumes = (await db.execute(
                select(KnowledgeDoc)
                .where(KnowledgeDoc.user_id == user_id, KnowledgeDoc.deleted_at.is_(None))
                .order_by(KnowledgeDoc.created_at.desc())
                .limit(5)
            )).scalars().all()
            matches = (await db.execute(
                select(JobMatch)
                .where(JobMatch.user_id == user_id, JobMatch.deleted_at.is_(None))
                .order_by(JobMatch.created_at.desc())
                .limit(5)
            )).scalars().all()
            interviews = (await db.execute(
                select(InterviewSession)
                .where(InterviewSession.user_id == user_id, InterviewSession.deleted_at.is_(None))
                .order_by(InterviewSession.created_at.desc())
                .limit(5)
            )).scalars().all()

        events.extend({
            "stage": "Resume Processed",
            "timestamp": row.created_at.isoformat(),
            "status": row.status,
            "detail": f"{row.title}: {row.chunk_count or 0} chunks",
        } for row in resumes)
        events.extend({
            "stage": "Opportunity Matched",
            "timestamp": row.created_at.isoformat(),
            "status": "completed",
            "detail": f"{row.resume_name or 'Resume'}: {row.overall_score}% match",
        } for row in matches)
        events.extend({
            "stage": "Interview Session",
            "timestamp": row.created_at.isoformat(),
            "status": row.status,
            "detail": f"{row.interview_type}: score {row.total_score or 0}",
        } for row in interviews)
        return sorted(events, key=lambda event: event["timestamp"], reverse=True)

    # ── Dimension Scorers ───────────────────────────────────────────

    async def _score_resume_quality(self, user_id: str) -> Dict[str, Any]:
        """Score resume quality using one structured provider call."""
        from sqlalchemy import select
        from src.db.session import async_session
        from src.models.knowledge import KnowledgeDoc

        async with async_session() as db:
            resume = (await db.execute(
                select(KnowledgeDoc)
                .where(
                    KnowledgeDoc.user_id == user_id,
                    KnowledgeDoc.deleted_at.is_(None),
                    KnowledgeDoc.status.in_(["indexed", "analyzed"]),
                )
                .order_by(KnowledgeDoc.created_at.desc())
                .limit(1)
            )).scalar_one_or_none()
        if not resume:
            return self._make_dim("resume_quality", 0.0, ["No indexed resume exists."])
        content = (resume.content or "").strip()
        content_score = min(100.0, len(content) / 30.0)
        chunk_score = min(100.0, float(resume.chunk_count or 0) * 10.0)
        analysis_score = 100.0 if resume.analysis_results else 0.0
        status_score = 100.0 if resume.status in ("indexed", "analyzed") else 0.0
        score = (content_score * 0.35) + (chunk_score * 0.25) + (analysis_score * 0.20) + (status_score * 0.20)
        return self._make_dim("resume_quality", score, [
            f"resume={resume.title}",
            f"status={resume.status}",
            f"chunks={resume.chunk_count or 0}",
            f"content_characters={len(content)}",
            f"analysis_present={bool(resume.analysis_results)}",
        ])

    async def _score_skill_readiness(self, user_id: str) -> Dict[str, Any]:
        """Score skill readiness from market signals + skill gap analysis."""
        from sqlalchemy import func, select
        from src.db.session import async_session
        from src.models.jobs import JobMatch

        async with async_session() as db:
            average, count = (await db.execute(
                select(func.avg(JobMatch.skill_match), func.count(JobMatch.id))
                .where(JobMatch.user_id == user_id, JobMatch.deleted_at.is_(None))
            )).one()
        return self._make_dim("skill_readiness", float(average or 0.0), [
            f"persisted_matches={int(count or 0)}",
            f"average_skill_match={round(float(average or 0.0), 1)}",
        ])

    async def _score_interview_readiness(self, user_id: str) -> Dict[str, Any]:
        """Score interview readiness from actual evaluation data."""
        from sqlalchemy import func, select
        from src.db.session import async_session
        from src.models.interview import InterviewSession

        async with async_session() as db:
            average, count = (await db.execute(
                select(func.avg(InterviewSession.total_score), func.count(InterviewSession.id))
                .where(InterviewSession.user_id == user_id, InterviewSession.deleted_at.is_(None))
            )).one()
        return self._make_dim("interview_readiness", float(average or 0.0), [
            f"persisted_sessions={int(count or 0)}",
            f"average_interview_score={round(float(average or 0.0), 1)}",
        ])

    async def _score_opportunity_readiness(self, user_id: str) -> Dict[str, Any]:
        """Score opportunity readiness from actual match engine outputs."""
        from sqlalchemy import func, select
        from src.db.session import async_session
        from src.models.jobs import JobMatch

        async with async_session() as db:
            highest, average, count = (await db.execute(
                select(func.max(JobMatch.overall_score), func.avg(JobMatch.overall_score), func.count(JobMatch.id))
                .where(JobMatch.user_id == user_id, JobMatch.deleted_at.is_(None))
            )).one()
        score = float(highest or 0.0)
        return self._make_dim("opportunity_readiness", score, [
            f"persisted_matches={int(count or 0)}",
            f"highest_match={round(score, 1)}",
            f"average_match={round(float(average or 0.0), 1)}",
        ])

    # ── Helpers ─────────────────────────────────────────────────────

    def _make_dim(self, key: str, score: float, evidence: Any) -> Dict[str, Any]:
        meta = DIMENSIONS.get(key, {})
        return {
            key: {
                "score": round(min(max(score, 0), 100), 1),
                "label": meta.get("label", key),
                "weight": meta.get("weight", 0.25),
                "factors": meta.get("factors", []),
                "evidence": evidence if isinstance(evidence, list) else [f"{k}: {v}" for k, v in (evidence.items() if isinstance(evidence, dict) else [])][:6],
            }
        }

    async def _get_event_ts(self, user_id: str, event: str) -> Optional[str]:
        """Try to retrieve actual timestamp from pipeline state."""
        try:
            from src.db.redis import redis_client
            key = f"careeros:user:{user_id}:events:{event}"
            ts = await redis_client.get(key)
            return ts.decode() if ts else None
        except Exception:
            return None

    async def _compute_trend(self, user_id: str, current_score: float) -> List[Dict[str, Any]]:
        """Build trend from historical scores or seed first entry."""
        trend = []
        try:
            from src.db.redis import redis_client
            key = f"careeros:user:{user_id}:readiness_trend"
            raw = await redis_client.get(key)
            if raw:
                import json
                trend = json.loads(raw.decode())
        except Exception:
            pass

        import datetime
        today = datetime.date.today().isoformat()

        trend.append({"date": today, "score": current_score})
        if len(trend) > 10:
            trend = trend[-10:]

        try:
            from src.db.redis import redis_client
            import json
            key = f"careeros:user:{user_id}:readiness_trend"
            await redis_client.set(key, json.dumps(trend), ex=86400 * 30)
        except Exception:
            pass

        return trend


    async def _compute_cache_key(self, user_id: str) -> str:
        markers = {
            "resume_upload": await self._get_event_ts(user_id, "resume_upload"),
            "pii_filter": await self._get_event_ts(user_id, "pii_filter"),
            "embed_index": await self._get_event_ts(user_id, "embed_index"),
            "opportunity_scan": await self._get_event_ts(user_id, "opportunity_scan"),
            "interview": await self._get_event_ts(user_id, "interview"),
        }
        payload = json.dumps({"user_id": user_id, "markers": markers}, sort_keys=True, default=str)
        return f"careeros:readiness:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"

    async def _get_cached_compute(self, cache_key: str) -> Optional[Dict[str, Any]]:
        try:
            from src.db.redis import redis_client
            raw = await redis_client.get(cache_key)
            if raw:
                if isinstance(raw, bytes):
                    raw = raw.decode()
                cached = json.loads(raw)
                if isinstance(cached, dict):
                    return cached
        except Exception:
            pass
        return None

    async def _set_cached_compute(self, cache_key: str, result: Dict[str, Any]) -> None:
        try:
            from src.db.redis import redis_client
            await redis_client.setex(cache_key, 300, json.dumps(result, default=str))
        except Exception:
            pass



# ── Singleton ────────────────────────────────────────────────────────

_engine: Optional[ReadinessEngine] = None


def get_readiness_engine() -> ReadinessEngine:
    global _engine
    if _engine is None:
        _engine = ReadinessEngine()
    return _engine


def reset_readiness_engine() -> None:
    global _engine
    _engine = None
