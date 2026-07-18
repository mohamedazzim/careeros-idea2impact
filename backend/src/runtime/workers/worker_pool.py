"""Phase 6 — Worker Pool.

Manages a pool of async workers for concurrent orchestration execution.
With concurrency caps, queue balancing, and graceful lifecycle.
"""

import uuid
import time
import logging
import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PoolWorker:
    worker_id: str
    task: Optional[asyncio.Task] = None
    active_since: float = 0.0
    session_uid: Optional[str] = None
    status: str = "idle"  # idle, busy, draining


class WorkerPool:
    """Pool of async workers for orchestration graph execution."""

    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or getattr(
            settings, "ORCHESTRATION_MAX_CONCURRENT_AGENTS", 5
        )
        self._workers: List[PoolWorker] = []
        self._pending: List[Tuple[str, asyncio.Task]] = []
        self._lock = asyncio.Lock()
        self._draining = False

    async def start(self, count: Optional[int] = None):
        """Initialize the worker pool."""
        count = count or self.max_workers
        self._workers = [
            PoolWorker(worker_id=str(uuid.uuid4()))
            for _ in range(count)
        ]
        logger.info(f"Worker pool started with {count} workers (max={self.max_workers})")

    async def submit(
        self,
        session_uid: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> Optional[PoolWorker]:
        """Submit an orchestration to an available worker."""
        async with self._lock:
            available = None
            for w in self._workers:
                if w.status == "idle":
                    available = w
                    break
            if not available:
                logger.warning(f"No available workers for session {session_uid}")
                return None

            available.session_uid = session_uid
            available.active_since = time.time()
            available.status = "busy"

            async def _runner():
                try:
                    await coro_factory()
                except Exception as exc:
                    logger.error(f"Worker {available.worker_id} failed session {session_uid}: {exc}")
                finally:
                    available.status = "idle"
                    available.session_uid = None
                    available.active_since = 0.0

            available.task = asyncio.create_task(_runner())
            logger.info(f"Session {session_uid} assigned to worker {available.worker_id}")
            return available

    async def submit_with_lock(
        self,
        session_uid: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        worker_id: str,
    ) -> bool:
        """Submit to a specific worker with worker-level dedup."""
        from src.runtime.workers.distributed_lock_manager import get_lock_manager
        lock_mgr = get_lock_manager()
        lease = await lock_mgr.acquire(session_uid, worker_id)
        if not lease:
            logger.warning(f"Lock acquisition failed for {session_uid}")
            return False

        async with self._lock:
            available = None
            for w in self._workers:
                if w.status == "idle":
                    available = w
                    break
            if not available:
                await lock_mgr.release(session_uid)
                return False

            available.session_uid = session_uid
            available.status = "busy"

            async def _locked_runner():
                try:
                    await lock_mgr.start_auto_renew(session_uid, worker_id)
                    await coro_factory()
                except Exception as exc:
                    logger.error(f"Locked execution failed for {session_uid}: {exc}")
                finally:
                    await lock_mgr.release(session_uid)
                    available.status = "idle"
                    available.session_uid = None

            available.task = asyncio.create_task(_locked_runner())
            return True

    @property
    def active_count(self) -> int:
        return sum(1 for w in self._workers if w.status == "busy")

    @property
    def idle_count(self) -> int:
        return sum(1 for w in self._workers if w.status == "idle")

    @property
    def capacity(self) -> float:
        return self.idle_count / max(len(self._workers), 1)

    def status_report(self) -> Dict[str, Any]:
        return {
            "total_workers": len(self._workers),
            "active_workers": self.active_count,
            "idle_workers": self.idle_count,
            "capacity_pct": round(self.capacity * 100, 1),
            "draining": self._draining,
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "status": w.status,
                    "session_uid": w.session_uid,
                    "active_seconds": round(time.time() - w.active_since, 1) if w.active_since else 0,
                }
                for w in self._workers
            ],
        }

    async def drain(self, timeout: float = 60.0):
        """Wait for all active tasks to complete, then drain."""
        self._draining = True
        logger.info("Worker pool draining...")
        deadline = time.time() + timeout
        while self.active_count > 0 and time.time() < deadline:
            await asyncio.sleep(0.5)
        remaining = self.active_count
        if remaining > 0:
            logger.warning(f"Drain timeout after {timeout}s, {remaining} workers still active")
        else:
            logger.info("Worker pool drained cleanly")

    async def shutdown(self):
        """Cancel all tasks and shut down the pool."""
        for w in self._workers:
            if w.task and not w.task.done():
                w.task.cancel()
        await self.drain(timeout=10)


# ── Singleton ────────────────────────────────────────────────────────

_pool: Optional[WorkerPool] = None


def get_worker_pool() -> WorkerPool:
    global _pool
    if _pool is None:
        _pool = WorkerPool()
    return _pool
