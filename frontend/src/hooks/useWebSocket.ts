"use client";
import { useRef, useEffect, useCallback, useState } from "react";

type WSEvent = {
  event: string;
  data: Record<string, unknown>;
  session_uid?: string;
  timestamp: number;
};

type WSOptions = {
  userId?: string;
  sessionType?: string;
  sessionUid?: string;
  onEvent?: (event: WSEvent) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
};

const WS_BASE = (process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1/realtime");
const INITIAL_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 30000;
const RECONNECT_JITTER_MS = 500;
const MAX_RECONNECT_ATTEMPTS = 10;
const HEARTBEAT_TIMEOUT_MS = 90000;

function getStoredToken(): string {
  try {
    return localStorage.getItem('careeros_token') || '';
  } catch {
    return '';
  }
}

export function useRealtimeWebSocket(options: WSOptions = {}) {
  const {
    userId = "anonymous",
    sessionType = "interview",
    sessionUid = "",
    onEvent,
    onConnected,
    onDisconnected,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const connectRef = useRef<() => void>(() => {});
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const reconnectAttemptRef = useRef(0);
  const heartbeatTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const mountedRef = useRef(true);
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [events, setEvents] = useState<WSEvent[]>([]);

  const getBackoffMs = useCallback(() => {
    const attempt = reconnectAttemptRef.current;
    const baseMs = Math.min(INITIAL_RECONNECT_MS * Math.pow(2, attempt), MAX_RECONNECT_MS);
    const jitter = Math.random() * RECONNECT_JITTER_MS;
    return baseMs + jitter;
  }, []);

  const resetHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) clearTimeout(heartbeatTimerRef.current);
    heartbeatTimerRef.current = setTimeout(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.close();
      }
    }, HEARTBEAT_TIMEOUT_MS);
  }, []);

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = undefined;
    }
    if (heartbeatTimerRef.current) {
      clearTimeout(heartbeatTimerRef.current);
      heartbeatTimerRef.current = undefined;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    if (sessionType === "interview" && !sessionUid) return;
    if (reconnectAttemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
      setReconnecting(false);
      return;
    }
    setReconnecting(true);
    const delay = getBackoffMs();
    reconnectTimerRef.current = setTimeout(() => {
      if (!mountedRef.current) return;
      connectRef.current();
    }, delay);
  }, [getBackoffMs, sessionType, sessionUid]);

  const disconnectAndConnect = useCallback(() => {
    cleanup();
    if (!mountedRef.current) return;
    if (sessionType === "interview" && !sessionUid) {
      setConnected(false);
      setReconnecting(false);
      return;
    }

    const params = new URLSearchParams();
    const token = getStoredToken();
    if (token) params.set("token", token);
    if (sessionUid) params.set("session_uid", sessionUid);

    const url = `${WS_BASE}/ws/${sessionType}?${params.toString()}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) {
        ws.close();
        return;
      }
      reconnectAttemptRef.current = 0;
      setConnected(true);
      setReconnecting(false);
      resetHeartbeat();
      onConnected?.();
    };

    ws.onmessage = (msg) => {
      try {
        const event: WSEvent = JSON.parse(msg.data);
        if (event.event === "heartbeat") {
          resetHeartbeat();
          return;
        }
        setEvents((prev) => [event, ...prev.slice(0, 199)]);
        onEvent?.(event);
      } catch {
        // non-JSON
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setConnected(false);
      onDisconnected?.();
      reconnectAttemptRef.current += 1;
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [sessionType, sessionUid, onEvent, onConnected, onDisconnected, resetHeartbeat, scheduleReconnect, cleanup]);

  connectRef.current = disconnectAndConnect;

  useEffect(() => {
    mountedRef.current = true;
    disconnectAndConnect();
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [disconnectAndConnect, cleanup]);

  const subscribe = useCallback((channel: string) => {
    wsRef.current?.send(JSON.stringify({ type: "subscribe", channel }));
  }, []);

  const send = useCallback((eventType: string, data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: eventType, data }));
    }
  }, []);

  const sendBinary = useCallback((data: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  return { connected, reconnecting, events, send, sendBinary, subscribe, ws: wsRef };
}


export function useInterviewWebSocket(
  sessionUid: string,
  userId: string,
  interviewType: string,
  onEvent?: (event: WSEvent) => void,
) {
  return useRealtimeWebSocket({
    userId,
    sessionType: "interview",
    sessionUid,
    onEvent,
  });
}
