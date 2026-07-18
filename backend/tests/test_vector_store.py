import pytest
from unittest.mock import AsyncMock, MagicMock
from qdrant_client.models import PointStruct, ScoredPoint
from src.services.vector_store.engine import vector_engine
from src.services.vector_store.manager import vector_store_manager
from src.schemas.vector_payloads import ResumePayload, JobPayload, KnowledgePayload

@pytest.mark.asyncio
async def test_create_collections(mocker):
    mock_qdrant = mocker.AsyncMock()
    existing = mocker.MagicMock()
    existing.collections = []
    mock_qdrant.get_collections.return_value = existing

    mocker.patch('src.services.vector_store.manager.get_qdrant', return_value=mock_qdrant)

    await vector_store_manager.init_collections()
    assert mock_qdrant.create_collection.call_count == 3

    # For delete, the manager checks collection_exists() which needs collections present
    existing_with_cols = mocker.MagicMock()
    existing_with_cols.collections = [
        mocker.MagicMock(name="careeros_resumes"),
        mocker.MagicMock(name="careeros_jobs"),
        mocker.MagicMock(name="careeros_knowledge"),
    ]
    existing_with_cols.collections[0].name = "careeros_resumes"
    existing_with_cols.collections[1].name = "careeros_jobs"
    existing_with_cols.collections[2].name = "careeros_knowledge"
    mock_qdrant.get_collections.return_value = existing_with_cols

    await vector_store_manager.delete_collections()
    assert mock_qdrant.delete_collection.call_count == 3

@pytest.mark.asyncio
async def test_insert_resume_vectors(mocker):
    mock_qdrant = mocker.AsyncMock()
    mocker.patch('src.services.vector_store.engine.get_qdrant', return_value=mock_qdrant)
    
    payload = ResumePayload(
        document_id="doc_123",
        chunk_id="chunk_1",
        version_num=2,
        chunk_index=0,
        text="Experienced software engineer."
    )
    points = [PointStruct(id="uid-1", vector=[0.01] * 4096, payload=payload.model_dump())]
    result = await vector_engine.insert_vectors("careeros_resumes", points)
    assert result is True
    mock_qdrant.upsert.assert_called_once_with(collection_name="careeros_resumes", points=points)

@pytest.mark.asyncio
async def test_insert_job_vectors(mocker):
    mock_qdrant = mocker.AsyncMock()
    mocker.patch('src.services.vector_store.engine.get_qdrant', return_value=mock_qdrant)
    
    payload = JobPayload(job_id="j_1", company="TechCorp", title="Dev", text="Looking for Dev")
    points = [PointStruct(id="uid-2", vector=[0.01] * 4096, payload=payload.model_dump())]
    result = await vector_engine.insert_vectors("careeros_jobs", points)
    assert result is True
    mock_qdrant.upsert.assert_called_once_with(collection_name="careeros_jobs", points=points)

@pytest.mark.asyncio
async def test_insert_knowledge_vectors(mocker):
    mock_qdrant = mocker.AsyncMock()
    mocker.patch('src.services.vector_store.engine.get_qdrant', return_value=mock_qdrant)
    
    payload = KnowledgePayload(document_id="k_1", category="HR", text="PTO policy")
    points = [PointStruct(id="uid-3", vector=[0.01] * 4096, payload=payload.model_dump())]
    result = await vector_engine.insert_vectors("careeros_knowledge", points)
    assert result is True
    mock_qdrant.upsert.assert_called_once_with(collection_name="careeros_knowledge", points=points)

@pytest.mark.asyncio
async def test_resume_metadata_filtering(mocker):
    mock_qdrant = mocker.AsyncMock()
    mock_qdrant.query_points.return_value = [ScoredPoint(id="1", version=1, score=0.98, payload={}, vector=None)]
    mocker.patch('src.services.vector_store.engine.get_qdrant', return_value=mock_qdrant)
    
    await vector_engine.query_resumes([0.05] * 4096, user_id="u_999", version_num=2)
    search_call_kwargs = mock_qdrant.query_points.call_args[1]
    assert search_call_kwargs["collection_name"] == "careeros_resumes"
    query_filter = search_call_kwargs["query_filter"]
    assert len(query_filter.must) == 2

@pytest.mark.asyncio
async def test_job_metadata_filtering(mocker):
    mock_qdrant = mocker.AsyncMock()
    mock_qdrant.query_points.return_value = []
    mocker.patch('src.services.vector_store.engine.get_qdrant', return_value=mock_qdrant)
    
    await vector_engine.query_jobs([0.05] * 4096, company="TechCorp")
    search_call_kwargs = mock_qdrant.query_points.call_args[1]
    assert search_call_kwargs["collection_name"] == "careeros_jobs"
    assert search_call_kwargs["query_filter"].must[0].key == "company"

@pytest.mark.asyncio
async def test_knowledge_metadata_filtering(mocker):
    mock_qdrant = mocker.AsyncMock()
    mock_qdrant.query_points.return_value = []
    mocker.patch('src.services.vector_store.engine.get_qdrant', return_value=mock_qdrant)
    
    await vector_engine.query_knowledge([0.05] * 4096, category="HR")
    search_call_kwargs = mock_qdrant.query_points.call_args[1]
    assert search_call_kwargs["collection_name"] == "careeros_knowledge"
    assert search_call_kwargs["query_filter"].must[0].key == "category"
