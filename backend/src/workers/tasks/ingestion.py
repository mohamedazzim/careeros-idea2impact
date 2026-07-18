"""
Resume ingestion task.
Worker orchestration - delegates processing to services.
"""
import logging
from typing import Dict, Any

from src.db.session import async_session
from src.observability.langsmith import traceable
from src.services.resume import (
    processing_service,
    status_service,
    ProcessingError,
    RetryableProcessingError,
    PermanentProcessingError
)
from .retries import TaskRetryableError, TaskPermanentError

logger = logging.getLogger(__name__)


@traceable(name="process_resume_task")
async def process_resume_task(ctx: Dict[str, Any], resume_id: int) -> Dict[str, Any]:
    """
    Background task to process a resume.
    
    Orchestrates the processing service through its lifecycle.
    Delegates all business logic to ResumeProcessingService.
    
    Args:
        ctx: ARQ context with job metadata
        resume_id: The resume ID to process
        
    Returns:
        Dict with status, message, and version info
        
    Raises:
        TaskRetryableError: For transient failures (will retry)
        TaskPermanentError: For permanent failures (no retry)
    """
    job_id = ctx.get('job_id', 'unknown')
    job_try = ctx.get('job_try', 1)
    
    logger.info(f"Processing resume {resume_id}", extra={
        "task": "process_resume",
        "resume_id": resume_id,
        "job_id": job_id,
        "attempt": job_try
    })
    
    try:
        async with async_session() as db:
            # Fetch resume
            resume = await processing_service.get_resume_for_processing(db, resume_id)
            
            if not resume:
                logger.error(f"Resume {resume_id} not found")
                raise TaskPermanentError(f"Resume {resume_id} not found")
            
            # Check if already processed (idempotency)
            if processing_service.is_already_processed(resume):
                logger.info(f"Resume {resume_id} already processed, skipping")
                return {
                    "status": "success",
                    "message": "Already processed",
                    "resume_id": resume_id,
                    "cached": True
                }
            
            # Mark as processing
            await processing_service.mark_processing(db, resume)
            await status_service.publish_status_update(resume_id, "processing", job_id)
            
            # Parse document
            try:
                raw_text = await processing_service.parse_document(resume)
            except PermanentProcessingError as e:
                raise TaskPermanentError(str(e))
            except RetryableProcessingError as e:
                raise TaskRetryableError(str(e))
            
            # Run processing pipeline
            try:
                version = await processing_service.run_processing_pipeline(db, resume, raw_text)
            except ProcessingError as e:
                raise TaskRetryableError(str(e))
            
            # Mark as processed
            await processing_service.mark_processed(db, resume)
            await status_service.publish_status_update(
                resume_id,
                "processed",
                job_id,
                {"version_id": version.id, "version_num": version.version_num}
            )
            
            logger.info(f"Resume {resume_id} processed successfully", extra={
                "task": "process_resume",
                "resume_id": resume_id,
                "version_id": version.id,
                "version_num": version.version_num
            })
            
            return {
                "status": "success",
                "message": "Processed successfully",
                "resume_id": resume_id,
                "version_id": version.id,
                "version_num": version.version_num
            }
            
    except TaskPermanentError:
        # Update status to failed via service
        await status_service.update_status(
            async_session(),
            resume_id,
            "failed"
        )
        raise
        
    except TaskRetryableError:
        # Keep processing status, will retry
        raise
        
    except Exception as e:
        # Unexpected error - treat as retryable
        logger.exception(f"Unexpected error processing resume {resume_id}")
        raise TaskRetryableError(f"Unexpected error: {e}")
