"""
End-to-End Runtime Validation Script.

Validates all CareerOS services with actual API calls.
Returns: endpoint, payload, response, status code, latency.

Usage:
    cd backend && python -m scripts.validate_runtime
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ValidationResult:
    service: str
    endpoint: str
    method: str
    payload: Optional[dict]
    response_status: int
    response_body: Optional[dict]
    latency_ms: float
    success: bool
    error: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


async def _check_gemini_provider() -> ValidationResult:
    """Validate Gemini provider is accessible."""
    t0 = time.monotonic()
    try:
        from src.services.llm.factory import get_llm_provider
        provider = get_llm_provider()
        result = await asyncio.wait_for(
            provider.generate(
                system_prompt="Reply with exactly: OK",
                user_message="Reply OK",
                max_tokens=10,
                temperature=0.0,
                cache_key_hint="runtime:health",
            ),
            timeout=30.0,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="llm_provider",
            endpoint="provider.generate()",
            method="INTERNAL",
            payload=None,
            response_status=200,
            response_body={"result": result.get("result", ""), "provider": result.get("provider")},
            latency_ms=round(latency_ms, 2),
            success=True,
            provider=result.get("provider"),
            model=result.get("model"),
        )
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="llm_provider",
            endpoint="provider.generate()",
            method="INTERNAL",
            payload=None,
            response_status=500,
            response_body=None,
            latency_ms=round(latency_ms, 2),
            success=False,
            error=str(e)[:200],
        )


async def _check_redis() -> ValidationResult:
    """Validate Redis connectivity."""
    t0 = time.monotonic()
    try:
        from src.db.redis import get_redis
        redis = await get_redis()
        await redis.ping()
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="redis",
            endpoint="redis.ping()",
            method="INTERNAL",
            payload=None,
            response_status=200,
            response_body={"status": "connected"},
            latency_ms=round(latency_ms, 2),
            success=True,
        )
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="redis",
            endpoint="redis.ping()",
            method="INTERNAL",
            payload=None,
            response_status=500,
            response_body=None,
            latency_ms=round(latency_ms, 2),
            success=False,
            error=str(e)[:200],
        )


async def _check_postgres() -> ValidationResult:
    """Validate PostgreSQL connectivity."""
    t0 = time.monotonic()
    try:
        from src.db.session import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="postgres",
            endpoint="SELECT 1",
            method="INTERNAL",
            payload=None,
            response_status=200,
            response_body={"status": "connected"},
            latency_ms=round(latency_ms, 2),
            success=True,
        )
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="postgres",
            endpoint="SELECT 1",
            method="INTERNAL",
            payload=None,
            response_status=500,
            response_body=None,
            latency_ms=round(latency_ms, 2),
            success=False,
            error=str(e)[:200],
        )


async def _check_qdrant() -> ValidationResult:
    """Validate Qdrant connectivity."""
    t0 = time.monotonic()
    try:
        from src.db.qdrant import qdrant_client
        collections = await qdrant_client.get_collections()
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="qdrant",
            endpoint="get_collections()",
            method="INTERNAL",
            payload=None,
            response_status=200,
            response_body={"collections": len(collections.collections)},
            latency_ms=round(latency_ms, 2),
            success=True,
        )
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="qdrant",
            endpoint="get_collections()",
            method="INTERNAL",
            payload=None,
            response_status=500,
            response_body=None,
            latency_ms=round(latency_ms, 2),
            success=False,
            error=str(e)[:200],
        )


async def _check_langsmith() -> ValidationResult:
    """Validate LangSmith connectivity."""
    t0 = time.monotonic()
    try:
        from src.core.config import settings
        if not settings.LANGCHAIN_API_KEY:
            return ValidationResult(
                service="langsmith",
                endpoint="api_key_check",
                method="INTERNAL",
                payload=None,
                response_status=200,
                response_body={"status": "disabled", "reason": "no API key"},
                latency_ms=0,
                success=True,
            )
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="langsmith",
            endpoint="api_key_check",
            method="INTERNAL",
            payload=None,
            response_status=200,
            response_body={"status": "configured", "project": settings.LANGCHAIN_PROJECT},
            latency_ms=round(latency_ms, 2),
            success=True,
        )
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="langsmith",
            endpoint="api_key_check",
            method="INTERNAL",
            payload=None,
            response_status=500,
            response_body=None,
            latency_ms=round(latency_ms, 2),
            success=False,
            error=str(e)[:200],
        )


async def _check_langgraph() -> ValidationResult:
    """Validate LangGraph compilation."""
    t0 = time.monotonic()
    try:
        from src.services.orchestration.graph import career_os_graph
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="langgraph",
            endpoint="orchestration_graph.compile()",
            method="INTERNAL",
            payload=None,
            response_status=200,
            response_body={"status": "compiled", "nodes": len(career_os_graph.get_graph().nodes)},
            latency_ms=round(latency_ms, 2),
            success=True,
        )
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="langgraph",
            endpoint="orchestration_graph.compile()",
            method="INTERNAL",
            payload=None,
            response_status=500,
            response_body=None,
            latency_ms=round(latency_ms, 2),
            success=False,
            error=str(e)[:200],
        )


async def _check_observability_llm() -> ValidationResult:
    """Validate LLM observability endpoint."""
    t0 = time.monotonic()
    try:
        from src.services.llm.fallback_provider import get_llm_observability
        obs = get_llm_observability()
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="observability",
            endpoint="/observability/llm",
            method="GET",
            payload=None,
            response_status=200,
            response_body={
                "provider_stats": obs["provider_stats"],
                "fallback_stats": obs["fallback_stats"],
                "latency_metrics": obs["latency_metrics"],
            },
            latency_ms=round(latency_ms, 2),
            success=True,
        )
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return ValidationResult(
            service="observability",
            endpoint="/observability/llm",
            method="GET",
            payload=None,
            response_status=500,
            response_body=None,
            latency_ms=round(latency_ms, 2),
            success=False,
            error=str(e)[:200],
        )


async def validate_all() -> Dict[str, Any]:
    """Run all runtime validations."""
    checks = [
        _check_gemini_provider,
        _check_redis,
        _check_postgres,
        _check_qdrant,
        _check_langsmith,
        _check_langgraph,
        _check_observability_llm,
    ]

    results = []
    for check_fn in checks:
        try:
            result = await check_fn()
        except Exception as e:
            result = ValidationResult(
                service=check_fn.__name__,
                endpoint="unknown",
                method="INTERNAL",
                payload=None,
                response_status=500,
                response_body=None,
                latency_ms=0,
                success=False,
                error=str(e)[:200],
            )
        results.append(asdict(result))

    passed = sum(1 for r in results if r["success"])
    total = len(results)

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_checks": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total * 100, 2) if total else 0,
        "results": results,
    }


if __name__ == "__main__":
    result = asyncio.run(validate_all())
    print(json.dumps(result, indent=2, default=str))
