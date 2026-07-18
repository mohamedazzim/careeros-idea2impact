"""Gap-to-action recommendations for learning resources and proof-building."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.redis import get_redis
from src.models.jobs import Job, JobMatch
from src.services.learning.learning_path_service import (
    LearningPathService,
    SkillGapAggregate,
    get_learning_path_service,
)
from src.services.learning.resource_provenance_service import get_resource_provenance_service
from src.services.events import get_career_event_service
from src.services.learning.learning_outcome_service import get_learning_outcome_service
from src.services.learning.learning_resource_service import (
    LearningResourceService,
    get_learning_resource_service,
)
from src.services.learning.skill_normalizer import canonical_display_name, normalize_skill_list

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SkillContext:
    skill_slug: str
    skill_name: str
    aggregate: SkillGapAggregate
    resources: list[Any]
    resource_status: str
    source_status: str


class LearningGapActionService:
    def __init__(
        self,
        learning_path_service: Optional[LearningPathService] = None,
        learning_resource_service: Optional[LearningResourceService] = None,
    ) -> None:
        self.learning_path_service = learning_path_service or get_learning_path_service()
        self.learning_resource_service = learning_resource_service or get_learning_resource_service()
        self.provenance_service = get_resource_provenance_service()
        self.outcome_service = get_learning_outcome_service()

    def _cache_key(self, user_id: str, skills: list[str], job_id: Optional[int]) -> str:
        raw = "|".join([user_id, str(job_id or ""), ",".join(skills)])
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return f"{settings.RETRIEVAL_CACHE_KEY_PREFIX}learning_gap_actions:{digest}"

    async def _read_cache(self, key: str) -> Optional[dict[str, Any]]:
        if not settings.RETRIEVAL_CACHE_ENABLED:
            return None
        try:
            redis = await get_redis()
            raw = await redis.get(key)
            if not raw:
                return None
            import json

            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else None
        except Exception as exc:
            logger.debug("Learning gap-action cache read failed: %s", exc)
            return None

    async def _write_cache(self, key: str, payload: dict[str, Any]) -> None:
        if not settings.RETRIEVAL_CACHE_ENABLED:
            return
        try:
            redis = await get_redis()
            import json

            await redis.setex(
                key,
                max(60, int(settings.LEARNING_RESOURCE_CACHE_TTL_HOURS) * 3600),
                json.dumps(payload, default=str),
            )
        except Exception as exc:
            logger.debug("Learning gap-action cache write failed: %s", exc)

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

    def _template_for_skill(
        self,
        skill_slug: str,
        skill_name: str,
        source_resources: list[dict[str, Any]],
        job_context: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        primary_resource_title = source_resources[0]["title"] if source_resources else None
        job_label = None
        if job_context:
            job_bits = [job_context.get("title"), job_context.get("company")]
            job_label = " at ".join([bit for bit in job_bits if bit]) or None

        project_title = {
            "aws": "Deploy a FastAPI service on AWS",
            "docker": "Containerize a small service with Docker",
            "kubernetes": "Ship the service to Kubernetes",
            "fastapi": "Build a typed API with FastAPI",
            "react": "Create a job-matching dashboard in React",
            "postgresql": "Design a PostgreSQL career tracker schema",
            "python": "Build a Python automation or CLI tool",
            "java": "Ship a small REST API in Java",
            "javascript": "Build a browser-facing workflow with JavaScript",
            "langchain": "Build a cited retrieval assistant with LangChain",
            "pytorch": "Train and evaluate a small PyTorch model",
            "tensorflow": "Train and evaluate a small TensorFlow model",
            "git": "Create a clean git workflow demo",
        }.get(skill_slug, f"Build a small {skill_name} demo project")

        project_focus = {
            "aws": "deployment choices, observability, and infrastructure tradeoffs",
            "docker": "reproducible local setup and build hygiene",
            "kubernetes": "deployment manifests, service exposure, and rollout checks",
            "fastapi": "typed APIs, validation, and a protected endpoint",
            "react": "state, forms, loading states, and clean UX",
            "postgresql": "schema design, indexing, and analytics queries",
            "python": "automation, tests, and practical scripting",
            "java": "package structure, service layers, and basic REST design",
            "javascript": "browser interaction, DOM state, and event handling",
            "langchain": "retrieval flow, citations, and context grounding",
            "pytorch": "model training, evaluation, and experiment notes",
            "tensorflow": "training workflow, evaluation, and reporting",
            "git": "branching, commits, and change documentation",
        }.get(skill_slug, f"a production-style workflow that demonstrates {skill_name}")

        read_source = primary_resource_title or f"official {skill_name} docs"
        steps = [
            f"Review {read_source} and capture the pieces you need for the build.",
            f"Build {project_title.lower()} focused on {project_focus}{f' for {job_label}' if job_label else ''}.",
            "Document the tradeoffs, add a short demo note, and keep the repo easy to explain in interviews.",
        ]

        source_status = (
            "ai_generated_with_verified_learning_resources"
            if source_resources
            else "generated_from_skill_context_no_external_source"
        )

        return {
            "title": project_title,
            "difficulty": "beginner" if skill_slug in {"aws", "docker", "fastapi", "react", "postgresql", "python", "javascript", "git"} else "intermediate",
            "estimated_hours": 6 if skill_slug in {"aws", "docker", "fastapi", "react", "postgresql", "python", "javascript", "git"} else 8,
            "proof_type": "portfolio_project",
            "steps": steps,
            "source_resources": source_resources,
            "resume_bullets": [
                f"Suggested resume bullet: Built a sample {skill_name} project to practice {project_focus} and documented the architecture, tradeoffs, and verification steps.",
                f"Suggested resume bullet: Turned {read_source} into a portfolio-ready demo that clearly shows {skill_name} proficiency.",
            ],
            "github_readme_outline": [
                "Problem statement",
                f"Why {skill_name} was the right tool",
                "Architecture and setup",
                "Deployment or run steps",
                "What I learned and what I would improve",
            ],
            "source_status": source_status,
        }

    def _resume_proof(
        self,
        skill_name: str,
        project_title: str,
        job_context: Optional[dict[str, Any]],
        source_status: str,
    ) -> dict[str, Any]:
        job_label = None
        if job_context:
            job_bits = [job_context.get("title"), job_context.get("company")]
            job_label = " at ".join([bit for bit in job_bits if bit]) or None
        target_phrase = f" for {job_label}" if job_label else ""
        return {
            "before_gap": f"No verified {skill_name} proof is linked yet{target_phrase}.",
            "suggested_bullets": [
                f"Suggested resume bullet: Built and documented {project_title.lower()} to demonstrate {skill_name} on a real portfolio project{target_phrase}.",
                f"Suggested resume bullet: Added measurable notes, screenshots, or code samples that show how the {skill_name} project was verified.",
            ],
            "linkedin_bullets": [
                f"Suggested LinkedIn bullet: Shared a {skill_name} proof project with clear architecture notes and a demo link.",
                f"Suggested LinkedIn bullet: Highlighted a {skill_name} build that closes the gap for the target role{target_phrase}.",
            ],
            "portfolio_description": f"Suggested portfolio blurb: A concise {skill_name} project that shows the learning-to-proof path and why it matters for the role.",
            "source_status": source_status,
        }

    def _interview_proof(self, skill_name: str, project_title: str, source_status: str) -> dict[str, Any]:
        return {
            "talking_points": [
                f"Why did you choose {skill_name} for this project?",
                f"What tradeoffs did you make while building {project_title.lower()}?",
                f"How did you verify the result and what would you improve next?",
                "How would you explain the architecture to a teammate or interviewer?",
            ],
            "sample_answer": f"Suggested interview answer: I used the {skill_name} project to close a real gap, validate the workflow, and turn learning into proof.",
            "source_status": source_status,
        }

    async def _attach_resource_provenance(
        self,
        db: AsyncSession,
        resource_payloads: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for resource in resource_payloads:
            resource_id = resource.get("id")
            if resource_id is None:
                enriched.append(resource)
                continue
            try:
                summary = await self.provenance_service.get_latest_resource_summary(db, resource_id=int(resource_id))
            except Exception as exc:  # pragma: no cover - provenance must not break gap actions
                logger.debug("Gap action provenance lookup skipped for resource_id=%s: %s", resource_id, exc)
                summary = None
            if summary:
                resource = {**resource, "provenance_summary": summary}
            enriched.append(resource)
        return enriched

    async def _attach_resource_outcomes(
        self,
        db: AsyncSession,
        resource_payloads: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for resource in resource_payloads:
            resource_id = resource.get("id")
            if resource_id is None:
                enriched.append(resource)
                continue
            try:
                summary = await self.outcome_service.get_latest_resource_outcome_summary(db, resource_id=int(resource_id))
            except Exception as exc:  # pragma: no cover - outcome lookup must not break gap actions
                logger.debug("Gap action outcome lookup skipped for resource_id=%s: %s", resource_id, exc)
                summary = None
            if summary:
                resource = {**resource, "outcome_summary": summary}
            enriched.append(resource)
        return enriched

    async def build_gap_actions(
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
                    "message": "Provide at least one skill or a valid job_id to build proof actions.",
                },
                "actions": [],
                "provider_health": self.learning_resource_service.provider_health(),
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

        actions: list[dict[str, Any]] = []
        any_verified_sources = False

        for normalized in normalized_skills:
            aggregate = aggregate_by_slug.get(normalized.slug)
            if aggregate is None:
                aggregate = SkillGapAggregate(
                    skill_slug=normalized.slug,
                    skill_name=normalized.display_name or canonical_display_name(normalized.slug),
                    count=1,
                    source_job_ids=[job_context["job_id"]] if job_context and job_context.get("job_id") else [],
                    source_job_titles=[job_context["title"]] if job_context and job_context.get("title") else [],
                    job_match_ids=[],
                    max_match_score=float(job_context.get("match_score") or 0.0) if job_context else 0.0,
                    latest_match_at=None,
                )

            resources = await self.learning_resource_service.ensure_skill_resources(
                db,
                aggregate.skill_slug,
                skill_name=aggregate.skill_name,
                limit=4,
                force_refresh=force_refresh,
            )
            resource_payloads = [self.learning_path_service.resource_service_record(resource) for resource in resources]
            resource_payloads = await self._attach_resource_provenance(db, resource_payloads)
            resource_payloads = await self._attach_resource_outcomes(db, resource_payloads)
            resource_status = "available" if resource_payloads else "not_available"
            source_status = (
                "ai_generated_with_verified_learning_resources"
                if resource_payloads
                else "generated_from_skill_context_no_external_source"
            )
            any_verified_sources = any_verified_sources or bool(resource_payloads)
            resource_scores = [
                {
                    "trust": float(resource.get("trust_score") or 0.0),
                    "relevance": float(resource.get("relevance_score") or 0.0),
                    "freshness": float(resource.get("freshness_score") or 0.0),
                }
                for resource in resource_payloads
                if resource.get("id") is not None
            ]
            if resource_scores:
                avg_trust = sum(item["trust"] for item in resource_scores) / len(resource_scores)
                avg_relevance = sum(item["relevance"] for item in resource_scores) / len(resource_scores)
                avg_freshness = sum(item["freshness"] for item in resource_scores) / len(resource_scores)
            else:
                avg_trust = avg_relevance = avg_freshness = 0.0
            action_score_breakdown = self.provenance_service.build_score_breakdown(
                trust_score=avg_trust,
                relevance_score=avg_relevance,
                freshness_score=avg_freshness,
                verification_status="verified" if resource_payloads else "insufficient_data",
                source_kind="gap_action",
            )

            project_idea = self._template_for_skill(aggregate.skill_slug, aggregate.skill_name, resource_payloads, job_context)
            actions.append(
                {
                    "skill_slug": aggregate.skill_slug,
                    "skill_name": aggregate.skill_name,
                    "count": aggregate.count,
                    "priority": aggregate.priority,
                    "estimated_hours": aggregate.estimated_hours,
                    "reason": aggregate.reason,
                    "source_job_ids": aggregate.source_job_ids,
                    "source_job_titles": aggregate.source_job_titles,
                    "job_match_ids": aggregate.job_match_ids,
                    "resource_status": resource_status,
                    "resource_count": len(resource_payloads),
                    "source_status": source_status,
                    "source_resources": resource_payloads,
                    "project_ideas": [project_idea],
                    "resume_proof": self._resume_proof(aggregate.skill_name, project_idea["title"], job_context, source_status),
                    "interview_proof": self._interview_proof(aggregate.skill_name, project_idea["title"], source_status),
                    "provenance_summary": {
                        "source_entity_type": "gap_action",
                        "source_entity_id": aggregate.skill_slug,
                        "resource_count": len(resource_payloads),
                        "source_status": source_status,
                        "score_breakdown": action_score_breakdown,
                        "score_total": action_score_breakdown["composite_score"],
                        "score_formula": action_score_breakdown["formula"],
                        "confidence": self.provenance_service._confidence_for_score(action_score_breakdown["composite_score"], "success" if resource_payloads else "insufficient_data"),
                        "status": "success" if resource_payloads else "insufficient_data",
                        "recorded_at": datetime.utcnow().isoformat() + "Z",
                        "evidence_count": len(resource_payloads),
                        "explanation": (
                            f"{aggregate.skill_name} proof actions were assembled from "
                            f"{len(resource_payloads)} verified learning resource(s)."
                        ),
                    },
                }
            )

        payload = {
            "status": "ok",
            "user_id": user_id,
            "job_id": job_id,
            "job_context": job_context,
            "cached": False,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "provider_health": self.learning_resource_service.provider_health(),
            "source_status": "verified_resource_supported" if any_verified_sources else "generated_from_skill_context_no_external_source",
            "actions": actions,
        }
        await get_career_event_service().emit_event(
            db,
            event_type="GapActionsRefreshed",
            entity_type="gap_action_set",
            entity_id=",".join(item.slug for item in normalized_skills)[:128],
            source_service="services.learning.gap_action_service",
            user_id=user_id,
            source_table="job_matches" if job_id is not None else None,
            source_id=job_id,
            payload={
                "job_id": job_id,
                "skills": [item.slug for item in normalized_skills],
                "cached": False,
                "source_status": payload["source_status"],
                "provider_health": payload["provider_health"],
                "action_count": len(actions),
            },
            evidence=[
                get_career_event_service().build_evidence_ref(
                    table="job_matches" if job_id is not None else "learning_resources",
                    source_id=job_id if job_id is not None else (normalized_skills[0].slug if normalized_skills else None),
                    note="gap actions generated from verified skill gaps and learning resources",
                    extra={
                        "skills": [item.slug for item in normalized_skills],
                        "job_context": job_context,
                    },
                )
            ],
            provider=(self.learning_resource_service.provider_health() or {}).get("provider"),
            trace_id=f"gap_actions:{job_id or normalized_skills[0].slug}",
        )
        await self._write_cache(cache_key, payload)
        resource_scores = [
            {
                "trust": float(resource.get("trust_score") or 0.0),
                "relevance": float(resource.get("relevance_score") or 0.0),
                "freshness": float(resource.get("freshness_score") or 0.0),
            }
            for action in actions
            for resource in action.get("source_resources", [])
            if resource.get("id") is not None
        ]
        if resource_scores:
            avg_trust = sum(item["trust"] for item in resource_scores) / len(resource_scores)
            avg_relevance = sum(item["relevance"] for item in resource_scores) / len(resource_scores)
            avg_freshness = sum(item["freshness"] for item in resource_scores) / len(resource_scores)
        else:
            avg_trust = avg_relevance = avg_freshness = 0.0
        try:
            await self.provenance_service.record_provenance(
                db,
                provenance_type="gap_actions",
                source_entity_type="gap_action_set",
                source_entity_id=",".join(item.slug for item in normalized_skills)[:128],
                skill_slug=normalized_skills[0].slug,
                skill_name=normalized_skills[0].display_name if normalized_skills else "Gap Actions",
                title=f"Gap actions for {', '.join(item.display_name for item in normalized_skills)}",
                provider=(self.learning_resource_service.provider_health() or {}).get("provider", "learning"),
                source_url=None,
                user_id=user_id,
                job_id=job_id,
                source_table="job_matches" if job_id is not None else None,
                source_pk=job_id,
                trust_score=avg_trust,
                relevance_score=avg_relevance,
                freshness_score=avg_freshness,
                verification_status="verified" if resource_scores else "insufficient_data",
                source_kind="gap_action",
                status="success" if resource_scores else "insufficient_data",
                evidence=[
                    get_career_event_service().build_evidence_ref(
                        table="job_matches" if job_id is not None else "learning_resources",
                        source_id=job_id if job_id is not None else (normalized_skills[0].slug if normalized_skills else None),
                        note="Gap actions generated from verified learning resources and proof-building templates",
                        extra={
                            "skills": [item.slug for item in normalized_skills],
                            "job_context": job_context,
                        },
                    )
                ],
                source_context={
                    "action_count": len(actions),
                    "resource_count": sum(len(action.get("source_resources", [])) for action in actions),
                    "source_status": payload["source_status"],
                },
            )
        except Exception as exc:  # pragma: no cover - provenance must not break gap actions
            logger.debug("Failed to store gap action provenance: %s", exc)
        return payload


_SERVICE: Optional[LearningGapActionService] = None


def get_learning_gap_action_service() -> LearningGapActionService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = LearningGapActionService()
    return _SERVICE
