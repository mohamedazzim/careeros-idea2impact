"""Reclassify existing jobs in the database for India eligibility.

Runs the location_filter.classify_job_location() logic on every active job
and updates the India-specific classification fields.
"""
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)


async def reclassify_all_jobs():
    from src.db.session import async_session
    from src.models.jobs import Job
    from src.services.job_location_filter import classify_job_location
    from sqlalchemy import select, func

    async with async_session() as db:
        total_result = await db.execute(select(func.count(Job.id)))
        total = total_result.scalar() or 0
        print(f"Total jobs in database: {total}")

        active_result = await db.execute(
            select(Job).where(Job.deleted_at.is_(None))
        )
        jobs = list(active_result.scalars().all())
        print(f"Active jobs to reclassify: {len(jobs)}")

        india_count = 0
        non_india_count = 0
        remote_count = 0
        by_source = {}
        by_country = {}

        for job in jobs:
            decision = classify_job_location(
                location_raw=job.location,
                title=job.title,
                description=job.description,
            )
            job.location_country = decision.location_country
            job.location_region = decision.location_region
            job.location_city = decision.location_city
            job.is_remote = decision.is_remote
            job.remote_region = decision.remote_region
            job.is_india_eligible = decision.is_india_eligible
            job.exclusion_reason = decision.exclusion_reason
            job.eligibility_checked_at = job.fetched_at or job.ingested_at

            if decision.is_india_eligible:
                india_count += 1
            else:
                non_india_count += 1

            if decision.is_remote:
                remote_count += 1

            source = job.source or "unknown"
            by_source[source] = by_source.get(source, 0) + 1

            country = decision.location_country or "unknown"
            by_country[country] = by_country.get(country, 0) + 1

        await db.commit()

        print(f"\n=== RECLASSIFICATION RESULTS ===")
        print(f"India-eligible: {india_count}")
        print(f"Non-India: {non_india_count}")
        print(f"Remote jobs: {remote_count}")
        print(f"\nBy source:")
        for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"  {source}: {count}")
        print(f"\nBy country:")
        for country, count in sorted(by_country.items(), key=lambda x: -x[1]):
            print(f"  {country}: {count}")

        return {
            "total": len(jobs),
            "india_eligible": india_count,
            "non_india": non_india_count,
            "remote": remote_count,
            "by_source": by_source,
            "by_country": by_country,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(reclassify_all_jobs())
    print(f"\nDone. Result: {result}")
