"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BellRing, ChevronLeft, ChevronRight, Filter, ExternalLink } from "lucide-react";
import { formatDateOnly } from "@/lib/datetime";

type AlertRecord = {
  id: number;
  decision: string;
  channel?: string | null;
  reason?: string | null;
  created_at?: string | null;
  scores?: Record<string, unknown> | null;
  decision_factors?: Record<string, unknown> | null;
  decision_confidence?: number | null;
  job?: {
    id: number;
    job_uid: string;
    title: string;
    company?: string | null;
    location?: string | null;
    source?: string | null;
    source_provider?: string | null;
    source_job_id?: string | null;
    source_url?: string | null;
    apply_url?: string | null;
    match_score?: number | null;
    freshness_score?: number | null;
    lifecycle_state?: string | null;
    posted_date?: string | null;
    fetched_at?: string | null;
  } | null;
};

export default function AlertRecordsView({ token }: { token: string | null }) {
  const [records, setRecords] = useState<AlertRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(50);
  const [decision, setDecision] = useState("DASHBOARD_ONLY");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<AlertRecord | null>(null);

  const headers = useMemo(() => ({
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }), [token]);

  const loadRecords = useCallback(async () => {
    setLoading(true);
    try {
      const baseUrl = (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) || "/api/v1";
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
      });
      if (decision) params.set("decision", decision);
      const res = await fetch(`${baseUrl}/jobs/alerts?${params.toString()}`, { headers });
      if (!res.ok) return;
      const payload = await res.json();
      const items = (payload.records || []).filter((record: AlertRecord) => {
        if (!query.trim()) return true;
        const haystack = `${record.job?.title || ""} ${record.job?.company || ""} ${record.job?.location || ""} ${record.reason || ""}`.toLowerCase();
        return haystack.includes(query.trim().toLowerCase());
      });
      setRecords(items);
      setTotal(payload.total || 0);
      setSelected((curr) => {
        if (curr && items.some((row: AlertRecord) => row.id === curr.id)) return curr;
        return items[0] || null;
      });
    } finally {
      setLoading(false);
    }
  }, [decision, headers, limit, offset, query]);

  useEffect(() => { loadRecords(); }, [loadRecords]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-[1600px] mx-auto space-y-5">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-[10px] uppercase font-mono tracking-wider text-amber-400 font-black">Decision Browser</p>
            <h1 className="text-2xl font-black">Alert Records</h1>
            <p className="text-sm text-slate-400 mt-1">
              These are the dashboard-only decisions behind the large count on the Jobs page. They are not job rows.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/jobs/library" className="text-xs font-semibold px-3 py-2 rounded-lg border border-indigo-300 bg-indigo-50 text-indigo-800 hover:bg-indigo-100">
              Back to Job Library
            </Link>
            <Link href="/jobs" className="text-xs font-semibold px-3 py-2 rounded-lg border border-slate-700 bg-slate-900 hover:bg-slate-800 text-white">
              Back to Ranked Jobs
            </Link>
          </div>
        </div>

        <div className="bg-white text-slate-900 rounded-2xl border border-slate-200 p-4">
          <div className="flex flex-col lg:flex-row gap-3 lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2 items-center">
              <div className="relative">
                <Filter className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search alerts..." className="pl-9 pr-3 py-2 rounded-lg border border-slate-200 text-sm w-72" />
              </div>
              <select value={decision} onChange={(e) => setDecision(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-200 text-sm">
                <option value="DASHBOARD_ONLY">Dashboard only</option>
                <option value="CALL">Call</option>
                <option value="EMAIL">Email</option>
                <option value="WHATSAPP">WhatsApp</option>
                <option value="IGNORE">Ignore</option>
                <option value="NONE">None</option>
              </select>
              <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="px-3 py-2 rounded-lg border border-slate-200 text-sm">
                {[25, 50, 100].map((n) => <option key={n} value={n}>{n} per page</option>)}
              </select>
            </div>
            <button onClick={loadRecords} className="px-4 py-2 rounded-lg bg-slate-950 text-white text-sm font-semibold">
              {loading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
          <div className="mt-3 text-xs text-slate-500 font-mono">Showing {records.length} of {total} alert records</div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.95fr] gap-5">
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900 flex items-center gap-2"><BellRing className="h-4 w-4 text-amber-500" /> Alert Decision Rows</h2>
              <div className="flex items-center gap-2 text-sm">
                <button disabled={offset === 0} onClick={() => setOffset((curr) => Math.max(0, curr - limit))} className="px-2 py-1 rounded border disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button>
                <span className="font-mono text-xs">Page {Math.floor(offset / limit) + 1}</span>
                <button disabled={offset + limit >= total} onClick={() => setOffset((curr) => curr + limit)} className="px-2 py-1 rounded border disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button>
              </div>
            </div>
            <div className="divide-y divide-slate-100 max-h-[72vh] overflow-auto">
              {records.map((record) => (
                <button key={record.id} onClick={() => setSelected(record)} className={`w-full text-left p-4 hover:bg-slate-50 transition ${selected?.id === record.id ? "bg-amber-50" : ""}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-slate-900">{record.job?.title || "Unknown job"}</h3>
                      <p className="text-sm text-slate-600">{record.job?.company || "Unknown"} · {record.job?.location || "Unknown location"}</p>
                      <p className="text-[11px] text-slate-400 font-mono mt-1">
                        {record.decision} · {record.channel || "NONE"} · {record.job?.source_provider || record.job?.source || "unknown"}
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-black text-amber-600">{Math.round(record.job?.match_score || 0)}%</div>
                      <div className="text-[10px] text-slate-400 font-mono">{formatDateOnly(record.created_at, "n/a")}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            {selected ? (
              <div className="space-y-4">
                <div>
                  <p className="text-[10px] uppercase font-mono tracking-wider text-amber-500 font-black">Selected Alert</p>
                  <h2 className="text-xl font-black text-slate-900">{selected.job?.title || "Unknown job"}</h2>
                  <p className="text-sm text-slate-600">{selected.job?.company} · {selected.job?.location}</p>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <InfoCard label="Decision" value={selected.decision} />
                  <InfoCard label="Channel" value={selected.channel || "NONE"} />
                  <InfoCard label="Match" value={`${Math.round(selected.job?.match_score || 0)}%`} />
                  <InfoCard label="Confidence" value={selected.decision_confidence != null ? `${Math.round((selected.decision_confidence || 0) * 100)}%` : "n/a"} />
                  <InfoCard label="Posted" value={selected.job?.posted_date || "n/a"} />
                  <InfoCard label="Fetched" value={selected.job?.fetched_at || "n/a"} />
                </div>
                <div className="space-y-2">
                  <p className="text-[10px] uppercase font-mono tracking-wider text-slate-500 font-black">Reason</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3">{selected.reason || "No reason recorded."}</p>
                </div>
                {selected.job?.apply_url && (
                  <div className="space-y-2">
                    <p className="text-[10px] uppercase font-mono tracking-wider text-slate-500 font-black">Job Link</p>
                    <a className="inline-flex items-center gap-2 text-indigo-600 text-sm font-semibold" href={selected.job.apply_url} target="_blank" rel="noreferrer">
                      Open Apply URL <ExternalLink className="h-4 w-4" />
                    </a>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                Select an alert record to see the full audit trail
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-black">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900 break-words">{value}</p>
    </div>
  );
}
