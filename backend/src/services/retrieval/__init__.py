from .reranker import RerankerService
from .context_builder import ContextBuilder
from .orchestrator import RetrievalOrchestrator
from .retrieval_service import RetrievalService
from .retrieval_pipeline import RetrievalPipeline
from .sparse_retriever import SparseRetriever
from .reciprocal_rank_fusion import (
    fuse_rrf,
    fuse_weighted_sum,
)
from .hybrid_retrieval_service import HybridRetrievalService
from .query_understanding_service import QueryUnderstandingService
from .retrieval_router import RetrievalRouter
from .retrieval_evaluation_service import RetrievalEvaluationService
from .retrieval_cache import RetrievalCache
from .retrieval_drift_monitor import RetrievalDriftMonitor
from .federated_hardening import FederatedResultMerger
from .bm25_persistence import (
    save_index,
    load_index,
    delete_index,
    index_is_stale,
    get_index_version,
)

__all__ = [
    # Existing
    "RerankerService",
    "ContextBuilder",
    "RetrievalOrchestrator",
    "RetrievalService",
    "RetrievalPipeline",
    # Phase 3B
    "SparseRetriever",
    "HybridRetrievalService",
    "QueryUnderstandingService",
    "RetrievalRouter",
    "RetrievalEvaluationService",
    # Phase 3B Hardening
    "RetrievalCache",
    "RetrievalDriftMonitor",
    "FederatedResultMerger",
    # Singletons
    "reranker_service", "context_builder", "retrieval_orchestrator",
    "retrieval_service", "retrieval_pipeline",
    "sparse_retriever", "hybrid_retrieval_service",
    "query_understanding_service", "retrieval_router",
    "retrieval_evaluation_service",
    "retrieval_cache",
    "drift_monitor",
    "federated_merger",
]


def __getattr__(name: str):
    if name == "reranker_service":
        from .reranker import get_reranker_service
        return get_reranker_service()
    if name == "context_builder":
        from .context_builder import get_context_builder
        return get_context_builder()
    if name == "retrieval_orchestrator":
        from .orchestrator import get_retrieval_orchestrator
        return get_retrieval_orchestrator()
    if name == "retrieval_service":
        from .retrieval_service import get_retrieval_service
        return get_retrieval_service()
    if name == "retrieval_pipeline":
        from .retrieval_pipeline import get_retrieval_pipeline
        return get_retrieval_pipeline()
    if name == "sparse_retriever":
        from .sparse_retriever import get_sparse_retriever
        return get_sparse_retriever()
    if name == "hybrid_retrieval_service":
        from .hybrid_retrieval_service import get_hybrid_retrieval_service
        return get_hybrid_retrieval_service()
    if name == "query_understanding_service":
        from .query_understanding_service import get_query_understanding_service
        return get_query_understanding_service()
    if name == "retrieval_router":
        from .retrieval_router import get_retrieval_router
        return get_retrieval_router()
    if name == "retrieval_evaluation_service":
        from .retrieval_evaluation_service import get_retrieval_evaluation_service
        return get_retrieval_evaluation_service()
    if name == "retrieval_cache":
        from .retrieval_cache import get_retrieval_cache
        return get_retrieval_cache()
    if name == "drift_monitor":
        from .retrieval_drift_monitor import get_drift_monitor
        return get_drift_monitor()
    if name == "federated_merger":
        from .federated_hardening import get_federated_merger
        return get_federated_merger()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
