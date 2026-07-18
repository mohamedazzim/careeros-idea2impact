"""Phase 6 — Distributed Autonomous Runtime.

Runtime components for orchestration execution, worker coordination,
scheduling, streaming, human-in-the-loop, graph recovery, and queuing.

Lazy imports — no component is loaded until its getter is called.
"""


def __getattr__(name: str):
    if name == "WorkerNode":
        from src.runtime.workers.worker_registry import WorkerNode
        return WorkerNode
    if name == "get_event_bus":
        from src.runtime.events.event_bus import get_event_bus
        return get_event_bus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
