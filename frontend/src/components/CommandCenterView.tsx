/**
 * CareerOS Live Status Center
 *
 * A plain-language operations page that shows real readiness data,
 * live agent status, explainability evidence, timeline history, and
 * report generation actions.
 */

'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertCircle,
  Award,
  BarChart3,
  Brain,
  Clock,
  Download,
  FileText,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Users,
} from 'lucide-react';
import { formatDateTimeLocal } from '@/lib/datetime';

const API = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';

type TabId = 'overview' | 'readiness' | 'agents' | 'explain' | 'timeline' | 'reports';

interface Tab {
  id: TabId;
  label: string;
  icon: React.ElementType;
}

const TABS: Tab[] = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'readiness', label: 'Readiness', icon: Award },
  { id: 'agents', label: 'Agents', icon: Activity },
  { id: 'explain', label: 'Why this score', icon: Brain },
  { id: 'timeline', label: 'Timeline', icon: Clock },
  { id: 'reports', label: 'Reports', icon: FileText },
];

const REPORT_TYPES = [
  { type: 'candidate', label: 'Candidate summary', desc: 'Resume, strengths, gaps, and practical next steps.' },
  { type: 'resume', label: 'Resume report', desc: 'Resume quality, evidence, and improvement suggestions.' },
  { type: 'readiness', label: 'Readiness report', desc: 'Overall readiness plus the score breakdown.' },
  { type: 'interview', label: 'Interview report', desc: 'Interview performance, confidence, and areas to improve.' },
  { type: 'career_progress', label: 'Career progress', desc: 'Trajectory, trend, and milestone progress.' },
  { type: 'opportunity', label: 'Opportunity report', desc: 'Job fit, market alignment, and opportunity recommendations.' },
];

function authHeaders(json = false) {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${localStorage.getItem('careeros_token') ?? ''}`,
  };
  if (json) headers['Content-Type'] = 'application/json';
  return headers;
}

function statusLabel(status?: string) {
  const value = (status || '').toLowerCase();
  if (value === 'active' || value === 'running') return 'Working';
  if (value === 'completed' || value === 'success') return 'Done';
  if (value === 'failed') return 'Problem';
  return 'Idle';
}

export default function CommandCenterView() {
  const [active, setActive] = useState<TabId>('overview');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [readiness, setReadiness] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [explain, setExplain] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const loadReadiness = useCallback(async () => {
    const res = await fetch(`${API}/readiness/score`, { headers: authHeaders() });
    if (!res.ok) throw new Error('Could not load readiness score');
    setReadiness(await res.json());
  }, []);

  const loadAgents = useCallback(async () => {
    const res = await fetch(`${API}/agents/status`, { headers: authHeaders() });
    if (!res.ok) throw new Error('Could not load agent status');
    const json = await res.json();
    setAgents(Array.isArray(json) ? json : json.agents || json.data || []);
  }, []);

  const loadExplain = useCallback(async () => {
    const res = await fetch(`${API}/readiness/explain`, { headers: authHeaders() });
    if (!res.ok) throw new Error('Could not load explanation');
    setExplain(await res.json());
  }, []);

  const loadTimeline = useCallback(async () => {
    const res = await fetch(`${API}/readiness/timeline`, { headers: authHeaders() });
    if (!res.ok) throw new Error('Could not load timeline');
    const json = await res.json();
    setTimeline(Array.isArray(json) ? json : json.items || json.events || []);
  }, []);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      await Promise.all([loadReadiness(), loadAgents(), loadExplain(), loadTimeline()]);
      setLastUpdated(formatDateTimeLocal(new Date()));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load live CareerOS data');
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, [loadAgents, loadExplain, loadReadiness, loadTimeline]);

  useEffect(() => {
    void refreshAll();
    const interval = setInterval(() => {
      void refreshAll();
    }, 30000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  const activeAgents = useMemo(
    () => agents.filter((agent) => ['active', 'running', 'working'].includes((agent.status || '').toLowerCase())).length,
    [agents],
  );

  const overallReadiness = readiness?.overall ?? 0;
  const readinessItems = readiness
    ? [
        readiness.resume_score,
        readiness.interview_score,
        readiness.opportunity_score,
        readiness.skill_gap,
        readiness.market_readiness,
        readiness.career_progress,
      ].filter(Boolean)
    : [];
  const latestTimeline = timeline?.[0];

  const card = 'rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-sm';
  const pill = 'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em]';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className={`${card} bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950`}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <span className={`${pill} border-indigo-500/30 bg-indigo-500/10 text-indigo-300`}>Live status</span>
              <h1 className="mt-3 text-3xl font-bold text-white">CareerOS Control Center</h1>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                This page shows real data from CareerOS. It tells you how ready the profile is, which agents are active,
                why the system made a decision, and what happened most recently.
              </p>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">What it is for</p>
                  <p className="mt-1 text-sm text-slate-200">A simple place to check CareerOS health and career progress.</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">When to use it</p>
                  <p className="mt-1 text-sm text-slate-200">When you want to see what CareerOS learned and what it would do next.</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">What you can trust</p>
                  <p className="mt-1 text-sm text-slate-200">Only data returned by the live backend is shown here.</p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3 self-start">
              <button
                onClick={() => void refreshAll()}
                className="inline-flex items-center gap-2 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-2 text-sm font-semibold text-indigo-200 transition-colors hover:bg-indigo-500/15"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
                Refresh live data
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          <div className={card}>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Readiness</p>
            <div className="mt-2 flex items-end gap-2">
              <span className="text-3xl font-bold text-indigo-300">{overallReadiness}</span>
              <span className="pb-1 text-sm text-slate-500">/ 100</span>
            </div>
            <p className="mt-2 text-sm text-slate-300">How ready the profile is right now.</p>
          </div>

          <div className={card}>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Live agents</p>
            <div className="mt-2 flex items-end gap-2">
              <span className="text-3xl font-bold text-emerald-300">{activeAgents}</span>
              <span className="pb-1 text-sm text-slate-500">working</span>
            </div>
            <p className="mt-2 text-sm text-slate-300">Agents currently doing useful work.</p>
          </div>

          <div className={card}>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Latest step</p>
            <div className="mt-2 flex items-end gap-2">
              <span className="text-3xl font-bold text-sky-300">{timeline.length}</span>
              <span className="pb-1 text-sm text-slate-500">events</span>
            </div>
            <p className="mt-2 text-sm text-slate-300">
              {latestTimeline?.stage ? latestTimeline.stage : 'No timeline event yet.'}
            </p>
          </div>

          <div className={card}>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Last refresh</p>
            <div className="mt-2 flex items-end gap-2">
              <span className="text-xl font-bold text-white">{lastUpdated || 'Pending'}</span>
            </div>
            <p className="mt-2 text-sm text-slate-300">When the live data was last fetched.</p>
          </div>
        </div>

        <div className="flex gap-2 overflow-x-auto border-b border-slate-800">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = active === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActive(tab.id)}
                className={`flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-3 text-sm font-medium transition-colors ${
                  isActive
                    ? 'border-indigo-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {active === 'overview' && (
          <div className="grid gap-4 lg:grid-cols-2">
            <div className={card}>
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-indigo-300" />
                <h2 className="text-lg font-semibold">What this page means</h2>
              </div>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                <p>• CareerOS is reading your real profile data.</p>
                <p>• It is checking whether the system can confidently help you next.</p>
                <p>• It is showing the latest evidence instead of a fake summary.</p>
              </div>
            </div>

            <div className={card}>
              <div className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-indigo-300" />
                <h2 className="text-lg font-semibold">Quick snapshot</h2>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Status</p>
                  <p className="mt-1 text-sm text-slate-200">{statusLabel(agents[0]?.status)}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Evidence</p>
                  <p className="mt-1 text-sm text-slate-200">
                    {explain?.status || 'Waiting for a live explanation from the backend.'}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Next action</p>
                  <p className="mt-1 text-sm text-slate-200">Generate a report or inspect the score breakdown.</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">People-friendly</p>
                  <p className="mt-1 text-sm text-slate-200">No backend jargon is needed to understand the result.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {active === 'readiness' && readiness && (
          <div className="space-y-4">
            <div className={card}>
              <div className="flex items-center gap-2">
                <Award className="h-5 w-5 text-indigo-300" />
                <h2 className="text-lg font-semibold">Readiness score</h2>
              </div>
              <p className="mt-2 text-sm text-slate-300">
                This score comes from persisted CareerOS evidence. It is not a mock value.
              </p>
              <div className="mt-4 grid gap-4 md:grid-cols-3">
                <div className="flex items-center justify-center rounded-2xl border border-slate-800 bg-slate-950/40 p-6 text-center md:col-span-1">
                  <div>
                    <div className="text-5xl font-bold text-indigo-300">{overallReadiness}</div>
                    <div className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-500">overall readiness</div>
                  </div>
                </div>
                <div className="grid gap-3 md:col-span-2 md:grid-cols-2">
                  {readinessItems.map((item: any) => (
                    <div key={item.label} className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{item.label}</p>
                      <div className="mt-2 text-2xl font-bold text-white">{item.score}/100</div>
                      <div className="mt-2 space-y-1">
                        {(item.evidence || []).slice(0, 3).map((e: string, i: number) => (
                          <p key={i} className="text-xs text-slate-400">• {e}</p>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {!!readiness?.trend?.length && (
              <div className={card}>
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-emerald-300" />
                  <h3 className="text-lg font-semibold">Readiness trend</h3>
                </div>
                <div className="mt-4 flex items-end gap-4 h-24">
                  {readiness.trend.map((t: any) => (
                    <div key={t.date} className="flex flex-1 flex-col items-center">
                      <span className="text-xs text-slate-300">{t.score}</span>
                      <div className="mt-2 w-full rounded-t bg-indigo-500/70" style={{ height: `${Math.max((t.score / 100) * 72, 8)}px` }} />
                      <span className="mt-2 text-[10px] text-slate-500">{String(t.date).slice(-5)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {active === 'agents' && (
          <div className="space-y-4">
            <div className={card}>
              <div className="flex items-center gap-2">
                <Users className="h-5 w-5 text-indigo-300" />
                <h2 className="text-lg font-semibold">Live agents</h2>
              </div>
              <p className="mt-2 text-sm text-slate-300">
                These are the CareerOS workers and helpers currently reporting status.
              </p>
            </div>

            {agents.length > 0 ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {agents.map((agent: any, index: number) => (
                  <div key={`${agent.name || 'agent'}-${index}`} className={card}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">{agent.name || 'Agent'}</p>
                        <p className="mt-1 text-xs text-slate-400">{agent.detail || agent.description || 'No extra detail returned yet.'}</p>
                      </div>
                      <span
                        className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase ${
                          ['active', 'running', 'working'].includes((agent.status || '').toLowerCase())
                            ? 'bg-emerald-500/10 text-emerald-300'
                            : (agent.status || '').toLowerCase() === 'failed'
                              ? 'bg-red-500/10 text-red-300'
                              : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {statusLabel(agent.status)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={card}>
                <p className="text-sm text-slate-300">No live agent telemetry returned yet.</p>
              </div>
            )}
          </div>
        )}

        {active === 'explain' && (
          <div className="space-y-4">
            <div className={card}>
              <div className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-indigo-300" />
                <h2 className="text-lg font-semibold">Why the system reached this score</h2>
              </div>
              <p className="mt-2 text-sm text-slate-300">
                This section explains the score in plain English using the live backend response.
              </p>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className={card}>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Formula</p>
                <p className="mt-2 text-sm text-slate-200">{explain?.formula || 'Waiting for explanation data.'}</p>
                <p className="mt-4 text-xs text-slate-400">
                  Overall score: <span className="font-semibold text-white">{explain?.overall_score ?? overallReadiness}</span>
                </p>
              </div>

              <div className={card}>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Explanation status</p>
                <p className="mt-2 text-sm text-slate-200">{explain?.status || 'No explanation returned yet.'}</p>
                <p className="mt-4 text-xs text-slate-400">
                  The page only shows what the backend already computed and stored.
                </p>
              </div>
            </div>

            {explain?.dimensions && (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {Object.entries(explain.dimensions).map(([name, dim]: [string, any]) => (
                  <div key={name} className={card}>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{dim.label || name}</p>
                    <div className="mt-2 text-2xl font-bold text-white">{dim.score ?? 0}/100</div>
                    <div className="mt-3 space-y-1">
                      {(dim.evidence || []).slice(0, 4).map((e: string, i: number) => (
                        <p key={i} className="text-xs text-slate-400">• {e}</p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {active === 'timeline' && (
          <div className="space-y-4">
            <div className={card}>
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-indigo-300" />
                <h2 className="text-lg font-semibold">Career timeline</h2>
              </div>
              <p className="mt-2 text-sm text-slate-300">
                A simple history of the most recent CareerOS milestones and actions.
              </p>
            </div>

            <div className="relative space-y-4 border-l border-slate-800 pl-6">
              {timeline.length > 0 ? timeline.map((event: any, index: number) => (
                <div key={`${event.stage || 'event'}-${index}`} className="relative">
                  <div
                    className={`absolute -left-[31px] top-2 h-3 w-3 rounded-full border-2 ${
                      (event.status || '').toLowerCase() === 'completed'
                        ? 'border-emerald-500 bg-emerald-500'
                        : 'border-amber-500 bg-amber-500 animate-pulse'
                    }`}
                  />
                  <div className={card}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">{event.stage || 'Step'}</p>
                        <p className="mt-1 text-sm text-slate-300">{event.detail || 'No detail returned.'}</p>
                      </div>
                      <span className="text-xs text-slate-500">
                        {formatDateTimeLocal(event.timestamp, '—')}
                      </span>
                    </div>
                  </div>
                </div>
              )) : (
                <div className={card}>
                  <p className="text-sm text-slate-300">No timeline events returned yet.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {active === 'reports' && (
          <div className="space-y-4">
            <div className={card}>
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-indigo-300" />
                <h2 className="text-lg font-semibold">Generate a real report</h2>
              </div>
              <p className="mt-2 text-sm text-slate-300">
                These buttons call the live readiness report endpoint and produce persisted output.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {REPORT_TYPES.map((report) => (
                <div key={report.type} className={card}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{report.label}</p>
                      <p className="mt-1 text-xs text-slate-400">{report.desc}</p>
                    </div>
                    <Download className="h-4 w-4 text-indigo-300" />
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        const res = await fetch(`${API}/readiness/report`, {
                          method: 'POST',
                          headers: authHeaders(true),
                          body: JSON.stringify({ report_type: report.type }),
                        });
                        if (res.ok) alert(`${report.label} generated successfully. Check the report downloads.`);
                        else alert(`Could not generate ${report.label.toLowerCase()}.`);
                      } catch {
                        alert(`Could not generate ${report.label.toLowerCase()}.`);
                      }
                    }}
                    className="mt-4 inline-flex items-center gap-2 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-3 py-2 text-xs font-semibold text-indigo-200 transition-colors hover:bg-indigo-500/15"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Generate report
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div className="flex justify-center py-10">
            <RefreshCw className="h-6 w-6 animate-spin text-indigo-300" />
          </div>
        )}

        {error && (
          <div className="fixed bottom-4 right-4 max-w-sm rounded-xl border border-red-700/40 bg-red-950/90 px-4 py-3 text-sm text-red-100 shadow-xl">
            <div className="mb-1 flex items-center gap-2 font-semibold">
              <AlertCircle className="h-4 w-4" />
              Live data error
            </div>
            <p className="text-xs text-red-200">{error}</p>
            <button onClick={() => setError(null)} className="mt-2 text-xs text-red-300 underline">
              Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
