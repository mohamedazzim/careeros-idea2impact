"""Resume-centric job intelligence for real-provider opportunity discovery."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jobs import Job, JobMatch
from src.models.knowledge import KnowledgeDoc


SKILL_ALIASES: Dict[str, List[str]] = {
    "python": ["python"],
    "sql": ["sql", "mysql", "postgresql", "sqlite"],
    "power bi": ["power bi", "powerbi"],
    "machine learning": ["machine learning", "ml", "ai/ml"],
    "ai": ["artificial intelligence", " ai ", "ai/ml"],
    "generative ai": ["generative ai", "genai", "llm", "large language model"],
    "tensorflow": ["tensorflow"],
    "pytorch": ["pytorch"],
    "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "matplotlib": ["matplotlib"],
    "nlp": ["nlp", "natural language processing"],
    "fastapi": ["fastapi"],
    "django": ["django"],
    "docker": ["docker"],
    "excel": ["excel", "ms excel"],
}


REAL_PROVIDER_CATALOG = [
    {
        "name": "theirstack",
        "display_name": "TheirStack",
        "supported_mode": "direct_provider_api",
    },
    {
        "name": "remoteok",
        "display_name": "RemoteOK",
        "supported_mode": "direct_provider_api",
    },
    {
        "name": "arbeitnow",
        "display_name": "Arbeitnow",
        "supported_mode": "direct_provider_api",
    },
    {
        "name": "adzuna",
        "display_name": "Adzuna",
        "supported_mode": "direct_provider_api",
    },
    {
        "name": "usajobs",
        "display_name": "USAJobs",
        "supported_mode": "direct_provider_api",
    },
    {
        "name": "greenhouse",
        "display_name": "Greenhouse",
        "supported_mode": "direct_provider_api",
    },
    {
        "name": "lever",
        "display_name": "Lever",
        "supported_mode": "direct_provider_api",
    },
]

PLACEHOLDER_RESUME_TEXTS = {
    "extracting document binary securely...",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def has_meaningful_resume_content(content: Optional[str]) -> bool:
    stripped = (content or "").strip()
    if not stripped:
        return False
    if _norm(stripped) in PLACEHOLDER_RESUME_TEXTS:
        return False
    return len(stripped) >= 50 and len(stripped.split()) >= 5


def _contains_any(text: str, aliases: Iterable[str]) -> bool:
    haystack = f" {_norm(text)} "
    return any(re.search(r"(?<![a-z0-9])" + re.escape(alias.lower().strip()) + r"(?![a-z0-9])", haystack) for alias in aliases)


def _extract_skills(text: str) -> List[str]:
    found = []
    for skill, aliases in SKILL_ALIASES.items():
        if _contains_any(text, aliases):
            found.append(skill)
    return found


def _token_set(text: str) -> set[str]:
    stop = {"and", "the", "with", "for", "from", "this", "that", "role", "job", "candidate", "skills"}
    return {t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}", _norm(text)) if t not in stop}


class JobIntelligenceService:
    def provider_catalog(self) -> List[Dict[str, Any]]:
        return REAL_PROVIDER_CATALOG

    async def get_active_resume(
        self,
        db: AsyncSession,
        user_id: str,
        resume_id: Optional[str] = None,
    ) -> Optional[KnowledgeDoc]:
        conditions = [
            KnowledgeDoc.user_id == user_id,
            KnowledgeDoc.deleted_at.is_(None),
            KnowledgeDoc.status.in_(["indexed", "analyzed"]),
        ]
        if resume_id:
            conditions.append(KnowledgeDoc.doc_uid == resume_id)
        limit = 1 if resume_id else 25
        stmt = select(KnowledgeDoc).where(*conditions).order_by(KnowledgeDoc.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        if resume_id:
            candidate = result.scalar_one_or_none()
            return candidate if candidate and has_meaningful_resume_content(candidate.content) else None

        for candidate in result.scalars().all():
            if has_meaningful_resume_content(candidate.content):
                return candidate
        return None

    def resume_profile(self, resume: Optional[KnowledgeDoc]) -> Dict[str, Any]:
        if not resume:
            return {
                "status": "missing",
                "message": "No indexed resume selected.",
                "skills": [],
            }
        content = resume.content or ""
        if not has_meaningful_resume_content(content):
            return {
                "status": "missing",
                "message": "Selected resume has no extractable content. Re-upload the original file.",
                "skills": [],
                "doc_id": resume.doc_uid,
                "name": resume.title,
            }
        skills = _extract_skills(content)
        education = []
        if _contains_any(content, ["mca"]):
            education.append("MCA")
        if _contains_any(content, ["bca"]):
            education.append("BCA")
        location = "Kerala" if _contains_any(content, ["kerala"]) else "Not stated"
        return {
            "status": resume.status,
            "doc_id": resume.doc_uid,
            "name": resume.title,
            "upload_date": resume.created_at.isoformat() if resume.created_at else None,
            "chunk_count": int(resume.chunk_count or 0),
            "embedding_status": "indexed" if resume.status in ("indexed", "analyzed") else resume.status,
            "vector_count": int(resume.chunk_count or 0),
            "skills": skills,
            "education": education,
            "location": location,
            "experience_years": self._experience_years(content),
            "content": content,
        }

    async def ensure_india_jobs(
        self,
        db: AsyncSession,
        resume_profile: Dict[str, Any],
        preferences: Dict[str, Any] | None = None,
    ) -> int:
        return 0

    async def recalculate_matches(
        self,
        db: AsyncSession,
        user_id: str,
        resume: KnowledgeDoc,
        limit: int = 600,
    ) -> Dict[str, Any]:
        profile = self.resume_profile(resume)
        stmt = select(Job).where(
            Job.status == "active",
            Job.deleted_at.is_(None),
            Job.is_india_eligible == True,
            Job.is_tech_role == True,
            Job.apply_url.is_not(None),
            Job.apply_url != "",
            Job.lifecycle_state.notin_(["APPLIED", "INTERVIEWING", "OFFERED", "HIRED", "EXPIRED"]),
            (Job.freshness_bucket.is_(None) | (Job.freshness_bucket != "stale")),
        ).limit(limit)
        result = await db.execute(stmt)
        jobs = result.scalars().all()
        evaluated = 0
        for job in jobs:
            details = self.score_job(profile, job)
            source_job_id = job.source_job_id or job.job_uid
            existing_stmt = select(JobMatch).where(
                JobMatch.user_id == user_id,
                JobMatch.source_job_id == source_job_id,
                JobMatch.resume_doc_uid == resume.doc_uid,
            )
            existing_result = await db.execute(existing_stmt)
            match = existing_result.scalar_one_or_none()
            strengths = [
                {"id": f"{job.job_uid}-{c['key']}", "title": c["label"], "impact": "high" if c["score"] >= 80 else "medium", "description": c["reason"]}
                for c in details["components"]
                if c["score"] >= 70
            ][:6]
            gaps = [
                {"id": f"{job.job_uid}-{c['key']}", "category": c["label"], "severity": "high" if c["score"] < 40 else "medium", "description": ", ".join(c["missing"]) or c["reason"], "suggestion": c["suggestion"]}
                for c in details["components"]
                if c["score"] < 70 or c["missing"]
            ][:6]
            if match:
                match.job_id = job.id
                match.source_provider = job.source
                match.source_url = job.source_url
                match.ingested_at = job.ingested_at
                match.overall_score = details["overall_match"]
                match.skill_match = details["dimensions"]["skill_match"]
                match.experience_match = details["dimensions"]["experience_match"]
                match.education_match = details["dimensions"]["education_match"]
                match.gap_score = 100.0 - details["overall_match"]
                match.strengths = strengths
                match.gaps = gaps
                match.recommendation = details["reason"]
                match.match_details = details
                match.resume_doc_uid = resume.doc_uid
                match.resume_name = resume.title
            else:
                db.add(JobMatch(
                    user_id=user_id,
                    job_id=job.id,
                    source_job_id=source_job_id,
                    source_provider=job.source,
                    source_url=job.source_url,
                    ingested_at=job.ingested_at,
                    overall_score=details["overall_match"],
                    skill_match=details["dimensions"]["skill_match"],
                    experience_match=details["dimensions"]["experience_match"],
                    education_match=details["dimensions"]["education_match"],
                    gap_score=100.0 - details["overall_match"],
                    strengths=strengths,
                    gaps=gaps,
                    recommendation=details["reason"],
                    match_details=details,
                    resume_doc_uid=resume.doc_uid,
                    resume_name=resume.title,
                ))
            job.match_score = details["overall_match"]
            job.match_details = details
            job.opportunity_priority_score = details["opportunity_priority_score"]
            evaluated += 1
        await db.commit()
        return {"evaluated": evaluated, "resume": self.resume_profile(resume)}

    def score_job(self, profile: Dict[str, Any], job: Job) -> Dict[str, Any]:
        from src.services.intelligence.career_domain_classifier import get_career_domain_classifier
        from src.services.intelligence.deadline_intelligence import get_deadline_intelligence

        resume_text = profile.get("content", "")
        job_text = " ".join([
            job.title or "",
            job.company or "",
            job.location or "",
            job.description or "",
            " ".join(job.skills_required or []),
        ])
        resume_skills = set(profile.get("skills", []))
        job_skills = set(job.skills_required or _extract_skills(job_text))
        matched_skills = sorted(resume_skills & job_skills)
        missing_skills = sorted(job_skills - resume_skills)

        # Domain classification
        classifier = get_career_domain_classifier()
        job_class = classifier.classify_job(job.title or "", job.description or "", list(job_skills))
        resume_class = classifier.classify_resume(resume_text, list(resume_skills), profile.get("target_role", ""))
        domain_score, domain_reason = classifier.calculate_domain_alignment(
            resume_class["career_family"],
            job_class["career_family"],
        )

        # Deadline intelligence
        deadline_intel = get_deadline_intelligence()
        posted_date = job.posted_date if hasattr(job, 'posted_date') else None
        deadline_info = deadline_intel.extract_deadline(
            job_title=job.title or "",
            job_description=job.description or "",
            posted_date=posted_date,
        )

        # If completely unrelated domain, cap score at 15
        if domain_score == 0:
            return {
                "overall_match": 15.0,
                "dimensions": {k: 0.0 for k in ["education_match", "skill_match", "project_match", "experience_match", "certification_match", "location_match", "keyword_match", "semantic_similarity"]},
                "weights": {},
                "components": [{
                    "key": "domain_alignment",
                    "label": "Domain Alignment",
                    "score": 0.0,
                    "weight": 1.0,
                    "contribution": 0.0,
                    "evidence": [f"Resume: {resume_class['family_display']}, Job: {job_class['family_display']}"],
                    "missing": [],
                    "reason": f"Unrelated domains: resume={resume_class['career_family']}, job={job_class['career_family']}",
                    "suggestion": "Focus on jobs matching your career domain.",
                }],
                "resume_extraction": {"skills": sorted(resume_skills), "education": profile.get("education", []), "location": profile.get("location"), "experience_years": profile.get("experience_years", 0)},
                "job_extraction": {"skills": sorted(job_skills), "source_provider": job.source_provider or job.source, "source_job_id": job.source_job_id, "apply_url": job.apply_url or job.source_url},
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "semantic_similarity": 0.0,
                "semantic_evidence": [],
                "education_evidence": [],
                "experience_evidence": [],
                "confidence": 0.85,
                "estimated_score_improvement": {"points": 0.0, "projected_score": 15.0, "explanation": "Domain mismatch - cannot improve by adding skills."},
                "estimated_learning_time": "N/A",
                "below_40_explanation": f"Domain mismatch: resume is {resume_class['family_display']}, job is {job_class['family_display']}.",
                "freshness_score": float(job.freshness_score if job.freshness_score is not None else 50.0),
                "freshness_bucket": job.freshness_bucket,
                "provider_quality_score": float(job.provider_quality_score or self._provider_quality(job.source_provider or job.source)),
                "salary_quality_score": float(job.salary_quality_score if job.salary_quality_score is not None else (90.0 if job.salary_range else 30.0)),
                "apply_url_valid": bool(job.apply_url_valid),
                "opportunity_priority_score": 15.0,
                "reason": f"Domain mismatch: resume={resume_class['family_display']}, job={job_class['family_display']}. Score capped at 15%.",
                "active_resume": {k: v for k, v in profile.items() if k != "content"},
                "calculated_at": datetime.utcnow().isoformat(),
                "career_domain": job_class["career_domain"],
                "career_family": job_class["career_family"],
                "resume_career_family": resume_class["career_family"],
                "domain_alignment_score": domain_score,
                "domain_alignment_reason": domain_reason,
                "application_deadline": deadline_info["application_deadline"],
                "deadline_source": deadline_info["deadline_source"],
                "deadline_confidence": deadline_info["deadline_confidence"],
                "deadline_status": deadline_info["deadline_status"],
                "hours_until_deadline": deadline_info["hours_until_deadline"],
                "deadline_display": deadline_info["deadline_display"],
            }

        dimensions = {
            "education_match": self._education_score(resume_text, job_text),
            "skill_match": self._ratio_score(len(matched_skills), len(job_skills), 60.0),
            "project_match": self._project_score(resume_text, job_text),
            "experience_match": self._experience_score(profile, job_text),
            "certification_match": self._certification_score(resume_text, job_text),
            "location_match": self._location_score(resume_text, job.location or job_text),
            "keyword_match": self._keyword_score(resume_text, job_text),
            "semantic_similarity": self._semantic_score(resume_text, job_text),
        }
        weights = {
            "education_match": 0.15,
            "skill_match": 0.25,
            "project_match": 0.15,
            "experience_match": 0.15,
            "certification_match": 0.10,
            "location_match": 0.08,
            "keyword_match": 0.07,
            "semantic_similarity": 0.05,
        }
        overall = round(sum(dimensions[k] * weights[k] for k in weights), 1)

        # Apply domain alignment boost/penalty
        if domain_score == 100:
            overall = min(100.0, overall * 1.1)  # 10% boost for same family
        elif domain_score == 50:
            overall = overall * 0.9  # 10% penalty for adjacent family

        overall = round(overall, 1)
        provider_quality_score = float(job.provider_quality_score or self._provider_quality(job.source_provider or job.source))
        freshness_score = float(job.freshness_score if job.freshness_score is not None else 50.0)
        salary_quality_score = float(job.salary_quality_score if job.salary_quality_score is not None else (90.0 if job.salary_range else 30.0))
        apply_url_score = 100.0 if (job.apply_url_valid is not False and (job.apply_url or "").strip()) else 0.0
        opportunity_priority_score = round(
            overall * 0.55
            + freshness_score * 0.20
            + provider_quality_score * 0.15
            + salary_quality_score * 0.05
            + apply_url_score * 0.05,
            1,
        )
        components = []
        labels = {
            "education_match": "Education Match",
            "skill_match": "Skill Match",
            "project_match": "Project Match",
            "experience_match": "Experience Match",
            "certification_match": "Certification Match",
            "location_match": "Location Match",
            "keyword_match": "Keyword Match",
            "semantic_similarity": "Semantic Similarity",
        }
        evidence = self._evidence(resume_text, job_text, matched_skills, missing_skills)
        for key, label in labels.items():
            score = round(dimensions[key], 1)
            components.append({
                "key": key,
                "label": label,
                "score": score,
                "weight": weights[key],
                "contribution": round(score * weights[key], 1),
                "evidence": evidence.get(key, []),
                "missing": self._missing_for(key, missing_skills, resume_text, job_text),
                "reason": self._reason_for(key, score, evidence.get(key, [])),
                "suggestion": self._suggestion_for(key),
            })
        return {
            "overall_match": overall,
            "dimensions": dimensions,
            "weights": weights,
            "components": components,
            "resume_extraction": {
                "skills": sorted(resume_skills),
                "education": profile.get("education", []),
                "location": profile.get("location"),
                "experience_years": profile.get("experience_years", 0),
            },
            "job_extraction": {
                "skills": sorted(job_skills),
                "source_provider": job.source_provider or job.source,
                "source_job_id": job.source_job_id,
                "apply_url": job.apply_url or job.source_url,
            },
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "semantic_similarity": dimensions["semantic_similarity"],
            "semantic_evidence": self._semantic_evidence(resume_text, job_text),
            "education_evidence": evidence.get("education_match", []),
            "experience_evidence": evidence.get("experience_match", []),
            "confidence": self._confidence(overall, len(matched_skills), len(job_skills)),
            "estimated_score_improvement": self._estimated_improvement(dimensions, weights, missing_skills, len(job_skills)),
            "estimated_learning_time": self._estimated_learning_time(missing_skills),
            "below_40_explanation": self._below_40_explanation(overall, components, missing_skills),
            "freshness_score": freshness_score,
            "freshness_bucket": job.freshness_bucket,
            "provider_quality_score": provider_quality_score,
            "salary_quality_score": salary_quality_score,
            "apply_url_valid": bool(apply_url_score),
            "opportunity_priority_score": opportunity_priority_score,
            "reason": self._top_reason(overall, matched_skills, missing_skills, components),
            "active_resume": {k: v for k, v in profile.items() if k != "content"},
            "calculated_at": datetime.utcnow().isoformat(),
            "career_domain": job_class["career_domain"],
            "career_family": job_class["career_family"],
            "resume_career_family": resume_class["career_family"],
            "domain_alignment_score": domain_score,
            "domain_alignment_reason": domain_reason,
            "application_deadline": deadline_info["application_deadline"],
            "deadline_source": deadline_info["deadline_source"],
            "deadline_confidence": deadline_info["deadline_confidence"],
            "deadline_status": deadline_info["deadline_status"],
            "hours_until_deadline": deadline_info["hours_until_deadline"],
            "deadline_display": deadline_info["deadline_display"],
        }

    def _provider_quality(self, source: str) -> float:
        source = (source or "").lower()
        if source in {"theirstack", "greenhouse", "lever", "ashby"}:
            return 95.0
        if source == "remoteok":
            return 85.0
        return 50.0

    def _confidence(self, overall: float, matched_count: int, total_count: int) -> float:
        coverage = matched_count / total_count if total_count else 0.5
        return round(min(0.98, max(0.35, (overall / 100) * 0.65 + coverage * 0.35)), 2)

    def _estimated_learning_time(self, missing_skills: List[str]) -> str:
        if not missing_skills:
            return "0 weeks"
        weeks = min(12, max(1, len(missing_skills) * 2))
        return f"{weeks} weeks"

    def _semantic_evidence(self, resume_text: str, job_text: str) -> List[str]:
        resume_tokens = _token_set(resume_text)
        job_tokens = _token_set(job_text)
        shared = sorted((resume_tokens & job_tokens), key=len, reverse=True)
        return shared[:8]

    def summary(self, resume_profile: Dict[str, Any], matches: List[JobMatch]) -> Dict[str, Any]:
        if resume_profile.get("status") == "missing":
            return {
                "active_resume": None,
                "message": "No indexed resume selected.",
                "jobs_evaluated": 0,
                "average_match": None,
                "highest_match": None,
                "lowest_match": None,
                "last_calculated": None,
            }
        scores = [float(m.overall_score or 0) for m in matches]
        def calculated_at(match: JobMatch) -> str | None:
            details = match.match_details or {}
            value = details.get("calculated_at")
            if value:
                return str(value)
            return match.created_at.isoformat() if match.created_at else None

        last_calculated = max((v for v in (calculated_at(m) for m in matches) if v), default=None)
        return {
            "active_resume": {k: v for k, v in resume_profile.items() if k != "content"},
            "jobs_evaluated": len(scores),
            "average_match": round(sum(scores) / len(scores), 1) if scores else None,
            "highest_match": round(max(scores), 1) if scores else None,
            "lowest_match": round(min(scores), 1) if scores else None,
            "last_calculated": last_calculated,
        }

    def _ratio_score(self, matched: int, total: int, default: float) -> float:
        return round((matched / total) * 100, 1) if total else default

    def _education_score(self, resume: str, job: str) -> float:
        if _contains_any(job, ["mca", "b.tech", "btech", "be", "m.tech"]) and _contains_any(resume, ["mca", "bca", "b.tech", "btech", "be"]):
            return 90.0
        return 60.0

    def _project_score(self, resume: str, job: str) -> float:
        project_hits = sum(1 for term in ["project", "prediction", "chatbot", "attendance", "fake job", "readiness", "nlp"] if _contains_any(resume, [term]))
        framework_gap = sum(1 for term in ["tensorflow", "pytorch"] if _contains_any(job, [term]) and not _contains_any(resume, [term]))
        return max(0.0, min(100.0, 45 + project_hits * 8 - framework_gap * 10))

    def _experience_score(self, profile: Dict[str, Any], job: str) -> float:
        score = 55.0
        if profile.get("experience_years", 0) <= 1 and _contains_any(job, ["intern", "fresher", "trainee", "0 to 1", "entry"]):
            score += 25
        if _contains_any(profile.get("content", ""), ["internship", "developed", "processed"]):
            score += 10
        if _contains_any(job, ["generative ai"]) and not _contains_any(profile.get("content", ""), ["generative ai"]):
            score -= 20
        return max(0.0, min(100.0, score))

    def _certification_score(self, resume: str, job: str) -> float:
        hits = sum(1 for term in ["certification", "data science", "machine learning", "python programming", "data visualization"] if _contains_any(resume, [term]))
        return min(100.0, hits * 25.0) if _contains_any(job, ["certified", "certification", "course"]) else min(85.0, hits * 25.0)

    def _location_score(self, resume: str, location: str) -> float:
        loc = _norm(location)
        if "remote india" in loc or loc == "india":
            return 80.0
        if "kerala" in loc:
            if _contains_any(resume, ["kerala", "relocate", "relocation", "willing to relocate"]):
                return 100.0
            return 20.0
        if any(city in loc for city in ["india", "bengaluru", "chennai", "hyderabad", "kochi"]):
            return 60.0
        return 40.0

    def _keyword_score(self, resume: str, job: str) -> float:
        job_keywords = _extract_skills(job)
        resume_keywords = _extract_skills(resume)
        return self._ratio_score(len(set(job_keywords) & set(resume_keywords)), len(set(job_keywords)), 50.0)

    def _semantic_score(self, resume: str, job: str) -> float:
        a = _token_set(resume)
        b = _token_set(job)
        if not a or not b:
            return 50.0
        return round((len(a & b) / len(a | b)) * 100, 1)

    def _experience_years(self, resume: str) -> float:
        if _contains_any(resume, ["internship", "intern"]):
            return 0.5
        years = [float(v) for v in re.findall(r"(\d+(?:\.\d+)?)\s*(?:years|yrs)", resume, re.I)]
        return max(years) if years else 0.0

    def _evidence(self, resume: str, job: str, matched_skills: List[str], missing_skills: List[str]) -> Dict[str, List[str]]:
        return {
            "education_match": ["MCA/BCA evidence present"] if _contains_any(resume, ["mca", "bca"]) else [],
            "skill_match": [f"{skill}: present" for skill in matched_skills],
            "project_match": [term for term in ["AI project", "NLP project", "Prediction project"] if _contains_any(resume, [term.split()[0]])],
            "experience_match": ["Internship experience present"] if _contains_any(resume, ["internship", "intern"]) else [],
            "certification_match": ["Relevant certification evidence present"] if _contains_any(resume, ["certification", "coursera", "data science"]) else [],
            "location_match": ["India-focused role"] if _contains_any(job, ["india", "kerala", "remote india"]) else [],
            "keyword_match": [f"{skill}: present" for skill in matched_skills[:6]],
            "semantic_similarity": ["Resume and JD share data/AI vocabulary"],
        }

    def _missing_for(self, key: str, missing_skills: List[str], resume: str, job: str) -> List[str]:
        if key in ("skill_match", "keyword_match"):
            return [f"{skill}: missing" for skill in missing_skills]
        if key == "location_match" and _contains_any(job, ["kerala"]) and not _contains_any(resume, ["kerala", "relocate", "relocation"]):
            return ["Kerala/relocation evidence missing"]
        if key == "experience_match" and _contains_any(job, ["generative ai"]) and not _contains_any(resume, ["generative ai"]):
            return ["Generative AI evidence partial/missing"]
        if key == "project_match":
            return [f"{skill} project evidence missing" for skill in missing_skills if skill in ("tensorflow", "pytorch", "generative ai")]
        return []

    def _reason_for(self, key: str, score: float, evidence: List[str]) -> str:
        if score >= 80:
            return f"Strong evidence: {', '.join(evidence[:3]) or 'requirements satisfied'}."
        if score >= 50:
            return "Partial evidence found; score reduced by missing or indirect proof."
        return "Weak explicit evidence for this requirement."

    def _suggestion_for(self, key: str) -> str:
        suggestions = {
            "skill_match": "Add truthful missing tools to skills and projects.",
            "project_match": "Add project bullets proving the required tools.",
            "experience_match": "Clarify internship scope, dates, and production exposure.",
            "location_match": "State relocation/India location preference explicitly.",
            "keyword_match": "Mirror important JD keywords when truthful.",
        }
        return suggestions.get(key, "Add explicit resume evidence and rerun matching.")

    def _top_reason(self, overall: float, matched: List[str], missing: List[str], components: List[Dict[str, Any]]) -> str:
        positives = ", ".join(matched[:4]) or "profile evidence"
        negatives = ", ".join(missing[:3]) or "few explicit gaps"
        return f"{overall}% because {positives} match the role; score is reduced by {negatives}."

    def _estimated_improvement(
        self,
        dimensions: Dict[str, float],
        weights: Dict[str, float],
        missing_skills: List[str],
        total_job_skills: int,
    ) -> Dict[str, Any]:
        if not missing_skills or not total_job_skills:
            before = round(sum(dimensions[k] * weights[k] for k in weights), 1)
            return {"points": 0.0, "projected_score": before, "explanation": "No explicit missing skills detected."}
        improved = dict(dimensions)
        improved["skill_match"] = 100.0
        improved["keyword_match"] = 100.0
        if any(skill in {"tensorflow", "pytorch", "generative ai"} for skill in missing_skills):
            improved["project_match"] = max(improved["project_match"], 75.0)
        before = sum(dimensions[k] * weights[k] for k in weights)
        after = sum(improved[k] * weights[k] for k in weights)
        points = round(max(0.0, after - before), 1)
        return {
            "points": points,
            "projected_score": round(after, 1),
            "after_closing_gaps": round(after, 1),
            "gaps_modeled": missing_skills[:8],
            "explanation": f"Adding truthful evidence for {', '.join(missing_skills[:5])} could add about {points} points.",
        }

    def _below_40_explanation(
        self,
        overall: float,
        components: List[Dict[str, Any]],
        missing_skills: List[str],
    ) -> str | None:
        if overall >= 40:
            return None
        weakest = sorted(components, key=lambda c: c.get("contribution", 0))[:3]
        weak_labels = ", ".join(c["label"] for c in weakest)
        gaps = ", ".join(missing_skills[:5]) or "limited explicit skill overlap"
        return f"Below 40 because the lowest contributing dimensions are {weak_labels}; missing or weak evidence includes {gaps}."


def get_job_intelligence_service() -> JobIntelligenceService:
    return JobIntelligenceService()
