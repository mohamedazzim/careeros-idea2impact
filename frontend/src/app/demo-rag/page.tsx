"use client";

import { useState } from "react";

type Citation = {
  doc_name?: string;
  section_title?: string;
  source_path?: string;
  score?: number;
};

type RagResponse = {
  status: string;
  answer: string;
  confidence: number;
  citations: Citation[];
  follow_up_questions: string[];
  needs_verification: boolean;
  error?: { code?: string; message?: string };
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function DemoRagPage() {
  const [sessionId, setSessionId] = useState("mentor-demo-session");
  const [viewerRole, setViewerRole] = useState("mentor");
  const [topK, setTopK] = useState(6);
  const [question, setQuestion] = useState("Which agents are implemented?");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [response, setResponse] = useState<RagResponse | null>(null);

  const askQuestion = async () => {
    const normalizedQuestion = question.trim();
    if (!normalizedQuestion) {
      setError("Please enter a question.");
      return;
    }

    setLoading(true);
    setError("");
    setResponse(null);

    try {
      const token = typeof window !== "undefined" ? window.localStorage.getItem("careeros_token") : "";
      const res = await fetch(`${API_BASE}/demo-rag/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          session_id: sessionId.trim(),
          question: normalizedQuestion,
          viewer_role: viewerRole.trim() || "mentor",
          top_k: topK,
        }),
      });

      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const message = data?.detail?.message || data?.detail || "RAG service unavailable.";
        throw new Error(message);
      }
      if (data?.status === "error") {
        throw new Error(data?.error?.message || "RAG service returned an error.");
      }
      setResponse(data as RagResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "RAG service unavailable.");
    } finally {
      setLoading(false);
    }
  };

  const sampleQuestions = [
    "Which agents are implemented?",
    "How does job matching work?",
    "What does the voice-call workflow do?",
    "What are the main limitations?",
  ];

  return (
    <div className="min-h-screen bg-slate-950 px-6 py-8 text-slate-100">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="rounded-3xl border border-slate-800 bg-slate-900/85 p-6 shadow-2xl shadow-cyan-950/20">
          <p className="text-xs uppercase tracking-[0.3em] text-cyan-300">Demo RAG</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">CareerOS mentor and HR chatbot</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Ask about the implementation, agents, workflows, APIs, and limitations. The backend validates the question, retrieves docs from `docs/rag/`, and returns cited answers.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <section className="rounded-3xl border border-slate-800 bg-slate-900 p-6">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm">
                <span className="text-slate-400">Session ID</span>
                <input
                  className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-cyan-400"
                  value={sessionId}
                  onChange={(e) => setSessionId(e.target.value)}
                />
              </label>
              <label className="space-y-2 text-sm">
                <span className="text-slate-400">Viewer role</span>
                <input
                  className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-cyan-400"
                  value={viewerRole}
                  onChange={(e) => setViewerRole(e.target.value)}
                />
              </label>
            </div>

            <label className="mt-4 block space-y-2 text-sm">
              <span className="text-slate-400">Question</span>
              <textarea
                className="min-h-36 w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-cyan-400"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask anything about CareerOS"
              />
            </label>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-3 text-sm text-slate-400">
                <span>Top K</span>
                <input
                  type="number"
                  min={1}
                  max={12}
                  className="w-24 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400"
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value) || 6)}
                />
              </label>

              <button
                type="button"
                onClick={askQuestion}
                disabled={loading}
                className="rounded-2xl bg-cyan-500 px-5 py-3 font-medium text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? "Thinking..." : "Ask chatbot"}
              </button>
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              {sampleQuestions.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setQuestion(item)}
                  className="rounded-full border border-slate-700 px-4 py-2 text-xs text-slate-300 transition hover:border-cyan-400 hover:text-cyan-300"
                >
                  {item}
                </button>
              ))}
            </div>

            {error && (
              <div className="mt-6 rounded-2xl border border-rose-700 bg-rose-950/40 p-4 text-sm text-rose-200">
                {error}
              </div>
            )}
          </section>

          <section className="rounded-3xl border border-slate-800 bg-slate-900 p-6">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-lg font-semibold text-white">Response</h2>
              {response && (
                <div className="flex items-center gap-2">
                  <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">
                    Confidence {Math.round((response.confidence || 0) * 100)}%
                  </span>
                  {response.needs_verification && (
                    <span className="rounded-full border border-amber-700 bg-amber-950/40 px-3 py-1 text-xs text-amber-200">
                      Needs verification
                    </span>
                  )}
                </div>
              )}
            </div>

            {!response && !error && (
              <div className="mt-6 rounded-2xl border border-dashed border-slate-700 p-6 text-sm text-slate-400">
                Ask a question to see the answer, citations, and follow-up suggestions.
              </div>
            )}

            {response && (
              <div className="mt-6 space-y-6">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Answer</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-100">{response.answer || "No answer returned."}</p>
                </div>

                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Citations</p>
                  <div className="mt-2 space-y-3">
                    {response.citations?.length ? (
                      response.citations.map((citation, index) => (
                        <div key={`${citation.source_path ?? "citation"}-${index}`} className="rounded-2xl border border-slate-700 bg-slate-950 p-4 text-sm">
                          <p className="font-medium text-cyan-300">{citation.doc_name || "Source file"}</p>
                          <p className="mt-1 text-slate-300">{citation.section_title || "Section not provided"}</p>
                          <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-500">
                            {citation.source_path || "docs/rag"} · score {(citation.score || 0).toFixed(2)}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-400">No citations returned.</p>
                    )}
                  </div>
                </div>

                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Follow-up questions</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {response.follow_up_questions?.length ? (
                      response.follow_up_questions.map((item) => (
                        <span key={item} className="rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-300">
                          {item}
                        </span>
                      ))
                    ) : (
                      <p className="text-sm text-slate-400">No follow-up questions returned.</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
