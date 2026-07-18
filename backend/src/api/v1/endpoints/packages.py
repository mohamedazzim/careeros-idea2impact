"""Application Packages endpoint — structured resume, cover letter, outreach, interview guide.

Uses PackageRepository for persistence. Gemini Flash-backed with JSON repair and
deterministic fallback. Validates all LLM output against Pydantic schema.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.repositories.package_repository import PackageRepository
from src.db.repositories.domain_repositories import JobRepository
from src.db.repositories.knowledge_repository import KnowledgeRepository
from src.db.session import get_db
from src.schemas.package import (
    PackageContent,
    ResumeContent,
    ResumeHeader,
    ExperienceEntry,
    ProjectEntry,
    EducationEntry,
    CertificationEntry,
    CoverLetterContent,
    OutreachContent,
    InterviewGuideContent,
    PackageMetadata,
    build_deterministic_package,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/packages", tags=["Application Packages"])


class GeneratePackageRequest(BaseModel):
    job_id: str = Field(..., min_length=1)

    @field_validator("job_id", mode="before")
    @classmethod
    def coerce_job_id(cls, v):
        if v is None:
            raise ValueError("job_id is required")
        return str(v).strip()


def _pkg_response(pkg, *, display_title: str | None = None) -> dict:
    return {
        "id": pkg.package_uid,
        "user_id": pkg.user_id,
        "job_id": pkg.job_id,
        "title": display_title or pkg.title,
        "status": pkg.status,
        "resume_tailored": pkg.resume_tailored,
        "cover_letter": pkg.cover_letter,
        "outreach_message": pkg.outreach_message,
        "interview_guide": pkg.interview_guide,
        "readiness_summary": pkg.readiness_summary,
        "metadata": pkg.metadata_,
        "created_at": pkg.created_at.isoformat() if pkg.created_at else None,
        "updated_at": pkg.updated_at.isoformat() if pkg.updated_at else None,
    }


async def _resolve_job_record(job_repo, job_id: str):
    resolved_job = await job_repo.get_by_uid(job_id)
    if resolved_job:
        return resolved_job
    try:
        numeric_job_id = int(job_id)
    except (TypeError, ValueError):
        return None
    return await job_repo.get_by_id(numeric_job_id)


def _serialize_content(content: PackageContent) -> dict[str, str]:
    """Serialize PackageContent to string fields for DB persistence."""
    return {
        "resume_tailored": json.dumps(content.resume.model_dump(), default=str),
        "cover_letter": json.dumps(content.cover_letter.model_dump(), default=str),
        "outreach_message": json.dumps(content.outreach.model_dump(), default=str),
        "interview_guide": json.dumps(content.interview_guide.model_dump(), default=str),
    }


def _is_sparse_package_content(content: PackageContent) -> bool:
    resume = content.resume
    cover = content.cover_letter
    outreach = content.outreach
    interview = content.interview_guide
    meaningful_resume = any([
        any((resume.summary or [])),
        bool(resume.skills),
        any((resume.experience or [])),
        any((resume.projects or [])),
        any((resume.education or [])),
        any((resume.certifications or [])),
        any((resume.achievements or [])),
        any((resume.ats_keywords or [])),
    ])
    meaningful_non_resume = any([
        bool((cover.subject or "").strip()),
        bool((cover.body or "").strip()),
        bool((outreach.linkedin_message or "").strip()),
        bool((outreach.email_message or "").strip()),
        any((interview.likely_questions or [])),
        any((interview.talking_points or [])),
        any((interview.weaknesses_to_prepare or [])),
        any((interview.questions_to_ask or [])),
    ])
    return not (meaningful_resume or meaningful_non_resume)


def _deserialize_content(pkg) -> PackageContent | None:
    """Deserialize DB string fields back to PackageContent."""
    try:
        resume = json.loads(pkg.resume_tailored) if pkg.resume_tailored else {}
        if isinstance(resume, dict):
            resume_obj = ResumeContent(
                header=ResumeHeader(**(resume.get("header") or {})),
                summary=resume.get("summary") or [],
                skills=resume.get("skills") or {},
                experience=[ExperienceEntry(**e) for e in (resume.get("experience") or [])],
                projects=[ProjectEntry(**p) for p in (resume.get("projects") or [])],
                education=[EducationEntry(**e) for e in (resume.get("education") or [])],
                certifications=[CertificationEntry(**c) for c in (resume.get("certifications") or [])],
                achievements=resume.get("achievements") or [],
                ats_keywords=resume.get("ats_keywords") or [],
                quality_notes=resume.get("quality_notes") or [],
            )
        else:
            resume_obj = ResumeContent(summary=[str(resume)])
        cover = json.loads(pkg.cover_letter) if pkg.cover_letter else {}
        if isinstance(cover, dict):
            cover_obj = CoverLetterContent(**cover)
        else:
            cover_obj = CoverLetterContent(body=str(cover))
        outreach = json.loads(pkg.outreach_message) if pkg.outreach_message else {}
        if isinstance(outreach, dict):
            outreach_obj = OutreachContent(**outreach)
        else:
            outreach_obj = OutreachContent(linkedin_message=str(outreach))
        interview = json.loads(pkg.interview_guide) if pkg.interview_guide else {}
        if isinstance(interview, dict):
            interview_obj = InterviewGuideContent(**interview)
        else:
            interview_obj = InterviewGuideContent(likely_questions=[str(interview)])
        meta = pkg.metadata_ or {}
        if isinstance(meta, dict):
            meta_obj = PackageMetadata(**{k: v for k, v in meta.items() if k in PackageMetadata.model_fields})
        else:
            meta_obj = PackageMetadata()
        return PackageContent(resume=resume_obj, cover_letter=cover_obj, outreach=outreach_obj, interview_guide=interview_obj, metadata=meta_obj)
    except Exception:
        return None


def _collect_candidate_evidence(docs) -> dict[str, Any]:
    """Extract candidate evidence from Knowledge Hub docs."""
    skills: list[str] = []
    experience_parts: list[str] = []
    education: list[dict] = []
    for doc in docs:
        if doc.content:
            experience_parts.append(doc.content)
        meta = getattr(doc, "metadata_", None) or {}
        if isinstance(meta, dict):
            skills.extend(meta.get("skills", []))
            if meta.get("institution"):
                education.append({"degree": meta.get("degree", ""), "institution": meta.get("institution", ""), "year": meta.get("year", "")})
    return {
        "skills": list(set(skills))[:30],
        "experience_text": "\n\n".join(experience_parts),
        "education": education[:5],
        "doc_count": len(docs),
    }


@router.get("")
async def list_packages(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    repo = PackageRepository(db)
    job_repo = JobRepository(db)
    packages, total = await repo.find_by_user(user["sub"])
    job_title_cache: dict[int, str] = {}
    payload = []
    for pkg in packages:
        display_title = pkg.title
        if (not display_title or display_title.strip().lower() == "position") and pkg.job_id:
            if pkg.job_id not in job_title_cache:
                job = await job_repo.get_by_id(pkg.job_id)
                job_title_cache[pkg.job_id] = (job.title if job and job.title else "Position").strip()
            display_title = job_title_cache[pkg.job_id]
        payload.append(_pkg_response(pkg, display_title=display_title))
    return {"packages": payload, "total": total}


@router.post("/generate")
async def generate_package(request: GeneratePackageRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    repo = PackageRepository(db)
    job_repo = JobRepository(db)
    resolved_job = await _resolve_job_record(job_repo, request.job_id)
    if not resolved_job:
        raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
    numeric_job_id = resolved_job.id

    pkg = await repo.create(
        user_id=user["sub"],
        job_id=numeric_job_id,
        title=resolved_job.title or "Position",
        status="generating",
        created_by=user["sub"],
    )

    asyncio.create_task(_run_structured_generation(pkg.package_uid, user["sub"], request.job_id, numeric_job_id))
    return {"package_id": pkg.package_uid, "status": "generating"}


async def _run_structured_generation(package_uid: str, user_id: str, job_uid: str, numeric_job_id: int):
    from src.db.repositories.package_repository import PackageRepository
    from src.db.session import async_session

    async with async_session() as db:
        repo = PackageRepository(db)
        job_repo = JobRepository(db)
        knowledge_repo = KnowledgeRepository(db)

        try:
            pkg = await repo.get_by_uid(package_uid)
            if not pkg:
                return

            job = await job_repo.get_by_id(numeric_job_id)
            if not job:
                await repo.update(pkg.id, status="failed", readiness_summary="Job not found", updated_by=user_id)
                return

            job_title = job.title or "Position"
            company = job.company or "the company"
            job_desc = job.description or ""

            docs, _ = await knowledge_repo.find_by_user(user_id)
            evidence = _collect_candidate_evidence(docs)

            content = await _generate_with_llm_or_fallback(
                job_title=job_title,
                company=company,
                job_desc=job_desc,
                evidence=evidence,
                package_uid=package_uid,
            )

            serialized = _serialize_content(content)
            await repo.update(
                pkg.id,
                title=job_title,
                status="ready",
                resume_tailored=serialized["resume_tailored"],
                cover_letter=serialized["cover_letter"],
                outreach_message=serialized["outreach_message"],
                interview_guide=serialized["interview_guide"],
                metadata_={
                    "job_id": job_uid,
                    "target_role": job_title,
                    "target_company": company,
                    "match_score": content.metadata.match_score,
                    "generation_mode": content.metadata.generation_mode,
                    "warnings": content.metadata.warnings,
                },
                updated_by=user_id,
            )
            logger.info("Package %s generated successfully (mode=%s)", package_uid, content.metadata.generation_mode)

        except Exception as gen_err:
            logger.exception("Package generation failed for %s", package_uid)
            pkg = await repo.get_by_uid(package_uid)
            if pkg:
                await repo.update(
                    pkg.id,
                    status="failed",
                    readiness_summary=f"Package generation failed: {str(gen_err)[:500]}",
                    metadata_={"error": str(gen_err)[:500], "generation_mode": "failed"},
                    updated_by=user_id,
                )


async def _generate_with_llm_or_fallback(
    *,
    job_title: str,
    company: str,
    job_desc: str,
    evidence: dict,
    package_uid: str,
) -> PackageContent:
    skills = evidence.get("skills", [])
    experience_text = evidence.get("experience_text", "")
    education = evidence.get("education", [])
    doc_count = evidence.get("doc_count", 0)

    prompt = json.dumps(
        {
            "job_title": job_title,
            "company": company,
            "job_description": job_desc[:1800],
            "candidate_skills": skills[:24],
            "candidate_experience": experience_text[:2200],
            "candidate_education": education,
            "instructions": [
                "Create a polished, ATS-friendly application package for a real candidate.",
                "Return only valid JSON matching the requested schema; do not add markdown or commentary.",
                "Use only the supplied evidence. Do not invent contact details, employers, dates, metrics, or credentials.",
                "Tailor the resume summary and bullets to the target role and company.",
                "Group skills into practical categories such as Languages, Backend, AI/ML, Cloud/DevOps, Databases, and Tools.",
                "Keep outreach concise, professional, and specific to the role.",
                "Make interview questions relevant to the role description and the candidate's evidence.",
                "Surface gaps honestly in quality notes and warnings when the profile evidence is sparse.",
            ],
        },
        default=str,
    )

    from src.services.llm.factory import get_reasoning_provider

    provider = get_reasoning_provider()
    try:
        raw_result = await asyncio.wait_for(
            provider.structured_generate(
                system_prompt=(
                    "You are a senior career strategist and ATS optimization expert. "
                    "Return only valid JSON for the requested schema."
                ),
                user_message=prompt,
                output_schema=PackageContent,
                max_tokens=2400,
                temperature=0.0,
                cache_key_hint=f"package:v3:{package_uid}",
            ),
            timeout=120.0,
        )
        parsed = raw_result.get("parsed")
        if parsed is None:
            raise RuntimeError("LLM structured generation returned unparsed content")

        content = parsed if isinstance(parsed, PackageContent) else PackageContent.model_validate(parsed)
        content.metadata.generation_mode = "llm"
        content.metadata.target_role = job_title
        content.metadata.target_company = company
        if doc_count == 0:
            content.metadata.warnings.append(
                "No resume/profile documents were found in Knowledge Hub. Upload your resume for better tailoring."
            )
        if _is_sparse_package_content(content):
            raise RuntimeError("LLM output was too sparse to use safely")
        return content

    except Exception as llm_err:
        logger.warning("LLM generation failed for %s, using deterministic fallback: %s", package_uid, llm_err)
        return build_deterministic_package(
            job_title=job_title,
            company=company,
            skills=skills,
            missing_skills=[],
            experience_summary=experience_text[:500] if experience_text else "",
            match_score=0.0,
        )


@router.get("/{pkg_id}")
async def get_package(pkg_id: str, db: AsyncSession = Depends(get_db)):
    repo = PackageRepository(db)
    job_repo = JobRepository(db)
    pkg = await repo.get_by_uid(pkg_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    display_title = pkg.title
    if (not display_title or display_title.strip().lower() == "position") and pkg.job_id:
        job = await job_repo.get_by_id(pkg.job_id)
        if job and job.title:
            display_title = job.title
    return _pkg_response(pkg, display_title=display_title)


@router.delete("/{pkg_id}")
async def delete_package(pkg_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    repo = PackageRepository(db)
    pkg = await repo.get_by_uid(pkg_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    await repo.soft_delete(pkg.id)
    return {"status": "deleted", "package_id": pkg_id}


@router.post("/{pkg_id}/regenerate")
async def regenerate_package(pkg_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    repo = PackageRepository(db)
    pkg = await repo.get_by_uid(pkg_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    if not pkg.job_id:
        raise HTTPException(status_code=400, detail="Package has no associated job")

    await repo.update(pkg.id, status="regenerating", updated_by=user["sub"])
    asyncio.create_task(_run_structured_generation(pkg.package_uid, pkg.user_id, str(pkg.job_id), pkg.job_id))
    return {"status": "regenerating", "package_id": pkg_id}


@router.get("/{pkg_id}/download")
async def download_package(pkg_id: str, asset: str = "resume", format: str = "markdown", db: AsyncSession = Depends(get_db)):
    repo = PackageRepository(db)
    job_repo = JobRepository(db)
    pkg = await repo.get_by_uid(pkg_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    content = _deserialize_content(pkg)
    if not content:
        raise HTTPException(status_code=500, detail="Package content is corrupted")

    if asset == "resume":
        text = _render_resume_markdown(content)
    elif asset == "cover_letter":
        text = f"# {content.cover_letter.subject}\n\n{content.cover_letter.body}"
    elif asset == "outreach":
        text = f"## LinkedIn\n\n{content.outreach.linkedin_message}\n\n## Email\n\n{content.outreach.email_message}"
    elif asset == "interview_guide":
        text = _render_interview_markdown(content)
    else:
        text = ""

    return {
        "package_id": pkg_id,
        "asset": asset,
        "format": format,
        "content": text,
        "filename": f"{asset}_{pkg_id}.{'md' if format == 'markdown' else format}",
    }


def _render_resume_markdown(content: PackageContent) -> str:
    r = content.resume
    lines = [f"# {r.header.name or '[Your Name]'}", f"**{r.header.role_target}**"]
    if r.header.location:
        lines.append(r.header.location)
    lines.append("")
    lines.append("## Professional Summary")
    for s in r.summary:
        lines.append(f"- {s}")
    lines.append("")
    if r.skills:
        lines.append("## Core Skills")
        for category, skill_list in r.skills.items():
            if skill_list:
                lines.append(f"**{category}**: {', '.join(skill_list)}")
    lines.append("")
    if r.experience:
        lines.append("## Experience")
        for exp in r.experience:
            lines.append(f"### {exp.title} — {exp.company}")
            if exp.dates:
                lines.append(f"*{exp.dates}*")
            for b in exp.bullets:
                lines.append(f"- {b}")
            lines.append("")
    if r.projects:
        lines.append("## Projects")
        for proj in r.projects:
            lines.append(f"### {proj.name}")
            lines.append(f"**Tech**: {', '.join(proj.tech_stack)}")
            lines.append(proj.description)
            if proj.impact:
                lines.append(f"*Impact*: {proj.impact}")
            lines.append("")
    if r.education:
        lines.append("## Education")
        for edu in r.education:
            lines.append(f"- {edu.degree}, {edu.institution} ({edu.year})")
        lines.append("")
    if r.quality_notes:
        lines.append("## Notes")
        for n in r.quality_notes:
            lines.append(f"- ⚠ {n}")
    return "\n".join(lines)


def _render_interview_markdown(content: PackageContent) -> str:
    ig = content.interview_guide
    lines = ["# Interview Preparation Guide", ""]
    if ig.likely_questions:
        lines.append("## Likely Questions")
        for q in ig.likely_questions:
            lines.append(f"- {q}")
        lines.append("")
    if ig.talking_points:
        lines.append("## Key Talking Points")
        for t in ig.talking_points:
            lines.append(f"- {t}")
        lines.append("")
    if ig.weaknesses_to_prepare:
        lines.append("## Weaknesses to Prepare For")
        for w in ig.weaknesses_to_prepare:
            lines.append(f"- {w}")
        lines.append("")
    if ig.questions_to_ask:
        lines.append("## Questions to Ask the Interviewer")
        for q in ig.questions_to_ask:
            lines.append(f"- {q}")
    return "\n".join(lines)
