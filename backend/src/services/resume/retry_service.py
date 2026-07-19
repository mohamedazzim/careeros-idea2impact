"""
Resume retry service.
Handles retry orchestration for failed processing attempts.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.resume import Resume

logger = logging.getLogger(__name__)


class RetryServiceError(Exception):
    """Raised when retry fails."""
    pass


class ResumeNotRetryableError(RetryServiceError):
    """Raised when resume cannot be retried."""
    pass


class ResumeRetryService:
    """
    Service for retrying failed resume processing.
    Separates retry orchestration from endpoints and workers.
    """

    # Statuses that can be retried
    RETRYABLE_STATUSES = {"failed", "error"}

    async def can_retry(
        self,
        db: AsyncSession,
        resume_id: int,
        force: bool = False
    ) -> tuple[bool, Optional[Resume]]:
        """
        Check if a resume can be retried.

        Args:
            db: Database session
            resume_id: Resume ID
            force: If True, allow retry regardless of status

        Returns:
            Tuple of (can_retry, resume_or_none)
        """
        result = await db.execute(
            select(Resume).where(Resume.id == resume_id)
        )
        resume = result.scalar_one_or_none()

        if not resume:
            return False, None

        if force:
            return True, resume

        if resume.status in self.RETRYABLE_STATUSES:
            return True, resume

        return False, resume

    async def retry_resume(
        self,
        db: AsyncSession,
        resume_id: int,
        user_id: Optional[str] = None,
        force: bool = False
    ) -> str:
        """
        Retry processing for a failed resume.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: Optional user ID for ownership verification
            force: If True, retry even if not failed

        Returns:
            New job ID

        Raises:
            RetryServiceError: If retry fails
            ResumeNotRetryableError: If cannot retry
        """
        # Get resume
        result = await db.execute(
            select(Resume).where(Resume.id == resume_id)
        )
        resume = result.scalar_one_or_none()

        if not resume:
            raise RetryServiceError(f"Resume {resume_id} not found")

        # Check ownership if user_id provided
        if user_id and resume.user_id != user_id:
            raise RetryServiceError("Resume not found")

        # Check if can retry
        if resume.status not in self.RETRYABLE_STATUSES and not force:
            raise ResumeNotRetryableError(
                f"Cannot retry resume with status '{resume.status}'. Use force=True to override."
            )

        # Reset status
        resume.status = "uploaded"
        resume.error_message = None
        resume.updated_at = datetime.utcnow()
        db.add(resume)
        await db.commit()

        # Enqueue new job
        try:
            from src.workers.arq_worker import enqueue_resume_processing
            job_id = await enqueue_resume_processing(resume_id)
        except Exception as e:
            logger.error(f"Failed to enqueue retry: {e}", extra={
                "resume_id": resume_id
            })
            raise RetryServiceError(f"Failed to enqueue retry: {e}")

        logger.info(f"Retrying resume {resume_id} with new job {job_id}", extra={
            "resume_id": resume_id,
            "job_id": job_id,
            "force": force
        })

        return job_id

    async def reset_for_retry(
        self,
        db: AsyncSession,
        resume: Resume
    ) -> None:
        """
        Reset resume status for retry without enqueueing.

        Args:
            db: Database session
            resume: Resume to reset
        """
        resume.status = "uploaded"
        resume.error_message = None
        resume.updated_at = datetime.utcnow()
        db.add(resume)
        await db.commit()

        logger.info(f"Reset resume {resume.id} for retry", extra={
            "resume_id": resume.id
        })


# Global service instance
retry_service = ResumeRetryService()
