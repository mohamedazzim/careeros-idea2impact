"""Skill graph inspection and import endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.session import get_db
from src.schemas.skill_graph import (
    SkillGraphDetailResponse,
    SkillGraphHealthResponse,
    SkillGraphImportRequest,
    SkillGraphImportResponse,
    SkillGraphImportRunListResponse,
    SkillGraphNodeListResponse,
    SkillGraphStateListResponse,
    SkillGraphSummaryResponse,
)
from src.services.skill_graph import get_skill_graph_service

router = APIRouter(prefix="/skill-graph", tags=["Skill Graph"])


@router.get("/health", response_model=SkillGraphHealthResponse)
async def skill_graph_health(db: AsyncSession = Depends(get_db)):
    service = get_skill_graph_service()
    payload = await service.get_health(db)
    return SkillGraphHealthResponse.model_validate(payload)


@router.get("/summary", response_model=SkillGraphSummaryResponse)
async def skill_graph_summary(
    limit: int = Query(default=12, ge=1, le=50),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_skill_graph_service()
    payload = await service.get_summary(db, user_id=user["sub"], limit=limit)
    return SkillGraphSummaryResponse.model_validate(payload)


@router.get("/nodes", response_model=SkillGraphNodeListResponse)
async def list_skill_nodes(
    search: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_skill_graph_service()
    nodes = await service.list_nodes(db, search=search, limit=limit)
    return SkillGraphNodeListResponse(status="ok", total=len(nodes), nodes=[node for node in nodes])


@router.get("/nodes/{skill_slug}", response_model=SkillGraphDetailResponse)
async def get_skill_node(
    skill_slug: str,
    limit: int = Query(default=12, ge=1, le=50),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_skill_graph_service()
    try:
        payload = await service.get_node_detail(db, skill_slug, user_id=user["sub"], limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SkillGraphDetailResponse.model_validate(payload)


@router.get("/states", response_model=SkillGraphStateListResponse)
async def list_skill_states(
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_skill_graph_service()
    states = await service.list_user_states(db, user_id=user["sub"], limit=limit)
    return SkillGraphStateListResponse(status="ok", total=len(states), states=[state for state in states])


@router.get("/import-runs", response_model=SkillGraphImportRunListResponse)
async def list_import_runs(
    limit: int = Query(default=10, ge=1, le=50),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_skill_graph_service()
    runs = await service.list_import_runs(db, limit=limit)
    return SkillGraphImportRunListResponse(status="ok", total=len(runs), runs=[run for run in runs])


@router.post("/import", response_model=SkillGraphImportResponse)
async def import_skill_graph(
    request: SkillGraphImportRequest = Body(default_factory=SkillGraphImportRequest),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_skill_graph_service()
    payload = await service.import_graph(db, user_id=user["sub"], request=request)
    return SkillGraphImportResponse.model_validate(payload)
