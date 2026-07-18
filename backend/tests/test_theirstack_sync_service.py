import pytest


class _BillingBlockedClient:
    def __init__(self):
        self.configured = True
        self.calls = 0

    async def search_jobs(self, payload, use_cache=True):
        from src.integrations.theirstack.client import ClientSearchResult

        self.calls += 1
        return ClientSearchResult(
            success=False,
            billing_required=True,
            provider_blocked=True,
            provider_status_code=402,
            error="HTTP 402 Payment Required",
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
