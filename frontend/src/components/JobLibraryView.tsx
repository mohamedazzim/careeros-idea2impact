"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ExternalLink, Filter, ChevronLeft, ChevronRight, Layers, BellRing } from "lucide-react";

type JobItem = {
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
  posted_date?: string | null;
  fetched_at?: string | null;
  salary_range?: string | null;
  skills_required?: string[] | null;
  extracted_skills?: string[] | null;
  freshness_score?: number | null;
  lifecycle_state?: string | null;
  match_score?: number | null;
  full_description?: string | null;
};

export default function JobLibraryView({ token }: { token: string | null }) {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [selected, setSelected] = useState<JobItem | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(50);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("");

  const headers = useMemo(() => ({
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }), [token]);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    try {
      const baseUrl = (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) || "/api/v1";
      const params = new URLSearchParams({
        include_unmatched: "true",
        limit: String(limit),
        offset: String(page * limit),
      });
      if (query.trim()) params.set("query", query.trim());
      if (source) params.set("source", source);
      const res = await fetch(`${baseUrl}/jobs?${params.toString()}`, { headers });
      if (res.ok) {
        const payload = await res.json();
        setJobs(payload.jobs || []);
        setTotal(payload.total || 0);
        setSelected((curr) => {
          if (curr && (payload.jobs || []).some((j: JobItem) => j.id === curr.id)) return curr;
          return (payload.jobs || [])[0] || null;
        });
      }
    } finally {
      setLoading(false);
    }
  }, [headers, limit, page, query, source]);

  useEffect(() => { loadJobs(); }, [loadJobs]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-[1600px] mx-auto space-y-5">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-[10px] uppercase font-mono tracking-wider text-indigo-400 font-black">Dedicated Job Browser</p>
            <h1 className="text-2xl font-black">All Job Records</h1>
            <p className="text-sm text-slate-400 mt-1">
              Browse the full persisted job inventory with source, salary, freshness, and match details.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/jobs/alerts" className="text-xs font-semibold px-3 py-2 rounded-lg border border-indigo-300 bg-indigo-50 text-indigo-800 hover:bg-indigo-100 inline-flex items-center gap-2">
              <BellRing className="h-4 w-4" />
              Open Alert Records
            </Link>
            <Link href="/jobs" className="text-xs font-semibold px-3 py-2 rounded-lg border border-slate-700 bg-slate-900 hover:bg-slate-800 text-white">Back to Ranked Jobs</Link>
          </div>
        </div>

        <div className="bg-white text-slate-900 rounded-2xl border border-slate-200 p-4">
          <div className="flex flex-col lg:flex-row gap-3 lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2 items-center">
              <div className="relative">
                <Filter className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search jobs..." className="pl-9 pr-3 py-2 rounded-lg border border-slate-200 text-sm w-72" />
              </div>
              <select value={source} onChange={(e) => setSource(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-200 text-sm">
                <option value="">All Sources</option>
                <option value="theirstack">TheirStack</option>
                <option value="remoteok">RemoteOK</option>
                <option value="arbeitnow">Arbeitnow</option>
                <option value="adzuna">Adzuna</option>
                <option value="usajobs">USAJobs</option>
                <option value="greenhouse">Greenhouse</option>
                <option value="lever">Lever</option>
              </select>
              <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="px-3 py-2 rounded-lg border border-slate-200 text-sm">
                {[25, 50, 100].map((n) => <option key={n} value={n}>{n} per page</option>)}
              </select>
            </div>
            <button onClick={loadJobs} className="px-4 py-2 rounded-lg bg-slate-950 text-white text-sm font-semibold">{loading ? "Refreshing..." : "Refresh"}</button>
          </div>
          <div className="mt-3 text-xs text-slate-500 font-mono">Showing {jobs.length} of {total} jobs</div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[1.4fr_0.9fr] gap-5">
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900 flex items-center gap-2"><Layers className="h-4 w-4 text-indigo-500" /> Job Rows</h2>
              <div className="flex items-center gap-2 text-sm">
                <button disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))} className="px-2 py-1 rounded border disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button>
                <span className="font-mono text-xs">Page {page + 1}</span>
                <button disabled={(page + 1) * limit >= total} onClick={() => setPage((p) => p + 1)} className="px-2 py-1 rounded border disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button>
              </div>
            </div>
            <div className="divide-y divide-slate-100 max-h-[72vh] overflow-auto">
              {jobs.map((job) => (
                <button key={job.id} onClick={() => setSelected(job)} className={`w-full text-left p-4 hover:bg-slate-50 transition ${selected?.id === job.id ? "bg-indigo-50" : ""}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-slate-900">{job.title}</h3>
                      <p className="text-sm text-slate-600">{job.company || "Unknown"} · {job.location || "Unknown location"}</p>
                      <p className="text-[11px] text-slate-400 font-mono mt-1">{job.source_provider || job.source || "unknown"} · {job.source_job_id || job.job_uid}</p>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-black text-indigo-600">{Math.round(job.match_score || 0)}%</div>
                      <div className="text-[10px] text-slate-400 font-mono">{job.lifecycle_state || "ACTIVE"}</div>
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
                  <p className="text-[10px] uppercase font-mono tracking-wider text-indigo-500 font-black">Selected Job</p>
                  <h2 className="text-xl font-black text-slate-900">{selected.title}</h2>
                  <p className="text-sm text-slate-600">{selected.company} · {selected.location}</p>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <InfoCard label="Source" value={selected.source_provider || selected.source || "unknown"} />
                  <InfoCard label="Match" value={`${Math.round(selected.match_score || 0)}%`} />
                  <InfoCard label="Posted" value={selected.posted_date || "n/a"} />
                  <InfoCard label="Fetched" value={selected.fetched_at || "n/a"} />
                  <InfoCard label="Freshness" value={selected.freshness_score != null ? `${Math.round(selected.freshness_score)}%` : "n/a"} />
                  <InfoCard label="Salary" value={selected.salary_range || "n/a"} />
                </div>
                <div className="space-y-2">
                  <p className="text-[10px] uppercase font-mono tracking-wider text-slate-500 font-black">Links</p>
                  <a className="inline-flex items-center gap-2 text-indigo-600 text-sm font-semibold" href={selected.apply_url || selected.source_url || "#"} target="_blank" rel="noreferrer">
                    Open Apply URL <ExternalLink className="h-4 w-4" />
                  </a>
                </div>
                <div className="space-y-2">
                  <p className="text-[10px] uppercase font-mono tracking-wider text-slate-500 font-black">Description</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap max-h-[42vh] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3">
                    {selected.full_description || "No description available."}
                  </p>
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                Select a job to see the full record
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
