"""Evidence collection helpers for the CareerOS skill gap engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import Job, JobMatch
from src.models.learning import (
    LearningActivityEvent,
    LearningResource,
    LearningSession,
    ResourceFeedback,
    ResourceOutcome,
    ResourceProvenanceRecord,
)
from src.models.roadmap import Roadmap, RoadmapGoal, RoadmapTask
from src.models.resume import Resume, ResumeChunk, ResumeVersion
from src.models.skill_graph import SkillGraphEvidence, SkillGraphNode, UserSkillState
from src.services.learning.skill_normalizer import canonical_display_name, normalize_skill, normalize_skill_list, skill_search_terms

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SkillGapRequirement:
    skill_slug: str
    skill_name: str
    required_by_type: str
    required_by_id: Optional[str]
    source_table: Optional[str]
    source_id: Optional[str]
    source_title: Optional[str]
    source_url: Optional[str]
    source_strength: str = "strong"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SkillGapEvidenceRecord:
    skill_slug: str
    skill_name: str
    evidence_type: str
    source_table: Optional[str]
    source_id: Optional[str]
    source_url: Optional[str]
    evidence_strength: str
    supports_status: str
    quote_or_snippet: Optional[str]
    metadata_json: dict[str, Any] = field(default_factory=dict)
    confidence: str = "low"
    source_title: Optional[str] = None


def _now() -> datetime:
    return datetime.utcnow()


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = text.replace("/", " ").replace("-", " ").replace("_", " ")
    text = "".join(ch if ch.isalnum() or ch in {"+", "#", ".", " "} else " " for ch in text)
    return " ".join(text.split())


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


def _combine_text(*parts: Any) -> str:
    return " ".join(part.strip() for part in (str(item).strip() for item in parts if item) if part)


def _confidence_for_strength(strength: str, evidence_count: int) -> str:
    if strength == "strong" or evidence_count >= 4:
        return "high"
    if strength == "medium" or evidence_count >= 2:
        return "medium"
    return "low"


class SkillGapEvidenceService:
    """Read real stored data and convert it into explainable evidence rows."""

    async def collect_required_skill_evidence(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        source_scope: str,
        job_id: int | None = None,
        target_role_slug: str | None = None,
    ) -> list[SkillGapRequirement]:
        if source_scope == "job":
            return await self._collect_job_requirements(db, user_id=user_id, job_id=job_id)
        if source_scope == "user":
            return await self._collect_user_requirements(db, user_id=user_id)
        if source_scope in {"role", "roadmap"}:
            return await self._collect_roadmap_requirements(db, user_id=user_id, target_role_slug=target_role_slug)
        return []

    async def _collect_job_requirements(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        job_id: int | None,
    ) -> list[SkillGapRequirement]:
        if job_id is None:
            return []
        job_result = await db.execute(select(Job).where(Job.id == job_id, Job.deleted_at.is_(None)))
        job = job_result.scalar_one_or_none()
        if job is None:
            return []
        match_result = await db.execute(
            select(JobMatch)
            .where(JobMatch.user_id == user_id, JobMatch.job_id == job_id, JobMatch.deleted_at.is_(None))
            .order_by(JobMatch.created_at.desc(), JobMatch.id.desc())
            .limit(1)
        )
        match = match_result.scalar_one_or_none()

        raw_sources: list[tuple[object, str, str, str | None, str | None]] = []
        for value in job.skills_required or []:
            raw_sources.append((value, "job.skills_required", "jobs", str(job.id), job.title))
        if match and isinstance(match.gaps, list):
            for value in match.gaps:
                raw_sources.append((value, "job_matches.gaps", "job_matches", str(match.id), job.title))
        if match and isinstance(match.match_details, dict):
            for value in match.match_details.get("missing_skills") or []:
                raw_sources.append((value, "job_matches.match_details.missing_skills", "job_matches", str(match.id), job.title))
            for value in (match.match_details.get("job_extraction", {}) or {}).get("skills", []) or []:
                raw_sources.append((value, "job_matches.match_details.job_extraction.skills", "job_matches", str(match.id), job.title))

        requirements: dict[str, SkillGapRequirement] = {}
        for raw_value, source_field, source_table, source_id, source_title in raw_sources:
            normalized = normalize_skill(raw_value)
            if not normalized.slug:
                continue
            requirement = requirements.get(normalized.slug)
            if requirement is None:
                requirement = SkillGapRequirement(
                    skill_slug=normalized.slug,
                    skill_name=normalized.display_name or canonical_display_name(normalized.slug),
                    required_by_type="job",
                    required_by_id=str(job.id),
                    source_table=source_table,
                    source_id=source_id,
                    source_title=source_title,
                    source_url=job.apply_url or job.source_url,
                    source_strength="strong",
                    metadata={
                        "job_id": job.id,
                        "job_title": job.title,
                        "company": job.company,
                        "source_fields": [],
                        "source_values": [],
                        "match_id": match.id if match else None,
                    },
                )
                requirements[normalized.slug] = requirement
            requirement.metadata.setdefault("source_fields", []).append(source_field)
            requirement.metadata.setdefault("source_values", []).append(normalized.display_name or str(raw_value))
            if match:
                requirement.metadata.setdefault("match_score", float(match.overall_score or 0.0))
        return list(requirements.values())

    async def _collect_user_requirements(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> list[SkillGapRequirement]:
        match_result = await db.execute(
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

        requirements: dict[str, SkillGapRequirement] = {}
        for match, job in match_result.all():
            raw_sources: list[tuple[object, str]] = []
            if isinstance(match.gaps, list):
                raw_sources.extend((value, "job_matches.gaps") for value in match.gaps)
            if isinstance(match.match_details, dict):
                raw_sources.extend((value, "job_matches.match_details.missing_skills") for value in (match.match_details.get("missing_skills") or []))
                raw_sources.extend((value, "job_matches.match_details.job_extraction.skills") for value in (match.match_details.get("job_extraction", {}) or {}).get("skills", []) or [])
            if isinstance(job.skills_required, list):
                raw_sources.extend((value, "jobs.skills_required") for value in job.skills_required)
            for raw_value, source_field in raw_sources:
                normalized = normalize_skill(raw_value)
                if not normalized.slug:
                    continue
                requirement = requirements.get(normalized.slug)
                if requirement is None:
                    requirement = SkillGapRequirement(
                        skill_slug=normalized.slug,
                        skill_name=normalized.display_name or canonical_display_name(normalized.slug),
                        required_by_type="user",
                        required_by_id=user_id,
                        source_table="job_matches",
                        source_id=str(match.id),
                        source_title=job.title,
                        source_url=job.apply_url or job.source_url,
                        source_strength="strong",
                        metadata={
                            "user_id": user_id,
                            "source_job_ids": [],
                            "source_job_titles": [],
                            "job_match_ids": [],
                            "source_fields": [],
                        },
                    )
                    requirements[normalized.slug] = requirement
                requirement.metadata.setdefault("source_job_ids", []).append(job.id)
                requirement.metadata.setdefault("source_job_titles", []).append(job.title)
                requirement.metadata.setdefault("job_match_ids", []).append(match.id)
                requirement.metadata.setdefault("source_fields", []).append(source_field)
        return list(requirements.values())

    async def _collect_roadmap_requirements(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        target_role_slug: str | None,
    ) -> list[SkillGapRequirement]:
        roadmap_query = select(Roadmap).where(Roadmap.user_id == user_id, Roadmap.deleted_at.is_(None))
        if target_role_slug:
            role_term = _normalize_text(target_role_slug)
            if role_term:
                roadmap_query = roadmap_query.where(
                    (Roadmap.target_role.ilike(f"%{target_role_slug}%"))
                    | (Roadmap.title.ilike(f"%{target_role_slug}%"))
                )
        roadmap_rows = list((await db.execute(roadmap_query.order_by(Roadmap.updated_at.desc(), Roadmap.id.desc()))).scalars().all())
        if not roadmap_rows:
            return []

        node_rows = list((await db.execute(select(SkillGraphNode.skill_slug, SkillGraphNode.skill_name))).all())
        if not node_rows:
            return []

        requirements: dict[str, SkillGapRequirement] = {}
        for roadmap in roadmap_rows:
            goal_rows = list((await db.execute(select(RoadmapGoal).where(RoadmapGoal.roadmap_id == roadmap.id, RoadmapGoal.deleted_at.is_(None)))).scalars().all())
            for goal in goal_rows:
                task_rows = list((await db.execute(select(RoadmapTask).where(RoadmapTask.goal_id == goal.id, RoadmapTask.deleted_at.is_(None)))).scalars().all())
                for task in task_rows:
                    blobs = _flatten_strings({"roadmap": roadmap.title, "target_role": roadmap.target_role, "goal": {"title": goal.title, "description": goal.description}, "task": {"title": task.title, "description": task.description}})
                    text = _combine_text(*blobs)
                    if not text:
                        continue
                    normalized_text = _normalize_text(text)
                    for skill_slug, skill_name in node_rows:
                        search_terms = skill_search_terms(skill_name or skill_slug)
                        if not search_terms:
                            continue
                        if not any(term in normalized_text for term in search_terms):
                            continue
                        requirement = requirements.get(skill_slug)
                        if requirement is None:
                            requirement = SkillGapRequirement(
                                skill_slug=skill_slug,
                                skill_name=skill_name or canonical_display_name(skill_slug),
                                required_by_type="roadmap",
                                required_by_id=roadmap.roadmap_uid,
                                source_table="roadmap_tasks",
                                source_id=task.task_uid,
                                source_title=task.title,
                                source_url=None,
                                source_strength="medium",
                                metadata={
                                    "user_id": user_id,
                                    "roadmap_uid": roadmap.roadmap_uid,
                                    "roadmap_title": roadmap.title,
                                    "goal_titles": [],
                                    "task_uids": [],
                                    "matched_terms": [],
                                },
                            )
                            requirements[skill_slug] = requirement
                        requirement.metadata.setdefault("goal_titles", []).append(goal.title)
                        requirement.metadata.setdefault("task_uids", []).append(task.task_uid)
                        requirement.metadata.setdefault("matched_terms", []).extend([term for term in search_terms if term in normalized_text][:3])
        return list(requirements.values())

    def _matches_skill(self, text: str, requirement: SkillGapRequirement) -> bool:
        normalized_text = _normalize_text(text)
        if not normalized_text:
            return False
        return any(term in normalized_text for term in skill_search_terms(requirement.skill_name or requirement.skill_slug))

    def _requirement_search_terms(self, requirement: SkillGapRequirement) -> tuple[str, ...]:
        return skill_search_terms(requirement.skill_name or requirement.skill_slug)

    async def collect_resume_evidence(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        required_skills: list[SkillGapRequirement],
    ) -> dict[str, list[SkillGapEvidenceRecord]]:
        if not required_skills:
            return {}
        skill_map = {item.skill_slug: item for item in required_skills}
        evidence: dict[str, list[SkillGapEvidenceRecord]] = {item.skill_slug: [] for item in required_skills}
        resumes_result = await db.execute(select(Resume).where(Resume.user_id == user_id, Resume.deleted_at.is_(None)))
        resumes = resumes_result.scalars().all()
        for resume in resumes:
            versions_result = await db.execute(select(ResumeVersion).where(ResumeVersion.resume_id == resume.id, ResumeVersion.deleted_at.is_(None)))
            versions = list(versions_result.scalars().all())
            if not versions:
                continue
            latest_version = sorted(versions, key=lambda item: (item.created_at or _now(), item.version_num, item.id), reverse=True)[0]
            chunks_result = await db.execute(select(ResumeChunk).where(ResumeChunk.version_id == latest_version.id, ResumeChunk.deleted_at.is_(None)))
            chunks = sorted(chunks_result.scalars().all(), key=lambda item: item.chunk_index)
            chunk_texts = [chunk.content or "" for chunk in chunks]
            normalized = latest_version.normalized_content or {}
            skill_entries = normalized.get("skills") or []
            project_entries = normalized.get("projects") or []
            blobs = [
                *chunk_texts,
                *(_flatten_strings(normalized.get("experience"))),
                *(_flatten_strings(normalized.get("education"))),
                *(_flatten_strings(normalized.get("certifications"))),
                *(_flatten_strings(normalized.get("summary"))),
            ]
            for requirement in required_skills:
                terms = self._requirement_search_terms(requirement)
                if not terms:
                    continue
                matched = False
                skill_list_match = False
                for entry in skill_entries:
                    if self._matches_skill(str(entry), requirement):
                        skill_list_match = True
                        evidence[requirement.skill_slug].append(
                            SkillGapEvidenceRecord(
                                skill_slug=requirement.skill_slug,
                                skill_name=requirement.skill_name,
                                evidence_type="resume_skill",
                                source_table="resume_versions",
                                source_id=str(latest_version.id),
                                source_url=None,
                                evidence_strength="weak",
                                supports_status="evidenced",
                                quote_or_snippet=f"Resume skills list matched for {resume.filename}",
                                metadata_json={
                                    "resume_id": resume.id,
                                    "resume_filename": resume.filename,
                                    "version_id": latest_version.id,
                                },
                                confidence="low",
                                source_title=resume.filename,
                            )
                        )
                        matched = True
                        break
                if skill_list_match:
                    continue
                for blob_index, blob in enumerate(blobs):
                    if not blob or not any(term in _normalize_text(blob) for term in terms):
                        continue
                    evidence[requirement.skill_slug].append(
                        SkillGapEvidenceRecord(
                            skill_slug=requirement.skill_slug,
                            skill_name=requirement.skill_name,
                            evidence_type="resume_chunk",
                            source_table="resume_chunks",
                            source_id=str(chunks[blob_index].id) if blob_index < len(chunks) else str(latest_version.id),
                            source_url=None,
                            evidence_strength="weak",
                            supports_status="evidenced",
                            quote_or_snippet=f"Resume chunk matched for {resume.filename}",
                            metadata_json={
                                "resume_id": resume.id,
                                "resume_filename": resume.filename,
                                "version_id": latest_version.id,
                                "chunk_index": blob_index if blob_index < len(chunks) else None,
                            },
                            confidence="low",
                            source_title=resume.filename,
                        )
                    )
                    matched = True
                    break
                if matched:
                    continue
        return evidence

    async def collect_project_evidence(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        required_skills: list[SkillGapRequirement],
    ) -> dict[str, list[SkillGapEvidenceRecord]]:
        if not required_skills:
            return {}
        evidence: dict[str, list[SkillGapEvidenceRecord]] = {item.skill_slug: [] for item in required_skills}
        resumes_result = await db.execute(select(Resume).where(Resume.user_id == user_id, Resume.deleted_at.is_(None)))
        resumes = resumes_result.scalars().all()
        for resume in resumes:
            versions_result = await db.execute(select(ResumeVersion).where(ResumeVersion.resume_id == resume.id, ResumeVersion.deleted_at.is_(None)))
            versions = list(versions_result.scalars().all())
            if not versions:
                continue
            latest_version = sorted(versions, key=lambda item: (item.created_at or _now(), item.version_num, item.id), reverse=True)[0]
            normalized = latest_version.normalized_content or {}
            project_entries = normalized.get("projects") or []
            for requirement in required_skills:
                terms = self._requirement_search_terms(requirement)
                if not terms:
                    continue
                for project in project_entries:
                    project_text = _combine_text(
                        project.get("name"),
                        project.get("title"),
                        project.get("description"),
                        " ".join(project.get("tech_stack") or []),
                    )
                    if not project_text:
                        continue
                    normalized_project = _normalize_text(project_text)
                    if not any(term in normalized_project for term in terms):
                        continue
                    evidence[requirement.skill_slug].append(
                        SkillGapEvidenceRecord(
                            skill_slug=requirement.skill_slug,
                            skill_name=requirement.skill_name,
                            evidence_type="resume_project",
                            source_table="resume_versions",
                            source_id=str(latest_version.id),
                            source_url=None,
                            evidence_strength="medium",
                            supports_status="evidenced",
                            quote_or_snippet=f"Resume project entry matched for {resume.filename}",
                            metadata_json={
                                "resume_id": resume.id,
                                "resume_filename": resume.filename,
                                "version_id": latest_version.id,
                                "project_name": project.get("name") or project.get("title"),
                                "tech_stack": project.get("tech_stack") or [],
                            },
                            confidence="medium",
                            source_title=project.get("name") or project.get("title") or resume.filename,
                        )
                    )
                    break
        return evidence

    async def collect_learning_evidence(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        required_skills: list[SkillGapRequirement],
    ) -> dict[str, list[SkillGapEvidenceRecord]]:
        if not required_skills:
            return {}
        skill_slugs = [item.skill_slug for item in required_skills]
        evidence: dict[str, list[SkillGapEvidenceRecord]] = {item.skill_slug: [] for item in required_skills}

        sessions_result = await db.execute(
            select(LearningSession).where(LearningSession.user_id == user_id, LearningSession.skill_slug.in_(skill_slugs))
        )
        for session in sessions_result.scalars().all():
            if session.status == "opened" and float(session.completion_percentage or 0.0) <= 0.0:
                evidence[session.skill_slug].append(
                    SkillGapEvidenceRecord(
                        skill_slug=session.skill_slug,
                        skill_name=next((item.skill_name for item in required_skills if item.skill_slug == session.skill_slug), canonical_display_name(session.skill_slug)),
                        evidence_type="learning_session",
                        source_table="learning_sessions",
                        source_id=session.session_uid,
                        source_url=session.external_resource_url,
                        evidence_strength="weak",
                        supports_status="insufficient_data",
                        quote_or_snippet=f"Learning resource opened for {session.skill_slug}",
                        metadata_json={
                            "session_uid": session.session_uid,
                            "status": session.status,
                            "completion_percentage": float(session.completion_percentage or 0.0),
                            "resource_id": session.resource_id,
                            "provenance_uid": session.provenance_uid,
                        },
                        confidence="low",
                        source_title=session.skill_slug,
                    )
                )
                continue
            supports_status = "learning" if session.status in {"opened", "in_progress", "abandoned"} else "evidenced"
            evidence_strength = "medium" if session.status != "completed" else "strong"
            evidence[session.skill_slug].append(
                SkillGapEvidenceRecord(
                    skill_slug=session.skill_slug,
                    skill_name=next((item.skill_name for item in required_skills if item.skill_slug == session.skill_slug), canonical_display_name(session.skill_slug)),
                    evidence_type="learning_session",
                    source_table="learning_sessions",
                    source_id=session.session_uid,
                    source_url=session.external_resource_url,
                    evidence_strength=evidence_strength,
                    supports_status=supports_status,
                    quote_or_snippet=f"Learning session status={session.status}",
                    metadata_json={
                        "session_uid": session.session_uid,
                        "status": session.status,
                        "completion_percentage": float(session.completion_percentage or 0.0),
                        "resource_id": session.resource_id,
                        "job_id": session.job_id,
                        "started_at": session.started_at.isoformat() if session.started_at else None,
                        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                    },
                    confidence=_confidence_for_strength(evidence_strength, 1),
                    source_title=session.skill_slug,
                )
            )

        activity_result = await db.execute(
            select(LearningActivityEvent).where(LearningActivityEvent.user_id == user_id, LearningActivityEvent.skill_slug.in_(skill_slugs))
        )
        for event in activity_result.scalars().all():
            if event.event_type in {"ResourceStarted", "ResourceProgressUpdated", "ResourceCompleted", "ResourceAbandoned", "ResourceFeedbackSubmitted"}:
                supports_status = "learning" if event.event_type in {"ResourceStarted", "ResourceProgressUpdated", "ResourceAbandoned"} else "evidenced"
                evidence_strength = "medium" if event.event_type != "ResourceCompleted" else "strong"
            else:
                supports_status = "insufficient_data"
                evidence_strength = "weak"
            evidence[event.skill_slug].append(
                SkillGapEvidenceRecord(
                    skill_slug=event.skill_slug,
                    skill_name=next((item.skill_name for item in required_skills if item.skill_slug == event.skill_slug), canonical_display_name(event.skill_slug)),
                    evidence_type="learning_activity",
                    source_table="learning_activity_events",
                    source_id=event.activity_uid,
                    source_url=None,
                    evidence_strength=evidence_strength,
                    supports_status=supports_status,
                    quote_or_snippet=f"Learning activity event {event.event_type}",
                    metadata_json={
                        "activity_uid": event.activity_uid,
                        "event_type": event.event_type,
                        "session_uid": event.session_uid,
                        "resource_id": event.resource_id,
                        "job_id": event.job_id,
                    },
                    confidence=_confidence_for_strength(evidence_strength, 1),
                    source_title=event.skill_slug,
                )
            )

        feedback_result = await db.execute(
            select(ResourceFeedback).where(ResourceFeedback.user_id == user_id, ResourceFeedback.skill_slug.in_(skill_slugs))
        )
        for feedback in feedback_result.scalars().all():
            evidence[feedback.skill_slug].append(
                SkillGapEvidenceRecord(
                    skill_slug=feedback.skill_slug,
                    skill_name=next((item.skill_name for item in required_skills if item.skill_slug == feedback.skill_slug), canonical_display_name(feedback.skill_slug)),
                    evidence_type="resource_feedback",
                    source_table="resource_feedback",
                    source_id=feedback.feedback_uid,
                    source_url=None,
                    evidence_strength="medium",
                    supports_status="evidenced",
                    quote_or_snippet="Learning feedback submitted",
                    metadata_json={
                        "feedback_uid": feedback.feedback_uid,
                        "rating": float(feedback.rating) if feedback.rating is not None else None,
                        "would_recommend": feedback.would_recommend,
                        "outcome_tag": feedback.outcome_tag,
                        "resource_id": feedback.resource_id,
                        "session_uid": feedback.session_uid,
                    },
                    confidence="medium",
                    source_title=feedback.skill_slug,
                )
            )

        return evidence

    async def collect_outcome_evidence(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        required_skills: list[SkillGapRequirement],
    ) -> dict[str, list[SkillGapEvidenceRecord]]:
        if not required_skills:
            return {}
        skill_slugs = [item.skill_slug for item in required_skills]
        evidence: dict[str, list[SkillGapEvidenceRecord]] = {item.skill_slug: [] for item in required_skills}
        result = await db.execute(select(ResourceOutcome).where(ResourceOutcome.skill_slug.in_(skill_slugs)))
        for outcome in result.scalars().all():
            supports_status = "evidenced" if int(outcome.started_count or 0) > 0 else "insufficient_data"
            strength = "medium" if supports_status == "evidenced" else "weak"
            evidence[outcome.skill_slug].append(
                SkillGapEvidenceRecord(
                    skill_slug=outcome.skill_slug,
                    skill_name=next((item.skill_name for item in required_skills if item.skill_slug == outcome.skill_slug), canonical_display_name(outcome.skill_slug)),
                    evidence_type="resource_outcome",
                    source_table="resource_outcomes",
                    source_id=str(outcome.id),
                    source_url=None,
                    evidence_strength=strength,
                    supports_status=supports_status,
                    quote_or_snippet=f"Outcome status={outcome.status}",
                    metadata_json={
                        "resource_id": outcome.resource_id,
                        "provenance_uid": outcome.provenance_uid,
                        "started_count": int(outcome.started_count or 0),
                        "completion_count": int(outcome.completion_count or 0),
                        "feedback_count": int(outcome.feedback_count or 0),
                        "status": outcome.status,
                    },
                    confidence=_confidence_for_strength(strength, 1),
                    source_title=outcome.skill_slug,
                )
            )
        return evidence

    async def collect_provenance_evidence(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        required_skills: list[SkillGapRequirement],
    ) -> dict[str, list[SkillGapEvidenceRecord]]:
        if not required_skills:
            return {}
        skill_slugs = [item.skill_slug for item in required_skills]
        evidence: dict[str, list[SkillGapEvidenceRecord]] = {item.skill_slug: [] for item in required_skills}
        result = await db.execute(
            select(ResourceProvenanceRecord).where(
                ResourceProvenanceRecord.skill_slug.in_(skill_slugs),
                (ResourceProvenanceRecord.user_id == user_id) | (ResourceProvenanceRecord.user_id.is_(None)),
            )
        )
        for record in result.scalars().all():
            evidence[record.skill_slug].append(
                SkillGapEvidenceRecord(
                    skill_slug=record.skill_slug,
                    skill_name=record.skill_name,
                    evidence_type="resource_provenance",
                    source_table="learning_resource_provenance_records",
                    source_id=record.provenance_uid,
                    source_url=record.source_url,
                    evidence_strength="medium",
                    supports_status="evidenced",
                    quote_or_snippet=f"Provenance record {record.provenance_type}",
                    metadata_json={
                        "provenance_uid": record.provenance_uid,
                        "resource_id": record.resource_id,
                        "discovery_run_id": record.discovery_run_id,
                        "source_entity_type": record.source_entity_type,
                        "source_entity_id": record.source_entity_id,
                        "provenance_type": record.provenance_type,
                        "score_total": float(record.score_total or 0.0),
                        "confidence": record.confidence,
                    },
                    confidence=record.confidence or "medium",
                    source_title=record.title,
                )
            )
        return evidence

    async def collect_skill_graph_evidence(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        required_skills: list[SkillGapRequirement],
    ) -> dict[str, list[SkillGapEvidenceRecord]]:
        if not required_skills:
            return {}
        skill_slugs = [item.skill_slug for item in required_skills]
        evidence: dict[str, list[SkillGapEvidenceRecord]] = {item.skill_slug: [] for item in required_skills}

        state_result = await db.execute(
            select(UserSkillState, SkillGraphNode)
            .join(SkillGraphNode, SkillGraphNode.id == UserSkillState.skill_node_id)
            .where(UserSkillState.user_id == user_id, SkillGraphNode.skill_slug.in_(skill_slugs))
        )
        for state, node in state_result.all():
            if state.status == "validated":
                supports_status = "validated"
                strength = "strong"
            elif state.status in {"growing", "observed"}:
                supports_status = "evidenced" if int(state.completion_count or 0) > 0 else "learning"
                strength = "medium" if supports_status == "learning" else "medium"
            else:
                supports_status = "insufficient_data"
                strength = "weak"
            evidence[node.skill_slug].append(
                SkillGapEvidenceRecord(
                    skill_slug=node.skill_slug,
                    skill_name=node.skill_name,
                    evidence_type="user_skill_state",
                    source_table="user_skill_states",
                    source_id=state.state_uid,
                    source_url=None,
                    evidence_strength=strength,
                    supports_status=supports_status,
                    quote_or_snippet=f"Skill graph user state {state.status}",
                    metadata_json={
                        "state_uid": state.state_uid,
                        "status": state.status,
                        "confidence_score": float(state.confidence_score or 0.0),
                        "evidence_count": int(state.evidence_count or 0),
                        "started_count": int(state.started_count or 0),
                        "completion_count": int(state.completion_count or 0),
                        "feedback_count": int(state.feedback_count or 0),
                        "recommended_action": state.recommended_action,
                    },
                    confidence=_confidence_for_strength(strength, int(state.evidence_count or 0)),
                    source_title=node.skill_name,
                )
            )

        evidence_result = await db.execute(select(SkillGraphEvidence).where(SkillGraphEvidence.skill_node_id.is_not(None)))
        for row in evidence_result.scalars().all():
            metadata = row.metadata_ or {}
            if metadata.get("user_id") != user_id:
                continue
            if row.skill_node_id is None:
                continue
            node_skill = next((item for item in required_skills if item.skill_slug == row.normalized_value or item.skill_slug == row.skill_node_id), None)
            if node_skill is None:
                skill_node_result = await db.execute(select(SkillGraphNode).where(SkillGraphNode.id == row.skill_node_id))
                node = skill_node_result.scalar_one_or_none()
            else:
                node = None
            skill_slug = node.skill_slug if node is not None else row.normalized_value
            skill_name = node.skill_name if node is not None else next((item.skill_name for item in required_skills if item.skill_slug == skill_slug), canonical_display_name(skill_slug))
            if skill_slug not in evidence:
                evidence[skill_slug] = []
            source_type = row.source_entity_type
            if source_type in {"learning_session", "learning_activity"}:
                supports_status = "learning"
            elif source_type in {"resource_feedback", "resource_outcome", "resource_provenance", "resume_chunk"}:
                supports_status = "evidenced"
            elif source_type == "roadmap_task":
                supports_status = "learning"
            else:
                supports_status = "insufficient_data"
            strength = "medium" if supports_status != "insufficient_data" else "weak"
            evidence[skill_slug].append(
                SkillGapEvidenceRecord(
                    skill_slug=skill_slug,
                    skill_name=skill_name,
                    evidence_type="skill_graph_evidence",
                    source_table=row.source_table,
                    source_id=row.evidence_uid,
                    source_url=row.source_url,
                    evidence_strength=strength,
                    supports_status=supports_status,
                    quote_or_snippet=f"Skill graph evidence {row.evidence_kind}",
                    metadata_json={
                        "evidence_uid": row.evidence_uid,
                        "source_entity_type": row.source_entity_type,
                        "source_entity_id": row.source_entity_id,
                        "source_field": row.source_field,
                        "source_title": row.source_title,
                        "provider": row.provider,
                        "evidence_kind": row.evidence_kind,
                        "trust_score": float(row.trust_score or 0.0),
                        "relevance_score": float(row.relevance_score or 0.0),
                        "freshness_score": float(row.freshness_score or 0.0),
                        "confidence": row.confidence,
                        "status": row.status,
                    },
                    confidence=row.confidence or _confidence_for_strength(strength, 1),
                    source_title=row.source_title,
                )
            )
        return evidence

    async def build_absence_evidence(
        self,
        *,
        requirement: SkillGapRequirement,
        searched_sources: list[str],
    ) -> list[SkillGapEvidenceRecord]:
        return [
            SkillGapEvidenceRecord(
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
                confidence="medium" if requirement.source_strength == "strong" else "low",
                source_title=requirement.source_title,
            )
        ]


_SERVICE: SkillGapEvidenceService | None = None


def get_skill_gap_evidence_service() -> SkillGapEvidenceService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = SkillGapEvidenceService()
    return _SERVICE
