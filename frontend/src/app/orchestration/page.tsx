"use client";
import { useState, useEffect, useCallback } from "react";

interface OrchestrationSession {
  session_uid: string;
  status: string;
  current_node: string;
  completion_pct: number;
  started_at?: string;
  completed_at?: string;
  should_notify: boolean;
  governance_verdict?: Record<string, unknown>;
  trace?: Record<string, unknown>;
  errors: string[];
}

interface ActiveWorkers {
  total: number;
  active: number;
  idle: number;
  capacity_pct: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getToken(): string {
  try { return localStorage.getItem("careeros_token") || ""; } catch { return ""; }
}

function authHeaders(json = false) {
  const h: Record<string, string> = { Authorization: `Bearer ${getToken()}` };
  if (json) h["Content-Type"] = "application/json";
  return h;
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

export default function OrchestrationPage() {
  const [sessions, setSessions] = useState<OrchestrationSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [userId, setUserId] = useState("");
  const [error, setError] = useState("");
  const [workers, setWorkers] = useState<ActiveWorkers>({ total: 0, active: 0, idle: 0, capacity_pct: 0 });
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<OrchestrationSession | null>(null);
  const completedCount = sessions.filter((s) => s.status === "completed" || s.status === "success").length;
  const runningCount = sessions.filter((s) => s.status === "active").length;

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/orchestration/history?limit=20`, {
        headers: authHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (e) {
      // API not available
    }
    setLoading(false);
  }, []);

  const fetchWorkers = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/orchestration/health`, {
        headers: authHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setWorkers({
          total: data.active_sessions || 0,
          active: data.active_sessions || 0,
          idle: 0,
          capacity_pct: data.graph_compiled ? 100 : 0,
        });
      }
    } catch {
      // offline
    }
  }, []);

  useEffect(() => {
    fetchSessions();
    fetchWorkers();
    const interval = setInterval(() => {
      fetchSessions();
      if (selectedSession) fetchSessionDetail(selectedSession);
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchSessions, fetchWorkers, selectedSession]);

  const fetchSessionDetail = async (sid: string) => {
    try {
      const res = await fetch(`${API_BASE}/orchestration/status/${sid}`, {
        headers: authHeaders(),
      });
      if (res.ok) {
        setSessionDetail(await res.json());
      }
    } catch {
      // skip
    }
  };

  const trigger = async () => {
    if (!userId.trim()) return;
    setTriggering(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/orchestration/trigger`, {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({ user_id: userId, auto_execute: true }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || "Trigger failed");
      } else {
        const session = await res.json();
        setSessions((prev) => [session, ...prev]);
        setSelectedSession(session.session_uid);
      }
    } catch (e) {
      setError("API connection failed");
    }
    setTriggering(false);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "success":
      case "completed": return "bg-green-500";
      case "failed": return "bg-red-500";
      case "cancelled": return "bg-yellow-500";
      case "active": return "bg-blue-500 animate-pulse";
      default: return "bg-gray-500";
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-900 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div>
            <h1 className="text-2xl font-bold text-white">CareerOS Automation Center</h1>
            <p className="text-sm text-gray-400">Shows what CareerOS is doing behind the scenes for a user</p>
          </div>
          <div className="flex items-center gap-4">
            <a href="/orchestration/live" className="text-sm text-blue-400 hover:text-blue-300">Now</a>
            <a href="/orchestration/history" className="text-sm text-blue-400 hover:text-blue-300">Past Runs</a>
            <a href="/orchestration/governance" className="text-sm text-blue-400 hover:text-blue-300">Rules</a>
            <a href="/orchestration/traces" className="text-sm text-blue-400 hover:text-blue-300">Trace Log</a>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        <div className="bg-blue-950/30 border border-blue-800 rounded-lg p-4 mb-6">
          <p className="text-sm text-blue-100 font-medium mb-1">What this page means</p>
          <p className="text-sm text-blue-200/90">
            CareerOS is like a helper that watches your profile, checks jobs, and decides whether to keep going, ask for approval, or send an alert.
          </p>
          <div className="grid gap-3 md:grid-cols-3 mt-4 text-sm">
            <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-3">
              <p className="text-blue-300 font-semibold mb-1">1. Pick a user</p>
              <p className="text-gray-300">Tell CareerOS which account to run for.</p>
            </div>
            <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-3">
              <p className="text-blue-300 font-semibold mb-1">2. It checks everything</p>
              <p className="text-gray-300">It reads the resume, job match, and decision rules.</p>
            </div>
            <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-3">
              <p className="text-blue-300 font-semibold mb-1">3. You see the result</p>
              <p className="text-gray-300">You can see if it is running, finished, or needs a decision.</p>
            </div>
          </div>
        </div>

        {/* Health Cards */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-400">Work in progress</p>
            <p className="text-2xl font-bold text-white">{runningCount}</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-400">Automation engine</p>
            <p className="text-2xl font-bold text-green-400">Ready</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-400">System capacity</p>
            <div className="mt-1 h-2 bg-gray-800 rounded-full">
              <div className="h-2 bg-green-500 rounded-full" style={{ width: `${Math.max(workers.capacity_pct, 5)}%` }} />
            </div>
          </div>
        </div>

        {/* Trigger */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6">
          <h2 className="text-lg font-semibold mb-3">Run for one user</h2>
          <div className="flex gap-3">
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="Enter user ID or email"
              className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={trigger}
              disabled={triggering || !userId.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 rounded text-sm font-medium transition-colors"
            >
              {triggering ? "Working..." : "Start check"}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            This tells CareerOS to review the chosen user and prepare the next action.
          </p>
          {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
        </div>

        {/* Sessions List */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800">
            <h2 className="text-lg font-semibold">Recent runs</h2>
          </div>
          {loading ? (
            <div className="p-8 text-center text-gray-500">Loading...</div>
          ) : sessions.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <p className="text-lg mb-2">No runs yet</p>
              <p className="text-sm">Enter a user ID or email, then click Start check</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-800">
              {sessions.map((s) => (
                <div
                  key={s.session_uid}
                  onClick={() => { setSelectedSession(s.session_uid); fetchSessionDetail(s.session_uid); }}
                  className={`px-4 py-3 hover:bg-gray-800/50 cursor-pointer transition-colors ${
                    selectedSession === s.session_uid ? "bg-gray-800" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${getStatusColor(s.status)}`} />
                      <div>
                        <p className="text-sm font-medium text-white truncate max-w-xs">Run {s.session_uid.slice(0, 8)}...</p>
                        <p className="text-xs text-gray-400">Current step: {NODE_NAMES[s.current_node] || s.current_node}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-white">{s.completion_pct.toFixed(0)}%</p>
                      <p className="text-xs text-gray-500 capitalize">{s.status === "active" ? "In progress" : s.status}</p>
                    </div>
                  </div>
                  {s.status === "active" && (
                    <div className="mt-2 h-1 bg-gray-800 rounded-full">
                      <div className="h-1 bg-blue-500 rounded-full transition-all" style={{ width: `${s.completion_pct}%` }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Session Detail */}
        {sessionDetail && (
          <div className="mt-6 bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-3">What happened in this run: {sessionDetail.session_uid.slice(0, 12)}...</h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-400">Status</p>
                <p className="text-white capitalize">{sessionDetail.status}</p>
              </div>
              <div>
                <p className="text-gray-400">Progress</p>
                <p className="text-white">{sessionDetail.completion_pct.toFixed(0)}%</p>
              </div>
              <div>
                <p className="text-gray-400">What it is doing now</p>
                <p className="text-white">{NODE_NAMES[sessionDetail.current_node] || sessionDetail.current_node}</p>
              </div>
              <div>
                <p className="text-gray-400">Needs your attention</p>
                <p className={sessionDetail.should_notify ? "text-green-400" : "text-gray-500"}>
                  {sessionDetail.should_notify ? "Yes" : "No"}
                </p>
              </div>
              {sessionDetail.governance_verdict && (
                <div className="col-span-2">
                  <p className="text-gray-400 mb-1">Decision summary</p>
                  <pre className="bg-gray-800 rounded p-2 text-xs text-gray-300 overflow-x-auto">
                    {JSON.stringify(sessionDetail.governance_verdict, null, 2)}
                  </pre>
                </div>
              )}
              {sessionDetail.errors.length > 0 && (
                <div className="col-span-2">
                  <p className="text-red-400 mb-1">Problems found</p>
                  {sessionDetail.errors.map((e, i) => (
                    <p key={i} className="text-red-300 text-xs">{e}</p>
                  ))}
                </div>
              )}
              <div className="col-span-2 text-xs text-gray-400">
                {completedCount > 0 ? `Completed runs so far: ${completedCount}` : "Completed runs will appear here after the system finishes a user check."}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
