"""
Resume versioning service.
Manages version creation, retrieval, and lifecycle.
"""
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func

from src.models.resume import ResumeVersion

logger = logging.getLogger(__name__)


class VersioningServiceError(Exception):
    """Raised when versioning operation fails."""
    pass


class ResumeVersioningService:
    """
    Service for resume version management.
    Separates version logic from processing and retrieval.
    """

    async def create_version(
        self,
        db: AsyncSession,
        resume_id: int,
        raw_content: Optional[str] = None,
        masked_content: Optional[str] = None,
        normalized_content: Optional[Dict[str, Any]] = None
    ) -> ResumeVersion:
        """
        Create a new version for a resume.

        Args:
            db: Database session
            resume_id: Parent resume ID
            raw_content: Raw extracted text
            masked_content: PII-masked content
            normalized_content: Normalized structured data

        Returns:
            Created ResumeVersion
        """
        # Get next version number
        version_num = await self._get_next_version_number(db, resume_id)

        version = ResumeVersion(
            resume_id=resume_id,
            version_num=version_num,
            raw_content=raw_content,
            masked_content=masked_content,
            normalized_content=normalized_content
        )

        db.add(version)
        await db.commit()
        await db.refresh(version)

        logger.info(f"Created version {version_num} for resume {resume_id}", extra={
            "resume_id": resume_id,
            "version_id": version.id,
            "version_num": version_num
        })

        return version

    async def _get_next_version_number(self, db: AsyncSession, resume_id: int) -> int:
        """Get next version number for a resume."""
        result = await db.execute(
            select(func.max(ResumeVersion.version_num))
            .where(ResumeVersion.resume_id == resume_id)
        )
        max_version = result.scalar()
        return (max_version or 0) + 1

    async def get_version(
        self,
        db: AsyncSession,
        version_id: int
    ) -> Optional[ResumeVersion]:
        """Get a specific version by ID."""
        result = await db.execute(
            select(ResumeVersion).where(ResumeVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def get_versions_for_resume(
        self,
        db: AsyncSession,
        resume_id: int
    ) -> List[ResumeVersion]:
        """
        Get all versions for a resume, ordered by version number descending.

        Args:
            db: Database session
            resume_id: Resume ID

        Returns:
            List of ResumeVersion instances
        """
        result = await db.execute(
            select(ResumeVersion)
            .where(ResumeVersion.resume_id == resume_id)
            .order_by(desc(ResumeVersion.version_num))
        )
        return list(result.scalars().all())

    async def get_latest_version(
        self,
        db: AsyncSession,
        resume_id: int
    ) -> Optional[ResumeVersion]:
        """Get the latest version for a resume."""
        result = await db.execute(
            select(ResumeVersion)
            .where(ResumeVersion.resume_id == resume_id)
            .order_by(desc(ResumeVersion.version_num))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def delete_versions_for_resume(
        self,
        db: AsyncSession,
        resume_id: int
    ) -> int:
        """
        Delete all versions for a resume.

        Args:
            db: Database session
            resume_id: Resume ID

        Returns:
            Number of versions deleted
        """
        result = await db.execute(
            select(ResumeVersion).where(ResumeVersion.resume_id == resume_id)
        )
        versions = result.scalars().all()

        count = 0
        for version in versions:
            await db.delete(version)
            count += 1

        await db.commit()

        logger.info(f"Deleted {count} versions for resume {resume_id}", extra={
            "resume_id": resume_id,
            "versions_deleted": count
        })

        return count

    async def get_version_count(
        self,
        db: AsyncSession,
        resume_id: int
    ) -> int:
        """Get number of versions for a resume."""
        result = await db.execute(
            select(func.count(ResumeVersion.id))
            .where(ResumeVersion.resume_id == resume_id)
        )
        return result.scalar() or 0


# Global service instance
versioning_service = ResumeVersioningService()
