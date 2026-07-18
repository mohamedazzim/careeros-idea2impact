"""
Task cleanup operations.
Resource cleanup for aborted or failed jobs.
"""
import logging

from src.db.redis import redis_client

logger = logging.getLogger(__name__)


async def cleanup_status_keys(resume_id: int):
    """
    Clean up Redis status keys for a resume.
    
    Args:
        resume_id: Resume ID to clean up
    """
    try:
        # Clean up status channel and key
        pattern = f"resume:status:{resume_id}*"
        # Note: In production, use SCAN instead of KEYS
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)
            logger.debug(f"Cleaned up {len(keys)} status keys for resume {resume_id}")
    except Exception as e:
        logger.warning(f"Failed to cleanup status keys for resume {resume_id}: {e}")


async def abort_job(job_id: str) -> bool:
    """
    Abort a running or queued job.
    
    Args:
        job_id: The ARQ job ID
        
    Returns:
        True if aborted, False if not found or already complete
    """
    from src.workers.arq_worker import get_arq_pool
    
    pool = await get_arq_pool()
    job = pool.job(job_id)
    
    if not job:
        return False
    
    try:
        await job.abort()
        logger.info(f"Job {job_id} aborted")
        return True
    except Exception as e:
        logger.error(f"Failed to abort job {job_id}: {e}")
        return False
