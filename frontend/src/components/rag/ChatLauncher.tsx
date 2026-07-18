"use client";

import { Bot, MessageSquareMore, Sparkles, X } from "lucide-react";
import type { RagPanelState } from "@/types/demo-rag";

interface ChatLauncherProps {
  mode: RagPanelState;
  onOpen: () => void;
  onRestore: () => void;
  onClose: () => void;
  unreadCount?: number;
}

export default function ChatLauncher({
  mode,
  onOpen,
  onRestore,
  onClose,
  unreadCount = 0,
}: ChatLauncherProps) {
  if (mode === "closed") {
    return (
      <button
        type="button"
        onClick={onOpen}
        className="group pointer-events-auto flex items-center gap-3 rounded-full border border-cyan-400/20 bg-gradient-to-r from-cyan-500 to-indigo-500 px-4 py-3 text-left text-white shadow-[0_20px_60px_rgba(8,145,178,0.35)] transition duration-200 hover:scale-[1.02] hover:shadow-[0_24px_70px_rgba(59,130,246,0.42)] focus:outline-none focus:ring-2 focus:ring-cyan-300"
        aria-label="Open CareerOS RAG chatbot"
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/15">
          <Bot className="h-5 w-5" aria-hidden="true" />
        </span>
        <span className="min-w-0">
          <span className="block text-xs font-semibold uppercase tracking-[0.28em] text-cyan-100/80">
            CareerOS RAG
          </span>
          <span className="block text-sm font-medium text-white">
            Ask the docs chatbot
          </span>
        </span>
        <span className="flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-medium text-cyan-50">
          <Sparkles className="h-3.5 w-3.5" />
          Live
        </span>
        {unreadCount > 0 && (
          <span className="ml-1 flex h-6 min-w-6 items-center justify-center rounded-full bg-white text-xs font-semibold text-slate-900">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>
    );
  }

  return (
    <div className="pointer-events-auto flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/95 px-4 py-3 text-slate-100 shadow-[0_20px_60px_rgba(2,6,23,0.55)] backdrop-blur-xl">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-indigo-500 text-white">
        <MessageSquareMore className="h-5 w-5" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-white">CareerOS RAG</p>
        <p className="text-xs text-slate-400">
          {mode === "minimized" ? "Conversation minimized" : "Conversation restored"}
        </p>
      </div>
      <button
        type="button"
        onClick={onRestore}
        className="rounded-full border border-slate-700 px-3 py-2 text-xs font-medium text-slate-200 transition hover:border-cyan-400 hover:text-cyan-200"
        aria-label="Restore chatbot panel"
      >
        Restore
      </button>
      <button
        type="button"
        onClick={onClose}
        className="rounded-full border border-slate-700 p-2 text-slate-400 transition hover:border-rose-400 hover:text-rose-300"
        aria-label="Close chatbot panel"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

