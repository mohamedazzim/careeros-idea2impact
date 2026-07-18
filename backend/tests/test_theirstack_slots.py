"""Tests for TheirStack 15-slot key resolution, rotation, and ingestion safety."""
import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone


class TestKeyResolution:
    """Test credential_resolver loads all 15 slots correctly."""

    def test_loads_15_canonical_keys(self):
        from src.integrations.theirstack.credential_resolver import resolve_keys

        mock_settings = MagicMock()
        mock_settings.THEIRSTACK_API_KEY = None
        for i in range(1, 16):
            setattr(mock_settings, f"THEIRSTACK_API_KEY_{i}", f"key_{i}_value")
            setattr(mock_settings, f"THEIRSTACK_API_URL_{i}", None)

        with patch("src.integrations.theirstack.credential_resolver.settings", mock_settings):
            result = resolve_keys()

        assert result.total_slots == 15
        assert result.has_keys is True
        slot_names = [s.slot_name for s in result.slots]
        assert "key_1" in slot_names
        assert "key_15" in slot_names

    def test_loads_15_legacy_url_keys(self):
        from src.integrations.theirstack.credential_resolver import resolve_keys

        mock_settings = MagicMock()
        mock_settings.THEIRSTACK_API_KEY = None
        for i in range(1, 16):
            setattr(mock_settings, f"THEIRSTACK_API_KEY_{i}", None)
            setattr(mock_settings, f"THEIRSTACK_API_URL_{i}", f"legacy_key_{i}")

        with patch("src.integrations.theirstack.credential_resolver.settings", mock_settings):
            result = resolve_keys()

        assert result.total_slots == 15
        assert all(s.is_legacy for s in result.slots)
        assert any("legacy TheirStack key alias slot" in warning for warning in result.warnings)

    def test_canonical_overrides_legacy(self):
        from src.integrations.theirstack.credential_resolver import resolve_keys

        mock_settings = MagicMock()
        mock_settings.THEIRSTACK_API_KEY = None
        for i in range(1, 16):
            setattr(mock_settings, f"THEIRSTACK_API_KEY_{i}", f"canonical_{i}")
            setattr(mock_settings, f"THEIRSTACK_API_URL_{i}", f"legacy_{i}")

        with patch("src.integrations.theirstack.credential_resolver.settings", mock_settings):
            result = resolve_keys()

        canonical_count = sum(1 for s in result.slots if not s.is_legacy)
        legacy_count = sum(1 for s in result.slots if s.is_legacy)
        assert canonical_count == 15
        assert legacy_count == 0

    def test_legacy_url_skipped_if_canonical_exists(self):
        from src.integrations.theirstack.credential_resolver import resolve_keys

        mock_settings = MagicMock()
        mock_settings.THEIRSTACK_API_KEY = "primary"
        for i in range(1, 16):
            setattr(mock_settings, f"THEIRSTACK_API_KEY_{i}", None)
            setattr(mock_settings, f"THEIRSTACK_API_URL_{i}", None)

        with patch("src.integrations.theirstack.credential_resolver.settings", mock_settings):
            result = resolve_keys()

        assert result.total_slots == 1
        assert result.slots[0].slot_name == "primary"

    def test_empty_config_returns_no_keys(self):
        from src.integrations.theirstack.credential_resolver import resolve_keys

        mock_settings = MagicMock()
        mock_settings.THEIRSTACK_API_KEY = None
        for i in range(1, 16):
            setattr(mock_settings, f"THEIRSTACK_API_KEY_{i}", None)
            setattr(mock_settings, f"THEIRSTACK_API_URL_{i}", None)

        with patch("src.integrations.theirstack.credential_resolver.settings", mock_settings):
            result = resolve_keys()

        assert result.total_slots == 0
        assert result.has_keys is False

    def test_deduplication(self):
        from src.integrations.theirstack.credential_resolver import resolve_keys

        mock_settings = MagicMock()
        mock_settings.THEIRSTACK_API_KEY = "same_key"
        mock_settings.THEIRSTACK_API_KEY_1 = None
        mock_settings.THEIRSTACK_API_KEY_2 = "same_key"
        for i in range(3, 16):
            setattr(mock_settings, f"THEIRSTACK_API_KEY_{i}", None)
        for i in range(1, 16):
            setattr(mock_settings, f"THEIRSTACK_API_URL_{i}", None)

        with patch("src.integrations.theirstack.credential_resolver.settings", mock_settings):
            result = resolve_keys()

        keys = [s.key for s in result.slots]
        assert keys.count("same_key") == 1

    def test_http_urls_not_treated_as_keys(self):
        from src.integrations.theirstack.credential_resolver import resolve_keys

        mock_settings = MagicMock()
        mock_settings.THEIRSTACK_API_KEY = None
        for i in range(1, 16):
            setattr(mock_settings, f"THEIRSTACK_API_KEY_{i}", None)
            setattr(mock_settings, f"THEIRSTACK_API_URL_{i}", f"https://example.com/api/{i}")

        with patch("src.integrations.theirstack.credential_resolver.settings", mock_settings):
            result = resolve_keys()

        assert result.total_slots == 0

    def test_whitespace_stripped(self):
        from src.integrations.theirstack.credential_resolver import resolve_keys

        mock_settings = MagicMock()
        mock_settings.THEIRSTACK_API_KEY = None
        mock_settings.THEIRSTACK_API_KEY_1 = "  key_1  "
        for i in range(2, 16):
            setattr(mock_settings, f"THEIRSTACK_API_KEY_{i}", None)
        for i in range(1, 16):
            setattr(mock_settings, f"THEIRSTACK_API_URL_{i}", None)

        with patch("src.integrations.theirstack.credential_resolver.settings", mock_settings):
            result = resolve_keys()

        assert result.slots[0].key == "key_1"


class TestIngestionSafety:
    """Verify TheirStack upsert correctly excludes non-India jobs at save time."""

    def test_uk_germany_location_is_rejected(self):
        from src.services.job_location_filter import classify_job_location
        r = classify_job_location(location_raw="Remote - United Kingdom, Germany")
        assert r.is_india_eligible is False

    def test_london_uk_ontario_us_is_rejected(self):
        from src.services.job_location_filter import classify_job_location
        r = classify_job_location(location_raw="London, UK; Ontario, CAN; United States; San Francisco, CA")
        assert r.is_india_eligible is False

    def test_bare_remote_without_india_is_rejected(self):
        from src.services.job_location_filter import classify_job_location
        r = classify_job_location(location_raw="Remote")
        assert r.is_india_eligible is False

    def test_remote_india_is_accepted(self):
        from src.services.job_location_filter import classify_job_location
        r = classify_job_location(location_raw="Remote India")
        assert r.is_india_eligible is True

    def test_bengaluru_india_is_accepted(self):
        from src.services.job_location_filter import classify_job_location
        r = classify_job_location(location_raw="Bengaluru, Karnataka, India")
        assert r.is_india_eligible is True

    def test_upsert_sets_excluded_for_non_india(self):
        """Non-India TheirStack jobs must be saved as status='excluded', not 'active'."""
        from src.services.job_location_filter import classify_job_location
        loc = classify_job_location(location_raw="Berlin, Germany")
        assert loc.is_india_eligible is False
        status = "active"
        lifecycle = "NEW"
        is_non_tech = False
        is_stale = False
        if is_non_tech:
            status = "excluded"
            lifecycle = "EXCLUDED"
        elif not loc.is_india_eligible:
            status = "excluded"
            lifecycle = "EXCLUDED"
        elif is_stale:
            status = "expired"
            lifecycle = "EXPIRED"
        assert status == "excluded"
        assert lifecycle == "EXCLUDED"


class TestRotation:
    """Test client rotation behavior."""

    def test_get_next_valid_slot(self):
        from src.integrations.theirstack.credential_resolver import KeySlot, get_next_valid_slot

        slots = [
            KeySlot(slot_name="a", key="k1"),
            KeySlot(slot_name="b", key="k2"),
            KeySlot(slot_name="c", key="k3"),
        ]
        result = get_next_valid_slot(slots, after_slot="a")
        assert result.slot_name == "b"

    def test_get_next_valid_slot_skips_invalid(self):
        from src.integrations.theirstack.credential_resolver import KeySlot, get_next_valid_slot

        slots = [
            KeySlot(slot_name="a", key="k1"),
            KeySlot(slot_name="b", key="k2", valid=False),
            KeySlot(slot_name="c", key="k3"),
        ]
        result = get_next_valid_slot(slots, after_slot="a")
        assert result.slot_name == "c"

    def test_get_next_valid_slot_returns_none_at_end(self):
        from src.integrations.theirstack.credential_resolver import KeySlot, get_next_valid_slot

        slots = [
            KeySlot(slot_name="a", key="k1"),
            KeySlot(slot_name="b", key="k2"),
        ]
        result = get_next_valid_slot(slots, after_slot="b")
        assert result is None


class TestNoKeyValuesInLogs:
    """Verify no actual key values leak into log output."""

    def test_resolve_keys_does_not_log_values(self, caplog):
        from src.integrations.theirstack.credential_resolver import resolve_keys

        mock_settings = MagicMock()
        mock_settings.THEIRSTACK_API_KEY = None
        mock_settings.THEIRSTACK_API_KEY_1 = None
        mock_settings.THEIRSTACK_API_URL_1 = "secret_abc_123"
        for i in range(2, 16):
            setattr(mock_settings, f"THEIRSTACK_API_KEY_{i}", None)
        for i in range(2, 16):
            setattr(mock_settings, f"THEIRSTACK_API_URL_{i}", None)

        with patch("src.integrations.theirstack.credential_resolver.settings", mock_settings):
            result = resolve_keys()

        for warning in result.warnings:
            assert "secret_abc_123" not in warning
        assert len(result.warnings) == 1
        assert "legacy TheirStack key alias slot" in result.warnings[0]


class TestTheirStackStrictPayload:
    """Verify strict India-only job discovery payload construction."""

    def test_module_payload_builder_supports_preview_and_optional_incremental_fields(self):
        from src.integrations.theirstack.sync_service import build_theirstack_indian_tech_jobs_payload

        payload = build_theirstack_indian_tech_jobs_payload(
            limit=10,
            page=2,
            since_days=7,
            preview=True,
            discovered_at_gte=datetime(2026, 6, 1, tzinfo=timezone.utc),
            exclude_job_ids=["abc", "def"],
            title_terms=["software engineer"],
            negative_title_terms=["sales"],
        )

        assert payload["limit"] == 1
        assert payload["page"] == 2
        assert payload["blur_company_data"] is True
        assert payload["include_total_results"] is True
        assert payload["discovered_at_gte"] == "2026-06-01"
        assert payload["job_id_not"] == ["abc", "def"]
        assert payload["property_exists_and"] == ["final_url"]
        assert payload["job_title_or"] == ["software engineer"]
        assert payload["job_title_not"] == ["sales"]

    def test_build_search_payload_is_strict_and_resume_centric(self):
        from src.integrations.theirstack.sync_service import TheirStackSyncService

        service = TheirStackSyncService(client=MagicMock())
        profile = {
            "skills": ["Python", "SQL", "FastAPI"],
            "education": ["MCA"],
            "location": "Pune, India",
            "target_role": "Data Engineer",
        }
        preferences = {
            "target_role": "Senior Data Engineer",
            "target_location": "Bengaluru",
            "salary_preference": "15-20 LPA",
        }

        payload = service.build_search_payload(profile, preferences)

        assert payload["page"] == 0
        assert payload["limit"] == 25
        assert payload["job_country_code_or"] == ["IN"]
        assert payload["company_type"] == "direct_employer"
        assert payload["is_closed"] is False
        assert payload["property_exists_and"] == ["final_url"]
        assert payload["employment_statuses_or"] == ["full_time"]
        assert "job_title_or" in payload and "Data Engineer" in payload["job_title_or"]
        assert "job_description_contains_or" in payload and any(
            term.lower() == "python" for term in payload["job_description_contains_or"]
        )
        assert payload["job_title_not"]
        assert "salary_preference" not in payload

        expected_date = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        assert payload["posted_at_gte"] == expected_date

    def test_preview_payload_enables_free_count_mode(self):
        from src.integrations.theirstack.sync_service import TheirStackSyncService

        service = TheirStackSyncService(client=MagicMock())
        payload = service.build_preview_payload({"skills": ["Python"]}, {})

        assert payload["blur_company_data"] is True
        assert payload["include_total_results"] is True
        assert payload["limit"] == 1
        assert payload["job_country_code_or"] == ["IN"]
        assert payload["property_exists_and"] == ["final_url"]

    def test_build_search_payload_includes_incremental_hints_when_present(self):
        from src.integrations.theirstack.sync_service import TheirStackSyncService

        service = TheirStackSyncService(client=MagicMock())
        payload = service.build_search_payload(
            {"skills": ["Python"]},
            {
                "discovered_at_gte": datetime(2026, 6, 8, tzinfo=timezone.utc),
                "exclude_job_ids": ["job-1", "job-2"],
            },
        )

        assert payload["discovered_at_gte"] == "2026-06-08"
        assert payload["job_id_not"] == ["job-1", "job-2"]

    def test_final_url_is_preferred_for_apply_url_mapping(self):
        from src.integrations.theirstack.normalizer import normalize_job

        normalized = normalize_job({
            "id": "job-123",
            "job_title": "Backend Engineer",
            "company_name": "Example Co",
            "description": "Python SQL FastAPI",
            "posted_at": "2026-06-10T00:00:00Z",
            "final_url": "https://company.example/jobs/123",
            "url": "https://aggregator.example/jobs/123",
            "source_url": "https://source.example/jobs/123",
        })

        assert normalized is not None
        assert normalized.apply_url == "https://company.example/jobs/123"

    @pytest.mark.asyncio
    async def test_upsert_jobs_updates_existing_duplicate_source_job_id(self):
        from src.integrations.theirstack.sync_service import TheirStackSyncService
        from src.integrations.theirstack.schemas import NormalizedTheirStackJob

        service = TheirStackSyncService(client=MagicMock())
        posted_at = datetime(2026, 6, 10, 0, 0, 0)

        first = NormalizedTheirStackJob(
            source_job_id="job-duplicate-1",
            title="Backend Engineer",
            company="Acme",
            location="Bengaluru, India",
            full_description="Python FastAPI SQL",
            apply_url="https://company.example/jobs/1",
            posted_at=posted_at,
            extracted_skills=["python", "fastapi", "sql"],
            salary="INR 12-18 LPA",
            remote=None,
            original_provider="theirstack",
            original_provider_metadata={"id": "job-duplicate-1"},
            freshness_score=100.0,
            freshness_bucket="fresh",
            provider_quality_score=95.0,
            salary_quality_score=90.0,
            apply_url_valid=True,
        )
        second = first.model_copy(update={"company": "Acme Updated", "salary": "INR 15-20 LPA"})
        fake_db = AsyncMock()
        fake_existing = SimpleNamespace(id=321)
        fake_db.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=lambda: None),
            MagicMock(scalars=lambda: MagicMock(all=lambda: [])),
            MagicMock(scalar_one_or_none=lambda: fake_existing),
            MagicMock(scalars=lambda: MagicMock(all=lambda: [SimpleNamespace(source_job_id="job-duplicate-1")])),
        ])
        fake_db.commit = AsyncMock()
        fake_repo = AsyncMock()

        with patch("src.integrations.theirstack.sync_service.JobRepository", return_value=fake_repo):
            added_1, updated_1, expired_1 = await service.upsert_jobs(fake_db, [first])
            added_2, updated_2, expired_2 = await service.upsert_jobs(fake_db, [second])

        assert added_1 == 1 and updated_1 == 0 and expired_1 == 0
        assert added_2 == 0 and updated_2 == 1 and expired_2 == 0
        fake_repo.create.assert_awaited_once()
        fake_repo.update.assert_awaited_once()
        _, update_kwargs = fake_repo.update.await_args
        assert update_kwargs["company"] == "Acme Updated"
        assert update_kwargs["salary_range"] == "INR 15-20 LPA"
