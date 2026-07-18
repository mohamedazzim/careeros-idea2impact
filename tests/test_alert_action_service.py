"""Minimal tests for AlertActionService safety model.

Verifies that CALL/EMAIL decisions create pending approvals (no direct delivery),
DASHBOARD_ONLY creates dashboard records, and IGNORE/NONE produce no outbound action.

All DB tests share a single event loop to avoid asyncpg pool binding issues.
"""

from __future__ import annotations

import asyncio
import uuid
import pytest


_shared_loop: asyncio.AbstractEventLoop | None = None


def _get_loop():
    global _shared_loop
    if _shared_loop is None or _shared_loop.is_closed():
        _shared_loop = asyncio.new_event_loop()
    return _shared_loop


def _run(coro):
    loop = _get_loop()
    return loop.run_until_complete(coro)


async def _create_test_job(user_id: str, title: str) -> int:
    """Insert a real job row so FK constraints are satisfied."""
    from src.db.session import async_session
    from src.models.jobs import Job

    async with async_session() as db:
        job = Job(
            title=title,
            company="TestCo",
            source="test",
            source_url=f"https://example.com/{uuid.uuid4().hex[:8]}",
            lifecycle_state="NEW",
            status="active",
            created_by=user_id,
        )
        db.add(job)
        await db.flush()
        job_id = job.id
        await db.commit()
        return job_id


class TestAlertActionServiceSafety:
    """Core safety matrix tests for AlertActionService."""

    def test_ignore_no_outbound(self):
        from src.services.opportunity.alert_action_service import AlertActionService

        svc = AlertActionService()
        result = _run(svc.process_decision(
            user_id="test-user-ignore",
            job_id=0,
            opportunity={"id": "opp-ignore"},
            decision="IGNORE",
            decision_reason="below threshold",
            dry_run=False,
        ))
        assert result.decision == "IGNORE"
        assert result.delivery_status == "suppressed"
        assert result.approval_uid is None

    def test_none_no_outbound(self):
        from src.services.opportunity.alert_action_service import AlertActionService

        svc = AlertActionService()
        result = _run(svc.process_decision(
            user_id="test-user-none",
            job_id=0,
            opportunity={"id": "opp-none"},
            decision="NONE",
            decision_reason="no action",
            dry_run=False,
        ))
        assert result.decision == "NONE"
        assert result.delivery_status == "suppressed"
        assert result.approval_uid is None

    def test_call_creates_pending_approval(self):
        from src.services.opportunity.alert_action_service import AlertActionService

        job_id = _run(_create_test_job("test-user-call", "Software Engineer"))
        svc = AlertActionService()
        result = _run(svc.process_decision(
            user_id="test-user-call",
            job_id=job_id,
            opportunity={
                "id": "opp-call",
                "title": "Software Engineer",
                "company": "Acme Corp",
                "overall_score": 97.5,
            },
            decision="CALL",
            decision_reason="high match",
            decision_scores={"match_score": 97.5},
            decision_confidence=0.9,
            dry_run=False,
            phone_number="+15550000000",
        ))
        assert result.decision == "CALL"
        assert result.delivery_status == "pending_approval"
        assert result.approval_uid is not None

    def test_email_creates_pending_approval(self):
        from src.services.opportunity.alert_action_service import AlertActionService

        job_id = _run(_create_test_job("test-user-email", "Data Scientist"))
        svc = AlertActionService()
        result = _run(svc.process_decision(
            user_id="test-user-email",
            job_id=job_id,
            opportunity={
                "id": "opp-email",
                "title": "Data Scientist",
                "company": "DataCo",
                "overall_score": 92.0,
            },
            decision="EMAIL",
            decision_reason="strong match",
            decision_confidence=0.8,
            dry_run=False,
        ))
        assert result.decision == "EMAIL"
        assert result.delivery_status == "pending_approval"
        assert result.approval_uid is not None

    def test_dashboard_only_creates_dashboard_record(self):
        from src.services.opportunity.alert_action_service import AlertActionService

        job_id = _run(_create_test_job("test-user-dash", "Product Manager"))
        svc = AlertActionService()
        result = _run(svc.process_decision(
            user_id="test-user-dash",
            job_id=job_id,
            opportunity={
                "id": "opp-dash",
                "title": "Product Manager",
                "company": "PMCo",
                "overall_score": 78.0,
            },
            decision="DASHBOARD_ONLY",
            decision_reason="moderate match",
            decision_confidence=0.6,
            dry_run=False,
        ))
        assert result.decision == "DASHBOARD_ONLY"
        assert result.delivery_status == "delivered_to_dashboard"
        assert result.approval_uid is None

    def test_dry_run_does_not_create_approval(self):
        from src.services.opportunity.alert_action_service import AlertActionService

        job_id = _run(_create_test_job("test-user-dry", "SRE"))
        svc = AlertActionService()
        result = _run(svc.process_decision(
            user_id="test-user-dry",
            job_id=job_id,
            opportunity={
                "id": "opp-dry",
                "title": "SRE",
                "company": "OpsCo",
                "overall_score": 95.0,
            },
            decision="CALL",
            decision_reason="test",
            decision_confidence=0.9,
            dry_run=True,
        ))
        assert result.delivery_status == "dry_run"
        assert result.approval_uid is None
