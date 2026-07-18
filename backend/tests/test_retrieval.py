import pytest
import time
from src.schemas.retrieval import RetrievedChunk
from src.services.embedding.nvembed_service import NVEmbedV1Service
from src.services.retrieval.reranker import RerankerService
from src.services.retrieval.context_builder import ContextBuilder
from src.services.retrieval.orchestrator import RetrievalOrchestrator
from qdrant_client.models import ScoredPoint

@pytest.mark.asyncio
async def test_embed_query(monkeypatch):
    monkeypatch.setenv("MOCK_EMBEDDINGS", "true")
    service = NVEmbedV1Service()
    vector = await service.embed_query("test query")
    assert len(vector) == 4096

@pytest.mark.asyncio
async def test_reranker_mock_behavior():
    service = RerankerService(api_key="")
    chunks = [
        RetrievedChunk(id="1", text="chunk 1", score=0.8),
        RetrievedChunk(id="2", text="chunk 2", score=0.9),
    ]
    reranked = service._mock_rerank(chunks, top_n=2)
    assert len(reranked) == 2
    assert reranked[0].id == "2" # score 0.9 + 1.0 = 1.9
    assert reranked[1].id == "1" # score 0.8 + 0.5 = 1.3
    assert reranked[0].rerank_score > reranked[1].rerank_score

@pytest.mark.asyncio
async def test_reranker_provider_selection_real(mocker):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = mocker.MagicMock(
        status_code=200,
        text='{"rankings": [{"index": 1, "logit": 1.5}, {"index": 0, "logit": 0.5}]}',
        json=lambda: {"rankings": [{"index": 1, "logit": 1.5}, {"index": 0, "logit": 0.5}]}
    )

    service = RerankerService(api_key="nv-test-key")
    chunks = [
        RetrievedChunk(id="1", text="chunk 1", score=0.8),
        RetrievedChunk(id="2", text="chunk 2", score=0.9),
    ]
    reranked = await service.rerank("query", chunks, top_n=2)
    assert len(reranked) == 2
    assert reranked[0].id == "2"
    assert reranked[1].id == "1"
    mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_reranker_fallback_behavior_when_key_absent(monkeypatch):
    from src.core.config import settings

    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "", raising=False)
    service = RerankerService(api_key="")
    chunks = [
        RetrievedChunk(id="1", text="chunk 1", score=0.8),
        RetrievedChunk(id="2", text="chunk 2", score=0.9),
    ]
    reranked = await service.rerank("query", chunks, top_n=2)
    assert len(reranked) == 2
    assert reranked[0].id == "2"
    assert reranked[1].id == "1"

def test_context_builder():
    builder = ContextBuilder(max_tokens=100)
    
    from src.schemas.retrieval import RerankedChunk
    chunks = [
        RerankedChunk(id="1", text="Duplicate", score=0.9, rerank_score=0.95, source="src_1"),
        RerankedChunk(id="2", text="Unique text", score=0.8, rerank_score=0.85, source="src_2"),
        RerankedChunk(id="3", text="Duplicate", score=0.7, rerank_score=0.75, source="src_3"),
    ]
    context, citations = builder.assemble(chunks)
    assert len(citations) == 2
    assert "Duplicate" in context
    assert "Unique text" in context
    assert "[1] Source: src_1" in context

@pytest.mark.asyncio
async def test_retrieval_orchestrator(mocker, monkeypatch):
    monkeypatch.setenv("MOCK_EMBEDDINGS", "true")
    monkeypatch.setenv("MOCK_RERANKER", "true")

    mock_nvembed = mocker.AsyncMock()
    mock_nvembed.embed_query.return_value = [0.1] * 4096
    mocker.patch("src.services.retrieval.orchestrator.get_nvembed_service", return_value=mock_nvembed)

    mock_engine = mocker.AsyncMock()
    mock_engine.query_resumes.return_value = [
        ScoredPoint(id="1", version=1, score=0.9, payload={"text": "Hello World", "source": "Resume A"}, vector=None)
    ]
    mocker.patch("src.services.retrieval.orchestrator.get_vector_engine", return_value=mock_engine)

    orchestrator = RetrievalOrchestrator()
    result = await orchestrator.retrieve_context("Test Query", collection_type="resumes")

    assert result is not None
    assert result.query == "Test Query"
    assert len(result.retrieved_chunks) == 1
    assert result.retrieved_chunks[0].text == "Hello World"
    assert len(result.citations) == 1
    assert "embed_latency" in result.metrics
