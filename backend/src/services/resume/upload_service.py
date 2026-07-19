"""
Resume upload service.
Orchestrates validation, storage, and database record creation.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.resume import Resume
from .validation_service import validation_service
from .storage_service import storage_service, StorageServiceError

logger = logging.getLogger(__name__)


class UploadServiceError(Exception):
    """Raised when upload fails."""
    pass


class ResumeUploadService:
    """
    Service for handling resume uploads.
    Coordinates validation, storage, and database operations.
    """

    async def process_upload(
        self,
        filename: str,
        content: bytes,
        content_type: Optional[str],
        user_id: str,
        db: AsyncSession
    ) -> Resume:
        """
        Process complete upload workflow.

        Args:
            filename: Original filename
            content: File content bytes
            content_type: MIME type
            user_id: User ID
            db: Database session

        Returns:
            Created Resume model instance

        Raises:
            UploadServiceError: If any step fails
        """
        # Step 1: Save to storage
        try:
            storage_path = await storage_service.save_file(filename, content, user_id)
        except StorageServiceError as e:
            raise UploadServiceError(f"Storage failed: {e}")

        # Step 2: Create database record
        try:
            resume = await self._create_resume_record(
                db=db,
                user_id=user_id,
                filename=filename,
                storage_path=storage_path,
                content_type=content_type,
                size_bytes=len(content)
            )
            return resume

        except Exception as e:
            # Cleanup storage on DB failure
            logger.error(f"Database error, cleaning up storage: {e}", extra={
                "user_id": user_id,
                "filename": filename
            })
            await storage_service.delete_file(storage_path)
            raise UploadServiceError(f"Database operation failed: {e}")

    async def _create_resume_record(
        self,
        db: AsyncSession,
        user_id: str,
        filename: str,
        storage_path: str,
        content_type: Optional[str],
        size_bytes: int
    ) -> Resume:
        """Create resume database record."""
        resume = Resume(
            user_id=user_id,
            filename=filename,
            storage_path=storage_path,
            status="uploaded",
            metadata_={
                "content_type": content_type or validation_service.get_content_type(filename),
                "size_bytes": size_bytes,
                "uploaded_at": datetime.utcnow().isoformat()
            }
        )

        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        logger.info("Resume record created", extra={
            "resume_id": resume.id,
            "user_id": user_id,
            "filename": filename
        })

        return resume

    async def update_task_id(
        self,
        db: AsyncSession,
        resume: Resume,
        task_id: Optional[str]
    ) -> None:
        """
        Update resume with task ID after enqueue.

        Args:
            db: Database session
            resume: Resume instance
            task_id: Background job ID
        """
        if task_id:
            resume.task_id = task_id
            await db.commit()
            await db.refresh(resume)

            logger.info("Resume updated with task_id", extra={
                "resume_id": resume.id,
                "task_id": task_id
            })


# Global service instance
upload_service = ResumeUploadService()
