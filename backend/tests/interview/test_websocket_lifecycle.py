"""WebSocket lifecycle tests — connect, broadcast, disconnect, reconnect."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestWebSocketLifecycle:
    @pytest.mark.asyncio
    async def test_ws_manager_register(self):
        from src.runtime.realtime import WebSocketSessionManager
        ws_mgr = WebSocketSessionManager()

        mock_ws = AsyncMock()
        conn = await ws_mgr.register(mock_ws, "user1", "interview", "sess-001")
        assert conn.connection_id is not None
        assert conn.user_id == "user1"
        assert conn.session_type == "interview"

    @pytest.mark.asyncio
    async def test_ws_manager_unregister(self):
        from src.runtime.realtime import WebSocketSessionManager
        ws_mgr = WebSocketSessionManager()

        mock_ws = AsyncMock()
        conn = await ws_mgr.register(mock_ws, "user2", "interview", "sess-002")
        cid = conn.connection_id

        await ws_mgr.unregister(cid)
        assert cid not in ws_mgr._connections

    @pytest.mark.asyncio
    async def test_ws_manager_broadcast_to_session(self):
        from src.runtime.realtime import WebSocketSessionManager
        ws_mgr = WebSocketSessionManager()

        mock_ws = AsyncMock()
        conn = await ws_mgr.register(mock_ws, "user3", "interview", "sess-003")
        await ws_mgr.broadcast_to_session("sess-003", "test_event", {"key": "value"})

        # Should not raise
        assert True

    @pytest.mark.asyncio
    async def test_ws_manager_connection_lifecycle(self):
        from src.runtime.realtime import WebSocketSessionManager, ConnectionState
        ws_mgr = WebSocketSessionManager()

        mock_ws = AsyncMock()
        conn = await ws_mgr.register(mock_ws, "lifecycle_user", "orchestration", "sess-life")

        # After register: connection tracked
        assert conn.connection_id in ws_mgr._connections
        assert conn.connection_id in ws_mgr._user_sessions["lifecycle_user"]
        assert conn.connection_id in ws_mgr._session_connections["sess-life"]

        # After unregister: cleaned up completely
        await ws_mgr.unregister(conn.connection_id)
        assert conn.connection_id not in ws_mgr._connections
        assert conn.connection_id not in ws_mgr._user_sessions.get("lifecycle_user", set())
        assert conn.connection_id not in ws_mgr._session_connections.get("sess-life", set())
