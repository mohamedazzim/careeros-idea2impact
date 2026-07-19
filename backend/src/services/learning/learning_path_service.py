"""Learning path generation from real skill-gap signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from urllib.parse import urlparse
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import Job, JobMatch
from src.models.learning import LearningPathItem, LearningResource, UserSkillLearningPath
from src.services.events import get_career_event_service
from src.services.learning.learning_outcome_service import get_learning_outcome_service
from src.services.learning.learning_resource_service import LearningResourceService, get_learning_resource_service
from src.services.learning.resource_provenance_service import get_resource_provenance_service
from src.services.learning.skill_normalizer import canonical_display_name, normalize_skill, normalize_skill_list

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SkillGapAggregate:
    skill_slug: str
    skill_name: str
    count: int
    source_job_ids: list[int]
    source_job_titles: list[str]
    job_match_ids: list[int]
    max_match_score: float
    latest_match_at: Optional[datetime]

    @property
    def priority(self) -> str:
        if self.count >= 4 or self.max_match_score >= 85:
            return "high"
        if self.count >= 2 or self.max_match_score >= 70:
            return "medium"
        return "low"

    @property
    def estimated_hours(self) -> float:
        base = 4 + (self.count * 3)
        if self.max_match_score < 60:
            base += 2
        return float(min(24, max(4, base)))

    @property
    def reason(self) -> str:
        role_count = len(self.source_job_titles)
        score_text = f"highest match score {round(self.max_match_score, 1)}"
        return (
            f"{self.skill_name} appears in {self.count} matched jobs across {role_count} roles; "
            f"{score_text}."
        )


class LearningPathService:
    def __init__(self, resource_service: Optional[LearningResourceService] = None) -> None:
        self.resource_service = resource_service or get_learning_resource_service()
        self.provenance_service = get_resource_provenance_service()

    async def aggregate_skill_gaps(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 10,
    ) -> list[SkillGapAggregate]:
        query = (
            select(JobMatch, Job)
            .join(Job, Job.id == JobMatch.job_id)
            .where(
                JobMatch.user_id == user_id,
                JobMatch.deleted_at.is_(None),
                Job.deleted_at.is_(None),
                Job.status == "active",
                Job.apply_url.is_not(None),
                Job.apply_url != "",
                JobMatch.overall_score.is_not(None),
            )
            .order_by(JobMatch.overall_score.desc(), JobMatch.created_at.desc())
            .limit(200)
        )
        result = await db.execute(query)

        aggregates: dict[str, dict[str, Any]] = {}
        for match, job in result.all():
            # Prefer the canonical missing-skill list produced by the
            # opportunity matcher. JobMatch.gaps may contain dimension-level
            # explanation dictionaries such as "Experience Match", which are
            # not learnable skill names.
            gap_candidates: list[object] = []

            if isinstance(match.match_details, dict):
                explicit_missing_skills = (
                    match.match_details.get("missing_skills")
                    or []
                )

                if isinstance(
                    explicit_missing_skills,
                    list,
                ):
                    gap_candidates.extend(
                        explicit_missing_skills
                    )

            # Backward-compatible fallback for legacy matches that stored
            # actual skill strings directly in JobMatch.gaps.
            if (
                not gap_candidates
                and isinstance(match.gaps, list)
            ):
                for value in match.gaps:
                    if isinstance(value, str):
                        gap_candidates.append(value)
                        continue

                    if isinstance(value, dict):
                        explicit_skill = (
                            value.get("skill")
                            or value.get("name")
                        )

                        if explicit_skill:
                            gap_candidates.append(
                                explicit_skill
                            )
            for normalized in normalize_skill_list(gap_candidates):
                if not normalized.slug:
                    continue
                bucket = aggregates.setdefault(
                    normalized.slug,
                    {
                        "skill_slug": normalized.slug,
                        "skill_name": normalized.display_name,
                        "count": 0,
                        "source_job_ids": [],
                        "source_job_titles": [],
                        "job_match_ids": [],
                        "max_match_score": 0.0,
                        "latest_match_at": None,
                    },
                )
                bucket["count"] += 1
                bucket["skill_name"] = bucket["skill_name"] or normalized.display_name
                if job.id not in bucket["source_job_ids"]:
                    bucket["source_job_ids"].append(job.id)
                if job.title not in bucket["source_job_titles"]:
                    bucket["source_job_titles"].append(job.title)
                if match.id not in bucket["job_match_ids"]:
                    bucket["job_match_ids"].append(match.id)
                bucket["max_match_score"] = max(bucket["max_match_score"], float(match.overall_score or 0))
                latest = match.created_at or job.created_at if hasattr(job, "created_at") else None
                if latest and (bucket["latest_match_at"] is None or latest > bucket["latest_match_at"]):
                    bucket["latest_match_at"] = latest

        aggregates_list = [
            SkillGapAggregate(**value)
            for value in sorted(
                aggregates.values(),
                key=lambda item: (-item["count"], -float(item["max_match_score"]), item["skill_name"].lower()),
            )[:limit]
        ]
        return aggregates_list

    def _build_steps(
        self,
        aggregate: SkillGapAggregate,
        resources: list[LearningResource],
    ) -> list[dict[str, Any]]:
        foundation = resources[0] if resources else None
        hands_on = next(
            (resource for resource in resources if (resource.metadata_ or {}).get("step_type") in {"hands_on", "project"}),
            None,
        )
        proof = next(
            (resource for resource in resources if (resource.metadata_ or {}).get("step_type") in {"proof", "portfolio"}),
            None,
        )

        def _resource_payload(resource: Optional[LearningResource]) -> list[dict[str, Any]]:
            if not resource:
                return []
            return [self.resource_service_record(resource)]

        return [
            {
                "order_index": 1,
                "step_type": "foundation",
                "title": f"Understand {aggregate.skill_name} fundamentals",
                "reason": f"Start with the official free material for {aggregate.skill_name}.",
                "estimated_minutes": 90,
                "practice_project": None,
                "resources": _resource_payload(foundation),
            },
            {
                "order_index": 2,
                "step_type": "hands_on",
                "title": f"Apply {aggregate.skill_name} in a small project",
                "reason": "Turn reading into a runnable or demonstrable artifact.",
                "estimated_minutes": 180,
                "practice_project": self._practice_project_idea(aggregate.skill_name),
                "resources": _resource_payload(hands_on) or _resource_payload(foundation),
            },
            {
                "order_index": 3,
                "step_type": "proof",
                "title": "Add evidence to resume and portfolio",
                "reason": "Translate the new skill into interview-ready proof.",
                "estimated_minutes": 60,
                "practice_project": f"Write one resume bullet and one portfolio note showing how you used {aggregate.skill_name}.",
                "resources": _resource_payload(proof),
            },
        ]

    def _practice_project_idea(self, skill_name: str) -> str:
        skill = skill_name.strip()
        lower = skill.lower()
        if lower in {"aws", "amazon web services"}:
            return "Deploy a small API or static site on AWS and document the architecture choices."
        if lower in {"docker"}:
            return "Containerize a small API and publish a repeatable local development workflow."
        if lower in {"kubernetes"}:
            return "Deploy a containerized app to a local Kubernetes cluster and expose it with a Service."
        if lower in {"fastapi"}:
            return "Build a small typed API with validation, auth, and one protected endpoint."
        if lower in {"react"}:
            return "Create a small dashboard with forms, state updates, and loading/error states."
        if lower in {"postgresql"}:
            return "Model a simple career tracker schema and write two analytics queries."
        if lower in {"pytorch", "tensorflow"}:
            return "Train a small model on a public dataset and explain evaluation metrics clearly."
        if lower in {"langchain"}:
            return "Build a minimal retrieval assistant over a small document set with citations."
        return f"Build a small demo that uses {skill} in one production-style workflow."

    def resource_service_record(
        self,
        resource: LearningResource,
        provenance_summary: Optional[dict[str, Any]] = None,
        outcome_summary: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        metadata = resource.metadata_ or {}
        source_domain = metadata.get("source_domain") or urlparse(resource.source_url).netloc.lower()
        payload = {
            "id": resource.id,
            "skill_slug": resource.skill_slug,
            "skill_name": resource.skill_name,
            "title": resource.title,
            "provider": resource.provider,
            "source_type": resource.source_type,
            "source_url": resource.source_url,
            "channel_name": resource.channel_name,
            "duration_minutes": resource.duration_minutes,
            "difficulty": resource.difficulty,
            "format": resource.format,
            "is_free": resource.is_free,
            "language": resource.language,
            "trust_score": float(resource.trust_score or 0),
            "relevance_score": float(resource.relevance_score or 0),
            "freshness_score": float(resource.freshness_score or 0),
            "last_verified_at": resource.last_verified_at.isoformat() if resource.last_verified_at else None,
            "metadata": metadata,
            "source_domain": source_domain,
            "discovery_source": metadata.get("discovery_source"),
            "verification_status": metadata.get("verification_status"),
            "price_status": metadata.get("price_status"),
            "cache_status": metadata.get("cache_status"),
        }
        if provenance_summary:
            payload["provenance_summary"] = provenance_summary
        if outcome_summary:
            payload["outcome_summary"] = outcome_summary
        return payload

    async def _resource_provenance_summaries(
        self,
        db: AsyncSession,
        resources: list[LearningResource],
    ) -> dict[int, dict[str, Any]]:
        summaries: dict[int, dict[str, Any]] = {}
        try:
            for resource in resources:
                summary = await self.provenance_service.get_latest_resource_summary(db, resource_id=resource.id)
                if summary:
                    summaries[resource.id] = summary
        except Exception as exc:  # pragma: no cover - provenance must not break learning paths
            logger.debug("Learning path provenance lookup skipped: %s", exc)
        return summaries

    async def _resource_outcome_summaries(
        self,
        db: AsyncSession,
        resources: list[LearningResource],
    ) -> dict[int, dict[str, Any]]:
        summaries: dict[int, dict[str, Any]] = {}
        outcome_service = get_learning_outcome_service()
        try:
            for resource in resources:
                summary = await outcome_service.get_latest_resource_outcome_summary(db, resource_id=resource.id)
                if summary:
                    summaries[resource.id] = summary
        except Exception as exc:  # pragma: no cover - outcome lookup must not break learning paths
            logger.debug("Learning path outcome lookup skipped: %s", exc)
        return summaries

    def _aggregate_resource_scores(self, resources: list[LearningResource]) -> dict[str, float]:
        if not resources:
            return {"trust": 0.0, "relevance": 0.0, "freshness": 0.0}
        count = float(len(resources))
        return {
            "trust": sum(float(resource.trust_score or 0.0) for resource in resources) / count,
            "relevance": sum(float(resource.relevance_score or 0.0) for resource in resources) / count,
            "freshness": sum(float(resource.freshness_score or 0.0) for resource in resources) / count,
        }

    async def _build_path_payload(
        self,
        db: AsyncSession,
        user_id: str,
        aggregate: SkillGapAggregate,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        skill_name = aggregate.skill_name
        resources = await self.resource_service.ensure_skill_resources(
            db,
            aggregate.skill_slug,
            skill_name=skill_name,
            limit=6,
            force_refresh=force_refresh,
        )
        if not resources:
            provider_health = self.resource_service.provider_health()
            discovery_status = provider_health.get("status", "seeded_fallback")
            provider_message = provider_health.get("message") or "Verified curated fallback resources are available when seeded."
            if discovery_status == "success":
                message = f"No verified resources were returned for {skill_name} yet. {provider_message}"
            elif discovery_status in {"missing_api_key", "skipped"}:
                message = f"Live discovery is not fully configured for {skill_name}. {provider_message}"
            else:
                message = f"No verified {skill_name} resources were discovered yet. {provider_message}"
            return {
                "skill_slug": aggregate.skill_slug,
                "skill_name": skill_name,
                "priority": aggregate.priority,
                "estimated_hours": aggregate.estimated_hours,
                "reason": aggregate.reason,
                "source_job_ids": aggregate.source_job_ids,
                "source_job_titles": aggregate.source_job_titles,
                "job_match_ids": aggregate.job_match_ids,
                "resource_status": "not_available",
                "discovery_status": discovery_status,
                "resource_count": 0,
                "resource_titles": [],
                "source_domains": [],
                "message": message,
                "cached": False,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "refreshed_at": datetime.utcnow().isoformat() + "Z",
                "steps": [],
            }

        provenance_summaries = await self._resource_provenance_summaries(db, resources)
        outcome_summaries = await self._resource_outcome_summaries(db, resources)
        resource_scores = self._aggregate_resource_scores(resources)
        score_builder = getattr(self.provenance_service, "build_score_breakdown", None)
        if callable(score_builder):
            path_score_breakdown = score_builder(
                trust_score=resource_scores["trust"],
                relevance_score=resource_scores["relevance"],
                freshness_score=resource_scores["freshness"],
                verification_status="verified" if resources else "insufficient_data",
                source_kind="generated_path",
            )
        else:
            path_score_breakdown = {
                "formula": "trust*0.45 + relevance*0.35 + freshness*0.20",
                "trust": round(resource_scores["trust"], 4),
                "relevance": round(resource_scores["relevance"], 4),
                "freshness": round(resource_scores["freshness"], 4),
                "weighted_total": round(
                    ((resource_scores["trust"] * 0.45) + (resource_scores["relevance"] * 0.35) + (resource_scores["freshness"] * 0.20))
                    * 100.0,
                    2,
                ),
                "verification_bonus": 0.0,
                "source_bonus": 0.0,
                "composite_score": round(
                    min(
                        100.0,
                        ((resource_scores["trust"] * 0.45) + (resource_scores["relevance"] * 0.35) + (resource_scores["freshness"] * 0.20))
                        * 100.0,
                    ),
                    2,
                ),
                "verification_status": "verified" if resources else "insufficient_data",
                "source_kind": "generated_path",
            }
        steps = self._build_steps(aggregate, resources)
        for step in steps:
            for resource in step.get("resources", []):
                resource_id = resource.get("id")
                if resource_id in provenance_summaries:
                    resource["provenance_summary"] = provenance_summaries[resource_id]
                if resource_id in outcome_summaries:
                    resource["outcome_summary"] = outcome_summaries[resource_id]
        source_domains = sorted({(resource.metadata_ or {}).get("source_domain") or urlparse(resource.source_url).netloc.lower() for resource in resources if resource.source_url})
        return {
            "skill_slug": aggregate.skill_slug,
            "skill_name": skill_name,
            "priority": aggregate.priority,
            "estimated_hours": aggregate.estimated_hours,
            "reason": aggregate.reason,
            "source_job_ids": aggregate.source_job_ids,
            "source_job_titles": aggregate.source_job_titles,
            "job_match_ids": aggregate.job_match_ids,
            "resource_status": "available",
            "discovery_status": self.resource_service.provider_health().get("status", "success"),
            "resource_count": len(resources),
            "resource_titles": [resource.title for resource in resources],
            "source_domains": [domain for domain in source_domains if domain],
            "message": None,
            "cached": True,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "refreshed_at": datetime.utcnow().isoformat() + "Z",
            "steps": steps,
            "provenance_summary": {
                "source_entity_type": "learning_path",
                "source_entity_id": aggregate.skill_slug,
                "score_breakdown": path_score_breakdown,
                "score_total": path_score_breakdown["composite_score"],
                "score_formula": "trust*0.45 + relevance*0.35 + freshness*0.20",
                "confidence": "high" if resources else "low",
                "status": "success" if resources else "insufficient_data",
                "recorded_at": datetime.utcnow().isoformat() + "Z",
                "evidence_count": len(provenance_summaries),
                "record_count": len(provenance_summaries),
                "explanation": f"Learning path built from {len(resources)} verified resource(s) for {aggregate.skill_name}.",
            },
        }

    async def persist_path(
        self,
        db: AsyncSession,
        user_id: str,
        aggregate: SkillGapAggregate,
        path_payload: dict[str, Any],
    ) -> dict[str, Any]:
        stmt = insert(UserSkillLearningPath.__table__).values(
            user_id=user_id,
            skill_slug=aggregate.skill_slug,
            skill_name=aggregate.skill_name,
            source_job_id=aggregate.source_job_ids[0] if aggregate.source_job_ids else None,
            job_match_id=aggregate.job_match_ids[0] if aggregate.job_match_ids else None,
            priority=aggregate.priority,
            reason=aggregate.reason,
            status="active",
            estimated_hours=aggregate.estimated_hours,
            resource_status=path_payload["resource_status"],
            message=path_payload.get("message"),
            evidence={
                "source_job_ids": aggregate.source_job_ids,
                "source_job_titles": aggregate.source_job_titles,
                "job_match_ids": aggregate.job_match_ids,
                "max_match_score": aggregate.max_match_score,
            },
            generated_at=datetime.utcnow(),
            refreshed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_learning_paths_user_skill",
            set_={
                "skill_name": stmt.excluded.skill_name,
                "source_job_id": stmt.excluded.source_job_id,
                "job_match_id": stmt.excluded.job_match_id,
                "priority": stmt.excluded.priority,
                "reason": stmt.excluded.reason,
                "status": "active",
                "estimated_hours": stmt.excluded.estimated_hours,
                "resource_status": stmt.excluded.resource_status,
                "message": stmt.excluded.message,
                "evidence": stmt.excluded.evidence,
                "refreshed_at": stmt.excluded.refreshed_at,
                "updated_at": datetime.utcnow(),
            },
        ).returning(UserSkillLearningPath.id)
        result = await db.execute(stmt)
        learning_path_id = result.scalar_one()

        await db.execute(delete(LearningPathItem).where(LearningPathItem.learning_path_id == learning_path_id))
        for index, step in enumerate(path_payload.get("steps", [])):
            resources = step.get("resources") or []
            resource_id = resources[0].get("id") if resources else None
            await db.execute(
                insert(LearningPathItem.__table__).values(
                    learning_path_id=learning_path_id,
                    resource_id=resource_id,
                    order_index=index,
                    step_type=step.get("step_type") or f"step_{index + 1}",
                    reason=step.get("reason"),
                    estimated_minutes=step.get("estimated_minutes"),
                    practice_project=step.get("practice_project"),
                    created_at=datetime.utcnow(),
                )
            )
        await get_career_event_service().emit_event(
            db,
            event_type="LearningPathGenerated",
            entity_type="learning_path",
            entity_id=str(learning_path_id),
            source_service="services.learning.learning_path_service",
            user_id=user_id,
            source_table="user_skill_learning_paths",
            source_id=learning_path_id,
            payload={
                "skill_slug": aggregate.skill_slug,
                "skill_name": aggregate.skill_name,
                "priority": aggregate.priority,
                "estimated_hours": aggregate.estimated_hours,
                "resource_status": path_payload.get("resource_status"),
                "resource_count": path_payload.get("resource_count", 0),
                "cached": bool(path_payload.get("cached", False)),
                "generated_at": path_payload.get("generated_at"),
                "refreshed_at": path_payload.get("refreshed_at"),
            },
            evidence=[
                get_career_event_service().build_evidence_ref(
                    table="user_skill_learning_paths",
                    source_id=learning_path_id,
                    note="learning path generated from stored job matches and verified resources",
                    extra={
                        "source_job_ids": aggregate.source_job_ids,
                        "job_match_ids": aggregate.job_match_ids,
                        "resource_titles": path_payload.get("resource_titles", []),
                    },
                )
            ],
            provider=(self.resource_service.provider_health() or {}).get("provider"),
            trace_id=f"learning_path:{aggregate.skill_slug}",
        )
        await db.commit()
        resource_entries: list[dict[str, Any]] = []
        for step in path_payload.get("steps", []):
            resource_entries.extend(step.get("resources") or [])
        if resource_entries:
            trust_scores = [float(resource.get("trust_score") or 0.0) for resource in resource_entries]
            relevance_scores = [float(resource.get("relevance_score") or 0.0) for resource in resource_entries]
            freshness_scores = [float(resource.get("freshness_score") or 0.0) for resource in resource_entries]
            provenance_source_uid = f"learning_path:{aggregate.skill_slug}:{learning_path_id}"
            try:
                await self.provenance_service.record_provenance(
                    db,
                    provenance_type="learning_path",
                    source_entity_type="learning_path",
                    source_entity_id=str(learning_path_id),
                    skill_slug=aggregate.skill_slug,
                    skill_name=aggregate.skill_name,
                    title=f"{aggregate.skill_name} learning path",
                    provider=(self.resource_service.provider_health() or {}).get("provider", "learning"),
                    source_url=None,
                    resource_id=None,
                    discovery_run_uid=None,
                    user_id=user_id,
                    job_id=aggregate.source_job_ids[0] if aggregate.source_job_ids else None,
                    source_table="user_skill_learning_paths",
                    source_pk=learning_path_id,
                    trust_score=sum(trust_scores) / len(trust_scores),
                    relevance_score=sum(relevance_scores) / len(relevance_scores),
                    freshness_score=sum(freshness_scores) / len(freshness_scores),
                    verification_status="verified",
                    source_kind="generated_path",
                    status="success",
                    evidence=[
                        get_career_event_service().build_evidence_ref(
                            table="user_skill_learning_paths",
                            source_id=learning_path_id,
                            note="Learning path generated from verified resources and skill-gap evidence",
                            extra={
                                "source_job_ids": aggregate.source_job_ids,
                                "job_match_ids": aggregate.job_match_ids,
                                "resource_titles": path_payload.get("resource_titles", []),
                            },
                        )
                    ],
                    source_context={
                        "resource_count": len(resource_entries),
                        "resource_titles": path_payload.get("resource_titles", []),
                        "source_job_titles": aggregate.source_job_titles,
                        "provenance_uid": provenance_source_uid,
                    },
                )
            except Exception as exc:  # pragma: no cover - provenance must not break path generation
                logger.debug("Failed to store learning path provenance for path_id=%s: %s", learning_path_id, exc)
        return path_payload

    async def get_skill_gap_summary(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        aggregates = await self.aggregate_skill_gaps(db, user_id, limit=limit)
        items = [
            {
                "skill_slug": item.skill_slug,
                "skill_name": item.skill_name,
                "count": item.count,
                "priority": item.priority,
                "estimated_hours": item.estimated_hours,
                "reason": item.reason,
                "source_job_ids": item.source_job_ids,
                "source_job_titles": item.source_job_titles,
                "job_match_ids": item.job_match_ids,
                "max_match_score": item.max_match_score,
                "resource_status": "available",
            }
            for item in aggregates
        ]
        return {
            "status": "ok",
            "user_id": user_id,
            "total_gaps": sum(item["count"] for item in items),
            "unique_skills": len(items),
            "gaps": items,
            "provider_health": self.resource_service.provider_health(),
        }

    async def list_paths(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 10,
        skill_slugs: Optional[list[str]] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        effective_limit = limit
        if skill_slugs:
            effective_limit = max(limit, len(skill_slugs))

        aggregates = await self.aggregate_skill_gaps(db, user_id, limit=effective_limit)
        if skill_slugs:
            requested = []
            aggregate_by_slug = {aggregate.skill_slug: aggregate for aggregate in aggregates}
            seen_requested: set[str] = set()
            for raw_skill in skill_slugs:
                normalized = normalize_skill(raw_skill)
                if not normalized.slug:
                    continue
                if normalized.slug in seen_requested:
                    continue
                seen_requested.add(normalized.slug)
                aggregate = aggregate_by_slug.get(normalized.slug)
                if aggregate is None:
                    aggregate = SkillGapAggregate(
                        skill_slug=normalized.slug,
                        skill_name=normalized.display_name or canonical_display_name(normalized.slug),
                        count=1,
                        source_job_ids=[],
                        source_job_titles=[],
                        job_match_ids=[],
                        max_match_score=0.0,
                        latest_match_at=None,
                    )
                requested.append(aggregate)
            aggregates = requested or aggregates
        paths: list[dict[str, Any]] = []
        for aggregate in aggregates:
            payload = await self._build_path_payload(db, user_id, aggregate, force_refresh=force_refresh)
            if payload.get("resource_status") == "available":
                await self.persist_path(db, user_id, aggregate, payload)
            paths.append(payload)
        return {
            "status": "ok",
            "user_id": user_id,
            "paths": paths,
            "provider_health": self.resource_service.provider_health(),
            "skill_gaps": [
                {
                    "skill_slug": agg.skill_slug,
                    "skill_name": agg.skill_name,
                    "count": agg.count,
                    "priority": agg.priority,
                    "estimated_hours": agg.estimated_hours,
                    "reason": agg.reason,
                }
                for agg in aggregates
            ],
        }

    async def get_path(
        self,
        db: AsyncSession,
        user_id: str,
        skill_slug: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        normalized = normalize_skill(skill_slug)
        if not normalized.slug:
            return {
                "status": "error",
                "error": {"code": "INVALID_SKILL", "message": "Skill slug is required."},
                "provider_health": self.resource_service.provider_health(),
            }

        aggregate = await self._aggregate_single_skill(db, user_id, normalized.slug)
        if not aggregate:
            aggregate = SkillGapAggregate(
                skill_slug=normalized.slug,
                skill_name=normalized.display_name,
                count=1,
                source_job_ids=[],
                source_job_titles=[],
                job_match_ids=[],
                max_match_score=0.0,
                latest_match_at=None,
            )

        payload = await self._build_path_payload(db, user_id, aggregate, force_refresh=force_refresh)
        if payload["resource_status"] == "available":
            await self.persist_path(db, user_id, aggregate, payload)
        return {
            "status": "ok",
            "user_id": user_id,
            "path": payload,
            "provider_health": self.resource_service.provider_health(),
        }

    async def refresh_paths(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        result = await self.list_paths(db, user_id, limit=limit, force_refresh=True)
        return {
            "status": "ok",
            "user_id": user_id,
            "refreshed_count": len(result["paths"]),
            "paths": result["paths"],
            "provider_health": result["provider_health"],
        }

    async def _aggregate_single_skill(
        self,
        db: AsyncSession,
        user_id: str,
        skill_slug: str,
    ) -> Optional[SkillGapAggregate]:
        aggregates = await self.aggregate_skill_gaps(db, user_id, limit=50)
        for item in aggregates:
            if item.skill_slug == skill_slug:
                return item
        return None


_SERVICE: Optional[LearningPathService] = None


def get_learning_path_service() -> LearningPathService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = LearningPathService()
    return _SERVICE
