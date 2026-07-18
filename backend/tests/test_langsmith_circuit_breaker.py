from __future__ import annotations

import pytest

from src.core.config import settings
from src.observability.langsmith.breaker import get_langsmith_circuit_breaker
import src.observability.langsmith.decorators as langsmith_decorators


@pytest.fixture(autouse=True)
def _reset_breaker():
    breaker = get_langsmith_circuit_breaker()
    breaker.reset()
    yield
    breaker.reset()


class _FakeClient:
    def __init__(self, *, create_side_effect=None):
        self.create_side_effect = create_side_effect
        self.create_calls = 0
        self.update_calls = 0

    def create_run(self, **kwargs):
        self.create_calls += 1
        if self.create_side_effect:
            raise self.create_side_effect
        return None

    def update_run(self, **kwargs):
        self.update_calls += 1
        return None


class _FakeManager:
    def __init__(self, enabled: bool, client):
        self.enabled = enabled
        self.client = client


def _configure_langsmith(monkeypatch, *, enabled: bool = True, api_key: str = "", tracing_v2: bool = False):
    monkeypatch.setattr(settings, "LANGSMITH_ENABLED", enabled, raising=False)
    monkeypatch.setattr(settings, "LANGCHAIN_TRACING_V2", tracing_v2, raising=False)
    monkeypatch.setattr(settings, "LANGCHAIN_API_KEY", api_key, raising=False)


@pytest.mark.asyncio
async def test_langsmith_429_enters_cooldown(monkeypatch):
    _configure_langsmith(monkeypatch)
    breaker = get_langsmith_circuit_breaker()
    fake_client = _FakeClient(create_side_effect=RuntimeError("429 Too Many Requests"))
    monkeypatch.setattr(
        langsmith_decorators,
        "get_manager",
        lambda: _FakeManager(True, fake_client),
    )

    @langsmith_decorators.traceable(name="quota-test")
    async def sample_job(value: str) -> str:
        return f"processed:{value}"

    result = await sample_job("abc")

    snapshot = breaker.status_snapshot()
    assert result == "processed:abc"
    assert fake_client.create_calls == 1
    assert snapshot["status"] == "degraded"
    assert snapshot["cooldown_active"] is True
    assert snapshot["observed_quota_events"] >= 1


@pytest.mark.asyncio
async def test_langsmith_cooldown_skips_trace_creation(monkeypatch):
    _configure_langsmith(monkeypatch)
    breaker = get_langsmith_circuit_breaker()
    breaker.trip_quota_exceeded(source="test")
    fake_client = _FakeClient()
    monkeypatch.setattr(
        langsmith_decorators,
        "get_manager",
        lambda: _FakeManager(True, fake_client),
    )

    @langsmith_decorators.traceable(name="cooldown-test")
    async def sample_job(value: str) -> str:
        return f"processed:{value}"

    result = await sample_job("abc")

    snapshot = breaker.status_snapshot()
    assert result == "processed:abc"
    assert fake_client.create_calls == 0
    assert snapshot["status"] == "degraded"
    assert snapshot["cooldown_active"] is True


def test_langsmith_fail_open_does_not_break_worker_task(monkeypatch):
    _configure_langsmith(monkeypatch)
    fake_client = _FakeClient(create_side_effect=RuntimeError("network down"))
    monkeypatch.setattr(
        langsmith_decorators,
        "get_manager",
        lambda: _FakeManager(True, fake_client),
    )

    @langsmith_decorators.traceable(name="worker-task-test")
    def sample_job(value: str) -> str:
        return f"processed:{value}"

    result = sample_job("abc")

    assert result == "processed:abc"
    assert fake_client.create_calls == 1


def test_langsmith_enabled_false_makes_no_external_calls(monkeypatch):
    _configure_langsmith(monkeypatch, enabled=False, api_key="", tracing_v2=False)
    fake_client = _FakeClient(create_side_effect=AssertionError("external call should not happen"))
    monkeypatch.setattr(
        langsmith_decorators,
        "get_manager",
        lambda: _FakeManager(False, fake_client),
    )

    @langsmith_decorators.traceable(name="disabled-test")
    def sample_job(value: str) -> str:
        return f"processed:{value}"

    result = sample_job("abc")

    assert result == "processed:abc"
    assert fake_client.create_calls == 0


def test_langsmith_logs_quota_warning_once(monkeypatch, caplog):
    _configure_langsmith(monkeypatch)
    breaker = get_langsmith_circuit_breaker()

    with caplog.at_level("WARNING"):
        first = breaker.trip_quota_exceeded(source="test")
        second = breaker.trip_quota_exceeded(source="test")
        third = breaker.record_quota_log("monthly unique traces usage limit exceeded")

    warnings = [record for record in caplog.records if "LangSmith disabled temporarily" in record.message]
    assert first is True
    assert second is False
    assert third is True
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_langsmith_probe_after_cooldown(monkeypatch):
    _configure_langsmith(monkeypatch)
    monkeypatch.setattr(settings, "LANGSMITH_429_COOLDOWN_SECONDS", 0, raising=False)
    breaker = get_langsmith_circuit_breaker()
    breaker.trip_quota_exceeded(source="test")
    fake_client = _FakeClient()
    monkeypatch.setattr(
        langsmith_decorators,
        "get_manager",
        lambda: _FakeManager(True, fake_client),
    )

    @langsmith_decorators.traceable(name="probe-test")
    async def sample_job(value: str) -> str:
        return f"processed:{value}"

    result = await sample_job("abc")
    snapshot = breaker.status_snapshot()

    assert result == "processed:abc"
    assert fake_client.create_calls == 1
    assert snapshot["status"] == "healthy"
    assert snapshot["last_probe_at"] > 0
