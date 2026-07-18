"""RC3.1 Outcome Intelligence — Conversion funnel tracking.

Tracks: Notification → Open → Interested → Applied → Interview → Offer → Accepted
Persists conversion_metrics, outcome_metrics per provider/channel/role family.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import (
    ApplicationTimelineEvent,
    CommunicationRequest,
    OpportunityConversionMetric,
    OpportunityOutcomeEvent,
    OpportunityOutcomeMetric,
    VoiceSession,
)

CONVERSION_FUNNEL = [
    "NOTIFIED", "OPENED", "INTERESTED", "APPLIED",
    "INTERVIEW", "OFFER", "ACCEPTED",
]

CONVERSION_FUNNEL_REJECTED = [
    "NOT_INTERESTED", "REJECTED", "DECLINED", "EXPIRED",
]


class OutcomeIntelligenceService:
    async def record_event(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        job_id: int | None,
        communication_request_id: int | None,
        status: str,
        channel: str | None,
        data: Dict[str, Any] | None = None,
    ) -> OpportunityOutcomeEvent:
        event = OpportunityOutcomeEvent(
            user_id=user_id,
            job_id=job_id,
            communication_request_id=communication_request_id,
            status=status,
            channel=channel,
            data=data or {},
        )
        db.add(event)
        await db.flush()
        return event

    async def refresh_metrics(self, db: AsyncSession, *, user_id: str) -> None:
        total = int((await db.execute(
            select(func.count()).select_from(CommunicationRequest).where(CommunicationRequest.user_id == user_id)
        )).scalar() or 0)
        delivered = int((await db.execute(
            select(func.count()).select_from(CommunicationRequest).where(
                CommunicationRequest.user_id == user_id,
                CommunicationRequest.communication_status.in_(["sent", "delivered", "partial"]),
            )
        )).scalar() or 0)
        db.add(OpportunityOutcomeMetric(
            user_id=user_id,
            metric_name="notification_effectiveness",
            metric_value=round(delivered / total, 4) if total else 0.0,
            dimensions={"delivered_or_partial": delivered, "total": total},
        ))

        # Voice session metrics
        voice_total = int((await db.execute(
            select(func.count()).select_from(VoiceSession).where(VoiceSession.user_id == user_id)
        )).scalar() or 0)
        voice_completed = int((await db.execute(
            select(func.count()).select_from(VoiceSession).where(
                VoiceSession.user_id == user_id,
                VoiceSession.status.in_(["COMPLETED", "USER_INTERESTED", "sent"]),
            )
        )).scalar() or 0)
        db.add(OpportunityOutcomeMetric(
            user_id=user_id,
            metric_name="voice_session_completion",
            metric_value=round(voice_completed / voice_total, 4) if voice_total else 0.0,
            dimensions={"completed": voice_completed, "total": voice_total},
        ))

        # Conversion funnel metrics
        for channel in ("VOICE_CALL", "WHATSAPP", "EMAIL", "DASHBOARD_ONLY"):
            channel_total = int((await db.execute(
                select(func.count()).select_from(CommunicationRequest).where(
                    CommunicationRequest.user_id == user_id,
                    CommunicationRequest.channel == channel,
                )
            )).scalar() or 0)
            applied_count = int((await db.execute(
                select(func.count()).select_from(ApplicationTimelineEvent).where(
                    ApplicationTimelineEvent.user_id == user_id,
                    ApplicationTimelineEvent.status == "APPLIED",
                )
            )).scalar() or 0)
            interview_count = int((await db.execute(
                select(func.count()).select_from(ApplicationTimelineEvent).where(
                    ApplicationTimelineEvent.user_id == user_id,
                    ApplicationTimelineEvent.status == "INTERVIEW",
                )
            )).scalar() or 0)
            offer_count = int((await db.execute(
                select(func.count()).select_from(ApplicationTimelineEvent).where(
                    ApplicationTimelineEvent.user_id == user_id,
                    ApplicationTimelineEvent.status == "OFFER",
                )
            )).scalar() or 0)

            notified_count = channel_total
            conv_rate = 0.0
            if notified_count > 0:
                conv_rate = round(applied_count / notified_count, 4)

            db.add(OpportunityConversionMetric(
                user_id=user_id,
                channel=channel,
                notified_count=notified_count,
                applied_count=applied_count,
                interview_count=interview_count,
                offer_count=offer_count,
                conversion_rate=conv_rate,
            ))

    async def get_conversion_funnel(
        self, db: AsyncSession, *, user_id: str
    ) -> Dict[str, Any]:
        funnel = {}
        for stage in CONVERSION_FUNNEL:
            count = int((await db.execute(
                select(func.count()).select_from(OpportunityOutcomeEvent).where(
                    OpportunityOutcomeEvent.user_id == user_id,
                    OpportunityOutcomeEvent.status == stage,
                )
            )).scalar() or 0)
            funnel[stage] = count
        return {
            "funnel": funnel,
            "total_notified": funnel.get("NOTIFIED", 0),
            "total_applied": funnel.get("APPLIED", 0),
            "total_interviews": funnel.get("INTERVIEW", 0),
            "total_offers": funnel.get("OFFER", 0),
            "notification_to_apply_rate": (
                round(funnel["APPLIED"] / funnel["NOTIFIED"], 4) if funnel.get("NOTIFIED", 0) > 0 else 0.0
            ),
        }

    async def get_channel_performance(
        self, db: AsyncSession, *, user_id: str
    ) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(OpportunityConversionMetric)
            .where(OpportunityConversionMetric.user_id == user_id)
            .order_by(OpportunityConversionMetric.calculated_at.desc())
            .limit(20)
        )
        return [
            {
                "channel": m.channel,
                "notified_count": m.notified_count,
                "applied_count": m.applied_count,
                "interview_count": m.interview_count,
                "offer_count": m.offer_count,
                "conversion_rate": m.conversion_rate,
            }
            for m in result.scalars().all()
        ]

    async def get_outcome_events(
        self, db: AsyncSession, *, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(OpportunityOutcomeEvent)
            .where(OpportunityOutcomeEvent.user_id == user_id)
            .order_by(OpportunityOutcomeEvent.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "event_uid": e.event_uid,
                "job_id": e.job_id,
                "status": e.status,
                "channel": e.channel,
                "data": e.data,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in result.scalars().all()
        ]

    async def get_provider_performance(
        self, db: AsyncSession, *, user_id: str
    ) -> List[Dict[str, Any]]:
        from src.models.jobs import Job

        result = await db.execute(
            select(
                Job.source_provider,
                func.count(CommunicationRequest.id).label("notified_count"),
            )
            .join(CommunicationRequest, CommunicationRequest.job_id == Job.id)
            .where(CommunicationRequest.user_id == user_id)
            .group_by(Job.source_provider)
        )
        provider_counts = {row[0] or "unknown": row[1] for row in result.all()}

        applied_result = await db.execute(
            select(
                Job.source_provider,
                func.count(ApplicationTimelineEvent.id).label("applied_count"),
            )
            .join(ApplicationTimelineEvent, ApplicationTimelineEvent.job_id == Job.id)
            .where(ApplicationTimelineEvent.user_id == user_id, ApplicationTimelineEvent.status == "APPLIED")
            .group_by(Job.source_provider)
        )
        provider_applied = {row[0] or "unknown": row[1] for row in applied_result.all()}

        providers = []
        for provider, notified in provider_counts.items():
            applied = provider_applied.get(provider, 0)
            providers.append({
                "provider": provider,
                "notified_count": notified,
                "applied_count": applied,
                "conversion_rate": round(applied / notified, 4) if notified > 0 else 0.0,
            })
        return sorted(providers, key=lambda x: x["conversion_rate"], reverse=True)

    async def get_role_family_performance(
        self, db: AsyncSession, *, user_id: str
    ) -> List[Dict[str, Any]]:
        from src.models.jobs import Job
        from src.services.opportunity.career_memory import _extract_role_family

        result = await db.execute(
            select(
                Job.title,
                func.count(CommunicationRequest.id).label("notified_count"),
            )
            .join(CommunicationRequest, CommunicationRequest.job_id == Job.id)
            .where(CommunicationRequest.user_id == user_id)
            .group_by(Job.title)
        )
        role_counts: Dict[str, int] = {}
        for title, count in result.all():
            family = _extract_role_family(title or "")
            role_counts[family] = role_counts.get(family, 0) + count

        applied_result = await db.execute(
            select(
                Job.title,
                func.count(ApplicationTimelineEvent.id).label("applied_count"),
            )
            .join(ApplicationTimelineEvent, ApplicationTimelineEvent.job_id == Job.id)
            .where(ApplicationTimelineEvent.user_id == user_id, ApplicationTimelineEvent.status == "APPLIED")
            .group_by(Job.title)
        )
        role_applied: Dict[str, int] = {}
        for title, count in applied_result.all():
            family = _extract_role_family(title or "")
            role_applied[family] = role_applied.get(family, 0) + count

        roles = []
        for family, notified in role_counts.items():
            applied = role_applied.get(family, 0)
            roles.append({
                "role_family": family,
                "notified_count": notified,
                "applied_count": applied,
                "conversion_rate": round(applied / notified, 4) if notified > 0 else 0.0,
            })
        return sorted(roles, key=lambda x: x["conversion_rate"], reverse=True)


def get_outcome_intelligence_service() -> OutcomeIntelligenceService:
    return OutcomeIntelligenceService()
