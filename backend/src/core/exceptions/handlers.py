"""Global exception handler for FastAPI.

Registers handlers for every domain exception so FastAPI
returns structured JSON error responses with correlation IDs.
"""
import uuid
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.exceptions import (
    CareerOSError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    ProcessingError,
    RetrievalError,
    LLMError,
    OrchestrationError,
    MCPError,
    InterviewError,
    InfrastructureError,
)
from src.observability.context import request_id_ctx
from src.observability.logger import structured_logger


def register_exception_handlers(app: FastAPI) -> None:
    """Register all structured exception handlers with the FastAPI app."""

    def _get_correlation_id(request: Request) -> str:
        """Get or generate a correlation ID for the current request."""
        corr_id = request_id_ctx.get()
        if not corr_id:
            corr_id = str(uuid.uuid4())
            request_id_ctx.set(corr_id)
        return corr_id

    def _log_error(exc: CareerOSError, request: Request) -> None:
        structured_logger.error(
            exc.message,
            extra={
                "service": exc.domain,
                "operation": "exception_handler",
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": str(request.url.path),
                "method": request.method,
                "details": exc.details,
                "correlation_id": exc.correlation_id or _get_correlation_id(request),
            },
        )

    # ── HTTPException (FastAPI/Starlette built-in) ──────────────────
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        corr_id = _get_correlation_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "message": exc.detail,
                "domain": "http",
                "status_code": exc.status_code,
                "correlation_id": corr_id,
            },
        )

    # ── CareerOS Base ────────────────────────────────────────────────
    @app.exception_handler(CareerOSError)
    async def careeros_error_handler(
        request: Request, exc: CareerOSError
    ) -> JSONResponse:
        _log_error(exc, request)
        corr_id = exc.correlation_id or _get_correlation_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content={**exc.to_dict(), "correlation_id": corr_id},
        )

    # ── Domain handlers (narrower scopes for isolated logging) ──────
    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        structured_logger.warning(
            exc.message,
            extra={
                "service": "auth",
                "operation": "auth_failure",
                "error_code": exc.error_code,
                "path": str(request.url.path),
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(
        request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        structured_logger.warning(
            exc.message,
            extra={
                "service": "auth",
                "operation": "authorization_failure",
                "error_code": exc.error_code,
                "path": str(request.url.path),
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        _log_error(exc, request)
        return JSONResponse(
            status_code=404,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        structured_logger.warning(
            exc.message,
            extra={
                "service": "validation",
                "operation": "validation_failure",
                "error_code": exc.error_code,
                "path": str(request.url.path),
                "details": exc.details,
            },
        )
        return JSONResponse(
            status_code=422,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    @app.exception_handler(ProcessingError)
    async def processing_error_handler(
        request: Request, exc: ProcessingError
    ) -> JSONResponse:
        _log_error(exc, request)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    @app.exception_handler(RetrievalError)
    async def retrieval_error_handler(
        request: Request, exc: RetrievalError
    ) -> JSONResponse:
        _log_error(exc, request)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    @app.exception_handler(LLMError)
    async def llm_error_handler(
        request: Request, exc: LLMError
    ) -> JSONResponse:
        _log_error(exc, request)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    @app.exception_handler(OrchestrationError)
    async def orchestration_error_handler(
        request: Request, exc: OrchestrationError
    ) -> JSONResponse:
        _log_error(exc, request)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    @app.exception_handler(MCPError)
    async def mcp_error_handler(
        request: Request, exc: MCPError
    ) -> JSONResponse:
        _log_error(exc, request)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    @app.exception_handler(InterviewError)
    async def interview_error_handler(
        request: Request, exc: InterviewError
    ) -> JSONResponse:
        _log_error(exc, request)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    @app.exception_handler(InfrastructureError)
    async def infra_error_handler(
        request: Request, exc: InfrastructureError
    ) -> JSONResponse:
        structured_logger.critical(
            exc.message,
            extra={
                "service": exc.domain,
                "operation": "infrastructure_failure",
                "error_code": exc.error_code,
                "path": str(request.url.path),
                "details": exc.details,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                **exc.to_dict(),
                "correlation_id": _get_correlation_id(request),
            },
        )

    # ── Catch-all for unexpected errors ──────────────────────────────
    @app.exception_handler(Exception)
    async def catchall_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        corr_id = _get_correlation_id(request)
        structured_logger.critical(
            f"Unhandled exception: {exc}",
            extra={
                "service": "core",
                "operation": "unhandled_error",
                "path": str(request.url.path),
                "method": request.method,
                "error_type": type(exc).__name__,
                "traceback": traceback.format_exc(),
                "correlation_id": corr_id,
            },
        )
        # Never leak tracebacks to the client in production
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "domain": "core",
                "status_code": 500,
                "correlation_id": corr_id,
            },
        )
