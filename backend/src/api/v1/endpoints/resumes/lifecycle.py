"""
Resume lifecycle endpoints.
Thin controllers - delegates operations to services.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.observability.langsmith import traceable
from src.services.resume import (
    deletion_service,
    DeletionServiceError
)
from .shared import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete resume",
    description="Delete a resume and all associated data."
)
@traceable(name="delete_resume")
async def delete_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> None:
    """
    Delete a resume and all its data.

    This includes:
    - The resume record
    - All versions and chunks
    - The stored file
    - Any pending processing tasks
    """
    try:
        await deletion_service.delete_resume(
            db=db,
            resume_id=resume_id,
            user_id=current_user
        )
    except DeletionServiceError as e:
        logger.error(f"Deletion failed: {e}", extra={
            "resume_id": resume_id,
            "user_id": current_user
        })
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
