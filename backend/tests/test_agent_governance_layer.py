"""Tests for Phase 5 agent governance enforcement — recursion, autonomous caps, confidence thresholds."""

import pytest
from src.governance.agent_governance import AgentGovernance, get_agent_governance


class TestAgentGovernance:
    @pytest.fixture
    def gov(self):
        return AgentGovernance()

    def test_initial_limits(self, gov):
        limits = gov.get_limits()
        assert limits["max_recursion_depth"] == 3
        assert limits["max_autonomous_actions"] == 5
        assert limits["min_confidence"] == 0.75

    def test_check_recursion_under_limit(self, gov):
        assert gov.check_recursion(0) is True
        assert gov.check_recursion(1) is True
        assert gov.check_recursion(2) is True

    def test_check_recursion_at_limit(self, gov):
        assert gov.check_recursion(3) is False

    def test_check_recursion_over_limit(self, gov):
        assert gov.check_recursion(5) is False
        assert gov.check_recursion(100) is False

    def test_check_autonomous_under_cap(self, gov):
        assert gov.check_autonomous_cap(0) is True
        assert gov.check_autonomous_cap(3) is True
        assert gov.check_autonomous_cap(4) is True

    def test_check_autonomous_at_cap(self, gov):
        assert gov.check_autonomous_cap(5) is False

    def test_check_autonomous_over_cap(self, gov):
        assert gov.check_autonomous_cap(10) is False

    def test_check_confidence_above_threshold(self, gov):
        assert gov.check_confidence(0.75) is True
        assert gov.check_confidence(0.85) is True
        assert gov.check_confidence(0.99) is True

    def test_check_confidence_below_threshold(self, gov):
        assert gov.check_confidence(0.74) is False
        assert gov.check_confidence(0.5) is False
        assert gov.check_confidence(0.0) is False

    def test_pre_action_allows_valid(self, gov):
        import asyncio
        result = asyncio.run(gov.pre_action_check(
            action_type="notification",
            confidence=0.85,
            recursion_depth=1,
            autonomous_count=2,
            session_uid="s1",
        ))
        assert result["allowed"] is True
        assert result["verdict"] == "passed"
        assert result["violations"] == []

    def test_pre_action_blocks_recursion(self, gov):
        import asyncio
        result = asyncio.run(gov.pre_action_check(
            action_type="notification",
            confidence=0.85,
            recursion_depth=5,
            autonomous_count=1,
            session_uid="s1",
        ))
        assert result["allowed"] is False
        assert "recursion_depth_exceeded" in result["violations"]

    def test_pre_action_blocks_autonomous_cap(self, gov):
        import asyncio
        result = asyncio.run(gov.pre_action_check(
            action_type="notification",
            confidence=0.85,
            recursion_depth=0,
            autonomous_count=7,
            session_uid="s1",
        ))
        assert result["allowed"] is False
        assert "autonomous_cap_exceeded" in result["violations"]

    def test_pre_action_blocks_low_confidence(self, gov):
        import asyncio
        result = asyncio.run(gov.pre_action_check(
            action_type="call",
            confidence=0.3,
            recursion_depth=0,
            autonomous_count=0,
            session_uid="s1",
        ))
        assert result["allowed"] is False
        assert "low_confidence" in result["violations"]

    def test_pre_action_multiple_violations(self, gov):
        import asyncio
        result = asyncio.run(gov.pre_action_check(
            action_type="notification",
            confidence=0.2,
            recursion_depth=10,
            autonomous_count=10,
            session_uid="s1",
        ))
        assert result["allowed"] is False
        assert len(result["violations"]) >= 2

    def test_limits_are_configurable(self, gov):
        gov.max_recursion = 10
        gov.max_autonomous = 20
        gov.min_confidence = 0.4
        assert gov.check_recursion(9) is True
        assert gov.check_recursion(10) is False
        assert gov.check_autonomous_cap(19) is True
        assert gov.check_confidence(0.5) is True

    def test_singleton(self):
        a = get_agent_governance()
        b = get_agent_governance()
        assert a is b
