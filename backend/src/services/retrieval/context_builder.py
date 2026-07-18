import logging
from typing import List, Tuple
from langsmith import traceable
from src.schemas.retrieval import RerankedChunk, Citation
from src.services.processing.tokenizer_utils import estimate_tokens

logger = logging.getLogger(__name__)

class ContextBuilder:
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens

    @traceable(name="assemble_context_and_citations")
    def assemble(self, chunks: List[RerankedChunk]) -> Tuple[str, List[Citation]]:
        seen_texts = set()
        deduplicated = []
        for chunk in chunks:
            if chunk.text not in seen_texts:
                deduplicated.append(chunk)
                seen_texts.add(chunk.text)

        context_parts = []
        citations = []
        current_token_estimate = 0
        citation_counter = 1
        
        for chunk in deduplicated:
            # Tokenizer-aware estimation: use calibrated heuristic or real tokenizer
            chunk_tokens = estimate_tokens(chunk.text, text_type="resume")
            if current_token_estimate + chunk_tokens > self.max_tokens:
                break
                
            current_token_estimate += chunk_tokens
            
            citations.append(Citation(
                citation_id=citation_counter,
                source=chunk.source,
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id
            ))
            
            source_header = f"Source: {chunk.source or 'Unknown'}"
            context_parts.append(f"[{citation_counter}] {source_header}\n{chunk.text}")
            
            citation_counter += 1

        context = "\n\n".join(context_parts)
        return context, citations

_context_builder = None


def get_context_builder() -> ContextBuilder:
    """Lazily initialize and return the module-level singleton."""
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder()
    return _context_builder


def reset_context_builder() -> None:
    global _context_builder
    _context_builder = None


def __getattr__(name: str):
    if name == "context_builder":
        return get_context_builder()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
