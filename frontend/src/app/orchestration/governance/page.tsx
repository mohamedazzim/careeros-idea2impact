"use client";
import { useState, useEffect, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getToken(): string {
  try { return localStorage.getItem("careeros_token") || ""; } catch { return ""; }
}

interface GovernanceDecision {
  id: string;
  session_uid: string;
  rule_name: string;
  verdict: string;
  reason: string;
  severity: "high" | "medium" | "low";
  created_at: string;
}

interface GovernanceStats {
  total_decisions: number;
  suppressed: number;
  approved: number;
  rules: { name: string; description: string; threshold: string }[];
}

export default function GovernancePage() {
  const [decisions, setDecisions] = useState<GovernanceDecision[]>([]);
  const [stats, setStats] = useState<GovernanceStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    const token = getToken();
    const headers = { Authorization: `Bearer ${token}` };
    try {
      const [decRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/orchestration/governance/decisions?limit=50`, { headers }).catch(() => null),
        fetch(`${API_BASE}/orchestration/governance/stats`, { headers }).catch(() => null),
      ]);

      if (decRes?.ok) {
        const data = await decRes.json();
        setDecisions(data.decisions || data || []);
      }
      if (statsRes?.ok) {
        const data = await statsRes.json();
        setStats(data);
      }
    } catch {
      // API not available
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <div className="border-b border-gray-800 bg-gray-900 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold text-white">Rules</h1>
          <a href="/orchestration" className="text-sm text-blue-400 hover:text-blue-300">← Back to overview</a>
        </div>
      </div>
      <div className="max-w-7xl mx-auto p-6">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading governance data...</div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold mb-4">Decision log</h2>
              {decisions.length === 0 ? (
                <div className="p-6 text-center text-gray-500">
                  <p className="text-sm">No decisions recorded yet.</p>
                  <p className="text-xs mt-1">This area will show when CareerOS approves, pauses, or blocks an action.</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {decisions.map((d) => (
                    <div key={d.id} className="flex items-center justify-between p-3 bg-gray-800/50 rounded">
                      <div>
                        <p className="text-sm text-white">{d.rule_name}</p>
                        <p className={`text-xs capitalize ${d.severity === "high" ? "text-red-400" : d.severity === "medium" ? "text-yellow-400" : "text-blue-400"}`}>
                          {d.severity} — {d.verdict}
                        </p>
                      </div>
                      <span className="text-xs text-gray-500">{d.reason}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold mb-4">Safety rules</h2>
              {stats?.rules && stats.rules.length > 0 ? (
                <div className="space-y-3 text-sm">
                  {stats.rules.map((rule) => (
                    <div key={rule.name} className="p-3 bg-gray-800/50 rounded">
                      <p className="text-white font-medium">{rule.name}</p>
                      <p className="text-gray-400">{rule.description} — Threshold: {rule.threshold}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-3 text-sm">
                  <div className="p-3 bg-gray-800/50 rounded">
                    <p className="text-white font-medium">Loop limit</p>
                    <p className="text-gray-400">Prevents CareerOS from getting stuck repeating the same step.</p>
                  </div>
                  <div className="p-3 bg-gray-800/50 rounded">
                    <p className="text-white font-medium">Auto-action limit</p>
                    <p className="text-gray-400">Keeps the system from taking too many actions without review.</p>
                  </div>
                  <div className="p-3 bg-gray-800/50 rounded">
                    <p className="text-white font-medium">Confidence limit</p>
                    <p className="text-gray-400">If the system is unsure, it stops instead of guessing.</p>
                  </div>
                  <div className="p-3 bg-gray-800/50 rounded">
                    <p className="text-white font-medium">Retry limit</p>
                    <p className="text-gray-400">It tries a small number of times before giving up safely.</p>
                  </div>
                </div>
              )}
              {stats && (
                <div className="mt-4 pt-4 border-t border-gray-800 grid grid-cols-2 gap-4 text-center">
                  <div className="p-3 bg-gray-800/50 rounded">
                    <p className="text-2xl font-bold text-green-400">{stats.approved}</p>
                    <p className="text-xs text-gray-400">Approved</p>
                  </div>
                  <div className="p-3 bg-gray-800/50 rounded">
                    <p className="text-2xl font-bold text-red-400">{stats.suppressed}</p>
                    <p className="text-xs text-gray-400">Suppressed</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
