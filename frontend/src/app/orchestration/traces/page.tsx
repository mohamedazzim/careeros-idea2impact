"use client";
import { useState, useEffect, useCallback } from "react";
import { formatDateTimeLocal } from "@/lib/datetime";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getToken(): string {
  try { return localStorage.getItem("careeros_token") || ""; } catch { return ""; }
}

interface TraceEntry {
  session_uid: string;
  trace_id?: string;
  why_happened?: string[];
  evidence?: Record<string, unknown>;
  governance_verdict?: string;
  confidence?: number;
  created_at?: string;
}

export default function TracesPage() {
  const [traces, setTraces] = useState<TraceEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchTraces = useCallback(async () => {
    const token = getToken();
    try {
      const res = await fetch(`${API_BASE}/orchestration/traces?limit=20`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setTraces(data.traces || data.sessions?.filter((s: { trace?: unknown }) => s.trace) || []);
      }
    } catch {
      // API not available
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchTraces();
  }, [fetchTraces]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <div className="border-b border-gray-800 bg-gray-900 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold text-white">Trace Log</h1>
          <a href="/orchestration" className="text-sm text-blue-400 hover:text-blue-300">← Back to overview</a>
        </div>
      </div>
      <div className="max-w-7xl mx-auto p-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Why the system chose this</h2>
          {loading ? (
            <div className="p-6 text-center text-gray-500">Loading traces...</div>
          ) : traces.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              <p className="text-sm">No trace entries yet.</p>
              <p className="text-xs mt-1">This will fill with simple reasons and evidence after CareerOS makes a decision.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {traces.map((trace, i) => (
                <div key={trace.session_uid || i} className="border border-gray-800 rounded p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-medium text-white">Trace #{i + 1}</h3>
                    <span className="text-xs text-gray-500">Session: {trace.session_uid?.slice(0, 12) || "unknown"}</span>
                  </div>
                  <div className="space-y-2 text-sm">
                    {trace.why_happened && trace.why_happened.length > 0 && (
                      <div className="flex gap-2">
                        <span className="text-gray-500">Reason:</span>
                        <span className="text-gray-300">{trace.why_happened.join(". ")}</span>
                      </div>
                    )}
                    {trace.evidence && (
                      <div className="flex gap-2">
                        <span className="text-gray-500">Proof:</span>
                        <span className="text-gray-300 font-mono text-xs">{JSON.stringify(trace.evidence)}</span>
                      </div>
                    )}
                    {trace.governance_verdict && (
                      <div className="flex gap-2">
                        <span className="text-gray-500">Rule result:</span>
                        <span className={trace.governance_verdict === "passed" ? "text-green-400" : "text-yellow-400"}>
                          {trace.governance_verdict}
                        </span>
                      </div>
                    )}
                    {trace.confidence !== undefined && (
                      <div className="flex gap-2">
                        <span className="text-gray-500">Confidence:</span>
                        <span className="text-gray-300">{(trace.confidence * 100).toFixed(1)}%</span>
                      </div>
                    )}
                    {trace.created_at && (
                      <p className="text-xs text-gray-600">{formatDateTimeLocal(trace.created_at)}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
