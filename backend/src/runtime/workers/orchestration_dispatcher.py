"""Phase 6 — Orchestration Dispatcher.

Routes incoming orchestration requests to available workers
with load balancing, deduplication, and queue overflow protection.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DISPATCH_KEY_PREFIX = "orch:dispatch:"


class OrchestrationDispatcher:
    """Routes orchestration jobs to workers with dedup and load balancing."""

    async def dispatch(
        self,
        session_uid: str,
        initial_state: Dict[str, Any],
        auto_notify: bool = False,
    ) -> Dict[str, Any]:
        """Dispatch an orchestration job to the worker pool."""
        dedup_key = f"{DISPATCH_KEY_PREFIX}{session_uid}"
        try:
            from src.db.redis import redis_client
            already_dispatched = await redis_client.get(dedup_key)
            if already_dispatched:
                logger.warning(f"Duplicate dispatch blocked for {session_uid}")
                return {"status": "rejected", "reason": "duplicate_dispatch"}
            await redis_client.setex(dedup_key, 300, "dispatched")
        except Exception:
            pass

        try:
            from src.runtime.workers.worker_pool import get_worker_pool
            pool = get_worker_pool()

            from src.runtime.workers.orchestration_worker import get_orchestration_worker
            worker = get_orchestration_worker()

            async def _job():
                return await worker.execute(session_uid, initial_state, auto_notify)

            assigned = await pool.submit(session_uid, _job)
            if not assigned:
                return {"status": "queued", "reason": "no_idle_workers", "session_uid": session_uid}

            # Wait briefly for worker to start
            await worker._active_executions.get(session_uid)
            return {
                "status": "dispatched",
                "session_uid": session_uid,
                "worker_id": assigned.worker_id,
            }
        except Exception as exc:
            logger.error(f"Dispatch failed: {exc}")
            return {"status": "failed", "reason": str(exc)}

    async def dispatch_with_lock(
        self,
        session_uid: str,
        initial_state: Dict[str, Any],
        worker_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch with distributed lock to prevent duplicate execution."""
        from src.runtime.workers.orchestration_worker import get_orchestration_worker
        from src.runtime.workers.worker_pool import get_worker_pool

        worker = get_orchestration_worker()
        wid = worker_id or worker.worker_id
        pool = get_worker_pool()

        async def _locked_job():
            return await worker.execute(session_uid, initial_state)

        ok = await pool.submit_with_lock(session_uid, _locked_job, wid)
        if not ok:
            return {"status": "rejected", "reason": "lock_acquisition_failed"}

        return {
            "status": "dispatched",
            "session_uid": session_uid,
            "worker_id": wid,
            "locked": True,
        }

    async def get_queue_depth(self) -> int:
        """Return pending orchestration jobs waiting for dispatch."""
        try:
            from src.db.redis import redis_client
            cursor = 0
            count = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match=f"{DISPATCH_KEY_PREFIX}*")
                count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception:
            return 0


_dispatcher: Optional[OrchestrationDispatcher] = None


def get_orchestration_dispatcher() -> OrchestrationDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = OrchestrationDispatcher()
    return _dispatcher
