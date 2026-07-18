"""Tests for MCP Router, Governance, and Observability."""

import pytest
from unittest.mock import patch, MagicMock
from src.services.mcp.mcp_router import MCPRouter, get_mcp_router, TOOL_REGISTRY
from src.services.mcp.mcp_governance import MCPGovernance, get_mcp_governance
from src.services.mcp.mcp_observability import MCPObservability, get_mcp_observability


class TestMCPRouter:
    @pytest.fixture
    def router(self):
        return MCPRouter()

    def test_tool_registry_maps_correctly(self):
        assert TOOL_REGISTRY["generate_audio"] == "elevenlabs"
        assert TOOL_REGISTRY["make_call"] == "twilio"
        assert TOOL_REGISTRY["send_sms"] == "twilio"

    def test_resolve_server_known(self, router):
        assert router._resolve_server("generate_audio") == "elevenlabs"
        assert router._resolve_server("make_call") == "twilio"

    def test_resolve_server_unknown(self, router):
        assert router._resolve_server("nonexistent") == "unknown"

    def test_available_tools(self, router):
        tools = router.available_tools()
        assert len(tools) >= 4
        assert any(t["tool"] == "generate_audio" for t in tools)
        assert any(t["tool"] == "make_call" for t in tools)

    def test_dispatch_unknown_server(self, router):
        import asyncio
        result = asyncio.run(router.dispatch(
            tool_name="nonexistent",
            arguments={},
            session_uid="test",
        ))
        assert result["status"] in ("failed", "rejected")
        assert "unknown" in result.get("reason", "") or "unknown" in result.get("error", "")

    def test_dispatch_returns_selection_reason(self, router):
        import asyncio
        result = asyncio.run(router.dispatch(
            tool_name="send_sms",
            arguments={"phone_number": "+1", "message": "test"},
            session_uid="s1",
        ))
        assert "selection_reason" in result

    def test_singleton(self):
        a = get_mcp_router()
        b = get_mcp_router()
        assert a is b


class TestMCPGovernance:
    @pytest.fixture
    def gov(self):
        return MCPGovernance()

    def test_validate_empty_tool_name(self, gov):
        import asyncio
        result = asyncio.run(gov.validate_call("", {}, "", ""))
        assert result["allowed"] is False
        assert "empty_tool_name" in result["reason"]

    def test_validate_missing_phone(self, gov):
        import asyncio
        result = asyncio.run(gov.validate_call("make_call", {}, "s1", "k1"))
        assert result["allowed"] is False
        assert "missing_phone" in result["reason"]

    def test_validate_missing_job_title(self, gov):
        import asyncio
        result = asyncio.run(gov.validate_call("generate_audio", {}, "s1", "k1"))
        assert result["allowed"] is False
        assert "missing_job_title" in result["reason"]

    def test_validate_valid_call(self, gov):
        import asyncio
        result = asyncio.run(gov.validate_call("make_call", {"phone_number": "+1", "audio_message": "test"}, "s1", "k1"))
        assert result["allowed"] is True

    def test_validate_valid_audio(self, gov):
        import asyncio
        result = asyncio.run(gov.validate_call("generate_audio", {"job_title": "Engineer"}, "s1", "k1"))
        assert result["allowed"] is True

    def test_idempotency_key_generation(self, gov):
        key = gov.generate_idempotency_key("s1", "make_call", "opp_1")
        assert "s1" in key
        assert "make_call" in key
        assert "opp_1" in key

    def test_invalid_arguments_type(self, gov):
        import asyncio
        result = asyncio.run(gov.validate_call("test", "not_a_dict", "s1", "k1"))
        assert result["allowed"] is False

    def test_singleton(self):
        a = get_mcp_governance()
        b = get_mcp_governance()
        assert a is b


class TestMCPObservability:
    @pytest.fixture
    def obs(self):
        return MCPObservability()

    def test_record_execution(self, obs):
        obs.record_execution("test_tool", "test_server", "success", 100)

    def test_record_failure(self, obs):
        obs.record_failure("test_tool", "timeout")

    def test_record_retry(self, obs):
        obs.record_retry("test_tool", 2)

    def test_record_call(self, obs):
        obs.record_call("test_tool", "success", 50)

    def test_singleton(self):
        a = get_mcp_observability()
        b = get_mcp_observability()
        assert a is b
