"""
LangSmith tracing decorators.
Function instrumentation for observability.
"""
import asyncio
import functools
import inspect
import logging
import uuid
from typing import Optional, Any, Dict, Callable
from contextvars import ContextVar

from src.core.config import settings
from .breaker import get_langsmith_circuit_breaker
from .client import get_manager

logger = logging.getLogger(__name__)
SENSITIVE_FIELDS = {
    "candidate_id", "phone_number", "raw_transcript", "transcript", "api_key",
    "token", "password", "secret", "call_sid",
}

current_run_id: ContextVar[Optional[str]] = ContextVar('current_run_id', default=None)


def traceable(
    name: Optional[str] = None,
    run_type: str = "chain",
    project_name: Optional[str] = None,
    tags: Optional[list] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Callable:
    def decorator(func: Callable) -> Callable:
        run_name = name or func.__name__
        manager = get_manager()
        breaker = get_langsmith_circuit_breaker()

        def _should_trace() -> tuple[bool, bool]:
            if not manager.enabled:
                return False, False
            if breaker.cooldown_active():
                return False, False
            probe_mode = breaker.begin_probe_if_ready()
            return True, probe_mode

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            valid_params = set(inspect.signature(func).parameters.keys())
            call_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
            trace_enabled, probe_mode = _should_trace()
            if not trace_enabled:
                return await func(*args, **call_kwargs)
            client = manager.client
            inputs = _build_inputs(func, args, kwargs)
            run_id = uuid.uuid4()
            try:
                client.create_run(
                    id=run_id,
                    name=run_name, run_type=run_type, inputs=inputs,
                    project_name=project_name or settings.LANGCHAIN_PROJECT,
                    tags=tags or [], extra=metadata or {}
                )
            except Exception as exc:
                logger.warning("LangSmith create_run failed: %s", exc)
                if _is_quota_error(exc):
                    breaker.trip_quota_exceeded(source="create_run")
                run_id = None
            token = current_run_id.set(str(run_id) if run_id else None)
            try:
                result = await func(*args, **call_kwargs)
                if run_id:
                    try:
                        client.update_run(
                            run_id=run_id,
                            outputs={"result": _safe_output(result)} if result is not None else None,
                            error=None
                        )
                    except Exception:
                        pass
                return result
            except Exception as e:
                if run_id:
                    try:
                        client.update_run(run_id=run_id, error=str(e), outputs=None)
                    except Exception:
                        pass
                if _is_quota_error(e):
                    breaker.trip_quota_exceeded(source="update_run")
                raise
            finally:
                if probe_mode:
                    breaker.record_probe()
                current_run_id.reset(token)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            valid_params = set(inspect.signature(func).parameters.keys())
            call_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
            trace_enabled, probe_mode = _should_trace()
            if not trace_enabled:
                return func(*args, **call_kwargs)
            client = manager.client
            inputs = _build_inputs(func, args, kwargs)
            run_id = uuid.uuid4()
            try:
                client.create_run(
                    id=run_id,
                    name=run_name, run_type=run_type, inputs=inputs,
                    project_name=project_name or settings.LANGCHAIN_PROJECT,
                    tags=tags or [], extra=metadata or {}
                )
            except Exception as exc:
                logger.warning("LangSmith create_run failed: %s", exc)
                if _is_quota_error(exc):
                    breaker.trip_quota_exceeded(source="create_run")
                run_id = None
            token = current_run_id.set(str(run_id) if run_id else None)
            try:
                result = func(*args, **kwargs)
                if run_id:
                    try:
                        client.update_run(
                            run_id=run_id,
                            outputs={"result": _safe_output(result)} if result is not None else None,
                            error=None
                        )
                    except Exception:
                        pass
                return result
            except Exception as e:
                if run_id:
                    try:
                        client.update_run(run_id=run_id, error=str(e), outputs=None)
                    except Exception:
                        pass
                if _is_quota_error(e):
                    breaker.trip_quota_exceeded(source="update_run")
                raise
            finally:
                if probe_mode:
                    breaker.record_probe()
                current_run_id.reset(token)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "monthly unique traces usage limit exceeded",
            "failed to multipart ingest runs",
            "too many requests",
            "quota exceeded",
            "429",
        )
    )


def _build_inputs(func: Callable, args: tuple, kwargs: dict) -> Dict[str, Any]:
    sig = inspect.signature(func)
    valid_params = set(sig.parameters.keys())
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
    bound = sig.bind(*args, **filtered_kwargs)
    bound.apply_defaults()
    inputs = {}
    for name, value in bound.arguments.items():
        if name in ('self', 'cls', 'ctx', 'context'):
            continue
        if name.lower() in SENSITIVE_FIELDS or any(part in name.lower() for part in ("password", "secret", "token", "api_key")):
            inputs[name] = "[REDACTED]"
        elif isinstance(value, dict):
            inputs[name] = _redact_dict(value)
        elif isinstance(value, list):
            inputs[name] = value[:20]
        elif isinstance(value, (str, int, float, bool)):
            inputs[name] = value
        elif value is None:
            inputs[name] = None
        else:
            inputs[name] = str(value)
    return inputs


def _redact_dict(value: Dict[str, Any]) -> Dict[str, Any]:
    redacted = {}
    for key, item in value.items():
        lowered = str(key).lower()
        if lowered in SENSITIVE_FIELDS or any(part in lowered for part in ("password", "secret", "token", "api_key", "phone")):
            redacted[key] = "[REDACTED]"
        elif isinstance(item, dict):
            redacted[key] = _redact_dict(item)
        elif isinstance(item, str) and len(item) > 1000:
            redacted[key] = f"[REDACTED_LONG_TEXT:{len(item)}]"
        else:
            redacted[key] = item
    return redacted


def _safe_output(value: Any) -> Any:
    if isinstance(value, dict):
        return _redact_dict(value)
    if isinstance(value, list):
        return [_safe_output(item) for item in value[:20]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value if not isinstance(value, str) or len(value) <= 1000 else f"[REDACTED_LONG_TEXT:{len(value)}]"
    return {"type": type(value).__name__, "id": getattr(value, "id", None)}


def get_current_run_id() -> Optional[str]:
    return current_run_id.get()
