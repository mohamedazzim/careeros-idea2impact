"""GitHub repository and issue recommendations for missing learning skills."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.redis import get_redis
from src.integrations.github.repo_discovery import (
    GitHubProjectDiscoveryProvider,
    GitHubSkillDiscoveryResult,
    get_github_project_discovery_provider,
)
from src.models.jobs import Job, JobMatch
from src.services.learning.resource_provenance_service import get_resource_provenance_service
from src.services.events import get_career_event_service
from src.services.learning.learning_path_service import LearningPathService, SkillGapAggregate, get_learning_path_service
from src.services.learning.skill_normalizer import canonical_display_name, normalize_skill_list

logger = logging.getLogger(__name__)


class GitHubProjectService:
    def __init__(
        self,
        learning_path_service: Optional[LearningPathService] = None,
        github_provider: Optional[GitHubProjectDiscoveryProvider] = None,
    ) -> None:
        self.learning_path_service = learning_path_service or get_learning_path_service()
        self.github_provider = github_provider or get_github_project_discovery_provider()
        self.provenance_service = get_resource_provenance_service()

    def _cache_key(self, user_id: str, skills: list[str], job_id: Optional[int]) -> str:
        raw = "|".join([user_id, str(job_id or ""), ",".join(skills)])
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return f"{settings.RETRIEVAL_CACHE_KEY_PREFIX}learning_github_projects:{digest}"

    async def _read_cache(self, key: str) -> Optional[dict[str, Any]]:
        if not settings.RETRIEVAL_CACHE_ENABLED:
            return None
        try:
            redis = await get_redis()
            raw = await redis.get(key)
            if not raw:
                return None
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else None
        except Exception as exc:  # pragma: no cover - defensive cache fallback
            logger.debug("Learning GitHub project cache read failed: %s", exc)
            return None

    async def _write_cache(self, key: str, payload: dict[str, Any]) -> None:
        if not settings.RETRIEVAL_CACHE_ENABLED:
            return
        try:
            redis = await get_redis()
            await redis.setex(
                key,
                max(60, int(settings.GITHUB_REPO_CACHE_TTL_HOURS) * 3600),
                json.dumps(payload, default=str),
            )
        except Exception as exc:  # pragma: no cover - defensive cache fallback
            logger.debug("Learning GitHub project cache write failed: %s", exc)

    async def _load_job_context(self, db: AsyncSession, user_id: str, job_id: int) -> dict[str, Any]:
        job_result = await db.execute(select(Job).where(Job.id == job_id, Job.deleted_at.is_(None)))
        job = job_result.scalar_one_or_none()
        if job is None:
            raise ValueError("Job not found")

        match_result = await db.execute(
            select(JobMatch).where(
                JobMatch.user_id == user_id,
                JobMatch.job_id == job_id,
                JobMatch.deleted_at.is_(None),
            )
            .order_by(JobMatch.created_at.desc(), JobMatch.id.desc())
            .limit(1)
        )
        match = match_result.scalar_one_or_none()

        raw_gap_values: list[object] = []
        if match and isinstance(match.gaps, list):
            raw_gap_values.extend(match.gaps)
        if match and isinstance(match.match_details, dict):
            raw_gap_values.extend(match.match_details.get("missing_skills") or [])
            raw_gap_values.extend(match.match_details.get("job_extraction", {}).get("skills", []))
        if not raw_gap_values and isinstance(job.skills_required, list):
            raw_gap_values.extend(job.skills_required)

        normalized_gaps = normalize_skill_list(raw_gap_values)
        return {
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "apply_url": job.apply_url,
            "source_url": job.source_url,
            "match_score": float(match.overall_score or 0.0) if match else None,
            "missing_skill_slugs": [item.slug for item in normalized_gaps],
            "missing_skill_names": [item.display_name for item in normalized_gaps],
        }

    def _aggregate_for_skill(
        self,
        aggregate_map: dict[str, SkillGapAggregate],
        skill_slug: str,
        skill_name: str,
        job_context: Optional[dict[str, Any]],
    ) -> SkillGapAggregate:
        aggregate = aggregate_map.get(skill_slug)
        if aggregate is not None:
            return aggregate
        return SkillGapAggregate(
            skill_slug=skill_slug,
            skill_name=skill_name,
            count=1,
            source_job_ids=[job_context["job_id"]] if job_context and job_context.get("job_id") else [],
            source_job_titles=[job_context["title"]] if job_context and job_context.get("title") else [],
            job_match_ids=[],
            max_match_score=float(job_context.get("match_score") or 0.0) if job_context else 0.0,
            latest_match_at=None,
        )

    def _skill_payload(
        self,
        aggregate: SkillGapAggregate,
        discovery: GitHubSkillDiscoveryResult,
    ) -> dict[str, Any]:
        repositories = [repo.to_dict() for repo in discovery.repositories]
        templates = [repo.to_dict() for repo in discovery.templates]
        issues = [issue.to_dict() for issue in discovery.good_first_issues]
        return {
            "skill_slug": aggregate.skill_slug,
            "skill_name": aggregate.skill_name,
            "count": aggregate.count,
            "priority": aggregate.priority,
            "estimated_hours": aggregate.estimated_hours,
            "reason": aggregate.reason,
            "source_job_ids": aggregate.source_job_ids,
            "source_job_titles": aggregate.source_job_titles,
            "job_match_ids": aggregate.job_match_ids,
            "repository_status": "available" if repositories else "not_available",
            "issue_status": "available" if issues else "not_available",
            "source_status": discovery.source_status,
            "repository_count": len(repositories),
            "template_count": len(templates),
            "issue_count": len(issues),
            "repositories": repositories,
            "templates": templates,
            "good_first_issues": issues,
            "search_queries": discovery.search_queries,
            "errors": discovery.errors,
            "provenance_summary": {
                "source_entity_type": "github_project",
                "source_entity_id": aggregate.skill_slug,
                "resource_count": len(repositories) + len(issues),
                "source_status": discovery.source_status,
                "score_breakdown": self.provenance_service.build_score_breakdown(
                    trust_score=min(1.0, 0.55 + (len(repositories) * 0.1)),
                    relevance_score=min(1.0, 0.6 + (len(issues) * 0.08)),
                    freshness_score=0.8 if discovery.source_status == "available" else 0.6,
                    verification_status="verified" if (repositories or issues) else "insufficient_data",
                    source_kind="github_project",
                ),
                "score_total": self.provenance_service.build_score_breakdown(
                    trust_score=min(1.0, 0.55 + (len(repositories) * 0.1)),
                    relevance_score=min(1.0, 0.6 + (len(issues) * 0.08)),
                    freshness_score=0.8 if discovery.source_status == "available" else 0.6,
                    verification_status="verified" if (repositories or issues) else "insufficient_data",
                    source_kind="github_project",
                )["composite_score"],
                "score_formula": "trust*0.45 + relevance*0.35 + freshness*0.20",
                "confidence": "high" if (repositories or issues) else "low",
                "status": "success" if (repositories or issues) else "insufficient_data",
                "recorded_at": datetime.utcnow().isoformat().replace("+00:00", "Z"),
                "evidence_count": len(repositories) + len(issues),
                "explanation": (
                    f"GitHub suggestions for {aggregate.skill_name} were assembled from "
                    f"{len(repositories)} repository result(s), {len(templates)} template(s), and {len(issues)} issue(s)."
                ),
            },
        }

    async def build_github_projects(
        self,
        db: AsyncSession,
        user_id: str,
        skills: list[str],
        job_id: Optional[int] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        normalized_skills = normalize_skill_list(skills)

        job_context: Optional[dict[str, Any]] = None
        if job_id is not None:
            job_context = await self._load_job_context(db, user_id, job_id)
            if not normalized_skills:
                normalized_skills = normalize_skill_list(job_context.get("missing_skill_slugs") or [])

        if not normalized_skills:
            return {
                "status": "error",
                "error": {
                    "code": "NO_SKILLS",
                    "message": "Provide at least one skill or a valid job_id to discover GitHub projects.",
                },
                "skills": [],
                "provider_health": self.github_provider.provider_health(),
            }

        cache_key = self._cache_key(user_id, [item.slug for item in normalized_skills], job_id)
        if not force_refresh:
            cached = await self._read_cache(cache_key)
            if cached:
                cached["cached"] = True
                return cached

        aggregates = await self.learning_path_service.aggregate_skill_gaps(
            db,
            user_id,
            limit=max(10, len(normalized_skills)),
        )
        aggregate_by_slug = {aggregate.skill_slug: aggregate for aggregate in aggregates}

        skills_payload: list[dict[str, Any]] = []
        source_statuses: list[str] = []
        any_repositories = False
        any_issues = False

        for normalized in normalized_skills:
            aggregate = self._aggregate_for_skill(aggregate_by_slug, normalized.slug, normalized.display_name, job_context)
            discovery = await self.github_provider.discover_skill(
                normalized.slug,
                normalized.display_name,
                limit=settings.GITHUB_REPO_MAX_RESULTS_PER_SKILL,
            )
            skill_payload = self._skill_payload(aggregate, discovery)
            any_repositories = any_repositories or bool(skill_payload["repositories"])
            any_issues = any_issues or bool(skill_payload["good_first_issues"])
            source_statuses.append(str(skill_payload["source_status"]))
            skills_payload.append(skill_payload)

        for skill_payload in skills_payload:
            try:
                resource_count = int(skill_payload.get("repository_count") or 0) + int(skill_payload.get("issue_count") or 0)
                avg_trust = min(1.0, 0.55 + (float(skill_payload.get("repository_count") or 0) * 0.1))
                avg_relevance = min(1.0, 0.6 + (float(skill_payload.get("issue_count") or 0) * 0.08))
                avg_freshness = 0.8 if skill_payload.get("source_status") == "available" else 0.6
                await self.provenance_service.record_provenance(
                    db,
                    provenance_type="github_project",
                    source_entity_type="github_project",
                    source_entity_id=str(skill_payload.get("skill_slug") or ""),
                    skill_slug=str(skill_payload.get("skill_slug") or ""),
                    skill_name=str(skill_payload.get("skill_name") or ""),
                    title=f"GitHub projects for {skill_payload.get('skill_name') or skill_payload.get('skill_slug')}",
                    provider=(self.github_provider.provider_health() or {}).get("provider", "github"),
                    source_url=None,
                    user_id=user_id,
                    job_id=job_id,
                    source_table="job_matches" if job_id is not None else None,
                    source_pk=job_id,
                    trust_score=avg_trust,
                    relevance_score=avg_relevance,
                    freshness_score=avg_freshness,
                    verification_status="verified" if resource_count else "insufficient_data",
                    source_kind="github_project",
                    status="success" if resource_count else "insufficient_data",
                    evidence=[
                        get_career_event_service().build_evidence_ref(
                            table="job_matches" if job_id is not None else "github_repositories",
                            source_id=job_id if job_id is not None else skill_payload.get("skill_slug"),
                            note="GitHub project suggestions generated from repository and issue discovery",
                            extra={
                                "repository_count": skill_payload.get("repository_count"),
                                "template_count": skill_payload.get("template_count"),
                                "issue_count": skill_payload.get("issue_count"),
                            },
                        )
                    ],
                    source_context={
                        "repository_count": skill_payload.get("repository_count"),
                        "template_count": skill_payload.get("template_count"),
                        "issue_count": skill_payload.get("issue_count"),
                        "resource_count": resource_count,
                    },
                )
            except Exception as exc:  # pragma: no cover - provenance must not break GitHub projects
                logger.debug("Failed to store GitHub project provenance for skill=%s: %s", skill_payload.get("skill_slug"), exc)

        if any_repositories and any_issues and all(status == "available" for status in source_statuses):
            source_status = "available"
        elif any_repositories or any_issues:
            source_status = "partial"
        elif "rate_limited" in source_statuses:
            source_status = "rate_limited"
        else:
            source_status = "not_available"

        payload = {
            "status": "ok",
            "user_id": user_id,
            "job_id": job_id,
            "job_context": job_context,
            "cached": False,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "provider_health": self.github_provider.provider_health(),
            "source_status": source_status,
            "skills": skills_payload,
        }
        await get_career_event_service().emit_event(
            db,
            event_type="GitHubProjectsRefreshed",
            entity_type="github_project_set",
            entity_id=",".join(item.slug for item in normalized_skills)[:128],
            source_service="services.learning.github_project_service",
            user_id=user_id,
            source_table="job_matches" if job_id is not None else None,
            source_id=job_id,
            payload={
                "job_id": job_id,
                "skills": [item.slug for item in normalized_skills],
                "cached": False,
                "source_status": payload["source_status"],
                "provider_health": payload["provider_health"],
                "skill_count": len(skills_payload),
            },
            evidence=[
                get_career_event_service().build_evidence_ref(
                    table="job_matches" if job_id is not None else "github_repositories",
                    source_id=job_id if job_id is not None else (normalized_skills[0].slug if normalized_skills else None),
                    note="GitHub project suggestions generated from verified skill gaps and repository signals",
                    extra={
                        "skills": [item.slug for item in normalized_skills],
                        "job_context": job_context,
                    },
                )
            ],
            provider=(self.github_provider.provider_health() or {}).get("provider"),
            trace_id=f"github_projects:{job_id or normalized_skills[0].slug}",
        )
        await self._write_cache(cache_key, payload)
        return payload


_SERVICE: Optional[GitHubProjectService] = None


def get_github_project_service() -> GitHubProjectService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = GitHubProjectService()
    return _SERVICE
