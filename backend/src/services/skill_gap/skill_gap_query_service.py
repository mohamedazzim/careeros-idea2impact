"""Read helpers for persisted evidence-backed skill gap analyses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.skill_gap import SkillGapAnalysisRun, SkillGapFinding, SkillGapFindingEvidence, UserSkillGapSnapshot
from src.schemas.skill_gap import (
    SkillGapEvidenceResponse,
    SkillGapFindingListResponse,
    SkillGapFindingResponse,
    SkillGapJobResponse,
    SkillGapRunDetailResponse,
    SkillGapRunListResponse,
    SkillGapRunSummaryResponse,
    SkillGapSnapshotResponse,
    SkillGapSkillEvidenceResponse,
    SkillGapSummaryResponse,
    SkillGapUserResponse,
)


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class SkillGapQueryService:
    async def get_run(self, db: AsyncSession, *, user_id: str, run_uid: str) -> Optional[SkillGapRunDetailResponse]:
        run = await self._load_run(db, user_id=user_id, run_uid=run_uid)
        if run is None:
            return None
        findings = await self._load_findings(db, user_id=user_id, run_uid=run_uid)
        return SkillGapRunDetailResponse(
            status="ok",
            run=run,
            summary=self._summary_from_run(run),
            findings=findings,
        )

    async def get_latest_run(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        job_id: int | None = None,
        target_role_slug: str | None = None,
        source_scope: str | None = None,
    ) -> Optional[SkillGapRunDetailResponse]:
        query = select(SkillGapAnalysisRun).where(SkillGapAnalysisRun.user_id == user_id)
        if job_id is not None:
            query = query.where(SkillGapAnalysisRun.job_id == job_id)
        if target_role_slug:
            query = query.where(SkillGapAnalysisRun.target_role_slug == target_role_slug)
        if source_scope:
            query = query.where(SkillGapAnalysisRun.source_scope == source_scope)
        query = query.order_by(desc(SkillGapAnalysisRun.started_at), desc(SkillGapAnalysisRun.id)).limit(1)
        result = await db.execute(query)
        run = result.scalar_one_or_none()
        if run is None:
            return None
        findings = await self._load_findings(db, user_id=user_id, run_uid=run.run_uid)
        run_response = self._run_payload(run)
        return SkillGapRunDetailResponse(status="ok", run=run_response, summary=self._summary_from_run(run_response), findings=findings)

    async def list_runs(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> SkillGapRunListResponse:
        query = (
            select(SkillGapAnalysisRun)
            .where(SkillGapAnalysisRun.user_id == user_id)
            .order_by(desc(SkillGapAnalysisRun.started_at), desc(SkillGapAnalysisRun.id))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        rows = result.scalars().all()
        runs = [self._run_payload(row) for row in rows]
        total = await self._count_runs(db, user_id=user_id)
        return SkillGapRunListResponse(status="ok", total=total, runs=runs)

    async def get_job_response(self, db: AsyncSession, *, user_id: str, job_id: int) -> SkillGapJobResponse:
        latest_run = await self.get_latest_run(db, user_id=user_id, job_id=job_id, source_scope="job")
        if latest_run is None:
            return SkillGapJobResponse(status="ok", job_id=job_id, summary=SkillGapSummaryResponse(), findings=[])
        return SkillGapJobResponse(
            status="ok",
            job_id=job_id,
            latest_run=latest_run.run,
            summary=latest_run.summary,
            findings=latest_run.findings,
        )

    async def get_snapshot(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        source_scope: str | None = None,
        job_id: int | None = None,
        target_role_slug: str | None = None,
    ) -> SkillGapSnapshotResponse:
        query = select(UserSkillGapSnapshot).where(UserSkillGapSnapshot.user_id == user_id)
        if job_id is not None:
            query = query.where(UserSkillGapSnapshot.job_id == job_id)
        if target_role_slug:
            query = query.where(UserSkillGapSnapshot.target_role_slug == target_role_slug)
        query = query.order_by(desc(UserSkillGapSnapshot.created_at), desc(UserSkillGapSnapshot.id)).limit(1)
        result = await db.execute(query)
        row = result.scalar_one_or_none()
        if row is None:
            latest = await self.get_latest_run(db, user_id=user_id, job_id=job_id, source_scope=source_scope, target_role_slug=target_role_slug)
            if latest is None:
                return SkillGapSnapshotResponse(status="ok", snapshot_uid="", user_id=user_id, run_uid="", summary_json={})
            return SkillGapSnapshotResponse(
                status="ok",
                snapshot_uid="",
                user_id=user_id,
                target_role_slug=target_role_slug,
                job_id=job_id,
                run_uid=latest.run.run_uid,
                summary_json=latest.summary.model_dump(),
                missing_count=latest.summary.missing_skill_count,
                learning_count=latest.summary.learning_skill_count,
                evidenced_count=latest.summary.evidenced_skill_count,
                validated_count=latest.summary.validated_skill_count,
                insufficient_data_count=latest.summary.insufficient_data_count,
                created_at=latest.run.started_at,
                latest_run=latest.run,
                findings=latest.findings,
            )

        latest = await self.get_run(db, user_id=user_id, run_uid=row.run_uid)
        return SkillGapSnapshotResponse(
            status="ok",
            snapshot_uid=row.snapshot_uid,
            user_id=row.user_id,
            target_role_slug=row.target_role_slug,
            job_id=row.job_id,
            run_uid=row.run_uid,
            summary_json=row.summary_json or {},
            missing_count=row.missing_count,
            learning_count=row.learning_count,
            evidenced_count=row.evidenced_count,
            validated_count=row.validated_count,
            insufficient_data_count=row.insufficient_data_count,
            created_at=_iso(row.created_at),
            latest_run=latest.run if latest else None,
            findings=latest.findings if latest else [],
        )

    async def get_skill_evidence(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        skill_slug: str,
        run_uid: str | None = None,
    ) -> SkillGapSkillEvidenceResponse:
        finding_query = select(SkillGapFinding).where(SkillGapFinding.user_id == user_id, SkillGapFinding.skill_slug == skill_slug)
        if run_uid:
            finding_query = finding_query.where(SkillGapFinding.run_uid == run_uid)
        finding_query = finding_query.order_by(desc(SkillGapFinding.created_at), desc(SkillGapFinding.id)).limit(5)
        rows = (await db.execute(finding_query)).scalars().all()
        evidence: list[SkillGapEvidenceResponse] = []
        for finding in rows:
            evidence.extend(await self._load_evidence(db, finding_uid=finding.finding_uid))
        return SkillGapSkillEvidenceResponse(status="ok", skill_slug=skill_slug, evidence=evidence, total=len(evidence))

    async def list_findings(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> SkillGapFindingListResponse:
        query = (
            select(SkillGapFinding)
            .where(SkillGapFinding.user_id == user_id)
            .order_by(desc(SkillGapFinding.created_at), desc(SkillGapFinding.id))
            .limit(limit)
            .offset(offset)
        )
        rows = (await db.execute(query)).scalars().all()
        findings = []
        for row in rows:
            findings.append(await self._finding_payload(db, row))
        total = await self._count_findings(db, user_id=user_id)
        return SkillGapFindingListResponse(status="ok", total=total, findings=findings)

    async def _load_run(self, db: AsyncSession, *, user_id: str, run_uid: str) -> Optional[SkillGapRunSummaryResponse]:
        result = await db.execute(
            select(SkillGapAnalysisRun).where(
                SkillGapAnalysisRun.user_id == user_id,
                SkillGapAnalysisRun.run_uid == run_uid,
            )
        )
        run = result.scalar_one_or_none()
        if run is None:
            return None
        return self._run_payload(run)

    async def _load_findings(self, db: AsyncSession, *, user_id: str, run_uid: str) -> list[SkillGapFindingResponse]:
        result = await db.execute(
            select(SkillGapFinding).where(
                SkillGapFinding.user_id == user_id,
                SkillGapFinding.run_uid == run_uid,
            ).order_by(desc(SkillGapFinding.evidence_count), desc(SkillGapFinding.created_at), desc(SkillGapFinding.id))
        )
        rows = result.scalars().all()
        return [await self._finding_payload(db, row) for row in rows]

    async def _finding_payload(self, db: AsyncSession, row: SkillGapFinding) -> SkillGapFindingResponse:
        evidence = await self._load_evidence(db, finding_uid=row.finding_uid)
        return SkillGapFindingResponse(
            finding_uid=row.finding_uid,
            run_uid=row.run_uid,
            user_id=row.user_id,
            job_id=row.job_id,
            skill_node_uid=row.skill_node_uid,
            skill_slug=row.skill_slug,
            skill_name=row.skill_name,
            required_by_type=row.required_by_type,
            required_by_id=row.required_by_id,
            gap_status=row.gap_status,
            confidence=row.confidence,
            evidence_count=row.evidence_count,
            missing_evidence=list(row.missing_evidence_json or []),
            reason_summary=row.reason_summary,
            recommendation_summary=row.recommendation_summary,
            calculation_metadata_json=row.calculation_metadata_json or {},
            evidence=evidence,
            created_at=_iso(row.created_at),
            updated_at=_iso(row.updated_at),
        )

    async def _load_evidence(self, db: AsyncSession, *, finding_uid: str) -> list[SkillGapEvidenceResponse]:
        result = await db.execute(
            select(SkillGapFindingEvidence).where(SkillGapFindingEvidence.finding_uid == finding_uid).order_by(desc(SkillGapFindingEvidence.created_at), desc(SkillGapFindingEvidence.id))
        )
        rows = result.scalars().all()
        return [
            SkillGapEvidenceResponse(
                evidence_uid=row.evidence_uid,
                finding_uid=row.finding_uid,
                user_id=row.user_id,
                skill_slug=row.skill_slug,
                evidence_type=row.evidence_type,
                source_table=row.source_table,
                source_id=row.source_id,
                source_url=row.source_url,
                evidence_strength=row.evidence_strength,
                supports_status=row.supports_status,
                quote_or_snippet=row.quote_or_snippet,
                metadata_json=row.metadata_json or {},
                confidence=row.confidence,
                created_at=_iso(row.created_at),
            )
            for row in rows
        ]

    def _run_payload(self, row: SkillGapAnalysisRun) -> SkillGapRunSummaryResponse:
        duration_ms = None
        if row.started_at and row.completed_at:
            duration_ms = int(max(0.0, (row.completed_at - row.started_at).total_seconds() * 1000))
        return SkillGapRunSummaryResponse(
            run_uid=row.run_uid,
            user_id=row.user_id,
            job_id=row.job_id,
            target_role_slug=row.target_role_slug,
            source_scope=row.source_scope,
            source_service=row.source_service,
            status=row.status,
            started_at=_iso(row.started_at),
            completed_at=_iso(row.completed_at),
            duration_ms=duration_ms,
            required_skill_count=row.required_skill_count,
            missing_skill_count=row.missing_skill_count,
            evidenced_skill_count=row.evidenced_skill_count,
            learning_skill_count=row.learning_skill_count,
            validated_skill_count=row.validated_skill_count,
            insufficient_data_count=row.insufficient_data_count,
            confidence=row.confidence,
            failure_reason=row.failure_reason,
            metadata_json=row.metadata_ or {},
            created_at=_iso(row.created_at),
        )

    async def _count_runs(self, db: AsyncSession, *, user_id: str) -> int:
        result = await db.execute(select(func.count()).select_from(SkillGapAnalysisRun).where(SkillGapAnalysisRun.user_id == user_id))
        return int(result.scalar_one() or 0)

    async def _count_findings(self, db: AsyncSession, *, user_id: str) -> int:
        result = await db.execute(select(func.count()).select_from(SkillGapFinding).where(SkillGapFinding.user_id == user_id))
        return int(result.scalar_one() or 0)

    def _summary_from_run(self, run: SkillGapRunSummaryResponse) -> SkillGapSummaryResponse:
        return SkillGapSummaryResponse(
            required_skill_count=run.required_skill_count,
            missing_skill_count=run.missing_skill_count,
            learning_skill_count=run.learning_skill_count,
            evidenced_skill_count=run.evidenced_skill_count,
            validated_skill_count=run.validated_skill_count,
            insufficient_data_count=run.insufficient_data_count,
        )


_SERVICE: SkillGapQueryService | None = None


def get_skill_gap_query_service() -> SkillGapQueryService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = SkillGapQueryService()
    return _SERVICE
