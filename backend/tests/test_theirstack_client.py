import httpx
import pytest


def _make_response(status_code: int, payload=None, text: str = "") -> httpx.Response:
    request = httpx.Request("POST", "https://api.theirstack.com/v1/jobs/search")
    if payload is not None:
        return httpx.Response(status_code, request=request, json=payload)
    return httpx.Response(status_code, request=request, content=text.encode("utf-8"))


class _FakeAsyncClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


@pytest.mark.asyncio
async def test_search_jobs_requires_posted_at_filter():
    from src.integrations.theirstack.client import TheirStackClient

    client = TheirStackClient("test-key")
    result = await client.search_jobs({"limit": 1, "page": 0}, use_cache=False)

    assert result.success is False
    assert "posted_at_gte or posted_at_max_age_days" in (result.error or "")


@pytest.mark.parametrize("raw_limit,expected", [
    (None, 5),
    (1, 1),
    (5, 5),
    (6, 5),
    (500, 5),
    (0, 1),
    (-3, 1),
    ("invalid", 5),
])
@pytest.mark.asyncio
async def test_search_jobs_clamps_limit_before_provider_call(monkeypatch, raw_limit, expected):
    from src.integrations.theirstack.client import TheirStackClient

    fake_client = _FakeAsyncClient([
        _make_response(200, {"data": []}),
    ])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    captured_payloads = []
    original_post = fake_client.post

    async def capturing_post(*args, **kwargs):
        captured_payloads.append(kwargs["json"])
        return await original_post(*args, **kwargs)

    fake_client.post = capturing_post
    client = TheirStackClient("test-key")
    payload = {"posted_at_gte": "2026-06-01", "page": 0}
    if raw_limit is not None:
        payload["limit"] = raw_limit
    result = await client.search_jobs(payload, use_cache=False)

    assert result.success is True
    assert captured_payloads[0]["limit"] == expected
    assert result.provider_http_call_count == 1


@pytest.mark.asyncio
async def test_try_single_slot_does_not_retry_500(monkeypatch):
    from src.integrations.theirstack.client import TheirStackClient
    from src.integrations.theirstack.credential_resolver import KeySlot

    fake_client = _FakeAsyncClient([
        _make_response(500, {"error": {"title": "server error"}}),
        _make_response(200, {"data": [{"id": "job-1", "title": "Software Engineer", "company": "ACME", "description": "Python SQL", "apply_url": "https://example.com/job/1", "posted_at": "2026-06-01T00:00:00Z"}]}),
    ])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    client = TheirStackClient("test-key")
    audit = await client._try_single_slot(
        "https://api.theirstack.com/v1/jobs/search",
        {"posted_at_gte": "2026-06-01", "limit": 1, "page": 0},
        KeySlot(slot_name="primary", key="secret"),
    )

    assert audit.success is False
    assert audit.error == "HTTP 500"
    assert fake_client.calls == 1
    assert audit.provider_http_call_count == 1


@pytest.mark.asyncio
async def test_try_single_slot_does_not_retry_422(monkeypatch):
    from src.integrations.theirstack.client import TheirStackClient
    from src.integrations.theirstack.credential_resolver import KeySlot

    fake_client = _FakeAsyncClient([
        _make_response(422, {"error": {"title": "validation failed"}}),
    ])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    client = TheirStackClient("test-key")
    audit = await client._try_single_slot(
        "https://api.theirstack.com/v1/jobs/search",
        {"posted_at_gte": "2026-06-01", "limit": 1, "page": 0},
        KeySlot(slot_name="primary", key="secret"),
    )

    assert audit.success is False
    assert audit.error and audit.error.startswith("HTTP 422")
    assert fake_client.calls == 1


@pytest.mark.asyncio
async def test_try_single_slot_marks_401_invalid_without_retry(monkeypatch):
    from src.integrations.theirstack.client import TheirStackClient
    from src.integrations.theirstack.credential_resolver import KeySlot

    fake_client = _FakeAsyncClient([
        _make_response(401, {"error": {"title": "unauthorized"}}),
    ])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    client = TheirStackClient("test-key")
    audit = await client._try_single_slot(
        "https://api.theirstack.com/v1/jobs/search",
        {"posted_at_gte": "2026-06-01", "limit": 1, "page": 0},
        KeySlot(slot_name="primary", key="secret"),
    )

    assert audit.success is False
    assert audit.is_invalid_key is True
    assert fake_client.calls == 1


@pytest.mark.asyncio
async def test_try_single_slot_marks_402_billing_required_without_retry(monkeypatch):
    from src.integrations.theirstack.client import TheirStackClient
    from src.integrations.theirstack.credential_resolver import KeySlot

    fake_client = _FakeAsyncClient([
        _make_response(402, {"error": {"title": "payment required"}}),
    ])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    client = TheirStackClient("test-key")
    audit = await client._try_single_slot(
        "https://api.theirstack.com/v1/jobs/search",
        {"posted_at_gte": "2026-06-01", "limit": 1, "page": 0},
        KeySlot(slot_name="primary", key="secret"),
    )

    assert audit.success is False
    assert audit.billing_required is True
    assert audit.provider_blocked is True
    assert "Payment Required" in (audit.error or "")
    assert fake_client.calls == 1


@pytest.mark.asyncio
async def test_search_jobs_rotates_on_402_billing_required(monkeypatch):
    from src.integrations.theirstack.client import TheirStackClient
    from src.integrations.theirstack.credential_resolver import KeySlot

    fake_client = _FakeAsyncClient([
        _make_response(402, {"error": {"title": "payment required"}}),
        _make_response(200, {"data": [{"id": "job-1"}]}),
    ])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    client = TheirStackClient("test-key")
    client._slots = [
        KeySlot(slot_name="primary", key="secret-1"),
        KeySlot(slot_name="key_2", key="secret-2"),
    ]

    result = await client.search_jobs({"posted_at_gte": "2026-06-01", "limit": 1, "page": 0}, use_cache=False)

    assert result.success is True
    assert result.billing_required is False
    assert result.provider_blocked is False
    assert result.provider_status_code == 200
    assert result.selected_key_slot == "key_2"
    assert result.rate_limited_slots == ["primary"]
    assert result.attempted_key_slots == ["primary", "key_2"]
    assert fake_client.calls == 2
    assert result.provider_http_call_count == 2
    assert result.fetched_count == 1


@pytest.mark.asyncio
async def test_search_jobs_treats_200_billing_body_as_effective_402(monkeypatch):
    from src.integrations.theirstack.client import TheirStackClient
    from src.integrations.theirstack.credential_resolver import KeySlot

    fake_client = _FakeAsyncClient([
        _make_response(200, {"error": {"title": "credits exhausted"}}),
        _make_response(200, {"error": {"title": "subscription expired"}}),
    ])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    client = TheirStackClient("test-key")
    client._slots = [
        KeySlot(slot_name="primary", key="secret-1"),
        KeySlot(slot_name="key_2", key="secret-2"),
    ]

    result = await client.search_jobs({"posted_at_gte": "2026-06-01", "limit": 1, "page": 0}, use_cache=False)

    assert result.success is False
    assert result.billing_required is True
    assert result.provider_blocked is True
    assert result.provider_status_code == 402
    assert result.rate_limited_slots == ["primary", "key_2"]
    assert result.attempted_key_slots == ["primary", "key_2"]
    assert result.provider_http_call_count == 2


@pytest.mark.asyncio
async def test_search_jobs_rotates_on_401_invalid_key(monkeypatch):
    from src.integrations.theirstack.client import TheirStackClient
    from src.integrations.theirstack.credential_resolver import KeySlot

    fake_client = _FakeAsyncClient([
        _make_response(401, {"error": {"title": "unauthorized"}}),
        _make_response(200, {"data": []}),
    ])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    client = TheirStackClient("test-key")
    client._slots = [
        KeySlot(slot_name="primary", key="secret-1"),
        KeySlot(slot_name="key_2", key="secret-2"),
    ]

    result = await client.search_jobs({"posted_at_gte": "2026-06-01", "limit": 5, "page": 0}, use_cache=False)

    assert result.success is True
    assert result.invalid_slots == ["primary"]
    assert result.selected_key_slot == "key_2"
    assert result.attempted_key_slots == ["primary", "key_2"]
    assert fake_client.calls == 2
    assert result.provider_http_call_count == 2


@pytest.mark.asyncio
async def test_search_jobs_rotates_on_429_rate_limit(monkeypatch):
    from src.integrations.theirstack.client import TheirStackClient
    from src.integrations.theirstack.credential_resolver import KeySlot

    fake_client = _FakeAsyncClient([
        _make_response(429, {"error": {"title": "rate limited"}}),
        _make_response(200, {"data": [{"id": "job-1"}]}),
    ])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    client = TheirStackClient("test-key")
    client._slots = [
        KeySlot(slot_name="primary", key="secret-1"),
        KeySlot(slot_name="key_2", key="secret-2"),
    ]
    result = await client.search_jobs({"posted_at_gte": "2026-06-01", "limit": 5, "page": 0}, use_cache=False)

    assert result.success is True
    assert result.rate_limited_slots == ["primary"]
    assert result.selected_key_slot == "key_2"
    assert result.attempted_key_slots == ["primary", "key_2"]
    assert fake_client.calls == 2
    assert result.provider_http_call_count == 2
    assert result.fetched_count == 1


@pytest.mark.asyncio
async def test_try_single_slot_timeout_does_not_retry(monkeypatch):
    from src.integrations.theirstack.client import TheirStackClient
    from src.integrations.theirstack.credential_resolver import KeySlot

    class TimeoutClient(_FakeAsyncClient):
        async def post(self, *args, **kwargs):
            self.calls += 1
            raise httpx.TimeoutException("timeout")

    fake_client = TimeoutClient([])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    client = TheirStackClient("test-key")
    audit = await client._try_single_slot(
        "https://api.theirstack.com/v1/jobs/search",
        {"posted_at_gte": "2026-06-01", "limit": 5, "page": 0},
        KeySlot(slot_name="primary", key="secret"),
    )

    assert audit.success is False
    assert fake_client.calls == 1
    assert audit.provider_http_call_count == 1


@pytest.mark.asyncio
async def test_try_single_slot_malformed_json_does_not_retry(monkeypatch):
    from src.integrations.theirstack.client import TheirStackClient
    from src.integrations.theirstack.credential_resolver import KeySlot

    fake_client = _FakeAsyncClient([
        _make_response(200, payload=None, text="not-json"),
        _make_response(200, {"data": []}),
    ])
    monkeypatch.setattr("src.integrations.theirstack.client.httpx.AsyncClient", lambda *args, **kwargs: fake_client)

    client = TheirStackClient("test-key")
    audit = await client._try_single_slot(
        "https://api.theirstack.com/v1/jobs/search",
        {"posted_at_gte": "2026-06-01", "limit": 5, "page": 0},
        KeySlot(slot_name="primary", key="secret"),
    )

    assert audit.success is False
    assert audit.error == "Invalid JSON response"
    assert fake_client.calls == 1
    assert audit.provider_http_call_count == 1
