"use client";
import { useState, useEffect, useCallback } from "react";
import { formatTimeLocal } from "@/lib/datetime";

interface LiveEvent {
  event_type: string;
  node?: string;
  completion_pct?: number;
  timestamp: number;
  session_uid: string;
}

interface LiveSession {
  session_uid: string;
  status: string;
  current_node: string;
  completion_pct: number;
  started_at?: string;
}

const NODE_NAMES: Record<string, string> = {
  retrieve_candidate_context: "Candidate Context",
  retrieve_resume_context: "Resume Context",
  retrieve_market_context: "Market Signals",
  retrieve_deadline_context: "Deadline (removed)",
  evaluate_opportunity_fit: "Fit Scoring",
  evaluate_urgency: "Urgency Eval",
  generate_priority_score: "Priority Ranking",
  governance_validation: "Governance",
  notification_decision: "Notification Decision",
  voice_synthesis: "Voice Synthesis",
  twilio_call_execution: "Call Execution",
  trace_compilation: "Trace Compilation",
};

const PIPELINE_NODES = Object.keys(NODE_NAMES);
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getToken(): string {
  try { return localStorage.getItem("careeros_token") || ""; } catch { return ""; }
}

export default function LiveOrchestrationPage() {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [currentNode, setCurrentNode] = useState("");
  const [completionPct, setCompletionPct] = useState(0);
  const [activeSessions, setActiveSessions] = useState<LiveSession[]>([]);

  const fetchLiveData = useCallback(async () => {
    const token = getToken();
    try {
      const res = await fetch(`${API_BASE}/orchestration/history?limit=10`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const sessions: LiveSession[] = data.sessions || [];
        setActiveSessions(sessions);

        const active = sessions.find((s) => s.status === "active");
        if (active) {
          setCurrentNode(active.current_node);
          setCompletionPct(active.completion_pct);
          setEvents((prev) => [
            {
              event_type: "node_executed",
              node: active.current_node,
              completion_pct: active.completion_pct,
              timestamp: Date.now(),
              session_uid: active.session_uid,
            },
            ...prev.slice(0, 49),
          ]);
        }
      }
    } catch {
      // API not available
    }
  }, []);

  useEffect(() => {
    fetchLiveData();
    const interval = setInterval(fetchLiveData, 5000);
    return () => clearInterval(interval);
  }, [fetchLiveData]);

  const completedNodes = currentNode
    ? PIPELINE_NODES.slice(0, PIPELINE_NODES.indexOf(currentNode))
    : [];

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <div className="border-b border-gray-800 bg-gray-900 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div>
            <h1 className="text-2xl font-bold text-white">Now</h1>
            <p className="text-sm text-gray-400">Shows what CareerOS is doing right this moment</p>
          </div>
          <a href="/orchestration" className="text-sm text-blue-400 hover:text-blue-300">← Back to overview</a>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* Pipeline Visualization */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">What is happening now</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
            {PIPELINE_NODES.map((node) => {
              const isCurrent = node === currentNode;
              const isComplete = completedNodes.includes(node);
              return (
                <div
                  key={node}
                  className={`p-2 rounded text-center text-xs transition-all ${
                    isCurrent ? "bg-blue-600 text-white scale-105" :
                    isComplete ? "bg-green-700 text-green-100" :
                    "bg-gray-800 text-gray-500"
                  }`}
                >
                  {NODE_NAMES[node]}
                </div>
              );
            })}
          </div>
          <div className="mt-4 h-2 bg-gray-800 rounded-full">
            <div
              className="h-2 bg-blue-500 rounded-full transition-all duration-700"
              style={{ width: `${completionPct}%` }}
            />
          </div>
          <p className="text-sm text-gray-400 mt-2">
            Current: {NODE_NAMES[currentNode] || "No active session"} ({completionPct.toFixed(0)}%)
          </p>
        </div>

        {/* Active Sessions */}
        {activeSessions.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Runs in progress ({activeSessions.filter(s => s.status === "active").length})</h2>
            <div className="space-y-2">
              {activeSessions.filter(s => s.status === "active").map((s) => (
                <div key={s.session_uid} className="flex items-center justify-between p-3 bg-gray-800/50 rounded">
                  <div>
                    <p className="text-sm text-white font-mono">{s.session_uid.slice(0, 12)}...</p>
                    <p className="text-xs text-gray-400">{NODE_NAMES[s.current_node] || s.current_node}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-blue-400">{s.completion_pct.toFixed(0)}%</p>
                    <div className="w-24 h-1 bg-gray-700 rounded-full mt-1">
                      <div className="h-1 bg-blue-500 rounded-full" style={{ width: `${s.completion_pct}%` }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Event Stream */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Activity log</h2>
          {events.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              <p className="text-sm">No activity yet.</p>
              <p className="text-xs mt-1">New entries will appear when CareerOS starts working for a user.</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {events.map((e, i) => (
                <div key={i} className="flex items-center gap-3 text-sm p-2 bg-gray-800/50 rounded">
                  <div className="w-2 h-2 rounded-full bg-green-400" />
                  <span className="text-blue-400 font-mono text-xs">
                    {formatTimeLocal(e.timestamp)}
                  </span>
                  <span className="text-gray-400">{e.event_type}</span>
                  <span className="text-white">{NODE_NAMES[e.node || ""] || e.node}</span>
                  <span className="text-gray-500">{e.completion_pct?.toFixed(0)}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
