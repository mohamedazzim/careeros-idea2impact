"""
Task lifecycle management.
Re-exports from status_service for backwards compatibility.
"""
import logging
from typing import Optional, Dict

from src.services.resume import status_service

logger = logging.getLogger(__name__)


# Re-export functions with compatible signatures
async def update_resume_status(resume_id: int, status: str, error_message: Optional[str] = None):
    """
    Update resume status in database.
    Delegates to status_service.
    """
    from src.db.session import async_session
    
    async with async_session() as db:
        await status_service.update_status(db, resume_id, status, error_message)


async def publish_status_update(
    resume_id: int,
    status: str,
    job_id: str,
    extra_data: Optional[Dict] = None
):
    """
    Publish status update to Redis for real-time notifications.
    Delegates to status_service.
    """
    await status_service.publish_status_update(resume_id, status, job_id, extra_data)
