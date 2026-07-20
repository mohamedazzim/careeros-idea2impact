"""
Job ingestion background task.
Fetches jobs from all providers, normalizes, deduplicates, stores in PostgreSQL,
and triggers embedding in Qdrant.
"""
import logging
from typing import Any, Dict

from src.core.config import settings
from src.observability.langsmith import traceable

logger = logging.getLogger(__name__)


@traceable(name="jobs_ingestion_pipeline")
async def jobs_ingestion_pipeline(ctx: Dict[str, Any], session_uid: str = None) -> Dict[str, Any]:
    """
    Background task to fetch jobs from all 6 providers and ingest into PostgreSQL + Qdrant.

    Args:
        ctx: ARQ context with job metadata
        session_uid: Optional session identifier for tracing

    Returns:
        Dict with found, added, embedded counts per source
    """
    job_id = ctx.get('job_id', 'unknown')
    job_try = ctx.get('job_try', 1)

    logger.info("Starting job ingestion pipeline", extra={
        "task": "jobs_ingestion_pipeline",
        "job_id": job_id,
        "attempt": job_try,
        "session_uid": session_uid,
    })

    try:
        from src.services.jobs import get_job_ingestion_engine
        engine = get_job_ingestion_engine()

        # Legacy/general ingestion jobs should not spend paid TheirStack credits.
        # TheirStack is reserved for the explicit Jobs page refresh pipeline.
        result = await engine.sync_jobs(admin_initiated=False)

        logger.info("Job ingestion completed", extra={
            "task": "jobs_ingestion_pipeline",
            "found": result["found"],
            "added": result["added"],
            "errors": result["errors"],
        })

        # If we added new jobs, trigger embedding
        if result["added"] > 0:
            try:
                embed_result = await engine.embed_jobs_batch(limit=200)
                result["embedded"] = embed_result["embedded"]
                logger.info("Job embedding completed", extra={
                    "embedded": embed_result["embedded"],
                    "total": embed_result["total_jobs"],
                })
            except Exception as e:
                logger.warning(f"Job embedding failed (non-critical): {e}")
                result["embedded"] = 0

        return result

    except Exception as e:
        logger.exception(f"Job ingestion pipeline failed: {e}")
        return {"found": 0, "added": 0, "errors": 1, "error_message": str(e)}


@traceable(name="auto_refresh_job_feeds_task")
async def auto_refresh_job_feeds_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cron-driven automatic job feed refresh — lightweight version.

    Only syncs providers and enqueues embedding + rematch as separate tasks.
    Each sub-task runs in its own ARQ job with its own timeout, preventing
    the 300s ARQ job_timeout from killing the pipeline mid-embedding.
    """
    job_id = ctx.get("job_id", "unknown")

    if not settings.JOB_AUTO_REFRESH_ENABLED:
        logger.debug("Auto-refresh disabled via config", extra={"task": "auto_refresh"})
        return {"status": "skipped", "reason": "disabled"}

    logger.info("Auto-refresh starting", extra={
        "task": "auto_refresh_job_feeds",
        "job_id": job_id,
    })

    result: Dict[str, Any] = {
        "found": 0,
        "added": 0,
        "updated": 0,
        "errors": 0,
        "embed_enqueued": False,
        "rematch_enqueued": False,
    }

    try:
        from src.services.jobs import get_job_ingestion_engine
        engine = get_job_ingestion_engine()

        # Phase 1 — Provider ingestion (completes quickly, <60s)
        sync = await engine.sync_jobs(admin_initiated=False)
        result["found"] = sync.get("found", 0)
        result["added"] = sync.get("added", 0)
        result["updated"] = sync.get("updated", 0)
        result["errors"] = sync.get("errors", 0)

        from src.workers.arq_worker import get_arq_pool
        pool = await get_arq_pool()

        # Phase 2 — Enqueue embedding as separate task (non-blocking)
        if result["added"] > 0:
            try:
                await pool.enqueue_job(
                    "embed_fresh_jobs_task",
                    _queue_name="arq:queue",
                    _expires=3600,
                    _timeout=600,
                )
                result["embed_enqueued"] = True
                logger.info("Enqueued embed_fresh_jobs_task")
            except Exception as exc:
                logger.warning("Failed to enqueue embed task: %s", exc)

        # Phase 3 — Enqueue rematch as separate task (non-blocking)
        try:
            await pool.enqueue_job(
                "rematch_active_users_task",
                _queue_name="arq:queue",
                _expires=3600,
                _timeout=300,
            )
            result["rematch_enqueued"] = True
            logger.info("Enqueued rematch_active_users_task")
        except Exception as exc:
            logger.warning("Failed to enqueue rematch task: %s", exc)

        logger.info("Auto-refresh completed", extra={
            "task": "auto_refresh_job_feeds",
            **result,
        })
        return result

    except Exception as exc:
        logger.exception("Auto-refresh job feeds failed: %s", exc)
        result["errors"] += 1
        result["error_message"] = str(exc)[:256]
        return result


@traceable(name="embed_fresh_jobs_task")
async def embed_fresh_jobs_task(ctx: Dict[str, Any], limit: int | None = None) -> Dict[str, Any]:
    """
    Embed recently ingested jobs into Qdrant in small configurable batches.

    Runs as a separate ARQ job from provider ingestion to avoid the 300s timeout.
    Batch size is configurable via JOB_AUTO_REFRESH_EMBED_BATCH_SIZE.
    """
    batch_size = limit or settings.JOB_AUTO_REFRESH_EMBED_BATCH_SIZE
    logger.info("Embed task starting", extra={
        "task": "embed_fresh_jobs_task",
        "batch_size": batch_size,
    })

    try:
        from src.services.jobs import get_job_ingestion_engine
        engine = get_job_ingestion_engine()

        embed = await engine.embed_jobs_batch(limit=batch_size)
        result = {
            "embedded": embed.get("embedded", 0),
            "total_jobs": embed.get("total_jobs", 0),
            "batch_size": batch_size,
        }

        logger.info("Embed task completed", extra={
            "task": "embed_fresh_jobs_task",
            **result,
        })
        return result

    except Exception as exc:
        logger.exception("Embed task failed: %s", exc)
        return {"embedded": 0, "error": str(exc)[:256]}


@traceable(name="rematch_active_users_task")
async def rematch_active_users_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find active users with completed sessions and enqueue re-matching.

    Runs as a separate ARQ job so it executes after embedding completes
    (enqueued by auto_refresh_job_feeds_task).
    """
    logger.info("Rematch task starting", extra={"task": "rematch_active_users_task"})

    try:
        enqueued = await _rematch_active_users()
        result = {"active_users": enqueued, "status": "completed"}

        logger.info("Rematch task completed", extra={
            "task": "rematch_active_users_task",
            **result,
        })
        return result

    except Exception as exc:
        logger.exception("Rematch task failed: %s", exc)
        return {"active_users": 0, "status": "failed", "error": str(exc)[:256]}


async def _rematch_active_users() -> int:
    """
    Enqueue a re-match for every user who has an active orchestration
    session with a resume_doc_uid.

    A Redis dedup lock prevents overlapping re-match runs.
    Returns the number of users enqueued.
    """
    try:
        from src.db.redis import redis_client
        from src.db.session import async_session
        from src.models.orchestration import OrchestrationSession
        from src.workers.arq_worker import get_arq_pool
        from sqlalchemy import distinct, select

        lock_key = "arq:auto_refresh:rematch_lock"
        if await redis_client.exists(lock_key):
            logger.debug("Re-match already in progress, skipping")
            return 0
        await redis_client.set(lock_key, "1", ex=600)

        async with async_session() as db:
            rows = await db.execute(
                select(distinct(OrchestrationSession.user_id)).where(
                    OrchestrationSession.status == "completed",
                ).limit(50)
            )
            user_ids = [r[0] for r in rows.all()]

        if not user_ids:
            await redis_client.delete(lock_key)
            return 0

        pool = await get_arq_pool()
        enqueued = 0

        async with async_session() as db:
            for uid in user_ids:
                try:
                    res = await db.execute(
                        select(OrchestrationSession.id).where(
                            OrchestrationSession.user_id == uid,
                            OrchestrationSession.status == "completed",
                        ).order_by(OrchestrationSession.updated_at.desc()).limit(1)
                    )
                    sid = res.scalar_one_or_none()
                    if sid:
                        await pool.enqueue_job(
                            "recalculate_all_jobs_async",
                            sid,
                            _queue_name="arq:queue",
                            _expires=3600,
                            _timeout=600,
                        )
                        enqueued += 1
                except Exception as exc:
                    logger.warning("Failed to enqueue re-match for user %s: %s", uid, exc)

        await redis_client.delete(lock_key)
        logger.info("Enqueued re-match for %d users", enqueued)
        return enqueued

    except Exception as exc:
        logger.warning("Re-match orchestration failed (non-critical): %s", exc)
        return 0
