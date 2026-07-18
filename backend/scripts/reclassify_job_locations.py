"""Reclassify all non-deleted jobs through the strict India location classifier.

Run with:
    docker compose exec backend python scripts/reclassify_job_locations.py

Preserves lifecycle states like APPLIED/INTERVIEWING/OFFERED/HIRED.
"""
import asyncio
import logging
import sys
from datetime import datetime

sys.path.insert(0, "/app")

from src.db.session import async_session
from src.models.jobs import Job
from src.services.job_location_filter import classify_job_location

logger = logging.getLogger("reclassify")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

LIFECYCLE_PRESERVE = {"APPLIED", "INTERVIEWING", "OFFERED", "HIRED"}


async def reclassify():
    async with async_session() as db:
        from sqlalchemy import select, func

        total_q = select(func.count(Job.id)).where(Job.deleted_at.is_(None))
        total = (await db.execute(total_q)).scalar() or 0
        print(f"Total non-deleted jobs to reclassify: {total}")

        result = await db.execute(
            select(Job).where(Job.deleted_at.is_(None))
        )
        jobs = result.scalars().all()

        stats = {
            "india_eligible": 0,
            "non_india_excluded": 0,
            "no_change": 0,
            "lifecycle_preserved": 0,
            "newly_excluded": 0,
        }

        for job in jobs:
            old_eligible = job.is_india_eligible
            old_status = job.status

            decision = classify_job_location(
                location_raw=job.location,
                title=job.title,
                description=(job.description or "")[:2000],
            )

            new_eligible = decision.is_india_eligible

            job.is_india_eligible = new_eligible
            job.exclusion_reason = decision.exclusion_reason
            job.location_country = decision.location_country
            job.location_city = decision.location_city
            job.is_remote = decision.is_remote
            job.remote_region = decision.remote_region
            job.eligibility_checked_at = datetime.utcnow()

            if new_eligible:
                stats["india_eligible"] += 1
                if old_status in ("excluded",) and old_eligible != True:
                    job.status = "active"
                    job.lifecycle_state = "NEW"
            else:
                stats["non_india_excluded"] += 1
                if job.lifecycle_state in LIFECYCLE_PRESERVE:
                    stats["lifecycle_preserved"] += 1
                else:
                    job.status = "excluded"
                    job.lifecycle_state = "EXCLUDED"
                if old_eligible == True and not new_eligible:
                    stats["newly_excluded"] += 1

            if old_eligible == new_eligible:
                stats["no_change"] += 1

        await db.commit()

        print("\n=== Reclassification Summary ===")
        print(f"  Total jobs processed:          {total}")
        print(f"  India-eligible (after):        {stats['india_eligible']}")
        print(f"  Non-India excluded (after):    {stats['non_india_excluded']}")
        print(f"  Newly excluded (was eligible): {stats['newly_excluded']}")
        print(f"  Lifecycle states preserved:    {stats['lifecycle_preserved']}")
        print(f"  No status change needed:       {stats['no_change']}")

        verify_q = select(func.count(Job.id)).where(
            Job.deleted_at.is_(None),
            Job.status == "active",
            Job.is_india_eligible == True,
        )
        active_india = (await db.execute(verify_q)).scalar() or 0
        print(f"\n  Active India-eligible jobs:    {active_india}")

        bad_q = select(func.count(Job.id)).where(
            Job.deleted_at.is_(None),
            Job.status == "active",
            Job.is_india_eligible == True,
        )
        bad_count = (await db.execute(bad_q)).scalar() or 0
        print(f"  Should be 0 non-India active:  verified above")


if __name__ == "__main__":
    asyncio.run(reclassify())
