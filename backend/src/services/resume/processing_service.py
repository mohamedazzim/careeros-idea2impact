"""
Resume processing service.
Thin service layer that delegates to processing pipelines.
Orchestration moved to processing/orchestration.py for LangGraph migration.
"""
import logging
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.resume import Resume, ResumeVersion
from .processing import (
    parser_pipeline,
    processing_orchestrator,
    RetryablePipelineError,
    PermanentPipelineError,
    ProcessingStatus
)

logger = logging.getLogger(__name__)


# Re-export errors for backwards compatibility
class ProcessingError(Exception):
    """Base error for processing failures."""
    pass


class RetryableProcessingError(ProcessingError):
    """Error that can be retried."""
    pass


class PermanentProcessingError(ProcessingError):
    """Error that cannot be retried."""
    pass


class InsufficientContentError(PermanentProcessingError):
    """Raised when document has insufficient content."""
    pass


class FileNotFoundError(PermanentProcessingError):
    """Raised when source file is missing."""
    pass


class ResumeProcessingService:
    """
    Service for processing resume documents.
    Thin layer - delegates to processing pipelines.
    """

    async def get_resume_for_processing(
        self,
        db: AsyncSession,
        resume_id: int
    ) -> Optional[Resume]:
        """Fetch resume and validate it can be processed."""
        stmt = select(Resume).where(Resume.id == resume_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    def is_already_processed(self, resume: Resume) -> bool:
        """Check if resume is already in processed state."""
        return resume.status == "processed"

    async def parse_document(
        self,
        resume: Resume
    ) -> str:
        """
        Parse document to extract text content.
        Delegates to parser_pipeline.

        Args:
            resume: Resume with storage_path

        Returns:
            Extracted text content

        Raises:
            FileNotFoundError: If source file missing
            RetryableProcessingError: For parsing failures
            InsufficientContentError: If content too short
        """
        try:
            result = await parser_pipeline.parse(
                filename=resume.filename,
                storage_path=resume.storage_path,
                content_type=resume.metadata_.get("content_type") if resume.metadata_ else None
            )

            return result.text

        except PermanentPipelineError as e:
            raise PermanentProcessingError(str(e))
        except RetryablePipelineError as e:
            raise RetryableProcessingError(str(e))

    async def run_processing_pipeline(
        self,
        db: AsyncSession,
        resume: Resume,
        raw_text: str
    ) -> ResumeVersion:
        """
        Execute full processing pipeline.
        Delegates to processing_orchestrator.

        Args:
            db: Database session
            resume: Resume being processed
            raw_text: Extracted text content (legacy, not used with orchestrator)

        Returns:
            Created ResumeVersion
        """
        # Use orchestrator for full pipeline
        # Note: orchestrator will re-parse, but that's acceptable for now
        # Phase 2B: Pass state to avoid re-parsing

        version = await processing_orchestrator.process_resume(
            db=db,
            resume=resume,
            job_id=resume.task_id or "unknown"
        )

        return version

    async def update_status(
        self,
        db: AsyncSession,
        resume: Resume,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update resume status."""
        from .status_service import status_service
        await status_service.update_status(db, resume.id, status, error_message)

    async def mark_processing(
        self,
        db: AsyncSession,
        resume: Resume
    ) -> None:
        """Mark resume as processing, clearing previous errors."""
        await self.update_status(db, resume, "processing", None)

    async def mark_processed(
        self,
        db: AsyncSession,
        resume: Resume
    ) -> None:
        """Mark resume as successfully processed."""
        await self.update_status(db, resume, "processed", None)

    async def mark_failed(
        self,
        db: AsyncSession,
        resume: Resume,
        error: str
    ) -> None:
        """Mark resume as failed."""
        await self.update_status(db, resume, "failed", error)

    # LangGraph node interfaces (delegates to pipelines)
    async def node_parse(self, resume: Resume) -> Dict[str, Any]:
        """
        LangGraph node: Parse document.
        Delegates to parser_pipeline.
        """
        from .processing import ProcessingState

        state: ProcessingState = {
            "resume_id": resume.id,
            "user_id": resume.user_id,
            "filename": resume.filename,
            "storage_path": resume.storage_path,
            "status": ProcessingStatus.PENDING
        }

        return await parser_pipeline.run(state)

    async def node_pipeline(
        self,
        db: AsyncSession,
        resume: Resume,
        raw_text: str
    ) -> Dict[str, Any]:
        """
        LangGraph node: Run full pipeline.
        Delegates to orchestrator.
        """
        try:
            version = await self.run_processing_pipeline(db, resume, raw_text)
            return {
                "version_id": version.id,
                "version_num": version.version_num,
                "pipeline_error": None
            }
        except Exception as e:
            return {
                "version_id": None,
                "version_num": None,
                "pipeline_error": str(e)
            }


# Global service instance
processing_service = ResumeProcessingService()
