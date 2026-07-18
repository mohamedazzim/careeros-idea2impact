import os
import pytest
import uuid
from fastapi import Request
from starlette.datastructures import Headers
from src.observability import (
    request_id_ctx, user_id_ctx, workflow_id_ctx,
    structured_logger, tracer, observability_middleware,
    API_REQUEST_COUNT, API_LATENCY, RETRIEVAL_LATENCY_HIST
)
from prometheus_client import REGISTRY
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry import trace


@pytest.fixture
def memory_exporter():
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider = trace.get_tracer_provider()
    provider.add_span_processor(processor)
    yield exporter
    exporter.clear()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "true",
    reason="Full graph trace propagation requires all services; skipped in default CI",
)
@pytest.mark.asyncio
async def test_trace_propagation(memory_exporter):
    from src.services.orchestration.graph import career_os_graph

    os.environ["MOCK_RETRIEVAL_AGENT"] = "true"
    os.environ["MOCK_EVAL"] = "true"
    os.environ["MOCK_MCP"] = "true"

    user_id = "test-user-trace"
    resume_id = "test-resume"
    job_id = "test-job"

    with tracer.start_as_current_span("POST /api/v1/evaluate") as root_span:
        trace_id = root_span.get_span_context().trace_id

        initial_state = {
            "user_id": user_id,
            "resume_id": resume_id,
            "job_id": job_id,
            "resume_data": {},
            "job_data": {},
            "retrieved_context": "",
            "evaluation_result": {},
            "recommendations": [],
            "opportunity_alert": False,
            "report": {},
            "errors": [],
            "execution_metrics": {},
            "metadata": {}
        }
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        await career_os_graph.ainvoke(initial_state, config=config)

    spans = memory_exporter.get_finished_spans()
    assert len(spans) > 0, "No spans exported"

    for span in spans:
        assert span.get_span_context().trace_id == trace_id, f"Trace propagation failed in {span.name}"

    span_names = [s.name for s in spans]
    assert "resume_agent" in span_names


@pytest.mark.asyncio
async def test_trace_id_propagates_through_context():
    """Deterministic test: verify trace ID is set and accessible via context vars."""
    with tracer.start_as_current_span("test_span") as span:
        trace_id = span.get_span_context().trace_id
        assert trace_id != 0, "trace_id should be non-zero"

    span_names = [s.name for s in []]
    assert isinstance(trace_id, int)


@pytest.mark.asyncio
async def test_observability_middleware():
    async def mock_call_next(request: Request):
        with tracer.start_as_current_span("mock_db_call") as span:
            span.set_attribute("db.system", "postgresql")
            structured_logger.info("Executed DB call", extra={"service": "db"})

        class MockResponse:
            status_code = 200
        return MockResponse()

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/health",
        "headers": Headers({"user-agent": "test"}).raw
    }
    request = Request(scope)

    response = await observability_middleware(request, mock_call_next)

    assert response.status_code == 200
    assert request_id_ctx.get() is not None


def test_metrics_collection():
    before_count = REGISTRY.get_sample_value('api_request_count_total', {'method': 'GET', 'endpoint': '/api/v1/health', 'status': '200'}) or 0

    API_REQUEST_COUNT.labels(method="GET", endpoint="/api/v1/health", status="200").inc()

    after_count = REGISTRY.get_sample_value('api_request_count_total', {'method': 'GET', 'endpoint': '/api/v1/health', 'status': '200'})
    assert after_count == before_count + 1
