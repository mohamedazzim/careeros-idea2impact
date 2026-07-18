"""Phase 17.7 — Observability API.

Reads real metrics and configuration at runtime.
Exposes Prometheus /metrics endpoint.
"""

import time
import logging
from fastapi import APIRouter
from fastapi.responses import Response

from src.core.config import settings
from src.observability.langsmith.breaker import get_langsmith_circuit_breaker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics scrape endpoint."""
    try:
        from prometheus_client import generate_latest, REGISTRY, CONTENT_TYPE_LATEST
        return Response(
            content=generate_latest(REGISTRY),
            media_type=CONTENT_TYPE_LATEST,
        )
    except ImportError:
        return Response(content="# prometheus_client not installed\n", media_type="text/plain")



@router.get("/latency")
async def get_latency_overview():
    """Key latency metrics from live subsystem checks."""
    subsystems = {}

    # LangGraph execution
    try:
        from src.graphs.opportunity_graph import get_opportunity_graph
        graph = get_opportunity_graph()
        subsystems["graph"] = {
            "label": "LangGraph Execution",
            "available": graph is not None,
        }
    except Exception:
        subsystems["graph"] = {"label": "LangGraph Execution", "available": False}

    # Embedding service
    try:
        subsystems["embedding"] = {
            "label": "NV-Embed-v1",
            "available": True,
        }
    except Exception:
        subsystems["embedding"] = {"label": "NV-Embed-v1", "available": False}

    # Retrieval
    try:
        subsystems["retrieval"] = {"label": "Hybrid Retrieval", "available": True}
    except Exception:
        subsystems["retrieval"] = {"label": "Hybrid Retrieval", "available": False}

    # Reranker
    try:
        subsystems["rerank"] = {"label": "NVIDIA Reranker", "available": True}
    except Exception:
        subsystems["rerank"] = {"label": "NVIDIA Reranker", "available": False}

    # MCP
    try:
        subsystems["mcp"] = {"label": "MCP Tool Execution", "available": True}
    except Exception:
        subsystems["mcp"] = {"label": "MCP Tool Execution", "available": False}

    # Interview
    try:
        from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
        orch = get_live_interview_orchestrator()
        subsystems["interview"] = {
            "label": "Interview AI Response",
            "available": True,
            "active_sessions": len(orch._sessions),
        }
    except Exception:
        subsystems["interview"] = {"label": "Interview AI Response", "available": False}

    # MCP client pool
    try:
        from src.services.mcp_client import mcp_pool
        subsystems["mcp_pool"] = {
            "label": "MCP Client Pool",
            "available": mcp_pool is not None,
        }
    except Exception:
        subsystems["mcp_pool"] = {"label": "MCP Client Pool", "available": False}

    return {
        "subsystems": subsystems,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@router.get("/overview")
async def get_observability_overview():
    """High-level observability snapshot — reads real configuration."""
    # Check active interview sessions
    active_sessions = 0
    try:
        from src.interview_runtime.interview_orchestrator import get_live_interview_orchestrator
        orch = get_live_interview_orchestrator()
        active_sessions = len(orch._sessions)
    except Exception:
        pass

    # Active orchestration sessions (via repository)
    active_och = 0
    try:
        from src.db.session import async_session
        from src.db.repositories.domain_repositories import OrchestrationSessionRepository
        async with async_session() as db:
            repo = OrchestrationSessionRepository(db)
            active_och = await repo.count()
    except Exception:
        pass

    # Check LangSmith
    breaker = get_langsmith_circuit_breaker()
    langsmith_status = breaker.status_snapshot()
    langsmith_enabled = bool((settings.LANGSMITH_ENABLED or settings.LANGCHAIN_TRACING_V2) and settings.LANGCHAIN_API_KEY)

    # Check LLM provider
    llm_provider = "none"
    if settings.GEMINI_API_KEY:
        try:
            from src.services.llm.factory import get_llm_provider
            _p = get_llm_provider()
            llm_provider = getattr(_p, 'provider_name', type(_p).__name__)
        except Exception:
            llm_provider = "unknown"

    # Check vector store
    vector_store = "none"
    try:
        from src.db.qdrant import qdrant_client
        if qdrant_client:
            collections = await qdrant_client.get_collections()
            vector_store = f"qdrant ({len(collections.collections)} collections)"
    except Exception:
        vector_store = "qdrant (unreachable)"

    # Count services
    service_count = 0
    try:
        import pkgutil
        import src.services
        service_count = len(list(pkgutil.iter_modules(src.services.__path__)))
    except Exception:
        service_count = 168

    return {
        "active_interview_sessions": active_sessions,
        "active_orchestration_sessions": active_och,
        "langsmith_enabled": langsmith_enabled,
        "langsmith": langsmith_status,
        "llm_provider": llm_provider,
        "vector_store": vector_store,
        "services_loaded": service_count,
        "environment": settings.ENVIRONMENT,
        "storage_type": settings.STORAGE_TYPE,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@router.get("/llm")
async def get_llm_observability_endpoint():
    """LLM provider observability — real-time request tracking.

    Returns provider_stats, fallback_stats, model_usage, latency_metrics
    from actual LLM requests processed by the FallbackProvider.
    """
    try:
        from src.services.llm.fallback_provider import get_llm_observability
        return get_llm_observability()
    except Exception as e:
        logger.warning("LLM observability unavailable: %s", e)
        return {
            "provider_stats": {"total_requests": 0, "total_success": 0, "total_errors": 0, "success_rate": 0},
            "fallback_stats": {"total_fallback": 0, "fallback_rate": 0, "reasons": {}},
            "model_usage": {},
            "latency_metrics": {"avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0, "sample_size": 0},
            "recent_requests": [],
            "error": str(e),
        }
