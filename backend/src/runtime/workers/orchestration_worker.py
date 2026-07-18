"""Phase 6 — Orchestration Worker.

Production runtime worker that executes LangGraph orchestration graphs
with full lifecycle management, event emission, and persistence.
"""

import uuid
import time
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class WorkerExecution:
    """Tracks a single graph execution by this worker."""
    execution_id: str
    session_uid: str
    worker_id: str
    status: str = "active"
    current_node: str = "initialized"
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    errors: List[str] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None


class OrchestrationWorker:
    """Executes LangGraph orchestration graphs as a distributed worker."""

    def __init__(self, worker_id: Optional[str] = None):
        self._worker_id = worker_id or str(uuid.uuid4())
        self._active_executions: Dict[str, WorkerExecution] = {}

    @property
    def worker_id(self) -> str:
        return self._worker_id

    async def execute(
        self,
        session_uid: str,
        initial_state: Dict[str, Any],
        auto_notify: bool = False,
    ) -> WorkerExecution:
        """Execute the full orchestration graph for a session."""
        execution = WorkerExecution(
            execution_id=f"exec_{session_uid}_{int(time.time())}",
            session_uid=session_uid,
            worker_id=self._worker_id,
        )
        self._active_executions[session_uid] = execution

        try:
            from src.runtime.events.event_bus import get_event_bus, Event
            event_bus = get_event_bus()
            await event_bus.publish(Event(
                event_type="orchestration_started",
                session_uid=session_uid,
                payload={"worker_id": self._worker_id},
            ))
        except Exception:
            pass

        try:
            from src.runtime.workers.worker_registry import get_worker_registry
            registry = get_worker_registry()
            await registry.assign_execution(session_uid)
        except Exception:
            pass

        try:
            from src.graphs.opportunity_graph import get_opportunity_graph
            graph = get_opportunity_graph()
            config = {"configurable": {"thread_id": session_uid}}

            state = {**initial_state, "session_uid": session_uid}
            if auto_notify:
                state["auto_notify"] = True

            result = await graph.ainvoke(state, config)
            execution.result = result if isinstance(result, dict) else {}
            execution.status = "completed"
            execution.current_node = "trace_compilation"

        except Exception as exc:
            execution.status = "failed"
            execution.errors.append(str(exc))
            logger.error(f"Orchestration worker {self._worker_id} failed: {exc}")

            try:
                from src.observability.metrics import ORCHESTRATION_FAILURES
                ORCHESTRATION_FAILURES.labels(
                    node_name="worker_execution", reason=type(exc).__name__
                ).inc()
            except Exception:
                pass

        execution.completed_at = time.time()

        try:
            from src.runtime.workers.worker_registry import get_worker_registry
            registry = get_worker_registry()
            await registry.release_execution(session_uid)
        except Exception:
            pass

        try:
            from src.runtime.events.event_bus import get_event_bus, Event
            event_bus = get_event_bus()
            await event_bus.publish(Event(
                event_type="orchestration_completed",
                session_uid=session_uid,
                payload={
                    "worker_id": self._worker_id,
                    "status": execution.status,
                    "duration_ms": int((execution.completed_at - execution.started_at) * 1000),
                },
            ))
        except Exception:
            pass

        await self._persist_execution(execution)
        return execution

    async def execute_with_retry(
        self,
        session_uid: str,
        initial_state: Dict[str, Any],
        max_attempts: int = 3,
    ) -> WorkerExecution:
        """Execute with automatic retry via RetryCoordinator."""
        from src.runtime.workers.retry_coordinator import get_retry_coordinator
        coordinator = get_retry_coordinator()

        async def _attempt():
            return await self.execute(session_uid, initial_state)

        result = await coordinator.schedule(session_uid, _attempt, max_attempts)
        if isinstance(result, dict) and result.get("status") == "failed":
            execution = WorkerExecution(
                execution_id=f"exec_{session_uid}_{int(time.time())}",
                session_uid=session_uid,
                worker_id=self._worker_id,
                status="failed",
                errors=[result.get("last_error", "Unknown")],
            )
        else:
            execution = result
        return execution

    async def resume(
        self,
        session_uid: str,
        checkpointer_thread_id: Optional[str] = None,
    ) -> Optional[WorkerExecution]:
        """Resume a previously failed or interrupted graph execution."""
        try:
            from src.graphs.opportunity_graph import get_opportunity_graph
            graph = get_opportunity_graph()

            thread_id = checkpointer_thread_id or session_uid
            config = {"configurable": {"thread_id": thread_id}}

            state = await graph.aget_state(config)
            if state is None or state.next == ():
                logger.info(f"No pending state to resume for {session_uid}")
                return None

            execution = WorkerExecution(
                execution_id=f"resume_{session_uid}_{int(time.time())}",
                session_uid=session_uid,
                worker_id=self._worker_id,
                status="active",
            )
            self._active_executions[session_uid] = execution

            try:
                from src.observability.metrics import GRAPH_RESUME_COUNT
                GRAPH_RESUME_COUNT.labels(graph_name="opportunity").inc()
            except Exception:
                pass

            result = await graph.ainvoke(None, config)
            execution.result = result if isinstance(result, dict) else {}
            execution.status = "completed"
            execution.completed_at = time.time()
            return execution
        except Exception as exc:
            logger.error(f"Resume failed for {session_uid}: {exc}")
            return None

    def get_active_executions(self) -> List[WorkerExecution]:
        return list(self._active_executions.values())

    async def _persist_execution(self, execution: WorkerExecution):
        try:
            import json
            from src.db.redis import redis_client
            key = f"orch:execution:{execution.execution_id}"
            await redis_client.setex(
                key,
                getattr(settings, 'ORCHESTRATION_SESSION_TTL', 7200),
                json.dumps({
                    "execution_id": execution.execution_id,
                    "session_uid": execution.session_uid,
                    "worker_id": execution.worker_id,
                    "status": execution.status,
                    "current_node": execution.current_node,
                    "started_at": execution.started_at,
                    "completed_at": execution.completed_at,
                    "errors": execution.errors,
                }),
            )
        except Exception:
            pass

    async def shutdown(self, timeout: float = 30.0):
        """Gracefully wait for active executions to finish."""
        deadline = time.time() + timeout
        while self._active_executions and time.time() < deadline:
            await asyncio.sleep(1)
        remaining = len(self._active_executions)
        if remaining:
            logger.warning(f"{remaining} executions still active after {timeout}s drain timeout")


# ── Singleton ────────────────────────────────────────────────────────

_worker: Optional[OrchestrationWorker] = None


def get_orchestration_worker() -> OrchestrationWorker:
    global _worker
    if _worker is None:
        _worker = OrchestrationWorker()
    return _worker
