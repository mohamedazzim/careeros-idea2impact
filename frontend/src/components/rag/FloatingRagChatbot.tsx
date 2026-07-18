"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import ChatLauncher from "@/components/rag/ChatLauncher";
import ChatPanel from "@/components/rag/ChatPanel";
import type {
  DemoRagChatResponse,
  DemoRagError,
  RagChatMessage,
  RagPanelState,
} from "@/types/demo-rag";
import {
  DemoRagApiError,
  getOrCreateDemoRagSessionId,
  setDemoRagSessionId,
  submitDemoRagChat,
} from "@/lib/demo-rag";
import { readAuthToken } from "@/lib/auth-session";
import { isPublicRoute } from "@/lib/rbac";

const MESSAGES_KEY = "careeros_demo_rag_messages_v1";
const PANEL_KEY = "careeros_demo_rag_panel_state_v1";
const DRAFT_KEY = "careeros_demo_rag_draft_v1";

function createMessageId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function defaultWelcomeMessage(): RagChatMessage {
  return {
    id: createMessageId("assistant"),
    role: "assistant",
    content:
      "Hi, I'm the CareerOS docs assistant. Ask me about implemented features, agents, workflows, APIs, or limitations.",
    createdAt: Date.now(),
    followUpQuestions: [
      "Which agents are implemented?",
      "How does the RAG pipeline work?",
      "What are the current limitations?",
    ],
  };
}

function safeParse<T>(value: string | null, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function loadMessages(): RagChatMessage[] {
  if (typeof window === "undefined") return [defaultWelcomeMessage()];
  try {
    const stored = window.localStorage.getItem(MESSAGES_KEY);
    const parsed = safeParse<RagChatMessage[]>(stored, []);
    return parsed.length ? parsed : [defaultWelcomeMessage()];
  } catch {
    return [defaultWelcomeMessage()];
  }
}

function loadPanelState(): RagPanelState {
  if (typeof window === "undefined") return "closed";
  try {
    const stored = window.localStorage.getItem(PANEL_KEY);
    if (stored === "open" || stored === "minimized" || stored === "maximized" || stored === "closed") {
      return stored;
    }
  } catch {
    // ignore
  }
  return "closed";
}

function saveJson(key: string, value: unknown): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore storage failures
  }
}

function mapChatResponseToMessage(response: DemoRagChatResponse): RagChatMessage {
  return {
    id: createMessageId("assistant"),
    role: "assistant",
    content: response.answer || "No answer returned.",
    createdAt: Date.now(),
    confidence: response.confidence,
    citations: response.citations,
    followUpQuestions: response.follow_up_questions,
    needsVerification: response.needs_verification,
    error: response.error ?? null,
  };
}

function mapErrorToMessage(error: unknown): RagChatMessage {
  if (error instanceof DemoRagApiError) {
    const detail: DemoRagError = {
      code: error.code ?? (error.loginRequired ? "AUTH_REQUIRED" : "RAG_ERROR"),
      message: error.message,
    };
    return {
      id: createMessageId("assistant"),
      role: "assistant",
      content: error.message,
      createdAt: Date.now(),
      error: detail,
      needsVerification: true,
      followUpQuestions: [],
    };
  }

  const message = error instanceof Error ? error.message : "The CareerOS RAG service is temporarily unavailable.";
  return {
    id: createMessageId("assistant"),
    role: "assistant",
    content: message,
    createdAt: Date.now(),
    error: { code: "RAG_ERROR", message },
    needsVerification: true,
    followUpQuestions: [],
  };
}

export default function FloatingRagChatbot() {
  const pathname = usePathname();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [sessionId] = useState<string>(() => getOrCreateDemoRagSessionId());
  const [panelState, setPanelState] = useState<RagPanelState>(() => loadPanelState());
  const [draft, setDraft] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    try {
      return window.localStorage.getItem(DRAFT_KEY) || "";
    } catch {
      return "";
    }
  });
  const [messages, setMessages] = useState<RagChatMessage[]>(() => loadMessages());
  const [loading, setLoading] = useState(false);
  const [authToken, setAuthToken] = useState<string | null>(() => readAuthToken());
  const [sessionExpired, setSessionExpired] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const signedIn = Boolean(authToken);
  const canRender = mounted && signedIn && !isPublicRoute(pathname);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    setDemoRagSessionId(sessionId);
    saveJson(MESSAGES_KEY, messages);
  }, [sessionId, messages]);

  useEffect(() => {
    saveJson(PANEL_KEY, panelState);
  }, [panelState]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(DRAFT_KEY, draft);
    } catch {
      // ignore
    }
  }, [draft]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, panelState]);

  useEffect(() => {
    const syncAuth = () => {
      setAuthToken(readAuthToken());
    };

    const handleStorage = (event: StorageEvent) => {
      if (event.key && event.key !== "careeros_token") return;
      syncAuth();
    };

    syncAuth();
    window.addEventListener("storage", handleStorage);
    window.addEventListener("focus", syncAuth);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("focus", syncAuth);
    };
  }, []);

  useEffect(() => {
    if (!messages.length) {
      setMessages([defaultWelcomeMessage()]);
    }
  }, [messages.length]);

  const openPanel = () => {
    setPanelState("open");
  };

  const closePanel = () => {
    setPanelState("closed");
  };

  const minimizePanel = () => {
    setPanelState("minimized");
  };

  const toggleMaximize = () => {
    setPanelState((current) => (current === "maximized" ? "open" : "maximized"));
  };

  const restorePanel = () => {
    setPanelState("open");
  };

  const login = () => {
    const redirect = pathname || "/";
    router.push(`/login?redirect=${encodeURIComponent(redirect)}`);
  };

  const sendQuestion = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    const userMessage: RagChatMessage = {
      id: createMessageId("user"),
      role: "user",
      content: trimmed,
      createdAt: Date.now(),
    };
    const pendingMessage: RagChatMessage = {
      id: createMessageId("assistant"),
      role: "assistant",
      content: "Thinking...",
      createdAt: Date.now(),
      pending: true,
    };

    setMessages((current) => [...current, userMessage, pendingMessage]);
    setDraft("");
    setSessionExpired(false);
    setLoading(true);

    try {
      const response = await submitDemoRagChat({
        session_id: sessionId,
        question: trimmed,
        viewer_role: "mentor",
        top_k: 6,
      });

      const assistantMessage = mapChatResponseToMessage(response);
      setMessages((current) => {
        const next = [...current];
        const pendingIndex = next.map((item) => item.pending).lastIndexOf(true);
        if (pendingIndex >= 0) {
          next.splice(pendingIndex, 1, assistantMessage);
          return next;
        }
        return [...next, assistantMessage];
      });
    } catch (error) {
      const assistantMessage = mapErrorToMessage(error);
      if (error instanceof DemoRagApiError && error.loginRequired) {
        setSessionExpired(true);
      }
      setMessages((current) => {
        const next = [...current];
        const pendingIndex = next.map((item) => item.pending).lastIndexOf(true);
        if (pendingIndex >= 0) {
          next.splice(pendingIndex, 1, assistantMessage);
          return next;
        }
        return [...next, assistantMessage];
      });
    } finally {
      setLoading(false);
      if (panelState === "closed") {
        setPanelState("open");
      }
    }
  };

  const handleFollowUpClick = (question: string) => {
    setDraft(question);
    void sendQuestion(question);
  };

  if (!canRender) {
    return null;
  }

  const visible = panelState !== "closed";
  const minimized = panelState === "minimized";

  return (
    <div className="pointer-events-none fixed inset-0 z-50">
      <div className="absolute bottom-4 right-4 max-sm:bottom-3 max-sm:right-3">
        {!visible ? (
          <ChatLauncher mode={panelState} onOpen={openPanel} onRestore={restorePanel} onClose={closePanel} />
        ) : minimized ? (
          <ChatLauncher
            mode={panelState}
            onOpen={openPanel}
            onRestore={restorePanel}
            onClose={closePanel}
          />
        ) : (
          <ChatPanel
            mode={panelState === "maximized" ? "maximized" : "open"}
            messages={messages}
            draft={draft}
            loading={loading}
            signedIn={signedIn}
            sessionExpired={sessionExpired}
            messagesEndRef={messagesEndRef}
            onDraftChange={setDraft}
            onSubmit={() => void sendQuestion(draft)}
            onFollowUpClick={handleFollowUpClick}
            onMinimize={minimizePanel}
            onToggleMaximize={toggleMaximize}
            onClose={closePanel}
            onLogin={login}
          />
        )}
      </div>
    </div>
  );
}
