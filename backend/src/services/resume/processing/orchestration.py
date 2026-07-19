"""
Processing orchestration.
Coordinates pipeline execution and manages flow control.
Phase 2C: Extended pipeline with normalization → chunking → embedding prep.
"""
import logging
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.resume import Resume, ResumeVersion
from .interfaces import ProcessingState, ProcessingStatus, PipelineConfig
from .parser import parser_pipeline
from .ocr_pipeline import ocr_pipeline
from .extraction_pipeline import extraction_pipeline
from .masking_pipeline import masking_pipeline
from .normalization_pipeline import normalization_pipeline
from .chunking_pipeline import chunking_pipeline
from .embedding_preparation import embedding_preparation_pipeline
from .indexing_pipeline import indexing_pipeline
from .status_pipeline import status_pipeline

logger = logging.getLogger(__name__)


class ProcessingOrchestrator:
    """
    Orchestrates resume processing pipelines.

    Phase 2C/3A Pipeline Order:
    1. Parser → raw_text
    2. OCR (optional) → ocr_text
    3. Normalization → normalized_text + sections
    4. Entity Extraction (GLiNER) → entities
    5. PII Masking → masked_text + audit
    6. Semantic Chunking → chunks + section_boundaries
    7. Embedding Preparation → payloads + retrieval metadata
    8. Indexing → embeddings + Qdrant upsert
    9. Status checkpoint → version creation
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()

    async def process_resume(
        self,
        db: AsyncSession,
        resume: Resume,
        job_id: str,
    ) -> ResumeVersion:
        """
        Execute full processing pipeline for a resume.

        Args:
            db: Database session
            resume: Resume to process
            job_id: Background job ID for status tracking

        Returns:
            Created ResumeVersion

        Raises:
            Exception: If processing fails
        """
        logger.info(f"Starting Phase 2C processing pipeline for resume {resume.id}")

        state: ProcessingState = {
            "resume_id": resume.id,
            "user_id": resume.user_id,
            "filename": resume.filename,
            "storage_path": resume.storage_path,
            "content_type": resume.metadata_.get("content_type") if resume.metadata_ else None,
            "status": ProcessingStatus.PENDING,
        }

        try:
            # Stage 1: Parse document
            state = await self._run_stage(
                db, state, job_id, "parsing", parser_pipeline.run
            )
            if state.get("status") == ProcessingStatus.FAILED:
                raise Exception(state.get("parse_error", "Parsing failed"))

            # Stage 2: OCR (if enabled)
            if self.config.enable_ocr:
                state = await self._run_stage(
                    db, state, job_id, "ocr", ocr_pipeline.run
                )
                if state.get("status") == ProcessingStatus.FAILED:
                    raise Exception(state.get("ocr_error", "OCR failed"))

            # Stage 3: Normalization (Phase 2C: full preprocessing)
            if self.config.enable_normalization:
                state = await self._run_stage(
                    db, state, job_id, "normalization", normalization_pipeline.run
                )
                if state.get("status") == ProcessingStatus.FAILED:
                    raise Exception(state.get("normalization_error", "Normalization failed"))

            # Stage 4: Entity extraction (GLiNER)
            if self.config.enable_gliner:
                state = await self._run_stage(
                    db, state, job_id, "extraction", extraction_pipeline.run
                )
                if state.get("status") == ProcessingStatus.FAILED:
                    raise Exception(state.get("extraction_error", "Extraction failed"))

            # Stage 5: PII masking
            if self.config.enable_masking:
                state = await self._run_stage(
                    db, state, job_id, "masking", masking_pipeline.run
                )
                if state.get("status") == ProcessingStatus.FAILED:
                    raise Exception(state.get("masking_error", "Masking failed"))

            # Stage 6: Semantic chunking
            if self.config.enable_chunking:
                state = await self._run_stage(
                    db, state, job_id, "chunking", chunking_pipeline.run
                )
                if state.get("status") == ProcessingStatus.FAILED:
                    raise Exception(state.get("chunking_error", "Chunking failed"))

            # Stage 7: Embedding preparation
            if self.config.enable_embedding_prep:
                state = await self._run_stage(
                    db, state, job_id, "embedding_preparation", embedding_preparation_pipeline.run
                )
                if state.get("status") == ProcessingStatus.FAILED:
                    raise Exception(state.get("embedding_error", "Embedding prep failed"))

            # Stage 8: Indexing (Phase 3A: embeddings + Qdrant upsert)
            if self.config.enable_embedding_prep:
                state = await self._run_stage(
                    db, state, job_id, "indexing", indexing_pipeline.run
                )
                if state.get("status") == ProcessingStatus.FAILED:
                    raise Exception(state.get("indexing_error", "Indexing failed"))

            # Final checkpoint and version creation
            state["status"] = ProcessingStatus.COMPLETED
            version_id = await status_pipeline.checkpoint(
                db, resume.id, state, ProcessingStatus.COMPLETED
            )

            await status_pipeline.update_resume_status(db, resume.id, "processed")
            await status_pipeline.publish_stage_update(
                resume.id, ProcessingStatus.COMPLETED, job_id, {"version_id": version_id}
            )

            version = await self._get_version(db, version_id)
            logger.info(
                f"Phase 3A processing complete for resume {resume.id}",
                extra={"resume_id": resume.id, "version_id": version_id},
            )
            return version

        except Exception as e:
            logger.error(f"Processing failed for resume {resume.id}: {e}")
            await status_pipeline.update_resume_status(db, resume.id, "failed", str(e))
            await status_pipeline.publish_stage_update(
                resume.id, ProcessingStatus.FAILED, job_id, {"error": str(e)}
            )
            raise

    async def _run_stage(
        self,
        db: AsyncSession,
        state: Dict[str, Any],
        job_id: str,
        stage_name: str,
        pipeline_runner,
    ) -> Dict[str, Any]:
        """Run a single pipeline stage with status tracking."""
        logger.debug(f"Running stage: {stage_name}")

        update = await pipeline_runner(state)
        state.update(update)

        current_status = state.get("status")
        if isinstance(current_status, ProcessingStatus):
            await status_pipeline.publish_stage_update(
                state["resume_id"], current_status, job_id
            )

        if status_pipeline.should_checkpoint(current_status):
            await status_pipeline.checkpoint(
                db, state["resume_id"], state, current_status
            )

        return state

    async def _get_version(self, db: AsyncSession, version_id: int) -> ResumeVersion:
        from sqlalchemy.future import select

        result = await db.execute(
            select(ResumeVersion).where(ResumeVersion.id == version_id)
        )
        return result.scalar_one()


processing_orchestrator = ProcessingOrchestrator()


def create_orchestrator(
    enable_ocr: bool = False,
    enable_gliner: bool = True,
    enable_masking: bool = True,
    enable_chunking: bool = True,
    enable_normalization: bool = True,
    enable_embedding_prep: bool = True,
) -> ProcessingOrchestrator:
    """Create orchestrator with custom config."""
    config = PipelineConfig(
        enable_ocr=enable_ocr,
        enable_gliner=enable_gliner,
        enable_masking=enable_masking,
        enable_chunking=enable_chunking,
        enable_normalization=enable_normalization,
        enable_embedding_prep=enable_embedding_prep,
    )
    return ProcessingOrchestrator(config)
