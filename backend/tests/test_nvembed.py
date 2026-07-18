import pytest
from src.services.embedding.nvembed_service import NVEmbedV1Service
from src.services.embedding.orchestrator import EmbeddingOrchestrator
from src.schemas.processing import ResumeChunkData

@pytest.mark.asyncio
async def test_nvembed_mock_generation():
    service = NVEmbedV1Service(api_key="")
    texts = ["Test chunk 1", "Test chunk 2"]
    
    embeddings = await service.generate_embeddings(texts)
    
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 4096
    assert service.dimensions == 4096
    assert service.model_name == "nvidia/nv-embed-v1"

@pytest.mark.asyncio
async def test_orchestrator_upsert(mocker):
    mock_vector_engine = mocker.AsyncMock()
    mock_vector_engine.insert_vectors.return_value = True

    mock_nvembed = mocker.AsyncMock()
    mock_nvembed.generate_embeddings.return_value = [[0.1] * 4096]
    mock_nvembed.model_name = "nvidia/nv-embed-v1"
    mock_nvembed.dimensions = 4096

    mocker.patch('src.services.embedding.orchestrator.get_vector_engine', return_value=mock_vector_engine)
    mocker.patch('src.services.embedding.orchestrator.get_nvembed_service', return_value=mock_nvembed)

    orchestrator = EmbeddingOrchestrator()

    chunks = [
        ResumeChunkData(chunk_index=0, content="Hello", metadata={"start_char": 0, "end_char": 5})
    ]

    resp = await orchestrator.process_and_store_version_embeddings(
        user_id="user_123",
        resume_id=1,
        version_num=1,
        chunks=chunks
    )

    assert resp.status == "success"
    assert resp.dimensions == 4096
    assert resp.chunks_processed == 1
    mock_vector_engine.insert_vectors.assert_called_once()
