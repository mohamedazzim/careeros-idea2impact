import asyncio
import pytest
from src.services.processing.chunking import chunking_service
from src.services.processing.normalization import normalization_service, ResumeExtraction

def test_chunking_service():
    text = "Hello world! " * 100
    chunks = chunking_service.chunk_text(text)
    
    assert len(chunks) >= 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].metadata["start_char"] >= 0
    assert "Hello world!" in chunks[0].content

def test_normalization_service(mocker):
    text = "John Doe\njohn@example.com\nPython, React"
    
    mock_llm = mocker.MagicMock()
    mock_llm.invoke.return_value = ResumeExtraction(
        name="John Doe",
        email="john@example.com",
        phone="",
        skills=["Python", "React"],
        experience=[],
        education=[],
        projects=[],
        certifications=[],
        summary="",
    )
    
    normalization_service.structured_llm = mock_llm
    
    normalized = asyncio.run(normalization_service.normalize(text))
    
    assert normalized.personal_info["email"] == "john@example.com"
    assert "Python" in normalized.skills
