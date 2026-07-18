"""Phase 5 — Orchestration Memory Service.

Dual-storage (Redis active + PostgreSQL durable) for orchestration state.
Follows the same pattern as InterviewPersistenceService from Phase 4D.
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.db.redis import redis_client

# ── Constants ────────────────────────────────────────────────────────

ORCH_PREFIX = settings.ORCHESTRATION_REDIS_KEY_PREFIX
SESSION_TTL = settings.ORCHESTRATION_SESSION_TTL


# ── State Contracts ──────────────────────────────────────────────────

@dataclass
class OrchestrationSessionState:
    session_uid: str
    user_id: str
    graph_name: str = "opportunity_graph"
    status: str = "active"
    current_node: Optional[str] = None
    completion_pct: float = 0.0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    db_id: Optional[int] = None


@dataclass
class OrchestrationEventState:
    event_uid: str
    session_uid: str
    event_type: str
    node_name: Optional[str] = None
    agent_name: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    status: str = "completed"
    retry_count: int = 0
    duration_ms: Optional[int] = None
    created_at: float = field(default_factory=time.time)


# ── OrchestrationMemoryService ───────────────────────────────────────

class OrchestrationMemoryService:
    """Redis-backed active orchestration memory with PostgreSQL fallback."""

    def __init__(self):
        self.prefix = ORCH_PREFIX

    # ── Session Management ──────────────────────────────────────────

    def _session_key(self, session_uid: str) -> str:
        return f"{self.prefix}session:{session_uid}"

    def _events_key(self, session_uid: str) -> str:
        return f"{self.prefix}events:{session_uid}"

    def _actions_key(self, session_uid: str) -> str:
        return f"{self.prefix}actions:{session_uid}"

    def _active_key(self) -> str:
        return f"{self.prefix}sessions:active"

    async def create_session(
        self,
        user_id: str,
        graph_name: str = "opportunity_graph",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationSessionState:
        session = OrchestrationSessionState(
            session_uid=str(uuid.uuid4()),
            user_id=user_id,
            graph_name=graph_name,
            metadata=metadata or {},
        )
        await self._save_session(session)
        await redis_client.sadd(self._active_key(), session.session_uid)
        return session

    async def get_session(self, session_uid: str) -> Optional[OrchestrationSessionState]:
        key = self._session_key(session_uid)
        data = await redis_client.hgetall(key)
        if not data:
            return None
        return self._deserialize_session(data)

    async def update_session(self, session: OrchestrationSessionState) -> None:
        session.updated_at = time.time()
        await self._save_session(session)

    async def close_session(self, session_uid: str, status: str = "completed") -> None:
        session = await self.get_session(session_uid)
        if session:
            session.status = status
            session.updated_at = time.time()
            await self._save_session(session)
            await redis_client.srem(self._active_key(), session_uid)

    async def list_active_sessions(self, limit: int = 50) -> List[str]:
        members = await redis_client.smembers(self._active_key())
        return list(members)[:limit]

    async def delete_session(self, session_uid: str) -> None:
        await redis_client.delete(self._session_key(session_uid))
        await redis_client.delete(self._events_key(session_uid))
        await redis_client.delete(self._actions_key(session_uid))
        await redis_client.srem(self._active_key(), session_uid)

    # ── Event Management ────────────────────────────────────────────

    async def record_event(self, event: OrchestrationEventState) -> None:
        event_json = self._serialize_event(event)
        await redis_client.hset(
            self._events_key(event.session_uid),
            event.event_uid,
            event_json,
        )
        await redis_client.expire(self._events_key(event.session_uid), SESSION_TTL)

    async def get_events(
        self, session_uid: str, event_type: Optional[str] = None
    ) -> List[OrchestrationEventState]:
        raw = await redis_client.hgetall(self._events_key(session_uid))
        events = []
        for _, val in raw.items():
            evt = self._deserialize_event(val)
            if event_type is None or evt.event_type == event_type:
                events.append(evt)
        return sorted(events, key=lambda e: e.created_at)

    async def get_event(self, session_uid: str, event_uid: str) -> Optional[OrchestrationEventState]:
        val = await redis_client.hget(self._events_key(session_uid), event_uid)
        return self._deserialize_event(val) if val else None

    async def get_event_count(self, session_uid: str) -> int:
        return await redis_client.hlen(self._events_key(session_uid))

    # ── Action Tracking ─────────────────────────────────────────────

    async def record_action(self, session_uid: str, action_data: Dict[str, Any]) -> None:
        action_id = action_data.get("action_uid", str(uuid.uuid4()))
        action_data["action_uid"] = action_id
        await redis_client.hset(
            self._actions_key(session_uid),
            action_id,
            json.dumps(action_data),
        )
        await redis_client.expire(self._actions_key(session_uid), SESSION_TTL)

    async def get_actions(self, session_uid: str) -> List[Dict[str, Any]]:
        raw = await redis_client.hgetall(self._actions_key(session_uid))
        return [json.loads(v) for v in raw.values()]

    async def get_action_count(self, session_uid: str) -> int:
        return await redis_client.hlen(self._actions_key(session_uid))

    # ── Idempotency ─────────────────────────────────────────────────

    async def action_already_taken(self, session_uid: str, action_type: str, opportunity_id: str) -> bool:
        actions = await self.get_actions(session_uid)
        for a in actions:
            if (
                a.get("action_type") == action_type
                and a.get("opportunity_id") == opportunity_id
                and a.get("status") == "completed"
            ):
                return True
        return False

    async def notification_already_sent(self, session_uid: str, opportunity_id: str) -> bool:
        key = f"{self.prefix}notified:{session_uid}:{opportunity_id}"
        exists = await redis_client.exists(key)
        return bool(exists)

    async def mark_notification_sent(self, session_uid: str, opportunity_id: str) -> None:
        key = f"{self.prefix}notified:{session_uid}:{opportunity_id}"
        await redis_client.setex(key, settings.AGENT_DUPLICATE_NOTIFICATION_TTL, "1")

    # ── Dead Letter ─────────────────────────────────────────────────

    async def dead_letter_event(self, event: OrchestrationEventState, reason: str) -> None:
        key = f"{self.prefix}dead_letter"
        entry = {
            "event": self._serialize_event(event),
            "reason": reason,
            "timestamp": time.time(),
        }
        await redis_client.lpush(key, json.dumps(entry))
        await redis_client.ltrim(key, 0, settings.ORCHESTRATION_EVENT_RETENTION)
        await redis_client.expire(key, settings.ORCHESTRATION_DEAD_LETTER_TTL)

    # ── Serialization ───────────────────────────────────────────────

    def _save_session(self, session: OrchestrationSessionState) -> None:
        data = {
            "session_uid": session.session_uid,
            "user_id": session.user_id,
            "graph_name": session.graph_name,
            "status": session.status,
            "current_node": session.current_node or "",
            "completion_pct": str(session.completion_pct),
            "errors": json.dumps(session.errors),
            "metadata": json.dumps(session.metadata),
            "created_at": str(session.created_at),
            "updated_at": str(session.updated_at),
            "db_id": str(session.db_id) if session.db_id else "",
        }
        pipe = redis_client.pipeline()
        key = self._session_key(session.session_uid)
        pipe.delete(key)
        for k, v in data.items():
            pipe.hset(key, k, v)
        pipe.expire(key, SESSION_TTL)
        pipe.execute()

    def _deserialize_session(self, data: Dict[str, str]) -> OrchestrationSessionState:
        return OrchestrationSessionState(
            session_uid=data.get("session_uid", ""),
            user_id=data.get("user_id", ""),
            graph_name=data.get("graph_name", "opportunity_graph"),
            status=data.get("status", "active"),
            current_node=data.get("current_node") or None,
            completion_pct=float(data.get("completion_pct", "0.0")),
            errors=self._json_list(data.get("errors", "[]")),
            metadata=self._json_dict(data.get("metadata", "{}")),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            db_id=int(data["db_id"]) if data.get("db_id") and data["db_id"] != "" else None,
        )

    def _serialize_event(self, event: OrchestrationEventState) -> str:
        return json.dumps({
            "event_uid": event.event_uid,
            "session_uid": event.session_uid,
            "event_type": event.event_type,
            "node_name": event.node_name,
            "agent_name": event.agent_name,
            "payload": event.payload or {},
            "status": event.status,
            "retry_count": event.retry_count,
            "duration_ms": event.duration_ms,
            "created_at": event.created_at,
        })

    def _deserialize_event(self, raw: str) -> OrchestrationEventState:
        data = json.loads(raw)
        return OrchestrationEventState(
            event_uid=data.get("event_uid", ""),
            session_uid=data.get("session_uid", ""),
            event_type=data.get("event_type", ""),
            node_name=data.get("node_name"),
            agent_name=data.get("agent_name"),
            payload=data.get("payload"),
            status=data.get("status", "completed"),
            retry_count=data.get("retry_count", 0),
            duration_ms=data.get("duration_ms"),
            created_at=data.get("created_at", time.time()),
        )

    @staticmethod
    def _json_list(raw: str) -> list:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    @staticmethod
    def _json_dict(raw: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}


# ── Singleton ────────────────────────────────────────────────────────

_orch_memory: Optional[OrchestrationMemoryService] = None


def get_orchestration_memory() -> OrchestrationMemoryService:
    global _orch_memory
    if _orch_memory is None:
        _orch_memory = OrchestrationMemoryService()
    return _orch_memory


def reset_orchestration_memory() -> None:
    global _orch_memory
    _orch_memory = None
