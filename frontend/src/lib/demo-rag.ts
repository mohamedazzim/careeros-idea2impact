import type {
  DemoRagChatRequest,
  DemoRagChatResponse,
} from "@/types/demo-rag";
import { readAuthToken } from "@/lib/auth-session";

const API_BASE =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) ||
  "/api/v1";

const SESSION_KEY = "careeros_demo_rag_session_id";

export class DemoRagApiError extends Error {
  status: number;
  code?: string;
  loginRequired: boolean;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "DemoRagApiError";
    this.status = status;
    this.code = code;
    this.loginRequired = status === 401 || status === 403;
  }
}

function safeRandomId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `fallback-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function ensureTrailingSlash(base: string): string {
  return base.endsWith("/") ? base.slice(0, -1) : base;
}

export function getOrCreateDemoRagSessionId(): string {
  if (typeof window === "undefined") {
    return `mentor-demo-session-${safeRandomId()}`;
  }

  try {
    const existing = window.localStorage.getItem(SESSION_KEY);
    if (existing) {
      return existing;
    }
    const sessionId = `mentor-demo-session-${safeRandomId()}`;
    window.localStorage.setItem(SESSION_KEY, sessionId);
    return sessionId;
  } catch {
    return `mentor-demo-session-${safeRandomId()}`;
  }
}

export function setDemoRagSessionId(sessionId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(SESSION_KEY, sessionId);
  } catch {
    // Ignore storage failures so the widget still functions.
  }
}

async function parseJsonResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const record = payload as Record<string, unknown>;
  if (typeof record.message === "string" && record.message.trim()) {
    return record.message.trim();
  }
  const detail = record.detail;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (detail && typeof detail === "object") {
    const nested = detail as Record<string, unknown>;
    if (typeof nested.message === "string" && nested.message.trim()) {
      return nested.message.trim();
    }
  }
  return fallback;
}

export async function submitDemoRagChat(
  request: DemoRagChatRequest,
): Promise<DemoRagChatResponse> {
  const token = readAuthToken();
  if (!token) {
    throw new DemoRagApiError("Sign in to use the CareerOS chatbot.", 401, "AUTH_REQUIRED");
  }

  const response = await fetch(`${ensureTrailingSlash(API_BASE)}/demo-rag/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(request),
  });

  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    const message = extractErrorMessage(
      payload,
      response.status === 401
        ? "Your session expired. Please sign in again."
        : "The CareerOS RAG service is temporarily unavailable.",
    );
    const code =
      payload && typeof payload === "object" && "code" in payload
        ? String((payload as Record<string, unknown>).code ?? "")
        : undefined;
    throw new DemoRagApiError(message, response.status, code);
  }

  if (!payload || typeof payload !== "object") {
    throw new DemoRagApiError("The chatbot returned an unexpected response.", 502, "BAD_RESPONSE");
  }

  return payload as DemoRagChatResponse;
}

