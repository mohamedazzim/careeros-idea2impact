"""
Reranking package: pipeline, score fusion, calibration, observability, enterprise orchestrator.

Extends rerank-qa-mistral-4b with enterprise-grade reranking intelligence.
All components are now wired into production retrieval paths.
"""
from .rerank_pipeline import RerankPipeline
from .score_fusion_service import ScoreFusionService
from .rerank_observability import RerankObservability
from .enterprise_reranker import EnterpriseReranker, get_enterprise_reranker

__all__ = [
    "RerankPipeline",
    "ScoreFusionService",
    "RerankObservability",
    "EnterpriseReranker",
    "get_enterprise_reranker",
    "rerank_pipeline",
    "score_fusion_service",
    "rerank_observability",
    "enterprise_reranker",
]


def __getattr__(name: str):
    if name == "rerank_pipeline":
        from .rerank_pipeline import RerankPipeline
        return RerankPipeline()
    if name == "score_fusion_service":
        from .score_fusion_service import ScoreFusionService
        return ScoreFusionService()
    if name == "rerank_observability":
        from .rerank_observability import RerankObservability
        return RerankObservability()
    if name == "enterprise_reranker":
        from .enterprise_reranker import get_enterprise_reranker
        return get_enterprise_reranker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
