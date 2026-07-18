"""Phase 5 — Cross-Agent Memory Package.

Redis (active) + PostgreSQL (durable) dual-write.
Access via lazy __getattr__: `from src.memory import orchestration_memory`.
"""


def __getattr__(name: str):
    if name == "orchestration_memory":
        from src.memory.orchestration_memory import get_orchestration_memory
        return get_orchestration_memory()
    if name == "get_orchestration_memory":
        from src.memory.orchestration_memory import get_orchestration_memory
        return get_orchestration_memory
    if name == "reset_orchestration_memory":
        from src.memory.orchestration_memory import reset_orchestration_memory
        return reset_orchestration_memory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
