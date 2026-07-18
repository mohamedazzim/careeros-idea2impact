"""Phase 8 — Redis Distributed Session Fabric.

Horizontally-scalable session registry, WebSocket fanout,
presence tracking, and node-coordinated failover.
All state is Redis-authoritative for Kubernetes multi-pod support.
"""

import json
import time
import uuid
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

NODE_ID = str(uuid.uuid4())[:8]

DISTRIBUTED_PREFIX = "realtime:distributed:"
NODE_HEARTBEAT_TTL = 15
SESSION_OWNERSHIP_TTL = 60
PRESENCE_SCAN_INTERVAL = 30


@dataclass
class SessionOwnership:
    session_uid: str
    node_id: str
    connection_count: int = 0
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_uid": self.session_uid,
            "node_id": self.node_id,
            "connection_count": self.connection_count,
            "last_heartbeat": self.last_heartbeat,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionOwnership":
        return cls(**data)


class DistributedSessionRegistry:
    """Redis-backed session ownership registry for multi-node scaling."""

    def __init__(self, node_id: str = NODE_ID):
        self._node_id = node_id
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def register_node(self) -> bool:
        """Register this node in the distributed registry."""
        try:
            from src.db.redis import redis_client
            key = f"{DISTRIBUTED_PREFIX}nodes:{self._node_id}"
            await redis_client.setex(key, NODE_HEARTBEAT_TTL, json.dumps({
                "node_id": self._node_id,
                "started_at": time.time(),
                "host": self._node_id,
            }))
            return True
        except Exception as exc:
            logger.error(f"Node registration failed: {exc}")
            return False

    async def heartbeat(self) -> bool:
        """Refresh this node's heartbeat."""
        try:
            from src.db.redis import redis_client
            key = f"{DISTRIBUTED_PREFIX}nodes:{self._node_id}"
            await redis_client.expire(key, NODE_HEARTBEAT_TTL)
            return True
        except Exception:
            return False

    async def claim_session(self, session_uid: str, connection_count: int = 1) -> bool:
        """Claim ownership of a session for this node."""
        try:
            from src.db.redis import redis_client
            key = f"{DISTRIBUTED_PREFIX}session_owner:{session_uid}"
            ownership = SessionOwnership(
                session_uid=session_uid,
                node_id=self._node_id,
                connection_count=connection_count,
            )
            await redis_client.setex(key, SESSION_OWNERSHIP_TTL, json.dumps(ownership.to_dict()))
            await redis_client.sadd(f"{DISTRIBUTED_PREFIX}node_sessions:{self._node_id}", session_uid)
            return True
        except Exception as exc:
            logger.error(f"Session claim failed: {exc}")
            return False

    async def get_session_owner(self, session_uid: str) -> Optional[str]:
        """Get which node owns a session."""
        try:
            from src.db.redis import redis_client
            raw = await redis_client.get(f"{DISTRIBUTED_PREFIX}session_owner:{session_uid}")
            if raw:
                ownership = SessionOwnership.from_dict(json.loads(raw))
                return ownership.node_id
        except Exception:
            pass
        return None

    async def release_session(self, session_uid: str) -> bool:
        """Release session ownership."""
        try:
            from src.db.redis import redis_client
            await redis_client.delete(f"{DISTRIBUTED_PREFIX}session_owner:{session_uid}")
            await redis_client.srem(f"{DISTRIBUTED_PREFIX}node_sessions:{self._node_id}", session_uid)
            return True
        except Exception:
            return False

    async def get_active_nodes(self) -> List[str]:
        try:
            from src.db.redis import redis_client
            cursor = 0
            nodes = []
            while True:
                cursor, keys = await redis_client.scan(cursor, match=f"{DISTRIBUTED_PREFIX}nodes:*")
                for key in keys:
                    node = key.decode().split(":")[-1]
                    nodes.append(node)
                if cursor == 0:
                    break
            return nodes
        except Exception:
            return [self._node_id]

    async def start_heartbeat(self):
        async def _loop():
            while True:
                await self.heartbeat()
                await asyncio.sleep(NODE_HEARTBEAT_TTL // 2)
        self._heartbeat_task = asyncio.create_task(_loop())

    async def stop_heartbeat(self):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        try:
            from src.db.redis import redis_client
            await redis_client.delete(f"{DISTRIBUTED_PREFIX}nodes:{self._node_id}")
        except Exception:
            pass


class RedisPubSubRouter:
    """Routes messages across nodes using Redis PubSub."""

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._pubsub = None
        self._listening = False

    async def subscribe(self, channel: str, handler: Callable[[Dict[str, Any]], None]):
        if channel not in self._handlers:
            self._handlers[channel] = []
        self._handlers[channel].append(handler)

        if not self._listening:
            await self._start_listening()

    async def publish(self, channel: str, data: Dict[str, Any]):
        try:
            from src.db.redis import redis_client
            message = json.dumps({"channel": channel, "data": data, "node_id": NODE_ID, "timestamp": time.time()})
            await redis_client.publish(channel, message)
        except Exception as exc:
            logger.error(f"PubSub publish failed: {exc}")

    async def _start_listening(self):
        self._listening = True
        try:
            from src.db.redis import redis_client
            self._pubsub = redis_client.pubsub()
            # Subscribe to all known channels
            for channel in self._handlers:
                await self._pubsub.subscribe(channel)
            asyncio.create_task(self._listen_loop())
        except Exception as exc:
            logger.error(f"PubSub listener start failed: {exc}")

    async def _listen_loop(self):
        while self._listening and self._pubsub:
            try:
                message = await asyncio.wait_for(
                    self._pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=1.0,
                )
                if message and message.get("type") == "message":
                    data = json.loads(message["data"])
                    channel = data.get("channel", message.get("channel", ""))
                    handlers = self._handlers.get(channel, [])
                    for handler in handlers:
                        try:
                            handler(data)
                        except Exception:
                            pass
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.error(f"PubSub listen error: {exc}")

    async def close(self):
        self._listening = False
        if self._pubsub:
            try:
                await self._pubsub.close()
            except Exception:
                pass


class DistributedPresence:
    """Tracks presence of users and sessions across all nodes."""

    async def set_presence(self, user_id: str, node_id: str, session_uid: str = "") -> bool:
        try:
            from src.db.redis import redis_client
            key = f"{DISTRIBUTED_PREFIX}presence:{user_id}"
            data = {
                "user_id": user_id,
                "node_id": node_id,
                "session_uid": session_uid,
                "last_seen": time.time(),
            }
            await redis_client.setex(key, 60, json.dumps(data))
            return True
        except Exception:
            return False

    async def get_presence(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            from src.db.redis import redis_client
            raw = await redis_client.get(f"{DISTRIBUTED_PREFIX}presence:{user_id}")
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    async def get_online_users(self) -> List[str]:
        try:
            from src.db.redis import redis_client
            cursor = 0
            users = []
            while True:
                cursor, keys = await redis_client.scan(cursor, match=f"{DISTRIBUTED_PREFIX}presence:*")
                for key in keys:
                    users.append(key.decode().split(":")[-1])
                if cursor == 0:
                    break
            return users
        except Exception:
            return []


# ── Singletons ───────────────────────────────────────────────────────

_registry: Optional[DistributedSessionRegistry] = None
_router: Optional[RedisPubSubRouter] = None
_presence: Optional[DistributedPresence] = None


def get_session_registry() -> DistributedSessionRegistry:
    global _registry
    if _registry is None:
        _registry = DistributedSessionRegistry()
    return _registry


def get_pubsub_router() -> RedisPubSubRouter:
    global _router
    if _router is None:
        _router = RedisPubSubRouter()
    return _router


def get_presence() -> DistributedPresence:
    global _presence
    if _presence is None:
        _presence = DistributedPresence()
    return _presence
