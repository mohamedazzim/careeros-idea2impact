"""
Enterprise context assembly service.

Builds Claude-ready context with:
- Citation-aware formatting
- Structured retrieval blocks (source/chronology/section grouping)
- Relevance and rerank scoring per block
- Token-budget-aware prioritization
- Source preservation

Stateless, async-safe, observable. Worker-safe.
"""
import logging
from typing import List, Dict, Optional

from src.schemas.retrieval import (
    FusedResult,
    RerankedChunk,
    Citation,
    AssemblyBlock,
    ContextAssemblyResult,
)
from src.services.context.context_compression_service import get_context_compression_service
from src.services.processing.tokenizer_utils import estimate_tokens

logger = logging.getLogger(__name__)

MAX_TOKENS = 4000


class ContextAssemblyService:
    """Production-grade context assembly with structured formatting."""

    async def assemble(
        self,
        chunks: List[FusedResult],
        reranked: Optional[List[RerankedChunk]] = None,
        query: str = "",
        max_tokens: int = MAX_TOKENS,
        group_by_source: bool = True,
        group_by_section: bool = True,
    ) -> ContextAssemblyResult:
        """Assemble retrieval results into Claude-ready context.

        Pipeline:
        1. Compress chunks (dedup + overlap + budget)
        2. Build structured assembly blocks
        3. Generate citations
        4. Format final context string
        5. Track token usage
        """
        # 1. Compression
        compression = get_context_compression_service()
        compressed = await compression.compress(
            chunks=chunks,
            max_tokens=max_tokens,
            deduplicate=True,
            reduce_overlaps=True,
        )

        working_chunks = compressed.chunks

        # Build rerank score lookup if available
        rerank_map: Dict[str, float] = {}
        if reranked:
            for rc in reranked:
                rerank_map[rc.id] = rc.rerank_score

        # 2. Build assembly blocks
        blocks = self._build_blocks(working_chunks, rerank_map, query)

        # 3. Generate citations
        citations = self._generate_citations(blocks)

        # 4. Format context
        context = self._format_context(blocks, query)

        # 5. Token metrics
        total_tokens = estimate_tokens(context, text_type="resume")
        token_budget_used = (total_tokens / max_tokens * 100) if max_tokens > 0 else 0

        # Counts
        sources = set()
        sections = set()
        for block in blocks:
            if block.source:
                sources.add(block.source)
            if block.section:
                sections.add(block.section)

        return ContextAssemblyResult(
            context=context,
            blocks=blocks,
            citations=citations,
            total_tokens=total_tokens,
            token_budget_used_pct=round(token_budget_used, 1),
            source_count=len(sources),
            section_count=len(sections),
        )

    def _build_blocks(
        self,
        chunks: List[FusedResult],
        rerank_map: Dict[str, float],
        query: str,
    ) -> List[AssemblyBlock]:
        """Build structured assembly blocks from chunks."""
        blocks: List[AssemblyBlock] = []

        for i, chunk in enumerate(chunks):
            section = (
                chunk.metadata.get("section", "general")
                if isinstance(chunk.metadata, dict)
                else "general"
            )

            rerank_score = rerank_map.get(chunk.chunk_id)

            # Determine relevance reason
            reasons: List[str] = []
            if chunk.dense_score and chunk.dense_score > 0.7:
                reasons.append("strong semantic match")
            if chunk.sparse_rank and chunk.sparse_rank <= 5:
                reasons.append("exact keyword match")
            if section == "skills":
                reasons.append("skills section priority")
            if section == "experience":
                reasons.append("experience section")
            if not reasons:
                reasons.append("general relevance")

            reason = "; ".join(reasons)

            block_chunks = [
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "score": chunk.rrf_score,
                    "dense_score": chunk.dense_score,
                    "sparse_score": chunk.sparse_score,
                }
            ]

            block_citations = [
                Citation(
                    citation_id=i + 1,
                    source=chunk.source,
                    document_id=chunk.metadata.get("document_id") if isinstance(chunk.metadata, dict) else None,
                    chunk_id=chunk.chunk_id,
                )
            ]

            blocks.append(
                AssemblyBlock(
                    block_id=i + 1,
                    text=chunk.text,
                    source=chunk.source or "unknown",
                    section=section,
                    relevance_score=chunk.rrf_score,
                    rerank_score=rerank_score,
                    retrieval_reason=reason,
                    chunks=block_chunks,
                    citations=block_citations,
                )
            )

        return blocks

    def _generate_citations(self, blocks: List[AssemblyBlock]) -> List[Citation]:
        """Flatten citations from all blocks."""
        citations: List[Citation] = []
        for block in blocks:
            citations.extend(block.citations)
        return citations

    def _format_context(self, blocks: List[AssemblyBlock], query: str) -> str:
        """Format blocks into Claude-ready context string."""
        parts: List[str] = []

        if query:
            parts.append(f'[Retrieval Context for query: "{query}"]')

        for block in blocks:
            header = f"[{block.block_id}] Source: {block.source}"
            if block.section and block.section != "general":
                header += f" | Section: {block.section}"
            header += f" | Relevance: {block.relevance_score:.3f}"
            if block.rerank_score:
                header += f" | Rerank: {block.rerank_score:.3f}"

            parts.append(f"{header}\n{block.text}")

        return "\n\n".join(parts)


# Module-level singleton
_context_assembly_service: Optional[ContextAssemblyService] = None


def get_context_assembly_service() -> ContextAssemblyService:
    global _context_assembly_service
    if _context_assembly_service is None:
        _context_assembly_service = ContextAssemblyService()
    return _context_assembly_service


def reset_context_assembly_service() -> None:
    global _context_assembly_service
    _context_assembly_service = None


def __getattr__(name: str):
    if name == "context_assembly_service":
        return get_context_assembly_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
