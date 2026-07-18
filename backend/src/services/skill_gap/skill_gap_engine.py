"""Evidence-backed skill gap analysis engine."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.skill_gap import SkillGapAnalysisRun, SkillGapFinding, SkillGapFindingEvidence, UserSkillGapSnapshot
from src.models.skill_graph import SkillGraphNode
from src.services.events import get_career_event_service
from src.services.skill_gap.skill_gap_evidence_service import (
    SkillGapEvidenceRecord,
    SkillGapRequirement,
    get_skill_gap_evidence_service,
)
from src.services.skill_gap.skill_gap_explanation_service import get_skill_gap_explanation_service

_SOURCE_SERVICE = "services.skill_gap.skill_gap_engine"


def _now() -> datetime:
    current = datetime.utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(tzinfo=None)


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _finding_status_rank(status: str) -> int:
    return {
        "validated": 5,
        "evidenced": 4,
        "learning": 3,
        "missing": 2,
        "insufficient_data": 1,
    }.get(status, 0)


def _evidence_strength_rank(strength: str) -> int:
    return {
        "high": 4,
        "medium": 3,
        "low": 2,
        "weak": 1,
        "absence": 0,
    }.get(strength, 0)


class SkillGapEngineService:
    """Build and persist evidence-backed skill gap analyses."""

    def __init__(self) -> None:
        self.evidence_service = get_skill_gap_evidence_service()
        self.explanation_service = get_skill_gap_explanation_service()
        self.career_events = get_career_event_service()

    async def analyze(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        source_scope: str = "job",
        job_id: int | None = None,
        target_role_slug: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        if source_scope == "job" and job_id is None:
            return {
                "status": "error",
                "error": {"code": "JOB_ID_REQUIRED", "message": "job_id is required for job scope."},
            }

        run_uid = f"sgar_{uuid.uuid4().hex}"
        started_at = _now()
        run = SkillGapAnalysisRun(
            run_uid=run_uid,
            user_id=user_id,
            job_id=job_id,
            target_role_slug=target_role_slug,
            source_scope=source_scope,
            source_service=_SOURCE_SERVICE,
            status="running",
            required_skill_count=0,
            missing_skill_count=0,
            learning_skill_count=0,
            evidenced_skill_count=0,
            validated_skill_count=0,
            insufficient_data_count=0,
            confidence="low",
            metadata_={
                "analysis_version": "m5_evidence_backed_skill_gap_v1",
                "requested_limit": limit,
                "requested_source_scope": source_scope,
                "requested_job_id": job_id,
                "requested_target_role_slug": target_role_slug,
            },
            started_at=started_at,
        )
        db.add(run)
        await db.flush()

        requirements = await self.evidence_service.collect_required_skill_evidence(
            db,
            user_id=user_id,
            source_scope=source_scope,
            job_id=job_id,
            target_role_slug=target_role_slug,
        )

        if not requirements:
            run.status = "insufficient_data"
            run.failure_reason = "No evidence-backed skill requirements were found."
            run.completed_at = _now()
            run.required_skill_count = 0
            run.insufficient_data_count = 0
            snapshot = UserSkillGapSnapshot(
                snapshot_uid=f"sgsnap_{uuid.uuid4().hex}",
                user_id=user_id,
                target_role_slug=target_role_slug,
                job_id=job_id,
                run_uid=run_uid,
                summary_json={
                    "source_scope": source_scope,
                    "analysis_version": "m5_evidence_backed_skill_gap_v1",
                    "required_skill_count": 0,
                    "missing_skill_count": 0,
                    "learning_skill_count": 0,
                    "evidenced_skill_count": 0,
                    "validated_skill_count": 0,
                    "insufficient_data_count": 0,
                    "status": "insufficient_data",
                },
                missing_count=0,
                learning_count=0,
                evidenced_count=0,
                validated_count=0,
                insufficient_data_count=0,
                created_at=_now(),
            )
            db.add(snapshot)
            await db.commit()
            await self.career_events.emit_insufficient_data_event(
                db,
                event_type="SkillGapAnalysisCompleted",
                entity_type="skill_gap_analysis",
                source_service=_SOURCE_SERVICE,
                user_id=user_id,
                entity_id=run_uid,
                source_table="skill_gap_analysis_runs",
                source_id=run_uid,
                payload={
                    "run_uid": run_uid,
                    "source_scope": source_scope,
                    "job_id": job_id,
                    "target_role_slug": target_role_slug,
                    "status": "insufficient_data",
                    "reason": run.failure_reason,
                },
                evidence=[self.career_events.build_evidence_ref(table="skill_gap_analysis_runs", source_id=run_uid, note="No matching requirements found")],
            )
            return {
                "status": "ok",
                "run_uid": run_uid,
                "summary": {
                    "required_skill_count": 0,
                    "missing_skill_count": 0,
                    "learning_skill_count": 0,
                    "evidenced_skill_count": 0,
                    "validated_skill_count": 0,
                    "insufficient_data_count": 0,
                },
                "findings": [],
            }

        required_skills = requirements[:limit]
        evidence_maps = await self._collect_evidence_maps(db, user_id=user_id, required_skills=required_skills)

        findings_payload: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        evidence_count_total = 0
        for requirement in required_skills:
            relevant_evidence = self._merge_evidence(required_skills, requirement.skill_slug, evidence_maps)
            evidence_payloads = [self._evidence_payload(item, finding_uid=None) for item in relevant_evidence]
            status, confidence, missing_evidence = self._classify_finding(requirement, relevant_evidence)
            evidence_count = len([item for item in relevant_evidence if item.supports_status != "missing"])
            evidence_count_total += evidence_count
            status_counts[status] += 1

            reason_summary = self._build_reason_summary(requirement, status, evidence_payloads, missing_evidence)
            recommendation_summary = self.explanation_service.recommend_next_action(status, requirement.skill_name)

            node_result = await db.execute(select(SkillGraphNode).where(SkillGraphNode.skill_slug == requirement.skill_slug))
            node = node_result.scalar_one_or_none()

            finding_uid = f"sgfind_{uuid.uuid4().hex}"
            finding = SkillGapFinding(
                finding_uid=finding_uid,
                run_uid=run_uid,
                user_id=user_id,
                job_id=job_id,
                skill_node_uid=str(node.id) if node else None,
                skill_slug=requirement.skill_slug,
                skill_name=requirement.skill_name,
                required_by_type=requirement.required_by_type,
                required_by_id=requirement.required_by_id,
                gap_status=status,
                confidence=confidence,
                evidence_count=evidence_count,
                missing_evidence_json=missing_evidence,
                reason_summary=reason_summary,
                recommendation_summary=recommendation_summary,
                calculation_metadata_json={
                    "analysis_version": "m5_evidence_backed_skill_gap_v1",
                    "source_scope": source_scope,
                    "required_by_type": requirement.required_by_type,
                    "required_by_id": requirement.required_by_id,
                    "source_strength": requirement.source_strength,
                    "evidence_types": [item.evidence_type for item in relevant_evidence],
                },
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(finding)
            await db.flush()

            for evidence in relevant_evidence:
                evidence_row = SkillGapFindingEvidence(
                    evidence_uid=f"sgfe_{uuid.uuid4().hex}",
                    finding_uid=finding_uid,
                    user_id=user_id,
                    skill_slug=requirement.skill_slug,
                    evidence_type=evidence.evidence_type,
                    source_table=evidence.source_table,
                    source_id=evidence.source_id,
                    source_url=evidence.source_url,
                    evidence_strength=evidence.evidence_strength,
                    supports_status=evidence.supports_status,
                    quote_or_snippet=evidence.quote_or_snippet,
                    metadata_json={
                        **evidence.metadata_json,
                        "source_title": evidence.source_title,
                    },
                    confidence=evidence.confidence,
                    created_at=_now(),
                )
                db.add(evidence_row)

            findings_payload.append(
                {
                    "finding_uid": finding_uid,
                    "run_uid": run_uid,
                    "user_id": user_id,
                    "job_id": job_id,
                    "skill_node_uid": str(node.id) if node else None,
                    "skill_slug": requirement.skill_slug,
                    "skill_name": requirement.skill_name,
                    "required_by_type": requirement.required_by_type,
                    "required_by_id": requirement.required_by_id,
                    "gap_status": status,
                    "confidence": confidence,
                    "evidence_count": evidence_count,
                    "missing_evidence": missing_evidence,
                    "reason_summary": reason_summary,
                    "recommendation_summary": recommendation_summary,
                    "calculation_metadata_json": {
                        "analysis_version": "m5_evidence_backed_skill_gap_v1",
                        "source_scope": source_scope,
                        "required_by_type": requirement.required_by_type,
                        "required_by_id": requirement.required_by_id,
                        "source_strength": requirement.source_strength,
                        "evidence_types": [item.evidence_type for item in relevant_evidence],
                    },
                    "evidence": [self._evidence_payload(item, finding_uid) for item in relevant_evidence],
                    "created_at": _iso(_now()),
                    "updated_at": _iso(_now()),
                }
            )

        summary = {
            "required_skill_count": len(required_skills),
            "missing_skill_count": int(status_counts.get("missing", 0)),
            "learning_skill_count": int(status_counts.get("learning", 0)),
            "evidenced_skill_count": int(status_counts.get("evidenced", 0)),
            "validated_skill_count": int(status_counts.get("validated", 0)),
            "insufficient_data_count": int(status_counts.get("insufficient_data", 0)),
        }
        run.required_skill_count = summary["required_skill_count"]
        run.missing_skill_count = summary["missing_skill_count"]
        run.learning_skill_count = summary["learning_skill_count"]
        run.evidenced_skill_count = summary["evidenced_skill_count"]
        run.validated_skill_count = summary["validated_skill_count"]
        run.insufficient_data_count = summary["insufficient_data_count"]
        run.status = "completed"
        run.confidence = self._overall_confidence(status_counts, evidence_count_total)
        run.completed_at = _now()
        run.metadata_ = {
            **(run.metadata_ or {}),
            "findings_created": len(findings_payload),
            "evidence_count_total": evidence_count_total,
            "status_counts": dict(status_counts),
        }

        snapshot = UserSkillGapSnapshot(
            snapshot_uid=f"sgsnap_{uuid.uuid4().hex}",
            user_id=user_id,
            target_role_slug=target_role_slug,
            job_id=job_id,
            run_uid=run_uid,
            summary_json={
                "source_scope": source_scope,
                "analysis_version": "m5_evidence_backed_skill_gap_v1",
                **summary,
                "status_counts": dict(status_counts),
            },
            missing_count=summary["missing_skill_count"],
            learning_count=summary["learning_skill_count"],
            evidenced_count=summary["evidenced_skill_count"],
            validated_count=summary["validated_skill_count"],
            insufficient_data_count=summary["insufficient_data_count"],
            created_at=_now(),
        )
        db.add(snapshot)
        await db.commit()

        await self.career_events.emit_event(
            db,
            event_type="SkillGapAnalysisCompleted",
            entity_type="skill_gap_analysis",
            source_service=_SOURCE_SERVICE,
            user_id=user_id,
            entity_id=run_uid,
            source_table="skill_gap_analysis_runs",
            source_id=run_uid,
            payload={
                "run_uid": run_uid,
                "source_scope": source_scope,
                "job_id": job_id,
                "target_role_slug": target_role_slug,
                "summary": summary,
            },
            evidence=[self.career_events.build_evidence_ref(table="skill_gap_analysis_runs", source_id=run_uid, note="Evidence-backed skill gap analysis completed")],
            confidence=run.confidence,
            status="success",
        )

        return {
            "status": "ok",
            "run_uid": run_uid,
            "summary": summary,
            "findings": findings_payload,
        }

    async def _collect_evidence_maps(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        required_skills: list[SkillGapRequirement],
    ) -> dict[str, list[SkillGapEvidenceRecord]]:
        maps: dict[str, list[SkillGapEvidenceRecord]] = defaultdict(list)
        collected = [
            await self.evidence_service.collect_resume_evidence(db, user_id=user_id, required_skills=required_skills),
            await self.evidence_service.collect_project_evidence(db, user_id=user_id, required_skills=required_skills),
            await self.evidence_service.collect_learning_evidence(db, user_id=user_id, required_skills=required_skills),
            await self.evidence_service.collect_outcome_evidence(db, user_id=user_id, required_skills=required_skills),
            await self.evidence_service.collect_provenance_evidence(db, user_id=user_id, required_skills=required_skills),
            await self.evidence_service.collect_skill_graph_evidence(db, user_id=user_id, required_skills=required_skills),
        ]
        for mapping in collected:
            for skill_slug, records in mapping.items():
                maps[skill_slug].extend(records)
        return maps

    def _merge_evidence(
        self,
        required_skills: list[SkillGapRequirement],
        skill_slug: str,
        evidence_maps: dict[str, list[SkillGapEvidenceRecord]],
    ) -> list[SkillGapEvidenceRecord]:
        records = list(evidence_maps.get(skill_slug, []))
        if not records:
            requirement = next((item for item in required_skills if item.skill_slug == skill_slug), None)
            if requirement is not None:
                records.extend(
                    self._build_missing_evidence(requirement, searched_sources=[
                        "resume_versions",
                        "resume_chunks",
                        "learning_sessions",
                        "learning_activity_events",
                        "resource_feedback",
                        "resource_outcomes",
                        "learning_resource_provenance_records",
                        "user_skill_states",
                    ])
                )
        else:
            records.sort(key=lambda item: (_finding_status_rank(item.supports_status), _evidence_strength_rank(item.evidence_strength)), reverse=True)
        return records

    def _classify_finding(
        self,
        requirement: SkillGapRequirement,
        evidence: list[SkillGapEvidenceRecord],
    ) -> tuple[str, str, list[dict[str, Any]]]:
        missing_evidence = [self._evidence_payload(item, finding_uid=None) for item in evidence if item.supports_status == "missing"]
        if any(item.supports_status == "validated" for item in evidence):
            return "validated", "high", missing_evidence
        if any(item.supports_status == "evidenced" for item in evidence):
            return "evidenced", "medium" if requirement.source_strength == "medium" else "high", missing_evidence
        if any(item.supports_status == "learning" for item in evidence):
            return "learning", "medium", missing_evidence
        if any(item.supports_status == "missing" for item in evidence):
            return "missing", "low", missing_evidence
        return "insufficient_data", "low", missing_evidence

    def _build_reason_summary(
        self,
        requirement: SkillGapRequirement,
        status: str,
        evidence: list[dict[str, Any]],
        missing_evidence: list[dict[str, Any]],
    ) -> str:
        if status == "validated":
            return self.explanation_service.explain_validated(
                skill_name=requirement.skill_name,
                evidence=evidence,
            )
        if status == "evidenced":
            return self.explanation_service.explain_evidenced(
                skill_name=requirement.skill_name,
                evidence=evidence,
            )
        if status == "learning":
            return self.explanation_service.explain_learning(
                skill_name=requirement.skill_name,
                evidence=evidence,
            )
        if status == "missing":
            return self.explanation_service.explain_missing(
                skill_name=requirement.skill_name,
                required_by_type=requirement.required_by_type,
                evidence=evidence,
                missing_evidence=missing_evidence,
            )
        return self.explanation_service.explain_insufficient_data(
            skill_name=requirement.skill_name,
            required_by_type=requirement.required_by_type,
            evidence=evidence,
            metadata={
                "source_scope": requirement.required_by_type,
                "reason": requirement.source_title or requirement.skill_name,
            },
        )

    def _build_missing_evidence(
        self,
        requirement: SkillGapRequirement,
        *,
        searched_sources: list[str],
    ) -> list[SkillGapEvidenceRecord]:
        record = SkillGapEvidenceRecord(
            skill_slug=requirement.skill_slug,
            skill_name=requirement.skill_name,
            evidence_type="absence_check",
            source_table="search_summary",
            source_id=requirement.required_by_id,
            source_url=None,
            evidence_strength="absence",
            supports_status="missing",
            quote_or_snippet=f"Searched {', '.join(searched_sources)} and found no matching evidence",
            metadata_json={
                "required_by_type": requirement.required_by_type,
                "required_by_id": requirement.required_by_id,
                "searched_sources": searched_sources,
                "source_strength": requirement.source_strength,
            },
            confidence="low",
            source_title=requirement.source_title,
        )
        return [record]

    def _overall_confidence(self, status_counts: Counter[str], evidence_count_total: int) -> str:
        if status_counts.get("validated", 0) > 0:
            return "high"
        if status_counts.get("evidenced", 0) > 0 and evidence_count_total > 2:
            return "medium"
        if status_counts.get("learning", 0) > 0 or evidence_count_total > 0:
            return "medium"
        return "low"

    def _evidence_payload(self, evidence: SkillGapEvidenceRecord, finding_uid: str | None) -> dict[str, Any]:
        return {
            "evidence_uid": f"preview_{uuid.uuid4().hex}",
            "finding_uid": finding_uid or "",
            "user_id": "",
            "skill_slug": evidence.skill_slug,
            "evidence_type": evidence.evidence_type,
            "source_table": evidence.source_table,
            "source_id": evidence.source_id,
            "source_url": evidence.source_url,
            "evidence_strength": evidence.evidence_strength,
            "supports_status": evidence.supports_status,
            "quote_or_snippet": evidence.quote_or_snippet,
            "metadata_json": evidence.metadata_json,
            "confidence": evidence.confidence,
            "created_at": _iso(_now()),
        }


_SERVICE: SkillGapEngineService | None = None


def get_skill_gap_engine_service() -> SkillGapEngineService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = SkillGapEngineService()
    return _SERVICE
