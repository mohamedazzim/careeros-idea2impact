"""
Resume retrieval service.
Handles queries for resume listings, details, versions, and downloads.
"""
import logging
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func

from src.models.resume import Resume, ResumeVersion
from src.schemas.resume.resume import (
    ResumeListResponse,
    ResumeDetailResponse,
    ResumeVersionResponse
)
from .storage_service import storage_service, StorageServiceError

logger = logging.getLogger(__name__)


class RetrievalServiceError(Exception):
    """Raised when retrieval fails."""
    pass


class ResumeNotFoundError(RetrievalServiceError):
    """Raised when resume is not found."""
    pass


class ResumeRetrievalService:
    """
    Service for retrieving resume data.
    Separates query logic from API endpoints.
    """

    async def list_resumes(
        self,
        db: AsyncSession,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[str] = None
    ) -> ResumeListResponse:
        """
        List resumes for a user.

        Args:
            db: Database session
            user_id: User ID
            skip: Pagination offset
            limit: Pagination limit
            status_filter: Optional status filter

        Returns:
            ResumeListResponse with items and total count
        """
        # Build base query
        query = select(Resume).where(Resume.user_id == user_id)
        count_query = select(func.count(Resume.id)).where(Resume.user_id == user_id)

        if status_filter:
            query = query.where(Resume.status == status_filter)
            count_query = count_query.where(Resume.status == status_filter)

        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get paginated results
        query = query.order_by(desc(Resume.created_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        resumes = result.scalars().all()

        return ResumeListResponse(
            items=list(resumes),
            total=total,
            skip=skip,
            limit=limit
        )

    async def get_resume(
        self,
        db: AsyncSession,
        resume_id: int,
        user_id: str
    ) -> Resume:
        """
        Get single resume by ID.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID for ownership check

        Returns:
            Resume model instance

        Raises:
            ResumeNotFoundError: If not found or not owned
        """
        result = await db.execute(
            select(Resume).where(
                Resume.id == resume_id,
                Resume.user_id == user_id
            )
        )
        resume = result.scalar_one_or_none()

        if not resume:
            raise ResumeNotFoundError(f"Resume {resume_id} not found")

        return resume

    async def get_resume_detail(
        self,
        db: AsyncSession,
        resume_id: int,
        user_id: str
    ) -> ResumeDetailResponse:
        """
        Get detailed resume information.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID

        Returns:
            ResumeDetailResponse

        Raises:
            ResumeNotFoundError: If not found
        """
        resume = await self.get_resume(db, resume_id, user_id)
        return ResumeDetailResponse.model_validate(resume)

    async def get_resume_versions(
        self,
        db: AsyncSession,
        resume_id: int,
        user_id: str
    ) -> List[ResumeVersionResponse]:
        """
        Get version history for a resume.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID

        Returns:
            List of ResumeVersionResponse

        Raises:
            ResumeNotFoundError: If resume not found
        """
        # Verify ownership first
        await self.get_resume(db, resume_id, user_id)

        # Get versions
        result = await db.execute(
            select(ResumeVersion)
            .where(ResumeVersion.resume_id == resume_id)
            .order_by(desc(ResumeVersion.version_num))
        )
        versions = result.scalars().all()

        return [ResumeVersionResponse.model_validate(v) for v in versions]

    async def get_download_data(
        self,
        db: AsyncSession,
        resume_id: int,
        user_id: str
    ) -> Tuple[bytes, str, str]:
        """
        Get resume file for download.

        Args:
            db: Database session
            resume_id: Resume ID
            user_id: User ID

        Returns:
            Tuple of (content_bytes, filename, content_type)

        Raises:
            ResumeNotFoundError: If resume not found
            RetrievalServiceError: If file read fails
        """
        resume = await self.get_resume(db, resume_id, user_id)

        try:
            content = await storage_service.get_file_content(resume.storage_path)
        except StorageServiceError as e:
            logger.error(f"Failed to read file: {e}", extra={
                "resume_id": resume_id,
                "path": resume.storage_path
            })
            raise RetrievalServiceError(f"Failed to read file: {e}")

        content_type = self._determine_content_type(resume.filename)

        return content, resume.filename, content_type

    def _determine_content_type(self, filename: str) -> str:
        """Determine MIME type from filename."""
        filename_lower = filename.lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain',
            '.rtf': 'application/rtf'
        }

        for ext, content_type in content_types.items():
            if filename_lower.endswith(ext):
                return content_type

        return 'application/octet-stream'


# Global service instance
retrieval_service = ResumeRetrievalService()
