"use client";

import { Maximize2, Minimize2, X } from "lucide-react";
import ChatInput from "@/components/rag/ChatInput";
import ChatMessageList from "@/components/rag/ChatMessageList";
import type { RagChatMessage, RagPanelState } from "@/types/demo-rag";
import type { RefObject } from "react";

interface ChatPanelProps {
  mode: Exclude<RagPanelState, "closed" | "minimized">;
  messages: RagChatMessage[];
  draft: string;
  loading: boolean;
  signedIn: boolean;
  sessionExpired: boolean;
  messagesEndRef: RefObject<HTMLDivElement>;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
  onFollowUpClick: (question: string) => void;
  onMinimize: () => void;
  onToggleMaximize: () => void;
  onClose: () => void;
  onLogin: () => void;
}

export default function ChatPanel({
  mode,
  messages,
  draft,
  loading,
  signedIn,
  sessionExpired,
  messagesEndRef,
  onDraftChange,
  onSubmit,
  onFollowUpClick,
  onMinimize,
  onToggleMaximize,
  onClose,
  onLogin,
}: ChatPanelProps) {
  const shellClasses =
    mode === "maximized"
      ? "fixed inset-2 sm:inset-4 md:inset-6 h-[calc(100vh-1rem)] w-[calc(100vw-1rem)] md:h-auto md:w-[min(900px,calc(100vw-3rem))]"
      : "fixed bottom-4 right-4 left-4 sm:left-auto sm:w-[min(440px,calc(100vw-2rem))] h-[min(78vh,760px)] sm:h-[min(680px,calc(100vh-2rem))]";

  return (
    <section
      className={`${shellClasses} pointer-events-auto z-50 flex flex-col overflow-hidden rounded-[28px] border border-white/10 bg-slate-950/95 shadow-[0_30px_100px_rgba(2,6,23,0.62)] backdrop-blur-xl`}
      role="dialog"
      aria-label="CareerOS RAG chatbot"
      aria-modal="true"
    >
      <header className="flex items-start justify-between gap-3 border-b border-white/10 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 px-4 py-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-300">
            CareerOS RAG
          </p>
          <h2 className="mt-1 text-lg font-semibold text-white">
            Mentor / HR docs assistant
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Answers from docs, Qdrant Cloud, and Make.com relay.
          </p>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={onMinimize}
            className="rounded-full border border-slate-700 p-2 text-slate-300 transition hover:border-cyan-400 hover:text-cyan-200"
            aria-label="Minimize chatbot"
          >
            <Minimize2 className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onToggleMaximize}
            className="rounded-full border border-slate-700 p-2 text-slate-300 transition hover:border-cyan-400 hover:text-cyan-200"
            aria-label={mode === "maximized" ? "Restore chatbot size" : "Maximize chatbot"}
          >
            <Maximize2 className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-700 p-2 text-slate-300 transition hover:border-rose-400 hover:text-rose-200"
            aria-label="Close chatbot"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </header>

      {sessionExpired && (
        <div className="border-b border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          Your session expired or is missing. Sign in again to continue asking questions.
          <button
            type="button"
            onClick={onLogin}
            className="ml-3 rounded-full border border-amber-300/30 px-3 py-1.5 text-xs font-medium text-amber-50 transition hover:bg-amber-300/10"
          >
            Sign in
          </button>
        </div>
      )}

      {!signedIn && !sessionExpired && (
        <div className="border-b border-slate-800 bg-slate-900/70 px-4 py-3 text-sm text-slate-300">
          Sign in to ask the chatbot about CareerOS docs and workflows.
          <button
            type="button"
            onClick={onLogin}
            className="ml-3 rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-100 transition hover:bg-cyan-500/20"
          >
            Open login
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.08),_transparent_34%),linear-gradient(180deg,rgba(15,23,42,0.75),rgba(2,6,23,0.95))]">
        <ChatMessageList
          messages={messages}
          loading={loading}
          onFollowUpClick={onFollowUpClick}
          endRef={messagesEndRef}
        />
      </div>

      <ChatInput
        value={draft}
        onChange={onDraftChange}
        onSubmit={onSubmit}
        loading={loading}
        disabled={!signedIn}
      />
    </section>
  );
}
