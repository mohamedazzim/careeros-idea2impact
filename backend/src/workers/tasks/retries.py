"""
Task retry logic and error classification.
Re-exports from retry_service for backwards compatibility.
"""
import logging

logger = logging.getLogger(__name__)


# Re-export error classes for backwards compatibility
class TaskRetryableError(Exception):
    """Error that should trigger a retry."""
    pass


class TaskPermanentError(Exception):
    """Error that should NOT trigger a retry."""
    pass


# Re-export service function with compatible signature
async def retry_failed_task(resume_id: int, force: bool = False) -> str:
    """
    Manually retry a failed resume processing task.
    
    Args:
        resume_id: The resume to retry
        force: If True, retry even if not in failed state
        
    Returns:
        New job ID
        
    Raises:
        ValueError: If resume not found or cannot retry
    """
    from src.db.session import async_session
    from src.services.resume import retry_service, RetryServiceError, ResumeNotRetryableError
    
    async with async_session() as db:
        try:
            return await retry_service.retry_resume(db, resume_id, force=force)
        except ResumeNotRetryableError as e:
            raise ValueError(str(e))
        except RetryServiceError as e:
            raise ValueError(str(e))
