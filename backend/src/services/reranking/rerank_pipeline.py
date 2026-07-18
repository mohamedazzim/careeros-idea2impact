"""
Reranking pipeline: score fusion, calibration, and observability.

Extends rerank-qa-mistral-4b with:
- Score fusion (similarity + rerank + metadata)
- Confidence-aware ranking
- Skill-priority reranking
- Section-aware boost calibration
- Rank inversion tracking

Stateless, async-safe, observable. Worker-safe.
"""
import logging
from typing import List, Dict

from src.schemas.retrieval import (
    RetrievedChunk,
    RerankedChunk,
)
from src.services.retrieval.reranker import get_reranker_service
from src.observability.metrics import (
    RERANK_CONFIDENCE,
    RERANK_SCORE_DISTRIBUTION,
    RERANK_RANK_INVERSION,
    RERANK_SKILL_PRIORITY_BOOST,
)

logger = logging.getLogger(__name__)

SECTION_PRIORITY: Dict[str, float] = {
    "experience": 1.15,
    "skills": 1.25,
    "summary": 1.10,
    "projects": 1.05,
    "education": 0.95,
    "certifications": 1.05,
    "awards": 0.95,
    "languages": 0.85,
    "publications": 0.90,
    "contact": 0.50,
    "general": 0.85,
    "preamble": 0.60,
}

SKILL_PRIORITY_KEYWORDS: List[str] = [
    "react", "typescript", "aws", "kubernetes", "python", "docker",
    "fastapi", "postgresql", "redis", "graphql", "terraform", "ci/cd",
    "machine learning", "nlp", "langgraph", "mcp", "kafka", "elasticsearch",
    "golang", "rust", "java", "spring", "angular", "vue", "next.js",
]


class RerankPipeline:
    """Production-grade reranking pipeline with priority-aware boosting."""

    async def rerank_with_boosts(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_n: int = 10,
        use_skill_priority: bool = True,
        use_section_priority: bool = True,
        use_chronology: bool = True,
        use_experience_boost: bool = True,
    ) -> List[RerankedChunk]:
        if not chunks:
            return []

        reranker = get_reranker_service()
        base_reranked = await reranker.rerank(query, chunks, top_n=len(chunks))

        boosted: List[RerankedChunk] = []
        query_lower = query.lower()
        skill_terms = [t for t in SKILL_PRIORITY_KEYWORDS if t in query_lower]

        for i, chunk in enumerate(base_reranked):
            score = chunk.rerank_score

            if use_skill_priority and skill_terms:
                chunk_text_lower = chunk.text.lower()
                skill_matches = sum(1 for t in skill_terms if t in chunk_text_lower)
                if skill_matches > 0:
                    skill_boost = 1.0 + (0.08 * min(skill_matches, 4))
                    score *= skill_boost
                    RERANK_SKILL_PRIORITY_BOOST.inc()

            if use_section_priority:
                metadata_section = (
                    chunk.metadata.get("section", "")
                    if isinstance(chunk.metadata, dict)
                    else ""
                )
                section_boost = SECTION_PRIORITY.get(metadata_section, 0.85)
                score *= section_boost

            if use_chronology:
                chunk_index = chunk.metadata.get("chunk_index", 0) if isinstance(chunk.metadata, dict) else 0
                if chunk_index > 0:
                    decay = max(0.85, 1.0 - (chunk_index * 0.01))
                    score *= decay

            if use_experience_boost:
                metadata_section = (
                    chunk.metadata.get("section", "")
                    if isinstance(chunk.metadata, dict)
                    else ""
                )
                if metadata_section == "experience":
                    words = len(chunk.text.split())
                    if words > 100:
                        score *= 1.05

            RERANK_CONFIDENCE.observe(score)
            RERANK_SCORE_DISTRIBUTION.observe(score)

            chunk.rerank_score = round(score, 6)
            boosted.append(chunk)

        boosted.sort(key=lambda x: x.rerank_score, reverse=True)

        if len(base_reranked) >= 2 and len(boosted) >= 2:
            rank_changes = sum(
                1 for i, c in enumerate(boosted)
                if i < len(base_reranked) and base_reranked[i].id != c.id
            )
            RERANK_RANK_INVERSION.observe(rank_changes)

        return boosted[:top_n]
