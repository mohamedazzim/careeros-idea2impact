"""
Resume deletion service.
Handles complete resume deletion with all associated data.
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.resume import Resume
from .storage_service import storage_service
from .status_service import status_service

logger = logging.getLogger(__name__)


class DeletionServiceError(Exception):
    """Raised when deletion fails."""
    pass


class ResumeDeletionService:
    """
    Service for deleting resumes and all associated data.
    Separates deletion logic from API endpoints.
    """

    # Statuses that indicate potential active processing
    ACTIVE_STATUSES = {"uploaded", "processing"}

    async def get_resume_for_deletion(
        self,
        db: AsyncSession,
        resume_id: int,
        user_id: str
    ) -> Optional[Resume]:
        """
        Get resume with ownership verification.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID for ownership check

        Returns:
            Resume if found and owned, None otherwise
        """
        result = await db.execute(
            select(Resume).where(
                Resume.id == resume_id,
                Resume.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def delete_resume(
        self,
        db: AsyncSession,
        resume_id: int,
        user_id: str
    ) -> bool:
        """
        Delete a resume and all its associated data.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID for ownership verification

        Returns:
            True if deleted successfully

        Raises:
            DeletionServiceError: If deletion fails
        """
        # Get resume
        resume = await self.get_resume_for_deletion(db, resume_id, user_id)

        if not resume:
            raise DeletionServiceError(f"Resume {resume_id} not found")

        # Step 1: Abort any pending task
        await self._abort_pending_task(resume)

        # Step 2: Delete from storage
        await self._delete_storage_file(resume)

        # Step 3: Cleanup status cache
        await self._cleanup_status_cache(resume_id)

        # Step 4: Soft delete from database (sets deleted_at, cascades not triggered)
        try:
            from datetime import datetime
            resume.deleted_at = datetime.utcnow()
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to soft-delete resume from database: {e}", extra={
                "resume_id": resume_id,
                "user_id": user_id
            })
            raise DeletionServiceError(f"Database deletion failed: {e}")

        logger.info("Resume deleted", extra={
            "resume_id": resume_id,
            "user_id": user_id
        })

        return True

    async def _abort_pending_task(self, resume: Resume) -> None:
        """Abort any pending processing task."""
        if resume.task_id and resume.status in self.ACTIVE_STATUSES:
            try:
                from src.workers.arq_worker import abort_job
                await abort_job(resume.task_id)
                logger.info(f"Aborted job {resume.task_id}", extra={
                    "resume_id": resume.id,
                    "job_id": resume.task_id
                })
            except Exception as e:
                logger.warning(f"Failed to abort job {resume.task_id}: {e}", extra={
                    "resume_id": resume.id,
                    "job_id": resume.task_id
                })

    async def _delete_storage_file(self, resume: Resume) -> None:
        """Delete file from storage."""
        try:
            await storage_service.delete_file(resume.storage_path)
            logger.info("Deleted storage file", extra={
                "resume_id": resume.id,
                "storage_path": resume.storage_path
            })
        except Exception as e:
            logger.warning(f"Failed to delete file {resume.storage_path}: {e}", extra={
                "resume_id": resume.id,
                "storage_path": resume.storage_path
            })

    async def _cleanup_status_cache(self, resume_id: int) -> None:
        """Clean up status cache in Redis."""
        await status_service.cleanup_status_cache(resume_id)

    async def bulk_delete(
        self,
        db: AsyncSession,
        user_id: str,
        resume_ids: list[int]
    ) -> tuple[int, list[int]]:
        """
        Delete multiple resumes.

        Args:
            db: Database session
            user_id: User ID
            resume_ids: List of resume IDs to delete

        Returns:
            Tuple of (success_count, failed_ids)
        """
        success_count = 0
        failed_ids = []

        for resume_id in resume_ids:
            try:
                await self.delete_resume(db, resume_id, user_id)
                success_count += 1
            except DeletionServiceError:
                failed_ids.append(resume_id)

        return success_count, failed_ids


# Global service instance
deletion_service = ResumeDeletionService()
