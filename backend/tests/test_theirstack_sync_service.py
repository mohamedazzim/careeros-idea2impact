import pytest


def _raw_job(idx: int):
    return {
        "id": f"job-{idx}",
        "job_title": f"Backend Engineer {idx}",
        "company": "Example Co",
        "location": "Bengaluru, India",
        "description": "Python FastAPI PostgreSQL Redis",
        "posted_at": "2026-06-10T00:00:00Z",
        "final_url": f"https://example.com/jobs/{idx}",
    }


class _BillingBlockedClient:
    def __init__(self):
        self.configured = True
        self.calls = 0
        self.payloads = []

    async def search_jobs(self, payload, use_cache=True):
        from src.integrations.theirstack.client import ClientSearchResult

        self.calls += 1
        self.payloads.append(payload)
        return ClientSearchResult(
            success=False,
            billing_required=True,
            provider_blocked=True,
            provider_status_code=402,
            error="HTTP 402 Payment Required",
            provider_http_call_count=1,
        )


class _FakeSearchClient:
    configured = True

    def __init__(self, data):
        self.calls = 0
        self.payloads = []
        self.data = data

    async def search_jobs(self, payload, use_cache=True):
        from src.integrations.theirstack.client import ClientSearchResult

        self.calls += 1
        self.payloads.append(payload)
        return ClientSearchResult(
            success=True,
            data={"data": list(self.data)},
            fetched_count=len(self.data),
            selected_key_slot="primary",
            provider_status_code=200,
            provider_http_call_count=1,
        )


@pytest.mark.asyncio
async def test_search_from_resume_stops_on_billing_required(monkeypatch):
    from src.integrations.theirstack.sync_service import TheirStackSyncService

    monkeypatch.setattr("src.integrations.theirstack.sync_service.settings.THEIRSTACK_ENABLE_FREE_COUNT_PREVIEW", False)
    monkeypatch.setattr("src.integrations.theirstack.sync_service.settings.THEIRSTACK_MAX_QUERIES_PER_REFRESH", 3)

    client = _BillingBlockedClient()
    service = TheirStackSyncService(client=client)  # type: ignore[arg-type]

    result = await service.search_from_resume({"skills": ["python"], "location": "India"}, {})

    assert result["provider_blocked"] is True
    assert result["billing_required"] is True
    assert result["provider_status_code"] == 402
    assert result["jobs"] == []
    assert result["provider_health"]["status"] == "blocked"
    assert client.calls == 1
    assert result["provider_http_call_count"] == 1
    assert result["credit_upper_bound"] <= 5


@pytest.mark.asyncio
async def test_search_from_resume_makes_one_paid_call_no_preview_no_fallback(monkeypatch):
    from src.integrations.theirstack.sync_service import TheirStackSyncService

    monkeypatch.setattr("src.integrations.theirstack.sync_service.settings.THEIRSTACK_ENABLE_FREE_COUNT_PREVIEW", False)
    monkeypatch.setattr("src.integrations.theirstack.sync_service.settings.THEIRSTACK_MAX_QUERIES_PER_REFRESH", 1)
    client = _FakeSearchClient([])
    service = TheirStackSyncService(client=client)  # type: ignore[arg-type]

    result = await service.search_from_resume({"skills": ["python"], "location": "India"}, {})

    assert client.calls == 1
    assert client.payloads[0]["page"] == 0
    assert client.payloads[0]["limit"] == 5
    assert client.payloads[0].get("include_total_results") is False
    assert result["jobs"] == []
    assert result["provider_http_call_count"] == 1
    assert result["credit_upper_bound"] == 0
    assert all(item.get("type") != "preview" for item in result["queries"])
    assert all(item.get("type") != "fallback_search" for item in result["queries"])


@pytest.mark.asyncio
async def test_search_from_resume_explicit_broad_mode_makes_one_call(monkeypatch):
    from src.integrations.theirstack.sync_service import TheirStackSyncService

    monkeypatch.setattr("src.integrations.theirstack.sync_service.settings.THEIRSTACK_ENABLE_FREE_COUNT_PREVIEW", False)
    client = _FakeSearchClient([_raw_job(1)])
    service = TheirStackSyncService(client=client)  # type: ignore[arg-type]

    result = await service.search_from_resume({"skills": ["python"], "location": "India"}, {"search_mode": "broad"})

    assert client.calls == 1
    assert result["normalized"] == 1
    assert result["audit"]["search_mode"] == "broad"
    assert result["audit"]["provider_http_call_count"] == 1


@pytest.mark.asyncio
async def test_search_from_resume_caps_normalized_jobs_to_five(monkeypatch):
    from src.integrations.theirstack.sync_service import TheirStackSyncService

    monkeypatch.setattr("src.integrations.theirstack.sync_service.settings.THEIRSTACK_ENABLE_FREE_COUNT_PREVIEW", False)
    client = _FakeSearchClient([_raw_job(i) for i in range(7)])
    service = TheirStackSyncService(client=client)  # type: ignore[arg-type]

    result = await service.search_from_resume({"skills": ["python"], "location": "India"}, {})

    assert client.calls == 1
    assert result["found"] == 7
    assert result["normalized"] == 5
    assert len(result["jobs"]) == 5
    assert result["audit"]["credit_upper_bound"] == 5
    assert result["audit"]["provider_http_call_count"] == 1
