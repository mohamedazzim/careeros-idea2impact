"""
Reclassify all existing active jobs with tech-role and experience fields.

Run inside Docker:
  docker compose exec backend python scripts/reclassify_job_role_experience.py

Safe: only updates classification fields, does not delete jobs.
"""

import asyncio
import logging
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reclassify")

sys.path.insert(0, "/app")


async def main():
    from src.db.session import async_session
    from src.models.jobs import Job
    from src.services.job_role_filter import classify_tech_role, extract_job_experience_requirement
    from sqlalchemy import select, func

    async with async_session() as db:
        result = await db.execute(
            select(Job).where(
                Job.deleted_at.is_(None),
                Job.status.in_(["active", "excluded"]),
            )
        )
        jobs = result.scalars().all()
        total = len(jobs)

        tech_count = 0
        non_tech_count = 0
        updated = 0
        seniority_counts = {}
        experience_extracted = 0

        for job in jobs:
            tech = classify_tech_role(
                title=job.title or "",
                description=job.description or "",
                skills=job.skills_required if isinstance(job.skills_required, list) else None,
            )
            exp = extract_job_experience_requirement(
                title=job.title or "",
                description=job.description or "",
            )

            is_non_tech = not tech["is_tech_role"] and tech["confidence"] >= 0.7

            job.is_tech_role = tech["is_tech_role"]
            job.tech_role_category = tech["tech_role_category"]
            job.tech_role_confidence = tech["confidence"]
            job.role_classification_reason = tech["reason"]
            job.experience_min_years = exp["min_years"]
            job.experience_max_years = exp["max_years"]
            job.seniority_level = exp["seniority_level"]

            if is_non_tech and job.status == "active":
                job.status = "excluded"
                job.lifecycle_state = "EXCLUDED"
                job.exclusion_reason = f"non_tech_role: {tech['reason']}"
            elif not is_non_tech and job.status == "excluded" and "non_tech" in (job.exclusion_reason or ""):
                job.status = "active"
                job.lifecycle_state = "NEW"
                job.exclusion_reason = None

            if tech["is_tech_role"]:
                tech_count += 1
            else:
                non_tech_count += 1

            if exp["seniority_level"]:
                seniority_counts[exp["seniority_level"]] = seniority_counts.get(exp["seniority_level"], 0) + 1
            if exp["min_years"] is not None or exp["max_years"] is not None:
                experience_extracted += 1

            updated += 1

        await db.commit()

    logger.info("=== Reclassification Complete ===")
    logger.info("Total jobs processed: %d", total)
    logger.info("Tech jobs: %d", tech_count)
    logger.info("Non-tech excluded: %d", non_tech_count)
    logger.info("Experience extracted: %d", experience_extracted)
    logger.info("Seniority breakdown: %s", seniority_counts)


if __name__ == "__main__":
    asyncio.run(main())
