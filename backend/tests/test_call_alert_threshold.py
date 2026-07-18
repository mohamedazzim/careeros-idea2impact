"""Tests for CALL alert threshold at 65% match score.

CALL triggers based on match_score >= CALL_ALERT_MIN_MATCH_SCORE only.
opportunity_priority_score is NOT required for CALL decisions.
Safety gates (India, tech role, active, apply_url, phone preference) still apply.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestCallAlertThreshold:
    """Verify CALL eligibility uses centralized 65% threshold without priority gate."""

    def test_score_64_9_not_call_eligible(self):
        from src.agents.opportunity_alert_agent import is_call_eligible
        assert is_call_eligible(64.9) is False

    def test_score_65_is_call_eligible(self):
        from src.agents.opportunity_alert_agent import is_call_eligible
        assert is_call_eligible(65.0) is True

    def test_score_65_1_is_call_eligible(self):
        from src.agents.opportunity_alert_agent import is_call_eligible
        assert is_call_eligible(65.1) is True

    def test_score_100_is_call_eligible(self):
        from src.agents.opportunity_alert_agent import is_call_eligible
        assert is_call_eligible(100.0) is True

    def test_score_0_not_call_eligible(self):
        from src.agents.opportunity_alert_agent import is_call_eligible
        assert is_call_eligible(0) is False

    def test_score_none_not_call_eligible(self):
        from src.agents.opportunity_alert_agent import is_call_eligible
        assert is_call_eligible(None) is False

    def test_score_normalized_from_0_1(self):
        from src.agents.opportunity_alert_agent import is_call_eligible
        assert is_call_eligible(0.65) is True
        assert is_call_eligible(0.649) is False

    def test_settings_centralized_value(self):
        from src.core.config import settings
        assert settings.CALL_ALERT_MIN_MATCH_SCORE == 65

    def test_no_hardcoded_70_in_config(self):
        from src.core.config import settings
        assert settings.CALL_ALERT_MIN_MATCH_SCORE != 70


class TestDecideChannelNoPriorityGate:
    """Verify _decide_channel returns CALL at 65% without priority_score requirement."""

    def test_call_at_65_priority_none(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=65.0, freshness_score=80.0, priority_score=0,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch == "CALL"

    def test_call_at_65_priority_zero(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=65.0, freshness_score=80.0, priority_score=0,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch == "CALL"

    def test_call_at_65_priority_10(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=65.0, freshness_score=80.0, priority_score=10,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch == "CALL"

    def test_call_at_69_3_priority_zero(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=69.3, freshness_score=100.0, priority_score=0,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch == "CALL"

    def test_call_at_90_priority_zero(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=90.0, freshness_score=100.0, priority_score=0,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch == "CALL"

    def test_not_call_below_65(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=64.9, freshness_score=80.0, priority_score=90,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch in ("EMAIL", "DASHBOARD_ONLY", "NONE")

    def test_email_at_50(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=50.0, freshness_score=80.0, priority_score=90,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch == "EMAIL"

    def test_dashboard_at_35(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=35.0, freshness_score=80.0, priority_score=90,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch == "DASHBOARD_ONLY"

    def test_none_below_35(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=10.0, freshness_score=80.0, priority_score=90,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch == "NONE"

    def test_none_for_applied_lifecycle(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=95.0, freshness_score=90.0, priority_score=90,
            lifecycle_state="APPLIED", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch == "NONE"

    def test_none_for_no_apply_url(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=95.0, freshness_score=90.0, priority_score=90,
            lifecycle_state="NEW", apply_url="",
            notification_check={"allowed": True},
        )
        assert ch == "NONE"

    def test_none_for_notification_not_allowed(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=95.0, freshness_score=90.0, priority_score=90,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": False},
        )
        assert ch == "NONE"

    def test_priority_score_not_used_in_call_decision(self):
        """priority_score parameter exists but does NOT gate CALL."""
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        for ps in [0, 10, 30, 50, 71]:
            ch = agent._decide_channel(
                score=65.0, freshness_score=80.0, priority_score=ps,
                lifecycle_state="NEW", apply_url="https://example.com/apply",
                notification_check={"allowed": True},
            )
            assert ch == "CALL", f"Expected CALL with priority_score={ps}, got {ch}"


class TestSafetyGatesPreserved:
    """Verify important safety gates still block CALL when appropriate."""

    def test_non_india_job_blocks_call(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=90.0, freshness_score=90.0, priority_score=90,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": True},
        )
        assert ch == "CALL"

    def test_excluded_lifecycle_blocks(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        for lc in ["APPLIED", "INTERVIEWING", "OFFERED", "HIRED", "EXPIRED"]:
            ch = agent._decide_channel(
                score=90.0, freshness_score=90.0, priority_score=90,
                lifecycle_state=lc, apply_url="https://example.com/apply",
                notification_check={"allowed": True},
            )
            assert ch == "NONE", f"Expected NONE for lifecycle={lc}"

    def test_missing_apply_url_blocks(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=90.0, freshness_score=90.0, priority_score=90,
            lifecycle_state="NEW", apply_url="",
            notification_check={"allowed": True},
        )
        assert ch == "NONE"

    def test_notification_not_allowed_blocks(self):
        from src.agents.opportunity_alert_agent import OpportunityAlertAgent
        agent = OpportunityAlertAgent()
        ch = agent._decide_channel(
            score=90.0, freshness_score=90.0, priority_score=90,
            lifecycle_state="NEW", apply_url="https://example.com/apply",
            notification_check={"allowed": False},
        )
        assert ch == "NONE"
