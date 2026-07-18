"""
Resume retrieval endpoints.
Thin controllers - delegates all queries to services.
"""
import logging
import io
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, 
    Query, status
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.schemas.resume.resume import (
    ResumeListResponse,
    ResumeDetailResponse,
    ResumeVersionResponse
)
from src.observability.langsmith import traceable
from src.services.resume import (
    retrieval_service,
    ResumeNotFoundError,
    RetrievalServiceError
)
from .shared import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=ResumeListResponse,
    summary="List user resumes",
    description="Get paginated list of user's resumes with status."
)
@traceable(name="list_resumes")
async def list_resumes(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> ResumeListResponse:
    """
    List resumes for the current user.
    
    Supports pagination and status filtering.
    Delegates to retrieval service.
    """
    return await retrieval_service.list_resumes(
        db=db,
        user_id=current_user,
        skip=skip,
        limit=limit,
        status_filter=status_filter
    )


@router.get(
    "/{resume_id}",
    response_model=ResumeDetailResponse,
    summary="Get resume details",
    description="Get detailed information about a specific resume."
)
@traceable(name="get_resume")
async def get_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> ResumeDetailResponse:
    """
    Get details for a specific resume.
    
    Includes metadata and processing status.
    """
    try:
        return await retrieval_service.get_resume_detail(
            db=db,
            resume_id=resume_id,
            user_id=current_user
        )
    except ResumeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )


@router.get(
    "/{resume_id}/versions",
    response_model=List[ResumeVersionResponse],
    summary="Get resume versions",
    description="Get all versions of a processed resume."
)
@traceable(name="get_resume_versions")
async def get_resume_versions(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> List[ResumeVersionResponse]:
    """
    Get version history for a resume.
    
    Each processing creates a new version with extracted content.
    """
    try:
        return await retrieval_service.get_resume_versions(
            db=db,
            resume_id=resume_id,
            user_id=current_user
        )
    except ResumeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )


@router.get(
    "/{resume_id}/download",
    summary="Download original file",
    description="Download the original uploaded resume file."
)
@traceable(name="download_resume")
async def download_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Download the original resume file.
    
    Returns the file with original filename and content type.
    """
    try:
        content, filename, content_type = await retrieval_service.get_download_data(
            db=db,
            resume_id=resume_id,
            user_id=current_user
        )
    except ResumeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    except RetrievalServiceError as e:
        logger.error(f"Failed to download: {e}", extra={
            "resume_id": resume_id,
            "user_id": current_user
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read file"
        )
    
    return StreamingResponse(
        io.BytesIO(content),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )
