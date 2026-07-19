from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


@pytest.mark.asyncio
async def test_start_refresh_reuses_recent_matching_session(monkeypatch):
    from src.services.job_refresh import JobRefreshService

    monkeypatch.setattr("src.services.job_refresh.settings.JOB_REFRESH_COOLDOWN_SECONDS", 120)
    existing = SimpleNamespace(
        id=123,
        user_id="user-1",
        updated_at=datetime.now() - timedelta(seconds=30),
        metadata_={
            "resume_doc_uid": "resume-1",
            "preferences": {"target_role": "Backend Engineer"},
        },
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_ScalarResult(existing)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
        add=lambda session: None,
    )

    result = await JobRefreshService().start_refresh(
        db,  # type: ignore[arg-type]
        user_id="user-1",
        resume_doc_uid="resume-1",
        resume_profile={"skills": ["Python"]},
        preferences={"target_role": "Backend Engineer"},
    )

    assert result is existing
    assert result.metadata_["reused_existing_refresh"] is True
    assert result.metadata_["next_refresh_at"]
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(existing)


@pytest.mark.asyncio
async def test_start_refresh_marks_new_session_as_not_reused():
    from src.services.job_refresh import JobRefreshService

    added = []
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_ScalarResult(None)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
        add=lambda session: added.append(session),
    )

    result = await JobRefreshService().start_refresh(
        db,  # type: ignore[arg-type]
        user_id="user-1",
        resume_doc_uid="resume-1",
        resume_profile={"skills": ["Python"], "content": "private resume text"},
        preferences={"target_role": "Backend Engineer"},
    )

    assert added == [result]
    assert result.metadata_["reused_existing_refresh"] is False
    assert result.metadata_["next_refresh_at"] is None
    assert "content" not in result.metadata_["resume"]
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(result)
