"""
Production-grade health check endpoints.
Validates all critical subsystems with real connection tests.
"""
import time
import asyncio
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from src.db.session import async_session
from src.db.redis import redis_client
from src.db.qdrant import qdrant_client
from src.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


class HealthCheckError(Exception):
    """Raised when a health check fails."""
    pass


async def check_database() -> Dict[str, Any]:
    """
    Check database connectivity and performance.
    """
    start_time = time.time()
    try:
        async with async_session() as db:
            # Test basic connectivity
            result = await db.execute(text("SELECT 1"))
            result.scalar()
            
            # Test actual table access
            result = await db.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"))
            table_count = result.scalar()
            
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "tables": table_count
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "status": "unhealthy",
            "latency_ms": round(latency_ms, 2),
            "error": str(e)
        }


async def check_redis() -> Dict[str, Any]:
    """
    Check Redis connectivity and performance.
    """
    start_time = time.time()
    try:
        # Test ping
        await redis_client.ping()
        
        # Test write/read
        test_key = f"health:{datetime.utcnow().isoformat()}"
        await redis_client.setex(test_key, 10, "healthy")
        value = await redis_client.get(test_key)
        await redis_client.delete(test_key)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "test_value": value == "healthy"
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "status": "unhealthy",
            "latency_ms": round(latency_ms, 2),
            "error": str(e)
        }


async def check_qdrant() -> Dict[str, Any]:
    """
    Check Qdrant vector database connectivity.
    """
    start_time = time.time()
    try:
        # Get collections info (Async client requires awaiting)
        collections = await qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "collections": len(collection_names),
            "collection_names": collection_names
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "status": "unhealthy",
            "latency_ms": round(latency_ms, 2),
            "error": str(e)
        }


async def check_storage() -> Dict[str, Any]:
    """
    Check storage backend connectivity.
    """
    start_time = time.time()
    try:
        from src.services.storage import storage_client
        
        # Test write/read
        test_content = b"health_check_test"
        test_filename = f"health_check_{datetime.utcnow().timestamp()}.txt"
        
        # Write
        path = await storage_client.save_file(test_filename, test_content)
        
        # Read
        read_content = await storage_client.read_file(test_filename)
        
        # Cleanup
        await storage_client.delete_file(test_filename)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "storage_type": settings.STORAGE_TYPE,
            "read_write_ok": read_content == test_content
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "status": "unhealthy",
            "latency_ms": round(latency_ms, 2),
            "storage_type": settings.STORAGE_TYPE,
            "error": str(e)
        }


@router.get("/live", response_model=Dict[str, Any])
async def health_live() -> Dict[str, Any]:
    """
    Kubernetes/Docker liveness probe.
    Returns 200 if the process is running - no external dependencies checked.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }


@router.get("/ready", response_model=Dict[str, Any])
async def health_ready() -> Dict[str, Any]:
    """
    Kubernetes/Docker readiness probe.
    Verifies critical subsystems are accessible.
    
    Returns 200 only if all critical dependencies are healthy.
    """
    # Run checks in parallel
    results = await asyncio.gather(
        check_database(),
        check_redis(),
        check_qdrant(),
        return_exceptions=True
    )
    
    db_result = results[0] if not isinstance(results[0], Exception) else {"status": "unhealthy", "error": str(results[0])}
    redis_result = results[1] if not isinstance(results[1], Exception) else {"status": "unhealthy", "error": str(results[1])}
    qdrant_result = results[2] if not isinstance(results[2], Exception) else {"status": "unhealthy", "error": str(results[2])}
    
    all_healthy = all(
        r.get("status") == "healthy" 
        for r in [db_result, redis_result, qdrant_result]
    )
    
    response = {
        "status": "ok" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {
            "database": db_result,
            "redis": redis_result,
            "qdrant": qdrant_result
        }
    }
    
    if not all_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response
        )
    
    return response


@router.get("/deep", response_model=Dict[str, Any])
async def health_deep() -> Dict[str, Any]:
    """
    Deep health check with detailed diagnostics.
    Verifies all subsystems including storage.
    
    Use for: detailed diagnostics, debugging, pre-deployment validation
    """
    start_time = time.time()
    
    # Run all checks in parallel
    results = await asyncio.gather(
        check_database(),
        check_redis(),
        check_qdrant(),
        check_storage(),
        return_exceptions=True
    )
    
    db_result = results[0] if not isinstance(results[0], Exception) else {"status": "unhealthy", "error": str(results[0])}
    redis_result = results[1] if not isinstance(results[1], Exception) else {"status": "unhealthy", "error": str(results[1])}
    qdrant_result = results[2] if not isinstance(results[2], Exception) else {"status": "unhealthy", "error": str(results[2])}
    storage_result = results[3] if not isinstance(results[3], Exception) else {"status": "unhealthy", "error": str(results[3])}
    
    total_latency_ms = (time.time() - start_time) * 1000
    
    # Count healthy services
    services = {
        "database": db_result,
        "redis": redis_result,
        "qdrant": qdrant_result,
        "storage": storage_result
    }
    
    healthy_count = sum(1 for r in services.values() if r.get("status") == "healthy")
    total_count = len(services)
    
    response = {
        "status": "healthy" if healthy_count == total_count else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.ENVIRONMENT,
        "version": "2.0.0",  # TODO: Get from git or package
        "uptime_seconds": None,  # TODO: Track from app startup
        "services": services,
        "summary": {
            "healthy": healthy_count,
            "total": total_count,
            "total_latency_ms": round(total_latency_ms, 2)
        },
        "configuration": {
            "storage_type": settings.STORAGE_TYPE,
            "langsmith_enabled": settings.LANGCHAIN_TRACING_V2,
            "environment": settings.ENVIRONMENT
        }
    }
    
    return response


@router.get("/detailed", response_model=Dict[str, Any])
async def health_detailed() -> Dict[str, Any]:
    """Detailed infrastructure component health — used by Ops Center."""
    results = await asyncio.gather(
        check_database(),
        check_redis(),
        check_qdrant(),
        check_storage(),
        return_exceptions=True
    )
    db_result = results[0] if not isinstance(results[0], Exception) else {"status": "unhealthy", "error": str(results[0])}
    redis_result = results[1] if not isinstance(results[1], Exception) else {"status": "unhealthy", "error": str(results[1])}
    qdrant_result = results[2] if not isinstance(results[2], Exception) else {"status": "unhealthy", "error": str(results[2])}
    storage_result = results[3] if not isinstance(results[3], Exception) else {"status": "unhealthy", "error": str(results[3])}

    components = [
        {"name": "PostgreSQL", "service": "database", "status": db_result.get("status", "unknown"), "latency_ms": db_result.get("latency_ms", 0), "details": db_result},
        {"name": "Redis", "service": "cache", "status": redis_result.get("status", "unknown"), "latency_ms": redis_result.get("latency_ms", 0), "details": redis_result},
        {"name": "Qdrant", "service": "vector_store", "status": qdrant_result.get("status", "unknown"), "latency_ms": qdrant_result.get("latency_ms", 0), "details": qdrant_result},
        {"name": "Storage", "service": "storage", "status": storage_result.get("status", "unknown"), "latency_ms": storage_result.get("latency_ms", 0), "details": storage_result},
    ]

    overall = "healthy" if all(c["status"] == "healthy" for c in components) else "degraded"
    return {
        "status": overall,
        "components": components,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/dependencies", response_model=Dict[str, Any])
async def health_dependencies() -> Dict[str, Any]:
    """
    Check specific dependency health.
    Useful for targeted diagnostics.
    """
    return await health_deep()
