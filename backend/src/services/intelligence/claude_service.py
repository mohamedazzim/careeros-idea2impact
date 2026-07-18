"""
Production-grade Claude Sonnet 4.6 orchestration service.

Phase 4D: Domain-aware resource governance — every Claude call is gated by
domain-specific semaphores, token budgets, retry strategies, and observability.

Capabilities:
- Async Claude API with langchain-anthropic
- Domain-governed concurrency (evaluation/strategy/interview/general)
- Domain-specific token pressure enforcement with budget-aware throttling
- Domain validation — rejects calls without explicit domain
- Post-hoc structural enforcement (roadmap caps, recommendation caps)
- Retry-safe with exponential backoff within semaphore boundary
- Circuit breaker protection
- Timeout handling
- Structured output (with_structured_output via pydantic)
- Streaming preparation
- Token accounting + cost estimation
- Rate-limit handling
- Degraded execution strategy
- Per-domain observability: pressure, tokens, retry amp, latency, semaphore wait

Stateless, async-safe, retry-safe, observable. Worker-safe.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Type

from langsmith import traceable

from src.core.config import settings
from src.services.intelligence.domain_types import (
    ClaudeDomain,
    resolve_domain,
    is_valid_domain,
    DOMAIN_SEMAPHORE_DEFAULTS,
    DOMAIN_TOKEN_BUDGETS,
    DOMAIN_RETRY_DEFAULTS,
)
from src.observability.metrics import (
    CLAUDE_CALLS,
    CLAUDE_LATENCY,
    CLAUDE_COST_ESTIMATE,
    CLAUDE_CIRCUIT_OPEN,
    CLAUDE_RATE_LIMIT,
    LLM_TOKEN_USAGE,
    LLM_LATENCY_HIST,
    LLM_FAILURES,
    DOMAIN_CALL_TOTAL,
    DOMAIN_LATENCY,
    DOMAIN_TOKEN_USAGE,
    DOMAIN_SEMAPHORE_WAIT,
    DOMAIN_SEMAPHORE_PRESSURE,
    DOMAIN_TOKEN_PRESSURE,
    DOMAIN_THROTTLE_EVENTS,
    DOMAIN_RETRY_AMPLIFICATION,
    DOMAIN_RATE_LIMIT_HITS,
    DOMAIN_TIMEOUTS,
)

logger = logging.getLogger(__name__)

# Claude Sonnet 4 pricing per 1M tokens (approximate)
CLAUDE_INPUT_COST_PER_MT = 3.00
CLAUDE_OUTPUT_COST_PER_MT = 15.00


# ══════════════════════════════════════════════════════════════════════
# Circuit Breaker
# ══════════════════════════════════════════════════════════════════════

class ClaudeCircuitBreaker:
    def __init__(self, threshold: int = 3, recovery: float = 90.0):
        self.threshold = threshold
        self.recovery = recovery
        self.failure_count = 0
        self.last_failure = 0.0
        self.open = False

    def acquire(self) -> bool:
        if not self.open:
            return True
        if time.monotonic() - self.last_failure >= self.recovery:
            self.open = False
            self.failure_count = 0
            return True
        return False

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure = time.monotonic()
        if self.failure_count >= self.threshold and not self.open:
            self.open = True
            CLAUDE_CIRCUIT_OPEN.inc()
            logger.warning("Claude circuit breaker opened")

    def record_success(self) -> None:
        self.failure_count = 0


# ══════════════════════════════════════════════════════════════════════
# Domain Token Pressure Tracker
# ══════════════════════════════════════════════════════════════════════

class DomainTokenTracker:
    """Per-domain cumulative token usage tracker with budget enforcement."""

    def __init__(self, budgets: Optional[Dict[ClaudeDomain, int]] = None):
        self.budgets = budgets or DOMAIN_TOKEN_BUDGETS.copy()
        self.used: Dict[ClaudeDomain, int] = {d: 0 for d in ClaudeDomain}
        self.throttled_calls: Dict[ClaudeDomain, int] = {d: 0 for d in ClaudeDomain}
        self.pressure_events: Dict[ClaudeDomain, int] = {d: 0 for d in ClaudeDomain}

    def record_tokens(self, domain: ClaudeDomain, tokens_in: int, tokens_out: int) -> None:
        total = tokens_in + tokens_out
        self.used[domain] += total

    def is_throttled(self, domain: ClaudeDomain) -> bool:
        budget = self.budgets.get(domain, 100_000)
        return self.used[domain] >= budget

    def throttle_pct(self, domain: ClaudeDomain) -> float:
        budget = self.budgets.get(domain, 100_000)
        if budget <= 0:
            return 1.0
        return min(1.0, self.used[domain] / budget)

    def throttle_verbosity(self, domain: ClaudeDomain, base_max_tokens: int) -> int:
        """Reduce max_tokens when budget is under pressure."""
        pct = self.throttle_pct(domain)
        if pct < 0.5:
            return base_max_tokens
        if pct < 0.75:
            return max(256, base_max_tokens // 2)
        if pct < 0.9:
            return max(128, base_max_tokens // 4)
        return max(64, base_max_tokens // 8)

    def record_throttled(self, domain: ClaudeDomain) -> None:
        self.throttled_calls[domain] += 1

    def record_pressure(self, domain: ClaudeDomain) -> None:
        self.pressure_events[domain] += 1

    def snapshot(self) -> Dict[str, Any]:
        return {
            d.value: {
                "used": self.used[d],
                "budget": self.budgets.get(d, 100_000),
                "throttled": self.throttled_calls[d],
                "pressure": self.pressure_events[d],
                "pct": round(self.throttle_pct(d), 3),
            }
            for d in ClaudeDomain
        }


# ══════════════════════════════════════════════════════════════════════
# Post-Hoc Structural Enforcement
# ══════════════════════════════════════════════════════════════════════

POST_HOC_CAPS: Dict[str, Dict[str, int]] = {
    "roadmap_generation": {"milestones": 15, "phases": 4},
    "recommendation": {"recommendations": 8, "categories": 6},
    "opportunity_prioritization": {"opportunities": 10},
    "interview_questions": {"questions": 12, "follow_ups": 3},
}


def enforce_post_hoc_caps(
    prompt_id: str, data: Dict[str, Any]
) -> Dict[str, Any]:
    """Truncate structured output to hard caps after Claude returns."""
    caps = POST_HOC_CAPS.get(prompt_id)
    if not caps:
        return data

    result = dict(data)
    for field, max_count in caps.items():
        if field in result and isinstance(result[field], list):
            original = len(result[field])
            if original > max_count:
                result[field] = result[field][:max_count]
                result.setdefault("_truncated", {})[field] = {
                    "original_count": original,
                    "cap": max_count,
                }
                from src.observability.metrics import DOMAIN_POSTHOC_TRUNCATIONS
                DOMAIN_POSTHOC_TRUNCATIONS.labels(
                    prompt_id=prompt_id, field=field
                ).inc()

    sorted_fields = ["recommendations", "opportunities", "milestones", "questions"]
    for sf in sorted_fields:
        if sf in result and isinstance(result[sf], list):
            try:
                result[sf] = sorted(result[sf], key=lambda x: x.get("priority", x.get("score", 0)), reverse=True)
            except Exception:
                pass

    return result


# ══════════════════════════════════════════════════════════════════════
# Claude Service — Domain-Governed
# ══════════════════════════════════════════════════════════════════════

class ClaudeService:
    """Production Claude Sonnet 4.6 with domain-governed resource isolation.

    Each domain (evaluation, strategy, interview, general) operates under
    its own concurrency semaphore, token budget, retry strategy, and
    observability namespace.
    """

    def __init__(self):
        self.model_name = settings.CLAUDE_MODEL
        self.temperature = settings.CLAUDE_TEMPERATURE
        self.max_tokens = settings.CLAUDE_MAX_TOKENS
        self.timeout = settings.CLAUDE_TIMEOUT
        self.max_retries = settings.CLAUDE_MAX_RETRIES
        self.retry_delay = settings.CLAUDE_RETRY_BASE_DELAY
        self._circuit = ClaudeCircuitBreaker(
            threshold=settings.CLAUDE_CIRCUIT_THRESHOLD,
            recovery=settings.CLAUDE_CIRCUIT_RECOVERY,
        ) if settings.CLAUDE_CIRCUIT_BREAKER_ENABLED else None

        # Per-domain concurrency semaphores
        self._semaphores: Dict[ClaudeDomain, asyncio.Semaphore] = {
            d: asyncio.Semaphore(n)
            for d, n in DOMAIN_SEMAPHORE_DEFAULTS.items()
        }

        # Per-domain token pressure tracker
        self._token_tracker = DomainTokenTracker()

        # Runtime domain call counters
        self._calls_by_domain: Dict[ClaudeDomain, int] = {
            d: 0 for d in ClaudeDomain
        }

    # ── Semantic Methods ──────────────────────────────────────────

    async def _acquire_and_wait(
        self, domain: ClaudeDomain
    ) -> float:
        """Acquire domain semaphore and return wait time in seconds."""
        sem = self._semaphores[domain]
        wait_start = time.monotonic()
        await sem.acquire()
        return (time.monotonic() - wait_start) * 1000

    def _release_semaphore(self, domain: ClaudeDomain) -> None:
        self._semaphores[domain].release()

    def _get_max_retries(self, domain: ClaudeDomain) -> int:
        return DOMAIN_RETRY_DEFAULTS.get(domain, 2)

    # ── LLM Builder ───────────────────────────────────────────────

    def _build_llm(self, output_schema: Type = None, reduced_max_tokens: Optional[int] = None):
        max_tok = reduced_max_tokens if reduced_max_tokens is not None else self.max_tokens
        from src.services.llm.factory import get_llm_provider
        provider = get_llm_provider()
        return {
            "provider": provider,
            "output_schema": output_schema,
            "max_tokens": max(64, max_tok),
        }

    # ── Core Reason (Domain-Governed) ─────────────────────────────

    @traceable(name="claude_reason")
    async def reason(
        self,
        system_prompt: str,
        human_message: str,
        output_schema: Type = None,
        max_retries: Optional[int] = None,
        domain: Optional[str] = None,
        category: Optional[str] = None,
        cache_key_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Core Claude reasoning with domain-governed resource isolation.

        Args:
            domain: Explicit domain string (evaluation/strategy/interview/general).
                    If None, resolved from category.
            category: Reasoning pipeline category. Used to resolve domain when
                      domain is not explicitly passed.

        Returns:
            Dict with 'result', 'tokens', 'cost', 'latency_ms', 'domain'.

        Raises:
            ValueError: If domain cannot be resolved or is invalid.
            RuntimeError: If circuit breaker is open.
        """
        # Domain resolution and validation
        resolved = self._resolve_and_validate_domain(domain, category)
        retries = max_retries if max_retries is not None else self._get_max_retries(resolved)

        if self._circuit and not self._circuit.acquire():
            LLM_FAILURES.labels(
                model=self.model_name, error_type="circuit_open"
            ).inc()
            raise RuntimeError("Claude circuit breaker open")

        self._calls_by_domain[resolved] += 1

        # Token pressure: reduce max_tokens if budget is under pressure
        effective_max = self.max_tokens
        if self._token_tracker.is_throttled(resolved):
            effective_max = self._token_tracker.throttle_verbosity(
                resolved, self.max_tokens
            )
            self._token_tracker.record_throttled(resolved)
            DOMAIN_THROTTLE_EVENTS.labels(domain=resolved.value).inc()
            logger.info(
                f"Claude domain '{resolved.value}' token-throttled: "
                f"max_tokens {self.max_tokens} → {effective_max}, "
                f"budget {self._token_tracker.throttle_pct(resolved):.1%}"
            )

        start = time.monotonic()
        last_exc = None

        # Domain semaphore acquisition with wait-time tracking
        wait_ms = await self._acquire_and_wait(resolved)
        DOMAIN_SEMAPHORE_WAIT.labels(domain=resolved.value).observe(wait_ms / 1000)
        if wait_ms > 500:
            self._token_tracker.record_pressure(resolved)
            DOMAIN_SEMAPHORE_PRESSURE.labels(domain=resolved.value).observe(wait_ms / 1000)
            logger.info(
                f"Claude domain '{resolved.value}' semaphore wait: {wait_ms:.0f}ms"
            )

        try:
            for attempt in range(retries + 1):
                try:
                    llm = self._build_llm(output_schema, reduced_max_tokens=effective_max)

                    # ── Provider adapter dispatch ──
                    provider = llm["provider"]
                    schema = llm.get("output_schema")
                    mt = llm.get("max_tokens", effective_max)
                    if schema is not None:
                        result = await provider.structured_generate(
                            system_prompt=system_prompt,
                            user_message=human_message,
                            output_schema=schema,
                            max_tokens=mt,
                            temperature=self.temperature,
                            cache_key_hint=cache_key_hint or f"{resolved.value}:{category or 'general'}:{getattr(schema, '__name__', 'structured')}",
                        )
                    else:
                        result = await provider.generate(
                            system_prompt=system_prompt,
                            user_message=human_message,
                            max_tokens=mt,
                            temperature=self.temperature,
                            cache_key_hint=cache_key_hint or f"{resolved.value}:{category or 'general'}:text",
                        )
                    elapsed = result.get("latency_ms", 0)
                    tokens_in = result.get("tokens", {}).get("input", 0)
                    tokens_out = result.get("tokens", {}).get("output", 0)
                    cost = result.get("cost", 0.0)
                    result_data = result.get("result", "")

                    self._token_tracker.record_tokens(
                        resolved, tokens_in, tokens_out
                    )

                    # Emit per-domain observability
                    CLAUDE_CALLS.labels(
                        model=self.model_name, status="success"
                    ).inc()
                    CLAUDE_LATENCY.labels(
                        model=self.model_name, operation=resolved.value
                    ).observe(elapsed / 1000 if isinstance(elapsed, (int, float)) else 0)
                    CLAUDE_COST_ESTIMATE.observe(cost)
                    LLM_TOKEN_USAGE.labels(
                        model=self.model_name, token_type="input"
                    ).inc(tokens_in)
                    LLM_TOKEN_USAGE.labels(
                        model=self.model_name, token_type="output"
                    ).inc(tokens_out)
                    if isinstance(elapsed, (int, float)):
                        LLM_LATENCY_HIST.labels(
                            model=self.model_name, operation=resolved.value
                        ).observe(elapsed / 1000)

                    # Domain-level observability
                    DOMAIN_CALL_TOTAL.labels(
                        domain=resolved.value, status="success"
                    ).inc()
                    if isinstance(elapsed, (int, float)):
                        DOMAIN_LATENCY.labels(domain=resolved.value).observe(elapsed / 1000)
                    DOMAIN_TOKEN_USAGE.labels(
                        domain=resolved.value, token_type="input"
                    ).inc(tokens_in)
                    DOMAIN_TOKEN_USAGE.labels(
                        domain=resolved.value, token_type="output"
                    ).inc(tokens_out)
                    DOMAIN_TOKEN_PRESSURE.labels(
                        domain=resolved.value
                    ).observe(self._token_tracker.throttle_pct(resolved))

                    if self._circuit:
                        self._circuit.record_success()

                    return {
                        "result": result_data,
                        "tokens": {"input": tokens_in, "output": tokens_out},
                        "cost": round(cost, 6) if isinstance(cost, (int, float)) else cost,
                        "latency_ms": round(elapsed, 2) if isinstance(elapsed, (int, float)) else elapsed,
                        "model": self.model_name,
                        "domain": resolved.value,
                        "semaphore_wait_ms": round(wait_ms, 2),
                        "throttled": effective_max < self.max_tokens,
                    }

                except asyncio.TimeoutError:
                    last_exc = "timeout"
                    LLM_FAILURES.labels(
                        model=self.model_name, error_type="timeout"
                    ).inc()
                    DOMAIN_TIMEOUTS.labels(domain=resolved.value).inc()
                    DOMAIN_RETRY_AMPLIFICATION.labels(
                        domain=resolved.value, attempt=str(attempt + 1)
                    ).inc()
                    logger.warning(
                        f"Claude [{resolved.value}] timeout "
                        f"(attempt {attempt + 1}/{retries + 1})"
                    )

                except Exception as e:
                    last_exc = str(e)[:200]
                    error_msg = str(e).lower()
                    if "429" in error_msg or "rate" in error_msg:
                        CLAUDE_RATE_LIMIT.inc()
                        DOMAIN_RATE_LIMIT_HITS.labels(domain=resolved.value).inc()
                        DOMAIN_RETRY_AMPLIFICATION.labels(
                            domain=resolved.value, attempt=str(attempt + 1)
                        ).inc()
                        cooldown = 5.0 * (2 ** attempt)
                        logger.warning(
                            f"Claude [{resolved.value}] rate limited, "
                            f"waiting {cooldown}s"
                        )
                        await asyncio.sleep(cooldown)
                    else:
                        LLM_FAILURES.labels(
                            model=self.model_name, error_type="api_error"
                        ).inc()
                        logger.error(
                            f"Claude [{resolved.value}] error "
                            f"(attempt {attempt + 1}): {e}"
                        )

                if attempt < retries:
                    delay = self.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

            if self._circuit:
                self._circuit.record_failure()

            CLAUDE_CALLS.labels(
                model=self.model_name, status="error"
            ).inc()
            DOMAIN_CALL_TOTAL.labels(
                domain=resolved.value, status="error"
            ).inc()
            raise RuntimeError(
                f"Claude [{resolved.value}] failed after "
                f"{retries + 1} attempts: {last_exc}"
            )

        finally:
            self._release_semaphore(resolved)

    def _resolve_and_validate_domain(
        self, domain: Optional[str] = None, category: Optional[str] = None
    ) -> ClaudeDomain:
        """Resolve domain from explicit value or category, validate result."""
        if domain is not None:
            if not isinstance(domain, str) or not is_valid_domain(domain):
                raise ValueError(
                    f"Invalid Claude domain '{domain}'. "
                    f"Must be one of: {[d.value for d in ClaudeDomain]}"
                )
            return ClaudeDomain(domain)

        if category is not None:
            resolved = resolve_domain(category)
            logger.debug(
                f"Claude domain resolved: category='{category}' → {resolved.value}"
            )
            return resolved

        raise ValueError(
            "ClaudeService.reason() requires 'domain' or 'category'. "
            "No domain-less calls are permitted."
        )

    # ── Domain-Aware Text Reason ─────────────────────────────────

    @traceable(name="claude_reason_text")
    async def reason_text(
        self,
        system_prompt: str,
        human_message: str,
        max_retries: Optional[int] = None,
        domain: Optional[str] = None,
        category: Optional[str] = None,
        cache_key_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reason without structured output — returns raw text."""
        return await self.reason(
            system_prompt=system_prompt,
            human_message=human_message,
            output_schema=None,
            max_retries=max_retries,
            domain=domain,
            category=category,
            cache_key_hint=cache_key_hint,
        )

    # ── Token Budget Queries ─────────────────────────────────────

    def get_token_snapshot(self) -> Dict[str, Any]:
        return self._token_tracker.snapshot()

    def domain_pressure(self, domain: str) -> float:
        d = ClaudeDomain(domain) if is_valid_domain(domain) else ClaudeDomain.GENERAL
        return self._token_tracker.throttle_pct(d)

    def domain_call_count(self, domain: str) -> int:
        d = ClaudeDomain(domain) if is_valid_domain(domain) else ClaudeDomain.GENERAL
        return self._calls_by_domain.get(d, 0)

    # ── Utilities ────────────────────────────────────────────────

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text.split()) * 1.3)


_claude_service: Optional[ClaudeService] = None


def get_claude_service() -> ClaudeService:
    global _claude_service
    if _claude_service is None:
        _claude_service = ClaudeService()
    return _claude_service


def reset_claude_service() -> None:
    global _claude_service
    _claude_service = None


def __getattr__(name: str):
    if name == "claude_service":
        return get_claude_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
