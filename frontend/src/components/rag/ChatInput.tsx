"use client";

import { ArrowUpRight, Loader2, Lock } from "lucide-react";
import { useMemo } from "react";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
  disabled: boolean;
  placeholder?: string;
}

export default function ChatInput({
  value,
  onChange,
  onSubmit,
  loading,
  disabled,
  placeholder = "Ask about CareerOS...",
}: ChatInputProps) {
  const canSend = useMemo(() => value.trim().length > 0 && !loading && !disabled, [value, loading, disabled]);

  return (
    <div className="border-t border-white/10 bg-slate-950/95 p-3 backdrop-blur-xl">
      <label className="sr-only" htmlFor="demo-rag-chat-input">
        Chat prompt
      </label>
      <textarea
        id="demo-rag-chat-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (canSend) onSubmit();
          }
        }}
        placeholder={placeholder}
        rows={3}
        disabled={disabled}
        className="w-full resize-none rounded-2xl border border-slate-800 bg-slate-900/90 px-4 py-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-60"
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <p className="text-[11px] text-slate-500">
          Enter to send, Shift+Enter for a new line.
        </p>
        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSend}
          className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-cyan-500 to-indigo-500 px-4 py-2.5 text-sm font-medium text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <ArrowUpRight className="h-4 w-4" aria-hidden="true" />}
          {loading ? "Sending..." : "Send"}
        </button>
      </div>
      {disabled && (
        <div className="mt-3 flex items-center gap-2 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          <Lock className="h-3.5 w-3.5" />
          Sign in to continue the conversation.
        </div>
      )}
    </div>
  );
}

