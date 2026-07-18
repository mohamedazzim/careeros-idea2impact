from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from src.models.resume import ResumeVersion, ResumeChunk
from src.schemas.processing import VersionRecord

class VersioningService:
    async def create_version(self, db: AsyncSession, resume_id: int, version_num: int, 
                             raw_content: str, masked_content: str, normalized_content: dict) -> ResumeVersion:
        version = ResumeVersion(
            resume_id=resume_id,
            version_num=version_num,
            raw_content=raw_content,
            masked_content=masked_content,
            normalized_content=normalized_content
        )
        db.add(version)
        await db.flush()
        return version

    async def save_chunks(self, db: AsyncSession, version_id: int, chunks: list) -> None:
        db_chunks = []
        for chunk in chunks:
            c = ResumeChunk(
                version_id=version_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata_=chunk.metadata
            )
            db_chunks.append(c)
        db.add_all(db_chunks)
        await db.flush()

    async def get_version(self, db: AsyncSession, resume_id: int, version_num: int) -> Optional[VersionRecord]:
        stmt = select(ResumeVersion).where(
            ResumeVersion.resume_id == resume_id, 
            ResumeVersion.version_num == version_num
        )
        result = await db.execute(stmt)
        version = result.scalar_one_or_none()
        
        if version:
            return VersionRecord(
                version_num=version.version_num,
                resume_id=version.resume_id,
                raw_content=version.raw_content,
                masked_content=version.masked_content,
                normalized_content=version.normalized_content
            )
        return None
        
versioning_service = VersioningService()
