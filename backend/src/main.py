"""
CareerOS AI Enterprise Backend.
FastAPI application with production-grade configuration.
"""
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.core.config import settings
from src.api.v1.endpoints.resumes import router as resumes_router
from src.api.v1.endpoints.orchestration import router as orchestration_router
from src.api.v1.endpoints.realtime import router as realtime_router
from src.api.v1.endpoints.interview import router as interview_router
from src.api.v1.endpoints.auth import router as auth_router
from src.api.v1.endpoints.knowledge import router as knowledge_router
from src.api.v1.endpoints.packages import router as packages_router
from src.api.v1.endpoints.readiness import router as readiness_router
from src.api.v1.endpoints.agents import router as agents_router
from src.api.v1.endpoints.mcp import router as mcp_router
from src.api.v1.endpoints.observability import router as observability_router
from src.api.v1.endpoints.jobs import router as jobs_router
from src.api.v1.endpoints.approvals import router as approvals_router
from src.api.v1.endpoints.roadmaps import router as roadmaps_router
from src.api.v1.endpoints.evaluation import router as evaluation_router
from src.api.v1.endpoints.preferences import router as preferences_router
from src.api.v1.endpoints.troubleshoot import router as troubleshoot_router
from src.api.v1.endpoints.rerank import router as rerank_router
from src.api.v1.endpoints.opportunities_api import router as opportunities_router
from src.api.v1.endpoints.opportunity_alert import router as opportunity_alert_router
from src.api.v1.endpoints.events import router as events_router
from src.api.v1.endpoints.skill_graph import router as skill_graph_router
from src.api.v1.endpoints.skill_gaps import router as skill_gaps_router
from src.api.v1.endpoints.demo_rag import router as demo_rag_router
from src.api.v1.endpoints.learning import router as learning_router
from src.api.v1.endpoints.outcome_intelligence import router as outcome_intelligence_router
from src.api.v1.endpoints.autonomous_engagement import router as autonomous_engagement_router
from src.api.v1.endpoints.phase6 import router as phase6_router
from src.api.health import router as health_router
from src.observability.middleware import ObservabilityMiddleware
from src.observability.langsmith import langsmith_client
from src.observability.logger import structured_logger
from src.core.exceptions.handlers import register_exception_handlers
from src.workers import close_arq_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup initialization and graceful shutdown.
    """
    startup_start = time.time()
    structured_logger.info(f"Starting {settings.PROJECT_NAME}...", extra={
        "service": "core",
        "operation": "startup",
        "environment": settings.ENVIRONMENT,
        "version": "2.0.0",
    })
    
    # Initialize LangSmith
    if langsmith_client:
        structured_logger.info("LangSmith tracing initialized", extra={
            "service": "observability",
            "operation": "langsmith_init",
        })
    else:
        structured_logger.info("LangSmith tracing disabled", extra={
            "service": "observability",
            "operation": "langsmith_disabled",
        })
    
    # Validate critical configuration
    _validate_configuration()
    await _validate_runtime_dependencies()
    
    # Verify checkpoint persistence
    try:
        from src.services.checkpoint import get_checkpoint_saver
        saver = get_checkpoint_saver()
        saver_type = type(saver).__name__
        structured_logger.info(f"Checkpoint saver initialized: {saver_type}", extra={
            "service": "langgraph",
            "operation": "checkpoint_init",
            "saver_type": saver_type,
            "is_persistent": "Memory" not in saver_type,
        })
    except Exception as e:
        structured_logger.warning(f"Checkpoint saver init skipped: {e}", extra={
            "service": "langgraph",
            "operation": "checkpoint_init",
            "error": str(e),
        })

    # Initialize Qdrant collections
    try:
        from src.services.vector_store.qdrant_service import get_qdrant_service
        qdrant_svc = get_qdrant_service()
        await qdrant_svc.init_collections()
        structured_logger.info("Qdrant collections initialized", extra={
            "service": "vector_store",
            "operation": "init_collections",
        })
    except Exception as e:
        if settings.ENVIRONMENT == "production":
            structured_logger.error(f"Qdrant init failed in production: {e}", extra={
                "service": "vector_store",
                "operation": "init_collections",
                "error": str(e),
            })
            raise
        structured_logger.warning(f"Qdrant init skipped: {e}", extra={
            "service": "vector_store",
            "operation": "init_collections",
            "error": str(e),
        })
    
    startup_duration = time.time() - startup_start
    structured_logger.info("Startup complete", extra={
        "service": "core",
        "operation": "startup_complete",
        "duration_ms": startup_duration * 1000,
    })
    
    yield
    
    # Shutdown
    structured_logger.info("Shutting down...", extra={
        "service": "core",
        "operation": "shutdown",
    })
    
    # Close ARQ pool
    try:
        await close_arq_pool()
        structured_logger.info("ARQ pool closed", extra={
            "service": "core",
            "operation": "shutdown",
        })
    except Exception as e:
        structured_logger.error("Error closing ARQ pool", extra={
            "service": "core",
            "operation": "shutdown",
            "error": str(e),
        })
    
    # Close MCP connections if available
    try:
        from src.services.mcp_client import mcp_pool
        await mcp_pool.close_all()
        structured_logger.info("MCP connections closed", extra={
            "service": "mcp",
            "operation": "shutdown",
        })
    except ImportError:
        pass  # MCP client not available
    except Exception as e:
        structured_logger.error("Error closing MCP connections", extra={
            "service": "mcp",
            "operation": "shutdown",
            "error": str(e),
        })
    
    structured_logger.info("Shutdown complete", extra={
        "service": "core",
        "operation": "shutdown_complete",
    })


def _validate_configuration():
    """Validate critical configuration on startup."""
    issues = []
    production_issues = []
    is_production = settings.ENVIRONMENT == "production"
    
    # Check auth configuration
    if settings.SECRET_KEY == "dev-secret-change-in-production-via-env":
        issues.append("Using default SECRET_KEY - change in production!")
        production_issues.append("SECRET_KEY must be set to a non-default value")
    if is_production and len(settings.SECRET_KEY or "") < 32:
        production_issues.append("SECRET_KEY must be at least 32 characters in production")
    if is_production:
        cors_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
        if "*" in cors_origins:
            production_issues.append("Wildcard CORS is not allowed in production")
        if any("localhost" in origin or "127.0.0.1" in origin for origin in cors_origins):
            production_issues.append("Localhost CORS origins are not allowed in production")
        if "localhost" in settings.DATABASE_URL or "127.0.0.1" in settings.DATABASE_URL:
            production_issues.append("DATABASE_URL must not point to localhost in production")
        if "localhost" in settings.REDIS_URL or "127.0.0.1" in settings.REDIS_URL:
            production_issues.append("REDIS_URL must not point to localhost in production")
        if "localhost" in settings.QDRANT_URL or "127.0.0.1" in settings.QDRANT_URL:
            production_issues.append("QDRANT_URL must not point to localhost in production")
    
    # Check storage configuration
    if settings.STORAGE_TYPE == "s3":
        if not settings.S3_BUCKET_NAME:
            issues.append("STORAGE_TYPE=s3 but S3_BUCKET_NAME not set")
            production_issues.append("S3_BUCKET_NAME is required when STORAGE_TYPE=s3")
        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            issues.append("S3 storage configured but AWS credentials not set")
            production_issues.append("AWS credentials are required when STORAGE_TYPE=s3")
    
    # Check AI configuration — Gemini 2.5 Flash is the primary LLM, DeepSeek is emergency fallback
    if not settings.GEMINI_API_KEY:
        issues.append(
            "GEMINI_API_KEY is not set — Gemini LLM features will fail"
        )
    
    if issues:
        for issue in issues:
            structured_logger.warning(issue, extra={
                "service": "core",
                "operation": "config_validation",
            })
    if is_production and production_issues:
        for issue in production_issues:
            structured_logger.error(issue, extra={
                "service": "core",
                "operation": "production_config_validation",
            })
        raise RuntimeError("Invalid production configuration: " + "; ".join(production_issues))
    
    return len(issues) == 0


async def _validate_runtime_dependencies():
    """Fail fast on critical runtime dependencies in production."""
    if settings.ENVIRONMENT != "production":
        return

    from sqlalchemy import text
    from src.db.redis import redis_client
    from src.db.session import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        structured_logger.error("Database health check failed during production startup", extra={
            "service": "database",
            "operation": "startup_health_check",
            "error": str(exc),
        })
        raise

    try:
        await redis_client.ping()
    except Exception as exc:
        structured_logger.error("Redis health check failed during production startup", extra={
            "service": "redis",
            "operation": "startup_health_check",
            "error": str(exc),
        })
        raise


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="2.0.0",
    description="CareerOS AI Enterprise API - Resume Infrastructure",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add observability middleware
app.add_middleware(ObservabilityMiddleware)

# Security headers middleware (pure ASGI to avoid Starlette BaseHTTPMiddleware TaskGroup crash)
from starlette.types import ASGIApp, Scope, Receive, Send
class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                # ASGI headers are a list because some headers, especially
                # Set-Cookie, may legally occur more than once. Converting this
                # list to a dict would silently discard all but one cookie.
                headers = list(message.get("headers", []))

                security_headers = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"x-xss-protection": b"1; mode=block",
                    b"strict-transport-security": b"max-age=31536000; includeSubDomains",
                    b"content-security-policy": b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'",
                    b"referrer-policy": b"strict-origin-when-cross-origin",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
                }

                security_header_names = set(security_headers)

                # Replace only singleton security headers while preserving
                # duplicate headers such as Set-Cookie, Vary, and Link.
                headers = [
                    (name, value)
                    for name, value in headers
                    if name.lower() not in security_header_names
                ]
                headers.extend(security_headers.items())

                message["headers"] = headers
            await send(message)
        await self.app(scope, receive, send_with_headers)

app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register structured exception handlers (must come after all routers)
register_exception_handlers(app)

# Register all API routers
app.include_router(resumes_router, prefix="/api/v1/resumes")
app.include_router(orchestration_router, prefix="/api/v1")
app.include_router(realtime_router, prefix="/api/v1")
app.include_router(interview_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(packages_router, prefix="/api/v1")
app.include_router(readiness_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(mcp_router, prefix="/api/v1")
app.include_router(observability_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(roadmaps_router, prefix="/api/v1")
app.include_router(evaluation_router, prefix="/api/v1")
app.include_router(preferences_router, prefix="/api/v1")
app.include_router(troubleshoot_router, prefix="/api/v1")
app.include_router(rerank_router, prefix="/api/v1")
app.include_router(opportunities_router, prefix="/api/v1")
app.include_router(opportunity_alert_router, prefix="/api")
app.include_router(events_router, prefix="/api/v1")
app.include_router(skill_graph_router, prefix="/api/v1")
app.include_router(skill_gaps_router, prefix="/api/v1")
app.include_router(demo_rag_router, prefix="/api/v1")
app.include_router(learning_router, prefix="/api/v1")
app.include_router(outcome_intelligence_router, prefix="/api")
app.include_router(autonomous_engagement_router, prefix="/api")
app.include_router(phase6_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - redirects to API info."""
    return {
        "service": settings.PROJECT_NAME,
        "version": "2.0.0",
        "environment": settings.ENVIRONMENT,
        "documentation": "/api/docs",
        "health": "/api/health/live"
    }
