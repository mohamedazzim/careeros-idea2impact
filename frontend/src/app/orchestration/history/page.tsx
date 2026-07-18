"use client";
import { useState, useEffect } from "react";
import { formatDateTimeLocal } from "@/lib/datetime";

interface HistorySession {
  session_uid: string;
  status: string;
  current_node: string;
  completion_pct: number;
  started_at?: string;
  user_id?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getToken(): string {
  try { return localStorage.getItem("careeros_token") || ""; } catch { return ""; }
}

export default function OrchestrationHistoryPage() {
  const [sessions, setSessions] = useState<HistorySession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadHistory = async () => {
      const token = getToken();
      try {
        const res = await fetch(`${API_BASE}/orchestration/history?limit=100`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setSessions(data.sessions || []);
        }
      } catch { /* offline */ }
      setLoading(false);
    };
    loadHistory();
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <div className="border-b border-gray-800 bg-gray-900 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold text-white">Past Runs</h1>
          <a href="/orchestration" className="text-sm text-blue-400 hover:text-blue-300">← Back to overview</a>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {loading ? <p className="text-gray-500">Loading...</p> : sessions.length === 0 ? (
          <p className="text-gray-500">No past runs found yet.</p>
        ) : (
          <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-left">
                  <th className="px-4 py-3">Run</th>
                  <th className="px-4 py-3">Person</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Progress</th>
                  <th className="px-4 py-3">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {sessions.map((s) => (
                  <tr key={s.session_uid} className="hover:bg-gray-800/50">
                    <td className="px-4 py-3 font-mono text-xs text-blue-400">{s.session_uid.slice(0, 12)}...</td>
                    <td className="px-4 py-3 text-gray-400">{s.user_id || "—"}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs capitalize ${
                        s.status === "success" || s.status === "completed" ? "bg-green-900 text-green-300" :
                        s.status === "failed" ? "bg-red-900 text-red-300" :
                        s.status === "cancelled" ? "bg-yellow-900 text-yellow-300" :
                        "bg-blue-900 text-blue-300"
                      }`}>{s.status}</span>
                    </td>
                    <td className="px-4 py-3">{s.completion_pct.toFixed(0)}%</td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {formatDateTimeLocal(s.started_at, "—")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
