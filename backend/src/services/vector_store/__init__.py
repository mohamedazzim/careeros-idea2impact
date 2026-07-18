from .manager import VectorStoreManager
from .engine import VectorEngine
from .qdrant_service import QdrantService

__all__ = [
    "VectorStoreManager",
    "VectorEngine",
    "QdrantService",
    "vector_store_manager",
    "vector_engine",
    "qdrant_service",
]


def __getattr__(name: str):
    if name == "vector_store_manager":
        from .manager import get_vector_store_manager
        return get_vector_store_manager()
    if name == "vector_engine":
        from .engine import get_vector_engine
        return get_vector_engine()
    if name == "qdrant_service":
        from .qdrant_service import get_qdrant_service
        return get_qdrant_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
