"""Tests for agent governance, voice synthesis, twilio voice, explainability, and event bus."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.core.config import settings
from src.agents.orchestration_governance_agent import (
    OrchestrationGovernanceAgent, get_orchestration_governance_agent, GovernanceState
)
from src.agents.elevenlabs_voice_synthesis_agent import (
    ElevenLabsVoiceSynthesisAgent, get_elevenlabs_voice_synthesis_agent
)
from src.agents.twilio_voice_agent import TwilioVoiceAgent, get_twilio_voice_agent
from src.agents.explainability_agent import ExplainabilityAgent, get_explainability_agent
from src.services.opportunity.conversational_outbound_call_service import (
    ElevenLabsConversationalOutboundCallService,
    resolve_outbound_recipient_number,
)
from src.services.opportunity.voice_opportunity_agent import VoiceOpportunityAgent
from src.runtime.events.event_bus import EventBus, Event, get_event_bus


@pytest.fixture(autouse=True)
def _mock_default_call_locks(monkeypatch):
    """Keep governance tests isolated from the real Redis lock manager."""
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


class TestGovernanceAgent:
    @pytest.fixture
    def agent(self):
        return OrchestrationGovernanceAgent()

    def test_validate_passes(self, agent):
        state = asyncio.run(agent.validate(
            session_uid="s1",
            autonomous_count=0,
            recursion_depth=0,
            action_confidence=0.85,
            action_type="notification",
            opportunity_id="opp_1",
        ))
        assert state.verdict == "passed"

    def test_validate_blocks_recursion(self, agent):
        state = asyncio.run(agent.validate(
            session_uid="s1",
            autonomous_count=0,
            recursion_depth=5,
            action_confidence=0.85,
            action_type="notification",
            opportunity_id="opp_2",
        ))
        assert state.verdict == "suppressed"
        assert len(state.suppressed_actions) > 0

    def test_validate_blocks_autonomous_cap(self, agent):
        state = asyncio.run(agent.validate(
            session_uid="s1",
            autonomous_count=7,
            recursion_depth=0,
            action_confidence=0.85,
            action_type="notification",
            opportunity_id="opp_3",
        ))
        assert state.verdict == "suppressed"

    def test_governance_state_dataclass(self):
        state = GovernanceState(governance_run_id="g1", session_uid="s1")
        assert state.verdict == "passed"
        assert state.recursion_depth == 0

    def test_singleton(self):
        a = get_orchestration_governance_agent()
        b = get_orchestration_governance_agent()
        assert a is b


class TestVoiceSynthesisAgent:
    @pytest.fixture
    def agent(self):
        return ElevenLabsVoiceSynthesisAgent()

    def test_generate_script(self, agent):
        script = agent._generate_script("Alice", "Engineer", "Acme", 85, "high")
        assert "Alice" in script
        assert "Engineer" in script
        assert "Acme" in script
        assert "85" in script

    def test_synthesize_basic(self, agent):
        state = asyncio.run(agent.synthesize("u1", "test", "role", "co", 80, "normal"))
        assert state.status in ("completed", "failed")
        assert len(state.voice_script) > 0

    def test_singleton(self):
        a = get_elevenlabs_voice_synthesis_agent()
        b = get_elevenlabs_voice_synthesis_agent()
        assert a is b


class TestTwilioVoiceAgent:
    @pytest.fixture
    def agent(self):
        return TwilioVoiceAgent()

    @pytest.mark.asyncio
    async def test_execute_call(self, agent, monkeypatch):
        monkeypatch.setenv("CI", "true")
        monkeypatch.setenv("CALL_ALERT_DRY_RUN", "true")
        monkeypatch.setenv("OUTBOUND_CALL_DRY_RUN", "true")
        monkeypatch.setenv("MOCK_MCP", "true")

        state = await agent.execute_call("u1", "+15550001111", "test audio")

        assert state.status == "completed"
        assert state.call_sid is not None

    def test_singleton(self):
        a = get_twilio_voice_agent()
        b = get_twilio_voice_agent()
        assert a is b


class TestConversationalOpportunityAgent:
    def test_prompt_matches_live_agent_persona(self):
        agent = VoiceOpportunityAgent()
        prompt = agent.build_conversation_prompt()
        assert "You are Alex, a CareerOS opportunity advisor." in prompt
        assert "Do not end the call immediately after the first message." in prompt

    @pytest.mark.asyncio
    async def test_opportunity_calls_reject_notification_tts_mode(self):
        agent = VoiceOpportunityAgent()
        with pytest.raises(ValueError, match="conversation_agent mode"):
            await agent.start_session(
                None,
                communication_request_id=1,
                user_id="user-1",
                job_id=10,
                intelligence={"job": {"title": "Senior Python Developer", "company": "CareerOS"}},
                mode="notification_tts",
                provider="elevenlabs_convai",
                dynamic_variables={"job_title": "Senior Python Developer"},
            )

    def test_builds_convai_dynamic_variables(self):
        agent = VoiceOpportunityAgent()
        intelligence = {
            "job": {
                "title": "Senior Python Developer",
                "company": "CareerOS",
                "description": "Build backend services",
                "location": "Remote",
                "employment_type": "Full-time",
                "experience_level": "Senior",
            },
            "match_intelligence": {
                "match_score": 92,
                "matched_skills": ["FastAPI", "Python"],
                "missing_skills": ["Kubernetes"],
            },
            "urgency_intelligence": {
                "urgency_score": 0.9,
                "deadline": "2026-06-20",
            },
            "salary_intelligence": {
                "salary_range": "₹18-24 LPA",
            },
            "company_intelligence": {
                "company_description": "CareerOS builds AI hiring tools",
            },
            "application_intelligence": {
                "application_url": "https://example.com/apply",
                "opportunity_priority_score": 88,
            },
            "resume_intelligence": {
                "resume_strengths": ["Backend", "APIs"],
                "resume_gaps": ["Kubernetes"],
                "interview_focus_areas": ["System design"],
            },
        }
        vars_ = agent.build_dynamic_variables(user_name="Asha", opportunity={"user_name": "Asha"}, intelligence=intelligence)
        assert vars_["job_title"] == "Senior Python Developer"
        assert vars_["company"] == "CareerOS"
        assert vars_["salary_range"] == "₹18-24 LPA"
        assert vars_["matching_skills"] == "FastAPI, Python"
        assert vars_["missing_skills"] == "Kubernetes"
        assert vars_["application_url"] == "https://example.com/apply"

    def test_conversation_payload_includes_agent_ids_and_dynamic_variables(self, monkeypatch):
        monkeypatch.setenv("PIPEDREAM_WEBHOOK_URL", "")
        monkeypatch.setattr(settings, "ELEVENLABS_CONVAI_AGENT_ID", "agent_123", raising=False)
        monkeypatch.setattr(settings, "ELEVENLABS_CONVAI_PHONE_NUMBER_ID", "phnum_456", raising=False)

        service = ElevenLabsConversationalOutboundCallService()
        payload = service._build_payload(
            user_id="user-1",
            phone_number="+15555550123",
            dynamic_variables={"job_title": "Senior Python Developer", "company": "CareerOS"},
        )

        assert payload["agent_id"] == "agent_123"
        assert payload["agent_phone_number_id"] == "phnum_456"
        assert payload["To"] == "+15555550123"
        assert payload["to"] == "+15555550123"
        assert payload["to_number"] == "+15555550123"
        assert payload["phone_number"] == "+15555550123"
        assert payload["recipient_phone_number"] == "+15555550123"
        assert payload["destination_number"] == "+15555550123"
        assert payload["conversation_initiation_client_data"]["dynamic_variables"]["job_title"] == "Senior Python Developer"
        assert payload["conversation_initiation_client_data"]["dynamic_variables"]["phone_number"] == "+15555550123"
        assert payload["conversation_initiation_client_data"]["phone_number"] == "+15555550123"
        assert "conversation_config_override" not in payload["conversation_initiation_client_data"]

    def test_resolve_outbound_recipient_prefers_explicit_number_and_rejects_sender_number(self, monkeypatch):
        monkeypatch.setattr(settings, "TWILIO_PHONE_NUMBER", "+15555550100", raising=False)
        monkeypatch.setattr(settings, "TWILIO_TEST_PHONE_NUMBER", "+15555550101", raising=False)
        monkeypatch.setattr(settings, "OUTBOUND_TEST_TO_NUMBER", "+15555550123", raising=False)

        resolution = resolve_outbound_recipient_number("+15555550100")

        assert resolution.phone_number == "+15555550123"
        assert resolution.source == "OUTBOUND_TEST_TO_NUMBER"
        assert resolution.reason == ""

    def test_resolve_outbound_recipient_rejects_phone_ids_and_non_phone_strings(self, monkeypatch):
        monkeypatch.setattr(settings, "TWILIO_PHONE_NUMBER", "+15555550100", raising=False)
        monkeypatch.setattr(settings, "TWILIO_TEST_PHONE_NUMBER", "+15555550101", raising=False)
        monkeypatch.setattr(settings, "OUTBOUND_TEST_TO_NUMBER", "", raising=False)

        resolution = resolve_outbound_recipient_number("phnum_test_rejected_sender_id")

        assert resolution.phone_number == ""
        assert resolution.reason == "missing_recipient_number"
    def test_settings_accept_legacy_elevenlabs_env_names(self, monkeypatch):
        from src.core.config import Settings

        monkeypatch.delenv("ELEVENLABS_CONVAI_AGENT_ID", raising=False)
        monkeypatch.delenv("ELEVENLABS_AGENT_ID", raising=False)
        monkeypatch.delenv("ELEVENLABS_CONVAI_PHONE_NUMBER_ID", raising=False)
        monkeypatch.delenv("ELEVENLABS_AGENT_PHONE_NUMBER_ID", raising=False)
        monkeypatch.delenv("ELEVENLABS_PHONE_NUMBER_ID", raising=False)

        monkeypatch.setenv("ELEVENLABS_AGENT_ID", "legacy_agent_123")
        monkeypatch.setenv("ELEVENLABS_PHONE_NUMBER_ID", "legacy_phone_456")

        legacy_settings = Settings(_env_file=None)

        assert legacy_settings.ELEVENLABS_CONVAI_AGENT_ID == "legacy_agent_123"
        assert legacy_settings.ELEVENLABS_CONVAI_PHONE_NUMBER_ID == "legacy_phone_456"

    @pytest.mark.asyncio
    async def test_initiate_call_starts_conversation_agent_and_keeps_session_open(self, monkeypatch):
        from src.services.opportunity import conversational_outbound_call_service as service_mod

        monkeypatch.setattr(settings, "CALL_ALERT_DRY_RUN", False, raising=False)
        monkeypatch.setattr(settings, "OUTBOUND_CALL_DRY_RUN", False, raising=False)
        monkeypatch.setattr(settings, "ELEVENLABS_CONVAI_AGENT_ID", "agent_123", raising=False)
        monkeypatch.setattr(settings, "ELEVENLABS_CONVAI_PHONE_NUMBER_ID", "phnum_456", raising=False)
        monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "el_test", raising=False)
        monkeypatch.setattr(settings, "PIPEDREAM_WEBHOOK_URL", "", raising=False)

        class _FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"status": "started", "conversation_id": "conv_123", "call_sid": "call_123"}

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, *args, **kwargs):
                return _FakeResponse()

        class _FakeConversationRetrievalAgent:
            async def capture_session(self, *args, **kwargs):
                return None

        class _FakeDB:
            def __init__(self):
                self.objects = []

            def add(self, obj):
                self.objects.append(obj)

            async def flush(self):
                return None

        monkeypatch.setattr(service_mod.httpx, "AsyncClient", _FakeClient)
        monkeypatch.setattr(service_mod, "get_conversation_retrieval_agent", lambda: _FakeConversationRetrievalAgent())

        service = ElevenLabsConversationalOutboundCallService()

        async def _resolve_user_name(db, user_id):
            return ""

        monkeypatch.setattr(service, "_resolve_user_name", _resolve_user_name, raising=False)

        fake_db = _FakeDB()
        result = await service.initiate_call(
            fake_db,
            communication_request_id=99,
            user_id="user-1",
            job_id=10,
            opportunity={"title": "Senior Python Developer", "company": "CareerOS"},
            intelligence={
                "job": {"title": "Senior Python Developer", "company": "CareerOS", "location": "Remote"},
                "match_intelligence": {"match_score": 92, "matched_skills": ["FastAPI"], "missing_skills": ["Kubernetes"]},
                "salary_intelligence": {"salary_range": "₹18-24 LPA"},
                "application_intelligence": {"application_url": "https://example.com/apply"},
            },
            phone_number="+15555550123",
        )

        assert result["status"] == "started"
        assert result["delivery_mode"] == "conversation_agent"
        assert result["agent_id_configured"] is True
        assert result["agent_phone_number_id_configured"] is True
        assert result["dynamic_variables_present"] is True
        assert result["elevenlabs_api_key_configured"] is True
        assert result["payload"]["To"] == "+15555550123"
        assert result["payload"]["recipient_phone_number"] == "+15555550123"
        assert result["payload"]["conversation_initiation_client_data"]["dynamic_variables"]["job_title"] == "Senior Python Developer"
        assert result["payload"]["conversation_initiation_client_data"]["dynamic_variables"]["company"] == "CareerOS"
        assert result["payload"]["conversation_initiation_client_data"]["dynamic_variables"]["phone_number"] == "+15555550123"
        assert result["voice_session_id"] is None or isinstance(result["voice_session_id"], int)
        assert any(getattr(obj, "status", None) == "STARTED" for obj in fake_db.objects)

    @pytest.mark.asyncio
    async def test_initiate_call_blocks_when_direct_api_has_no_key_and_no_bridge(self, monkeypatch):
        monkeypatch.setattr(settings, "CALL_ALERT_DRY_RUN", False, raising=False)
        monkeypatch.setattr(settings, "OUTBOUND_CALL_DRY_RUN", False, raising=False)
        monkeypatch.setattr(settings, "ELEVENLABS_CONVAI_AGENT_ID", "agent_123", raising=False)
        monkeypatch.setattr(settings, "ELEVENLABS_CONVAI_PHONE_NUMBER_ID", "phnum_456", raising=False)
        monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", None, raising=False)
        monkeypatch.setattr(settings, "PIPEDREAM_WEBHOOK_URL", "", raising=False)

        class _FakeDB:
            async def flush(self):
                return None

        service = ElevenLabsConversationalOutboundCallService()
        result = await service.initiate_call(
            _FakeDB(),
            communication_request_id=100,
            user_id="user-1",
            job_id=10,
            opportunity={"title": "Senior Python Developer", "company": "CareerOS"},
            intelligence={"job": {"title": "Senior Python Developer", "company": "CareerOS"}},
            phone_number="+15555550123",
        )

        assert result["status"] == "blocked_missing_config"
        assert result["reason"] == "missing_elevenlabs_api_key"
        assert result["elevenlabs_api_key_configured"] is False

    @pytest.mark.asyncio
    async def test_initiate_call_marks_bridge_missing_to_as_provider_payload_error(self, monkeypatch):
        from src.services.opportunity import conversational_outbound_call_service as service_mod

        monkeypatch.setattr(settings, "CALL_ALERT_DRY_RUN", False, raising=False)
        monkeypatch.setattr(settings, "OUTBOUND_CALL_DRY_RUN", False, raising=False)
        monkeypatch.setattr(settings, "ELEVENLABS_CONVAI_AGENT_ID", "agent_123", raising=False)
        monkeypatch.setattr(settings, "ELEVENLABS_CONVAI_PHONE_NUMBER_ID", "phnum_456", raising=False)
        monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "el_test", raising=False)
        monkeypatch.setattr(settings, "PIPEDREAM_WEBHOOK_URL", "https://bridge.example.test/webhook", raising=False)

        class _FakeResponse:
            status_code = 400
            text = "No 'To' number is specified"

            def json(self):
                return {"error": self.text}

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, *args, **kwargs):
                return _FakeResponse()

        class _FakeConversationRetrievalAgent:
            async def capture_session(self, *args, **kwargs):
                return None

        class _FakeDB:
            def __init__(self):
                self.objects = []

            def add(self, obj):
                self.objects.append(obj)

            async def flush(self):
                return None

        monkeypatch.setattr(service_mod.httpx, "AsyncClient", _FakeClient)
        monkeypatch.setattr(service_mod, "get_conversation_retrieval_agent", lambda: _FakeConversationRetrievalAgent())

        service = ElevenLabsConversationalOutboundCallService()

        async def _resolve_user_name(db, user_id):
            return ""

        monkeypatch.setattr(service, "_resolve_user_name", _resolve_user_name, raising=False)

        fake_db = _FakeDB()
        result = await service.initiate_call(
            fake_db,
            communication_request_id=101,
            user_id="user-1",
            job_id=10,
            opportunity={"title": "Senior Python Developer", "company": "CareerOS"},
            intelligence={"job": {"title": "Senior Python Developer", "company": "CareerOS"}},
            phone_number="+15555550123",
        )

        assert result["status"] == "failed"
        assert result["provider_status"] == "provider_payload_error"
        assert result["reason"] == "bridge_missing_to_number"
        assert result["transport"] == "webhook_bridge"
        assert any(getattr(obj, "status", None) == "FAILED" for obj in fake_db.objects)

    @pytest.mark.asyncio
    async def test_communication_orchestrator_reuses_existing_request(self):
        from src.services.opportunity import communication_orchestrator as orchestrator_mod

        orchestrator = orchestrator_mod.get_communication_orchestrator()

        existing_request = MagicMock()
        existing_request.id = 10
        existing_request.correlation_id = "corr-existing"
        existing_request.communication_status = "pending_approval"
        existing_request.communication_provider = "elevenlabs_convai"
        existing_request.channel = "VOICE_CALL"
        existing_request.communication_result = {}
        existing_request.delivery_attempts = 0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_request

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.flush.return_value = None
        mock_db.commit.return_value = None

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_db)
        ctx.__aexit__ = AsyncMock(return_value=False)

        fake_voice_service = AsyncMock()
        fake_voice_service.initiate_call.return_value = {
            "status": "started",
            "provider": "elevenlabs_convai",
            "delivery_mode": "conversation_agent",
            "call_status": "started",
            "conversation_id": "conv_123",
            "call_sid": "call_123",
            "transport": "direct_api",
            "dynamic_variables_present": True,
            "agent_id_configured": True,
            "agent_phone_number_id_configured": True,
            "elevenlabs_api_key_configured": True,
            "voice_session_id": 55,
        }

        fake_context_builder = MagicMock()
        fake_context_builder.build = AsyncMock(return_value=MagicMock(
            conversation_context={},
            context_uid="ctx-123",
        ))

        fake_outcome = MagicMock()
        fake_outcome.record_event = AsyncMock()
        fake_outcome.refresh_metrics = AsyncMock()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(orchestrator_mod, "async_session", lambda: ctx)
            mp.setattr(orchestrator_mod, "get_elevenlabs_conversational_outbound_call_service", lambda: fake_voice_service)
            mp.setattr(orchestrator_mod, "get_opportunity_conversation_context_builder", lambda: fake_context_builder)
            mp.setattr(orchestrator_mod, "get_outcome_intelligence_service", lambda: fake_outcome)
            mp.setattr(orchestrator_mod, "get_pipedream_adapter", lambda: MagicMock())

            result = await orchestrator.deliver(
                user_id="user-1",
                opportunity={"id": "opp-1", "title": "Senior Python Developer", "company": "CareerOS", "job_id": 10},
                decision="CALL",
                phone_number="+15555550123",
                communication_request_id=10,
            )

        mock_db.add.assert_not_called()
        assert result["communication_request_id"] == 10
        assert result["delivery_status"] == "started"


class TestExplainabilityAgent:
    @pytest.fixture
    def agent(self):
        return ExplainabilityAgent()

    def test_compile_basic(self, agent):
        result = asyncio.run(agent.compile(
            session_uid="s1",
            action_data={"action_id": "a1", "action_type": "notification", "confidence": 0.8},
        ))
        assert result.status == "completed"
        assert "why_happened" in result.final_explanation
        assert "evidence" in result.final_explanation
        assert "governance_verdict" in result.final_explanation

    def test_compile_with_scoring(self, agent):
        result = asyncio.run(agent.compile(
            session_uid="s1",
            action_data={"action_id": "a2", "action_type": "call"},
            scoring_context={"overall_score": 85, "priority_rank": 1},
        ))
        assert result.status == "completed"
        assert len(result.final_explanation.get("evidence", [])) == 0

    def test_singleton(self):
        a = get_explainability_agent()
        b = get_explainability_agent()
        assert a is b


class TestEventBus:
    @pytest.fixture
    def bus(self):
        return EventBus()

    def test_event_dataclass(self):
        event = Event(event_type="test", session_uid="s1", payload={"key": "val"})
        assert event.event_type == "test"
        assert event.status == "pending"
        assert len(event.event_id) > 0

    @pytest.mark.skip(reason="Requires Redis running locally")
    def test_publish_and_replay(self, bus):
        event = Event(event_type="orchestration_started", session_uid="s_test")
        msg_id = asyncio.run(bus.publish(event))
        assert msg_id is not None
        events = asyncio.run(bus.replay("s_test"))
        assert len(events) > 0
        assert events[0].event_type == "orchestration_started"

    @pytest.mark.skip(reason="Requires Redis running locally")
    def test_dead_letter(self, bus):
        event = Event(event_type="failed_action", session_uid="s_dl")
        asyncio.run(bus.dead_letter(event, "test_reason"))
        dl = asyncio.run(bus.get_dead_letters(limit=10))
        assert len(dl) > 0

    def test_singleton(self):
        a = get_event_bus()
        b = get_event_bus()
        assert a is b
