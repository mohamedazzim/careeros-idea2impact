"""
Enterprise rerank API endpoints.

Exposes:
- POST /api/v1/rerank        — Execute reranking with full observability
- GET  /api/v1/rerank/health — Circuit breaker and service health
- GET  /api/v1/rerank/stats  — Aggregated metrics from persisted runs
- GET  /api/v1/rerank/history — Historical rerank runs with filtering
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.services.reranking.enterprise_reranker import get_enterprise_reranker
from src.schemas.retrieval import RetrievedChunk

router = APIRouter(prefix="/rerank", tags=["Reranking"])


# ── Request / Response Schemas ─────────────────────────────────────────

class RerankRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query for reranking")
    chunks: List[dict] = Field(..., min_length=1, description="Retrieved chunks to rerank")
    top_n: int = Field(default=10, ge=1, le=100, description="Number of top results to return")
    use_boosts: bool = Field(default=True, description="Enable skill/section/chronology boosts")


class RerankResponse(BaseModel):
    run_id: str
    query: str
    chunks_submitted: int
    chunks_returned: int
    primary_success: bool
    fallback_used: bool
    reranked_chunks: List[dict]
    observation: dict
    latency_ms: float


class RerankHealthResponse(BaseModel):
    status: str
    circuit_breaker_open: bool
    fallback_strategy: str
    model: str
    max_batch: int
    max_retries: int
    timeout_s: int


class RerankStatsResponse(BaseModel):
    total_runs: int
    success_rate: float
    fallback_rate: float
    avg_latency_ms: float
    avg_confidence: float
    avg_chunks_submitted: float
    avg_chunks_returned: float
    circuit_breaker_opens: int


class RerankHistoryItem(BaseModel):
    id: str
    query: str
    chunks_submitted: int
    chunks_returned: int
    primary_success: bool
    fallback_used: bool
    fallback_strategy: Optional[str] = None
    primary_latency_ms: Optional[float] = None
    confidence_avg: Optional[float] = None
    created_at: str

    class Config:
        from_attributes = True


class RerankHistoryResponse(BaseModel):
    runs: List[RerankHistoryItem]
    total: int


# ── POST /rerank ───────────────────────────────────────────────────────

@router.post(
    "",
    response_model=RerankResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute reranking with full enterprise pipeline",
    description="Reranks chunks against a query using NVIDIA rerank-qa-mistral-4b with skill/section/chronology boosts, circuit breaker, and fallbacks.",
)
async def rerank_execute(
    request: RerankRequest,
    user: dict = Depends(get_current_user),
):
    enterprise = get_enterprise_reranker()

    chunks = [
        RetrievedChunk(
            id=c.get("id", str(i)),
            text=c.get("text", ""),
            score=c.get("score", 0.0),
            source=c.get("source"),
            metadata=c.get("metadata", {}),
        )
        for i, c in enumerate(request.chunks)
    ]

    result = await enterprise.rerank(
        query=request.query,
        chunks=chunks,
        top_n=request.top_n,
        user_id=user.get("sub"),
        use_boosts=request.use_boosts,
        persist=True,
    )

    return RerankResponse(
        run_id=result["run_id"],
        query=request.query,
        chunks_submitted=len(chunks),
        chunks_returned=len(result["reranked_chunks"]),
        primary_success=result["primary_success"],
        fallback_used=result["fallback_used"],
        reranked_chunks=[c.model_dump() for c in result["reranked_chunks"]],
        observation=result["observation"].model_dump() if result["observation"] else {},
        latency_ms=result["observation"].rerank_latency_ms,
    )


# ── GET /rerank/health ─────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=RerankHealthResponse,
    summary="Reranker circuit breaker and health status",
)
async def rerank_health():
    enterprise = get_enterprise_reranker()
    stats = enterprise.get_stats_sync()

    status_str = "degraded" if stats["circuit_breaker_open"] else "healthy"

    return RerankHealthResponse(
        status=status_str,
        circuit_breaker_open=stats["circuit_breaker_open"],
        fallback_strategy=stats["fallback_strategy"],
        model=stats["model"],
        max_batch=stats["max_batch"],
        max_retries=stats["max_retries"],
        timeout_s=stats["timeout_s"],
    )


# ── GET /rerank/stats ──────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=RerankStatsResponse,
    summary="Aggregated reranking statistics from persisted runs",
)
async def rerank_stats(
    user: dict = Depends(get_current_user),
):
    try:
        from src.db.session import async_session
        from src.db.repositories.rerank_repository import RerankRepository
        async with async_session() as db:
            repo = RerankRepository(db)
            stats = await repo.get_stats()
        return RerankStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to retrieve rerank stats: {str(e)}",
        )


# ── GET /rerank/history ────────────────────────────────────────────────

@router.get(
    "/history",
    response_model=RerankHistoryResponse,
    summary="Historical rerank runs with pagination",
)
async def rerank_history(
    user_id: Optional[str] = Query(default=None, description="Filter by user ID"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
):
    try:
        from src.db.session import async_session
        from src.db.repositories.rerank_repository import RerankRepository
        async with async_session() as db:
            repo = RerankRepository(db)
            runs = await repo.list_runs(user_id=user_id, limit=limit, offset=offset)
            total = await repo.count()

        items = [
            RerankHistoryItem(
                id=str(r.id),
                query=r.query,
                chunks_submitted=r.chunks_submitted,
                chunks_returned=r.chunks_returned,
                primary_success=r.primary_success,
                fallback_used=r.fallback_used,
                fallback_strategy=r.fallback_strategy,
                primary_latency_ms=r.primary_latency_ms,
                confidence_avg=r.confidence_avg,
                created_at=r.created_at.isoformat(),
            )
            for r in runs
        ]
        return RerankHistoryResponse(runs=items, total=total)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to retrieve rerank history: {str(e)}",
        )
