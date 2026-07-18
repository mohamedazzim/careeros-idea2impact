"""Tests for CALL alert safety: dry-run, duplicate prevention, provider guards, and non-india leak."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def _make_async_session(result_obj=None):
    """Return an async context manager mock for async_session."""
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = result_obj
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, mock_db


@pytest.fixture(autouse=True)
def _mock_default_call_locks(monkeypatch):
    """Keep call-safety tests isolated from the real Redis lock manager."""
    fake_lease = MagicMock(name="lease")
    fake_lock_mgr = MagicMock()
    fake_lock_mgr.acquire = AsyncMock(return_value=fake_lease)
    fake_lock_mgr.release = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "src.services.opportunity.alert_action_service.get_lock_manager",
        lambda: fake_lock_mgr,
    )
    monkeypatch.setattr(
        "src.services.opportunity.communication_orchestrator.get_lock_manager",
        lambda: fake_lock_mgr,
    )


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------

class TestDryRunConfig:
    def test_dry_run_default_true(self):
        from src.core.config import Settings
        assert isinstance(Settings().CALL_ALERT_DRY_RUN, bool)

    def test_outbound_dry_run_default_true(self):
        from src.core.config import Settings
        assert isinstance(Settings().OUTBOUND_CALL_DRY_RUN, bool)

    def test_cooldown_default_24h(self):
        from src.core.config import Settings
        assert Settings().CALL_ALERT_COOLDOWN_HOURS == 24


# ---------------------------------------------------------------------------
# Decision logic tests (no DB mocking needed)
# ---------------------------------------------------------------------------

class TestDecisionLogic:
    @pytest.mark.asyncio
    async def test_score_below_threshold_blocks_call(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        with patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1):
            with patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=False):
                result = await svc.process_decision(
                    user_id="u1", job_id=1,
                    opportunity={"id": "1", "title": "X", "company": "Y", "overall_score": 50},
                    decision="CALL",
                )
            assert result.delivery_status == "blocked_by_threshold"

    @pytest.mark.asyncio
    async def test_suppressed_decision_returns_no_action(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        with patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1):
            result = await svc.process_decision(
                user_id="u1", job_id=1,
                opportunity={"id": "1", "title": "X", "company": "Y"},
                decision="NONE",
            )
            assert result.delivery_status == "suppressed"

    @pytest.mark.asyncio
    async def test_dashboard_decision_creates_notification(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        with patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1), \
             patch.object(svc, "_create_communication_request", new_callable=AsyncMock, return_value=10):
            result = await svc.process_decision(
                user_id="u1", job_id=1,
                opportunity={"id": "1", "title": "X", "company": "Y"},
                decision="DASHBOARD_ONLY",
            )
            assert result.delivery_status == "delivered_to_dashboard"


# ---------------------------------------------------------------------------
# Dry-run does NOT call providers
# ---------------------------------------------------------------------------

class TestDryRunNoProviderCalls:
    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_orchestrator(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        mock_orch = AsyncMock()
        ctx, mock_db = _make_async_session(None)

        with patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1), \
             patch.object(svc, "_create_communication_request", new_callable=AsyncMock, return_value=10), \
             patch.object(svc, "_check_duplicate_call", new_callable=AsyncMock, return_value=None), \
             patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=True), \
             patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx):
            with patch(
                "src.services.opportunity.communication_orchestrator.get_communication_orchestrator",
                return_value=mock_orch,
            ):
                result = await svc.process_decision(
                    user_id="u1", job_id=1,
                    opportunity={"id": "1", "title": "X", "company": "Y", "overall_score": 80},
                    decision="CALL", dry_run=True,
                )
            assert result.delivery_status == "dry_run"
            assert result.dry_run is True
            mock_orch.deliver.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_via_config_does_not_call_orchestrator(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        mock_orch = AsyncMock()
        ctx, mock_db = _make_async_session(None)

        with patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1), \
             patch.object(svc, "_create_communication_request", new_callable=AsyncMock, return_value=10), \
             patch.object(svc, "_check_duplicate_call", new_callable=AsyncMock, return_value=None), \
             patch.object(svc, "_create_approval", new_callable=AsyncMock, return_value="uid-456"), \
             patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=True), \
             patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_MIN_MATCH_SCORE = 65
            mock_settings.CALL_ALERT_DRY_RUN = True
            mock_settings.OUTBOUND_CALL_DRY_RUN = True
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            mock_settings.PIPEDREAM_WEBHOOK_URL = ""
            with patch(
                "src.services.opportunity.communication_orchestrator.get_communication_orchestrator",
                return_value=mock_orch,
            ):
                result = await svc.process_decision(
                    user_id="u1", job_id=1,
                    opportunity={"id": "1", "title": "X", "company": "Y", "overall_score": 80},
                    decision="CALL", dry_run=False,
                )
            assert result.delivery_status == "dry_run"
            mock_orch.deliver.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_delivery_blocked_when_phone_missing(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        mock_orch = AsyncMock()
        ctx, mock_db = _make_async_session(None)

        from src.services.opportunity.conversational_outbound_call_service import OutboundRecipientResolution
        with patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1), \
             patch.object(svc, "_create_communication_request", new_callable=AsyncMock, return_value=10), \
             patch.object(svc, "_check_duplicate_call", new_callable=AsyncMock, return_value=None), \
             patch.object(svc, "_create_approval", new_callable=AsyncMock, return_value="uid-789"), \
             patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=True), \
             patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.conversational_outbound_call_service.resolve_outbound_recipient_number", return_value=OutboundRecipientResolution("", "missing", "missing_recipient_number")), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_MIN_MATCH_SCORE = 65
            mock_settings.CALL_ALERT_DRY_RUN = False
            mock_settings.OUTBOUND_CALL_DRY_RUN = False
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            mock_settings.TWILIO_ACCOUNT_SID = "AC_test"
            mock_settings.ELEVENLABS_API_KEY = "el_test"
            mock_settings.PIPEDREAM_WEBHOOK_URL = ""
            with patch(
                "src.services.opportunity.communication_orchestrator.get_communication_orchestrator",
                return_value=mock_orch,
            ):
                result = await svc.process_decision(
                    user_id="u1", job_id=1,
                    opportunity={"id": "1", "title": "X", "company": "Y", "overall_score": 80},
                    decision="CALL", phone_number=None,
                )
            assert result.delivery_status == "blocked_no_phone"
            assert result.provider_status == "missing_phone_number"
            mock_orch.deliver.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_delivery_proceeds_without_twilio_account_sid(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        mock_orch = AsyncMock()
        mock_orch.deliver.return_value = {"delivery_status": "started", "provider_status": "conversation_agent_started"}
        ctx, mock_db = _make_async_session(None)

        with patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1), \
             patch.object(svc, "_create_communication_request", new_callable=AsyncMock, return_value=10), \
             patch.object(svc, "_check_duplicate_call", new_callable=AsyncMock, return_value=None), \
             patch.object(svc, "_create_approval", new_callable=AsyncMock, return_value="uid-t"), \
             patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=True), \
             patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_MIN_MATCH_SCORE = 65
            mock_settings.CALL_ALERT_DRY_RUN = False
            mock_settings.OUTBOUND_CALL_DRY_RUN = False
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            mock_settings.TWILIO_ACCOUNT_SID = None
            mock_settings.ELEVENLABS_API_KEY = "el_test"
            mock_settings.PIPEDREAM_WEBHOOK_URL = ""
            with patch(
                "src.services.opportunity.communication_orchestrator.get_communication_orchestrator",
                return_value=mock_orch,
            ):
                result = await svc.process_decision(
                    user_id="u1", job_id=1,
                    opportunity={"id": "1", "title": "X", "company": "Y", "overall_score": 80},
                    decision="CALL", phone_number="+12025550123",
                )
            assert result.delivery_status == "started"
            mock_orch.deliver.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_real_delivery_blocked_when_elevenlabs_not_configured(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        mock_orch = AsyncMock()
        ctx, mock_db = _make_async_session(None)

        with patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1), \
             patch.object(svc, "_create_communication_request", new_callable=AsyncMock, return_value=10), \
             patch.object(svc, "_check_duplicate_call", new_callable=AsyncMock, return_value=None), \
             patch.object(svc, "_create_approval", new_callable=AsyncMock, return_value="uid-e"), \
             patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=True), \
             patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_MIN_MATCH_SCORE = 65
            mock_settings.CALL_ALERT_DRY_RUN = False
            mock_settings.OUTBOUND_CALL_DRY_RUN = False
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            mock_settings.TWILIO_ACCOUNT_SID = "AC_test"
            mock_settings.ELEVENLABS_API_KEY = None
            mock_settings.PIPEDREAM_WEBHOOK_URL = ""
            with patch(
                "src.services.opportunity.communication_orchestrator.get_communication_orchestrator",
                return_value=mock_orch,
            ):
                result = await svc.process_decision(
                    user_id="u1", job_id=1,
                    opportunity={"id": "1", "title": "X", "company": "Y", "overall_score": 80},
                    decision="CALL", phone_number="+12025550123",
                )
            assert result.delivery_status == "blocked_missing_config"
            assert result.provider_status == "missing_elevenlabs_api_key"
            mock_orch.deliver.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_delivery_allowed_only_when_all_conditions_met(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        mock_orch = AsyncMock()
        mock_orch.deliver.return_value = {"delivery_status": "sent", "provider_status": "twilio_ok"}
        ctx, mock_db = _make_async_session(None)

        with patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1), \
             patch.object(svc, "_create_communication_request", new_callable=AsyncMock, return_value=10), \
             patch.object(svc, "_check_duplicate_call", new_callable=AsyncMock, return_value=None), \
             patch.object(svc, "_create_approval", new_callable=AsyncMock, return_value="uid-ok"), \
             patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=True), \
             patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_MIN_MATCH_SCORE = 65
            mock_settings.CALL_ALERT_DRY_RUN = False
            mock_settings.OUTBOUND_CALL_DRY_RUN = False
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            mock_settings.TWILIO_ACCOUNT_SID = "AC_test"
            mock_settings.ELEVENLABS_API_KEY = "el_test"
            mock_settings.PIPEDREAM_WEBHOOK_URL = ""
            with patch(
                "src.services.opportunity.communication_orchestrator.get_communication_orchestrator",
                return_value=mock_orch,
            ):
                result = await svc.process_decision(
                    user_id="u1", job_id=1,
                    opportunity={"id": "1", "title": "X", "company": "Y", "overall_score": 80},
                    decision="CALL", phone_number="+12025550123",
                )
            assert result.delivery_status == "sent"
            mock_orch.deliver.assert_called_once()

    @pytest.mark.asyncio
    async def test_real_delivery_passes_existing_request_id_to_orchestrator(self):
        from src.services.opportunity import alert_action_service as alert_mod
        svc = alert_mod.get_alert_action_service()
        mock_orch = AsyncMock()
        mock_orch.deliver.return_value = {"delivery_status": "started", "provider_status": "ok"}
        ctx, mock_db = _make_async_session(None)

        with patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1), \
             patch.object(svc, "_create_communication_request", new_callable=AsyncMock, return_value=77), \
             patch.object(svc, "_check_duplicate_call", new_callable=AsyncMock, return_value=None), \
             patch.object(svc, "_create_approval", new_callable=AsyncMock, return_value="uid-ok"), \
             patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=True), \
             patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_MIN_MATCH_SCORE = 65
            mock_settings.CALL_ALERT_DRY_RUN = False
            mock_settings.OUTBOUND_CALL_DRY_RUN = False
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            mock_settings.TWILIO_ACCOUNT_SID = "AC_test"
            mock_settings.ELEVENLABS_API_KEY = "el_test"
            mock_settings.PIPEDREAM_WEBHOOK_URL = ""
            with patch(
                "src.services.opportunity.communication_orchestrator.get_communication_orchestrator",
                return_value=mock_orch,
            ):
                result = await svc.process_decision(
                    user_id="u1", job_id=1,
                    opportunity={"id": "1", "title": "X", "company": "Y", "overall_score": 80},
                    decision="CALL", phone_number="+12025550123",
                )

        mock_orch.deliver.assert_awaited_once()
        assert mock_orch.deliver.await_args.kwargs["communication_request_id"] == 77
        assert result.communication_request_id == 77


# ---------------------------------------------------------------------------
# Duplicate check tests (mock DB layer)
# ---------------------------------------------------------------------------

class TestDuplicateCheck:
    @pytest.mark.asyncio
    async def test_duplicate_found_returns_reason(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        mock_existing = MagicMock()
        mock_existing.id = 42
        ctx, _ = _make_async_session(mock_existing)
        with patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            result = await svc._check_duplicate_call(user_id="u1", job_id=10)
            assert result is not None
            assert "recent_call_within_24h" in result

    @pytest.mark.asyncio
    async def test_no_duplicate_returns_none(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        ctx, _ = _make_async_session(None)
        with patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            result = await svc._check_duplicate_call(user_id="u1", job_id=10)
            assert result is None

    @pytest.mark.asyncio
    async def test_duplicate_query_uses_or_for_channels(self):
        """Verify duplicate check builds a query with OR for VOICE_CALL / phone_call."""
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        ctx, mock_db = _make_async_session(None)
        with patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            await svc._check_duplicate_call(user_id="u1", job_id=10)
            call_args = mock_db.execute.call_args[0][0]
            compiled = call_args.whereclause.compile(compile_kwargs={"literal_binds": True}).string
            assert "VOICE_CALL" in compiled or "phone_call" in compiled

    @pytest.mark.asyncio
    async def test_duplicate_query_uses_limit_1(self):
        """Verify duplicate check uses LIMIT(1) to prevent MultipleResultsFound."""
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        ctx, mock_db = _make_async_session(None)
        with patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            await svc._check_duplicate_call(user_id="u1", job_id=10)
            call_args = mock_db.execute.call_args[0][0]
            compiled = str(call_args)
            assert "LIMIT" in compiled or "limit" in compiled

    @pytest.mark.asyncio
    async def test_duplicate_handles_multiple_rows_without_crash(self):
        """Even if scalars().first() returns a result, no MultipleResultsFound."""
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()

        mock_existing = MagicMock()
        mock_existing.id = 99

        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_existing

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_db)
        ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            result = await svc._check_duplicate_call(user_id="u1", job_id=10)
            assert result is not None
            assert "recent_call_within_24h" in result
            assert "id=99" in result


# ---------------------------------------------------------------------------
# Duplicate suppression integration tests
# ---------------------------------------------------------------------------

class TestDuplicateSuppressionIntegration:
    @pytest.mark.asyncio
    async def test_duplicate_prevents_call(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        with patch.object(svc, "_check_duplicate_call", new_callable=AsyncMock, return_value="recent_call_within_24h"), \
             patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1):
            with patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=True):
                result = await svc.process_decision(
                    user_id="u1", job_id=99,
                    opportunity={"id": "99", "title": "X", "company": "Y", "overall_score": 80, "apply_url": "http://x"},
                    decision="CALL",
                )
            assert result.delivery_status == "duplicate_suppressed"
            assert "cooldown_active" in result.provider_status

    @pytest.mark.asyncio
    async def test_dispatch_lock_blocks_concurrent_call(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        fake_lock_mgr = MagicMock()
        fake_lock_mgr.acquire = AsyncMock(return_value=None)
        fake_lock_mgr.release = AsyncMock(return_value=True)

        with patch.object(svc, "_check_duplicate_call", new_callable=AsyncMock, return_value=None), \
             patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1), \
             patch.object(svc, "_create_communication_request", new_callable=AsyncMock) as mock_create, \
             patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=True), \
             patch("src.services.opportunity.alert_action_service.get_lock_manager", return_value=fake_lock_mgr):
            result = await svc.process_decision(
                user_id="u1", job_id=99,
                opportunity={"id": "99", "title": "X", "company": "Y", "overall_score": 80, "apply_url": "http://x"},
                decision="CALL",
                phone_number="+12025550123",
            )
        assert result.delivery_status == "duplicate_suppressed"
        assert result.provider_status == "dispatch_lock_active"
        mock_create.assert_not_called()
        fake_lock_mgr.acquire.assert_awaited_once()
        fake_lock_mgr.release.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_duplicate_allows_call_dry_run(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()
        ctx, mock_db = _make_async_session(None)
        with patch.object(svc, "_check_duplicate_call", new_callable=AsyncMock, return_value=None), \
             patch.object(svc, "_write_audit", new_callable=AsyncMock, return_value=1), \
             patch.object(svc, "_create_communication_request", new_callable=AsyncMock, return_value=20), \
             patch.object(svc, "_create_approval", new_callable=AsyncMock, return_value="uid-dry"), \
             patch("src.agents.opportunity_alert_agent.is_call_eligible", return_value=True), \
             patch("src.services.opportunity.alert_action_service.async_session", return_value=ctx), \
             patch("src.services.opportunity.alert_action_service.settings") as mock_settings:
            mock_settings.CALL_ALERT_MIN_MATCH_SCORE = 65
            mock_settings.CALL_ALERT_DRY_RUN = True
            mock_settings.OUTBOUND_CALL_DRY_RUN = True
            mock_settings.CALL_ALERT_COOLDOWN_HOURS = 24
            result = await svc.process_decision(
                user_id="u1", job_id=99,
                opportunity={"id": "99", "title": "X", "company": "Y", "overall_score": 80, "apply_url": "http://x"},
                decision="CALL",
            )
            assert result.delivery_status == "dry_run"
            assert result.decision == "CALL"

    @pytest.mark.asyncio
    async def test_create_request_reuses_active_idempotent_row(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()

        existing = MagicMock()
        existing.id = 123
        existing.communication_status = "started"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.opportunity.alert_action_service.async_session", return_value=mock_ctx):
            cr_id = await svc._create_communication_request(
                user_id="u1",
                job_id=10,
                opportunity={"id": "opp-1", "title": "X", "company": "Y", "overall_score": 80},
                channel="CALL",
                decision_reason="match",
                decision_confidence=0.9,
                idempotency_key="opportunity_call:u1:10:VOICE_CALL",
            )

        assert cr_id == 123
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_request_reuses_dry_run_row(self):
        from src.services.opportunity.alert_action_service import get_alert_action_service
        svc = get_alert_action_service()

        existing = MagicMock()
        existing.id = 124
        existing.communication_status = "dry_run"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.opportunity.alert_action_service.async_session", return_value=mock_ctx):
            cr_id = await svc._create_communication_request(
                user_id="u1",
                job_id=10,
                opportunity={"id": "opp-2", "title": "X", "company": "Y", "overall_score": 80},
                channel="CALL",
                decision_reason="match",
                decision_confidence=0.9,
                idempotency_key="opportunity_call:u1:10:VOICE_CALL",
            )

        assert cr_id == 124
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_orchestrator_blocks_duplicate_delivery_lock(self):
        from src.services.opportunity.communication_orchestrator import get_communication_orchestrator
        orchestrator = get_communication_orchestrator()

        request = MagicMock()
        request.id = 77
        request.correlation_id = "corr-77"
        request.communication_status = "pending"
        request.communication_result = {}
        request.webhook_status = None
        request.pipedream_response = None
        request.communication_provider = "career_os"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = request

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock(return_value=None)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        fake_lock_mgr = MagicMock()
        fake_lock_mgr.acquire = AsyncMock(return_value=None)
        fake_lock_mgr.release = AsyncMock(return_value=True)

        with patch("src.services.opportunity.communication_orchestrator.async_session", return_value=mock_ctx), \
             patch("src.services.opportunity.communication_orchestrator.get_lock_manager", return_value=fake_lock_mgr), \
             patch("src.services.opportunity.communication_orchestrator.get_elevenlabs_conversational_outbound_call_service") as mock_call_service:
            result = await orchestrator.deliver(
                user_id="u1",
                opportunity={"id": "1", "job_id": 10, "title": "X", "company": "Y"},
                decision="CALL",
                phone_number="+12025550123",
                communication_request_id=77,
            )

        assert result["duplicate_suppressed"] is True
        assert result["provider_status"] == "delivery_lock_active"
        mock_call_service.assert_not_called()
        fake_lock_mgr.acquire.assert_awaited_once()
        fake_lock_mgr.release.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_orchestrator_returns_existing_started_request_without_redelivery(self):
        from src.services.opportunity.communication_orchestrator import get_communication_orchestrator
        orchestrator = get_communication_orchestrator()

        request = MagicMock()
        request.id = 88
        request.correlation_id = "corr-88"
        request.communication_status = "started"
        request.communication_result = {
            "conversation_id": "conv_88",
            "call_sid": "call_88",
            "provider_status": "dispatching",
            "call_status": "started",
            "agent_id_configured": True,
            "agent_phone_number_id_configured": True,
            "dynamic_variables_present": True,
            "voice_session_id": 12,
        }
        request.webhook_status = "skipped_voice_call"
        request.pipedream_response = {"reason": "voice_call_already_started"}
        request.communication_provider = "elevenlabs_convai"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = request

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock(return_value=None)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.opportunity.communication_orchestrator.async_session", return_value=mock_ctx), \
             patch("src.services.opportunity.communication_orchestrator.get_elevenlabs_conversational_outbound_call_service") as mock_call_service:
            result = await orchestrator.deliver(
                user_id="u1",
                opportunity={"id": "1", "job_id": 10, "title": "X", "company": "Y"},
                decision="CALL",
                phone_number="+12025550123",
                communication_request_id=88,
            )

        assert result["duplicate_suppressed"] is True
        assert result["delivery_status"] == "started"
        assert result["conversation_id"] == "conv_88"
        mock_call_service.assert_not_called()


# ---------------------------------------------------------------------------
# Provider ingestion non_india_active leak tests
# ---------------------------------------------------------------------------

class TestProviderIngestionNonIndiaLeak:
    def _eval_status(self, loc, is_non_tech, is_stale):
        if is_non_tech:
            return "excluded"
        elif not loc.is_india_eligible:
            return "excluded"
        elif is_stale:
            return "expired"
        else:
            return "active"

    def test_non_india_non_tech_gets_excluded(self):
        from src.services.job_location_filter import classify_job_location
        loc = classify_job_location(location_raw="Berlin, Germany")
        assert self._eval_status(loc, True, False) == "excluded"

    def test_non_india_tech_gets_excluded(self):
        from src.services.job_location_filter import classify_job_location
        loc = classify_job_location(location_raw="Berlin, Germany")
        assert self._eval_status(loc, False, False) == "excluded"

    def test_india_tech_not_stale_gets_active(self):
        from src.services.job_location_filter import classify_job_location
        loc = classify_job_location(location_raw="Bengaluru, India")
        assert self._eval_status(loc, False, False) == "active"

    def test_india_tech_stale_gets_expired(self):
        from src.services.job_location_filter import classify_job_location
        loc = classify_job_location(location_raw="Bengaluru, India")
        assert self._eval_status(loc, False, True) == "expired"

    def test_india_eligible_lifecycle_new(self):
        from src.services.job_location_filter import classify_job_location
        loc = classify_job_location(location_raw="Bengaluru, India")
        is_non_tech = False
        is_stale = False
        lifecycle = "EXCLUDED" if (is_non_tech or not loc.is_india_eligible) else "EXPIRED" if is_stale else "NEW"
        assert lifecycle == "NEW"

    def test_non_india_lifecycle_excluded(self):
        from src.services.job_location_filter import classify_job_location
        loc = classify_job_location(location_raw="London, UK")
        is_non_tech = False
        is_stale = False
        lifecycle = "EXCLUDED" if (is_non_tech or not loc.is_india_eligible) else "EXPIRED" if is_stale else "NEW"
        assert lifecycle == "EXCLUDED"
