from .nvembed_service import NVEmbedV1Service
from .orchestrator import EmbeddingOrchestrator
from .embedding_service import EmbeddingService

__all__ = [
    "NVEmbedV1Service",
    "EmbeddingOrchestrator",
    "EmbeddingService",
    "nvembed_service",
    "embedding_orchestrator",
    "embedding_service",
]


def __getattr__(name: str):
    if name == "nvembed_service":
        from .nvembed_service import get_nvembed_service
        return get_nvembed_service()
    if name == "embedding_orchestrator":
        from .orchestrator import get_embedding_orchestrator
        return get_embedding_orchestrator()
    if name == "embedding_service":
        from .embedding_service import get_embedding_service
        return get_embedding_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
