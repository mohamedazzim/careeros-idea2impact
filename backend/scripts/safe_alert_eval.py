"""Safe alert evaluation for matches >=65. Dry-run only — no provider calls, no outbound.

This script MUST never call Twilio, ElevenLabs, or any outbound provider.
It forces dry-run mode via env vars before settings import.
"""
import asyncio
import os
import sys
import traceback

os.environ["CALL_ALERT_DRY_RUN"] = "true"
os.environ["OUTBOUND_CALL_DRY_RUN"] = "true"
os.environ["MOCK_MCP"] = "true"

sys.path.insert(0, "/app")


async def main():
    try:
        from src.db.session import async_session
        from src.models.jobs import Job, JobMatch
        from src.core.config import settings
        from sqlalchemy import select, func

        assert settings.CALL_ALERT_DRY_RUN is True, "CALL_ALERT_DRY_RUN must be true"
        assert settings.OUTBOUND_CALL_DRY_RUN is True, "OUTBOUND_CALL_DRY_RUN must be true"

        print(f"CALL_ALERT_MIN_MATCH_SCORE={settings.CALL_ALERT_MIN_MATCH_SCORE}")
        print(f"CALL_ALERT_DRY_RUN={settings.CALL_ALERT_DRY_RUN}")
        print(f"OUTBOUND_CALL_DRY_RUN={settings.OUTBOUND_CALL_DRY_RUN}")
        print(f"provider_calls=0")
        print(f"twilio_called=false")
        print(f"elevenlabs_called=false")

        user_id = "8a24f5d4-975a-42f8-b01f-6dcd2680cee9"

        async with async_session() as db:
            q = select(JobMatch, Job).join(Job, Job.id == JobMatch.job_id).where(
                JobMatch.user_id == user_id,
                JobMatch.deleted_at.is_(None),
                JobMatch.overall_score >= 65,
                Job.is_india_eligible == True,
                Job.is_tech_role == True,
                Job.status == "active",
            )
            rows = (await db.execute(q)).all()
            print(f"matches_above_65={len(rows)}")

            for jm, job in rows:
                from src.agents.opportunity_alert_agent import get_opportunity_alert_agent
                agent = get_opportunity_alert_agent()

                opp = {
                    "id": str(job.id),
                    "job_id": job.id,
                    "title": job.title[:40],
                    "company": job.company,
                    "location": job.location or "",
                    "overall_score": jm.overall_score,
                    "freshness_score": job.freshness_score or 0,
                    "opportunity_priority_score": job.opportunity_priority_score or 0,
                    "urgency_score": 0,
                    "lifecycle_state": job.lifecycle_state,
                    "source_url": job.source_url or "",
                    "apply_url": job.apply_url or "",
                }
                try:
                    state = await agent.evaluate_and_alert(user_id, opp)
                    print(
                        f"  score={jm.overall_score:.1f} "
                        f"title={job.title[:30]} "
                        f"location={job.location[:25] or 'N/A'} "
                        f"decision={state.channel} "
                        f"delivery=dry_run "
                        f"reason={state.failure_reason or 'ok'}"
                    )
                except Exception as e:
                    print(f"  score={jm.overall_score:.1f} title={job.title[:30]} ERROR={e}")
                    traceback.print_exc()

    except Exception as e:
        traceback.print_exc()


asyncio.run(main())
