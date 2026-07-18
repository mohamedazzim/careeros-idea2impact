import pytest

from src.agents.opportunity_alert_agent import AlertState, OpportunityAlertAgent
from src.core.config import settings
from src.services.mcp.twilio_adapter import get_twilio_health
from src.services.mcp.twilio_mcp_service import TwilioMCPService
from src.services.opportunity.communication_orchestrator import ROUTING_MATRIX


@pytest.mark.asyncio
async def test_twilio_service_blocks_when_credentials_missing(monkeypatch):
    monkeypatch.delenv("MOCK_MCP", raising=False)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "", raising=False)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "", raising=False)
    monkeypatch.setattr(settings, "TWILIO_PHONE_NUMBER", "", raising=False)

    svc = TwilioMCPService()
    result = await svc.make_call(phone_number="+15555550123", audio_message="test")

    assert result["status"] == "blocked_by_credentials"
    assert result["reason"].startswith("missing_credentials")
    assert result["remote_call"] is False


def test_high_match_alert_routes_to_call():
    agent = OpportunityAlertAgent()
    decision = agent._decide_channel(92, 0.2, 0.1, "NEW", "https://apply.example", {"allowed": True})
    assert decision == "CALL"


def test_twilio_health_reports_required_env_vars():
    health = get_twilio_health()
    assert "TWILIO_ACCOUNT_SID" in health["required_env_vars"]
    assert "TWILIO_AUTH_TOKEN" in health["required_env_vars"]
    assert "TWILIO_PHONE_NUMBER" in health["required_env_vars"]


def test_voice_call_routes_to_conversational_agent_mode():
    route = ROUTING_MATRIX["VOICE_CALL"]
    assert route["mode"] == "conversation_agent"
    assert route["provider"] == "elevenlabs_convai"
