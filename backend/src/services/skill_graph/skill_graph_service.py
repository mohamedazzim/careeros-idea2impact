"""CareerOS M4 skill graph import and inspection service."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import logging
import re
import uuid
from typing import Any, Iterable, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import Job, JobMatch
from src.models.learning import LearningActivityEvent, LearningResource, LearningSession, ResourceFeedback, ResourceOutcome, ResourceProvenanceRecord
from src.models.roadmap import Roadmap, RoadmapGoal, RoadmapTask
from src.models.resume import Resume, ResumeChunk, ResumeVersion
from src.models.skill_graph import (
    SkillGraphAlias,
    SkillGraphEdge,
    SkillGraphEvidence,
    SkillGraphImportRun,
    SkillGraphNode,
    UserSkillState,
)
from src.schemas.skill_graph import SkillGraphImportRequest
from src.services.events import get_career_event_service
from src.services.learning.skill_normalizer import canonical_display_name, normalize_skill, normalize_skill_list

logger = logging.getLogger(__name__)


DEFAULT_SKILL_TERMS = (
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "FastAPI",
    "React",
    "PostgreSQL",
    "Docker",
    "Kubernetes",
    "AWS",
    "Git",
    "GitHub",
    "CI/CD",
    "Machine Learning",
    "Deep Learning",
    "PyTorch",
    "TensorFlow",
    "LangChain",
    "Node.js",
    "C++",
    "C#",
)


def _now() -> datetime:
    return datetime.utcnow()


def _normalize_text(value: str) -> str:
    cleaned = re.sub(r"[\s/_-]+", " ", value.strip().lower())
    cleaned = re.sub(r"[^a-z0-9.+# ]+", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _hash_uid(*parts: object) -> str:
    raw = "||".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _source_key(source_entity_type: str, source_entity_id: str) -> tuple[str, str]:
    return (source_entity_type, source_entity_id)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _flatten_strings(value: Any, *, max_depth: int = 4, depth: int = 0) -> list[str]:
    if value is None or depth > max_depth:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        items: list[str] = []
        for child in value.values():
            items.extend(_flatten_strings(child, max_depth=max_depth, depth=depth + 1))
        return items
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for child in value:
            items.extend(_flatten_strings(child, max_depth=max_depth, depth=depth + 1))
        return items
    text = str(value).strip()
    return [text] if text else []


@dataclass(slots=True)
class SkillVocabularyEntry:
    skill_slug: str
    skill_name: str
    aliases: set[str] = field(default_factory=set)
    categories: set[str] = field(default_factory=set)


@dataclass(slots=True)
class SkillEvidenceCandidate:
    skill_slug: str
    skill_name: str
    raw_value: str
    source_entity_type: str
    source_entity_id: str
    source_table: Optional[str]
    source_pk: Optional[str]
    source_field: str
    source_title: Optional[str]
    source_url: Optional[str]
    provider: Optional[str]
    evidence_kind: str
    trust_score: float
    relevance_score: float
    freshness_score: float
    confidence: str
    status: str
    observed_at: datetime
    user_id: Optional[str] = None
    source_group: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_value(self) -> str:
        return _normalize_text(self.raw_value or self.skill_name or self.skill_slug)


@dataclass(slots=True)
class SkillAggregate:
    skill_slug: str
    skill_name: str
    category: str = "skill"
    evidence_count: int = 0
    source_keys: set[tuple[str, str]] = field(default_factory=set)
    source_types: set[str] = field(default_factory=set)
    user_ids: set[str] = field(default_factory=set)
    trust_scores: list[float] = field(default_factory=list)
    relevance_scores: list[float] = field(default_factory=list)
    freshness_scores: list[float] = field(default_factory=list)
    observed_at: Optional[datetime] = None
    demand_count: int = 0
    supply_count: int = 0
    learning_signal_count: int = 0
    resume_signal_count: int = 0
    aliases: set[str] = field(default_factory=set)


@dataclass(slots=True)
class UserSkillAggregate:
    user_id: str
    skill_slug: str
    skill_name: str
    category: str = "skill"
    evidence_count: int = 0
    demand_count: int = 0
    supply_count: int = 0
    learning_signal_count: int = 0
    resume_signal_count: int = 0
    started_count: int = 0
    completion_count: int = 0
    feedback_count: int = 0
    rating_values: list[float] = field(default_factory=list)
    last_activity_at: Optional[datetime] = None
    source_keys: set[tuple[str, str, str]] = field(default_factory=set)
    evidence_summary: dict[str, Any] = field(default_factory=dict)
    recommended_action: Optional[str] = None
    aliases: set[str] = field(default_factory=set)


@dataclass(slots=True)
class EdgeAggregate:
    source_skill_slug: str
    target_skill_slug: str
    edge_type: str
    source_entity_type: str
    source_entity_id: str
    source_table: Optional[str]
    source_pk: Optional[str]
    source_title: Optional[str]
    provider: Optional[str]
    weight: float = 0.0
    evidence_count: int = 0
    observed_at: Optional[datetime] = None
    raw_titles: set[str] = field(default_factory=set)
    evidence_kinds: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)


def _confidence_band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


class SkillGraphService:
    """Import and query service for the CareerOS skill graph."""

    def __init__(self) -> None:
        self._fallback_terms = tuple(DEFAULT_SKILL_TERMS)

    # ------------------------------------------------------------------
    # Pure scoring helpers
    # ------------------------------------------------------------------
    @staticmethod
    def score_node_status(*, evidence_count: int, source_count: int, demand_count: int, supply_count: int, learning_signal_count: int) -> tuple[str, float]:
        raw_score = min(
            1.0,
            (evidence_count * 0.12)
            + (source_count * 0.10)
            + (demand_count * 0.06)
            + (supply_count * 0.15)
            + (learning_signal_count * 0.10),
        )
        if supply_count == 0 and evidence_count <= 1:
            return "insufficient_data", round(raw_score, 4)
        if supply_count >= 3 and learning_signal_count >= 1:
            return "validated", round(max(raw_score, 0.78), 4)
        if supply_count >= 1 and (learning_signal_count >= 1 or demand_count >= 1):
            return "growing", round(max(raw_score, 0.62), 4)
        if evidence_count >= 2:
            return "observed", round(max(raw_score, 0.45), 4)
        return "insufficient_data", round(raw_score, 4)

    @staticmethod
    def score_user_status(
        *,
        demand_count: int,
        supply_count: int,
        learning_signal_count: int,
        resume_signal_count: int,
        started_count: int,
        completion_count: int,
        feedback_count: int,
    ) -> tuple[str, float, str]:
        raw_score = min(
            1.0,
            (demand_count * 0.05)
            + (supply_count * 0.18)
            + (learning_signal_count * 0.16)
            + (resume_signal_count * 0.08)
            + (started_count * 0.08)
            + (completion_count * 0.12)
            + (feedback_count * 0.10),
        )
        if supply_count == 0 and (demand_count > 0 or learning_signal_count > 0 or resume_signal_count > 0):
            return "insufficient_data", round(raw_score, 4), "Add one learning session or proof artifact to ground this skill."
        if completion_count >= 2 and feedback_count >= 1:
            return "validated", round(max(raw_score, 0.78), 4), "Keep the proof fresh with one more outcome or artifact."
        if supply_count >= 1 and (learning_signal_count >= 1 or resume_signal_count >= 1):
            return "growing", round(max(raw_score, 0.62), 4), "Keep building evidence and capture an outcome."
        if supply_count >= 1:
            return "observed", round(max(raw_score, 0.45), 4), "Add a learning session or feedback to strengthen the signal."
        return "insufficient_data", round(raw_score, 4), "Add evidence before treating this skill as established."

    @staticmethod
    def _category_for_skill(skill_slug: str) -> str:
        mapping = {
            "python": "language",
            "java": "language",
            "javascript": "language",
            "typescript": "language",
            "cpp": "language",
            "c-sharp": "language",
            "fastapi": "framework",
            "react": "framework",
            "tensorflow": "framework",
            "pytorch": "framework",
            "langchain": "framework",
            "docker": "platform",
            "kubernetes": "platform",
            "aws": "platform",
            "postgresql": "database",
            "git": "tool",
            "github": "tool",
            "ci-cd": "practice",
        }
        return mapping.get(skill_slug, "skill")

    @staticmethod
    def _source_trust_weight(source_type: str) -> tuple[float, float, float]:
        if source_type in {"resource_outcome", "resource_feedback", "learning_session", "learning_activity"}:
            return 0.92, 0.84, 0.90
        if source_type in {"resume_version", "resume_chunk"}:
            return 0.84, 0.78, 0.72
        if source_type in {"learning_resource", "resource_provenance"}:
            return 0.88, 0.86, 0.80
        if source_type in {"job", "job_match"}:
            return 0.90, 0.92, 0.58
        if source_type in {"roadmap_task", "roadmap_goal"}:
            return 0.72, 0.74, 0.62
        return 0.70, 0.70, 0.60

    def _make_vocabulary(self) -> dict[str, SkillVocabularyEntry]:
        vocabulary: dict[str, SkillVocabularyEntry] = {}
        for term in self._fallback_terms:
            normalized = normalize_skill(term)
            if not normalized.slug:
                continue
            entry = vocabulary.setdefault(normalized.slug, SkillVocabularyEntry(skill_slug=normalized.slug, skill_name=normalized.display_name or canonical_display_name(normalized.slug)))
            entry.aliases.add(_normalize_text(term))
            entry.aliases.add(_normalize_text(normalized.display_name or term))
            entry.categories.add(self._category_for_skill(normalized.slug))
        return vocabulary

    @staticmethod
    def _emit_alias_text(raw_value: str, skill_name: str) -> list[str]:
        aliases = {_normalize_text(raw_value), _normalize_text(skill_name)}
        return [alias for alias in aliases if alias]

    def _attach_vocabulary_term(
        self,
        vocabulary: dict[str, SkillVocabularyEntry],
        normalized_skill,
        *,
        raw_value: str,
    ) -> None:
        if not normalized_skill.slug:
            return
        entry = vocabulary.setdefault(
            normalized_skill.slug,
            SkillVocabularyEntry(
                skill_slug=normalized_skill.slug,
                skill_name=normalized_skill.display_name or canonical_display_name(normalized_skill.slug),
            ),
        )
        entry.aliases.add(_normalize_text(raw_value))
        entry.aliases.add(_normalize_text(normalized_skill.display_name or raw_value))
        for alias in getattr(normalized_skill, "aliases", ()) or ():
            alias_text = _normalize_text(str(alias))
            if alias_text:
                entry.aliases.add(alias_text)
        entry.categories.add(self._category_for_skill(normalized_skill.slug))

    def _match_text_to_vocabulary(self, text: str, vocabulary: dict[str, SkillVocabularyEntry]) -> list[tuple[str, str]]:
        simplified_text = _normalize_text(text)
        if not simplified_text:
            return []
        matches: list[tuple[str, str]] = []
        for slug, entry in vocabulary.items():
            for alias in sorted(entry.aliases, key=len, reverse=True):
                if not alias:
                    continue
                if alias in simplified_text:
                    matches.append((slug, entry.skill_name))
                    break
        return matches

    @staticmethod
    def _co_occurrence_pairs(skill_slugs: Iterable[str]) -> list[tuple[str, str]]:
        unique = sorted({slug for slug in skill_slugs if slug})
        pairs: list[tuple[str, str]] = []
        for idx, left in enumerate(unique):
            for right in unique[idx + 1 :]:
                if left != right:
                    pairs.append((left, right))
        return pairs

    @staticmethod
    def _event_kind_for_source(source_entity_type: str, source_field: str, source_table: Optional[str]) -> str:
        if source_entity_type == "job":
            return "job_requirement"
        if source_entity_type == "job_match":
            return "job_match_gap"
        if source_entity_type in {"resume", "resume_version", "resume_chunk"}:
            return "resume_chunk"
        if source_entity_type in {"learning_resource", "resource_provenance"}:
            return "learning_resource"
        if source_entity_type in {"learning_session", "resource_feedback", "resource_outcome", "learning_activity"}:
            return "learning_signal"
        if source_entity_type in {"roadmap", "roadmap_goal", "roadmap_task"}:
            return "roadmap_task"
        return source_table or source_entity_type or source_field

    @staticmethod
    def _source_visibility(source_entity_type: str) -> tuple[int, int, int]:
        if source_entity_type in {"learning_session", "resource_feedback", "resource_outcome", "learning_activity"}:
            return 0, 1, 1
        if source_entity_type in {"resume", "resume_version", "resume_chunk"}:
            return 0, 1, 0
        if source_entity_type in {"job", "job_match"}:
            return 1, 0, 0
        if source_entity_type in {"roadmap", "roadmap_goal", "roadmap_task"}:
            return 0, 0, 1
        if source_entity_type in {"learning_resource", "resource_provenance"}:
            return 0, 1, 0
        return 0, 0, 0

    # ------------------------------------------------------------------
    # Source collection
    # ------------------------------------------------------------------
    async def _collect_structured_observations(
        self,
        db: AsyncSession,
    ) -> tuple[list[SkillEvidenceCandidate], dict[str, SkillVocabularyEntry], dict[str, int]]:
        observations: list[SkillEvidenceCandidate] = []
        vocabulary = self._make_vocabulary()
        source_counts: Counter[str] = Counter()

        async def add_observation(candidate: SkillEvidenceCandidate) -> None:
            observations.append(candidate)
            source_counts[candidate.source_entity_type] += 1
            self._attach_vocabulary_term(vocabulary, normalize_skill(candidate.skill_name), raw_value=candidate.skill_name)
            if candidate.raw_value and len(candidate.raw_value) <= 120:
                self._attach_vocabulary_term(vocabulary, normalize_skill(candidate.raw_value), raw_value=candidate.raw_value)
            if candidate.skill_slug and candidate.skill_slug not in vocabulary:
                vocabulary[candidate.skill_slug] = SkillVocabularyEntry(
                    skill_slug=candidate.skill_slug,
                    skill_name=candidate.skill_name,
                    aliases={_normalize_text(candidate.skill_name), _normalize_text(candidate.raw_value) if candidate.raw_value and len(candidate.raw_value) <= 120 else ""},
                    categories={self._category_for_skill(candidate.skill_slug)},
                )

        # Jobs and job matches
        job_query = (
            select(Job, JobMatch)
            .join(JobMatch, JobMatch.job_id == Job.id)
            .where(Job.deleted_at.is_(None), JobMatch.deleted_at.is_(None))
            .order_by(JobMatch.created_at.desc(), JobMatch.id.desc())
        )
        job_result = await db.execute(job_query)
        latest_job_matches: dict[tuple[str, int], tuple[JobMatch, Job]] = {}
        for match, job in job_result.all():
            latest_job_matches[(match.user_id, job.id)] = (match, job)

        for match, job in latest_job_matches.values():
            raw_job_skills: list[object] = []
            if isinstance(job.skills_required, list):
                raw_job_skills.extend(job.skills_required)
            if isinstance(match.gaps, list):
                raw_job_skills.extend(match.gaps)
            if isinstance(match.match_details, dict):
                raw_job_skills.extend(match.match_details.get("missing_skills") or [])
                raw_job_skills.extend(match.match_details.get("job_extraction", {}).get("skills", []) or [])
            for normalized in normalize_skill_list(raw_job_skills):
                observed_at = getattr(match, "created_at", None) or getattr(job, "created_at", None) or _now()
                await add_observation(
                    SkillEvidenceCandidate(
                        skill_slug=normalized.slug,
                        skill_name=normalized.display_name or canonical_display_name(normalized.slug),
                        raw_value=normalized.aliases[0] if getattr(normalized, "aliases", None) else normalized.display_name or normalized.slug,
                        source_entity_type="job_match",
                        source_entity_id=str(match.id),
                        source_table="job_matches",
                        source_pk=str(match.id),
                        source_field="gaps",
                        source_title=job.title,
                        source_url=job.apply_url,
                        provider=job.source_provider or job.source or "jobs",
                        evidence_kind="job_match_gap",
                        trust_score=0.90,
                        relevance_score=min(1.0, float(match.overall_score or 0.0) / 100.0) if match.overall_score is not None else 0.78,
                        freshness_score=0.58,
                        confidence=_confidence_band(0.58),
                        status="success",
                        observed_at=observed_at if isinstance(observed_at, datetime) else _now(),
                        user_id=match.user_id,
                        source_group=f"job_match:{match.id}",
                        metadata={
                            "job_id": job.id,
                            "job_title": job.title,
                            "company": job.company,
                            "match_score": float(match.overall_score or 0.0) if match.overall_score is not None else None,
                        },
                    )
                )

            for normalized in normalize_skill_list(job.skills_required or []):
                observed_at = getattr(job, "created_at", None) or _now()
                await add_observation(
                    SkillEvidenceCandidate(
                        skill_slug=normalized.slug,
                        skill_name=normalized.display_name or canonical_display_name(normalized.slug),
                        raw_value=normalized.aliases[0] if getattr(normalized, "aliases", None) else normalized.display_name or normalized.slug,
                        source_entity_type="job",
                        source_entity_id=str(job.id),
                        source_table="jobs",
                        source_pk=str(job.id),
                        source_field="skills_required",
                        source_title=job.title,
                        source_url=job.apply_url,
                        provider=job.source_provider or job.source or "jobs",
                        evidence_kind="job_requirement",
                        trust_score=0.92,
                        relevance_score=0.90,
                        freshness_score=0.58,
                        confidence=_confidence_band(0.58),
                        status="success",
                        observed_at=observed_at if isinstance(observed_at, datetime) else _now(),
                        user_id=None,
                        source_group=f"job:{job.id}",
                        metadata={
                            "company": job.company,
                            "employment_type": job.employment_type,
                            "source_url": job.source_url,
                            "apply_url": job.apply_url,
                        },
                    )
                )

        # Learning resources and provenance
        learning_resources = await db.execute(select(LearningResource))
        for resource in learning_resources.scalars().all():
            observed_at = resource.last_verified_at or resource.created_at or _now()
            await add_observation(
                SkillEvidenceCandidate(
                    skill_slug=resource.skill_slug,
                    skill_name=resource.skill_name,
                    raw_value=resource.skill_name or resource.skill_slug,
                    source_entity_type="learning_resource",
                    source_entity_id=str(resource.id),
                    source_table="learning_resources",
                    source_pk=str(resource.id),
                    source_field="skill_slug",
                    source_title=resource.title,
                    source_url=resource.source_url,
                    provider=resource.provider,
                    evidence_kind="learning_resource",
                    trust_score=float(resource.trust_score or 0.0),
                    relevance_score=float(resource.relevance_score or 0.0),
                    freshness_score=float(resource.freshness_score or 0.0),
                    confidence="high" if resource.last_verified_at else "medium",
                    status="success",
                    observed_at=observed_at if isinstance(observed_at, datetime) else _now(),
                    user_id=None,
                    source_group=f"learning_resource:{resource.id}",
                    metadata={
                        "source_type": resource.source_type,
                        "channel_name": resource.channel_name,
                        "is_free": resource.is_free,
                        "language": resource.language,
                        "verification_status": (resource.metadata_ or {}).get("verification_status"),
                    },
                )
            )

        provenance_rows = await db.execute(select(ResourceProvenanceRecord))
        for record in provenance_rows.scalars().all():
            if not record.skill_slug:
                continue
            observed_at = record.recorded_at or record.created_at or _now()
            await add_observation(
                SkillEvidenceCandidate(
                    skill_slug=record.skill_slug,
                    skill_name=record.skill_name,
                    raw_value=record.title or record.skill_name,
                    source_entity_type="resource_provenance",
                    source_entity_id=record.provenance_uid,
                    source_table="learning_resource_provenance_records",
                    source_pk=str(record.id),
                    source_field="skill_slug",
                    source_title=record.title,
                    source_url=record.source_url,
                    provider=record.provider,
                    evidence_kind=record.provenance_type,
                    trust_score=float(record.trust_score or 0.0) / 100.0 if record.trust_score and record.trust_score > 1 else float(record.trust_score or 0.0),
                    relevance_score=float(record.relevance_score or 0.0) / 100.0 if record.relevance_score and record.relevance_score > 1 else float(record.relevance_score or 0.0),
                    freshness_score=float(record.freshness_score or 0.0) / 100.0 if record.freshness_score and record.freshness_score > 1 else float(record.freshness_score or 0.0),
                    confidence=record.confidence or "medium",
                    status=record.status or "success",
                    observed_at=observed_at if isinstance(observed_at, datetime) else _now(),
                    user_id=record.user_id,
                    source_group=f"resource_provenance:{record.provenance_uid}",
                    metadata={
                        "score_total": record.score_total,
                        "score_breakdown": record.score_breakdown or {},
                        "source_entity_type": record.source_entity_type,
                        "source_entity_id": record.source_entity_id,
                    },
                )
            )

        # Learning outcomes and activity
        session_rows = await db.execute(select(LearningSession))
        for session in session_rows.scalars().all():
            observed_at = session.last_activity_at or session.started_at or session.created_at or _now()
            evidence_kind = f"learning_session_{session.status}"
            await add_observation(
                SkillEvidenceCandidate(
                    skill_slug=session.skill_slug,
                    skill_name=canonical_display_name(session.skill_slug),
                    raw_value=session.skill_slug,
                    source_entity_type="learning_session",
                    source_entity_id=session.session_uid,
                    source_table="learning_sessions",
                    source_pk=str(session.id),
                    source_field="skill_slug",
                    source_title=None,
                    source_url=session.external_resource_url,
                    provider="learning",
                    evidence_kind=evidence_kind,
                    trust_score=0.92 if session.status in {"completed", "in_progress"} else 0.82,
                    relevance_score=0.80,
                    freshness_score=0.88,
                    confidence="high" if session.status == "completed" else "medium",
                    status="success",
                    observed_at=observed_at if isinstance(observed_at, datetime) else _now(),
                    user_id=session.user_id,
                    source_group=f"learning_session:{session.session_uid}",
                    metadata={
                        "status": session.status,
                        "completion_percentage": float(session.completion_percentage or 0.0),
                        "duration_seconds": session.duration_seconds,
                        "resource_id": session.resource_id,
                        "path_id": session.path_id,
                    },
                )
            )

        feedback_rows = await db.execute(select(ResourceFeedback))
        for feedback in feedback_rows.scalars().all():
            observed_at = feedback.created_at or _now()
            await add_observation(
                SkillEvidenceCandidate(
                    skill_slug=feedback.skill_slug,
                    skill_name=canonical_display_name(feedback.skill_slug),
                    raw_value=feedback.comment or feedback.skill_slug,
                    source_entity_type="resource_feedback",
                    source_entity_id=feedback.feedback_uid,
                    source_table="resource_feedback",
                    source_pk=str(feedback.id),
                    source_field="skill_slug",
                    source_title=None,
                    source_url=None,
                    provider="learning",
                    evidence_kind="resource_feedback",
                    trust_score=0.95 if feedback.would_recommend else 0.88,
                    relevance_score=min(1.0, float(feedback.helpfulness_score or feedback.rating or 0.0) / 5.0) if (feedback.helpfulness_score or feedback.rating) else 0.75,
                    freshness_score=0.88,
                    confidence="high" if feedback.rating and feedback.rating >= 4 else "medium",
                    status="success",
                    observed_at=observed_at if isinstance(observed_at, datetime) else _now(),
                    user_id=feedback.user_id,
                    source_group=f"resource_feedback:{feedback.feedback_uid}",
                    metadata={
                        "rating": feedback.rating,
                        "difficulty": feedback.difficulty,
                        "would_recommend": feedback.would_recommend,
                        "outcome_tag": feedback.outcome_tag,
                        "session_uid": feedback.session_uid,
                    },
                )
            )

        outcome_rows = await db.execute(select(ResourceOutcome))
        for outcome in outcome_rows.scalars().all():
            observed_at = outcome.last_calculated_at or outcome.created_at or _now()
            confidence = "high" if outcome.status == "sufficient_data" else "low"
            await add_observation(
                SkillEvidenceCandidate(
                    skill_slug=outcome.skill_slug,
                    skill_name=canonical_display_name(outcome.skill_slug),
                    raw_value=outcome.skill_slug,
                    source_entity_type="resource_outcome",
                    source_entity_id=str(outcome.id),
                    source_table="resource_outcomes",
                    source_pk=str(outcome.id),
                    source_field="skill_slug",
                    source_title=None,
                    source_url=None,
                    provider=outcome.provider,
                    evidence_kind="resource_outcome",
                    trust_score=min(1.0, float(outcome.average_rating or 0.0) / 5.0) if outcome.average_rating is not None else 0.78,
                    relevance_score=min(1.0, float(outcome.completion_rate or 0.0)) if outcome.completion_rate is not None else 0.70,
                    freshness_score=0.88,
                    confidence=confidence,
                    status=outcome.status,
                    observed_at=observed_at if isinstance(observed_at, datetime) else _now(),
                    user_id=None,
                    source_group=f"resource_outcome:{outcome.id}",
                    metadata={
                        "completion_count": outcome.completion_count,
                        "started_count": outcome.started_count,
                        "feedback_count": outcome.feedback_count,
                        "average_rating": outcome.average_rating,
                    },
                )
            )

        activity_rows = await db.execute(select(LearningActivityEvent))
        for activity in activity_rows.scalars().all():
            observed_at = activity.event_time or activity.created_at or _now()
            await add_observation(
                SkillEvidenceCandidate(
                    skill_slug=activity.skill_slug,
                    skill_name=canonical_display_name(activity.skill_slug),
                    raw_value=activity.event_type,
                    source_entity_type="learning_activity",
                    source_entity_id=activity.activity_uid,
                    source_table="learning_activity_events",
                    source_pk=str(activity.id),
                    source_field="skill_slug",
                    source_title=None,
                    source_url=None,
                    provider="learning",
                    evidence_kind=activity.event_type,
                    trust_score=0.88,
                    relevance_score=0.76,
                    freshness_score=0.88,
                    confidence="medium",
                    status="success",
                    observed_at=observed_at if isinstance(observed_at, datetime) else _now(),
                    user_id=activity.user_id,
                    source_group=f"learning_activity:{activity.activity_uid}",
                    metadata={
                        "event_type": activity.event_type,
                        "session_uid": activity.session_uid,
                        "path_id": activity.path_id,
                        "path_item_id": activity.path_item_id,
                        "job_id": activity.job_id,
                    },
                )
            )

        return observations, vocabulary, dict(source_counts)

    async def _collect_text_observations(
        self,
        db: AsyncSession,
        vocabulary: dict[str, SkillVocabularyEntry],
    ) -> tuple[list[SkillEvidenceCandidate], dict[str, int]]:
        observations: list[SkillEvidenceCandidate] = []
        source_counts: Counter[str] = Counter()

        async def add_text_observation(candidate: SkillEvidenceCandidate) -> None:
            observations.append(candidate)
            source_counts[candidate.source_entity_type] += 1
            self._attach_vocabulary_term(vocabulary, normalize_skill(candidate.skill_name), raw_value=candidate.skill_name)

        resumes_result = await db.execute(select(Resume).where(Resume.deleted_at.is_(None)))
        resumes = resumes_result.scalars().all()
        for resume in resumes:
            versions_result = await db.execute(select(ResumeVersion).where(ResumeVersion.resume_id == resume.id, ResumeVersion.deleted_at.is_(None)))
            versions = versions_result.scalars().all()
            if not versions:
                continue
            latest_version = sorted(versions, key=lambda item: (item.created_at or _now(), item.version_num), reverse=True)[0]
            chunk_result = await db.execute(select(ResumeChunk).where(ResumeChunk.version_id == latest_version.id, ResumeChunk.deleted_at.is_(None)))
            chunk_rows = chunk_result.scalars().all()
            chunk_texts = [chunk.content for chunk in sorted(chunk_rows, key=lambda item: item.chunk_index)]
            normalized_content_texts = _flatten_strings(latest_version.normalized_content)
            text_blobs = chunk_texts + normalized_content_texts
            for blob_index, blob in enumerate(text_blobs):
                matched = self._match_text_to_vocabulary(blob, vocabulary)
                if not matched:
                    continue
                for skill_slug, skill_name in matched:
                    await add_text_observation(
                        SkillEvidenceCandidate(
                            skill_slug=skill_slug,
                            skill_name=skill_name,
                            raw_value=blob,
                            source_entity_type="resume_chunk",
                            source_entity_id=f"{resume.id}:{latest_version.id}:{blob_index}",
                            source_table="resume_chunks",
                            source_pk=str(latest_version.id),
                            source_field="content",
                            source_title=resume.filename,
                            source_url=None,
                            provider="resume",
                            evidence_kind="resume_chunk",
                            trust_score=0.84,
                            relevance_score=0.82,
                            freshness_score=0.70,
                            confidence="medium",
                            status="success",
                            observed_at=latest_version.created_at or resume.created_at or _now(),
                            user_id=resume.user_id,
                            source_group=f"resume:{resume.id}",
                            metadata={
                                "filename": resume.filename,
                                "version_id": latest_version.id,
                                "chunk_count": len(chunk_rows),
                            },
                        )
                    )

        roadmaps_result = await db.execute(select(Roadmap).where(Roadmap.deleted_at.is_(None)))
        roadmaps = roadmaps_result.scalars().all()
        for roadmap in roadmaps:
            goals_result = await db.execute(select(RoadmapGoal).where(RoadmapGoal.roadmap_id == roadmap.id, RoadmapGoal.deleted_at.is_(None)))
            goals = goals_result.scalars().all()
            for goal in goals:
                task_result = await db.execute(select(RoadmapTask).where(RoadmapTask.goal_id == goal.id, RoadmapTask.deleted_at.is_(None)))
                tasks = task_result.scalars().all()
                for task in tasks:
                    text = " ".join(part for part in [roadmap.title, goal.title, task.title, task.description or ""] if part)
                    matched = self._match_text_to_vocabulary(text, vocabulary)
                    if not matched:
                        continue
                    for skill_slug, skill_name in matched:
                        await add_text_observation(
                            SkillEvidenceCandidate(
                                skill_slug=skill_slug,
                                skill_name=skill_name,
                                raw_value=text,
                                source_entity_type="roadmap_task",
                                source_entity_id=task.task_uid,
                                source_table="roadmap_tasks",
                                source_pk=str(task.id),
                                source_field="title_description",
                                source_title=task.title,
                                source_url=None,
                                provider="roadmap",
                                evidence_kind="roadmap_task",
                                trust_score=0.70,
                                relevance_score=0.72,
                                freshness_score=0.68,
                                confidence="medium",
                                status="success",
                                observed_at=task.created_at or goal.created_at or roadmap.created_at or _now(),
                                user_id=roadmap.user_id,
                                source_group=f"roadmap_task:{task.task_uid}",
                                metadata={
                                    "roadmap_uid": roadmap.roadmap_uid,
                                    "roadmap_title": roadmap.title,
                                    "goal_title": goal.title,
                                    "task_completed": bool(task.completed),
                                },
                            )
                        )

        return observations, dict(source_counts)

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------
    def _aggregate_nodes(
        self,
        structured_observations: list[SkillEvidenceCandidate],
        text_observations: list[SkillEvidenceCandidate],
    ) -> dict[str, SkillAggregate]:
        aggregates: dict[str, SkillAggregate] = {}
        for candidate in [*structured_observations, *text_observations]:
            bucket = aggregates.setdefault(
                candidate.skill_slug,
                SkillAggregate(
                    skill_slug=candidate.skill_slug,
                    skill_name=candidate.skill_name or canonical_display_name(candidate.skill_slug),
                    category=self._category_for_skill(candidate.skill_slug),
                ),
            )
            bucket.evidence_count += 1
            bucket.source_keys.add(_source_key(candidate.source_entity_type, candidate.source_entity_id))
            bucket.source_types.add(candidate.source_entity_type)
            if candidate.user_id:
                bucket.user_ids.add(candidate.user_id)
            bucket.trust_scores.append(candidate.trust_score)
            bucket.relevance_scores.append(candidate.relevance_score)
            bucket.freshness_scores.append(candidate.freshness_score)
            bucket.aliases.add(candidate.normalized_value)
            if candidate.observed_at and (bucket.observed_at is None or candidate.observed_at > bucket.observed_at):
                bucket.observed_at = candidate.observed_at
            if candidate.source_entity_type in {"job", "job_match"}:
                bucket.demand_count += 1
            elif candidate.source_entity_type in {"resume_chunk"}:
                bucket.supply_count += 1
                bucket.resume_signal_count += 1
            elif candidate.source_entity_type in {"learning_session", "resource_feedback", "resource_outcome"}:
                bucket.supply_count += 1
                bucket.learning_signal_count += 1
            elif candidate.source_entity_type in {"learning_activity"}:
                bucket.learning_signal_count += 1
            elif candidate.source_entity_type in {"roadmap_task", "roadmap_goal", "roadmap"}:
                bucket.learning_signal_count += 1
            elif candidate.source_entity_type in {"learning_resource", "resource_provenance"}:
                bucket.supply_count += 1

        return aggregates

    def _aggregate_user_states(self, candidates: list[SkillEvidenceCandidate]) -> dict[tuple[str, str], UserSkillAggregate]:
        aggregates: dict[tuple[str, str], UserSkillAggregate] = {}
        for candidate in candidates:
            if not candidate.user_id:
                continue
            key = (candidate.user_id, candidate.skill_slug)
            bucket = aggregates.setdefault(
                key,
                UserSkillAggregate(
                    user_id=candidate.user_id,
                    skill_slug=candidate.skill_slug,
                    skill_name=candidate.skill_name or canonical_display_name(candidate.skill_slug),
                    category=self._category_for_skill(candidate.skill_slug),
                ),
            )
            bucket.evidence_count += 1
            bucket.source_keys.add((candidate.source_entity_type, candidate.source_entity_id, candidate.source_field))
            bucket.aliases.add(candidate.normalized_value)
            if candidate.observed_at and (bucket.last_activity_at is None or candidate.observed_at > bucket.last_activity_at):
                bucket.last_activity_at = candidate.observed_at

            if candidate.source_entity_type in {"job_match"}:
                bucket.demand_count += 1
            elif candidate.source_entity_type in {"resume_chunk"}:
                bucket.supply_count += 1
                bucket.resume_signal_count += 1
            elif candidate.source_entity_type in {"learning_session"}:
                bucket.learning_signal_count += 1
                if candidate.status == "success" and candidate.metadata.get("status") == "completed":
                    bucket.completion_count += 1
                if candidate.metadata.get("status") == "started":
                    bucket.started_count += 1
            elif candidate.source_entity_type in {"resource_feedback"}:
                bucket.learning_signal_count += 1
                bucket.supply_count += 1
                bucket.feedback_count += 1
                rating = candidate.metadata.get("rating")
                if rating is not None:
                    try:
                        bucket.rating_values.append(float(rating))
                    except (TypeError, ValueError):
                        pass
            elif candidate.source_entity_type in {"resource_outcome"}:
                bucket.learning_signal_count += 1
                if candidate.metadata.get("completion_count"):
                    bucket.completion_count += int(candidate.metadata.get("completion_count") or 0)
                if candidate.metadata.get("started_count"):
                    bucket.started_count += int(candidate.metadata.get("started_count") or 0)
                if candidate.metadata.get("feedback_count"):
                    bucket.feedback_count += int(candidate.metadata.get("feedback_count") or 0)
                bucket.supply_count += 1
            elif candidate.source_entity_type in {"learning_activity"}:
                bucket.learning_signal_count += 1
            elif candidate.source_entity_type in {"roadmap_task", "roadmap_goal", "roadmap"}:
                bucket.learning_signal_count += 1
            elif candidate.source_entity_type in {"learning_resource", "resource_provenance"}:
                bucket.learning_signal_count += 1

        for bucket in aggregates.values():
            status, confidence, recommendation = self.score_user_status(
                demand_count=bucket.demand_count,
                supply_count=bucket.supply_count,
                learning_signal_count=bucket.learning_signal_count,
                resume_signal_count=bucket.resume_signal_count,
                started_count=bucket.started_count,
                completion_count=bucket.completion_count,
                feedback_count=bucket.feedback_count,
            )
            bucket.evidence_summary = {
                "demand_count": bucket.demand_count,
                "supply_count": bucket.supply_count,
                "learning_signal_count": bucket.learning_signal_count,
                "resume_signal_count": bucket.resume_signal_count,
                "started_count": bucket.started_count,
                "completion_count": bucket.completion_count,
                "feedback_count": bucket.feedback_count,
            }
            bucket.recommended_action = recommendation
            bucket.evidence_count = len(bucket.source_keys)
            bucket.aliases = {alias for alias in bucket.aliases if alias}
            bucket.category = bucket.category or "skill"
        return aggregates

    def _aggregate_edges(self, observations: list[SkillEvidenceCandidate]) -> dict[tuple[str, str, str, str, str], EdgeAggregate]:
        grouped: dict[tuple[str, str], list[SkillEvidenceCandidate]] = defaultdict(list)
        for candidate in observations:
            if candidate.source_group is None:
                continue
            grouped[(candidate.source_entity_type, candidate.source_group)].append(candidate)

        aggregates: dict[tuple[str, str, str, str, str], EdgeAggregate] = {}
        for candidates in grouped.values():
            slugs = sorted({candidate.skill_slug for candidate in candidates if candidate.skill_slug})
            if len(slugs) < 2:
                continue
            source_entity_type = candidates[0].source_entity_type
            source_entity_id = candidates[0].source_group or candidates[0].source_entity_id
            source_table = candidates[0].source_table
            source_pk = candidates[0].source_pk
            source_title = candidates[0].source_title
            provider = candidates[0].provider
            observed_at = max((candidate.observed_at for candidate in candidates if candidate.observed_at), default=_now())
            edge_type = "co_occurs"
            for left_slug, right_slug in self._co_occurrence_pairs(slugs):
                key = (left_slug, right_slug, edge_type, source_entity_type, source_entity_id)
                bucket = aggregates.setdefault(
                    key,
                    EdgeAggregate(
                        source_skill_slug=left_slug,
                        target_skill_slug=right_slug,
                        edge_type=edge_type,
                        source_entity_type=source_entity_type,
                        source_entity_id=source_entity_id,
                        source_table=source_table,
                        source_pk=source_pk,
                        source_title=source_title,
                        provider=provider,
                        weight=0.0,
                        evidence_count=0,
                        observed_at=observed_at,
                    ),
                )
                bucket.weight += 1.0
                bucket.evidence_count += 1
                bucket.evidence_kinds.update(candidate.evidence_kind for candidate in candidates if candidate.skill_slug in {left_slug, right_slug})
                if observed_at and (bucket.observed_at is None or observed_at > bucket.observed_at):
                    bucket.observed_at = observed_at
                if source_title:
                    bucket.raw_titles.add(source_title)

        return aggregates

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    async def _ensure_import_run(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[str],
        scope: str,
        notes: Optional[str],
    ) -> SkillGraphImportRun:
        run = SkillGraphImportRun(
            run_uid=str(uuid.uuid4()),
            user_id=user_id,
            scope=scope,
            status="running",
            strategy="real_data_import_v1",
            notes=notes,
            started_at=_now(),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(run)
        await db.flush()
        return run

    async def _upsert_node(self, db: AsyncSession, aggregate: SkillAggregate, run_uid: str) -> SkillGraphNode:
        status, confidence_score = self.score_node_status(
            evidence_count=aggregate.evidence_count,
            source_count=len(aggregate.source_keys),
            demand_count=aggregate.demand_count,
            supply_count=aggregate.supply_count,
            learning_signal_count=aggregate.learning_signal_count,
        )
        trust_score = round(sum(aggregate.trust_scores) / len(aggregate.trust_scores), 4) if aggregate.trust_scores else 0.0
        relevance_score = round(sum(aggregate.relevance_scores) / len(aggregate.relevance_scores), 4) if aggregate.relevance_scores else 0.0
        freshness_score = round(sum(aggregate.freshness_scores) / len(aggregate.freshness_scores), 4) if aggregate.freshness_scores else 0.0
        stmt = insert(SkillGraphNode.__table__).values(
            skill_slug=aggregate.skill_slug,
            skill_name=aggregate.skill_name,
            category=aggregate.category,
            status=status,
            evidence_count=aggregate.evidence_count,
            source_count=len(aggregate.source_keys),
            user_count=len(aggregate.user_ids),
            demand_count=aggregate.demand_count,
            supply_count=aggregate.supply_count,
            trust_score=trust_score,
            relevance_score=relevance_score,
            freshness_score=freshness_score,
            confidence_score=confidence_score,
            first_seen_at=aggregate.observed_at,
            last_seen_at=aggregate.observed_at,
            last_import_run_uid=run_uid,
            metadata={
                "source_types": sorted(aggregate.source_types),
                "aliases": sorted(aggregate.aliases),
                "evidence_count": aggregate.evidence_count,
                "demand_count": aggregate.demand_count,
                "supply_count": aggregate.supply_count,
                "learning_signal_count": aggregate.learning_signal_count,
                "resume_signal_count": aggregate.resume_signal_count,
            },
            created_at=_now(),
            updated_at=_now(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_skill_graph_nodes_skill_slug",
            set_={
                "skill_name": stmt.excluded.skill_name,
                "category": stmt.excluded.category,
                "status": stmt.excluded.status,
                "evidence_count": stmt.excluded.evidence_count,
                "source_count": stmt.excluded.source_count,
                "user_count": stmt.excluded.user_count,
                "demand_count": stmt.excluded.demand_count,
                "supply_count": stmt.excluded.supply_count,
                "trust_score": stmt.excluded.trust_score,
                "relevance_score": stmt.excluded.relevance_score,
                "freshness_score": stmt.excluded.freshness_score,
                "confidence_score": stmt.excluded.confidence_score,
                "first_seen_at": func.coalesce(SkillGraphNode.first_seen_at, stmt.excluded.first_seen_at),
                "last_seen_at": stmt.excluded.last_seen_at,
                "last_import_run_uid": stmt.excluded.last_import_run_uid,
                "metadata": stmt.excluded.metadata,
                "updated_at": _now(),
            },
        ).returning(SkillGraphNode)
        result = await db.execute(stmt)
        return result.scalar_one()

    async def _upsert_alias(
        self,
        db: AsyncSession,
        node_id: int,
        *,
        skill_slug: str,
        skill_name: str,
        raw_value: str,
        source_entity_type: str,
        source_entity_id: str,
        source_field: str,
        source_table: Optional[str],
        source_pk: Optional[str],
        provider: Optional[str],
        alias_type: str,
        metadata: dict[str, Any],
    ) -> Optional[SkillGraphAlias]:
        normalized_value = _normalize_text(raw_value or skill_name or skill_slug)
        if not normalized_value:
            return None
        alias_uid = _hash_uid(skill_slug, raw_value, source_entity_type, source_entity_id, source_field)
        stmt = insert(SkillGraphAlias.__table__).values(
            alias_uid=alias_uid,
            skill_node_id=node_id,
            raw_value=raw_value,
            normalized_value=normalized_value,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            source_field=source_field,
            source_table=source_table,
            source_pk=source_pk,
            provider=provider,
            alias_type=alias_type,
            metadata=metadata,
            created_at=_now(),
            updated_at=_now(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_skill_graph_aliases_source_alias",
            set_={
                "normalized_value": stmt.excluded.normalized_value,
                "provider": stmt.excluded.provider,
                "alias_type": stmt.excluded.alias_type,
                "metadata": stmt.excluded.metadata,
                "updated_at": _now(),
            },
        ).returning(SkillGraphAlias)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _upsert_edge(
        self,
        db: AsyncSession,
        aggregate: EdgeAggregate,
        node_map: dict[str, SkillGraphNode],
    ) -> Optional[SkillGraphEdge]:
        source_node = node_map.get(aggregate.source_skill_slug)
        target_node = node_map.get(aggregate.target_skill_slug)
        if source_node is None or target_node is None:
            return None
        edge_uid = _hash_uid(
            aggregate.source_skill_slug,
            aggregate.target_skill_slug,
            aggregate.edge_type,
            aggregate.source_entity_type,
            aggregate.source_entity_id,
        )
        confidence = min(1.0, 0.35 + (aggregate.evidence_count * 0.15) + (aggregate.weight * 0.05))
        relation_summary = aggregate.relation_summary or (
            f"{source_node.skill_name} and {target_node.skill_name} co-occurred in {aggregate.source_entity_type} {aggregate.source_entity_id}."
        )
        stmt = insert(SkillGraphEdge.__table__).values(
            edge_uid=edge_uid,
            source_skill_node_id=source_node.id,
            target_skill_node_id=target_node.id,
            edge_type=aggregate.edge_type,
            source_entity_type=aggregate.source_entity_type,
            source_entity_id=aggregate.source_entity_id,
            source_table=aggregate.source_table,
            source_pk=aggregate.source_pk,
            source_title=aggregate.source_title,
            provider=aggregate.provider,
            weight=float(aggregate.weight),
            evidence_count=aggregate.evidence_count,
            confidence_score=round(confidence, 4),
            relation_summary=relation_summary,
            metadata={
                **aggregate.metadata,
                "evidence_kinds": sorted(aggregate.evidence_kinds),
                "titles": sorted(aggregate.raw_titles),
            },
            first_seen_at=aggregate.observed_at,
            last_seen_at=aggregate.observed_at,
            created_at=_now(),
            updated_at=_now(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_skill_graph_edge_source_target",
            set_={
                "weight": SkillGraphEdge.weight + stmt.excluded.weight,
                "evidence_count": SkillGraphEdge.evidence_count + stmt.excluded.evidence_count,
                "confidence_score": stmt.excluded.confidence_score,
                "relation_summary": stmt.excluded.relation_summary,
                "metadata": stmt.excluded.metadata,
                "last_seen_at": stmt.excluded.last_seen_at,
                "provider": stmt.excluded.provider,
                "source_title": stmt.excluded.source_title,
                "updated_at": _now(),
            },
        ).returning(SkillGraphEdge)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _upsert_evidence(
        self,
        db: AsyncSession,
        candidate: SkillEvidenceCandidate,
        node_map: dict[str, SkillGraphNode],
        edge_map: dict[tuple[str, str, str, str, str], SkillGraphEdge],
    ) -> Optional[SkillGraphEvidence]:
        node = node_map.get(candidate.skill_slug)
        if node is None:
            return None
        edge = None
        if candidate.source_group:
            source_candidates = [key for key in edge_map if key[3] == candidate.source_entity_type and key[4] == candidate.source_group]
            if source_candidates:
                # attach to the first matching edge for the source group if available
                edge = edge_map[source_candidates[0]]

        evidence_uid = _hash_uid(
            candidate.skill_slug,
            candidate.source_entity_type,
            candidate.source_entity_id,
            candidate.source_field,
            candidate.evidence_kind,
            candidate.raw_value,
        )
        stmt = insert(SkillGraphEvidence.__table__).values(
            evidence_uid=evidence_uid,
            skill_node_id=node.id,
            edge_id=edge.id if edge else None,
            source_entity_type=candidate.source_entity_type,
            source_entity_id=candidate.source_entity_id,
            source_table=candidate.source_table,
            source_pk=candidate.source_pk,
            source_field=candidate.source_field,
            source_title=candidate.source_title,
            source_url=candidate.source_url,
            provider=candidate.provider,
            evidence_kind=candidate.evidence_kind,
            raw_value=candidate.raw_value,
            normalized_value=candidate.normalized_value,
            trust_score=candidate.trust_score,
            relevance_score=candidate.relevance_score,
            freshness_score=candidate.freshness_score,
            confidence=candidate.confidence,
            status=candidate.status,
            metadata={
                **candidate.metadata,
                "observed_at": candidate.observed_at.isoformat() if candidate.observed_at else None,
                "user_id": candidate.user_id,
                "source_group": candidate.source_group,
            },
            recorded_at=candidate.observed_at,
            created_at=_now(),
            updated_at=_now(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_skill_graph_evidence_source",
            set_={
                "edge_id": stmt.excluded.edge_id,
                "provider": stmt.excluded.provider,
                "trust_score": stmt.excluded.trust_score,
                "relevance_score": stmt.excluded.relevance_score,
                "freshness_score": stmt.excluded.freshness_score,
                "confidence": stmt.excluded.confidence,
                "status": stmt.excluded.status,
                "metadata": stmt.excluded.metadata,
                "recorded_at": stmt.excluded.recorded_at,
                "updated_at": _now(),
            },
        ).returning(SkillGraphEvidence)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _upsert_user_state(
        self,
        db: AsyncSession,
        aggregate: UserSkillAggregate,
        node_map: dict[str, SkillGraphNode],
        run_uid: str,
    ) -> Optional[UserSkillState]:
        node = node_map.get(aggregate.skill_slug)
        if node is None:
            return None
        status, confidence_score, recommendation = self.score_user_status(
            demand_count=aggregate.demand_count,
            supply_count=aggregate.supply_count,
            learning_signal_count=aggregate.learning_signal_count,
            resume_signal_count=aggregate.resume_signal_count,
            started_count=aggregate.started_count,
            completion_count=aggregate.completion_count,
            feedback_count=aggregate.feedback_count,
        )
        average_rating = None
        if aggregate.rating_values:
            average_rating = round(sum(aggregate.rating_values) / len(aggregate.rating_values), 4)
        state_uid = _hash_uid(aggregate.user_id, aggregate.skill_slug)
        stmt = insert(UserSkillState.__table__).values(
            state_uid=state_uid,
            user_id=aggregate.user_id,
            skill_node_id=node.id,
            status=status,
            confidence_score=confidence_score,
            evidence_count=aggregate.evidence_count,
            demand_count=aggregate.demand_count,
            supply_count=aggregate.supply_count,
            learning_signal_count=aggregate.learning_signal_count,
            resume_signal_count=aggregate.resume_signal_count,
            started_count=aggregate.started_count,
            completion_count=aggregate.completion_count,
            feedback_count=aggregate.feedback_count,
            average_rating=average_rating,
            last_activity_at=aggregate.last_activity_at,
            last_import_run_uid=run_uid,
            recommended_action=recommendation,
            evidence_summary=aggregate.evidence_summary,
            metadata={
                "aliases": sorted(aggregate.aliases),
                "source_count": len(aggregate.source_keys),
            },
            created_at=_now(),
            updated_at=_now(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_user_skill_states_user_skill",
            set_={
                "status": stmt.excluded.status,
                "confidence_score": stmt.excluded.confidence_score,
                "evidence_count": stmt.excluded.evidence_count,
                "demand_count": stmt.excluded.demand_count,
                "supply_count": stmt.excluded.supply_count,
                "learning_signal_count": stmt.excluded.learning_signal_count,
                "resume_signal_count": stmt.excluded.resume_signal_count,
                "started_count": stmt.excluded.started_count,
                "completion_count": stmt.excluded.completion_count,
                "feedback_count": stmt.excluded.feedback_count,
                "average_rating": stmt.excluded.average_rating,
                "last_activity_at": stmt.excluded.last_activity_at,
                "last_import_run_uid": stmt.excluded.last_import_run_uid,
                "recommended_action": stmt.excluded.recommended_action,
                "evidence_summary": stmt.excluded.evidence_summary,
                "metadata": stmt.excluded.metadata,
                "updated_at": _now(),
            },
        ).returning(UserSkillState)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _upsert_import_run(
        self,
        db: AsyncSession,
        run: SkillGraphImportRun,
        *,
        status: str,
        node_count: int,
        edge_count: int,
        evidence_count: int,
        alias_count: int,
        user_state_count: int,
        source_counts: dict[str, int],
        error_message: Optional[str] = None,
        completed: bool = True,
    ) -> SkillGraphImportRun:
        run.status = status
        run.node_count = node_count
        run.edge_count = edge_count
        run.evidence_count = evidence_count
        run.alias_count = alias_count
        run.user_state_count = user_state_count
        run.source_counts = dict(source_counts)
        run.error_message = error_message
        run.completed_at = _now() if completed else None
        run.updated_at = _now()
        await db.flush()
        return run

    # ------------------------------------------------------------------
    # Public import / query API
    # ------------------------------------------------------------------
    async def import_graph(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[str] = None,
        request: Optional[SkillGraphImportRequest] = None,
    ) -> dict[str, Any]:
        request = request or SkillGraphImportRequest()
        import_run = await self._ensure_import_run(
            db,
            user_id=user_id,
            scope=request.scope,
            notes=request.notes,
        )
        structured_observations, vocabulary, structured_counts = await self._collect_structured_observations(db)
        text_observations, text_counts = await self._collect_text_observations(db, vocabulary)
        all_observations = [*structured_observations, *text_observations]
        node_aggregates = self._aggregate_nodes(structured_observations, text_observations)
        user_aggregates = self._aggregate_user_states(all_observations) if request.include_user_states else {}
        edge_aggregates = self._aggregate_edges(all_observations) if request.include_edges else {}

        node_map: dict[str, SkillGraphNode] = {}
        for skill_slug, aggregate in node_aggregates.items():
            node = await self._upsert_node(db, aggregate, import_run.run_uid)
            node_map[skill_slug] = node

        alias_count = 0
        for candidate in all_observations:
            node = node_map.get(candidate.skill_slug)
            if node is None:
                continue
            alias = await self._upsert_alias(
                db,
                node.id,
                skill_slug=candidate.skill_slug,
                skill_name=candidate.skill_name,
                raw_value=candidate.raw_value,
                source_entity_type=candidate.source_entity_type,
                source_entity_id=candidate.source_entity_id,
                source_field=candidate.source_field,
                source_table=candidate.source_table,
                source_pk=candidate.source_pk,
                provider=candidate.provider,
                alias_type="source_value",
                metadata=candidate.metadata,
            )
            if alias is not None:
                alias_count += 1

        edge_map: dict[tuple[str, str, str, str, str], SkillGraphEdge] = {}
        if request.include_edges:
            for key, aggregate in edge_aggregates.items():
                edge = await self._upsert_edge(db, aggregate, node_map)
                if edge is not None:
                    edge_map[key] = edge

        evidence_count = 0
        if request.include_evidence:
            for candidate in all_observations:
                evidence = await self._upsert_evidence(db, candidate, node_map, edge_map)
                if evidence is not None:
                    evidence_count += 1

        user_state_count = 0
        if request.include_user_states:
            for aggregate in user_aggregates.values():
                state = await self._upsert_user_state(db, aggregate, node_map, import_run.run_uid)
                if state is not None:
                    user_state_count += 1

        # Refresh derived node counters after user state upserts
        for skill_slug, node in node_map.items():
            related_states = [aggregate for aggregate in user_aggregates.values() if aggregate.skill_slug == skill_slug]
            node.user_count = len({aggregate.user_id for aggregate in related_states})
            node.last_import_run_uid = import_run.run_uid
            node.updated_at = _now()

        await self._upsert_import_run(
            db,
            import_run,
            status="completed",
            node_count=len(node_map),
            edge_count=len(edge_map),
            evidence_count=evidence_count,
            alias_count=alias_count,
            user_state_count=user_state_count,
            source_counts=dict(Counter(structured_counts) + Counter(text_counts)),
            completed=True,
        )
        await db.commit()

        summary = await self.get_summary(db, user_id=user_id)
        run_payload = summary.get("latest_import_run")
        await get_career_event_service().emit_event(
            db,
            event_type="SkillGraphImportCompleted",
            entity_type="skill_graph_import_run",
            entity_id=import_run.run_uid,
            source_service="services.skill_graph.skill_graph_service",
            user_id=user_id,
            source_table="skill_graph_import_runs",
            source_id=import_run.id,
            payload={
                "run_uid": import_run.run_uid,
                "scope": import_run.scope,
                "status": import_run.status,
                "node_count": import_run.node_count,
                "edge_count": import_run.edge_count,
                "evidence_count": import_run.evidence_count,
                "alias_count": import_run.alias_count,
                "user_state_count": import_run.user_state_count,
            },
            evidence=[
                get_career_event_service().build_evidence_ref(
                    table="skill_graph_import_runs",
                    source_id=import_run.id,
                    note="Skill graph imported from live CareerOS data sources",
                    extra={
                        "source_counts": import_run.source_counts or {},
                        "strategy": import_run.strategy,
                    },
                )
            ],
            provider="skill_graph",
            trace_id=import_run.run_uid,
        )
        return {
            "status": "ok",
            "run": run_payload,
            "node_count": len(node_map),
            "edge_count": len(edge_map),
            "evidence_count": evidence_count,
            "alias_count": alias_count,
            "user_state_count": user_state_count,
            "source_counts": {**structured_counts, **text_counts},
        }

    async def _serialize_node(self, node: SkillGraphNode) -> dict[str, Any]:
        return {
            "skill_slug": node.skill_slug,
            "skill_name": node.skill_name,
            "category": node.category,
            "status": node.status,
            "evidence_count": node.evidence_count,
            "source_count": node.source_count,
            "user_count": node.user_count,
            "demand_count": node.demand_count,
            "supply_count": node.supply_count,
            "trust_score": float(node.trust_score or 0.0),
            "relevance_score": float(node.relevance_score or 0.0),
            "freshness_score": float(node.freshness_score or 0.0),
            "confidence_score": float(node.confidence_score or 0.0),
            "first_seen_at": node.first_seen_at.isoformat() if node.first_seen_at else None,
            "last_seen_at": node.last_seen_at.isoformat() if node.last_seen_at else None,
            "last_import_run_uid": node.last_import_run_uid,
            "metadata": node.metadata_ or {},
        }

    @staticmethod
    def _serialize_import_run(run: SkillGraphImportRun) -> dict[str, Any]:
        return {
            "run_uid": run.run_uid,
            "user_id": run.user_id,
            "scope": run.scope,
            "status": run.status,
            "strategy": run.strategy,
            "node_count": run.node_count,
            "edge_count": run.edge_count,
            "evidence_count": run.evidence_count,
            "alias_count": run.alias_count,
            "user_state_count": run.user_state_count,
            "source_counts": run.source_counts or {},
            "notes": run.notes,
            "error_message": run.error_message,
            "metadata": run.metadata_ or {},
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        }

    @staticmethod
    def _serialize_alias(alias: SkillGraphAlias, skill: SkillGraphNode) -> dict[str, Any]:
        return {
            "raw_value": alias.raw_value,
            "normalized_value": alias.normalized_value,
            "source_entity_type": alias.source_entity_type,
            "source_entity_id": alias.source_entity_id,
            "source_field": alias.source_field,
            "source_table": alias.source_table,
            "source_pk": alias.source_pk,
            "provider": alias.provider,
            "alias_type": alias.alias_type,
            "metadata": alias.metadata_ or {},
            "created_at": alias.created_at.isoformat() if alias.created_at else None,
            "skill_slug": skill.skill_slug,
            "skill_name": skill.skill_name,
        }

    @staticmethod
    def _serialize_edge(edge: SkillGraphEdge, source_skill: SkillGraphNode, target_skill: SkillGraphNode) -> dict[str, Any]:
        return {
            "edge_uid": edge.edge_uid,
            "source_skill_slug": source_skill.skill_slug,
            "source_skill_name": source_skill.skill_name,
            "target_skill_slug": target_skill.skill_slug,
            "target_skill_name": target_skill.skill_name,
            "edge_type": edge.edge_type,
            "source_entity_type": edge.source_entity_type,
            "source_entity_id": edge.source_entity_id,
            "source_table": edge.source_table,
            "source_pk": edge.source_pk,
            "source_title": edge.source_title,
            "provider": edge.provider,
            "weight": float(edge.weight or 0.0),
            "evidence_count": edge.evidence_count,
            "confidence_score": float(edge.confidence_score or 0.0),
            "relation_summary": edge.relation_summary,
            "metadata": edge.metadata_ or {},
            "first_seen_at": edge.first_seen_at.isoformat() if edge.first_seen_at else None,
            "last_seen_at": edge.last_seen_at.isoformat() if edge.last_seen_at else None,
        }

    @staticmethod
    def _serialize_evidence(evidence: SkillGraphEvidence, node: SkillGraphNode) -> dict[str, Any]:
        return {
            "evidence_uid": evidence.evidence_uid,
            "skill_slug": node.skill_slug,
            "skill_name": node.skill_name,
            "source_entity_type": evidence.source_entity_type,
            "source_entity_id": evidence.source_entity_id,
            "source_table": evidence.source_table,
            "source_pk": evidence.source_pk,
            "source_field": evidence.source_field,
            "source_title": evidence.source_title,
            "source_url": evidence.source_url,
            "provider": evidence.provider,
            "evidence_kind": evidence.evidence_kind,
            "raw_value": evidence.raw_value,
            "normalized_value": evidence.normalized_value,
            "trust_score": float(evidence.trust_score or 0.0),
            "relevance_score": float(evidence.relevance_score or 0.0),
            "freshness_score": float(evidence.freshness_score or 0.0),
            "confidence": evidence.confidence,
            "status": evidence.status,
            "metadata": evidence.metadata_ or {},
            "recorded_at": evidence.recorded_at.isoformat() if evidence.recorded_at else None,
        }

    @staticmethod
    def _serialize_user_state(state: UserSkillState, node: SkillGraphNode) -> dict[str, Any]:
        return {
            "state_uid": state.state_uid,
            "user_id": state.user_id,
            "skill_slug": node.skill_slug,
            "skill_name": node.skill_name,
            "category": node.category,
            "status": state.status,
            "confidence_score": float(state.confidence_score or 0.0),
            "evidence_count": state.evidence_count,
            "demand_count": state.demand_count,
            "supply_count": state.supply_count,
            "learning_signal_count": state.learning_signal_count,
            "resume_signal_count": state.resume_signal_count,
            "started_count": state.started_count,
            "completion_count": state.completion_count,
            "feedback_count": state.feedback_count,
            "average_rating": state.average_rating,
            "last_activity_at": state.last_activity_at.isoformat() if state.last_activity_at else None,
            "last_import_run_uid": state.last_import_run_uid,
            "recommended_action": state.recommended_action,
            "evidence_summary": state.evidence_summary or {},
            "metadata": state.metadata_ or {},
        }

    async def get_summary(self, db: AsyncSession, *, user_id: Optional[str] = None, limit: int = 12) -> dict[str, Any]:
        total_nodes = int((await db.execute(select(func.count()).select_from(SkillGraphNode))).scalar() or 0)
        total_edges = int((await db.execute(select(func.count()).select_from(SkillGraphEdge))).scalar() or 0)
        total_evidence = int((await db.execute(select(func.count()).select_from(SkillGraphEvidence))).scalar() or 0)
        total_aliases = int((await db.execute(select(func.count()).select_from(SkillGraphAlias))).scalar() or 0)
        total_user_states = int((await db.execute(select(func.count()).select_from(UserSkillState))).scalar() or 0)

        node_rows = (
            await db.execute(
                select(SkillGraphNode)
                .order_by(SkillGraphNode.confidence_score.desc(), SkillGraphNode.evidence_count.desc(), SkillGraphNode.skill_name.asc())
                .limit(limit)
            )
        ).scalars().all()
        top_nodes = [await self._serialize_node(node) for node in node_rows]

        latest_run_result = await db.execute(select(SkillGraphImportRun).order_by(SkillGraphImportRun.started_at.desc(), SkillGraphImportRun.id.desc()).limit(1))
        latest_run = latest_run_result.scalar_one_or_none()

        user_states: list[dict[str, Any]] = []
        if user_id:
            state_rows = (
                await db.execute(
                    select(UserSkillState, SkillGraphNode)
                    .join(SkillGraphNode, SkillGraphNode.id == UserSkillState.skill_node_id)
                    .where(UserSkillState.user_id == user_id)
                    .order_by(UserSkillState.confidence_score.desc(), UserSkillState.evidence_count.desc())
                    .limit(limit)
                )
            ).all()
            user_states = [self._serialize_user_state(state, node) for state, node in state_rows]

        source_counts: dict[str, int] = {}
        if latest_run and isinstance(latest_run.source_counts, dict):
            source_counts = {str(key): int(value) for key, value in latest_run.source_counts.items()}

        return {
            "status": "ok",
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "total_evidence": total_evidence,
            "total_aliases": total_aliases,
            "total_user_states": total_user_states,
            "source_counts": source_counts,
            "top_nodes": top_nodes,
            "user_states": user_states,
            "latest_import_run": self._serialize_import_run(latest_run) if latest_run else None,
        }

    async def list_nodes(self, db: AsyncSession, *, search: Optional[str] = None, limit: int = 25) -> list[dict[str, Any]]:
        query = select(SkillGraphNode)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(
                SkillGraphNode.skill_slug.ilike(pattern) | SkillGraphNode.skill_name.ilike(pattern) | SkillGraphNode.category.ilike(pattern)
            )
        rows = (
            await db.execute(
                query.order_by(SkillGraphNode.confidence_score.desc(), SkillGraphNode.evidence_count.desc(), SkillGraphNode.skill_name.asc()).limit(limit)
            )
        ).scalars().all()
        return [await self._serialize_node(row) for row in rows]

    async def get_node_detail(
        self,
        db: AsyncSession,
        skill_slug: str,
        *,
        user_id: Optional[str] = None,
        limit: int = 12,
    ) -> dict[str, Any]:
        node_result = await db.execute(select(SkillGraphNode).where(SkillGraphNode.skill_slug == skill_slug))
        node = node_result.scalar_one_or_none()
        if node is None:
            raise ValueError("Skill node not found")

        alias_rows = (
            await db.execute(
                select(SkillGraphAlias)
                .where(SkillGraphAlias.skill_node_id == node.id)
                .order_by(SkillGraphAlias.created_at.desc(), SkillGraphAlias.id.desc())
                .limit(limit)
            )
        ).scalars().all()
        from sqlalchemy.orm import aliased

        source_alias = aliased(SkillGraphNode)
        target_alias = aliased(SkillGraphNode)
        edge_rows = (
            await db.execute(
                select(SkillGraphEdge, source_alias, target_alias)
                .join(source_alias, source_alias.id == SkillGraphEdge.source_skill_node_id)
                .join(target_alias, target_alias.id == SkillGraphEdge.target_skill_node_id)
                .where(or_(source_alias.id == node.id, target_alias.id == node.id))
                .order_by(SkillGraphEdge.evidence_count.desc(), SkillGraphEdge.weight.desc())
                .limit(limit)
            )
        ).all()

        evidence_rows = (
            await db.execute(
                select(SkillGraphEvidence)
                .where(SkillGraphEvidence.skill_node_id == node.id)
                .order_by(SkillGraphEvidence.recorded_at.desc(), SkillGraphEvidence.id.desc())
                .limit(limit)
            )
        ).scalars().all()

        state_rows: list[tuple[UserSkillState, SkillGraphNode]] = []
        if user_id:
            state_rows = (
                await db.execute(
                    select(UserSkillState, SkillGraphNode)
                    .join(SkillGraphNode, SkillGraphNode.id == UserSkillState.skill_node_id)
                    .where(UserSkillState.user_id == user_id, UserSkillState.skill_node_id == node.id)
                    .order_by(UserSkillState.confidence_score.desc())
                )
            ).all()

        return {
            "status": "ok",
            "node": await self._serialize_node(node),
            "aliases": [self._serialize_alias(alias, node) for alias in alias_rows],
            "edges": [self._serialize_edge(edge, source_node, target_node) for edge, source_node, target_node in edge_rows],
            "evidence": [self._serialize_evidence(evidence, node) for evidence in evidence_rows],
            "user_states": [self._serialize_user_state(state, state_node) for state, state_node in state_rows],
        }

    async def list_import_runs(self, db: AsyncSession, *, limit: int = 10) -> list[dict[str, Any]]:
        rows = (
            await db.execute(
                select(SkillGraphImportRun)
                .order_by(SkillGraphImportRun.started_at.desc(), SkillGraphImportRun.id.desc())
                .limit(limit)
            )
        ).scalars().all()
        return [self._serialize_import_run(row) for row in rows]

    async def list_user_states(self, db: AsyncSession, *, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = (
            await db.execute(
                select(UserSkillState, SkillGraphNode)
                .join(SkillGraphNode, SkillGraphNode.id == UserSkillState.skill_node_id)
                .where(UserSkillState.user_id == user_id)
                .order_by(UserSkillState.confidence_score.desc(), UserSkillState.evidence_count.desc(), SkillGraphNode.skill_name.asc())
                .limit(limit)
            )
        ).all()
        return [self._serialize_user_state(state, node) for state, node in rows]

    async def get_health(self, db: AsyncSession) -> dict[str, Any]:
        node_count = int((await db.execute(select(func.count()).select_from(SkillGraphNode))).scalar() or 0)
        edge_count = int((await db.execute(select(func.count()).select_from(SkillGraphEdge))).scalar() or 0)
        evidence_count = int((await db.execute(select(func.count()).select_from(SkillGraphEvidence))).scalar() or 0)
        import_count = int((await db.execute(select(func.count()).select_from(SkillGraphImportRun))).scalar() or 0)
        ready = node_count > 0 and evidence_count > 0
        return {
            "status": "ok" if ready else "not_ready",
            "ready": ready,
            "tables": [
                "skill_graph_nodes",
                "skill_graph_aliases",
                "skill_graph_edges",
                "skill_graph_evidence",
                "skill_graph_import_runs",
                "user_skill_states",
            ],
            "collection": "skill_graph",
            "message": f"{node_count} nodes, {edge_count} edges, {evidence_count} evidence rows, {import_count} import runs.",
        }


_SERVICE: Optional[SkillGraphService] = None


def get_skill_graph_service() -> SkillGraphService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = SkillGraphService()
    return _SERVICE
