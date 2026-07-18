"""Phase 6 — Streaming Orchestration.

Real-time WebSocket streaming for orchestration execution visibility.
Node-level events, governance decisions, and live traces.
"""

import json
import time
import logging
import asyncio
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

STREAM_CHANNEL = "orch:stream"


class OrchestrationStreamManager:
    """Manages streaming orchestration updates via Redis PubSub."""

    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._pubsub = None

    async def subscribe(self, session_uid: str) -> asyncio.Queue:
        """Subscribe to orchestration events for a session."""
        queue = asyncio.Queue(maxsize=100)
        if session_uid not in self._subscribers:
            self._subscribers[session_uid] = set()
        self._subscribers[session_uid].add(queue)

        try:
            from src.db.redis import redis_client
            self._pubsub = redis_client.pubsub()
            await self._pubsub.subscribe(f"{STREAM_CHANNEL}:{session_uid}")
            asyncio.create_task(self._listen(session_uid))
        except Exception as exc:
            logger.error(f"Subscribe failed: {exc}")

        return queue

    async def unsubscribe(self, session_uid: str, queue: asyncio.Queue):
        """Remove a subscriber."""
        subscribers = self._subscribers.get(session_uid, set())
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(session_uid, None)
            try:
                if self._pubsub:
                    await self._pubsub.unsubscribe(f"{STREAM_CHANNEL}:{session_uid}")
            except Exception:
                pass

    async def publish(self, session_uid: str, event_type: str, data: Dict[str, Any]):
        """Publish an orchestration event to all subscribers."""
        message = json.dumps({
            "session_uid": session_uid,
            "event_type": event_type,
            "data": data,
            "timestamp": time.time(),
        })
        try:
            from src.db.redis import redis_client
            await redis_client.publish(f"{STREAM_CHANNEL}:{session_uid}", message)
        except Exception:
            pass

        subscribers = self._subscribers.get(session_uid, set())
        for queue in subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

    async def _listen(self, session_uid: str):
        """Listen for Redis PubSub messages and forward to subscribers."""
        try:
            while self._pubsub and session_uid in self._subscribers:
                message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    subscribers = self._subscribers.get(session_uid, set())
                    for queue in subscribers:
                        try:
                            queue.put_nowait(message["data"])
                        except asyncio.QueueFull:
                            pass
        except (asyncio.TimeoutError, Exception):
            pass

    async def broadcast_node_event(
        self, session_uid: str, node_name: str, completion_pct: float, metadata: Optional[Dict[str, Any]] = None
    ):
        await self.publish(session_uid, "node_executed", {
            "node": node_name,
            "completion_pct": completion_pct,
            "metadata": metadata or {},
        })

    async def broadcast_governance_event(
        self, session_uid: str, verdict: str, details: Dict[str, Any]
    ):
        await self.publish(session_uid, "governance_decision", {
            "verdict": verdict,
            "details": details,
        })

    async def broadcast_error(self, session_uid: str, node_name: str, error: str):
        await self.publish(session_uid, "error", {
            "node": node_name,
            "error": error,
        })


class LiveTraceStreamer:
    """Streams real-time LangGraph execution traces."""

    def __init__(self, stream_mgr: Optional[OrchestrationStreamManager] = None):
        self.stream_mgr = stream_mgr or OrchestrationStreamManager()
        self._active_traces: Dict[str, List[Dict[str, Any]]] = {}

    async def start_trace(self, session_uid: str):
        self._active_traces[session_uid] = []
        await self.stream_mgr.publish(session_uid, "trace_started", {
            "session_uid": session_uid,
            "trace_nodes": [],
        })

    async def record_node(self, session_uid: str, node_name: str,
                          state_snapshot: Optional[Dict[str, Any]] = None):
        trace = self._active_traces.get(session_uid, [])
        entry = {
            "node": node_name,
            "timestamp": time.time(),
            "state": state_snapshot or {},
        }
        trace.append(entry)
        await self.stream_mgr.publish(session_uid, "node_recorded", entry)

    async def end_trace(self, session_uid: str):
        trace = self._active_traces.pop(session_uid, [])
        await self.stream_mgr.publish(session_uid, "trace_completed", {
            "session_uid": session_uid,
            "node_count": len(trace),
            "duration_ms": int((trace[-1]["timestamp"] - trace[0]["timestamp"]) * 1000) if trace else 0,
        })


# ── Singleton ────────────────────────────────────────────────────────

_stream_mgr: Optional[OrchestrationStreamManager] = None


def get_stream_manager() -> OrchestrationStreamManager:
    global _stream_mgr
    if _stream_mgr is None:
        _stream_mgr = OrchestrationStreamManager()
    return _stream_mgr
