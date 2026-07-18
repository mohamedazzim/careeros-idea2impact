"""Phase 7 — Realtime WebSocket API endpoints.

Hardened WebSocket authentication: JWT tokens required.
Token passed as query param validated before connection accepted.
"""

import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.security import HTTPBearer

from src.services.security.auth import auth_service

router = APIRouter(prefix="/realtime", tags=["Realtime"])

logger = logging.getLogger(__name__)
security_scheme = HTTPBearer(auto_error=False)


async def verify_token(token: Optional[str]) -> Optional[dict]:
    """Verify JWT token for WebSocket connection. Returns payload or None."""
    if not token:
        return None
    try:
        payload = auth_service.decode_token(token)
        if payload.type != "access":
            return None
        return {"sub": payload.sub, "role": payload.role}
    except Exception:
        return None


@router.websocket("/ws/{session_type}")
async def realtime_websocket(
    ws: WebSocket,
    session_type: str,
    token: str = Query(""),
    session_uid: str = Query(""),
):
    """Main WebSocket endpoint for interview, orchestration, and trace streaming.

    Requires JWT token as query parameter: ?token=<jwt>
    """
    # If token not provided as query param, attempt to read from cookie header
    if not token:
        cookie_header = ws.headers.get('cookie')
        if cookie_header:
            from http.cookies import SimpleCookie
            c = SimpleCookie()
            c.load(cookie_header)
            if 'careeros_token' in c:
                token = c['careeros_token'].value

    user = await verify_token(token)
    if not user:
        await ws.close(code=4001, reason="Authentication required")
        return

    from src.runtime.realtime import get_ws_manager

    await ws.accept()
    ws_mgr = get_ws_manager()
    conn = await ws_mgr.register(ws, user["sub"], session_type, session_uid,
                                  metadata={"endpoint": f"/ws/{session_type}", "role": user["role"]})
    logger.info(f"WebSocket connected: {conn.connection_id} user={user['sub']} type={session_type}")

    try:
        await ws.send_json({
            "type": "connected",
            "connection_id": conn.connection_id,
            "session_uid": conn.session_uid,
        })
        await ws_mgr.run_connection(conn)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected cleanly: {conn.connection_id}")
    except Exception as exc:
        logger.error(f"WebSocket fatal error {conn.connection_id}: {exc}")
    finally:
        await ws_mgr.unregister(conn.connection_id)


@router.websocket("/interview/{session_uid}")
async def interview_websocket(
    ws: WebSocket,
    session_uid: str,
    token: str = Query(""),
    interview_type: str = Query("technical"),
):
    """Dedicated interview WebSocket — live audio, transcripts, evaluation.

    Requires JWT token as query parameter: ?token=<jwt>
    """
    if not token:
        cookie_header = ws.headers.get('cookie')
        if cookie_header:
            from http.cookies import SimpleCookie
            c = SimpleCookie()
            c.load(cookie_header)
            if 'careeros_token' in c:
                token = c['careeros_token'].value

    user = await verify_token(token)
    if not user:
        await ws.close(code=4001, reason="Authentication required")
        return

    from src.runtime.realtime import get_ws_manager

    await ws.accept()
    ws_mgr = get_ws_manager()
    conn = await ws_mgr.register(ws, user["sub"], "interview", session_uid,
                                  metadata={"interview_type": interview_type, "role": user["role"]})

    try:
        await ws.send_json({"type": "connected", "connection_id": conn.connection_id, "session_uid": session_uid})
        await ws.send_json({"type": "interview_config", "interview_type": interview_type, "session_uid": session_uid})
        await ws_mgr.run_connection(conn)
    except WebSocketDisconnect:
        pass
    finally:
        await ws_mgr.unregister(conn.connection_id)


@router.websocket("/orchestration/trace/{session_uid}")
async def trace_websocket(ws: WebSocket, session_uid: str, token: str = Query("")):
    """Stream orchestration graph execution trace in real-time.

    Requires JWT token as query parameter: ?token=<jwt>
    """
    if not token:
        cookie_header = ws.headers.get('cookie')
        if cookie_header:
            from http.cookies import SimpleCookie
            c = SimpleCookie()
            c.load(cookie_header)
            if 'careeros_token' in c:
                token = c['careeros_token'].value

    user = await verify_token(token)
    if not user:
        await ws.close(code=4001, reason="Authentication required")
        return

    from src.runtime.realtime import get_ws_manager

    await ws.accept()
    ws_mgr = get_ws_manager()
    conn = await ws_mgr.register(ws, user["sub"], "trace", session_uid,
                                  metadata={"role": user["role"]})

    try:
        await ws.send_json({"type": "trace_subscribed", "session_uid": session_uid})
        await ws_mgr.run_connection(conn)
    except WebSocketDisconnect:
        pass
    finally:
        await ws_mgr.unregister(conn.connection_id)
