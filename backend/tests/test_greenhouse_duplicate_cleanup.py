from __future__ import annotations

from datetime import datetime

from scripts.cleanup_greenhouse_duplicates import (
    DuplicateJobRow,
    _group_key,
    _select_survivor,
)


def _job(
    job_id: int,
    *,
    fetched_at: datetime | None = None,
    updated_at: datetime | None = None,
    source_url: str = "https://boards.greenhouse.io/acme/jobs/123",
    apply_url: str = "https://boards.greenhouse.io/acme/jobs/123",
    company: str = "Acme",
    title: str = "Backend Engineer",
    location: str = "Bengaluru, India",
    source_job_id: str | None = None,
) -> DuplicateJobRow:
    return DuplicateJobRow(
        id=job_id,
        job_uid=f"uid-{job_id}",
        source_job_id=source_job_id,
        source_url=source_url,
        apply_url=apply_url,
        company=company,
        title=title,
        location=location,
        fetched_at=fetched_at,
        updated_at=updated_at,
    )


def test_group_key_uses_greenhouse_identity_fields() -> None:
    left = _job(1, source_job_id="111")
    right = _job(2, source_job_id="222")

    assert _group_key(left) == _group_key(right)


def test_select_survivor_prefers_newest_fetched_row() -> None:
    older = _job(1, fetched_at=datetime(2026, 6, 1), updated_at=datetime(2026, 6, 2))
    newer = _job(2, fetched_at=datetime(2026, 6, 3), updated_at=datetime(2026, 6, 2))

    assert _select_survivor([older, newer]).id == 2


def test_select_survivor_uses_updated_at_when_fetched_ties() -> None:
    older = _job(1, fetched_at=datetime(2026, 6, 3), updated_at=datetime(2026, 6, 2))
    newer = _job(2, fetched_at=datetime(2026, 6, 3), updated_at=datetime(2026, 6, 4))

    assert _select_survivor([older, newer]).id == 2


def test_select_survivor_prefers_row_with_urls_when_timestamps_tie() -> None:
    bare = _job(1, fetched_at=None, updated_at=None, source_url="", apply_url="")
    rich = _job(2)

    assert _select_survivor([bare, rich]).id == 2


def test_select_survivor_breaks_final_tie_on_smallest_id() -> None:
    left = _job(1, fetched_at=datetime(2026, 6, 3), updated_at=datetime(2026, 6, 3))
    right = _job(2, fetched_at=datetime(2026, 6, 3), updated_at=datetime(2026, 6, 3))

    assert _select_survivor([right, left]).id == 1
