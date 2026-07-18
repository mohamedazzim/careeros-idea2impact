"""Phase 6 — Distributed Lock Manager.

Redis-based distributed locking for orchestration ownership.
Uses SET NX with TTL for exclusive locks and lease renewal.
Prevents duplicate execution across multiple workers.
"""

import uuid
import time
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

LOCK_KEY_PREFIX = "orch:lock:"
LEASE_KEY_PREFIX = "orch:lease:"
DEFAULT_LOCK_TTL = 300  # 5 minutes
DEFAULT_LEASE_TTL = 120  # 2 minutes
LEASE_RENEW_INTERVAL = 30


@dataclass
class OwnershipLease:
    lease_id: str
    session_uid: str
    worker_id: str
    acquired_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    renewed_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "session_uid": self.session_uid,
            "worker_id": self.worker_id,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "renewed_at": self.renewed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OwnershipLease":
        return cls(
            lease_id=data.get("lease_id", ""),
            session_uid=data.get("session_uid", ""),
            worker_id=data.get("worker_id", ""),
            acquired_at=data.get("acquired_at", 0.0),
            expires_at=data.get("expires_at", 0.0),
            renewed_at=data.get("renewed_at", 0.0),
        )


class DistributedLockManager:
    """Manages distributed locks for orchestration session ownership."""

    def __init__(self):
        self._active_leases: Dict[str, OwnershipLease] = {}
        self._renew_tasks: Dict[str, asyncio.Task] = {}

    async def acquire(
        self,
        session_uid: str,
        worker_id: str,
        ttl: int = DEFAULT_LOCK_TTL,
    ) -> Optional[OwnershipLease]:
        """Acquire exclusive lock for an orchestration session."""
        try:
            from src.db.redis import redis_client
            lock_key = f"{LOCK_KEY_PREFIX}{session_uid}"
            lease_id = str(uuid.uuid4())
            acquired = await redis_client.set(lock_key, lease_id, nx=True, ex=ttl)

            if not acquired:
                existing = await redis_client.get(lock_key)
                logger.warning(f"Lock for {session_uid} held by {existing}")
                return None

            lease = OwnershipLease(
                lease_id=lease_id,
                session_uid=session_uid,
                worker_id=worker_id,
                expires_at=time.time() + ttl,
            )
            await self._persist_lease(session_uid, lease)
            self._active_leases[session_uid] = lease
            logger.info(f"Lock acquired: {session_uid} by {worker_id} ({lease.lease_id})")
            return lease
        except Exception as exc:
            logger.error(f"Lock acquisition failed for {session_uid}: {exc}")
            return None

    async def release(self, session_uid: str) -> bool:
        """Release lock for a session."""
        try:
            from src.db.redis import redis_client
            lock_key = f"{LOCK_KEY_PREFIX}{session_uid}"
            await redis_client.delete(lock_key)
            await redis_client.delete(f"{LEASE_KEY_PREFIX}{session_uid}")
            if session_uid in self._active_leases:
                del self._active_leases[session_uid]
            if session_uid in self._renew_tasks:
                self._renew_tasks[session_uid].cancel()
                del self._renew_tasks[session_uid]
            logger.info(f"Lock released: {session_uid}")
            return True
        except Exception as exc:
            logger.error(f"Lock release failed: {exc}")
            return False

    async def renew(self, session_uid: str, worker_id: str, ttl: int = DEFAULT_LOCK_TTL) -> bool:
        """Renew an active lock lease."""
        try:
            from src.db.redis import redis_client
            lock_key = f"{LOCK_KEY_PREFIX}{session_uid}"
            current = await redis_client.get(lock_key)
            if not current:
                logger.warning(f"Cannot renew lock for {session_uid}: no lock exists")
                return False
            await redis_client.expire(lock_key, ttl)
            if session_uid in self._active_leases:
                self._active_leases[session_uid].expires_at = time.time() + ttl
                self._active_leases[session_uid].renewed_at = time.time()
            return True
        except Exception as exc:
            logger.error(f"Lock renewal failed: {exc}")
            return False

    async def start_auto_renew(self, session_uid: str, worker_id: str, interval: int = LEASE_RENEW_INTERVAL):
        """Start automatic lease renewal loop."""
        async def _renew_loop():
            while session_uid in self._active_leases:
                await asyncio.sleep(interval)
                if session_uid in self._active_leases:
                    ok = await self.renew(session_uid, worker_id)
                    if not ok:
                        logger.error(f"Auto-renewal failed for {session_uid}")
                        break
        self._renew_tasks[session_uid] = asyncio.create_task(_renew_loop())

    async def is_locked(self, session_uid: str) -> bool:
        """Check if a session is currently locked."""
        try:
            from src.db.redis import redis_client
            lock_key = f"{LOCK_KEY_PREFIX}{session_uid}"
            return bool(await redis_client.exists(lock_key))
        except Exception:
            return session_uid in self._active_leases

    async def get_lock_owner(self, session_uid: str) -> Optional[str]:
        """Get the worker ID currently holding the lock."""
        try:
            from src.db.redis import redis_client
            lease_key = f"{LEASE_KEY_PREFIX}{session_uid}"
            raw = await redis_client.get(lease_key)
            if raw:
                import json
                lease = OwnershipLease.from_dict(json.loads(raw))
                return lease.worker_id
            return None
        except Exception:
            return None

    async def force_release_stale_locks(self, max_age_seconds: int = 600):
        """Release locks older than max_age_seconds (stale lock cleanup)."""
        try:
            from src.db.redis import redis_client
            import json
            cursor = 0
            now = time.time()
            stale_sessions = []
            while True:
                cursor, keys = await redis_client.scan(cursor, match=f"{LOCK_KEY_PREFIX}*")
                for key in keys:
                    lock_ttl = await redis_client.ttl(key)
                    if lock_ttl == -2:  # Key expired
                        continue
                    session_uid = key.decode().replace(LOCK_KEY_PREFIX, "")
                    lease_raw = await redis_client.get(f"{LEASE_KEY_PREFIX}{session_uid}")
                    if lease_raw:
                        lease = OwnershipLease.from_dict(json.loads(lease_raw))
                        if now - lease.acquired_at > max_age_seconds:
                            stale_sessions.append(session_uid)
                if cursor == 0:
                    break
            for sid in stale_sessions:
                await self.release(sid)
            return stale_sessions
        except Exception as exc:
            logger.error(f"Stale lock cleanup failed: {exc}")
            return []

    async def _persist_lease(self, session_uid: str, lease: OwnershipLease):
        try:
            from src.db.redis import redis_client
            import json
            await redis_client.setex(
                f"{LEASE_KEY_PREFIX}{session_uid}",
                DEFAULT_LEASE_TTL,
                json.dumps(lease.to_dict()),
            )
        except Exception:
            pass


# ── Singleton ────────────────────────────────────────────────────────

_lock_manager: Optional[DistributedLockManager] = None


def get_lock_manager() -> DistributedLockManager:
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = DistributedLockManager()
    return _lock_manager
