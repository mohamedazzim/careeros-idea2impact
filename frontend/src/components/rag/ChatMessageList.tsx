"use client";

import { BadgeCheck, Bot, MessageSquareQuote, User } from "lucide-react";
import type { RefObject } from "react";
import type { RagChatMessage } from "@/types/demo-rag";
import CitationList from "@/components/rag/CitationList";

interface ChatMessageListProps {
  messages: RagChatMessage[];
  loading: boolean;
  onFollowUpClick: (question: string) => void;
  endRef: RefObject<HTMLDivElement>;
}

export default function ChatMessageList({
  messages,
  loading,
  onFollowUpClick,
  endRef,
}: ChatMessageListProps) {
  return (
    <div className="space-y-4 p-4">
      {messages.map((message) => {
        const isUser = message.role === "user";
        return (
          <article
            key={message.id}
            className={`flex ${isUser ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[88%] rounded-3xl border px-4 py-3 shadow-sm ${
                isUser
                  ? "border-cyan-400/20 bg-gradient-to-br from-cyan-500/20 to-indigo-500/20 text-slate-50"
                  : "border-white/10 bg-slate-900/90 text-slate-100"
              }`}
            >
              <div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">
                {isUser ? (
                  <>
                    <User className="h-3.5 w-3.5" />
                    You
                  </>
                ) : (
                  <>
                    <Bot className="h-3.5 w-3.5" />
                    CareerOS
                  </>
                )}
                {message.pending && (
                  <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] text-slate-300">
                    Thinking
                  </span>
                )}
                {typeof message.confidence === "number" && !message.pending && (
                  <span className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] text-cyan-200">
                    {(message.confidence * 100).toFixed(0)}% confidence
                  </span>
                )}
                {message.needsVerification && (
                  <span className="rounded-full border border-amber-400/20 bg-amber-500/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] text-amber-200">
                    Needs verification
                  </span>
                )}
              </div>

              <div className="whitespace-pre-wrap text-sm leading-6 text-slate-100">
                {message.content || (message.pending ? "Reviewing the docs..." : "")}
              </div>

              {!isUser && message.error?.message && (
                <div className="mt-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">
                  {message.error.message}
                </div>
              )}

              {!isUser && message.citations && message.citations.length > 0 && (
                <div className="mt-4 space-y-2">
                  <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.22em] text-slate-500">
                    <MessageSquareQuote className="h-3.5 w-3.5" />
                    Citations
                  </div>
                  <CitationList citations={message.citations} />
                </div>
              )}

              {!isUser && message.followUpQuestions && message.followUpQuestions.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {message.followUpQuestions.map((question) => (
                    <button
                      key={question}
                      type="button"
                      onClick={() => onFollowUpClick(question)}
                      disabled={loading}
                      className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              )}

              {message.error && (
                <div className="mt-3 flex items-center gap-2 text-xs text-rose-200">
                  <BadgeCheck className="h-3.5 w-3.5" />
                  {message.error.code}
                </div>
              )}
            </div>
          </article>
        );
      })}
      <div ref={endRef} />
    </div>
  );
}
