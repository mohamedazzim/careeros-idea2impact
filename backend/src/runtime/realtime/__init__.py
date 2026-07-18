"""Phase 7 — Real-time WebSocket Session Manager.

Manages WebSocket connections with heartbeat, authentication, reconnection
support, and horizontal scalability via Redis PubSub fanout.
"""

import json
import time
import uuid
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

WS_IDLE_TIMEOUT = 300
WS_HEARTBEAT_INTERVAL = 30
WS_MAX_MESSAGE_SIZE = 64 * 1024
WS_BACKPRESSURE_LIMIT = 200

WS_METRICS_PREFIX = "realtime_ws"


@dataclass
class ConnectionState:
    connection_id: str
    user_id: str
    session_type: str  # interview, orchestration, trace
    session_uid: str
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    last_message_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    outbound_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=WS_BACKPRESSURE_LIMIT))
    ws: Optional[WebSocket] = None
    closed: bool = False

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_message_at

    @property
    def stale(self) -> bool:
        return time.time() - self.last_heartbeat > WS_IDLE_TIMEOUT


class WebSocketSessionManager:
    """Manages all active WebSocket connections with Redis PubSub fanout."""

    def __init__(self):
        self._connections: Dict[str, ConnectionState] = {}
        self._user_sessions: Dict[str, Set[str]] = {}
        self._session_connections: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
        self._draining = False
        self._metrics_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

    async def register(self, ws: WebSocket, user_id: str, session_type: str,
                       session_uid: str = "", metadata: Optional[Dict[str, Any]] = None) -> ConnectionState:
        """Register a new WebSocket connection."""
        conn = ConnectionState(
            connection_id=str(uuid.uuid4()),
            user_id=user_id,
            session_type=session_type,
            session_uid=session_uid or str(uuid.uuid4()),
            metadata=metadata or {},
            ws=ws,
        )
        async with self._lock:
            self._connections[conn.connection_id] = conn
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = set()
            self._user_sessions[user_id].add(conn.connection_id)
            if session_uid not in self._session_connections:
                self._session_connections[session_uid] = set()
            self._session_connections[session_uid].add(conn.connection_id)

        try:
            from src.observability.metrics import WEBSOCKET_CONNECTIONS
            WEBSOCKET_CONNECTIONS.set(len(self._connections))
        except Exception:
            pass

        await self._broadcast_connection_event(conn.session_uid, "connected", {
            "user_id": user_id, "session_type": session_type,
            "connection_id": conn.connection_id,
        })
        return conn

    async def unregister(self, connection_id: str):
        """Remove a disconnected connection."""
        async with self._lock:
            conn = self._connections.pop(connection_id, None)
            if not conn:
                return
            if conn.user_id in self._user_sessions:
                self._user_sessions[conn.user_id].discard(connection_id)
                if not self._user_sessions[conn.user_id]:
                    del self._user_sessions[conn.user_id]
            if conn.session_uid in self._session_connections:
                self._session_connections[conn.session_uid].discard(connection_id)
                if not self._session_connections[conn.session_uid]:
                    del self._session_connections[conn.session_uid]
            conn.closed = True

        try:
            from src.observability.metrics import WEBSOCKET_CONNECTIONS
            WEBSOCKET_CONNECTIONS.set(len(self._connections))
        except Exception:
            pass

    async def send(self, connection_id: str, event_type: str, data: Dict[str, Any]):
        """Send an event to a specific connection."""
        conn = self._connections.get(connection_id)
        if not conn or conn.closed:
            return
        message = json.dumps({
            "event": event_type, "data": data, "timestamp": time.time(),
            "connection_id": connection_id,
        })
        try:
            conn.outbound_queue.put_nowait(message)
        except asyncio.QueueFull:
            try:
                from src.observability.metrics import STREAM_EVENTS_TOTAL
                STREAM_EVENTS_TOTAL.labels(event_type="dropped").inc()
            except Exception:
                pass
            logger.warning(f"Outbound queue full for {connection_id}")

    async def broadcast_to_session(self, session_uid: str, event_type: str, data: Dict[str, Any]):
        """Broadcast an event to all connections in a session."""
        conn_ids = self._session_connections.get(session_uid, set())
        message = json.dumps({
            "event": event_type, "data": data, "session_uid": session_uid,
            "timestamp": time.time(),
        })
        for cid in conn_ids:
            conn = self._connections.get(cid)
            if conn and not conn.closed:
                try:
                    conn.outbound_queue.put_nowait(message)
                except asyncio.QueueFull:
                    pass
        try:
            from src.db.redis import redis_client
            await redis_client.publish(f"realtime:session:{session_uid}", message)
        except Exception:
            pass

    async def broadcast_to_user(self, user_id: str, event_type: str, data: Dict[str, Any]):
        """Broadcast to all connections for a user."""
        conn_ids = self._user_sessions.get(user_id, set())
        for cid in conn_ids:
            await self.send(cid, event_type, data)

    async def get_session_connections(self, session_uid: str) -> List[ConnectionState]:
        conn_ids = self._session_connections.get(session_uid, set())
        return [c for cid in conn_ids if (c := self._connections.get(cid)) and not c.closed]

    @property
    def active_connections(self) -> int:
        return sum(1 for c in self._connections.values() if not c.closed)

    async def _broadcast_connection_event(self, session_uid: str, event: str, data: Dict[str, Any]):
        try:
            from src.db.redis import redis_client
            await redis_client.publish("realtime:connections", json.dumps({
                "event": event, "data": data, "session_uid": session_uid,
            }))
        except Exception:
            pass

    async def run_connection(self, conn: ConnectionState):
        """Run the full WebSocket lifecycle: hearbeat + outbound stream + inbound handling."""
        if not conn.ws:
            return
        try:
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(conn))
            outbound_task = asyncio.create_task(self._outbound_loop(conn))
            await self._inbound_loop(conn)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {conn.connection_id}")
        except Exception as exc:
            logger.error(f"WebSocket error {conn.connection_id}: {exc}")
        finally:
            if 'heartbeat_task' in dir():
                heartbeat_task.cancel()
            if 'outbound_task' in dir():
                outbound_task.cancel()
            await self.unregister(conn.connection_id)

    async def _heartbeat_loop(self, conn: ConnectionState):
        while not conn.closed:
            try:
                if conn.ws:
                    await conn.ws.send_json({"type": "heartbeat", "ts": time.time()})
                conn.last_heartbeat = time.time()
            except Exception:
                break
            await asyncio.sleep(WS_HEARTBEAT_INTERVAL)

    async def _outbound_loop(self, conn: ConnectionState):
        while not conn.closed:
            try:
                message = await asyncio.wait_for(conn.outbound_queue.get(), timeout=1.0)
                if conn.ws:
                    await conn.ws.send_text(message)
                conn.last_message_at = time.time()
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    async def _inbound_loop(self, conn: ConnectionState):
        while not conn.closed and conn.ws:
            try:
                raw = await asyncio.wait_for(conn.ws.receive_text(), timeout=WS_IDLE_TIMEOUT)
                conn.last_message_at = time.time()
                if raw == "ping":
                    continue
                try:
                    msg = json.loads(raw)
                    msg_type = msg.get("type", "")
                    if msg_type == "subscribe":
                        channel = msg.get("channel", "")
                        if channel:
                            await self._subscribe_connection(conn, channel)
                    elif msg_type == "heartbeat":
                        conn.last_heartbeat = time.time()
                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON message from {conn.connection_id}")
            except asyncio.TimeoutError:
                if conn.idle_seconds > WS_IDLE_TIMEOUT:
                    break
            except WebSocketDisconnect:
                break

    async def _subscribe_connection(self, conn: ConnectionState, channel: str):
        try:
            from src.db.redis import redis_client
            from src.runtime.streaming import get_stream_manager
            stream_mgr = get_stream_manager()
            queue = await stream_mgr.subscribe(conn.session_uid)
            conn.metadata[f"sub_{channel}"] = True
        except Exception:
            pass

    async def start_cleanup(self):
        async def _cleanup():
            while not self._draining:
                async with self._lock:
                    stale = [cid for cid, c in self._connections.items() if c.stale and not c.closed]
                for cid in stale:
                    await self.unregister(cid)
                await asyncio.sleep(60)
        self._cleanup_task = asyncio.create_task(_cleanup())

    async def shutdown(self):
        self._draining = True
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._metrics_task:
            self._metrics_task.cancel()
        for conn in list(self._connections.values()):
            if conn.ws and not conn.closed:
                try:
                    await conn.ws.close()
                except Exception:
                    pass
        self._connections.clear()
        self._user_sessions.clear()
        self._session_connections.clear()


_ws_manager: Optional[WebSocketSessionManager] = None


def get_ws_manager() -> WebSocketSessionManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketSessionManager()
    return _ws_manager
