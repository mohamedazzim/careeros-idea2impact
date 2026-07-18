import time
import uuid
from starlette.types import ASGIApp, Scope, Receive, Send
from src.observability.context import request_id_ctx
from src.observability.logger import structured_logger
from src.observability.metrics import API_REQUEST_COUNT, API_LATENCY
from src.observability.tracing import tracer
from opentelemetry import trace


class ObservabilityMiddleware:
    """Pure ASGI observability middleware — avoids Starlette BaseHTTPMiddleware TaskGroup crash."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        req_id = str(uuid.uuid4())
        request_id_ctx.set(req_id)
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        status_code = 500
        start_time = time.time()

        with tracer.start_as_current_span(f"{method} {path}") as span:
            span.set_attribute("http.method", method)
            span.set_attribute("http.route", path)
            span.set_attribute("request_id", req_id)

            structured_logger.info("API Request Started", extra={
                "service": "api",
                "operation": "request_start",
                "path": path,
                "method": method,
            })

            async def send_wrapper(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message.get("status", 500)
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as e:
                status_code = 500
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                structured_logger.error("API Request Failed", extra={
                    "service": "api",
                    "operation": "request_fail",
                    "error": str(e),
                })
                raise
            finally:
                duration = time.time() - start_time
                API_REQUEST_COUNT.labels(method=method, endpoint=path, status=str(status_code)).inc()
                API_LATENCY.labels(method=method, endpoint=path).observe(duration)
                span.set_attribute("http.status_code", status_code)
                structured_logger.info("API Request Completed", extra={
                    "service": "api",
                    "operation": "request_end",
                    "duration_ms": duration * 1000,
                    "status": status_code,
                })


async def observability_middleware(request, call_next):
    """Simple test-friendly middleware callable for unit tests."""
    req_id = str(uuid.uuid4())
    request_id_ctx.set(req_id)
    method = getattr(request, "method", "UNKNOWN")
    path = getattr(request, "url", type("U", (), {"path": "/"})()).path
    start_time = time.time()

    with tracer.start_as_current_span(f"{method} {path}") as span:
        span.set_attribute("http.method", method)
        span.set_attribute("http.route", path)
        span.set_attribute("request_id", req_id)
        try:
            response = await call_next(request)
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            raise
        finally:
            duration = time.time() - start_time
            API_REQUEST_COUNT.labels(method=method, endpoint=path, status=str(getattr(response, "status_code", 200))).inc()
            API_LATENCY.labels(method=method, endpoint=path).observe(duration)
    return response
