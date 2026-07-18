"use client";
import { useState, useEffect, useCallback } from "react";
import { Activity, AlertTriangle, BarChart3, CheckCircle2, Clock, RefreshCw, TrendingUp, Zap, ShieldOff } from "lucide-react";
import { formatTimeLocal } from "@/lib/datetime";

interface RerankHealth {
  status: string;
  circuit_breaker_open: boolean;
  fallback_strategy: string;
  model: string;
  max_batch: number;
  max_retries: number;
  timeout_s: number;
}

interface RerankStats {
  total_runs: number;
  success_rate: number;
  fallback_rate: number;
  avg_latency_ms: number;
  avg_confidence: number;
  avg_chunks_submitted: number;
  avg_chunks_returned: number;
  circuit_breaker_opens: number;
}

interface RerankHistoryItem {
  id: string;
  query: string;
  chunks_submitted: number;
  chunks_returned: number;
  primary_success: boolean;
  fallback_used: boolean;
  fallback_strategy: string | null;
  primary_latency_ms: number | null;
  confidence_avg: number | null;
  created_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetcher<T>(path: string, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json();
}

function getToken(): string {
  try {
    return localStorage.getItem("careeros_token") || "";
  } catch {
    return "";
  }
}

export default function RerankMonitoringDashboard() {
  const [health, setHealth] = useState<RerankHealth | null>(null);
  const [stats, setStats] = useState<RerankStats | null>(null);
  const [history, setHistory] = useState<RerankHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    const token = getToken();
    try {
      const [h, s, hist] = await Promise.all([
        fetcher<RerankHealth>("/rerank/health", token).catch(() => null),
        fetcher<RerankStats>("/rerank/stats", token).catch(() => null),
        fetcher<{ runs: RerankHistoryItem[] }>("/rerank/history?limit=20", token).catch(() => ({ runs: [] })),
      ]);
      setHealth(h);
      setStats(s);
      setHistory(hist.runs || []);
    } catch (e: any) {
      setError(e.message || "Failed to load rerank data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 15000);
    return () => clearInterval(interval);
  }, [loadAll]);

  if (loading && !health) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        <RefreshCw className="h-5 w-5 animate-spin mr-2" />
        Loading rerank monitoring...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-950/30 p-6 text-center">
        <AlertTriangle className="h-8 w-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-300 text-sm">{error}</p>
        <button onClick={loadAll} className="mt-3 text-xs text-indigo-400 hover:text-indigo-300 underline">
          Retry
        </button>
      </div>
    );
  }

  const isDegraded = health?.circuit_breaker_open || (stats && stats.fallback_rate > 0.3);
  const isHealthy = health?.status === "healthy" && !isDegraded;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-4 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <BarChart3 className="h-7 w-7 text-indigo-400" />
              Rerank Monitoring
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              NVIDIA rerank-qa-mistral-4b health, performance, and quality analytics
            </p>
          </div>
          <button
            onClick={loadAll}
            className="flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-700 bg-slate-900 hover:bg-slate-800 text-xs text-slate-300 transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {/* Health Banner */}
        <div className={`rounded-2xl border p-5 flex items-center gap-4 ${
          isHealthy
            ? "border-emerald-500/30 bg-emerald-950/20"
            : isDegraded
            ? "border-amber-500/30 bg-amber-950/20"
            : "border-slate-700 bg-slate-900/60"
        }`}>
          {isHealthy ? (
            <CheckCircle2 className="h-8 w-8 text-emerald-400" />
          ) : isDegraded ? (
            <AlertTriangle className="h-8 w-8 text-amber-400" />
          ) : (
            <Activity className="h-8 w-8 text-slate-400" />
          )}
          <div>
            <p className="text-lg font-semibold text-white">
              {isHealthy ? "Reranker Healthy" : isDegraded ? "Reranker Degraded" : "Reranker Status Unknown"}
            </p>
            <p className="text-sm text-slate-400">
              Model: {health?.model || "unknown"} • Fallback: {health?.fallback_strategy || "N/A"}
              {health?.circuit_breaker_open && (
                <span className="ml-2 inline-flex items-center gap-1 text-amber-400">
                  <ShieldOff className="h-3.5 w-3.5" />
                  Circuit breaker open
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Stats Grid */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              icon={Zap}
              label="Total Runs"
              value={stats.total_runs.toLocaleString()}
              color="indigo"
            />
            <StatCard
              icon={CheckCircle2}
              label="Success Rate"
              value={`${(stats.success_rate * 100).toFixed(1)}%`}
              color={stats.success_rate > 0.9 ? "emerald" : stats.success_rate > 0.7 ? "amber" : "red"}
            />
            <StatCard
              icon={Clock}
              label="Avg Latency"
              value={`${stats.avg_latency_ms.toFixed(0)}ms`}
              color={stats.avg_latency_ms < 2000 ? "emerald" : "amber"}
            />
            <StatCard
              icon={TrendingUp}
              label="Avg Confidence"
              value={stats.avg_confidence.toFixed(3)}
              color={stats.avg_confidence > 0.5 ? "indigo" : "amber"}
            />
            <StatCard
              icon={AlertTriangle}
              label="Fallback Rate"
              value={`${(stats.fallback_rate * 100).toFixed(1)}%`}
              color={stats.fallback_rate < 0.1 ? "emerald" : "red"}
            />
            <StatCard
              icon={ShieldOff}
              label="Circuit Breaker Opens"
              value={stats.circuit_breaker_opens.toString()}
              color={stats.circuit_breaker_opens === 0 ? "emerald" : "red"}
            />
            <StatCard
              icon={BarChart3}
              label="Avg Chunks In"
              value={stats.avg_chunks_submitted.toFixed(0)}
              color="slate"
            />
            <StatCard
              icon={BarChart3}
              label="Avg Chunks Out"
              value={stats.avg_chunks_returned.toFixed(0)}
              color="slate"
            />
          </div>
        )}

        {/* Configuration Card */}
        {health && (
          <div className="rounded-2xl border border-slate-700 bg-slate-900/60 p-5">
            <h2 className="text-sm font-semibold text-white mb-3">Configuration</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-xs">
              <ConfigItem label="Model" value={health.model} />
              <ConfigItem label="Fallback Strategy" value={health.fallback_strategy} />
              <ConfigItem label="Max Batch Size" value={health.max_batch.toString()} />
              <ConfigItem label="Max Retries" value={health.max_retries.toString()} />
              <ConfigItem label="Timeout" value={`${health.timeout_s}s`} />
            </div>
          </div>
        )}

        {/* History Table */}
        <div className="rounded-2xl border border-slate-700 bg-slate-900/60 p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Recent Rerank Runs</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="pb-3 pr-4">Time</th>
                  <th className="pb-3 pr-4">Query</th>
                  <th className="pb-3 pr-4">Chunks</th>
                  <th className="pb-3 pr-4">Success</th>
                  <th className="pb-3 pr-4">Fallback</th>
                  <th className="pb-3 pr-4">Latency</th>
                  <th className="pb-3">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-slate-500">
                      No rerank runs recorded yet. Execute a search to populate history.
                    </td>
                  </tr>
                ) : (
                  history.map((run) => (
                    <tr key={run.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                      <td className="py-2.5 pr-4 text-slate-400">
                        {formatTimeLocal(run.created_at)}
                      </td>
                      <td className="py-2.5 pr-4 text-slate-200 max-w-xs truncate">
                        {run.query}
                      </td>
                      <td className="py-2.5 pr-4 text-slate-400">
                        {run.chunks_submitted}→{run.chunks_returned}
                      </td>
                      <td className="py-2.5 pr-4">
                        {run.primary_success ? (
                          <span className="text-emerald-400">✓</span>
                        ) : (
                          <span className="text-red-400">✗</span>
                        )}
                      </td>
                      <td className="py-2.5 pr-4">
                        {run.fallback_used ? (
                          <span className="text-amber-400" title={run.fallback_strategy || ""}>
                            {run.fallback_strategy}
                          </span>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="py-2.5 pr-4 text-slate-400">
                        {run.primary_latency_ms?.toFixed(0) || "—"}ms
                      </td>
                      <td className="py-2.5 text-slate-400">
                        {run.confidence_avg?.toFixed(3) || "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color = "slate",
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    indigo: "border-indigo-500/30 bg-indigo-950/20 text-indigo-400",
    emerald: "border-emerald-500/30 bg-emerald-950/20 text-emerald-400",
    amber: "border-amber-500/30 bg-amber-950/20 text-amber-400",
    red: "border-red-500/30 bg-red-950/20 text-red-400",
    slate: "border-slate-700 bg-slate-900/60 text-slate-400",
  };

  return (
    <div className={`rounded-2xl border p-4 ${colorMap[color] || colorMap.slate}`}>
      <div className="flex items-center justify-between mb-2">
        <Icon className="h-4 w-4 opacity-70" />
      </div>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs mt-1 opacity-70">{label}</p>
    </div>
  );
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-slate-500 mb-1">{label}</p>
      <p className="text-slate-200 font-mono">{value}</p>
    </div>
  );
}
