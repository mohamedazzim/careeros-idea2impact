"""Phase 17.7 — Career Roadmap Endpoints (Enterprise).

Uses roadmap repositories for persistence. JWT auth on all endpoints.
No in-memory stores. No demo_user defaults.
"""

import asyncio
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.api.deps import get_current_user_id
from src.db.repositories.domain_repositories import (
    RoadmapRepository, RoadmapGoalRepository, RoadmapTaskRepository, PreferencesRepository,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/roadmaps", tags=["Roadmaps"])
ROADMAP_STALE_AFTER_DAYS = 30


def _gap_label(gap: Any) -> str:
    if isinstance(gap, str):
        return gap.strip()
    if isinstance(gap, dict):
        return str(
            gap.get("category")
            or gap.get("title")
            or gap.get("description")
            or gap.get("id")
            or ""
        ).strip()
    return str(gap).strip()


def _resolve_target_role(raw_role: Optional[str], preferences_extra: Optional[dict[str, Any]] = None) -> str:
    pref_role = ""
    if isinstance(preferences_extra, dict):
        pref_role = str(preferences_extra.get("target_role") or "").strip()
    resolved = str(raw_role or pref_role or "").strip()
    return resolved or "Career Target"


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _roadmap_evidence_status(total_tasks: int, completed_tasks: int) -> str:
    if total_tasks <= 0:
        return "empty"
    if completed_tasks <= 0:
        return "not_started"
    if completed_tasks >= total_tasks:
        return "complete"
    return "partial"


def _roadmap_staleness_status(updated_at: Optional[datetime], now: Optional[datetime] = None) -> str:
    if updated_at is None:
        return "unknown"
    current_time = now or datetime.utcnow()
    if current_time - updated_at > timedelta(days=ROADMAP_STALE_AFTER_DAYS):
        return "stale"
    return "fresh"


def _role_roadmap_template(role: str, blueprint_type: Optional[str] = None) -> dict[str, Any]:
    role_l = (role or "").lower()
    blueprint_l = (blueprint_type or "").lower()
    if blueprint_l == "skill_development":
        return {
            "summary": f"Strengthen the {role} profile with the highest-value gaps and practical proof.",
            "phases": [
                {
                    "title": f"Core Skill Gap Scan for {role}",
                    "description": "Identify the highest-frequency skills missing from current job matches.",
                    "category": "skill",
                    "skills": ["Skill Analysis", "Gap Review"],
                    "tasks": [
                        "Review recurring missing skills from the latest matching jobs.",
                        "Document which gaps are already covered by current resume evidence.",
                    ],
                },
                {
                    "title": f"Build Evidence for {role}",
                    "description": "Create a focused project or artifact that proves one missing capability.",
                    "category": "project",
                    "skills": ["Portfolio", "Project", "Proof"],
                    "tasks": [
                        "Ship one small project aligned to the most repeated missing skill.",
                        "Add measurable output or screenshots to prove the work.",
                    ],
                },
                {
                    "title": f"Polish Resume for {role}",
                    "description": "Translate the new evidence into resume bullets and interview stories.",
                    "category": "milestone",
                    "skills": ["Resume Writing", "Storytelling"],
                    "tasks": [
                        "Update one resume section with the new project outcome.",
                        "Prepare a short STAR-style story for the gap you closed.",
                    ],
                },
            ],
            "recommendations": [
                "Focus on the narrowest gaps that block the most matching jobs.",
                "Use one strong project rather than many superficial tasks.",
            ],
        }
    if blueprint_l == "interview_prep":
        return {
            "summary": f"Turn the current {role} profile into interview-ready stories, whiteboard practice, and role-specific confidence.",
            "phases": [
                {
                    "title": f"{role} Interview Question Map",
                    "description": "Collect the most likely interview topics for this role.",
                    "category": "skill",
                    "skills": ["Behavioral", "Technical Questions", "System Design"],
                    "tasks": [
                        "List the top technical and behavioral questions for this role.",
                        "Mark where your current experience is strongest and weakest.",
                    ],
                },
                {
                    "title": f"{role} Mock Answers & Narratives",
                    "description": "Write concise answers that use your real projects and achievements.",
                    "category": "milestone",
                    "skills": ["STAR Method", "Project Narration", "Communication"],
                    "tasks": [
                        "Draft one answer for each common interview theme.",
                        "Practice speaking the answers out loud.",
                    ],
                },
                {
                    "title": f"{role} Final Mock Round",
                    "description": "Run a realistic mock interview against the target role expectations.",
                    "category": "project",
                    "skills": ["Mock Interview", "Feedback", "Confidence"],
                    "tasks": [
                        "Simulate one full technical round.",
                        "Capture feedback and convert it into the next revision plan.",
                    ],
                },
            ],
            "recommendations": [
                "Use the exact role title in your answers so the interview story stays aligned.",
                "Practice explaining one project end-to-end without hand-waving.",
            ],
        }
    if blueprint_l == "job_search":
        return {
            "summary": f"Optimize the {role} job search with application targeting, resume alignment, and pipeline follow-up.",
            "phases": [
                {
                    "title": f"{role} Target Company List",
                    "description": "Build a focused list of companies and job boards that actually match the role.",
                    "category": "skill",
                    "skills": ["Job Search", "Company Research", "Targeting"],
                    "tasks": [
                        "Collect 10-15 real postings that match the target role.",
                        "Rank them by fit, salary, location, and remote preference.",
                    ],
                },
                {
                    "title": f"{role} Application Pipeline",
                    "description": "Track applications, follow-ups, and outcomes without losing context.",
                    "category": "project",
                    "skills": ["CRM", "Tracking", "Follow-up"],
                    "tasks": [
                        "Create a simple tracker for submitted applications.",
                        "Set a follow-up reminder for each active application.",
                    ],
                },
                {
                    "title": f"{role} Conversion Review",
                    "description": "Review what improves replies and interviews for this role.",
                    "category": "milestone",
                    "skills": ["Analytics", "Iteration", "Optimization"],
                    "tasks": [
                        "Compare which posting sources produce the best response.",
                        "Revise resume bullets based on matching feedback.",
                    ],
                },
            ],
            "recommendations": [
                "Keep the search list to real, current postings only.",
                "Track what gets replies so the roadmap adapts over time.",
            ],
        }
    if "flutter" in role_l or "dart" in role_l or "mobile" in role_l or "cross-platform" in role_l:
        return {
            "summary": "Focus on Flutter app delivery, Dart language fluency, state management, backend integration, and production release evidence.",
            "phases": [
                {
                    "title": "Flutter & Dart Foundations",
                    "description": "Build fluency in widget composition, Dart syntax, and app structure patterns used in production teams.",
                    "category": "skill",
                    "skills": ["Flutter", "Dart", "Widgets", "Navigation"],
                    "tasks": [
                        "Refresh Dart language fundamentals and null safety concepts.",
                        "Build one small UI screen using Flutter widgets and responsive layout rules.",
                    ],
                },
                {
                    "title": "State Management & API Integration",
                    "description": "Show that you can manage app state cleanly and connect to real backend APIs.",
                    "category": "project",
                    "skills": ["Provider", "Riverpod", "Bloc", "REST APIs"],
                    "tasks": [
                        "Connect a Flutter screen to a real REST endpoint.",
                        "Handle loading, error, and offline-friendly states clearly.",
                    ],
                },
                {
                    "title": "Mobile Release & Quality",
                    "description": "Prove production readiness with testing, build pipelines, and release packaging.",
                    "category": "project",
                    "skills": ["Testing", "CI/CD", "Android", "iOS"],
                    "tasks": [
                        "Add one widget or unit test that protects the core user flow.",
                        "Document build and release steps for one mobile target.",
                    ],
                },
                {
                    "title": "Portfolio Storytelling & Role Fit",
                    "description": "Turn the roadmap into interview-ready evidence for Flutter roles.",
                    "category": "milestone",
                    "skills": ["Portfolio", "Debugging", "Communication"],
                    "tasks": [
                        "Prepare a walkthrough of one Flutter project with tradeoffs and outcomes.",
                        "List the role-specific strengths you can demonstrate in interviews.",
                    ],
                },
            ],
            "recommendations": [
                "Use a real Flutter project as the anchor so the roadmap stays grounded.",
                "Keep one integration and one release-ready artifact visible in your portfolio.",
                "Show how your UI state handling and API integration map to actual product work.",
            ],
        }
    if any(term in role_l for term in ("java", "spring", "full stack", "backend")):
        return {
            "summary": "Focus on Java backend depth, Spring Boot delivery, SQL data handling, and deployable full-stack evidence.",
            "phases": [
                {
                    "title": "Java Foundations & Backend Structure",
                    "description": "Strengthen Java language mastery and backend engineering patterns used in real production services.",
                    "category": "skill",
                    "skills": ["Java", "OOP", "Collections", "REST APIs"],
                    "tasks": [
                        "Refresh Java core concepts with one small service implementation.",
                        "Document REST endpoint design choices with sample request/response payloads.",
                    ],
                },
                {
                    "title": "Spring Boot, JPA, and SQL Delivery",
                    "description": "Build service-layer experience around Spring Boot, persistence, and transactional data access.",
                    "category": "skill",
                    "skills": ["Spring Boot", "JPA", "Hibernate", "SQL"],
                    "tasks": [
                        "Build one CRUD service with validation, exception handling, and repository tests.",
                        "Ship a database-backed feature using JPA/Hibernate and optimized SQL queries.",
                    ],
                },
                {
                    "title": "Frontend Integration & Product Delivery",
                    "description": "Prove end-to-end full-stack work by connecting backend APIs to a UI and handling user flows cleanly.",
                    "category": "project",
                    "skills": ["React", "TypeScript", "API Integration", "Forms"],
                    "tasks": [
                        "Connect a frontend screen to the Spring Boot API with a real user workflow.",
                        "Add loading, error, and empty states to the demo surface.",
                    ],
                },
                {
                    "title": "Production Readiness & Deployment",
                    "description": "Demonstrate deployable engineering habits with Docker, CI/CD, observability, and reproducible environments.",
                    "category": "project",
                    "skills": ["Docker", "CI/CD", "Testing", "Monitoring"],
                    "tasks": [
                        "Containerize the project and document the deploy steps.",
                        "Add at least one test covering the main backend or integration path.",
                    ],
                },
                {
                    "title": "Interview Readiness & Project Storytelling",
                    "description": "Translate the roadmap into interview-ready evidence with metrics, tradeoffs, and project narratives.",
                    "category": "milestone",
                    "skills": ["System Design", "Problem Solving", "Project Narration"],
                    "tasks": [
                        "Prepare a 2-minute walkthrough of the strongest full-stack project.",
                        "List tradeoffs, bugs fixed, and impact metrics for interview discussion.",
                    ],
                },
            ],
            "recommendations": [
                "Prioritize Java, Spring Boot, SQL, and API integration because they show up repeatedly in full-stack role descriptions.",
                "Keep one deployable project live so the roadmap stays anchored to evidence, not theory.",
                "Use interview prep to turn each milestone into a measurable story.",
            ],
        }
    if "devops" in role_l or "sre" in role_l or "platform" in role_l:
        return {
            "summary": "Focus on infrastructure delivery, automation, cloud operations, and measurable platform reliability.",
            "phases": [
                {
                    "title": "Linux, Networking, and Scripting",
                    "description": "Strengthen operational fundamentals needed for daily platform work.",
                    "category": "skill",
                    "skills": ["Linux", "Networking", "Bash", "Python"],
                    "tasks": [
                        "Automate a repetitive ops task with a shell or Python script.",
                        "Document a simple incident runbook.",
                    ],
                },
                {
                    "title": "Containers, CI/CD, and Release Flow",
                    "description": "Prove the ability to package, test, and release services consistently.",
                    "category": "project",
                    "skills": ["Docker", "CI/CD", "GitHub Actions", "Testing"],
                    "tasks": [
                        "Create a containerized service with a repeatable release pipeline.",
                        "Add deployment notes and rollback steps.",
                    ],
                },
                {
                    "title": "Cloud, Observability, and Reliability",
                    "description": "Show cloud and monitoring competence with logs, metrics, alerts, and SLO thinking.",
                    "category": "project",
                    "skills": ["AWS", "Monitoring", "Logging", "Prometheus"],
                    "tasks": [
                        "Add metrics and traces to one service.",
                        "Define an uptime or latency target for the project.",
                    ],
                },
            ],
            "recommendations": [
                "Keep one automation or deployment project visible in your portfolio.",
                "Practice incident narratives, root cause analysis, and rollback reasoning.",
            ],
        }
    if "data scientist" in role_l or "data science" in role_l or "analyst" in role_l:
        return {
            "summary": "Focus on SQL, Python, statistics, dashboards, and model-backed evidence from real datasets.",
            "phases": [
                {
                    "title": "Data Handling & SQL Analysis",
                    "description": "Build confidence in extracting, cleaning, and analyzing business data.",
                    "category": "skill",
                    "skills": ["SQL", "Python", "Pandas", "Statistics"],
                    "tasks": [
                        "Solve one SQL analysis case using joins and aggregations.",
                        "Document the data cleaning decisions and assumptions.",
                    ],
                },
                {
                    "title": "Modeling & Experimentation",
                    "description": "Demonstrate model selection, validation, and evaluation with clear metrics.",
                    "category": "project",
                    "skills": ["Scikit-learn", "Experiment Design", "Evaluation Metrics"],
                    "tasks": [
                        "Train one small model with a reproducible evaluation split.",
                        "Record metric improvements and error analysis.",
                    ],
                },
                {
                    "title": "Visualization & Business Storytelling",
                    "description": "Turn findings into clear dashboards and decision-ready narratives.",
                    "category": "milestone",
                    "skills": ["Power BI", "Matplotlib", "Storytelling"],
                    "tasks": [
                        "Publish one dashboard with a business metric story.",
                        "Summarize the analysis for a non-technical stakeholder.",
                    ],
                },
            ],
            "recommendations": [
                "Show at least one analysis or dashboard project with measurable outcomes.",
                "Keep your statistics and SQL stories interview-ready.",
            ],
        }
    if "mlops" in role_l or "machine learning" in role_l or "ai engineer" in role_l:
        return {
            "summary": "Focus on model delivery, experimentation, deployment, and practical ML systems work.",
            "phases": [
                {
                    "title": "ML Foundations & Data Pipelines",
                    "description": "Reinforce data preprocessing, feature handling, and evaluation basics.",
                    "category": "skill",
                    "skills": ["Python", "SQL", "Pandas", "Scikit-learn"],
                    "tasks": [
                        "Rebuild one dataset pipeline with clean feature handling.",
                        "Write down how you validate models and avoid leakage.",
                    ],
                },
                {
                    "title": "Model Serving & Experimentation",
                    "description": "Show how a model is served, versioned, and measured in a real application.",
                    "category": "project",
                    "skills": ["FastAPI", "Docker", "MLflow", "Testing"],
                    "tasks": [
                        "Serve one model behind an API and capture latency/accuracy tradeoffs.",
                        "Add a reproducible experiment or model version note.",
                    ],
                },
                {
                    "title": "Monitoring & Reliability for ML Systems",
                    "description": "Demonstrate how you keep ML systems observable and maintainable.",
                    "category": "project",
                    "skills": ["Monitoring", "Logging", "Evaluation", "Deployment"],
                    "tasks": [
                        "Add one metric or log that proves model behavior over time.",
                        "Document a failure mode and the fallback response.",
                    ],
                },
            ],
            "recommendations": [
                "Anchor every milestone to a deployed artifact or experiment log.",
                "Keep the roadmap tied to current job-market tools you actually see in active postings.",
            ],
        }
    return {
        "summary": "Focus on the highest-signal competencies from the current job market and the user’s latest resume match.",
        "phases": [
            {
                "title": f"Core Competencies for {role}",
                "description": "Establish the technical baseline repeatedly requested by current role postings.",
                "category": "skill",
                "skills": [role],
                "tasks": [
                    "Review the top recurring skills from current matches.",
                    "Build one evidence artifact directly mapped to the target role.",
                ],
            },
            {
                "title": "Portfolio Evidence",
                "description": "Turn gaps into a visible project or case study.",
                "category": "project",
                "skills": ["Portfolio", "Project"],
                "tasks": [
                    "Ship one small project aligned to the role’s strongest job requirements.",
                    "Write a short narrative explaining the tradeoffs and results.",
                ],
            },
        ],
        "recommendations": [
            "Focus on the skills and project evidence that show up most often in the current match set.",
            "Use live job postings as the source of truth, not generic career advice.",
        ],
    }


class TaskToggleRequest(BaseModel):
    completed: bool


class RoadmapGenerateRequest(BaseModel):
    blueprint_type: Optional[str] = None
    target_role: Optional[str] = None
    target_salary: Optional[str] = None
    target_location: Optional[str] = None
    target_timeline: Optional[str] = None


@router.get("")
async def list_roadmaps(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = RoadmapRepository(db)
    roadmaps = await repo.find_by_user(user_id)
    return {
        "roadmaps": [
            {
                "id": r.id,
                "roadmap_uid": r.roadmap_uid,
                "user_id": r.user_id,
                "title": r.title,
                "target_role": r.target_role,
                "target_salary": r.target_salary,
                "target_location": r.target_location,
                "target_timeline": r.target_timeline,
                "status": r.status,
                "progress_pct": r.progress_pct,
                "recommendations": r.recommendations or [],
                "velocity_history": r.velocity_history or [],
                "trace_id": r.trace_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in roadmaps
        ],
        "total": len(roadmaps),
    }


@router.get("/{roadmap_id}")
async def get_roadmap(
    roadmap_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if roadmap_id == "progress":
        return await get_progress(db=db, user_id=user_id)

    repo = RoadmapRepository(db)
    r = await repo.get_by_uid(roadmap_id) or await repo.get_by_id(int(roadmap_id) if roadmap_id.isdigit() else -1)
    if not r:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    goal_repo = RoadmapGoalRepository(db)
    goals = await goal_repo.find_by_roadmap(r.id)

    task_repo = RoadmapTaskRepository(db)
    goals_with_tasks = []
    for g in goals:
        tasks = await task_repo.find_by_goal(g.id)
        goals_with_tasks.append({
            "id": g.id,
            "title": g.title,
            "description": g.description,
            "category": g.category,
            "priority": g.priority,
            "order_index": g.order_index,
            "tasks": [
                {
                    "id": t.id,
                    "task_uid": t.task_uid,
                    "title": t.title,
                    "completed": t.completed,
                    "due_date": t.due_date,
                    "order_index": t.order_index,
                }
                for t in tasks
            ],
        })

    return {
        "id": r.id,
        "roadmap_uid": r.roadmap_uid,
        "user_id": r.user_id,
        "title": r.title,
        "target_role": r.target_role,
        "target_salary": r.target_salary,
        "target_location": r.target_location,
        "target_timeline": r.target_timeline,
        "status": r.status,
        "progress_pct": r.progress_pct,
        "recommendations": r.recommendations or [],
        "velocity_history": r.velocity_history or [],
        "trace_id": r.trace_id,
        "goals": goals_with_tasks,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.post("/generate")
async def generate_roadmap(
    req: RoadmapGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    from src.models.jobs import JobMatch
    from src.models.jobs import Job
    from sqlalchemy import select, desc
    
    # Try to get missing skills from the user's latest job match
    missing_skills = []
    try:
        match_stmt = select(JobMatch).where(
            JobMatch.user_id == user_id,
            JobMatch.deleted_at.is_(None)
        ).order_by(JobMatch.created_at.desc()).limit(1)
        match_result = await db.execute(match_stmt)
        latest_match = match_result.scalar_one_or_none()
        if latest_match and latest_match.gaps:
            missing_skills = [
                label for label in (_gap_label(gap) for gap in latest_match.gaps[:5])
                if label
            ]
    except Exception:
        logger.exception("Unable to load persisted skill gaps for roadmap generation")

    market_skills: list[str] = []
    try:
        market_stmt = (
            select(JobMatch, Job)
            .join(Job, Job.id == JobMatch.job_id)
            .where(
                JobMatch.user_id == user_id,
                JobMatch.deleted_at.is_(None),
                Job.deleted_at.is_(None),
                Job.status == "active",
                JobMatch.overall_score.is_not(None),
            )
            .order_by(desc(JobMatch.overall_score), desc(JobMatch.created_at))
            .limit(5)
        )
        market_rows = await db.execute(market_stmt)
        for match, job in market_rows.all():
            skills = list(job.skills_required or [])
            if isinstance(match.match_details, dict):
                skills.extend([str(s) for s in match.match_details.get("job_extraction", {}).get("skills", []) if s])
            market_skills.extend([str(skill).strip() for skill in skills if str(skill).strip()])
    except Exception:
        logger.exception("Unable to load current job-market signals for roadmap generation")
    market_skills = list(dict.fromkeys(market_skills))[:12]

    preferences_extra: dict[str, Any] = {}
    try:
        pref_repo = PreferencesRepository(db)
        pref = await pref_repo.get_by_user(user_id)
        if pref and isinstance(pref.extra, dict):
            preferences_extra = pref.extra
    except Exception:
        logger.exception("Unable to load persisted user preferences for roadmap generation")

    resolved_role = _resolve_target_role(req.target_role, preferences_extra)
    resolved_blueprint = _safe_text(req.blueprint_type or "AI_ENGINEER", "AI_ENGINEER")
    resolved_salary = req.target_salary or str(preferences_extra.get("target_salary") or "").strip()
    resolved_location = req.target_location or str(preferences_extra.get("target_location") or "").strip()
    resolved_timeline = req.target_timeline or (
        f"{preferences_extra.get('timeline_months')} months" if preferences_extra.get("timeline_months") else ""
    )

    from pydantic import BaseModel
    from src.services.llm.factory import get_reasoning_provider as get_llm_provider

    class RoadmapTaskSpec(BaseModel):
        title: str
        completed: bool = False

    class RoadmapGoalSpec(BaseModel):
        title: str
        description: str
        category: str
        priority: int = Field(..., ge=1, le=10)
        tasks: list[RoadmapTaskSpec] = Field(default_factory=list)

    class RoadmapPlanSpec(BaseModel):
        title: str
        summary: str
        recommendations: list[str] = Field(default_factory=list)
        goals: list[RoadmapGoalSpec] = Field(default_factory=list)

    blueprint_label = {
        "AI_ENGINEER": "AI / MLOps",
        "SKILL_DEVELOPMENT": "Skill Development",
        "INTERVIEW_PREP": "Interview Prep",
        "JOB_SEARCH": "Job Search",
    }.get(resolved_blueprint.upper(), resolved_blueprint.replace("_", " ").title())

    def _task_specs(raw_tasks: Any) -> list[RoadmapTaskSpec]:
        if not isinstance(raw_tasks, list):
            return []
        tasks: list[RoadmapTaskSpec] = []
        for task in raw_tasks[:6]:
            if isinstance(task, str):
                text = _safe_text(task, "")
            elif isinstance(task, dict):
                text = _safe_text(
                    task.get("title")
                    or task.get("task")
                    or task.get("description")
                    or task.get("goal")
                    or task.get("focus")
                    or "",
                    "",
                )
            else:
                text = _safe_text(task, "")
            if text:
                tasks.append(RoadmapTaskSpec(title=text, completed=False))
        return tasks

    def _goal_specs_from_phases(phases: Any, fallback_category: str = "skill") -> list[RoadmapGoalSpec]:
        if not isinstance(phases, list):
            return []
        goals: list[RoadmapGoalSpec] = []
        for idx, phase in enumerate(phases[:6]):
            if not isinstance(phase, dict):
                phase = {"title": str(phase)}
            title = _safe_text(
                phase.get("title")
                or phase.get("phase")
                or phase.get("goal")
                or phase.get("name")
                or f"Phase {idx + 1}",
                f"Phase {idx + 1}",
            )
            description = _safe_text(
                phase.get("description")
                or phase.get("summary")
                or phase.get("focus")
                or title,
                title,
            )
            goals.append(
                RoadmapGoalSpec(
                    title=title,
                    description=description,
                    category=_safe_text(phase.get("category") or fallback_category, fallback_category),
                    priority=min(idx + 1, 10),
                    tasks=_task_specs(phase.get("tasks") or phase.get("steps") or phase.get("actions") or []),
                )
            )
        return goals

    def build_deterministic_plan() -> RoadmapPlanSpec:
        profile = _role_roadmap_template(resolved_role, resolved_blueprint)
        phase_items = profile["phases"]
        if market_skills:
            phase_items = [
                dict(phase_items[0]),
                *phase_items[1:],
            ]
            phase_items[0]["tasks"] = phase_items[0]["tasks"] + [
                f"Map recurring market skills into the roadmap: {', '.join(market_skills[:4])}.",
            ]
        return RoadmapPlanSpec(
            title=f"Career Path - {resolved_role}",
            summary=(
                f"{profile['summary']} "
                f"Blueprint focus: {blueprint_label}. "
                f"Grounded in current match signals: {', '.join(missing_skills) if missing_skills else 'core milestones'}."
            ),
            recommendations=profile["recommendations"]
            + ([f"Strengthen: {skill}" for skill in missing_skills[:3]] if missing_skills else [])
            + ([f"Leverage market evidence: {skill}" for skill in market_skills[:3]] if market_skills else []),
            goals=[
                RoadmapGoalSpec(
                    title=phase["title"] if isinstance(phase, dict) else f"Phase {idx + 1}",
                    description=phase["description"] if isinstance(phase, dict) else phase["title"],
                    category=phase.get("category", "skill") if isinstance(phase, dict) else "skill",
                    priority=min(idx + 1, 10),
                    tasks=[
                        RoadmapTaskSpec(title=str(task), completed=False)
                        for task in (phase.get("tasks", []) if isinstance(phase, dict) else [])
                        if str(task).strip()
                    ],
                )
                for idx, phase in enumerate(phase_items[:5])
            ],
        )

    def normalize_roadmap_payload(raw_payload: Any) -> RoadmapPlanSpec:
        payload = raw_payload
        if isinstance(payload, RoadmapPlanSpec):
            return payload

        if isinstance(payload, str):
            text = payload.strip()
            if text.startswith("```"):
                text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return _fallback_plan("invalid_json_output")

        if isinstance(payload, dict):
            has_canonical_fields = any(
                payload.get(field)
                for field in ("title", "summary", "goals", "recommendations")
            )
            if not has_canonical_fields:
                for wrapper_key in ("parsed", "result", "data", "roadmap", "career_roadmap"):
                    wrapped = payload.get(wrapper_key)
                    if isinstance(wrapped, (dict, list, str, RoadmapPlanSpec)):
                        payload = wrapped
                        break

        if isinstance(payload, RoadmapPlanSpec):
            return payload

        if not isinstance(payload, dict):
            return _fallback_plan("non_dict_provider_output")

        # Normalize common provider shapes into the canonical schema.
        title = _safe_text(payload.get("title"), f"Career Path - {resolved_role}")
        summary = _safe_text(
            payload.get("summary")
            or payload.get("overview")
            or payload.get("description")
            or payload.get("goal"),
            f"{_role_roadmap_template(resolved_role, resolved_blueprint)['summary']} Grounded in current match signals: {', '.join(missing_skills) if missing_skills else 'core milestones'}.",
        )

        recommendations: list[str] = []
        for key in ("recommendations", "recommendation", "tips", "actions", "suggestions"):
            raw_recs = payload.get(key)
            if isinstance(raw_recs, list):
                recommendations.extend(_safe_text(item, "") for item in raw_recs if _safe_text(item, ""))
        if not recommendations:
            rec_obj = payload.get("recommendations")
            if isinstance(rec_obj, dict):
                recommendations.extend(_safe_text(value, "") for value in rec_obj.values() if _safe_text(value, ""))
        if not recommendations:
            recommendations = [
                f"Focus on: {', '.join(missing_skills[:3])}" if missing_skills else f"Review current evidence for {resolved_role}.",
            ]

        goals: list[RoadmapGoalSpec] = []
        if isinstance(payload.get("goals"), list):
            goals = _goal_specs_from_phases(payload["goals"], "milestone")
        elif isinstance(payload.get("phases"), list):
            goals = _goal_specs_from_phases(payload["phases"], "skill")
        elif isinstance(payload.get("roadmap"), list):
            goals = _goal_specs_from_phases(payload["roadmap"], "skill")
        elif isinstance(payload.get("6_month_plan"), list):
            goals = _goal_specs_from_phases(payload["6_month_plan"], "skill")
        else:
            time_keys = [
                key
                for key in payload
                if key in ("short_term", "medium_term", "long_term", "immediate", "near_term", "long_range")
            ]
            if time_keys:
                goals = _goal_specs_from_phases([payload[key] for key in sorted(time_keys)], "milestone")
            else:
                month_keys = [key for key in payload if str(key).startswith("month")]
                if month_keys:
                    month_payload = [payload[key] for key in sorted(month_keys)]
                    goals = _goal_specs_from_phases(month_payload, "skill")

        if not goals:
            return _fallback_plan("unstructured_provider_output")

        return RoadmapPlanSpec(
            title=title,
            summary=summary,
            recommendations=recommendations,
            goals=goals,
        )


    provider = get_llm_provider()
    roadmap_prompt = {
        "candidate_role": resolved_role,
        "location": resolved_location,
        "timeline": resolved_timeline,
        "salary": resolved_salary,
        "missing_skills": missing_skills,
        "market_skills": market_skills,
        "blueprint_type": resolved_blueprint,
        "role_template": _role_roadmap_template(resolved_role, resolved_blueprint),
        "goal": f"Create a personalized, time-phased career roadmap for {resolved_role} with measurable goals and practical tasks.",
    }

    generation_mode = "provider_generated"
    generation_confidence = "medium"
    fallback_reason: Optional[str] = None

    def _use_deterministic_fallback(reason: str) -> None:
        nonlocal generation_mode, generation_confidence, fallback_reason
        generation_mode = "deterministic_fallback"
        generation_confidence = "low"
        fallback_reason = reason

    def _fallback_plan(reason: str) -> RoadmapPlanSpec:
        _use_deterministic_fallback(reason)
        return build_deterministic_plan()

    try:
        roadmap_plan = await asyncio.wait_for(
            provider.structured_generate(
                system_prompt="You are a senior career strategist. Return concise JSON only.",
                user_message=json.dumps(roadmap_prompt, default=str),
                output_schema=RoadmapPlanSpec,
                max_tokens=1400,
                temperature=0.2,
                cache_key_hint=f"roadmap:{user_id}:{resolved_role}:{resolved_location}:{resolved_timeline}",
            ),
            timeout=18.0,
        )
    except Exception as exc:
        logger.warning("Roadmap generation provider unavailable; using deterministic fallback", exc_info=exc)
        roadmap_plan = build_deterministic_plan()
        _use_deterministic_fallback("provider_unavailable")

    try:
        plan = normalize_roadmap_payload(roadmap_plan)
    except Exception as exc:
        logger.error(
            "Roadmap invalid output: type=%s data=%s",
            type(roadmap_plan).__name__,
            str(roadmap_plan)[:500],
        )
        logger.warning("Roadmap invalid output; using deterministic fallback", exc_info=exc)
        plan = build_deterministic_plan()
        _use_deterministic_fallback("invalid_provider_output")

    normalized_text = f"{plan.title} {plan.summary}".lower()
    if resolved_role.lower() not in normalized_text or blueprint_label.lower() not in normalized_text:
        logger.info(
            "Roadmap provider output too generic for role=%s blueprint=%s; using deterministic fallback",
            resolved_role,
            blueprint_label,
        )
        plan = build_deterministic_plan()
        _use_deterministic_fallback("generic_provider_output")

    if not plan.goals:
        logger.warning("Roadmap provider returned no goals; using deterministic fallback")
        plan = build_deterministic_plan()
        _use_deterministic_fallback("empty_provider_output")

    if len({g.title for g in plan.goals}) < len(plan.goals):
        deduped_goals = []
        seen_titles = set()
        for goal in plan.goals:
            if goal.title in seen_titles:
                continue
            seen_titles.add(goal.title)
            deduped_goals.append(goal)
        plan = RoadmapPlanSpec(
            title=plan.title,
            summary=plan.summary,
            recommendations=plan.recommendations,
            goals=deduped_goals,
        )

    recommendations = [
        {"type": "strategy", "text": text, "priority": "high"}
        for text in (plan.recommendations or [])
    ] or [
        {"type": "strategy", "text": f"Focus on: {', '.join(missing_skills) if missing_skills else 'core roadmap milestones'}", "priority": "high"}
    ]

    repo = RoadmapRepository(db)
    roadmap = await repo.create(
        user_id=user_id,
        title=plan.title or f"Career Path — {resolved_role}",
        target_role=resolved_role,
        target_salary=resolved_salary or None,
        target_location=resolved_location or None,
        target_timeline=resolved_timeline or None,
        status="active",
        progress_pct=0.0,
        trace_id=f"trace_rm_{uuid.uuid4().hex[:8]}",
        recommendations=recommendations,
    )

    goal_repo = RoadmapGoalRepository(db)
    task_repo = RoadmapTaskRepository(db)
    goals_created = []

    for i, goal_spec in enumerate(plan.goals[:5]):
        goal = await goal_repo.create(
            roadmap_id=roadmap.id,
            title=goal_spec.title,
            description=goal_spec.description,
            category=goal_spec.category,
            priority=goal_spec.priority or (i + 1),
            order_index=i,
        )
        for j, task_spec in enumerate(goal_spec.tasks[:5]):
            await task_repo.create(
                goal_id=goal.id,
                title=task_spec.title,
                completed=False,
                order_index=j,
            )
        goals_created.append(goal.id)

    try:
        from src.services.events import get_career_event_service

        await get_career_event_service().emit_event(
            db,
            event_type="RoadmapGenerated",
            entity_type="roadmap",
            entity_id=roadmap.roadmap_uid,
            source_service="api.v1.roadmaps.generate",
            user_id=user_id,
            source_table="roadmaps",
            source_id=roadmap.id,
            payload={
                "roadmap_uid": roadmap.roadmap_uid,
                "title": roadmap.title,
                "target_role": roadmap.target_role,
                "generation_mode": generation_mode,
                "generation_confidence": generation_confidence,
                "fallback_reason": fallback_reason,
                "goals_created": len(goals_created),
            },
            evidence=[
                get_career_event_service().build_evidence_ref(
                    table="roadmaps",
                    source_id=roadmap.id,
                    note="roadmap generated from stored job gaps and preferences",
                    extra={
                        "target_role": roadmap.target_role,
                        "goal_count": len(goals_created),
                    },
                )
            ],
            provider="fallback_provider" if generation_mode == "deterministic_fallback" else "llm_provider",
            trace_id=roadmap.trace_id,
        )
    except Exception:
        logger.warning("Failed to emit RoadmapGenerated audit event", exc_info=True)

    return {
        "roadmap_uid": roadmap.roadmap_uid,
        "status": "active",
        "goals_created": len(goals_created),
        "generation_mode": generation_mode,
        "generation_confidence": generation_confidence,
        "fallback_reason": fallback_reason,
    }


@router.post("/regenerate")
async def regenerate_roadmap(
    roadmap_id: str = Query(""),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = RoadmapRepository(db)
    roadmap = None
    if roadmap_id:
        roadmap = await repo.get_by_uid(roadmap_id)
    if roadmap is None:
        roadmaps = await repo.find_by_user(user_id)
        roadmap = roadmaps[0] if roadmaps else None

    if roadmap:
        await repo.update(
            roadmap.id,
            updated_at=datetime.utcnow(),
            trace_id=f"trace_rm_regenerated_{uuid.uuid4().hex[:8]}",
        )
        return {"roadmap_uid": roadmap.roadmap_uid, "status": "regenerated"}

    return {"status": "no_roadmap_available", "roadmap_uid": None}


@router.get("/progress")
async def get_progress(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = RoadmapRepository(db)
    roadmaps = await repo.find_by_user(user_id)

    total_tasks = 0
    completed_tasks = 0
    all_velocity = []

    goal_repo = RoadmapGoalRepository(db)
    task_repo = RoadmapTaskRepository(db)
    total_recommendations = 0
    roadmap_diagnostics = []
    stale_roadmaps = 0
    partial_roadmaps = 0

    for r in roadmaps:
        total_recommendations += len(r.recommendations or [])
        goals = await goal_repo.find_by_roadmap(r.id)
        roadmap_total_tasks = 0
        roadmap_completed_tasks = 0
        for g in goals:
            tasks = await task_repo.find_by_goal(g.id)
            for t in tasks:
                total_tasks += 1
                roadmap_total_tasks += 1
                if t.completed:
                    completed_tasks += 1
                    roadmap_completed_tasks += 1
        all_velocity.extend(r.velocity_history or [])
        evidence_status = _roadmap_evidence_status(roadmap_total_tasks, roadmap_completed_tasks)
        staleness_status = _roadmap_staleness_status(r.updated_at)
        if staleness_status == "stale":
            stale_roadmaps += 1
        if evidence_status == "partial":
            partial_roadmaps += 1
        roadmap_diagnostics.append(
            {
                "roadmap_uid": r.roadmap_uid,
                "status": staleness_status,
                "evidence_status": evidence_status,
                "tasks_completed": roadmap_completed_tasks,
                "total_tasks": roadmap_total_tasks,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "trace_id": r.trace_id,
            }
        )

    overall_progress = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
    recommendation_acceptance = round((total_recommendations / len(roadmaps)) if roadmaps else 0, 1)
    telemetry_status = "not_tracked"
    telemetry_summary = "Roadmap generation latency and refresh timing are not persisted yet."
    metrics_available = False
    analytics_confidence = None
    diagnostics_status = "empty" if not roadmaps else "stale" if stale_roadmaps > 0 else "partial" if partial_roadmaps > 0 else "healthy"

    return {
        "progress_history": all_velocity,
        "progress_source": "stored_task_completion",
        "telemetry_status": telemetry_status,
        "analytics_confidence": analytics_confidence,
        "metrics_available": metrics_available,
        "overall_progress": overall_progress,
        "completion_percentage": overall_progress,
        "tasks_completed": completed_tasks,
        "total_tasks": total_tasks,
        "active_tasks": total_tasks - completed_tasks,
        "completed_tasks": completed_tasks,
        "consistency_score": overall_progress,
        "recommendation_acceptance": recommendation_acceptance,
        "observability": {
            "status": telemetry_status,
            "summary": telemetry_summary,
            "averageGenerationTimeMs": None,
            "averageRefreshTimeMs": None,
            "goalCompletionRatePercent": overall_progress,
            "recommendationAcceptancePercent": recommendation_acceptance,
            "totalGenerations": None,
            "totalRefreshes": None,
        },
        "diagnostics": {
            "status": diagnostics_status,
            "summary": telemetry_summary,
            "roadmap_count": len(roadmaps),
            "stale_roadmap_count": stale_roadmaps,
            "partial_roadmap_count": partial_roadmaps,
            "roadmaps": roadmap_diagnostics,
        },
    }


@router.patch("/tasks/{task_id}")
async def toggle_task(
    task_id: str,
    req: TaskToggleRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    task_repo = RoadmapTaskRepository(db)
    task = await task_repo.toggle_completion(task_id, req.completed)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        from src.services.events import get_career_event_service

        await get_career_event_service().emit_event(
            db,
            event_type="RoadmapTaskUpdated",
            entity_type="roadmap_task",
            entity_id=task.task_uid,
            source_service="api.v1.roadmaps.toggle_task",
            user_id=user_id,
            source_table="roadmap_tasks",
            source_id=task.id,
            payload={
                "task_uid": task.task_uid,
                "completed": task.completed,
                "goal_id": task.goal_id,
            },
            evidence=[
                get_career_event_service().build_evidence_ref(
                    table="roadmap_tasks",
                    source_id=task.id,
                    note="roadmap task completion toggled by the user",
                    extra={
                        "completed": task.completed,
                        "title": task.title,
                    },
                )
            ],
            provider="roadmap_service",
            trace_id=task.task_uid,
        )
    except Exception:
        logger.warning("Failed to emit RoadmapTaskUpdated audit event", exc_info=True)
    return {
        "task_uid": task.task_uid,
        "completed": task.completed,
    }
