"""Phase 6 — Worker Registry.

Tracks active workers via Redis hash with heartbeat-based liveness detection.
Workers register themselves, send heartbeats, and are drained on shutdown.
"""

import uuid
import time
import json
import os
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

WORKER_KEY_PREFIX = "orch:worker:"
WORKER_REGISTRY_KEY = "orch:workers"
WORKER_TTL_SECONDS = 30
HEARTBEAT_INTERVAL = 10
STALE_THRESHOLD_SECONDS = 45


@dataclass
class WorkerNode:
    worker_id: str
    status: str = "active"  # active, draining, stopped
    hostname: str = ""
    pid: int = 0
    started_at: float = 0.0
    last_heartbeat: float = 0.0
    active_executions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "status": self.status,
            "hostname": self.hostname,
            "pid": self.pid,
            "started_at": self.started_at,
            "last_heartbeat": self.last_heartbeat,
            "active_executions": self.active_executions,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerNode":
        return cls(
            worker_id=data.get("worker_id", str(uuid.uuid4())),
            status=data.get("status", "active"),
            hostname=data.get("hostname", ""),
            pid=data.get("pid", 0),
            started_at=data.get("started_at", 0.0),
            last_heartbeat=data.get("last_heartbeat", 0.0),
            active_executions=data.get("active_executions", []),
            metadata=data.get("metadata", {}),
        )


class WorkerRegistry:
    """Redis-backed registry of active orchestration workers."""

    def __init__(self, worker_id: Optional[str] = None):
        self._worker_id = worker_id or str(uuid.uuid4())
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._draining = False

    @property
    def worker_id(self) -> str:
        return self._worker_id

    async def register(self, hostname: str = "", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Register this worker in the Redis registry."""
        try:
            from src.db.redis import redis_client
            node = WorkerNode(
                worker_id=self._worker_id,
                hostname=hostname,
                pid=os.getpid(),
                started_at=time.time(),
                last_heartbeat=time.time(),
                metadata=metadata or {},
            )
            await redis_client.hset(WORKER_REGISTRY_KEY, self._worker_id, json.dumps(node.to_dict()))
            await redis_client.setex(
                f"{WORKER_KEY_PREFIX}{self._worker_id}",
                WORKER_TTL_SECONDS,
                json.dumps(node.to_dict()),
            )
            logger.info(f"Worker {self._worker_id} registered (host={hostname})")
            return True
        except Exception as exc:
            logger.error(f"Worker registration failed: {exc}")
            return False

    async def heartbeat(self) -> bool:
        """Send heartbeat and refresh worker TTL."""
        try:
            from src.db.redis import redis_client
            node_data = await redis_client.hget(WORKER_REGISTRY_KEY, self._worker_id)
            if node_data:
                node = WorkerNode.from_dict(json.loads(node_data))
                node.last_heartbeat = time.time()
                await redis_client.hset(WORKER_REGISTRY_KEY, self._worker_id, json.dumps(node.to_dict()))
            key = f"{WORKER_KEY_PREFIX}{self._worker_id}"
            await redis_client.expire(key, WORKER_TTL_SECONDS)
            return True
        except Exception as exc:
            logger.error(f"Worker heartbeat failed: {exc}")
            return False

    async def start_heartbeat(self, interval: int = HEARTBEAT_INTERVAL):
        """Start periodic heartbeat loop."""
        async def _loop():
            while not self._draining:
                await self.heartbeat()
                await asyncio.sleep(interval)
        self._heartbeat_task = asyncio.create_task(_loop())
        logger.info(f"Heartbeat loop started for worker {self._worker_id}")

    async def stop_heartbeat(self):
        """Stop heartbeat loop and drain worker."""
        self._draining = True
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def drain(self) -> bool:
        """Mark worker as draining and remove from active registry."""
        try:
            from src.db.redis import redis_client
            node_data = await redis_client.hget(WORKER_REGISTRY_KEY, self._worker_id)
            if node_data:
                node = WorkerNode.from_dict(json.loads(node_data))
                node.status = "draining"
                await redis_client.hset(WORKER_REGISTRY_KEY, self._worker_id, json.dumps(node.to_dict()))
            logger.info(f"Worker {self._worker_id} draining")
            return True
        except Exception as exc:
            logger.error(f"Drain failed: {exc}")
            return False

    async def remove(self):
        """Remove worker from registry on graceful shutdown."""
        try:
            from src.db.redis import redis_client
            await redis_client.hdel(WORKER_REGISTRY_KEY, self._worker_id)
            await redis_client.delete(f"{WORKER_KEY_PREFIX}{self._worker_id}")
            logger.info(f"Worker {self._worker_id} removed from registry")
        except Exception as exc:
            logger.error(f"Worker removal failed: {exc}")

    async def get_all_workers(self) -> List[WorkerNode]:
        """List all registered workers and filter stale ones."""
        try:
            from src.db.redis import redis_client
            raw = await redis_client.hgetall(WORKER_REGISTRY_KEY)
            workers = []
            now = time.time()
            for wid, data in raw.items():
                node = WorkerNode.from_dict(json.loads(data))
                if now - node.last_heartbeat > STALE_THRESHOLD_SECONDS:
                    await self._reap_stale(wid)
                    continue
                workers.append(node)
            return workers
        except Exception:
            return []

    async def _reap_stale(self, worker_id: str):
        """Remove a stale worker from the registry."""
        try:
            from src.db.redis import redis_client
            await redis_client.hdel(WORKER_REGISTRY_KEY, worker_id)
            await redis_client.delete(f"{WORKER_KEY_PREFIX}{worker_id}")
            logger.warning(f"Reaped stale worker {worker_id}")
        except Exception:
            pass

    async def assign_execution(self, session_uid: str) -> bool:
        """Record that this worker is executing a session."""
        try:
            from src.db.redis import redis_client
            node_data = await redis_client.hget(WORKER_REGISTRY_KEY, self._worker_id)
            if node_data:
                node = WorkerNode.from_dict(json.loads(node_data))
                if session_uid not in node.active_executions:
                    node.active_executions.append(session_uid)
                await redis_client.hset(WORKER_REGISTRY_KEY, self._worker_id, json.dumps(node.to_dict()))
            return True
        except Exception:
            return False

    async def release_execution(self, session_uid: str) -> bool:
        """Remove a completed execution from this worker."""
        try:
            from src.db.redis import redis_client
            node_data = await redis_client.hget(WORKER_REGISTRY_KEY, self._worker_id)
            if node_data:
                node = WorkerNode.from_dict(json.loads(node_data))
                if session_uid in node.active_executions:
                    node.active_executions.remove(session_uid)
                await redis_client.hset(WORKER_REGISTRY_KEY, self._worker_id, json.dumps(node.to_dict()))
            return True
        except Exception:
            return False


# ── Singleton ────────────────────────────────────────────────────────

_registry: Optional[WorkerRegistry] = None


def get_worker_registry() -> WorkerRegistry:
    global _registry
    if _registry is None:
        _registry = WorkerRegistry()
    return _registry
