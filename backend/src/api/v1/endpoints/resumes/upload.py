"""
Resume upload endpoint.
Thin controller - delegates all business logic to services.
"""
import logging

from fastapi import (
    APIRouter, File, UploadFile, Depends, HTTPException,
    status, BackgroundTasks
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.schemas.resume.resume import ResumeUploadResponse
from src.workers.arq_worker import enqueue_resume_processing
from src.observability.langsmith import traceable
from src.services.resume import (
    validation_service,
    upload_service,
    ValidationError,
    UploadServiceError
)
from .shared import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a resume",
    description="Upload a resume file for processing. Returns immediately with task ID."
)
@traceable(name="resume_upload")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Resume file (PDF, DOCX, DOC, TXT, RTF)"),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> ResumeUploadResponse:
    """
    Upload a resume file for processing.

    The file is validated, stored, and queued for background processing.
    Use the returned task_id to check processing status.

    Controller flow:
    1. Validate file (service)
    2. Process upload (service)
    3. Enqueue for processing (worker)
    4. Return response
    """
    # Step 1: Validate file
    try:
        content = await validation_service.validate_upload(file)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Step 2: Process upload via service
    try:
        resume = await upload_service.process_upload(
            filename=file.filename,
            content=content,
            content_type=file.content_type,
            user_id=current_user,
            db=db
        )
    except UploadServiceError as e:
        logger.error(f"Upload failed: {e}", extra={
            "user_id": current_user,
            "filename": file.filename
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process upload"
        )

    # Step 3: Enqueue for processing
    try:
        job_id = await enqueue_resume_processing(resume.id)
        await upload_service.update_task_id(db, resume, job_id)

        logger.info("Resume uploaded and queued", extra={
            "resume_id": resume.id,
            "user_id": current_user,
            "job_id": job_id,
            "filename": file.filename
        })
    except Exception as e:
        logger.error(f"Failed to enqueue: {e}", extra={
            "resume_id": resume.id,
            "user_id": current_user
        })
        # Don't fail the upload, user can retry processing later

    return ResumeUploadResponse.model_validate(resume)
