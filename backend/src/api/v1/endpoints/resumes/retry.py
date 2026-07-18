"""
Resume retry endpoint.
Thin controller - delegates retry orchestration to services.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.schemas.resume.resume import ResumeRetryResponse
from src.observability.langsmith import traceable
from src.services.resume import (
    retry_service,
    RetryServiceError,
    ResumeNotRetryableError
)
from .shared import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/{resume_id}/retry",
    response_model=ResumeRetryResponse,
    summary="Retry failed processing",
    description="Manually retry processing for a failed resume."
)
@traceable(name="retry_resume")
async def retry_resume(
    resume_id: int,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> ResumeRetryResponse:
    """
    Retry processing for a failed resume.

    Only resumes in 'failed' or 'error' status can be retried.
    Use force=true to retry regardless of status.
    """
    try:
        job_id = await retry_service.retry_resume(
            db=db,
            resume_id=resume_id,
            user_id=current_user,
            force=force
        )

        return ResumeRetryResponse(
            resume_id=resume_id,
            job_id=job_id,
            message="Processing retry queued successfully"
        )

    except ResumeNotRetryableError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RetryServiceError as e:
        logger.error(f"Retry failed: {e}", extra={
            "resume_id": resume_id,
            "user_id": current_user
        })
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
