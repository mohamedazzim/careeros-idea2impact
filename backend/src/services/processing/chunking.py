from typing import List
from src.schemas.processing import ResumeChunkData
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langsmith import traceable
from .chunking_config import chunking_config

class ChunkingService:
    def __init__(self):
        self.chunk_size = chunking_config.CHUNK_SIZE
        self.overlap = chunking_config.CHUNK_OVERLAP
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.overlap,
            separators=["\n\n", "\n", ".", " ", ""],
            add_start_index=True,
        )

    @traceable(name="chunk_resume_text")
    def chunk_text(self, text: str) -> List[ResumeChunkData]:
        if not text:
            return []
            
        docs = self.splitter.create_documents([text])
        chunks = []
        for index, doc in enumerate(docs):
            start_index = doc.metadata.get("start_index", 0)
            end_index = start_index + len(doc.page_content)
            chunks.append(ResumeChunkData(
                chunk_index=index,
                content=doc.page_content,
                metadata={"start_char": start_index, "end_char": end_index}
            ))
            
        return chunks

chunking_service = ChunkingService()
