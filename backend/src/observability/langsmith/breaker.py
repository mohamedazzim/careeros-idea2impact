"""LangSmith observability circuit breaker and log suppression helpers."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, Optional

from src.core.config import settings

logger = logging.getLogger(__name__)

_QUOTA_PATTERNS = (
    re.compile(r"monthly unique traces usage limit exceeded", re.IGNORECASE),
    re.compile(r"failed to multipart ingest runs", re.IGNORECASE),
    re.compile(r"too many requests", re.IGNORECASE),
    re.compile(r"\b429\b", re.IGNORECASE),
    re.compile(r"quota exceeded", re.IGNORECASE),
)


@dataclass
class LangSmithCircuitState:
    """Mutable LangSmith breaker state kept in-process."""

    status: str = "healthy"
    reason: Optional[str] = None
    cooldown_until: float = 0.0
    last_trip_at: float = 0.0
    last_warning_cooldown_until: float = 0.0
    last_probe_at: float = 0.0
    suppressed_quota_logs: int = 0
    observed_quota_events: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class LangSmithCircuitBreaker:
    """In-memory LangSmith breaker with quota-aware cooldown."""

    def __init__(self) -> None:
        self._state = LangSmithCircuitState()
        self._lock = Lock()

    def _now(self) -> float:
        return time.monotonic()

    def enabled_by_config(self) -> bool:
        return bool(settings.LANGSMITH_ENABLED or settings.LANGCHAIN_TRACING_V2)

    def cooldown_seconds(self) -> int:
        return max(0, int(settings.LANGSMITH_429_COOLDOWN_SECONDS))

    def cooldown_active(self) -> bool:
        return self._now() < self._state.cooldown_until

    def cooldown_remaining_seconds(self) -> int:
        return max(0, int(self._state.cooldown_until - self._now()))

    def should_allow_requests(self) -> bool:
        if not self.enabled_by_config():
            return False
        return not self.cooldown_active()

    def begin_probe_if_ready(self) -> bool:
        """Mark the next post-cooldown request as a probe and re-open the gate."""
        if not self.enabled_by_config():
            return False
        if self.cooldown_active():
            return False
        with self._lock:
            if self._state.status == "degraded":
                self._state.status = "healthy"
                self._state.reason = None
                self._state.metadata = {"probe": True, "probe_at": self._now()}
        return True

    def record_probe(self) -> None:
        with self._lock:
            self._state.last_probe_at = self._now()
            if self._state.status == "degraded" and not self.cooldown_active():
                self._state.status = "healthy"
                self._state.reason = None
                self._state.metadata = {}

    def trip_quota_exceeded(self, source: str = "langsmith") -> bool:
        """Trip the breaker and emit one masked warning per cooldown window."""
        now = self._now()
        should_log = False
        with self._lock:
            self._state.observed_quota_events += 1
            active = now < self._state.cooldown_until
            if active and self._state.reason == "quota_exceeded":
                return False

            cooldown_until = now + self.cooldown_seconds()
            self._state.status = "degraded"
            self._state.reason = "quota_exceeded"
            self._state.cooldown_until = cooldown_until
            self._state.last_trip_at = now
            self._state.metadata = {"source": source, "cooldown_seconds": self.cooldown_seconds()}
            if self._state.last_warning_cooldown_until != cooldown_until:
                self._state.last_warning_cooldown_until = cooldown_until
                should_log = True

        if should_log:
            logger.warning(
                "LangSmith disabled temporarily: reason=quota_exceeded cooldown_seconds=%s",
                self.cooldown_seconds(),
            )
        return should_log

    def should_suppress_log(self, message: str) -> bool:
        if not message:
            return False
        lowered = message.lower()
        return any(pattern.search(lowered) for pattern in _QUOTA_PATTERNS)

    def record_quota_log(self, message: str) -> bool:
        if not self.should_suppress_log(message):
            return False
        self.trip_quota_exceeded(source="log")
        with self._lock:
            self._state.suppressed_quota_logs += 1
        return True

    def status_snapshot(self) -> Dict[str, Any]:
        active = self.cooldown_active()
        return {
            "enabled": self.enabled_by_config(),
            "fail_open": bool(settings.LANGSMITH_FAIL_OPEN),
            "status": "degraded" if active or self._state.status == "degraded" else "healthy",
            "reason": self._state.reason,
            "cooldown_active": active,
            "cooldown_seconds": self.cooldown_seconds(),
            "cooldown_remaining_seconds": self.cooldown_remaining_seconds(),
            "last_trip_at": self._state.last_trip_at,
            "last_probe_at": self._state.last_probe_at,
            "observed_quota_events": self._state.observed_quota_events,
            "suppressed_quota_logs": self._state.suppressed_quota_logs,
            "metadata": dict(self._state.metadata),
        }

    def reset(self) -> None:
        with self._lock:
            self._state = LangSmithCircuitState()


_breaker = LangSmithCircuitBreaker()


def get_langsmith_circuit_breaker() -> LangSmithCircuitBreaker:
    return _breaker


class _LangSmithQuotaLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if _breaker.record_quota_log(message):
            return False
        return True


_filter_installed = False
_quota_filter = _LangSmithQuotaLogFilter()


def _attach_filter(target: logging.Logger, quota_filter: logging.Filter) -> None:
    if quota_filter not in target.filters:
        target.addFilter(quota_filter)
    for handler in target.handlers:
        if quota_filter not in handler.filters:
            handler.addFilter(quota_filter)


def install_langsmith_log_filter() -> None:
    """Attach a root logger filter that suppresses repeated LangSmith quota spam."""
    global _filter_installed
    quota_filter = _quota_filter
    _attach_filter(logging.getLogger(), quota_filter)
    for name in ("langsmith", "langsmith.client", "langsmith.utils"):
        logger_obj = logging.getLogger(name)
        _attach_filter(logger_obj, quota_filter)
    root_logger = logging.getLogger()
    for logger_name, logger_obj in root_logger.manager.loggerDict.items():
        if isinstance(logger_obj, logging.Logger):
            _attach_filter(logger_obj, quota_filter)
    _filter_installed = True
