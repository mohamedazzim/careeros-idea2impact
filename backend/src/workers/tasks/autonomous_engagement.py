"""Background jobs for transcript synchronization and scheduled follow-ups."""
from src.db.session import async_session
from src.services.opportunity.elevenlabs_transcript_sync import get_elevenlabs_transcript_sync
from src.services.opportunity.followup_scheduler import get_followup_scheduler


async def sync_elevenlabs_transcripts_task(ctx, limit: int = 50):
    async with async_session() as db:
        jobs = await get_elevenlabs_transcript_sync().scan(db, limit=limit)
        await db.commit()
        return {
            "processed": len(jobs),
            "completed": sum(job.status == "COMPLETED" for job in jobs),
            "retry": sum(job.status == "RETRY" for job in jobs),
            "permanently_failed": sum(job.status == "PERMANENTLY_FAILED" for job in jobs),
        }


async def execute_due_followups_task(ctx, limit: int = 50):
    async with async_session() as db:
        tasks = await get_followup_scheduler().run_due(db, limit=limit)
        await db.commit()
        return {"processed": len(tasks), "completed": sum(task.status == "COMPLETED" for task in tasks)}
