"use client";
import { useState, useEffect, useCallback } from "react";
import {
  Compass, TrendingUp, Award, AlertCircle, CheckCircle2, Clock,
  RefreshCw, ExternalLink, Target, Star, Zap, BarChart3, Search,
  Briefcase, MapPin, DollarSign, Calendar
} from "lucide-react";

interface DimensionScore {
  score: number;
  confidence: number;
  citations: { [key: string]: any }[];
}

interface Opportunity {
  id: string;
  title: string;
  company: string;
  provider: string | null;
  source_url: string | null;
  source_job_id: string | null;
  overall_score: number;
  confidence: number;
  skill_overlap: number;
  dimension_scores: Record<string, DimensionScore>;
  missing_skills: string[];
  matched_skills: string[];
  salary_range: string | null;
  deadline?: string | null;
  source: string | null;
}

interface DiscoverResult {
  run_id: string;
  opportunities: Opportunity[];
  resume_status: string;
  market_signals_count: number;
  pipeline_elapsed_ms: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getToken(): string {
  try {
    return localStorage.getItem("careeros_token") || "";
  } catch {
    return "";
  }
}

function getCandidateId(token: string): string {
  try {
    return JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))).sub || "";
  } catch {
    return "";
  }
}

function normalizeSignalList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const record = item as Record<string, unknown>;
        const display =
          record.title ||
          record.category ||
          record.description ||
          record.skill ||
          record.name ||
          record.id;
        return display == null ? "" : String(display);
      }
      return item == null ? "" : String(item);
    })
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeOpportunity(opp: Opportunity): Opportunity {
  return {
    ...opp,
    matched_skills: normalizeSignalList(opp.matched_skills),
    missing_skills: normalizeSignalList(opp.missing_skills),
  };
}

export default function OpportunityCenterView() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRunId, setLastRunId] = useState<string>("");
  const [elapsed, setElapsed] = useState<number>(0);
  const [selectedOpp, setSelectedOpp] = useState<Opportunity | null>(null);
  const [rc3Intel, setRc3Intel] = useState<any | null>(null);
  const [callOutcomes, setCallOutcomes] = useState<any[]>([]);
  const [candidateMemory, setCandidateMemory] = useState<any[]>([]);
  const [followups, setFollowups] = useState<any[]>([]);
  const [lifecycles, setLifecycles] = useState<any[]>([]);
  const [careerProgress, setCareerProgress] = useState<any[]>([]);
  const [memoryHistory, setMemoryHistory] = useState<any[]>([]);
  const [reranked, setReranked] = useState<any[]>([]);
  const [learningRuns, setLearningRuns] = useState<any[]>([]);
  const [lifecycleHistory, setLifecycleHistory] = useState<any[]>([]);

  // Fetch persisted opportunities from database on load
  const fetchOpportunities = useCallback(async () => {
    setLoading(true);
    setError(null);
    const token = getToken();

    try {
      const res = await fetch(`${API_BASE}/opportunities/list`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errText}`);
      }

      const data = await res.json();
      if (data.opportunities && data.opportunities.length > 0) {
        // Transform persisted data to match Opportunity interface
        const transformed: Opportunity[] = data.opportunities.map((opp: any) => ({
          id: String(opp.job_id || opp.id),
          title: opp.title || `Opportunity ${opp.job_id}`,
          company: opp.company || "Unknown",
          provider: opp.provider || null,
          source_url: opp.source_url || null,
          source_job_id: opp.source_job_id || null,
          overall_score: opp.overall_score || 0,
          confidence: opp.confidence || 0.5,
          skill_overlap: opp.skill_match || 0,
          dimension_scores: opp.dimension_scores || {
            skill_overlap: { score: opp.skill_match || 0, confidence: 0.5, citations: [] },
            seniority_fit: { score: opp.experience_match || 0, confidence: 0.5, citations: [] },
            domain_alignment: { score: opp.education_match || 0, confidence: 0.5, citations: [] },
          },
          missing_skills: normalizeSignalList(opp.gaps),
          matched_skills: normalizeSignalList(opp.strengths),
          salary_range: null,
          /* deadline: null, */
          source: opp.source || null,
        }));
        setOpportunities(transformed);
      }
    } catch (e: any) {
      // Silently fail - user can trigger refresh manually
      console.warn("Failed to fetch persisted opportunities:", e.message);
    } finally {
      setLoading(false);
    }
  }, []);


  const fetchRc3Intel = useCallback(async () => {
    const token = getToken();
    const candidateId = getCandidateId(token);
    const outcomeApiBase = API_BASE.replace(/\/v1$/, "");
    try {
      const [res, outcomesRes, memoryRes, followupRes, lifecycleRes, progressRes, memoryHistoryRes, rerankedRes, learningRunsRes, lifecycleHistoryRes] = await Promise.all([
        fetch(`${API_BASE}/opportunities/rc3/intelligence`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${outcomeApiBase}/outcomes`, { headers: { Authorization: `Bearer ${token}` } }),
        candidateId
          ? fetch(`${outcomeApiBase}/candidate-memory/${candidateId}`, { headers: { Authorization: `Bearer ${token}` } })
          : Promise.resolve(null),
        fetch(`${outcomeApiBase}/followups`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${outcomeApiBase}/application-lifecycle`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${outcomeApiBase}/career-progress`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/candidate-memory/history`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/opportunities/reranked`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/learning-loop/history`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/application-lifecycle/history`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (res.ok) {
        setRc3Intel(await res.json());
      }
      if (outcomesRes.ok) setCallOutcomes((await outcomesRes.json()).items || []);
      if (memoryRes?.ok) setCandidateMemory((await memoryRes.json()).items || []);
      if (followupRes.ok) setFollowups((await followupRes.json()).items || []);
      if (lifecycleRes.ok) setLifecycles((await lifecycleRes.json()).items || []);
      if (progressRes.ok) setCareerProgress((await progressRes.json()).items || []);
      if (memoryHistoryRes.ok) setMemoryHistory((await memoryHistoryRes.json()).history || []);
      if (rerankedRes.ok) setReranked((await rerankedRes.json()).reranked || []);
      if (learningRunsRes.ok) setLearningRuns((await learningRunsRes.json()).runs || []);
      if (lifecycleHistoryRes.ok) setLifecycleHistory((await lifecycleHistoryRes.json()).history || []);
    } catch (e) {
      console.warn("Failed to fetch RC3 intelligence:", e);
    }
  }, []);

  // Fetch persisted opportunities on mount
  useEffect(() => {
    fetchOpportunities();
    fetchRc3Intel();
  }, [fetchOpportunities, fetchRc3Intel]);

  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-emerald-400";
    if (score >= 60) return "text-amber-400";
    return "text-red-400";
  };

  const getScoreBg = (score: number) => {
    if (score >= 80) return "bg-emerald-950/40 border-emerald-500/30";
    if (score >= 60) return "bg-amber-950/40 border-amber-500/30";
    return "bg-red-950/40 border-red-500/30";
  };
  const contextSourceTotal = Object.values(rc3Intel?.conversation_contexts?.[0]?.context_sources || {})
    .reduce<number>((total, value) => total + Number(value || 0), 0);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-4 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Compass className="h-7 w-7 text-cyan-400" />
              Opportunity Action Center
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Review ranked opportunities, understand match evidence, manage communication, approvals, lifecycle transitions, and follow-ups.
            </p>
          </div>
          <a
            href="/jobs"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-indigo-500/30 bg-indigo-950/30 hover:bg-indigo-950/50 text-indigo-300 text-sm font-medium transition-colors"
          >
            <Briefcase className="h-4 w-4" />
            View Job Pipeline
          </a>
        </div>

        {lastRunId && (
          <div className="text-xs text-slate-500 flex items-center gap-4">
            <span>Run: {lastRunId.slice(0, 8)}...</span>
            <span>Pipeline: {elapsed.toFixed(0)}ms</span>
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-950/20 p-4 flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-amber-400 shrink-0" />
            <p className="text-sm text-amber-300">{error}</p>
          </div>
        )}

        {rc3Intel && (
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-2xl border border-cyan-500/20 bg-cyan-950/20 p-4">
              <p className="text-xs uppercase tracking-wider text-cyan-300 font-semibold">Opportunity Intelligence Panel</p>
              <p className="text-sm text-slate-300 mt-2">
                Latest channel decision: {rc3Intel.decisions?.[0]?.decision || "No decision yet"}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Confidence: {rc3Intel.decisions?.[0]?.decision_confidence ?? "n/a"}
              </p>
              <p className="text-xs text-slate-400 mt-2">
                {rc3Intel.decisions?.[0]?.reason || "CareerOS will explain the next alert decision here."}
              </p>
            </div>
            <div className="rounded-2xl border border-indigo-500/20 bg-indigo-950/20 p-4">
              <p className="text-xs uppercase tracking-wider text-indigo-300 font-semibold">Communication Timeline</p>
              <div className="mt-2 space-y-2">
                {(rc3Intel.communications || []).slice(0, 3).map((item: any) => (
                  <div key={item.id} className="text-xs text-slate-300 flex items-center justify-between gap-3">
                    <span>{item.channel}</span>
                    <span className="text-slate-500">{item.status}</span>
                  </div>
                ))}
                {(rc3Intel.communications || []).length === 0 && (
                  <p className="text-xs text-slate-500">No communication requests yet.</p>
                )}
              </div>
            </div>
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/20 p-4">
              <p className="text-xs uppercase tracking-wider text-emerald-300 font-semibold">Memory Insights</p>
              <p className="text-sm text-slate-300 mt-2">
                Context sources: {contextSourceTotal}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Outcomes tracked: {(rc3Intel.outcomes || []).length}
              </p>
              <p className="text-xs text-slate-400 mt-2">
                Latest memory: {rc3Intel.memory?.[0]?.title || "No career memory recorded yet."}
              </p>
            </div>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-violet-500/20 bg-violet-950/20 p-4">
            <p className="text-xs uppercase tracking-wider text-violet-300 font-semibold">Outcome Intelligence Panel</p>
            {callOutcomes.length > 0 ? (
              <div className="mt-3 space-y-2">
                {callOutcomes.slice(0, 3).map((outcome) => (
                  <div key={outcome.id} className="border-t border-violet-500/10 pt-2 text-xs text-slate-300">
                    <div className="flex justify-between gap-3">
                      <span className="font-semibold text-violet-200">{outcome.outcome}</span>
                      <span>{Math.round(Number(outcome.confidence || 0) * 100)}% confidence</span>
                    </div>
                    <p className="mt-1">Interest: {outcome.interest_level} · Concern: {outcome.primary_concern || "None identified"}</p>
                    <p className="text-slate-500">Follow-up: {outcome.followup_required ? "Required" : "Not required"}</p>
                  </div>
                ))}
              </div>
            ) : <p className="text-xs text-slate-500 mt-3">Completed call outcomes will appear here.</p>}
          </div>
          <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/20 p-4">
            <p className="text-xs uppercase tracking-wider text-emerald-300 font-semibold">Candidate Memory Panel</p>
            {candidateMemory.length > 0 ? (
              <div className="mt-3 grid grid-cols-2 gap-2">
                {candidateMemory.slice(0, 6).map((memory, index) => (
                  <div key={`${memory.type}-${memory.value}-${index}`} className="rounded-lg border border-emerald-500/10 p-2 text-xs">
                    <p className="text-emerald-200">{String(memory.type).replace(/_/g, " ")}</p>
                    <p className="text-slate-300 mt-1">{memory.value}</p>
                    <p className="text-slate-500">{Math.round(Number(memory.confidence || 0) * 100)}% confidence</p>
                  </div>
                ))}
              </div>
            ) : <p className="text-xs text-slate-500 mt-3">Preferences learned from real conversations will appear here.</p>}
          </div>
        </div>
        <div className="rounded-2xl border border-blue-500/20 bg-blue-950/20 p-4">
          <p className="text-xs uppercase tracking-wider text-blue-300 font-semibold">Lifecycle Timeline</p>
          {lifecycleHistory.length ? lifecycleHistory.slice(0, 5).map((item, index) => (
            <div key={`${item.created_at}-${index}`} className="mt-3 flex justify-between border-t border-blue-500/10 pt-3 text-xs">
              <span>{item.from_state || "START"} to {item.to_state}</span><span className="text-slate-500">{item.reason}</span>
            </div>
          )) : <p className="mt-3 text-xs text-slate-500">No job-linked lifecycle transitions recorded</p>}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-2xl border border-amber-500/20 bg-amber-950/20 p-4">
            <p className="text-xs uppercase tracking-wider text-amber-300 font-semibold">Follow-Up Center</p>
            <p className="text-2xl font-bold mt-2">{followups.filter((x) => x.status === "PENDING").length}</p>
            <p className="text-xs text-slate-400">pending tasks and scheduled callbacks</p>
          </div>
          <div className="rounded-2xl border border-blue-500/20 bg-blue-950/20 p-4">
            <p className="text-xs uppercase tracking-wider text-blue-300 font-semibold">Application Lifecycle Center</p>
            <p className="text-sm text-slate-200 mt-2">{lifecycles[0]?.state || "No active lifecycle"}</p>
            <p className="text-xs text-slate-400">{lifecycles.length} tracked opportunities</p>
          </div>
          <div className="rounded-2xl border border-pink-500/20 bg-pink-950/20 p-4">
            <p className="text-xs uppercase tracking-wider text-pink-300 font-semibold">Career Intelligence Center</p>
            <p className="text-sm text-slate-200 mt-2">{careerProgress[0]?.value || "No conversion data yet"}</p>
            <p className="text-xs text-slate-400">top-performing role category</p>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/20 p-4">
            <p className="text-xs uppercase tracking-wider text-emerald-300 font-semibold">Candidate Memory History</p>
            <p className="text-2xl font-bold mt-2">{memoryHistory.length}</p>
            <p className="text-xs text-slate-400">{memoryHistory[0]?.evidence || "No transcript-backed preference history yet"}</p>
          </div>
          <div className="rounded-2xl border border-cyan-500/20 bg-cyan-950/20 p-4">
            <p className="text-xs uppercase tracking-wider text-cyan-300 font-semibold">Opportunity Explanations</p>
            <p className="text-2xl font-bold mt-2">{reranked.length}</p>
            <p className="text-xs text-slate-400">{reranked[0]?.explanation?.memory_reason || "No memory-driven reranking evidence yet"}</p>
          </div>
          <div className="rounded-2xl border border-violet-500/20 bg-violet-950/20 p-4">
            <p className="text-xs uppercase tracking-wider text-violet-300 font-semibold">Learning Loop Monitor</p>
            <p className="text-sm text-slate-200 mt-2">{learningRuns[0]?.status || "No autonomous run recorded"}</p>
            <p className="text-xs text-slate-400">{learningRuns.length} recorded runs</p>
          </div>
        </div>

        {loading && opportunities.length === 0 && (
          <div className="flex items-center justify-center h-64 text-slate-400">
            <RefreshCw className="h-5 w-5 animate-spin mr-2" />
            Fetching real provider opportunities...
          </div>
        )}

        {/* Opportunity Action Center - no duplicate ranked list */}
        {opportunities.length > 0 && (
          <div className="rounded-2xl border border-slate-700 bg-slate-900/40 p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-white">Tracked Opportunities</h3>
                <p className="text-xs text-slate-500 mt-1">{opportunities.length} opportunities with active lifecycle tracking</p>
              </div>
              <a href="/jobs" className="text-xs text-indigo-400 hover:text-indigo-300 font-medium">View Ranked Jobs →</a>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              {opportunities.slice(0, 6).map((opp) => (
                <div
                  key={opp.id}
                  className="rounded-xl border border-slate-700 bg-slate-800/40 p-3"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-white">{opp.title}</p>
                      <p className="text-xs text-slate-400">{opp.company}</p>
                    </div>
                    <span className={`text-lg font-bold ${getScoreColor(opp.overall_score)}`}>
                      {opp.overall_score.toFixed(0)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {opportunities.length === 0 && (
          <div className="rounded-2xl border border-slate-700 bg-slate-900/40 p-8 text-center">
            <Search className="h-8 w-8 text-slate-600 mx-auto mb-3" />
            <p className="text-sm text-slate-400">No tracked opportunities yet. Select a job from Jobs and choose Track as Opportunity.</p>
            <a href="/jobs" className="inline-block mt-3 text-xs text-indigo-400 hover:text-indigo-300 font-medium">Go to Ranked Jobs →</a>
          </div>
        )}
      </div>
    </div>
  );
}
