"""
Status tracking pipeline.
Tracks pipeline execution status and checkpoints.
Integrates with versioning service for persistence.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..versioning_service import versioning_service
from ..status_service import status_service
from .interfaces import ProcessingStatus

logger = logging.getLogger(__name__)


class StatusPipeline:
    """
    Pipeline for tracking processing status.
    Manages checkpoints and version creation.
    """

    async def checkpoint(
        self,
        db: AsyncSession,
        resume_id: int,
        state: Dict[str, Any],
        stage: ProcessingStatus
    ) -> int:
        """
        Create a checkpoint by saving version.

        Args:
            db: Database session
            resume_id: Resume ID
            state: Current processing state
            stage: Current pipeline stage

        Returns:
            Version ID
        """
        logger.debug(f"Creating checkpoint for resume {resume_id} at stage {stage}")

        # Build version content from state
        version_content = {
            "stage": stage.value,
            "timestamp": datetime.utcnow().isoformat(),
            "normalized_content": state.get("normalized_content"),
            "entities": state.get("entities"),
            "chunks": state.get("chunks"),
            "metadata": {
                "raw_text_length": len(state.get("raw_text", "")),
                "masked_text_length": len(state.get("masked_text", "")),
                "chunk_count": len(state.get("chunks", [])),
            }
        }

        # Create version
        version = await versioning_service.create_version(
            db=db,
            resume_id=resume_id,
            raw_content=state.get("raw_text"),
            masked_content=state.get("masked_text"),
            normalized_content=version_content
        )

        logger.info("Checkpoint created", extra={
            "resume_id": resume_id,
            "version_id": version.id,
            "stage": stage.value
        })

        return version.id

    async def update_resume_status(
        self,
        db: AsyncSession,
        resume_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update resume status via status service.

        Args:
            db: Database session
            resume_id: Resume ID
            status: New status
            error_message: Optional error message
        """
        await status_service.update_status(db, resume_id, status, error_message)

    async def publish_stage_update(
        self,
        resume_id: int,
        stage: ProcessingStatus,
        job_id: str,
        extra_data: Optional[Dict] = None
    ) -> None:
        """
        Publish stage update for real-time notifications.

        Args:
            resume_id: Resume ID
            stage: Current stage
            job_id: Background job ID
            extra_data: Additional data
        """
        data = extra_data or {}
        data["stage"] = stage.value

        await status_service.publish_status_update(
            resume_id=resume_id,
            status=stage.value,
            job_id=job_id,
            extra_data=data
        )

    def should_checkpoint(self, stage: ProcessingStatus) -> bool:
        """Determine if a stage should create a checkpoint."""
        # Checkpoint after major transformations
        checkpoint_stages = {
            ProcessingStatus.EXTRACTING,
            ProcessingStatus.MASKING,
            ProcessingStatus.CHUNKING,
            ProcessingStatus.NORMALIZING,
            ProcessingStatus.COMPLETED
        }
        return stage in checkpoint_stages

    # LangGraph node interface
    async def run(
        self,
        db: AsyncSession,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LangGraph node entry point for status tracking.

        Args:
            db: Database session
            state: ProcessingState dict

        Returns:
            State update dict
        """
        current_status = state.get("status", ProcessingStatus.PENDING)
        resume_id = state.get("resume_id")

        if not resume_id:
            return {"status_error": "No resume_id in state"}

        # Update resume status
        await self.update_resume_status(
            db=db,
            resume_id=resume_id,
            status=current_status.value if isinstance(current_status, ProcessingStatus) else str(current_status)
        )

        # Create checkpoint if needed
        version_id = None
        if self.should_checkpoint(current_status) and isinstance(current_status, ProcessingStatus):
            version_id = await self.checkpoint(db, resume_id, state, current_status)

        return {
            "version_id": version_id,
            "checkpoint_created": version_id is not None
        }


# Global pipeline instance
status_pipeline = StatusPipeline()
