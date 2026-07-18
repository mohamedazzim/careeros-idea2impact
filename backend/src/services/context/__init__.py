"""
Context services: assembly, compression, citation, prioritization, overlap resolution.
"""
from .context_assembly_service import ContextAssemblyService
from .context_compression_service import ContextCompressionService
from .semantic_deduplication import SemanticDeduplicator
from .context_integrity import ContextIntegrityGuard

__all__ = [
    "ContextAssemblyService",
    "ContextCompressionService",
    "SemanticDeduplicator",
    "ContextIntegrityGuard",
    "context_assembly_service",
    "context_compression_service",
    "semantic_deduplicator",
    "integrity_guard",
]


def __getattr__(name: str):
    if name == "context_assembly_service":
        from .context_assembly_service import get_context_assembly_service
        return get_context_assembly_service()
    if name == "context_compression_service":
        from .context_compression_service import get_context_compression_service
        return get_context_compression_service()
    if name == "semantic_deduplicator":
        from .semantic_deduplication import SemanticDeduplicator
        return SemanticDeduplicator()
    if name == "integrity_guard":
        from .context_integrity import get_integrity_guard
        return get_integrity_guard()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
