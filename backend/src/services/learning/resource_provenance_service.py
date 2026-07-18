"""Resource provenance ledger for learning recommendations and proof artifacts."""

from __future__ import annotations

from datetime import datetime
import logging
import uuid
from typing import Any, Optional

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.events import get_career_event_service
from src.models.learning import LearningResource, ResourceDiscoveryRun, ResourceProvenanceRecord

logger = logging.getLogger(__name__)


class ResourceProvenanceService:
    """Persist and summarize provenance for learning resources and downstream outputs."""

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _confidence_for_score(score_total: float, status: str) -> str:
        if status != "success":
            return "low"
        if score_total >= 80:
            return "high"
        if score_total >= 60:
            return "medium"
        return "low"

    @staticmethod
    def _score_formula() -> str:
        return "trust*0.45 + relevance*0.35 + freshness*0.20"

    def build_score_breakdown(
        self,
        *,
        trust_score: float,
        relevance_score: float,
        freshness_score: float,
        verification_status: str | None = None,
        source_kind: str | None = None,
    ) -> dict[str, Any]:
        trust = float(trust_score or 0.0)
        relevance = float(relevance_score or 0.0)
        freshness = float(freshness_score or 0.0)
        weighted_total = round((trust * 0.45 + relevance * 0.35 + freshness * 0.20) * 100.0, 2)
        verification_bonus = 10.0 if verification_status in {"verified", "seeded_fallback"} else 0.0
        source_bonus = 5.0 if source_kind in {"seed", "live", "discovered"} else 0.0
        composite = round(min(100.0, weighted_total + verification_bonus + source_bonus), 2)
        return {
            "formula": self._score_formula(),
            "trust": round(trust, 4),
            "relevance": round(relevance, 4),
            "freshness": round(freshness, 4),
            "weighted_total": weighted_total,
            "verification_bonus": verification_bonus,
            "source_bonus": source_bonus,
            "composite_score": composite,
            "verification_status": verification_status,
            "source_kind": source_kind,
        }

    def build_explanation(
        self,
        *,
        title: str,
        provider: str,
        source_kind: str,
        verification_status: str | None,
        score_breakdown: dict[str, Any],
    ) -> str:
        base = (
            f"{title} is kept because it came from {provider} and scored "
            f"{score_breakdown.get('composite_score', 0):.1f}/100 across trust, relevance, and freshness."
        )
        if verification_status:
            base += f" Verification status: {verification_status}."
        if source_kind:
            base += f" Source kind: {source_kind}."
        return base

    @staticmethod
    def _summary_payload(record: ResourceProvenanceRecord) -> dict[str, Any]:
        evidence = record.evidence or []
        if not isinstance(evidence, list):
            evidence = [evidence]
        score_breakdown = record.score_breakdown or {}
        return {
            "provenance_uid": record.provenance_uid,
            "provenance_type": record.provenance_type,
            "source_entity_type": record.source_entity_type,
            "source_entity_id": record.source_entity_id,
            "source_table": record.source_table,
            "source_pk": record.source_pk,
            "recorded_at": record.recorded_at.isoformat() if record.recorded_at else None,
            "status": record.status,
            "confidence": record.confidence,
            "score_total": float(record.score_total or 0.0),
            "score_formula": record.score_formula,
            "score_breakdown": score_breakdown,
            "explanation": record.explanation,
            "evidence_count": len(evidence),
            "provider": record.provider,
            "skill_slug": record.skill_slug,
            "skill_name": record.skill_name,
            "title": record.title,
            "source_url": record.source_url,
            "resource_id": record.resource_id,
            "discovery_run_uid": record.discovery_run.run_uid if record.discovery_run else None,
        }

    @staticmethod
    def _can_execute(db: AsyncSession) -> bool:
        return callable(getattr(db, "execute", None))

    async def start_discovery_run(
        self,
        db: AsyncSession,
        *,
        provider: str,
        source_type: str,
        skill_slug: str | None = None,
        skill_name: str | None = None,
        user_id: str | None = None,
        request_payload: Optional[dict[str, Any]] = None,
        evidence: Optional[list[dict[str, Any]]] = None,
    ) -> ResourceDiscoveryRun:
        run = ResourceDiscoveryRun(
            run_uid=str(uuid.uuid4()),
            user_id=user_id,
            skill_slug=skill_slug,
            skill_name=skill_name,
            provider=provider,
            source_type=source_type,
            status="running",
            request_payload=request_payload or {},
            evidence=evidence or [],
            started_at=self._now(),
            created_at=self._now(),
            updated_at=self._now(),
        )
        db.add(run)
        await db.flush()
        await db.commit()
        await db.refresh(run)
        await get_career_event_service().emit_event(
            db,
            event_type="ResourceDiscoveryRunStarted",
            entity_type="resource_discovery_run",
            entity_id=run.run_uid,
            source_service="services.learning.resource_provenance_service",
            user_id=user_id,
            source_table="learning_resource_discovery_runs",
            source_id=run.id,
            payload={
                "provider": provider,
                "source_type": source_type,
                "skill_slug": skill_slug,
                "skill_name": skill_name,
                "status": run.status,
            },
            evidence=[
                get_career_event_service().build_evidence_ref(
                    table="learning_resource_discovery_runs",
                    source_id=run.id,
                    note="Discovery run started for learning resource provenance tracking",
                    extra={"provider": provider, "skill_slug": skill_slug, "skill_name": skill_name},
                )
            ],
            provider=provider,
            trace_id=run.run_uid,
        )
        return run

    async def complete_discovery_run(
        self,
        db: AsyncSession,
        *,
        run_uid: str,
        status: str,
        candidate_count: int,
        stored_count: int,
        response_payload: Optional[dict[str, Any]] = None,
        error_message: str | None = None,
    ) -> Optional[dict[str, Any]]:
        result = await db.execute(select(ResourceDiscoveryRun).where(ResourceDiscoveryRun.run_uid == run_uid))
        run = result.scalar_one_or_none()
        if run is None:
            return None
        run.status = status
        run.candidate_count = candidate_count
        run.stored_count = stored_count
        run.response_payload = response_payload or {}
        run.error_message = error_message
        run.completed_at = self._now()
        run.updated_at = self._now()
        await db.commit()
        await db.refresh(run)
        await get_career_event_service().emit_event(
            db,
            event_type="ResourceDiscoveryRunCompleted",
            entity_type="resource_discovery_run",
            entity_id=run.run_uid,
            source_service="services.learning.resource_provenance_service",
            user_id=run.user_id,
            source_table="learning_resource_discovery_runs",
            source_id=run.id,
            payload={
                "provider": run.provider,
                "source_type": run.source_type,
                "status": run.status,
                "candidate_count": run.candidate_count,
                "stored_count": run.stored_count,
                "error_message": run.error_message,
            },
            evidence=[
                get_career_event_service().build_evidence_ref(
                    table="learning_resource_discovery_runs",
                    source_id=run.id,
                    note="Discovery run completed for learning resource provenance tracking",
                    extra={
                        "provider": run.provider,
                        "candidate_count": run.candidate_count,
                        "stored_count": run.stored_count,
                        "status": run.status,
                    },
                )
            ],
            provider=run.provider,
            status="success" if status == "completed" else status,
            trace_id=run.run_uid,
        )
        return self.discovery_run_summary(run)

    def discovery_run_summary(self, run: ResourceDiscoveryRun) -> dict[str, Any]:
        return {
            "run_uid": run.run_uid,
            "status": run.status,
            "provider": run.provider,
            "source_type": run.source_type,
            "skill_slug": run.skill_slug,
            "skill_name": run.skill_name,
            "candidate_count": run.candidate_count,
            "stored_count": run.stored_count,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "error_message": run.error_message,
        }

    async def record_provenance(
        self,
        db: AsyncSession,
        *,
        provenance_type: str,
        source_entity_type: str,
        source_entity_id: str,
        skill_slug: str,
        skill_name: str,
        title: str,
        provider: str,
        source_url: str | None = None,
        resource_id: int | None = None,
        discovery_run_uid: str | None = None,
        user_id: str | None = None,
        job_id: int | None = None,
        source_table: str | None = None,
        source_pk: str | int | None = None,
        trust_score: float = 0.0,
        relevance_score: float = 0.0,
        freshness_score: float = 0.0,
        verification_status: str | None = None,
        source_kind: str | None = None,
        status: str = "success",
        evidence: Optional[list[dict[str, Any]]] = None,
        source_context: Optional[dict[str, Any]] = None,
    ) -> ResourceProvenanceRecord:
        if resource_id is not None:
            existing = await db.execute(
                select(ResourceProvenanceRecord).where(
                    ResourceProvenanceRecord.resource_id == resource_id,
                    ResourceProvenanceRecord.provenance_type == provenance_type,
                    ResourceProvenanceRecord.source_entity_type == source_entity_type,
                    ResourceProvenanceRecord.source_entity_id == source_entity_id,
                    ResourceProvenanceRecord.source_url == source_url,
                )
            )
            found = existing.scalar_one_or_none()
            if found is not None:
                return found

        score_breakdown = self.build_score_breakdown(
            trust_score=trust_score,
            relevance_score=relevance_score,
            freshness_score=freshness_score,
            verification_status=verification_status,
            source_kind=source_kind,
        )
        provenance = ResourceProvenanceRecord(
            provenance_uid=str(uuid.uuid4()),
            resource_id=resource_id,
            discovery_run_id=None,
            user_id=user_id,
            job_id=job_id,
            skill_slug=skill_slug,
            skill_name=skill_name,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            provenance_type=provenance_type,
            title=title,
            source_url=source_url,
            provider=provider,
            source_table=source_table,
            source_pk=str(source_pk) if source_pk is not None else None,
            trust_score=trust_score,
            relevance_score=relevance_score,
            freshness_score=freshness_score,
            score_total=score_breakdown["composite_score"],
            score_formula=score_breakdown["formula"],
            score_breakdown=score_breakdown,
            explanation=self.build_explanation(
                title=title,
                provider=provider,
                source_kind=source_kind or provenance_type,
                verification_status=verification_status,
                score_breakdown=score_breakdown,
            ),
            evidence=evidence or [],
            status=status,
            confidence=self._confidence_for_score(score_breakdown["composite_score"], status),
            recorded_at=self._now(),
            created_at=self._now(),
            updated_at=self._now(),
        )

        if discovery_run_uid:
            discovery_result = await db.execute(
                select(ResourceDiscoveryRun).where(ResourceDiscoveryRun.run_uid == discovery_run_uid)
            )
            discovery_run = discovery_result.scalar_one_or_none()
            if discovery_run is not None:
                provenance.discovery_run_id = discovery_run.id

        db.add(provenance)
        await db.commit()
        await db.refresh(provenance)
        await get_career_event_service().emit_event(
            db,
            event_type="ResourceProvenanceRecorded",
            entity_type=source_entity_type,
            entity_id=source_entity_id,
            source_service="services.learning.resource_provenance_service",
            user_id=user_id,
            source_table=source_table,
            source_id=source_pk,
            payload={
                "provenance_uid": provenance.provenance_uid,
                "provenance_type": provenance.provenance_type,
                "skill_slug": skill_slug,
                "skill_name": skill_name,
                "title": title,
                "provider": provider,
                "score_total": provenance.score_total,
                "status": status,
            },
            evidence=evidence
            or [
                get_career_event_service().build_evidence_ref(
                    table=source_table or source_entity_type,
                    source_id=source_pk or source_entity_id,
                    note=f"Provenance record stored for {provenance_type}",
                    extra=source_context or {},
                )
            ],
            confidence=provenance.confidence,
            provider=provider,
            status=status,
            trace_id=provenance.provenance_uid,
        )
        return provenance

    async def record_batch(
        self,
        db: AsyncSession,
        records: list[dict[str, Any]],
    ) -> list[ResourceProvenanceRecord]:
        stored: list[ResourceProvenanceRecord] = []
        for record in records:
            stored.append(await self.record_provenance(db, **record))
        return stored

    async def get_latest_resource_summary(
        self,
        db: AsyncSession,
        *,
        resource_id: int,
    ) -> Optional[dict[str, Any]]:
        if not self._can_execute(db):
            return None
        result = await db.execute(
            select(ResourceProvenanceRecord)
            .where(ResourceProvenanceRecord.resource_id == resource_id)
            .order_by(desc(ResourceProvenanceRecord.recorded_at), desc(ResourceProvenanceRecord.id))
            .limit(1)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return self._summary_payload(record)

    async def get_provenance_by_uid(
        self,
        db: AsyncSession,
        provenance_uid: str,
        *,
        user_id: str | None = None,
    ) -> Optional[dict[str, Any]]:
        if not self._can_execute(db):
            return None
        result = await db.execute(
            select(ResourceProvenanceRecord).where(ResourceProvenanceRecord.provenance_uid == provenance_uid)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        if user_id and record.user_id not in {None, user_id}:
            return None
        return self._summary_payload(record)

    async def get_discovery_run_by_uid(
        self,
        db: AsyncSession,
        run_uid: str,
        *,
        user_id: str | None = None,
    ) -> Optional[dict[str, Any]]:
        if not self._can_execute(db):
            return None
        result = await db.execute(select(ResourceDiscoveryRun).where(ResourceDiscoveryRun.run_uid == run_uid))
        run = result.scalar_one_or_none()
        if run is None:
            return None
        if user_id and run.user_id not in {None, user_id}:
            return None
        return self.discovery_run_summary(run)

    async def list_provenance(
        self,
        db: AsyncSession,
        *,
        user_id: str | None = None,
        resource_id: int | None = None,
        source_entity_type: str | None = None,
        source_entity_id: str | None = None,
        provenance_type: str | None = None,
        skill_slug: str | None = None,
        provider: str | None = None,
        source_type: str | None = None,
        resource_type: str | None = None,
        job_id: int | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if not self._can_execute(db):
            return [], 0
        conditions = []
        if user_id:
            conditions.append(or_(ResourceProvenanceRecord.user_id == user_id, ResourceProvenanceRecord.user_id.is_(None)))
        if resource_id is not None:
            conditions.append(ResourceProvenanceRecord.resource_id == resource_id)
        if source_entity_type:
            conditions.append(ResourceProvenanceRecord.source_entity_type == source_entity_type)
        if source_entity_id:
            conditions.append(ResourceProvenanceRecord.source_entity_id == source_entity_id)
        if provenance_type:
            conditions.append(ResourceProvenanceRecord.provenance_type == provenance_type)
        if skill_slug:
            conditions.append(ResourceProvenanceRecord.skill_slug == skill_slug)
        if provider:
            conditions.append(ResourceProvenanceRecord.provider == provider)
        if source_type:
            conditions.append(ResourceProvenanceRecord.provenance_type == source_type)
        if resource_type:
            conditions.append(ResourceProvenanceRecord.source_entity_type == resource_type)
        if job_id is not None:
            conditions.append(ResourceProvenanceRecord.job_id == job_id)
        if status:
            conditions.append(ResourceProvenanceRecord.status == status)

        data_query = select(ResourceProvenanceRecord)
        for condition in conditions:
            data_query = data_query.where(condition)

        count_result = await db.execute(select(func.count()).select_from(ResourceProvenanceRecord).where(*conditions))
        total = int(count_result.scalar() or 0)
        data_result = await db.execute(
            data_query.order_by(desc(ResourceProvenanceRecord.recorded_at), desc(ResourceProvenanceRecord.id)).offset(offset).limit(limit)
        )
        records = [self._summary_payload(record) for record in data_result.scalars().all()]
        return records, total

    async def list_discovery_runs(
        self,
        db: AsyncSession,
        *,
        user_id: str | None = None,
        skill_slug: str | None = None,
        provider: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if not self._can_execute(db):
            return [], 0
        conditions = []
        if user_id:
            conditions.append(or_(ResourceDiscoveryRun.user_id == user_id, ResourceDiscoveryRun.user_id.is_(None)))
        if skill_slug:
            conditions.append(ResourceDiscoveryRun.skill_slug == skill_slug)
        if provider:
            conditions.append(ResourceDiscoveryRun.provider == provider)
        if status:
            conditions.append(ResourceDiscoveryRun.status == status)

        data_query = select(ResourceDiscoveryRun)
        for condition in conditions:
            data_query = data_query.where(condition)

        count_result = await db.execute(select(func.count()).select_from(ResourceDiscoveryRun).where(*conditions))
        total = int(count_result.scalar() or 0)
        data_result = await db.execute(
            data_query.order_by(desc(ResourceDiscoveryRun.started_at), desc(ResourceDiscoveryRun.id)).offset(offset).limit(limit)
        )
        records = [self.discovery_run_summary(run) for run in data_result.scalars().all()]
        return records, total


_SERVICE: Optional[ResourceProvenanceService] = None


def get_resource_provenance_service() -> ResourceProvenanceService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ResourceProvenanceService()
    return _SERVICE
