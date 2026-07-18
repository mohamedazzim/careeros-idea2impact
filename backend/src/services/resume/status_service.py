"""
Resume status service.
Manages status queries, updates, and real-time notifications.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from src.models.resume import Resume
from src.db.redis import redis_client

logger = logging.getLogger(__name__)


class StatusServiceError(Exception):
    """Raised when status operation fails."""
    pass


class ResumeStatusService:
    """
    Service for resume status management.
    Separates status logic from endpoints and workers.
    """

    # Status constants
    STATUS_UPLOADED = "uploaded"
    STATUS_PROCESSING = "processing"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_ERROR = "error"

    VALID_STATUSES = {
        STATUS_UPLOADED,
        STATUS_PROCESSING,
        STATUS_PROCESSED,
        STATUS_FAILED,
        STATUS_ERROR
    }

    async def update_status(
        self,
        db: AsyncSession,
        resume_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update resume status in database.

        Args:
            db: Database session
            resume_id: Resume ID
            status: New status
            error_message: Optional error message

        Returns:
            True if updated successfully
        """
        try:
            stmt = (
                update(Resume)
                .where(Resume.id == resume_id)
                .values(
                    status=status,
                    error_message=error_message,
                    updated_at=datetime.utcnow()
                )
            )
            await db.execute(stmt)
            await db.commit()

            logger.debug(f"Updated status for resume {resume_id}: {status}", extra={
                "resume_id": resume_id,
                "status": status
            })

            return True
        except Exception as e:
            logger.error(f"Failed to update status: {e}", extra={
                "resume_id": resume_id,
                "status": status
            })
            return False

    async def publish_status_update(
        self,
        resume_id: int,
        status: str,
        job_id: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish status update to Redis for real-time notifications.

        Args:
            resume_id: Resume ID
            status: Current status
            job_id: Background job ID
            extra_data: Additional data to include

        Returns:
            True if published successfully
        """
        try:
            message = {
                "resume_id": resume_id,
                "status": status,
                "job_id": job_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": extra_data or {}
            }

            channel = f"resume:status:{resume_id}"
            await redis_client.publish(channel, str(message))

            # Also set a short-lived key for polling fallback
            status_key = f"resume:status:{resume_id}:latest"
            await redis_client.setex(status_key, 3600, str(message))  # 1 hour TTL

            return True
        except Exception as e:
            logger.warning(f"Failed to publish status update: {e}", extra={
                "resume_id": resume_id,
                "status": status
            })
            return False

    async def get_cached_status(
        self,
        resume_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached status from Redis (for polling fallback).

        Args:
            resume_id: Resume ID

        Returns:
            Cached status dict or None
        """
        try:
            status_key = f"resume:status:{resume_id}:latest"
            data = await redis_client.get(status_key)
            if data:
                import ast
                return ast.literal_eval(data)
            return None
        except Exception as e:
            logger.debug(f"Failed to get cached status: {e}")
            return None

    async def cleanup_status_cache(
        self,
        resume_id: int
    ) -> bool:
        """
        Clean up status cache keys for a resume.

        Args:
            resume_id: Resume ID

        Returns:
            True if cleaned up
        """
        try:
            status_key = f"resume:status:{resume_id}:latest"
            await redis_client.delete(status_key)
            return True
        except Exception as e:
            logger.warning(f"Failed to cleanup status cache: {e}")
            return False

    def is_terminal_status(self, status: str) -> bool:
        """Check if status is terminal (no further processing)."""
        return status in {self.STATUS_PROCESSED, self.STATUS_FAILED}

    def is_processing_status(self, status: str) -> bool:
        """Check if status indicates active processing."""
        return status == self.STATUS_PROCESSING


# Global service instance
status_service = ResumeStatusService()
