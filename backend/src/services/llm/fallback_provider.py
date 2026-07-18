"""Fallback LLM provider — tries primary, falls back to secondary on failure.

Every request is tracked in the LLM observability store for the
/observability/llm endpoint.
"""

from __future__ import annotations

import logging
import statistics
import time
import uuid
from collections import deque
from typing import Any, Dict, List, Optional

from .provider import LLMProvider, Message

logger = logging.getLogger(__name__)

# ── Request-level observability store ────────────────────────────────
_MAX_HISTORY = 500
_request_history: deque = deque(maxlen=_MAX_HISTORY)

# Running aggregates
_stats: Dict[str, Any] = {
    "total_requests": 0,
    "total_success": 0,
    "total_fallback": 0,
    "total_errors": 0,
    "fallback_reasons": {},
    "model_usage": {},
    "provider_usage": {},
}


def get_llm_observability() -> Dict[str, Any]:
    """Return current LLM observability snapshot."""
    latencies = [r["latency_ms"] for r in _request_history if r.get("latency_ms")]
    sorted_lat = sorted(latencies) if latencies else []

    def percentile(data: List[float], p: float) -> float:
        if not data:
            return 0.0
        k = (len(data) - 1) * (p / 100)
        f = int(k)
        c = min(f + 1, len(data) - 1)
        return data[f] + (k - f) * (data[c] - data[f])

    return {
        "provider_stats": {
            "total_requests": _stats["total_requests"],
            "total_success": _stats["total_success"],
            "total_errors": _stats["total_errors"],
            "success_rate": round(
                _stats["total_success"] / max(_stats["total_requests"], 1) * 100, 2
            ),
        },
        "fallback_stats": {
            "total_fallback": _stats["total_fallback"],
            "fallback_rate": round(
                _stats["total_fallback"] / max(_stats["total_requests"], 1) * 100, 2
            ),
            "reasons": dict(_stats["fallback_reasons"]),
        },
        "model_usage": dict(_stats["model_usage"]),
        "latency_metrics": {
            "avg_ms": round(statistics.mean(latencies), 2) if latencies else 0,
            "p50_ms": round(percentile(sorted_lat, 50), 2),
            "p95_ms": round(percentile(sorted_lat, 95), 2),
            "p99_ms": round(percentile(sorted_lat, 99), 2),
            "min_ms": round(min(latencies), 2) if latencies else 0,
            "max_ms": round(max(latencies), 2) if latencies else 0,
            "sample_size": len(latencies),
        },
        "recent_requests": list(_request_history)[-20:],
    }


def _track_request(
    *,
    request_id: str,
    workflow_name: str,
    provider: str,
    model: str,
    latency_ms: float,
    tokens: Dict[str, int],
    success: bool,
    fallback_used: bool = False,
    fallback_reason: Optional[str] = None,
    cost_estimate: float = 0.0,
) -> None:
    """Record a single LLM request in the observability store."""
    _stats["total_requests"] += 1
    if success:
        _stats["total_success"] += 1
    else:
        _stats["total_errors"] += 1
    if fallback_used:
        _stats["total_fallback"] += 1
        if fallback_reason:
            _stats["fallback_reasons"][fallback_reason] = (
                _stats["fallback_reasons"].get(fallback_reason, 0) + 1
            )

    model_key = f"{provider}/{model}"
    _stats["model_usage"][model_key] = _stats["model_usage"].get(model_key, 0) + 1

    _request_history.append({
        "request_id": request_id,
        "workflow_name": workflow_name,
        "provider": provider,
        "model": model,
        "latency_ms": round(latency_ms, 2),
        "tokens": tokens,
        "cost_estimate": round(cost_estimate, 6),
        "success": success,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


class FallbackProvider(LLMProvider):
    """Wraps two providers: primary (Gemini) and fallback (DeepSeek).

    If primary fails, retries with fallback. Never returns fake content.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self._primary = primary
        self._fallback = fallback
        self._primary_failures = 0
        self._fallback_failures = 0

    @property
    def provider_name(self) -> str:
        return f"fallback({self._primary.provider_name}→{self._fallback.provider_name})"

    @property
    def model_name(self) -> str:
        return self._primary.model_name

    @property
    def active_provider(self) -> LLMProvider:
        """Currently active provider (primary unless it's in failure state)."""
        return self._fallback if self._primary_failures >= 3 else self._primary

    async def chat(
        self,
        messages: List[Message],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stream: bool = False,
        response_format: Optional[Dict[str, Any]] = None,
        cache_key_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        request_id = f"req_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        workflow_name = cache_key_hint or "unknown"
        t0 = time.monotonic()
        fallback_used = False
        fallback_reason = None
        provider = self.active_provider

        try:
            result = await provider.chat(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
                response_format=response_format,
                cache_key_hint=cache_key_hint,
            )
            if provider is self._primary:
                self._primary_failures = max(0, self._primary_failures - 1)
            else:
                self._fallback_failures = max(0, self._fallback_failures - 1)
                fallback_used = True
                fallback_reason = "primary_failover"

            latency_ms = (time.monotonic() - t0) * 1000
            tokens = result.get("tokens", {})
            _track_request(
                request_id=request_id,
                workflow_name=workflow_name,
                provider=result.get("provider", provider.provider_name),
                model=result.get("model", provider.model_name),
                latency_ms=latency_ms,
                tokens={"input": tokens.get("input", 0), "output": tokens.get("output", 0)},
                success=True,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                cost_estimate=result.get("cost", 0.0),
            )
            return result
        except Exception as primary_err:
            if provider is self._primary:
                self._primary_failures += 1
                logger.warning(
                    "Primary provider %s failed (%s), falling back to %s",
                    self._primary.provider_name, primary_err, self._fallback.provider_name,
                )
                fallback_used = True
                fallback_reason = str(primary_err)[:100]
                try:
                    t1 = time.monotonic()
                    result = await self._fallback.chat(
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        stream=stream,
                        response_format=response_format,
                        cache_key_hint=cache_key_hint,
                    )
                    latency_ms = (time.monotonic() - t0) * 1000
                    tokens = result.get("tokens", {})
                    _track_request(
                        request_id=request_id,
                        workflow_name=workflow_name,
                        provider=result.get("provider", self._fallback.provider_name),
                        model=result.get("model", self._fallback.model_name),
                        latency_ms=latency_ms,
                        tokens={"input": tokens.get("input", 0), "output": tokens.get("output", 0)},
                        success=True,
                        fallback_used=True,
                        fallback_reason=fallback_reason,
                        cost_estimate=result.get("cost", 0.0),
                    )
                    return result
                except Exception:
                    latency_ms = (time.monotonic() - t0) * 1000
                    _track_request(
                        request_id=request_id,
                        workflow_name=workflow_name,
                        provider=self._fallback.provider_name,
                        model=self._fallback.model_name,
                        latency_ms=latency_ms,
                        tokens={"input": 0, "output": 0},
                        success=False,
                        fallback_used=True,
                        fallback_reason=f"all_failed: {fallback_reason}",
                    )
                    raise

            self._fallback_failures += 1
            latency_ms = (time.monotonic() - t0) * 1000
            _track_request(
                request_id=request_id,
                workflow_name=workflow_name,
                provider=self._fallback.provider_name,
                model=self._fallback.model_name,
                latency_ms=latency_ms,
                tokens={"input": 0, "output": 0},
                success=False,
                fallback_used=True,
                fallback_reason="fallback_also_failed",
            )
            raise RuntimeError(
                f"All LLM providers failed. Primary: {primary_err}. "
                f"Fallback already failed {self._fallback_failures} times."
            ) from primary_err
