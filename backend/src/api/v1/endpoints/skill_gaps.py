"""Evidence-backed skill gap engine endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db
from src.models.jobs import Job
from src.schemas.skill_gap import (
    SkillGapAnalyzeRequest,
    SkillGapAnalysisResponse,
    SkillGapFindingListResponse,
    SkillGapJobResponse,
    SkillGapRunDetailResponse,
    SkillGapRunListResponse,
    SkillGapSnapshotResponse,
    SkillGapSkillEvidenceResponse,
)
from src.services.skill_gap import get_skill_gap_engine_service, get_skill_gap_query_service

router = APIRouter(prefix="/skill-gaps", tags=["Skill Gaps"])


@router.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "skill_gap_engine",
        "analysis_version": "m5_evidence_backed_skill_gap_v1",
    }


@router.post("/analyze", response_model=SkillGapAnalysisResponse)
async def analyze_skill_gaps(
    request: SkillGapAnalyzeRequest,
    limit: int = Query(default=25, ge=1, le=25),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request.source_scope == "job":
        if request.job_id is None:
            raise HTTPException(status_code=400, detail="job_id is required for job scope.")
        job_result = await db.execute(select(Job).where(Job.id == request.job_id, Job.deleted_at.is_(None)))
        if job_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Job not found.")
    engine = get_skill_gap_engine_service()
    payload = await engine.analyze(
        db,
        user_id=user["sub"],
        source_scope=request.source_scope,
        job_id=request.job_id,
        target_role_slug=request.target_role_slug,
        limit=limit,
    )
    if payload.get("status") != "ok":
        detail = payload.get("error") or {"code": "SKILL_GAP_ANALYSIS_FAILED", "message": "Skill gap analysis failed."}
        raise HTTPException(status_code=400, detail=detail)
    query_service = get_skill_gap_query_service()
    run_detail = await query_service.get_run(db, user_id=user["sub"], run_uid=payload["run_uid"])
    if run_detail is None:
        return SkillGapAnalysisResponse(run_uid=payload["run_uid"], status="ok", summary=payload["summary"], findings=[])
    return SkillGapAnalysisResponse(
        run_uid=run_detail.run.run_uid,
        status=run_detail.status,
        summary=run_detail.summary,
        findings=run_detail.findings,
    )


@router.get("/runs", response_model=SkillGapRunListResponse)
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_skill_gap_query_service().list_runs(db, user_id=user["sub"], limit=limit, offset=offset)


@router.get("/runs/{run_uid}", response_model=SkillGapRunDetailResponse)
async def get_run(
    run_uid: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = await get_skill_gap_query_service().get_run(db, user_id=user["sub"], run_uid=run_uid)
    if payload is None:
        raise HTTPException(status_code=404, detail="Skill gap analysis run not found.")
    return payload


@router.get("/jobs/{job_id}", response_model=SkillGapJobResponse)
async def get_job_analysis(
    job_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job_result = await db.execute(select(Job).where(Job.id == job_id, Job.deleted_at.is_(None)))
    if job_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return await get_skill_gap_query_service().get_job_response(db, user_id=user["sub"], job_id=job_id)


@router.get("/snapshot", response_model=SkillGapSnapshotResponse)
async def get_snapshot(
    source_scope: str = Query(default="job"),
    job_id: int | None = Query(default=None),
    target_role_slug: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_skill_gap_query_service().get_snapshot(
        db,
        user_id=user["sub"],
        source_scope=source_scope,
        job_id=job_id,
        target_role_slug=target_role_slug,
    )


@router.get("/skills/{skill_slug}/evidence", response_model=SkillGapSkillEvidenceResponse)
async def get_skill_evidence(
    skill_slug: str,
    run_uid: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_skill_gap_query_service().get_skill_evidence(db, user_id=user["sub"], skill_slug=skill_slug, run_uid=run_uid)


@router.get("/findings", response_model=SkillGapFindingListResponse)
async def list_findings(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_skill_gap_query_service().list_findings(db, user_id=user["sub"], limit=limit, offset=offset)
