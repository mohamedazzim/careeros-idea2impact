"""RC3 opportunity conversation context builder.

CareerOS remains the decision layer. This builder only packages existing
opportunity, application, notification, and career memory signals for delivery.
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import (
    ApplicationTimelineEvent,
    CareerMemory,
    OpportunityConversationContext,
    OpportunityNotification,
)
from src.models.orchestration import NotificationHistory
from src.models.evaluation_prefs import UserPreferences


class OpportunityConversationContextBuilder:
    async def build(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        opportunity: Dict[str, Any],
    ) -> OpportunityConversationContext:
        job_id = int(opportunity.get("job_id") or 0) or None

        career_rows = (await db.execute(
            select(CareerMemory)
            .where(CareerMemory.user_id == user_id)
            .order_by(desc(CareerMemory.created_at))
            .limit(8)
        )).scalars().all()
        timeline_rows = (await db.execute(
            select(ApplicationTimelineEvent)
            .where(ApplicationTimelineEvent.user_id == user_id)
            .order_by(desc(ApplicationTimelineEvent.created_at))
            .limit(8)
        )).scalars().all()
        notification_rows = (await db.execute(
            select(NotificationHistory)
            .where(NotificationHistory.user_id == user_id)
            .order_by(desc(NotificationHistory.created_at))
            .limit(8)
        )).scalars().all()
        application_rows = (await db.execute(
            select(OpportunityNotification)
            .where(OpportunityNotification.user_id == user_id)
            .order_by(desc(OpportunityNotification.updated_at))
            .limit(8)
        )).scalars().all()
        preference_row = (await db.execute(
            select(UserPreferences)
            .where(UserPreferences.user_id == user_id)
            .limit(1)
        )).scalar_one_or_none()
        preferred_language = (preference_row.language if preference_row and preference_row.language else "en").strip().lower()
        if preferred_language.startswith("ta"):
            preferred_language = "tamil"
        elif preferred_language in {"en-us", "en-gb"}:
            preferred_language = "english"
        elif preferred_language not in {"tamil", "english"}:
            preferred_language = "english"

        context = {
            "job": {
                "title": opportunity.get("title"),
                "company": opportunity.get("company"),
                "source": opportunity.get("source"),
                "source_job_id": opportunity.get("source_job_id"),
                "description": opportunity.get("description") or opportunity.get("job_description"),
                "location": opportunity.get("location"),
                "employment_type": opportunity.get("employment_type"),
                "experience_level": opportunity.get("experience_level"),
                "apply_url": opportunity.get("apply_url") or opportunity.get("source_url"),
            },
            "language_preferences": {
                "preferred_language": preferred_language,
                "response_language": preferred_language,
                "language_code": preference_row.language if preference_row else "en",
            },
            "match_intelligence": {
                "match_score": opportunity.get("overall_score"),
                "confidence": opportunity.get("confidence"),
                "matched_skills": opportunity.get("matched_skills") or opportunity.get("strengths") or [],
                "missing_skills": opportunity.get("missing_skills") or opportunity.get("gaps") or [],
            },
            "urgency_intelligence": {
                "urgency_score": opportunity.get("urgency_score"),
                "freshness_score": opportunity.get("freshness_score"),
                "deadline": opportunity.get("deadline"),
                "application_urgency": opportunity.get("application_urgency"),
            },
            "salary_intelligence": {
                "salary_range": opportunity.get("salary_range"),
                "salary_quality_score": opportunity.get("salary_quality_score"),
            },
            "company_intelligence": {
                "company_description": opportunity.get("company_description"),
                "industry": opportunity.get("industry"),
            },
            "application_intelligence": {
                "deadline": opportunity.get("deadline"),
                "application_url": opportunity.get("apply_url") or opportunity.get("source_url"),
                "urgency_score": opportunity.get("urgency_score"),
                "opportunity_priority_score": opportunity.get("opportunity_priority_score"),
            },
            "resume_intelligence": {
                "resume_strengths": opportunity.get("resume_strengths") or opportunity.get("strengths") or [],
                "resume_gaps": opportunity.get("resume_gaps") or opportunity.get("gaps") or [],
                "interview_focus_areas": opportunity.get("interview_focus_areas") or [],
            },
            "career_memory_summary": [
                {"event_type": row.event_type, "title": row.title, "created_at": row.created_at.isoformat()}
                for row in career_rows
            ],
            "application_memory_summary": [
                {"job_id": row.job_id, "status": row.status, "event_type": row.event_type, "created_at": row.created_at.isoformat()}
                for row in timeline_rows
            ],
            "notification_history_summary": [
                {"channel": row.channel, "status": row.status, "created_at": row.created_at.isoformat()}
                for row in notification_rows
            ],
            "application_state_summary": [
                {"job_id": row.job_id, "channel": row.channel, "status": row.status, "send_count": row.send_count}
                for row in application_rows
            ],
        }
        sources = {
            "career_memory": len(career_rows),
            "application_timeline": len(timeline_rows),
            "notification_history": len(notification_rows),
            "opportunity_notifications": len(application_rows),
        }
        confidence = 0.55 + min(0.4, sum(sources.values()) * 0.03)
        row = OpportunityConversationContext(
            user_id=user_id,
            job_id=job_id,
            conversation_context=context,
            context_sources=sources,
            context_confidence=round(confidence, 2),
        )
        db.add(row)
        await db.flush()
        return row


def get_opportunity_conversation_context_builder() -> OpportunityConversationContextBuilder:
    return OpportunityConversationContextBuilder()
