import logging
from typing import List, Any
from qdrant_client.models import PointStruct

from src.schemas.embedding import EmbeddingsGenerationResponse
from src.schemas.vector_payloads import ResumePayload
from src.services.vector_store.engine import get_vector_engine
from .nvembed_service import get_nvembed_service
from langsmith import traceable

import uuid

logger = logging.getLogger(__name__)

class EmbeddingOrchestrator:

    @traceable(name="process_and_store_embeddings")
    async def process_and_store_version_embeddings(
        self, 
        user_id: str, 
        resume_id: int, 
        version_num: int, 
        chunks: List[Any], 
    ) -> EmbeddingsGenerationResponse:
        """
        Takes database chunk models, generates embeddings via NV-Embed-v1, 
        and stores them into Qdrant vector database.
        """
        nvembed = get_nvembed_service()
        if not chunks:
             return EmbeddingsGenerationResponse(
                 dimensions=nvembed.dimensions,
                 model_name=nvembed.model_name,
                 chunks_processed=0,
                 status="skip",
                 error="No chunks provided"
             )

        # Extract text payloads
        texts = [c.content for c in chunks]

        try:
            # 1. Generate NV-Embed-V1 embeddings
            vectors = await nvembed.generate_embeddings(texts)
            
            # 2. Build points structure
            points = []
            for idx, chunk in enumerate(chunks):
                # Retrieve metadata, assume it contains start_char / end_char
                meta = chunk.metadata_ if hasattr(chunk, 'metadata_') else getattr(chunk, 'metadata', {})
                start_char = meta.get("start_char", 0)
                end_char = meta.get("end_char", 0)
                
                # We need a strict UUID for Qdrant Point identity
                point_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"resume_{resume_id}_v{version_num}_chunk_{chunk.chunk_index}"))
                
                payload_obj = ResumePayload(
                    user_id=user_id,
                    resume_id=resume_id,
                    version_num=version_num,
                    chunk_index=chunk.chunk_index,
                    start_char=start_char,
                    end_char=end_char,
                    text=chunk.content
                )
                
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vectors[idx],
                        payload=payload_obj.model_dump()
                    )
                )

            # 3. Upsert to Qdrant
            await get_vector_engine().insert_vectors(
                collection_name="careeros_resumes",
                points=points
            )
            
            return EmbeddingsGenerationResponse(
                 dimensions=nvembed.dimensions,
                 model_name=nvembed.model_name,
                 chunks_processed=len(points),
                 status="success"
            )

        except Exception as e:
            logger.error(f"Error embedding chunks: {e}")
            return EmbeddingsGenerationResponse(
                 dimensions=nvembed.dimensions,
                 model_name=nvembed.model_name,
                 chunks_processed=0,
                 status="failed",
                 error=str(e)
            )

_embedding_orchestrator = None


def get_embedding_orchestrator() -> EmbeddingOrchestrator:
    global _embedding_orchestrator
    if _embedding_orchestrator is None:
        _embedding_orchestrator = EmbeddingOrchestrator()
    return _embedding_orchestrator


def reset_embedding_orchestrator() -> None:
    global _embedding_orchestrator
    _embedding_orchestrator = None


def __getattr__(name: str):
    if name == "embedding_orchestrator":
        return get_embedding_orchestrator()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
