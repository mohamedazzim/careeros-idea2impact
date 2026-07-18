"""Learning outcome tracking for resource usage, progress, and feedback."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import desc, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.learning import (
    LearningActivityEvent,
    LearningResource,
    LearningSession,
    ResourceFeedback,
    ResourceOutcome,
    ResourceProvenanceRecord,
)
from src.services.events import get_career_event_service

logger = logging.getLogger(__name__)


class LearningOutcomeService:
    """Persist learning session activity and honest outcome aggregates."""

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _can_execute(db: AsyncSession) -> bool:
        return callable(getattr(db, "execute", None))

    @staticmethod
    def sanitize_feedback(payload: Any) -> Any:
        return get_career_event_service().sanitize_payload(payload)

    @staticmethod
    def build_outcome_explanation(
        *,
        resource_title: str,
        started_count: int,
        completion_count: int,
        feedback_count: int,
        average_rating: Optional[float],
        status: str,
    ) -> str:
        if status == "insufficient_data":
            return (
                f"Not enough learning activity has been recorded for {resource_title} yet. "
                f"Started sessions: {started_count}, feedback entries: {feedback_count}."
            )
        rating_text = (
            f"Average rating {average_rating:.1f}/5"
            if average_rating is not None
            else "No rating data yet"
        )
        return (
            f"{resource_title} has {started_count} started session(s), {completion_count} completion(s), "
            f"{feedback_count} feedback entry(ies), and {rating_text}."
        )

    def _session_payload(self, session: LearningSession) -> dict[str, Any]:
        return {
            "session_uid": session.session_uid,
            "user_id": session.user_id,
            "resource_id": session.resource_id,
            "provenance_uid": session.provenance_uid,
            "path_id": session.path_id,
            "path_item_id": session.path_item_id,
            "skill_slug": session.skill_slug,
            "job_id": session.job_id,
            "status": session.status,
            "source_ui": session.source_ui,
            "external_resource_url": session.external_resource_url,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "duration_seconds": session.duration_seconds,
            "completion_percentage": float(session.completion_percentage or 0.0),
            "metadata_json": session.metadata_ or {},
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }

    def _feedback_payload(self, feedback: ResourceFeedback) -> dict[str, Any]:
        return {
            "feedback_uid": feedback.feedback_uid,
            "user_id": feedback.user_id,
            "resource_id": feedback.resource_id,
            "provenance_uid": feedback.provenance_uid,
            "session_uid": feedback.session_uid,
            "skill_slug": feedback.skill_slug,
            "rating": float(feedback.rating) if feedback.rating is not None else None,
            "difficulty": feedback.difficulty,
            "would_recommend": feedback.would_recommend,
            "comment": feedback.comment,
            "helpfulness_score": float(feedback.helpfulness_score) if feedback.helpfulness_score is not None else None,
            "outcome_tag": feedback.outcome_tag,
            "metadata_json": feedback.metadata_ or {},
            "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
            "updated_at": feedback.updated_at.isoformat() if feedback.updated_at else None,
        }

    def _outcome_payload(self, outcome: ResourceOutcome, resource_title: str | None = None) -> dict[str, Any]:
        return {
            "resource_id": outcome.resource_id,
            "provenance_uid": outcome.provenance_uid,
            "skill_slug": outcome.skill_slug,
            "source_type": outcome.source_type,
            "provider": outcome.provider,
            "completion_count": int(outcome.completion_count or 0),
            "started_count": int(outcome.started_count or 0),
            "feedback_count": int(outcome.feedback_count or 0),
            "average_rating": float(outcome.average_rating) if outcome.average_rating is not None else None,
            "completion_rate": float(outcome.completion_rate) if outcome.completion_rate is not None else None,
            "drop_off_rate": float(outcome.drop_off_rate) if outcome.drop_off_rate is not None else None,
            "recommendation_rate": float(outcome.recommendation_rate) if outcome.recommendation_rate is not None else None,
            "average_completion_percentage": float(outcome.average_completion_percentage)
            if outcome.average_completion_percentage is not None
            else None,
            "average_duration_seconds": float(outcome.average_duration_seconds) if outcome.average_duration_seconds is not None else None,
            "last_calculated_at": outcome.last_calculated_at.isoformat() if outcome.last_calculated_at else None,
            "status": outcome.status,
            "calculation_metadata_json": outcome.calculation_metadata_json or {},
            "explanation": self.build_outcome_explanation(
                resource_title=resource_title or outcome.skill_slug,
                started_count=int(outcome.started_count or 0),
                completion_count=int(outcome.completion_count or 0),
                feedback_count=int(outcome.feedback_count or 0),
                average_rating=float(outcome.average_rating) if outcome.average_rating is not None else None,
                status=outcome.status,
            ),
            "created_at": outcome.created_at.isoformat() if outcome.created_at else None,
            "updated_at": outcome.updated_at.isoformat() if outcome.updated_at else None,
        }

    def _activity_payload(self, event: LearningActivityEvent) -> dict[str, Any]:
        return {
            "activity_uid": event.activity_uid,
            "user_id": event.user_id,
            "event_type": event.event_type,
            "resource_id": event.resource_id,
            "provenance_uid": event.provenance_uid,
            "session_uid": event.session_uid,
            "path_id": event.path_id,
            "path_item_id": event.path_item_id,
            "skill_slug": event.skill_slug,
            "job_id": event.job_id,
            "payload_json": event.payload_json or {},
            "event_time": event.event_time.isoformat() if event.event_time else None,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }

    async def _resource_by_id(self, db: AsyncSession, resource_id: int) -> Optional[LearningResource]:
        result = await db.execute(select(LearningResource).where(LearningResource.id == resource_id))
        return result.scalar_one_or_none()

    async def _resource_by_provenance_uid(self, db: AsyncSession, provenance_uid: str) -> tuple[Optional[LearningResource], Optional[ResourceProvenanceRecord]]:
        result = await db.execute(select(ResourceProvenanceRecord).where(ResourceProvenanceRecord.provenance_uid == provenance_uid))
        provenance = result.scalar_one_or_none()
        if provenance is None:
            return None, None
        if provenance.resource_id is None:
            return None, provenance
        return await self._resource_by_id(db, provenance.resource_id), provenance

    async def _resolve_resource_context(
        self,
        db: AsyncSession,
        *,
        resource_id: int | None = None,
        provenance_uid: str | None = None,
    ) -> tuple[Optional[LearningResource], Optional[ResourceProvenanceRecord]]:
        resource = None
        provenance = None
        if resource_id is not None:
            resource = await self._resource_by_id(db, resource_id)
        if provenance_uid:
            prov_resource, provenance = await self._resource_by_provenance_uid(db, provenance_uid)
            if resource is None:
                resource = prov_resource
        return resource, provenance

    async def _latest_provenance_uid(self, db: AsyncSession, *, resource_id: int) -> Optional[str]:
        result = await db.execute(
            select(ResourceProvenanceRecord.provenance_uid)
            .where(ResourceProvenanceRecord.resource_id == resource_id)
            .order_by(desc(ResourceProvenanceRecord.recorded_at), desc(ResourceProvenanceRecord.id))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _active_session(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        resource_id: int | None = None,
        provenance_uid: str | None = None,
        path_id: int | None = None,
        path_item_id: int | None = None,
    ) -> Optional[LearningSession]:
        query = select(LearningSession).where(LearningSession.user_id == user_id)
        if resource_id is not None:
            query = query.where(LearningSession.resource_id == resource_id)
        if provenance_uid:
            query = query.where(LearningSession.provenance_uid == provenance_uid)
        if path_id is not None:
            query = query.where(LearningSession.path_id == path_id)
        if path_item_id is not None:
            query = query.where(LearningSession.path_item_id == path_item_id)
        query = query.where(LearningSession.status.in_(["opened", "in_progress"]))
        query = query.order_by(desc(LearningSession.last_activity_at), desc(LearningSession.id)).limit(1)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def _session_by_uid(self, db: AsyncSession, *, session_uid: str, user_id: str | None = None) -> Optional[LearningSession]:
        query = select(LearningSession).where(LearningSession.session_uid == session_uid)
        if user_id is not None:
            query = query.where(LearningSession.user_id == user_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def _load_sessions(self, db: AsyncSession, *, resource_id: int) -> list[LearningSession]:
        result = await db.execute(
            select(LearningSession)
            .where(LearningSession.resource_id == resource_id)
            .order_by(desc(LearningSession.last_activity_at), desc(LearningSession.id))
        )
        return list(result.scalars().all())

    async def _load_feedback(self, db: AsyncSession, *, resource_id: int) -> list[ResourceFeedback]:
        result = await db.execute(
            select(ResourceFeedback)
            .where(ResourceFeedback.resource_id == resource_id)
            .order_by(desc(ResourceFeedback.created_at), desc(ResourceFeedback.id))
        )
        return list(result.scalars().all())

    async def _load_outcome(self, db: AsyncSession, *, resource_id: int) -> Optional[ResourceOutcome]:
        result = await db.execute(
            select(ResourceOutcome).where(ResourceOutcome.resource_id == resource_id)
        )
        return result.scalar_one_or_none()

    async def _load_outcome_by_provenance(
        self,
        db: AsyncSession,
        *,
        provenance_uid: str,
    ) -> Optional[ResourceOutcome]:
        result = await db.execute(select(ResourceOutcome).where(ResourceOutcome.provenance_uid == provenance_uid))
        return result.scalar_one_or_none()

    async def _resource_title(self, db: AsyncSession, *, resource_id: int) -> Optional[str]:
        result = await db.execute(select(LearningResource.title).where(LearningResource.id == resource_id))
        return result.scalar_one_or_none()

    async def _persist_outcome(self, db: AsyncSession, payload: dict[str, Any]) -> ResourceOutcome:
        stmt = insert(ResourceOutcome.__table__).values(
            resource_id=payload.get("resource_id"),
            provenance_uid=payload.get("provenance_uid"),
            skill_slug=payload["skill_slug"],
            source_type=payload["source_type"],
            provider=payload["provider"],
            completion_count=payload["completion_count"],
            started_count=payload["started_count"],
            feedback_count=payload["feedback_count"],
            average_rating=payload.get("average_rating"),
            completion_rate=payload.get("completion_rate"),
            drop_off_rate=payload.get("drop_off_rate"),
            recommendation_rate=payload.get("recommendation_rate"),
            average_completion_percentage=payload.get("average_completion_percentage"),
            average_duration_seconds=payload.get("average_duration_seconds"),
            last_calculated_at=payload.get("last_calculated_at"),
            status=payload["status"],
            calculation_metadata_json=payload.get("calculation_metadata_json") or {},
            created_at=self._now(),
            updated_at=self._now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["resource_id"],
            set_={
                "provenance_uid": stmt.excluded.provenance_uid,
                "skill_slug": stmt.excluded.skill_slug,
                "source_type": stmt.excluded.source_type,
                "provider": stmt.excluded.provider,
                "completion_count": stmt.excluded.completion_count,
                "started_count": stmt.excluded.started_count,
                "feedback_count": stmt.excluded.feedback_count,
                "average_rating": stmt.excluded.average_rating,
                "completion_rate": stmt.excluded.completion_rate,
                "drop_off_rate": stmt.excluded.drop_off_rate,
                "recommendation_rate": stmt.excluded.recommendation_rate,
                "average_completion_percentage": stmt.excluded.average_completion_percentage,
                "average_duration_seconds": stmt.excluded.average_duration_seconds,
                "last_calculated_at": stmt.excluded.last_calculated_at,
                "status": stmt.excluded.status,
                "calculation_metadata_json": stmt.excluded.calculation_metadata_json,
                "updated_at": self._now(),
            },
        ).returning(ResourceOutcome)
        result = await db.execute(stmt)
        await db.commit()
        refreshed = result.scalar_one()
        await db.refresh(refreshed)
        return refreshed

    async def _record_activity(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        event_type: str,
        resource_id: int | None,
        provenance_uid: str | None,
        session_uid: str | None,
        skill_slug: str,
        job_id: int | None = None,
        path_id: int | None = None,
        path_item_id: int | None = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> LearningActivityEvent:
        event = LearningActivityEvent(
            activity_uid=str(uuid.uuid4()),
            user_id=user_id,
            event_type=event_type,
            resource_id=resource_id,
            provenance_uid=provenance_uid,
            session_uid=session_uid,
            path_id=path_id,
            path_item_id=path_item_id,
            skill_slug=skill_slug,
            job_id=job_id,
            payload_json=self.sanitize_feedback(payload or {}),
            event_time=self._now(),
            created_at=self._now(),
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    async def _emit_career_event(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        user_id: str,
        resource_id: int | None,
        payload: dict[str, Any],
        evidence_note: str,
        provenance_uid: str | None = None,
        status: str = "success",
    ) -> None:
        try:
            await get_career_event_service().emit_event(
                db,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                source_service="services.learning.learning_outcome_service",
                user_id=user_id,
                source_table="learning_sessions" if resource_id is not None else None,
                source_id=resource_id,
                payload=payload,
                evidence=[
                    get_career_event_service().build_evidence_ref(
                        table="learning_sessions" if resource_id is not None else "resource_outcomes",
                        source_id=resource_id if resource_id is not None else entity_id,
                        note=evidence_note,
                        extra={"provenance_uid": provenance_uid},
                    )
                ],
                provider=payload.get("source_ui") or "learning",
                status=status,
                trace_id=entity_id,
            )
        except Exception as exc:  # pragma: no cover - audit rows must never block learning activity
            logger.debug("Learning outcome event emit skipped: %s", exc)

    async def _touch_session(
        self,
        db: AsyncSession,
        *,
        session: LearningSession,
        status: str,
        payload: Optional[dict[str, Any]] = None,
        completion_percentage: float | None = None,
        source_ui: str | None = None,
        external_resource_url: str | None = None,
    ) -> LearningSession:
        now = self._now()
        session.status = status
        session.last_activity_at = now
        if session.started_at is None:
            session.started_at = now
        if completion_percentage is not None:
            session.completion_percentage = max(0.0, min(100.0, float(completion_percentage)))
        if source_ui:
            session.source_ui = source_ui
        if external_resource_url:
            session.external_resource_url = external_resource_url
        if status in {"completed", "abandoned"}:
            session.ended_at = now
            if session.started_at:
                session.duration_seconds = max(0, int((now - session.started_at).total_seconds()))
        session.updated_at = now
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def open_resource(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        resource_id: int | None = None,
        provenance_uid: str | None = None,
        path_id: int | None = None,
        path_item_id: int | None = None,
        job_id: int | None = None,
        skill_slug: str | None = None,
        source_ui: str | None = None,
        external_resource_url: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        resource, provenance = await self._resolve_resource_context(db, resource_id=resource_id, provenance_uid=provenance_uid)
        if resource is None and provenance is None:
            return None
        resolved_resource_id = resource.id if resource is not None else resource_id
        resolved_skill_slug = skill_slug or (resource.skill_slug if resource else provenance.skill_slug if provenance else None)
        if resolved_skill_slug is None:
            return None
        existing = await self._active_session(
            db,
            user_id=user_id,
            resource_id=resolved_resource_id,
            provenance_uid=provenance_uid,
            path_id=path_id,
            path_item_id=path_item_id,
        )
        if existing is None:
            session = LearningSession(
                session_uid=str(uuid.uuid4()),
                user_id=user_id,
                resource_id=resolved_resource_id,
                provenance_uid=provenance_uid or (provenance.provenance_uid if provenance else None),
                path_id=path_id,
                path_item_id=path_item_id,
                skill_slug=resolved_skill_slug,
                job_id=job_id,
                status="opened",
                source_ui=source_ui,
                external_resource_url=external_resource_url or (resource.source_url if resource else None),
                started_at=self._now(),
                last_activity_at=self._now(),
                completion_percentage=0.0,
                metadata_=metadata or {},
                created_at=self._now(),
                updated_at=self._now(),
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
        else:
            session = await self._touch_session(
                db,
                session=existing,
                status=existing.status or "opened",
                source_ui=source_ui,
                external_resource_url=external_resource_url,
            )
            if metadata:
                session.metadata_ = {**(session.metadata_ or {}), **metadata}
                session.updated_at = self._now()
                db.add(session)
                await db.commit()
                await db.refresh(session)

        event = await self._record_activity(
            db,
            user_id=user_id,
            event_type="ResourceOpened",
            resource_id=session.resource_id,
            provenance_uid=session.provenance_uid,
            session_uid=session.session_uid,
            skill_slug=session.skill_slug,
            job_id=job_id,
            path_id=path_id,
            path_item_id=path_item_id,
            payload={
                "source_ui": source_ui,
                "external_resource_url": external_resource_url,
                "metadata": metadata or {},
                "status": session.status,
            },
        )
        await self._emit_career_event(
            db,
            event_type="ResourceOpened",
            entity_type="learning_session",
            entity_id=session.session_uid,
            user_id=user_id,
            resource_id=session.resource_id,
            payload=self._session_payload(session),
            evidence_note="Learning resource opened by the user",
            provenance_uid=session.provenance_uid,
        )
        outcome = await self.get_resource_outcome(db, resource_id=session.resource_id, provenance_uid=session.provenance_uid)
        return {
            "status": "ok",
            "session": self._session_payload(session),
            "outcome": outcome.get("outcome") if outcome else None,
            "event": self._activity_payload(event),
            "message": "Resource opened.",
            "insufficient_data": bool(outcome and outcome.get("status") == "insufficient_data"),
        }

    async def start_session(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        resource_id: int | None = None,
        provenance_uid: str | None = None,
        path_id: int | None = None,
        path_item_id: int | None = None,
        job_id: int | None = None,
        skill_slug: str | None = None,
        source_ui: str | None = None,
        external_resource_url: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        resource, provenance = await self._resolve_resource_context(db, resource_id=resource_id, provenance_uid=provenance_uid)
        if resource is None and provenance is None:
            return None
        resolved_resource_id = resource.id if resource is not None else resource_id
        resolved_skill_slug = skill_slug or (resource.skill_slug if resource else provenance.skill_slug if provenance else None)
        if resolved_skill_slug is None:
            return None
        existing = await self._active_session(
            db,
            user_id=user_id,
            resource_id=resolved_resource_id,
            provenance_uid=provenance_uid,
            path_id=path_id,
            path_item_id=path_item_id,
        )
        if existing is None:
            session = LearningSession(
                session_uid=str(uuid.uuid4()),
                user_id=user_id,
                resource_id=resolved_resource_id,
                provenance_uid=provenance_uid or (provenance.provenance_uid if provenance else None),
                path_id=path_id,
                path_item_id=path_item_id,
                skill_slug=resolved_skill_slug,
                job_id=job_id,
                status="in_progress",
                source_ui=source_ui,
                external_resource_url=external_resource_url or (resource.source_url if resource else None),
                started_at=self._now(),
                last_activity_at=self._now(),
                completion_percentage=0.0,
                metadata_=metadata or {},
                created_at=self._now(),
                updated_at=self._now(),
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
        else:
            session = await self._touch_session(
                db,
                session=existing,
                status="in_progress",
                source_ui=source_ui,
                external_resource_url=external_resource_url,
            )
            if metadata:
                session.metadata_ = {**(session.metadata_ or {}), **metadata}
                session.updated_at = self._now()
                db.add(session)
                await db.commit()
                await db.refresh(session)

        event = await self._record_activity(
            db,
            user_id=user_id,
            event_type="ResourceStarted",
            resource_id=session.resource_id,
            provenance_uid=session.provenance_uid,
            session_uid=session.session_uid,
            skill_slug=session.skill_slug,
            job_id=job_id,
            path_id=path_id,
            path_item_id=path_item_id,
            payload={
                "source_ui": source_ui,
                "external_resource_url": external_resource_url,
                "metadata": metadata or {},
                "status": session.status,
            },
        )
        await self._emit_career_event(
            db,
            event_type="ResourceStarted",
            entity_type="learning_session",
            entity_id=session.session_uid,
            user_id=user_id,
            resource_id=session.resource_id,
            payload=self._session_payload(session),
            evidence_note="Learning resource session started",
            provenance_uid=session.provenance_uid,
        )
        outcome = await self.get_resource_outcome(db, resource_id=session.resource_id, provenance_uid=session.provenance_uid)
        return {
            "status": "ok",
            "session": self._session_payload(session),
            "outcome": outcome.get("outcome") if outcome else None,
            "event": self._activity_payload(event),
            "message": "Session started.",
            "insufficient_data": bool(outcome and outcome.get("status") == "insufficient_data"),
        }

    async def update_progress(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        session_uid: str,
        completion_percentage: float,
        notes: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        session = await self._session_by_uid(db, session_uid=session_uid, user_id=user_id)
        if session is None:
            return None
        session = await self._touch_session(
            db,
            session=session,
            status="in_progress",
            completion_percentage=completion_percentage,
        )
        if metadata or notes:
            session.metadata_ = {**(session.metadata_ or {}), **(metadata or {})}
            if notes:
                session.metadata_["notes"] = notes
            session.updated_at = self._now()
            db.add(session)
            await db.commit()
            await db.refresh(session)
        event = await self._record_activity(
            db,
            user_id=user_id,
            event_type="ResourceProgressUpdated",
            resource_id=session.resource_id,
            provenance_uid=session.provenance_uid,
            session_uid=session.session_uid,
            skill_slug=session.skill_slug,
            job_id=session.job_id,
            path_id=session.path_id,
            path_item_id=session.path_item_id,
            payload={
                "completion_percentage": float(session.completion_percentage or 0.0),
                "notes": notes,
                "metadata": metadata or {},
            },
        )
        await self._emit_career_event(
            db,
            event_type="ResourceProgressUpdated",
            entity_type="learning_session",
            entity_id=session.session_uid,
            user_id=user_id,
            resource_id=session.resource_id,
            payload=self._session_payload(session),
            evidence_note="Learning resource progress updated",
            provenance_uid=session.provenance_uid,
        )
        outcome = await self.get_resource_outcome(db, resource_id=session.resource_id, provenance_uid=session.provenance_uid)
        return {
            "status": "ok",
            "session": self._session_payload(session),
            "outcome": outcome.get("outcome") if outcome else None,
            "event": self._activity_payload(event),
            "message": "Progress updated.",
            "insufficient_data": bool(outcome and outcome.get("status") == "insufficient_data"),
        }

    async def complete_resource(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        session_uid: str,
        notes: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        session = await self._session_by_uid(db, session_uid=session_uid, user_id=user_id)
        if session is None:
            return None
        session = await self._touch_session(db, session=session, status="completed")
        if metadata or notes:
            session.metadata_ = {**(session.metadata_ or {}), **(metadata or {})}
            if notes:
                session.metadata_["notes"] = notes
            session.updated_at = self._now()
            db.add(session)
            await db.commit()
            await db.refresh(session)
        event = await self._record_activity(
            db,
            user_id=user_id,
            event_type="ResourceCompleted",
            resource_id=session.resource_id,
            provenance_uid=session.provenance_uid,
            session_uid=session.session_uid,
            skill_slug=session.skill_slug,
            job_id=session.job_id,
            path_id=session.path_id,
            path_item_id=session.path_item_id,
            payload={
                "notes": notes,
                "metadata": metadata or {},
                "duration_seconds": session.duration_seconds,
                "completion_percentage": float(session.completion_percentage or 100.0),
            },
        )
        await self._emit_career_event(
            db,
            event_type="ResourceCompleted",
            entity_type="learning_session",
            entity_id=session.session_uid,
            user_id=user_id,
            resource_id=session.resource_id,
            payload=self._session_payload(session),
            evidence_note="Learning resource completed",
            provenance_uid=session.provenance_uid,
        )
        outcome = await self.calculate_resource_outcome(
            db,
            resource_id=session.resource_id,
            provenance_uid=session.provenance_uid,
        )
        return {
            "status": "ok",
            "session": self._session_payload(session),
            "outcome": outcome.get("outcome") if outcome else None,
            "event": self._activity_payload(event),
            "message": "Resource completed.",
            "insufficient_data": bool(outcome and outcome.get("status") == "insufficient_data"),
        }

    async def abandon_resource(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        session_uid: str,
        reason: str | None = None,
        notes: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        session = await self._session_by_uid(db, session_uid=session_uid, user_id=user_id)
        if session is None:
            return None
        session = await self._touch_session(db, session=session, status="abandoned")
        if metadata or notes or reason:
            session.metadata_ = {**(session.metadata_ or {}), **(metadata or {})}
            if notes:
                session.metadata_["notes"] = notes
            if reason:
                session.metadata_["reason"] = reason
            session.updated_at = self._now()
            db.add(session)
            await db.commit()
            await db.refresh(session)
        event = await self._record_activity(
            db,
            user_id=user_id,
            event_type="ResourceAbandoned",
            resource_id=session.resource_id,
            provenance_uid=session.provenance_uid,
            session_uid=session.session_uid,
            skill_slug=session.skill_slug,
            job_id=session.job_id,
            path_id=session.path_id,
            path_item_id=session.path_item_id,
            payload={
                "reason": reason,
                "notes": notes,
                "metadata": metadata or {},
            },
        )
        await self._emit_career_event(
            db,
            event_type="ResourceAbandoned",
            entity_type="learning_session",
            entity_id=session.session_uid,
            user_id=user_id,
            resource_id=session.resource_id,
            payload=self._session_payload(session),
            evidence_note="Learning resource abandoned",
            provenance_uid=session.provenance_uid,
            status="insufficient_data",
        )
        outcome = await self.calculate_resource_outcome(
            db,
            resource_id=session.resource_id,
            provenance_uid=session.provenance_uid,
        )
        return {
            "status": "ok",
            "session": self._session_payload(session),
            "outcome": outcome.get("outcome") if outcome else None,
            "event": self._activity_payload(event),
            "message": "Resource abandoned.",
            "insufficient_data": bool(outcome and outcome.get("status") == "insufficient_data"),
        }

    async def submit_feedback(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        resource_id: int | None = None,
        provenance_uid: str | None = None,
        session_uid: str | None = None,
        skill_slug: str | None = None,
        rating: float | None = None,
        difficulty: str | None = None,
        would_recommend: bool | None = None,
        comment: str | None = None,
        helpfulness_score: float | None = None,
        outcome_tag: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        resource, provenance = await self._resolve_resource_context(db, resource_id=resource_id, provenance_uid=provenance_uid)
        if resource is None and provenance is None:
            return None
        resolved_resource_id = resource.id if resource is not None else resource_id
        resolved_skill_slug = skill_slug or (resource.skill_slug if resource else provenance.skill_slug if provenance else None)
        if resolved_skill_slug is None:
            return None
        feedback = ResourceFeedback(
            feedback_uid=str(uuid.uuid4()),
            user_id=user_id,
            resource_id=resolved_resource_id,
            provenance_uid=provenance_uid or (provenance.provenance_uid if provenance else None),
            session_uid=session_uid,
            skill_slug=resolved_skill_slug,
            rating=rating,
            difficulty=difficulty,
            would_recommend=would_recommend,
            comment=comment,
            helpfulness_score=helpfulness_score,
            outcome_tag=outcome_tag,
            metadata_=metadata or {},
            created_at=self._now(),
            updated_at=self._now(),
        )
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)
        event = await self._record_activity(
            db,
            user_id=user_id,
            event_type="ResourceFeedbackSubmitted",
            resource_id=feedback.resource_id,
            provenance_uid=feedback.provenance_uid,
            session_uid=feedback.session_uid,
            skill_slug=feedback.skill_slug,
            payload=self._feedback_payload(feedback),
        )
        await self._emit_career_event(
            db,
            event_type="ResourceFeedbackSubmitted",
            entity_type="resource_feedback",
            entity_id=feedback.feedback_uid,
            user_id=user_id,
            resource_id=feedback.resource_id,
            payload=self._feedback_payload(feedback),
            evidence_note="User submitted feedback for a learning resource",
            provenance_uid=feedback.provenance_uid,
        )
        outcome = await self.calculate_resource_outcome(
            db,
            resource_id=feedback.resource_id,
            provenance_uid=feedback.provenance_uid,
        )
        return {
            "status": "ok",
            "feedback": self._feedback_payload(feedback),
            "outcome": outcome.get("outcome") if outcome else None,
            "event": self._activity_payload(event),
            "message": "Feedback recorded.",
            "insufficient_data": bool(outcome and outcome.get("status") == "insufficient_data"),
        }

    async def calculate_resource_outcome(
        self,
        db: AsyncSession,
        *,
        resource_id: int | None = None,
        provenance_uid: str | None = None,
    ) -> Optional[dict[str, Any]]:
        resource, provenance = await self._resolve_resource_context(db, resource_id=resource_id, provenance_uid=provenance_uid)
        if resource is None and provenance is None:
            return None
        if resource is None and provenance and provenance.resource_id is not None:
            resource = await self._resource_by_id(db, provenance.resource_id)
        if resource is None:
            return None

        sessions = await self._load_sessions(db, resource_id=resource.id)
        feedback_entries = await self._load_feedback(db, resource_id=resource.id)

        started_count = sum(1 for session in sessions if session.status in {"opened", "in_progress", "completed", "abandoned"})
        completion_count = sum(1 for session in sessions if session.status == "completed")
        abandoned_count = sum(1 for session in sessions if session.status == "abandoned")
        feedback_count = len(feedback_entries)
        recommend_count = sum(1 for feedback in feedback_entries if feedback.would_recommend)
        completed_sessions = [session for session in sessions if session.status == "completed"]

        average_rating = (
            sum(float(feedback.rating or 0.0) for feedback in feedback_entries) / feedback_count
            if feedback_count
            else None
        )
        average_completion_percentage = (
            sum(float(session.completion_percentage or 0.0) for session in sessions) / len(sessions)
            if sessions
            else None
        )
        average_duration_seconds = (
            sum(float(session.duration_seconds or 0.0) for session in completed_sessions) / len(completed_sessions)
            if completed_sessions
            else None
        )

        completion_rate = completion_count / started_count if started_count else None
        drop_off_rate = abandoned_count / started_count if started_count else None
        recommendation_rate = recommend_count / feedback_count if feedback_count else None
        status = "insufficient_data" if started_count == 0 and feedback_count == 0 else "sufficient_data"
        provenance_uid_value = provenance_uid or (provenance.provenance_uid if provenance else None) or await self._latest_provenance_uid(db, resource_id=resource.id)

        payload = {
            "resource_id": resource.id,
            "provenance_uid": provenance_uid_value,
            "skill_slug": resource.skill_slug,
            "source_type": resource.source_type,
            "provider": resource.provider,
            "completion_count": completion_count,
            "started_count": started_count,
            "feedback_count": feedback_count,
            "average_rating": average_rating,
            "completion_rate": completion_rate,
            "drop_off_rate": drop_off_rate,
            "recommendation_rate": recommendation_rate,
            "average_completion_percentage": average_completion_percentage,
            "average_duration_seconds": average_duration_seconds,
            "last_calculated_at": self._now(),
            "status": status,
            "calculation_metadata_json": {
                "session_count": len(sessions),
                "completed_session_count": len(completed_sessions),
                "abandoned_session_count": abandoned_count,
                "recommend_count": recommend_count,
                "resource_title": resource.title,
            },
        }
        outcome = await self._persist_outcome(db, payload)
        event_type = "ResourceOutcomeCalculated" if status == "sufficient_data" else "ResourceOutcomeInsufficientData"
        await self._record_activity(
            db,
            user_id="system",
            event_type=event_type,
            resource_id=resource.id,
            provenance_uid=payload["provenance_uid"],
            session_uid=None,
            skill_slug=resource.skill_slug,
            payload=payload,
        )
        try:
            await get_career_event_service().emit_event(
                db,
                event_type=event_type,
                entity_type="resource_outcome",
                entity_id=str(resource.id),
                source_service="services.learning.learning_outcome_service",
                user_id=None,
                source_table="resource_outcomes",
                source_id=outcome.id,
                payload=self._outcome_payload(outcome, resource_title=resource.title),
                evidence=[
                    get_career_event_service().build_evidence_ref(
                        table="resource_outcomes",
                        source_id=outcome.id,
                        note="Learning resource outcome aggregate calculated from stored sessions and feedback",
                        extra={"resource_id": resource.id, "skill_slug": resource.skill_slug},
                    )
                ],
                provider=resource.provider,
                confidence="low" if status == "insufficient_data" else "medium",
                status="insufficient_data" if status == "insufficient_data" else "success",
                trace_id=payload["provenance_uid"] or f"resource_outcome:{resource.id}",
            )
        except Exception as exc:  # pragma: no cover - audit rows must never block learning outcome updates
            logger.debug("Learning outcome audit emit skipped: %s", exc)
        return {
            "status": "ok",
            "outcome": self._outcome_payload(outcome, resource_title=resource.title),
            "insufficient_data": status == "insufficient_data",
            "message": "Learning outcome calculated.",
        }

    async def recalculate_outcomes_for_resource(
        self,
        db: AsyncSession,
        *,
        resource_id: int,
        provenance_uid: str | None = None,
    ) -> Optional[dict[str, Any]]:
        return await self.calculate_resource_outcome(db, resource_id=resource_id, provenance_uid=provenance_uid)

    async def get_resource_outcome(
        self,
        db: AsyncSession,
        *,
        resource_id: int | None = None,
        provenance_uid: str | None = None,
    ) -> Optional[dict[str, Any]]:
        resource, provenance = await self._resolve_resource_context(db, resource_id=resource_id, provenance_uid=provenance_uid)
        if resource is None and provenance is None:
            return None
        if resource is None and provenance and provenance.resource_id is not None:
            resource = await self._resource_by_id(db, provenance.resource_id)
        if resource is None:
            return None

        outcome = await self._load_outcome(db, resource_id=resource.id)
        if outcome is None:
            calculated = await self.calculate_resource_outcome(db, resource_id=resource.id, provenance_uid=provenance_uid or (provenance.provenance_uid if provenance else None))
            if calculated is None:
                return None
            return calculated
        return {
            "status": "ok",
            "outcome": self._outcome_payload(outcome, resource_title=resource.title),
            "insufficient_data": outcome.status == "insufficient_data",
            "message": "Learning outcome loaded.",
        }

    async def get_latest_resource_outcome_summary(
        self,
        db: AsyncSession,
        *,
        resource_id: int,
    ) -> Optional[dict[str, Any]]:
        if not self._can_execute(db):
            return None
        outcome = await self._load_outcome(db, resource_id=resource_id)
        resource_title = await self._resource_title(db, resource_id=resource_id)
        if outcome is not None:
            return self._outcome_payload(outcome, resource_title=resource_title)

        loaded = await self.get_resource_outcome(db, resource_id=resource_id)
        if not loaded:
            return None
        loaded_outcome = loaded.get("outcome")
        if isinstance(loaded_outcome, dict):
            if resource_title and not loaded_outcome.get("explanation"):
                loaded_outcome = {
                    **loaded_outcome,
                    "explanation": self.build_outcome_explanation(
                        resource_title=resource_title,
                        started_count=int(loaded_outcome.get("started_count") or 0),
                        completion_count=int(loaded_outcome.get("completion_count") or 0),
                        feedback_count=int(loaded_outcome.get("feedback_count") or 0),
                        average_rating=loaded_outcome.get("average_rating"),
                        status=str(loaded_outcome.get("status") or "insufficient_data"),
                    ),
                }
            return loaded_outcome
        return None

    async def list_resource_outcomes(
        self,
        db: AsyncSession,
        *,
        skill_slug: str | None = None,
        provider: str | None = None,
        status: str | None = None,
        resource_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if not self._can_execute(db):
            return [], 0
        conditions = []
        if skill_slug:
            conditions.append(ResourceOutcome.skill_slug == skill_slug)
        if provider:
            conditions.append(ResourceOutcome.provider == provider)
        if status:
            conditions.append(ResourceOutcome.status == status)
        if resource_id is not None:
            conditions.append(ResourceOutcome.resource_id == resource_id)
        count_result = await db.execute(select(func.count()).select_from(ResourceOutcome).where(*conditions))
        total = int(count_result.scalar() or 0)
        query = select(ResourceOutcome)
        for condition in conditions:
            query = query.where(condition)
        query = query.order_by(desc(ResourceOutcome.last_calculated_at), desc(ResourceOutcome.id)).offset(offset).limit(limit)
        result = await db.execute(query)
        outcome_rows = list(result.scalars().all())
        if not outcome_rows:
            return [], total
        resource_ids = {row.resource_id for row in outcome_rows if row.resource_id is not None}
        if not resource_ids:
            return [self._outcome_payload(row) for row in outcome_rows], total
        resources_result = await db.execute(select(LearningResource).where(LearningResource.id.in_(resource_ids)))
        resources = {resource.id: resource for resource in resources_result.scalars().all()}
        rows = [
            self._outcome_payload(
                row,
                resource_title=resources.get(row.resource_id).title if row.resource_id in resources else None,
            )
            for row in outcome_rows
        ]
        return rows, total

    async def list_user_learning_activity(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        event_type: str | None = None,
        resource_id: int | None = None,
        provenance_uid: str | None = None,
        session_uid: str | None = None,
        skill_slug: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if not self._can_execute(db):
            return [], 0
        conditions = [LearningActivityEvent.user_id == user_id]
        if event_type:
            conditions.append(LearningActivityEvent.event_type == event_type)
        if resource_id is not None:
            conditions.append(LearningActivityEvent.resource_id == resource_id)
        if provenance_uid:
            conditions.append(LearningActivityEvent.provenance_uid == provenance_uid)
        if session_uid:
            conditions.append(LearningActivityEvent.session_uid == session_uid)
        if skill_slug:
            conditions.append(LearningActivityEvent.skill_slug == skill_slug)
        count_result = await db.execute(select(func.count()).select_from(LearningActivityEvent).where(*conditions))
        total = int(count_result.scalar() or 0)
        result = await db.execute(
            select(LearningActivityEvent)
            .where(*conditions)
            .order_by(desc(LearningActivityEvent.event_time), desc(LearningActivityEvent.id))
            .offset(offset)
            .limit(limit)
        )
        return [self._activity_payload(event) for event in result.scalars().all()], total


_SERVICE: Optional[LearningOutcomeService] = None


def get_learning_outcome_service() -> LearningOutcomeService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = LearningOutcomeService()
    return _SERVICE
