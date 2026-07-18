"""
Task status queries.
Functions for querying job status from the queue.
"""
import logging
from typing import Dict, Any

from arq.jobs import JobStatus

logger = logging.getLogger(__name__)


async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get the status of a background job.
    
    Args:
        job_id: The ARQ job ID
        
    Returns:
        Dict with status, result, error info, and timestamps
    """
    from src.workers.arq_worker import get_arq_pool
    pool = await get_arq_pool()
    job = pool.job(job_id)
    
    if not job:
        return {
            "job_id": job_id,
            "status": "not_found",
            "exists": False
        }
    
    status = await job.status()
    info = await job.info()
    
    result = None
    error = None
    
    if info:
        if status == JobStatus.complete:
            result = info.result
        elif status == JobStatus.failed:
            error = info.result if isinstance(info.result, str) else str(info.result)
    
    return {
        "job_id": job_id,
        "status": status.value if status else "unknown",
        "exists": True,
        "result": result,
        "error": error,
        "enqueue_time": info.enqueue_time.isoformat() if info and info.enqueue_time else None,
        "start_time": info.start_time.isoformat() if info and info.start_time else None,
        "finish_time": info.finish_time.isoformat() if info and info.finish_time else None,
        "attempts": info.tries if info else 0
    }
