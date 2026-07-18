from sqlalchemy.ext.asyncio import AsyncSession
from src.services.privacy.engine import privacy_engine
from src.services.processing.chunking import chunking_service
from src.services.processing.normalization import normalization_service
from src.services.processing.versioning import versioning_service
from src.services.embedding.orchestrator import embedding_orchestrator
from src.models.resume import Resume
from langsmith import traceable

class ProcessingPipeline:
    @traceable(name="resume_orchestration_pipeline")
    async def run(self, db: AsyncSession, resume: Resume, raw_text: str):
        # 1. Masking (Privacy Engine)
        masked_text, report = privacy_engine.process(raw_text)
        
        # 2. Chunking
        chunks = chunking_service.chunk_text(masked_text)
        
        # 3. Normalization
        normalized_data = await normalization_service.normalize(masked_text)
        
        # 4. Versioning & Persistence
        # Assuming versions increment. Let's just create version 1 for simplicity
        version = await versioning_service.create_version(
            db=db,
            resume_id=resume.id,
            version_num=1,
            raw_content=raw_text,
            masked_content=masked_text,
            normalized_content=normalized_data.model_dump()
        )
        
        await versioning_service.save_chunks(db, version.id, chunks)
        
        # 5. NV-Embed-v1 Embedding Generation
        embed_result = await embedding_orchestrator.process_and_store_version_embeddings(
            user_id=resume.user_id,
            resume_id=resume.id,
            version_num=version.version_num,
            chunks=chunks
        )
        if embed_result.status == "failed":
            raise Exception(f"Embedding failed: {embed_result.error}")
        
        # Update Resume Status
        resume.status = "processed"
        db.add(resume)
        
        await db.commit()
        return version

pipeline = ProcessingPipeline()
