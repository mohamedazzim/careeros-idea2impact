"""Seed one fictional job for the public CareerOS demo flow.

This script is opt-in and intended only for local or disposable hackathon
environments. It never runs during application startup.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from src.db.session import async_session
from src.models.jobs import Job


SOURCE_JOB_ID = "synthetic-hackathon-ai-platform-engineer"


async def main() -> None:
    async with async_session() as db:
        existing = await db.scalar(
            select(Job).where(Job.source_job_id == SOURCE_JOB_ID)
        )
        if existing:
            print(f"Synthetic demo job already present (id={existing.id}).")
            return

        now = datetime.now(UTC).replace(tzinfo=None)
        job = Job(
            job_uid="synthetic-demo-ai-platform-engineer",
            title="AI Platform Engineer",
            company="Northstar Example Labs",
            location="Bengaluru, India (hybrid)",
            description=(
                "Build typed asynchronous Python and FastAPI services backed by "
                "PostgreSQL, Redis, and Qdrant. Design citation-aware RAG pipelines, "
                "ship Docker-based services, and collaborate with React and "
                "TypeScript teams. Kubernetes and cloud reliability are preferred."
            ),
            source="synthetic_demo",
            source_provider="synthetic_demo",
            source_job_id=SOURCE_JOB_ID,
            source_url="https://example.com/jobs/ai-platform-engineer",
            apply_url="https://example.com/jobs/ai-platform-engineer/apply",
            posted_date=now,
            fetched_at=now,
            original_provider_metadata={"synthetic": True, "public_demo": True},
            freshness_score=100.0,
            freshness_bucket="fresh",
            provider_quality_score=100.0,
            salary_quality_score=100.0,
            apply_url_valid=True,
            opportunity_priority_score=85.0,
            lifecycle_state="NEW",
            salary_range="INR 24-32 lakh per year",
            skills_required=[
                "Python",
                "FastAPI",
                "PostgreSQL",
                "Redis",
                "Qdrant",
                "Docker",
                "React",
                "TypeScript",
                "Kubernetes",
            ],
            status="active",
            ingested_at=now,
            location_country="IN",
            location_region="Karnataka",
            location_city="Bengaluru",
            is_remote=False,
            is_india_eligible=True,
            eligibility_checked_at=now,
            ingestion_run_id="synthetic-public-demo",
            is_tech_role=True,
            tech_role_category="software_engineering",
            tech_role_confidence=1.0,
            role_classification_reason="Explicit fictional AI platform engineering role",
            experience_min_years=4.0,
            experience_max_years=7.0,
            seniority_level="mid",
            experience_filter_status="eligible",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        print(f"Seeded synthetic demo job (id={job.id}).")


if __name__ == "__main__":
    asyncio.run(main())
