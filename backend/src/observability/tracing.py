import os
import functools
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

def setup_tracing():
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        provider = TracerProvider()
        if os.getenv("OTEL_EXPORTER") == "console":
            processor = SimpleSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

setup_tracing()
tracer = trace.get_tracer("careeros-ai")

def trace_async(name: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(name) as span:
                return await func(*args, **kwargs)
        return wrapper
    return decorator
