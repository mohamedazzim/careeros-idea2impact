"""Learning path endpoints for verified skill-gap resources."""

from __future__ import annotations

from typing import Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db
from src.services.learning.gap_action_service import get_learning_gap_action_service
from src.services.learning.github_project_service import get_github_project_service
from src.services.learning.learning_path_service import get_learning_path_service
from src.services.learning.learning_outcome_service import get_learning_outcome_service
from src.services.learning.resource_provenance_service import get_resource_provenance_service

router = APIRouter(prefix="/learning", tags=["Learning"])


class LearningResourceResponse(BaseModel):
    id: int
    skill_slug: str
    skill_name: str
    title: str
    provider: str
    source_type: str
    source_url: str
    channel_name: Optional[str] = None
    duration_minutes: Optional[int] = None
    difficulty: Optional[str] = None
    format: Optional[str] = None
    is_free: bool = True
    language: str = "en"
    trust_score: float = 0.0
    relevance_score: float = 0.0
    freshness_score: float = 0.0
    last_verified_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_domain: Optional[str] = None
    discovery_source: Optional[str] = None
    verification_status: Optional[str] = None
    price_status: Optional[str] = None
    cache_status: Optional[str] = None
    provenance_summary: Optional[dict[str, Any]] = None
    outcome_summary: Optional[dict[str, Any]] = None


class ResourceProvenanceSummaryResponse(BaseModel):
    provenance_uid: str
    provenance_type: str
    source_entity_type: str
    source_entity_id: str
    source_table: Optional[str] = None
    source_pk: Optional[str] = None
    recorded_at: Optional[str] = None
    status: str
    confidence: str
    score_total: float
    score_formula: str
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None
    evidence_count: int = 0
    provider: Optional[str] = None
    skill_slug: Optional[str] = None
    skill_name: Optional[str] = None
    title: Optional[str] = None
    source_url: Optional[str] = None
    resource_id: Optional[int] = None
    discovery_run_uid: Optional[str] = None


class ResourceDiscoveryRunResponse(BaseModel):
    run_uid: str
    status: str
    provider: str
    source_type: str
    skill_slug: Optional[str] = None
    skill_name: Optional[str] = None
    candidate_count: int = 0
    stored_count: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class ResourceProvenanceListResponse(BaseModel):
    status: str
    total: int
    records: list[ResourceProvenanceSummaryResponse] = Field(default_factory=list)


class ResourceDiscoveryRunListResponse(BaseModel):
    status: str
    total: int
    runs: list[ResourceDiscoveryRunResponse] = Field(default_factory=list)


class LearningPathStepResponse(BaseModel):
    order_index: int
    step_type: str
    title: str
    reason: Optional[str] = None
    estimated_minutes: Optional[int] = None
    practice_project: Optional[str] = None
    resources: list[LearningResourceResponse] = Field(default_factory=list)


class LearningSkillGapItemResponse(BaseModel):
    skill_slug: str
    skill_name: str
    count: int
    priority: str
    estimated_hours: float
    reason: str
    source_job_ids: list[int] = Field(default_factory=list)
    source_job_titles: list[str] = Field(default_factory=list)
    job_match_ids: list[int] = Field(default_factory=list)
    max_match_score: float = 0.0
    resource_status: str = "available"


class LearningPathResponse(BaseModel):
    skill_slug: str
    skill_name: str
    priority: str
    estimated_hours: float
    reason: str
    source_job_ids: list[int] = Field(default_factory=list)
    source_job_titles: list[str] = Field(default_factory=list)
    job_match_ids: list[int] = Field(default_factory=list)
    resource_status: str
    discovery_status: Optional[str] = None
    resource_count: int = 0
    resource_titles: list[str] = Field(default_factory=list)
    source_domains: list[str] = Field(default_factory=list)
    message: Optional[str] = None
    cached: bool = False
    generated_at: str
    refreshed_at: str
    steps: list[LearningPathStepResponse] = Field(default_factory=list)
    provenance_summary: Optional[dict[str, Any]] = None


class LearningGapSummaryResponse(BaseModel):
    status: str
    user_id: str
    total_gaps: int
    unique_skills: int
    gaps: list[LearningSkillGapItemResponse] = Field(default_factory=list)
    provider_health: dict[str, Any] = Field(default_factory=dict)


class LearningPathsListResponse(BaseModel):
    status: str
    user_id: str
    paths: list[LearningPathResponse] = Field(default_factory=list)
    skill_gaps: list[LearningSkillGapItemResponse] = Field(default_factory=list)
    provider_health: dict[str, Any] = Field(default_factory=dict)


class LearningPathEnvelopeResponse(BaseModel):
    status: str
    user_id: str
    path: Optional[LearningPathResponse] = None
    provider_health: dict[str, Any] = Field(default_factory=dict)
    error: Optional[dict[str, Any]] = None


class GapActionProjectIdeaResponse(BaseModel):
    title: str
    difficulty: str
    estimated_hours: float
    proof_type: str
    steps: list[str] = Field(default_factory=list)
    source_resources: list[LearningResourceResponse] = Field(default_factory=list)
    resume_bullets: list[str] = Field(default_factory=list)
    github_readme_outline: list[str] = Field(default_factory=list)
    source_status: str


class GapActionResumeProofResponse(BaseModel):
    before_gap: str
    suggested_bullets: list[str] = Field(default_factory=list)
    linkedin_bullets: list[str] = Field(default_factory=list)
    portfolio_description: str
    source_status: str


class GapActionInterviewProofResponse(BaseModel):
    talking_points: list[str] = Field(default_factory=list)
    sample_answer: str
    source_status: str


class GapActionSkillResponse(BaseModel):
    skill_slug: str
    skill_name: str
    count: int
    priority: str
    estimated_hours: float
    reason: str
    source_job_ids: list[int] = Field(default_factory=list)
    source_job_titles: list[str] = Field(default_factory=list)
    job_match_ids: list[int] = Field(default_factory=list)
    resource_status: str
    resource_count: int = 0
    source_status: str
    source_resources: list[LearningResourceResponse] = Field(default_factory=list)
    project_ideas: list[GapActionProjectIdeaResponse] = Field(default_factory=list)
    resume_proof: GapActionResumeProofResponse
    interview_proof: GapActionInterviewProofResponse
    provenance_summary: Optional[dict[str, Any]] = None


class JobContextResponse(BaseModel):
    job_id: Optional[int] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    apply_url: Optional[str] = None
    source_url: Optional[str] = None
    match_score: Optional[float] = None
    missing_skill_slugs: list[str] = Field(default_factory=list)
    missing_skill_names: list[str] = Field(default_factory=list)


class GapActionsResponse(BaseModel):
    status: str
    user_id: str
    job_id: Optional[int] = None
    job_context: Optional[JobContextResponse] = None
    cached: bool = False
    generated_at: str
    provider_health: dict[str, Any] = Field(default_factory=dict)
    source_status: str
    actions: list[GapActionSkillResponse] = Field(default_factory=list)


class GitHubProjectRepositoryResponse(BaseModel):
    skill_slug: str
    skill_name: str
    full_name: str
    html_url: str
    description: Optional[str] = None
    language: Optional[str] = None
    stargazers_count: int = 0
    forks_count: int = 0
    watchers_count: int = 0
    is_template: bool = False
    archived: bool = False
    updated_at: Optional[str] = None
    matched_query: str = ""
    matched_terms: list[str] = Field(default_factory=list)
    source_status: str = "available"


class GitHubProjectIssueResponse(BaseModel):
    skill_slug: str
    skill_name: str
    title: str
    html_url: str
    repository_full_name: str
    repository_html_url: str
    label_names: list[str] = Field(default_factory=list)
    state: str = "open"
    score: float = 0.0
    is_pull_request: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    matched_terms: list[str] = Field(default_factory=list)
    source_status: str = "available"


class GitHubProjectSkillResponse(BaseModel):
    skill_slug: str
    skill_name: str
    count: int
    priority: str
    estimated_hours: float
    reason: str
    source_job_ids: list[int] = Field(default_factory=list)
    source_job_titles: list[str] = Field(default_factory=list)
    job_match_ids: list[int] = Field(default_factory=list)
    repository_status: str = "not_available"
    issue_status: str = "not_available"
    source_status: str = "not_available"
    repository_count: int = 0
    template_count: int = 0
    issue_count: int = 0
    repositories: list[GitHubProjectRepositoryResponse] = Field(default_factory=list)
    templates: list[GitHubProjectRepositoryResponse] = Field(default_factory=list)
    good_first_issues: list[GitHubProjectIssueResponse] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provenance_summary: Optional[dict[str, Any]] = None


class GapActionsRequest(BaseModel):
    skills: list[str] = Field(default_factory=list)
    job_id: Optional[int] = None


class GitHubProjectsRequest(BaseModel):
    skills: list[str] = Field(default_factory=list)
    job_id: Optional[int] = None


class RefreshPathsRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=25)


class RefreshPathsResponse(BaseModel):
    status: str
    user_id: str
    refreshed_count: int
    paths: list[LearningPathResponse] = Field(default_factory=list)
    provider_health: dict[str, Any] = Field(default_factory=dict)


class GitHubProjectsResponse(BaseModel):
    status: str
    user_id: str
    job_id: Optional[int] = None
    job_context: Optional[JobContextResponse] = None
    cached: bool = False
    generated_at: str
    provider_health: dict[str, Any] = Field(default_factory=dict)
    source_status: str
    skills: list[GitHubProjectSkillResponse] = Field(default_factory=list)


class LearningResourceTrackingRequest(BaseModel):
    path_id: Optional[int] = None
    path_item_id: Optional[int] = None
    job_id: Optional[int] = None
    skill_slug: Optional[str] = None
    source_ui: Optional[str] = None
    external_resource_url: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningProgressRequest(BaseModel):
    completion_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    notes: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningCompletionRequest(BaseModel):
    notes: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningAbandonRequest(BaseModel):
    reason: Optional[str] = None
    notes: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningFeedbackRequest(BaseModel):
    session_uid: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    difficulty: Optional[str] = None
    would_recommend: Optional[bool] = None
    comment: Optional[str] = None
    helpfulness_score: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    outcome_tag: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningSessionResponse(BaseModel):
    session_uid: str
    user_id: str
    resource_id: Optional[int] = None
    provenance_uid: Optional[str] = None
    path_id: Optional[int] = None
    path_item_id: Optional[int] = None
    skill_slug: str
    job_id: Optional[int] = None
    status: str
    source_ui: Optional[str] = None
    external_resource_url: Optional[str] = None
    started_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    completion_percentage: float = 0.0
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ResourceFeedbackResponse(BaseModel):
    feedback_uid: str
    user_id: str
    resource_id: Optional[int] = None
    provenance_uid: Optional[str] = None
    session_uid: Optional[str] = None
    skill_slug: str
    rating: Optional[float] = None
    difficulty: Optional[str] = None
    would_recommend: Optional[bool] = None
    comment: Optional[str] = None
    helpfulness_score: Optional[float] = None
    outcome_tag: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ResourceOutcomeResponse(BaseModel):
    resource_id: Optional[int] = None
    provenance_uid: Optional[str] = None
    skill_slug: str
    source_type: Optional[str] = None
    provider: Optional[str] = None
    completion_count: int = 0
    started_count: int = 0
    feedback_count: int = 0
    average_rating: Optional[float] = None
    completion_rate: Optional[float] = None
    drop_off_rate: Optional[float] = None
    recommendation_rate: Optional[float] = None
    average_completion_percentage: Optional[float] = None
    average_duration_seconds: Optional[float] = None
    last_calculated_at: Optional[str] = None
    status: str = "insufficient_data"
    calculation_metadata_json: dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class LearningActivityEventResponse(BaseModel):
    activity_uid: str
    user_id: str
    event_type: str
    resource_id: Optional[int] = None
    provenance_uid: Optional[str] = None
    session_uid: Optional[str] = None
    path_id: Optional[int] = None
    path_item_id: Optional[int] = None
    skill_slug: str
    job_id: Optional[int] = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    event_time: Optional[str] = None
    created_at: Optional[str] = None


class LearningTrackingActionResponse(BaseModel):
    status: str
    message: Optional[str] = None
    session: Optional[LearningSessionResponse] = None
    feedback: Optional[ResourceFeedbackResponse] = None
    outcome: Optional[ResourceOutcomeResponse] = None
    event: Optional[LearningActivityEventResponse] = None
    insufficient_data: bool = False


class LearningResourceOutcomeResponse(BaseModel):
    status: str
    outcome: Optional[ResourceOutcomeResponse] = None
    insufficient_data: bool = False
    message: Optional[str] = None


class LearningOutcomeListResponse(BaseModel):
    status: str
    total: int
    outcomes: list[ResourceOutcomeResponse] = Field(default_factory=list)


class LearningActivityListResponse(BaseModel):
    status: str
    total: int
    events: list[LearningActivityEventResponse] = Field(default_factory=list)


def _normalize_resource_payload(resource: dict[str, Any]) -> LearningResourceResponse:
    return LearningResourceResponse.model_validate(resource)


def _normalize_step_payload(step: dict[str, Any]) -> LearningPathStepResponse:
    resources = [_normalize_resource_payload(resource) for resource in step.get("resources", [])]
    step_data = {**step, "resources": resources}
    return LearningPathStepResponse.model_validate(step_data)


def _normalize_path_payload(payload: dict[str, Any]) -> LearningPathResponse:
    steps = [_normalize_step_payload(step) for step in payload.get("steps", [])]
    path_data = {**payload, "steps": steps}
    return LearningPathResponse.model_validate(path_data)


@router.get("/skill-gaps", response_model=LearningGapSummaryResponse)
async def get_skill_gaps(
    limit: int = Query(default=10, ge=1, le=25),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_path_service()
    payload = await service.get_skill_gap_summary(db, user["sub"], limit=limit)
    return LearningGapSummaryResponse.model_validate(payload)


@router.get("/paths", response_model=LearningPathsListResponse)
async def list_paths(
    limit: int = Query(default=10, ge=1, le=25),
    skills: Optional[str] = Query(default=None),
    refresh: bool = Query(default=False),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_path_service()
    skill_slugs = [item.strip() for item in skills.split(",")] if skills else None
    payload = await service.list_paths(db, user["sub"], limit=limit, skill_slugs=skill_slugs, force_refresh=refresh)
    return LearningPathsListResponse(
        status=payload["status"],
        user_id=payload["user_id"],
        paths=[_normalize_path_payload(path) for path in payload.get("paths", [])],
        skill_gaps=[LearningSkillGapItemResponse.model_validate(item) for item in payload.get("skill_gaps", [])],
        provider_health=payload.get("provider_health", {}),
    )


@router.get("/paths/{skill_slug}", response_model=LearningPathEnvelopeResponse)
async def get_path(
    skill_slug: str,
    refresh: bool = Query(default=False),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_path_service()
    payload = await service.get_path(db, user["sub"], skill_slug, force_refresh=refresh)
    if payload.get("status") != "ok" or not payload.get("path"):
        return LearningPathEnvelopeResponse(
            status=payload.get("status", "error"),
            user_id=user["sub"],
            provider_health=payload.get("provider_health", {}),
            error=payload.get("error"),
        )
    return LearningPathEnvelopeResponse(
        status="ok",
        user_id=user["sub"],
        path=_normalize_path_payload(payload["path"]),
        provider_health=payload.get("provider_health", {}),
    )


@router.post("/paths/refresh", response_model=RefreshPathsResponse)
async def refresh_paths(
    request: RefreshPathsRequest = RefreshPathsRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_path_service()
    payload = await service.refresh_paths(db, user["sub"], limit=request.limit)
    return RefreshPathsResponse(
        status=payload["status"],
        user_id=payload["user_id"],
        refreshed_count=payload["refreshed_count"],
        paths=[_normalize_path_payload(path) for path in payload.get("paths", [])],
        provider_health=payload.get("provider_health", {}),
    )


def _split_skill_query(skills: Optional[str]) -> list[str]:
    if not skills:
        return []
    return [item.strip() for item in skills.split(",") if item.strip()]


def _normalize_gap_action_payload(payload: dict[str, Any]) -> GapActionsResponse:
    job_context = payload.get("job_context")
    return GapActionsResponse(
        status=payload.get("status", "error"),
        user_id=payload.get("user_id", ""),
        job_id=payload.get("job_id"),
        job_context=JobContextResponse.model_validate(job_context) if job_context else None,
        cached=bool(payload.get("cached", False)),
        generated_at=payload.get("generated_at") or datetime.utcnow().isoformat() + "Z",
        provider_health=payload.get("provider_health", {}),
        source_status=payload.get("source_status", "generated_from_skill_context_no_external_source"),
        actions=[GapActionSkillResponse.model_validate(action) for action in payload.get("actions", [])],
    )


def _normalize_github_project_payload(payload: dict[str, Any]) -> GitHubProjectsResponse:
    job_context = payload.get("job_context")
    return GitHubProjectsResponse(
        status=payload.get("status", "error"),
        user_id=payload.get("user_id", ""),
        job_id=payload.get("job_id"),
        job_context=JobContextResponse.model_validate(job_context) if job_context else None,
        cached=bool(payload.get("cached", False)),
        generated_at=payload.get("generated_at") or datetime.utcnow().isoformat() + "Z",
        provider_health=payload.get("provider_health", {}),
        source_status=payload.get("source_status", "not_available"),
        skills=[GitHubProjectSkillResponse.model_validate(skill) for skill in payload.get("skills", [])],
    )


def _normalize_learning_tracking_action(payload: dict[str, Any]) -> LearningTrackingActionResponse:
    return LearningTrackingActionResponse.model_validate(payload)


def _normalize_learning_outcome(payload: dict[str, Any]) -> LearningResourceOutcomeResponse:
    return LearningResourceOutcomeResponse.model_validate(payload)


def _normalize_learning_outcomes(payload: list[dict[str, Any]], total: int) -> LearningOutcomeListResponse:
    return LearningOutcomeListResponse(
        status="ok",
        total=total,
        outcomes=[ResourceOutcomeResponse.model_validate(item) for item in payload],
    )


def _normalize_learning_activity(payload: list[dict[str, Any]], total: int) -> LearningActivityListResponse:
    return LearningActivityListResponse(
        status="ok",
        total=total,
        events=[LearningActivityEventResponse.model_validate(item) for item in payload],
    )


@router.get("/gap-actions", response_model=GapActionsResponse)
async def get_gap_actions(
    skills: Optional[str] = Query(default=None),
    job_id: Optional[int] = Query(default=None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill_values = _split_skill_query(skills)
    if not skill_values and job_id is None:
        raise HTTPException(status_code=400, detail="Provide at least one skill or a job_id.")
    service = get_learning_gap_action_service()
    try:
        payload = await service.build_gap_actions(db, user["sub"], skill_values, job_id=job_id, force_refresh=False)
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(status_code=404, detail=message) from exc
    if payload.get("status") != "ok":
        return _normalize_gap_action_payload(payload)
    return _normalize_gap_action_payload(payload)


@router.post("/gap-actions/refresh", response_model=GapActionsResponse)
async def refresh_gap_actions(
    request: GapActionsRequest | None = None,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request is None:
        raise HTTPException(status_code=400, detail="Request body is required and must include skills or a job_id.")
    if not request.skills and request.job_id is None:
        raise HTTPException(status_code=400, detail="Provide at least one skill or a job_id.")
    service = get_learning_gap_action_service()
    try:
        payload = await service.build_gap_actions(db, user["sub"], request.skills, job_id=request.job_id, force_refresh=True)
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(status_code=404, detail=message) from exc
    return _normalize_gap_action_payload(payload)


@router.get("/github-projects", response_model=GitHubProjectsResponse)
async def get_github_projects(
    skills: Optional[str] = Query(default=None),
    job_id: Optional[int] = Query(default=None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill_values = _split_skill_query(skills)
    if not skill_values and job_id is None:
        raise HTTPException(status_code=400, detail="Provide at least one skill or a job_id.")
    service = get_github_project_service()
    try:
        payload = await service.build_github_projects(db, user["sub"], skill_values, job_id=job_id, force_refresh=False)
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(status_code=404, detail=message) from exc
    return _normalize_github_project_payload(payload)


@router.post("/github-projects/refresh", response_model=GitHubProjectsResponse)
async def refresh_github_projects(
    request: GitHubProjectsRequest | None = None,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request is None:
        raise HTTPException(status_code=400, detail="Request body is required and must include skills or a job_id.")
    if not request.skills and request.job_id is None:
        raise HTTPException(status_code=400, detail="Provide at least one skill or a job_id.")
    service = get_github_project_service()
    try:
        payload = await service.build_github_projects(db, user["sub"], request.skills, job_id=request.job_id, force_refresh=True)
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(status_code=404, detail=message) from exc
    return _normalize_github_project_payload(payload)


@router.post("/resources/{resource_id}/open", response_model=LearningTrackingActionResponse)
async def open_learning_resource(
    resource_id: int,
    request: LearningResourceTrackingRequest = LearningResourceTrackingRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.open_resource(
        db,
        user_id=user["sub"],
        resource_id=resource_id,
        path_id=request.path_id,
        path_item_id=request.path_item_id,
        job_id=request.job_id,
        skill_slug=request.skill_slug,
        source_ui=request.source_ui,
        external_resource_url=request.external_resource_url,
        metadata=request.metadata,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Learning resource not found.")
    return _normalize_learning_tracking_action(payload)


@router.post("/resources/{resource_id}/start", response_model=LearningTrackingActionResponse)
async def start_learning_resource(
    resource_id: int,
    request: LearningResourceTrackingRequest = LearningResourceTrackingRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.start_session(
        db,
        user_id=user["sub"],
        resource_id=resource_id,
        path_id=request.path_id,
        path_item_id=request.path_item_id,
        job_id=request.job_id,
        skill_slug=request.skill_slug,
        source_ui=request.source_ui,
        external_resource_url=request.external_resource_url,
        metadata=request.metadata,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Learning resource not found.")
    return _normalize_learning_tracking_action(payload)


@router.patch("/sessions/{session_uid}/progress", response_model=LearningTrackingActionResponse)
async def update_learning_progress(
    session_uid: str,
    request: LearningProgressRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.update_progress(
        db,
        user_id=user["sub"],
        session_uid=session_uid,
        completion_percentage=request.completion_percentage,
        notes=request.notes,
        metadata=request.metadata,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    return _normalize_learning_tracking_action(payload)


@router.post("/sessions/{session_uid}/complete", response_model=LearningTrackingActionResponse)
async def complete_learning_resource(
    session_uid: str,
    request: LearningCompletionRequest = LearningCompletionRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.complete_resource(
        db,
        user_id=user["sub"],
        session_uid=session_uid,
        notes=request.notes,
        metadata=request.metadata,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    return _normalize_learning_tracking_action(payload)


@router.post("/sessions/{session_uid}/abandon", response_model=LearningTrackingActionResponse)
async def abandon_learning_resource(
    session_uid: str,
    request: LearningAbandonRequest = LearningAbandonRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.abandon_resource(
        db,
        user_id=user["sub"],
        session_uid=session_uid,
        reason=request.reason,
        notes=request.notes,
        metadata=request.metadata,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    return _normalize_learning_tracking_action(payload)


@router.post("/resources/{resource_id}/feedback", response_model=LearningTrackingActionResponse)
async def submit_learning_feedback(
    resource_id: int,
    request: LearningFeedbackRequest = LearningFeedbackRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.submit_feedback(
        db,
        user_id=user["sub"],
        resource_id=resource_id,
        session_uid=request.session_uid,
        rating=request.rating,
        difficulty=request.difficulty,
        would_recommend=request.would_recommend,
        comment=request.comment,
        helpfulness_score=request.helpfulness_score,
        outcome_tag=request.outcome_tag,
        metadata=request.metadata,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Learning resource not found.")
    return _normalize_learning_tracking_action(payload)


@router.post("/provenance/{provenance_uid}/open", response_model=LearningTrackingActionResponse)
async def open_learning_resource_by_provenance(
    provenance_uid: str,
    request: LearningResourceTrackingRequest = LearningResourceTrackingRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.open_resource(
        db,
        user_id=user["sub"],
        provenance_uid=provenance_uid,
        path_id=request.path_id,
        path_item_id=request.path_item_id,
        job_id=request.job_id,
        skill_slug=request.skill_slug,
        source_ui=request.source_ui,
        external_resource_url=request.external_resource_url,
        metadata=request.metadata,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Provenance record not found.")
    return _normalize_learning_tracking_action(payload)


@router.post("/provenance/{provenance_uid}/start", response_model=LearningTrackingActionResponse)
async def start_learning_resource_by_provenance(
    provenance_uid: str,
    request: LearningResourceTrackingRequest = LearningResourceTrackingRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.start_session(
        db,
        user_id=user["sub"],
        provenance_uid=provenance_uid,
        path_id=request.path_id,
        path_item_id=request.path_item_id,
        job_id=request.job_id,
        skill_slug=request.skill_slug,
        source_ui=request.source_ui,
        external_resource_url=request.external_resource_url,
        metadata=request.metadata,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Provenance record not found.")
    return _normalize_learning_tracking_action(payload)


@router.post("/provenance/{provenance_uid}/feedback", response_model=LearningTrackingActionResponse)
async def submit_learning_feedback_by_provenance(
    provenance_uid: str,
    request: LearningFeedbackRequest = LearningFeedbackRequest(),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.submit_feedback(
        db,
        user_id=user["sub"],
        provenance_uid=provenance_uid,
        session_uid=request.session_uid,
        rating=request.rating,
        difficulty=request.difficulty,
        would_recommend=request.would_recommend,
        comment=request.comment,
        helpfulness_score=request.helpfulness_score,
        outcome_tag=request.outcome_tag,
        metadata=request.metadata,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Provenance record not found.")
    return _normalize_learning_tracking_action(payload)


@router.get("/resources/{resource_id}/outcome", response_model=LearningResourceOutcomeResponse)
async def get_learning_resource_outcome(
    resource_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.get_resource_outcome(db, resource_id=resource_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Learning resource not found.")
    return _normalize_learning_outcome(payload)


@router.get("/provenance/{provenance_uid}/outcome", response_model=LearningResourceOutcomeResponse)
async def get_learning_resource_outcome_by_provenance(
    provenance_uid: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    payload = await service.get_resource_outcome(db, provenance_uid=provenance_uid)
    if payload is None:
        raise HTTPException(status_code=404, detail="Provenance record not found.")
    return _normalize_learning_outcome(payload)


@router.get("/outcomes", response_model=LearningOutcomeListResponse)
async def list_learning_outcomes(
    skill_slug: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    resource_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    outcomes, total = await service.list_resource_outcomes(
        db,
        skill_slug=skill_slug,
        provider=provider,
        status=status,
        resource_id=resource_id,
        limit=limit,
        offset=offset,
    )
    return _normalize_learning_outcomes(outcomes, total)


@router.get("/activity", response_model=LearningActivityListResponse)
async def list_learning_activity(
    event_type: Optional[str] = Query(default=None),
    resource_id: Optional[int] = Query(default=None),
    provenance_uid: Optional[str] = Query(default=None),
    session_uid: Optional[str] = Query(default=None),
    skill_slug: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_learning_outcome_service()
    events, total = await service.list_user_learning_activity(
        db,
        user_id=user["sub"],
        event_type=event_type,
        resource_id=resource_id,
        provenance_uid=provenance_uid,
        session_uid=session_uid,
        skill_slug=skill_slug,
        limit=limit,
        offset=offset,
    )
    return _normalize_learning_activity(events, total)


@router.get("/provenance", response_model=ResourceProvenanceListResponse)
async def list_provenance(
    skill_slug: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    source_type: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None),
    job_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    resource_id: Optional[int] = Query(default=None),
    source_entity_type: Optional[str] = Query(default=None),
    source_entity_id: Optional[str] = Query(default=None),
    provenance_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_resource_provenance_service()
    records, total = await service.list_provenance(
        db,
        user_id=user["sub"],
        resource_id=resource_id,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        provenance_type=provenance_type,
        skill_slug=skill_slug,
        provider=provider,
        source_type=source_type,
        resource_type=resource_type,
        job_id=job_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ResourceProvenanceListResponse(status="ok", total=total, records=[ResourceProvenanceSummaryResponse.model_validate(record) for record in records])


@router.get("/provenance/{provenance_uid}", response_model=ResourceProvenanceSummaryResponse)
async def get_provenance(
    provenance_uid: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_resource_provenance_service()
    record = await service.get_provenance_by_uid(db, provenance_uid, user_id=user["sub"])
    if not record:
        raise HTTPException(status_code=404, detail="Provenance record not found.")
    return ResourceProvenanceSummaryResponse.model_validate(record)


@router.get("/resources/{resource_id}/provenance", response_model=ResourceProvenanceListResponse)
async def get_resource_provenance(
    resource_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_resource_provenance_service()
    records, total = await service.list_provenance(db, user_id=user["sub"], resource_id=resource_id, limit=limit, offset=offset)
    return ResourceProvenanceListResponse(status="ok", total=total, records=[ResourceProvenanceSummaryResponse.model_validate(record) for record in records])


@router.get("/discovery-runs", response_model=ResourceDiscoveryRunListResponse)
async def list_discovery_runs(
    skill_slug: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_resource_provenance_service()
    runs, total = await service.list_discovery_runs(
        db,
        user_id=user["sub"],
        skill_slug=skill_slug,
        provider=provider,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ResourceDiscoveryRunListResponse(status="ok", total=total, runs=[ResourceDiscoveryRunResponse.model_validate(run) for run in runs])


@router.get("/discovery-runs/{run_uid}", response_model=ResourceDiscoveryRunResponse)
async def get_discovery_run(
    run_uid: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_resource_provenance_service()
    run = await service.get_discovery_run_by_uid(db, run_uid, user_id=user["sub"])
    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found.")
    return ResourceDiscoveryRunResponse.model_validate(run)
