"""
ARQ Worker Configuration for background job processing.
Production-grade with retry logic, DLQ, and observability.
"""
import asyncio
import logging
from typing import Dict, Any

from arq import Worker, create_pool, cron
from arq.connections import RedisSettings, ArqRedis

from src.core.config import settings
from src.db.session import async_session
from src.db.redis import redis_client
from src.observability.langsmith import traceable
from sqlalchemy.future import select

# Import tasks from modular structure
from .tasks.ingestion import process_resume_task
from .tasks.job_ingestion import jobs_ingestion_pipeline, auto_refresh_job_feeds_task, embed_fresh_jobs_task, rematch_active_users_task
from .tasks.job_matching import recalculate_all_jobs_async
from .tasks.evaluation import run_evaluation_benchmark_task
from .tasks.autonomous_engagement import sync_elevenlabs_transcripts_task, execute_due_followups_task

logger = logging.getLogger(__name__)


class WorkerSettings:
    """
    ARQ Worker configuration.
    """
    functions = [
        process_resume_task,
        jobs_ingestion_pipeline,
        recalculate_all_jobs_async,
        run_evaluation_benchmark_task,
        sync_elevenlabs_transcripts_task,
        execute_due_followups_task,
        embed_fresh_jobs_task,
        rematch_active_users_task,
    ]
    cron_jobs = [
        cron(
            sync_elevenlabs_transcripts_task,
            name="sync_elevenlabs_transcripts_cron",
            minute=None,
            second=15,
            run_at_startup=True,
            unique=True,
        ),
        cron(
            execute_due_followups_task,
            name="execute_due_followups_cron",
            minute=None,
            second=45,
            run_at_startup=True,
            unique=True,
        ),
        cron(
            auto_refresh_job_feeds_task,
            name="auto_refresh_job_feeds_cron",
            minute={0, 30},
            run_at_startup=True,
            unique=True,
        ),
    ]
    
    # Redis connection settings
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
        conn_timeout=10,
        conn_retries=5,
        conn_retry_delay=1
    )
    
    # Worker behavior
    allow_abort_jobs = True
    max_jobs = settings.WORKER_MAX_JOBS
    job_timeout = settings.WORKER_JOB_TIMEOUT
    retry_jobs = True
    
    # Queue settings
    queue_name = 'arq:queue'
    
    @staticmethod
    async def on_startup(ctx: Dict[str, Any]):
        """
        Called when worker starts.
        Initialize connections and validate environment.
        """
        logger.info("Worker starting up...", extra={
            "worker_event": "startup",
            "max_jobs": settings.WORKER_MAX_JOBS,
            "queue_name": ctx.get('queue_name', 'unknown')
        })
        
        # Validate database connectivity
        try:
            async with async_session() as db:
                result = await db.execute(select(1))
                result.scalar()
            logger.info("Database connection validated")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
        
        # Validate Redis connectivity
        try:
            await redis_client.ping()
            logger.info("Redis connection validated")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise
        
        ctx['start_time'] = asyncio.get_event_loop().time()
        logger.info("Worker startup complete")
    
    @staticmethod
    async def on_shutdown(ctx: Dict[str, Any]):
        """
        Called when worker shuts down.
        Cleanup resources.
        """
        logger.info("Worker shutting down...", extra={
            "worker_event": "shutdown"
        })
        
        # Close Redis connection
        await redis_client.close()
        
        uptime = asyncio.get_event_loop().time() - ctx.get('start_time', 0)
        logger.info(f"Worker shutdown complete. Uptime: {uptime:.2f}s")
    
    @staticmethod
    async def on_job_start(ctx: Dict[str, Any]):
        """
        Called before each job starts.
        """
        job_id = ctx.get('job_id', 'unknown')
        function = ctx.get('function', 'unknown')
        
        logger.info(f"Job started: {function}", extra={
            "job_event": "start",
            "job_id": job_id,
            "function": function,
            "attempt": ctx.get('job_try', 1)
        })
    
    @staticmethod
    async def on_job_end(ctx: Dict[str, Any]):
        """
        Called after each job completes (success or failure).
        """
        job_id = ctx.get('job_id', 'unknown')
        function = ctx.get('function', 'unknown')
        result = ctx.get('result')
        
        logger.info(f"Job completed: {function}", extra={
            "job_event": "end",
            "job_id": job_id,
            "function": function,
            "result": result,
            "attempt": ctx.get('job_try', 1),
            "success": result is not None and not isinstance(result, Exception)
        })


# Global ARQ Redis pool for job enqueueing
_arq_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    """
    Get or create ARQ Redis pool for enqueueing jobs.
    Uses connection pooling for efficiency.
    """
    global _arq_pool
    
    if _arq_pool is None:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(settings.REDIS_URL)
            _host = parsed.hostname or settings.REDIS_HOST
            _port = parsed.port or settings.REDIS_PORT
        except Exception:
            _host = settings.REDIS_HOST
            _port = settings.REDIS_PORT
        _arq_pool = await create_pool(
            RedisSettings(
                host=_host,
                port=_port,
                database=settings.REDIS_DB,
                conn_timeout=10,
                conn_retries=5,
                conn_retry_delay=1
            )
        )
        logger.info("ARQ Redis pool created")
    
    return _arq_pool


async def close_arq_pool():
    """
    Close the ARQ Redis pool.
    Call during application shutdown.
    """
    global _arq_pool
    
    if _arq_pool:
        await _arq_pool.close()
        _arq_pool = None
        logger.info("ARQ Redis pool closed")


@traceable(name="enqueue_resume_processing")
async def enqueue_resume_processing(resume_id: int, max_retries: int = None) -> str:
    """
    Enqueue a resume for background processing.
    
    Args:
        resume_id: The resume ID to process
        max_retries: Override default max retries
        
    Returns:
        Job ID string
    """
    pool = await get_arq_pool()
    
    job = await pool.enqueue_job(
        'process_resume_task',
        resume_id,
        _queue_name='arq:queue',
        _expires=3600,  # Job expires after 1 hour if not started
        _timeout=settings.WORKER_JOB_TIMEOUT
    )
    
    if job:
        logger.info(f"Resume {resume_id} enqueued for processing", extra={
            "job_id": job.job_id,
            "resume_id": resume_id,
            "queue": 'arq:queue'
        })
        return job.job_id
    else:
        raise RuntimeError(f"Failed to enqueue resume {resume_id}")


@traceable(name="enqueue_evaluation_benchmark")
async def enqueue_evaluation_benchmark(
    run_uid: str,
    user_id: str,
    benchmark_name: str = "retrieval_evaluation",
    config: Dict[str, Any] | None = None,
) -> str:
    """
    Enqueue an evaluation benchmark for worker processing.

    Returns the ARQ job ID string.
    """
    pool = await get_arq_pool()
    job = await pool.enqueue_job(
        "run_evaluation_benchmark_task",
        run_uid,
        user_id,
        benchmark_name,
        config or {},
        _queue_name="arq:queue",
        _expires=3600,
        _timeout=settings.WORKER_JOB_TIMEOUT,
    )
    if job:
        logger.info(
            "Evaluation run %s enqueued",
            run_uid,
            extra={
                "job_id": job.job_id,
                "run_uid": run_uid,
                "queue": "arq:queue",
            },
        )
        return job.job_id
    raise RuntimeError(f"Failed to enqueue evaluation benchmark {run_uid}")


@traceable(name="enqueue_job_refresh")
async def enqueue_job_refresh(session_id: int) -> str:
    """Enqueue a job matching pipeline for background processing."""
    pool = await get_arq_pool()
    job = await pool.enqueue_job(
        "recalculate_all_jobs_async",
        session_id,
        True,
        _queue_name="arq:queue",
        _expires=3600,
        _timeout=600,
    )
    if job:
        logger.info("job refresh enqueued", extra={"session_id": session_id, "job_id": job.job_id})
        return job.job_id
    raise RuntimeError(f"Failed to enqueue job refresh for session {session_id}")


@traceable(name="get_job_status")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get the status of a background job.
    
    Args:
        job_id: The ARQ job ID
        
    Returns:
        Dict with status, result, error info
    """
    # Import here to avoid circular dependencies
    from .tasks.status import get_job_status as _get_job_status
    return await _get_job_status(job_id)


@traceable(name="abort_job")
async def abort_job(job_id: str) -> bool:
    """
    Abort a running or queued job.
    
    Args:
        job_id: The ARQ job ID
        
    Returns:
        True if aborted, False if not found or already complete
    """
    # Import here to avoid circular dependencies
    from .tasks.cleanup import abort_job as _abort_job
    return await _abort_job(job_id)


# For running worker directly
if __name__ == "__main__":
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting ARQ Worker...")
    
    # Run worker
    Worker(
        functions=WorkerSettings.functions,
        redis_settings=WorkerSettings.redis_settings,
        allow_abort_jobs=WorkerSettings.allow_abort_jobs,
        max_jobs=WorkerSettings.max_jobs,
        job_timeout=WorkerSettings.job_timeout,
        retry_jobs=WorkerSettings.retry_jobs,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown,
        on_job_start=WorkerSettings.on_job_start,
        on_job_end=WorkerSettings.on_job_end,
        cron_jobs=WorkerSettings.cron_jobs,
    ).run()
