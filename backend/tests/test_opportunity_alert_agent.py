from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.opportunity_alert import OpportunityAlertRequest
from src.services.opportunity_alert_agent import (
    CALL_CANDIDATE,
    CALL_CANDIDATE_HIGH_PRIORITY,
    IGNORE_OPPORTUNITY,
    STORE_NOTIFICATION,
    OpportunityAlertAgentService,
    OpportunityAlertDecisionEngine,
)


@pytest.mark.parametrize(
    ("score", "hours", "expected"),
    [
        (92, 72, CALL_CANDIDATE_HIGH_PRIORITY),
        (100, 1, CALL_CANDIDATE_HIGH_PRIORITY),
        (91, 32, CALL_CANDIDATE),
        (85, 10, CALL_CANDIDATE),
        (91, 33, STORE_NOTIFICATION),
        (92, 73, STORE_NOTIFICATION),
        (70, 1, STORE_NOTIFICATION),
        (69.99, 1, IGNORE_OPPORTUNITY),
    ],
)
def test_decision_boundaries(score, hours, expected):
    assert OpportunityAlertDecisionEngine.decide(score, hours).action == expected


def test_future_posting_is_clamped_to_zero_hours():
    future = datetime.now(timezone.utc) + timedelta(hours=3)
    assert OpportunityAlertAgentService._hours_since(future) == 0.0


def test_extracts_nested_call_sid():
    assert OpportunityAlertAgentService._extract_call_sid({"body": {"callSid": "CA123"}}) == "CA123"


def test_request_rejects_invalid_score():
    with pytest.raises(ValueError):
        OpportunityAlertRequest(
            candidate_id="candidate-1",
            phone_number="+12025550125",
            job_title="Engineer",
            company="CareerOS",
            match_score=101,
            job_posted_at=datetime.now(timezone.utc),
            application_url="https://example.com/jobs/1",
        )


class FakePipedream:
    def __init__(self):
        self.payload = None

    async def send(self, payload):
        self.payload = payload
        return "delivered", {"body": {"call_sid": "CA-test"}}


class FakeDb:
    def __init__(self):
        self.record = None

    def add(self, record):
        self.record = record

    async def commit(self):
        return None

    async def refresh(self, record):
        record.id = 42


class FakeActionResult:
    provider_status = "success"
    delivery_status = "pending_approval"
    reason = "routed_via_alert_action_service"


@pytest.mark.asyncio
async def test_high_priority_call_dispatches_webhook_and_persists():
    db = FakeDb()
    request = OpportunityAlertRequest(
        candidate_id="candidate-1",
        phone_number="+12025550125",
        job_title="AI Engineer",
        company="CareerOS",
        match_score=95,
        job_posted_at=datetime.now(timezone.utc) - timedelta(hours=12),
        application_url="https://example.com/jobs/1",
    )

    mock_action_service = AsyncMock()
    mock_action_service.process_decision.return_value = FakeActionResult()

    with patch(
        "src.services.opportunity.alert_action_service.get_alert_action_service",
        return_value=mock_action_service,
    ):
        result = await OpportunityAlertAgentService().evaluate(request, db)

    assert result.action == CALL_CANDIDATE_HIGH_PRIORITY
    assert result.called is True
    assert mock_action_service.process_decision.called
