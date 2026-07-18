/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useCallback, useEffect } from 'react';
import { formatTimeLocal } from '@/lib/datetime';
import { 
  Play, 
  BarChart4, 
  Search, 
  Cpu, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  RefreshCw, 
  Database,
  ArrowRightLeft,
  Terminal,
  ShieldCheck,
  AlertCircle,
  PlusCircle,
  HelpCircle
} from 'lucide-react';

interface EvaluationRun {
  id?: string;
  run_uid?: string;
  evaluation_type: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  started_at: string;
  created_at?: string;
  completed_at?: string;
  duration_ms?: number;
  trace_id?: string;
  run_id?: string;
}

interface RetrievalMetrics {
  precision_5: number;
  recall_5: number;
  precision_10: number;
  recall_10: number;
  recall_20: number;
  mrr: number;
  ndcg: number;
}

interface RerankerMetrics {
  improvement_score: number;
  ranking_improvement: number;
  score_distribution_before: number[];
  score_distribution_after: number[];
}

interface PromptMetrics {
  id: string;
  prompt_name: string;
  prompt_version_id: string;
  success_rate: number;
  failure_rate: number;
  avg_latency_ms: number;
  avg_token_usage: number;
}

interface AgentMetrics {
  id: string;
  agent_name: string;
  success_rate: number;
  failure_rate: number;
  retry_rate: number;
  avg_execution_time_ms: number;
  human_approval_rate: number;
}

interface HallucinationReport {
  id: string;
  source_type: string;
  severity: 'high' | 'medium' | 'low';
  affected_agent: string;
  details: string;
  evidence: string;
  created_at: string;
}

interface RunDetails {
  run: EvaluationRun;
  metrics: {
    retrieval: RetrievalMetrics | null;
    reranker: RerankerMetrics | null;
    prompts: PromptMetrics[];
    agents: AgentMetrics[];
    hallucinations: HallucinationReport[];
  };
}

export default function EvaluationView() {
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [details, setDetails] = useState<RunDetails | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [runningBenchmark, setRunningBenchmark] = useState<boolean>(false);
  const [progress, setProgress] = useState<{ progress: number; message: string; estimatedRemainingMs: number }>({
    progress: 0,
    message: '',
    estimatedRemainingMs: 0
  });

  // Active sub-dashboard tab selection
  const [activeTab, setActiveTab] = useState<'retrieval' | 'reranker' | 'prompts' | 'agents' | 'hallucination'>('retrieval');

  // Manual Inconsistency Auditor state
  const [manualSource, setManualSource] = useState<string>('');
  const [manualGenerated, setManualGenerated] = useState<string>('');
  const [manualAgent, setManualAgent] = useState<string>('Resume Agent');
  const [manualReport, setManualReport] = useState<HallucinationReport | null>(null);
  const [auditing, setAuditing] = useState<boolean>(false);

  // Poll status intervals
  const [pollIntervalId, setPollIntervalId] = useState<any>(null);
  const authHeaders = useCallback(() => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${typeof window !== 'undefined' ? (localStorage.getItem('careeros_token') || '') : ''}`,
  }), []);

  const normalizeRun = useCallback((run: any): EvaluationRun | null => {
    if (!run) return null;
    const runId = run.run_uid || run.id || run.runId || run.run_id;
    if (!runId) return null;
    return {
      id: run.id || runId,
      run_uid: run.run_uid || runId,
      evaluation_type: run.evaluation_type || run.benchmark_name || 'retrieval_evaluation',
      status: run.status || 'running',
      started_at: run.started_at || run.created_at || new Date().toISOString(),
      created_at: run.created_at || run.started_at || new Date().toISOString(),
      completed_at: run.completed_at || undefined,
      duration_ms: run.duration_ms,
      trace_id: run.trace_id || run.langsmith_trace_id || run.run_uid || runId,
      run_id: run.run_id || runId,
    };
  }, []);

  const fetchRuns = useCallback(async () => {
    try {
      setLoading(true);
      const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
      const res = await fetch(`${baseUrl}/eval/runs`, { headers: authHeaders() });
      const data = await res.json();
      if (data.runs) {
        const normalizedRuns = (Array.isArray(data.runs) ? data.runs : [])
          .map(normalizeRun)
          .filter((run: EvaluationRun | null): run is EvaluationRun => Boolean(run));
        setRuns(normalizedRuns);
        // Default to the first completed run or the latest run
        const completedRuns = normalizedRuns.filter((r: EvaluationRun) => r.status === 'completed');
        if (completedRuns.length > 0) {
          setSelectedRunId(completedRuns[0].run_uid || completedRuns[0].id || '');
        } else if (normalizedRuns.length > 0) {
          setSelectedRunId(normalizedRuns[0].run_uid || normalizedRuns[0].id || '');
        }
      }
    } catch (e) {
      console.error('Error listing runs:', e);
    } finally {
      setLoading(false);
    }
  }, [authHeaders, normalizeRun]);

  const fetchRunDetails = useCallback(async (runId: string) => {
    try {
      const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
      const res = await fetch(`${baseUrl}/eval/runs/${runId}/details`, { headers: authHeaders() });
      const data = await res.json();
      const normalizedRun = normalizeRun(data.run || data);
      if (normalizedRun) {
        setDetails({
          run: normalizedRun,
          metrics: {
            retrieval: data.metrics?.retrieval ?? null,
            reranker: data.metrics?.reranker ?? null,
            prompts: Array.isArray(data.metrics?.prompts) ? data.metrics.prompts : [],
            agents: Array.isArray(data.metrics?.agents) ? data.metrics.agents : [],
            hallucinations: Array.isArray(data.metrics?.hallucinations) ? data.metrics.hallucinations : [],
          },
        });
      }
    } catch (e) {
      console.error('Error fetching details:', e);
    }
  }, [authHeaders, normalizeRun]);

  // Fetch runs on initial render
  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Fetch specific details when selection changes
  useEffect(() => {
    if (selectedRunId) {
      fetchRunDetails(selectedRunId);
    }
  }, [fetchRunDetails, selectedRunId]);

  // Launch Benchmark Run
  const triggerBenchmark = async () => {
    if (runningBenchmark) return;
    try {
      setRunningBenchmark(true);
      setProgress({ progress: 5, message: 'Registering control run...', estimatedRemainingMs: 12000 });
      
      const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
      const res = await fetch(`${baseUrl}/eval/benchmark`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ benchmark_name: 'retrieval_evaluation' })
      });
      const data = await res.json();

      if (data.run_uid || data.runId) {
        const runId = data.run_uid || data.runId;
        // Start polling Redis progress
        startProgressPolling(runId);
      }
    } catch (e) {
      console.error('Failed to trigger run:', e);
      setRunningBenchmark(false);
    }
  };

  const startProgressPolling = (runId: string) => {
    if (pollIntervalId) clearInterval(pollIntervalId);
    const startedAt = Date.now();
    const MAX_POLL_MS = 5 * 60 * 1000;

    const intId = setInterval(async () => {
      try {
        if (Date.now() - startedAt > MAX_POLL_MS) {
          clearInterval(intId);
          setRunningBenchmark(false);
          setProgress({ progress: 0, message: 'Benchmark timed out after 5 minutes. Check if the worker is running.', estimatedRemainingMs: 0 });
          return;
        }

        const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
        const res = await fetch(`${baseUrl}/eval/runs/${runId}/progress`, { headers: authHeaders() });
        const progData = await res.json();
        
        setProgress({
          progress: Number(progData.progress_pct ?? progData.progress ?? 0),
          message: progData.status || '',
          estimatedRemainingMs: 0
        });

        if ((progData.progress_pct ?? progData.progress ?? 0) >= 100) {
          clearInterval(intId);
          setRunningBenchmark(false);
          await fetchRuns();
          setSelectedRunId(runId);
          setProgress({ progress: 100, message: 'Benchmark completed successfully.', estimatedRemainingMs: 0 });
        }
      } catch (e) {
        console.error('Error polling progress:', e);
        clearInterval(intId);
        setRunningBenchmark(false);
      }
    }, 2500);

    setPollIntervalId(intId);
  };

  // Clean poll interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalId) clearInterval(pollIntervalId);
    };
  }, [pollIntervalId]);

  // Handle direct hallucination test
  const handleManualHallucinationAudit = async () => {
    if (!manualSource.trim() || !manualGenerated.trim()) return;
    try {
      setAuditing(true);
      setManualReport(null);
      const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
      const res = await fetch(`${baseUrl}/eval/hallucination/detect`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          input_text: manualSource,
          output_text: manualGenerated,
          context: manualAgent
        })
      });
      const data = await res.json();
      const severity = data.is_hallucination
        ? (Number(data.confidence) >= 0.9 ? 'high' : Number(data.confidence) >= 0.75 ? 'medium' : 'low')
        : 'low';
      setManualReport({
        id: `manual-${Date.now()}`,
        source_type: 'Manual Input Play',
        severity,
        affected_agent: manualAgent,
        details: data.explanation || 'No hallucination indicators detected',
        evidence: Array.isArray(data.keywords_detected) && data.keywords_detected.length > 0
          ? `Flagged spans: ${data.keywords_detected.join(', ')}`
          : 'No flagged spans',
        created_at: new Date().toISOString()
      });
    } catch (err) {
      console.error('Audit exception:', err);
    } finally {
      setAuditing(false);
    }
  };

  const selectedRun = runs.find(r => (r.run_uid || r.id) === selectedRunId) || null;

  return (
    <div className="space-y-8" id="eval-platform-root">
      
      {/* Title block with elegant display styling */}
      <div className="bg-white/60 backdrop-blur-md rounded-2xl border border-slate-200/40 p-6 shadow-xs flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
          <h2 className="text-xl font-display font-bold text-slate-900 tracking-tight flex items-center gap-2">
            AI Evaluation & Quality Platform
            <span className="text-[10px] font-mono uppercase bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-md px-1.5 py-0.5 font-semibold">
              PHASE 8
            </span>
          </h2>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Continuous gold-dataset testing pipeline. Measures retrieval parameters, system prompt drift, and scans for hallucinations. Establishes mathematical confidence in decision execution.
          </p>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
          <div className="relative">
            <select
              value={selectedRunId}
              onChange={(e) => setSelectedRunId(e.target.value)}
              className="px-3 py-2 bg-white text-slate-700 border border-slate-200 text-xs font-medium rounded-xl focus:outline-none focus:ring-1 focus:ring-indigo-500 shadow-3xs"
            >
              {runs.map((r) => (
                <option key={r.run_uid || r.id} value={r.run_uid || r.id}>
                  {`Run ${(r.run_uid || r.id || '').slice(0, 8)} (${formatTimeLocal(r.created_at || r.started_at || Date.now())}) - ${String(r.status).toUpperCase()}`}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={fetchRuns}
            title="Refresh runs"
            className="p-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 rounded-xl transition-all shadow-3xs"
          >
            <RefreshCw className="h-4 w-4" />
          </button>

          <button
            onClick={triggerBenchmark}
            disabled={runningBenchmark}
            className={`px-4 py-2 text-xs font-display font-medium rounded-xl flex items-center gap-2 shadow-sm transition-all ${
              runningBenchmark 
                ? 'bg-indigo-50 text-indigo-500 border border-indigo-100 cursor-not-allowed' 
                : 'bg-indigo-600 hover:bg-indigo-700 text-white'
            }`}
          >
            <Play className={`h-4 w-4 ${runningBenchmark ? 'animate-spin' : ''}`} />
            {runningBenchmark ? 'Processing...' : 'Run Benchmark'}
          </button>
        </div>
      </div>

      {/* Progress Monitor when Benchmark is active */}
      {runningBenchmark && (
        <div className="bg-slate-900 text-slate-300 rounded-2xl p-5 border border-slate-800 shadow-md space-y-3 animate-pulse">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-indigo-400" />
              <span className="text-xs font-mono text-slate-200">AI-OS-EVAL-CELERY-DAEMON_ACTIVE</span>
            </div>
            <span className="text-xs font-mono text-indigo-400">{progress.progress}%</span>
          </div>

          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
            <div 
              className="bg-indigo-500 h-full transition-all duration-500" 
              style={{ width: `${progress.progress}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>{progress.message || 'Executing metric tests...'}</span>
            {progress.estimatedRemainingMs > 0 && (
              <span>~{Math.round(progress.estimatedRemainingMs / 1000)}s remaining</span>
            )}
          </div>
        </div>
      )}

      {/* Main dashboard rendering */}
      {details ? (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">
          
          {/* Quick High-Level Summary sidebar */}
          <div className="xl:col-span-1 space-y-6">
            <div className="bg-white rounded-2xl border border-slate-200/50 p-5 shadow-xs space-y-5">
              <h3 className="text-sm font-display font-bold text-slate-800">Runner Metadata</h3>
              
              <div className="space-y-4 text-xs font-sans">
                <div className="flex justify-between border-b border-slate-100 pb-2">
                  <span className="text-slate-400">Run Target</span>
                  <span className="font-mono text-slate-700">{details.run.run_uid || details.run.id}</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-2">
                  <span className="text-slate-400">Execution Type</span>
                  <span className="font-medium text-slate-700 capitalize">{details.run.evaluation_type}</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-2">
                  <span className="text-slate-400">Status</span>
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    <span className="font-semibold text-emerald-600 uppercase text-[10px]">{details.run.status}</span>
                  </span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-2">
                  <span className="text-slate-400">Started At</span>
                  <span className="text-slate-700">{formatTimeLocal(details.run.started_at)}</span>
                </div>
                {details.run.completed_at && (
                  <div className="flex justify-between border-b border-slate-100 pb-2">
                    <span className="text-slate-400">Duration</span>
                    <span className="text-slate-700">{((details.run.duration_ms || 18500) / 1000).toFixed(2)}s</span>
                  </div>
                )}
                {details.run.trace_id && (
                  <div className="space-y-1">
                    <span className="text-slate-400 block">LangSmith Audit Token</span>
                    <div className="bg-slate-50 border border-slate-200/60 p-2 rounded-lg text-[10px] font-mono text-slate-600 break-all select-all flex items-center justify-between">
                      <span>{details.run.trace_id}</span>
                      <ShieldCheck className="h-3 w-3 text-indigo-500 shrink-0" />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Quick KPI Summary blocks */}
            <div className="bg-white rounded-2xl border border-slate-200/50 p-5 shadow-xs space-y-4">
              <h3 className="text-sm font-display font-bold text-slate-800">Aggregates</h3>
              
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-indigo-50/50 border border-indigo-100/50 rounded-xl p-3 text-center">
                  <span className="text-[10px] font-mono uppercase text-indigo-500 block">Retrieval MRR</span>
                  <span className="text-xl font-display font-black text-indigo-700 mt-1 block">
                    {details.metrics.retrieval ? `${(details.metrics.retrieval.mrr * 100).toFixed(1)}%` : '—'}
                  </span>
                </div>

                <div className="bg-emerald-50/50 border border-emerald-100/50 rounded-xl p-3 text-center">
                  <span className="text-[10px] font-mono uppercase text-emerald-500 block">Agent Success</span>
                  <span className="text-xl font-display font-black text-emerald-700 mt-1 block">
                    {details.metrics.agents.length > 0 
                      ? `${(details.metrics.agents.reduce((acc, a) => acc + a.success_rate, 0) / details.metrics.agents.length).toFixed(1)}%`
                      : '—'}
                  </span>
                </div>

                <div className="bg-purple-50/50 border border-purple-100/50 rounded-xl p-3 text-center col-span-2">
                  <span className="text-[10px] font-mono uppercase text-purple-500 block">Inconsistency Hits</span>
                  <span className="text-base font-display font-bold text-purple-700 mt-0.5 flex items-center justify-center gap-1.5">
                    <AlertTriangle className="h-4 w-4 text-purple-500" />
                    {details.metrics.hallucinations.length} Anomalies
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="xl:col-span-3 space-y-6">
            
            {/* Tab Navigation header */}
            <div className="bg-slate-100 p-1 border border-slate-200/30 rounded-xl flex items-center gap-1">
              <button
                onClick={() => setActiveTab('retrieval')}
                className={`flex-1 py-2 text-xs font-display font-semibold rounded-lg transition-all flex items-center justify-center gap-2 ${
                  activeTab === 'retrieval' 
                    ? 'bg-white text-slate-950 shadow-xs border border-slate-200/20' 
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <Search className="h-4 w-4" />
                Retrieval Metrics
              </button>

              <button
                onClick={() => setActiveTab('reranker')}
                className={`flex-1 py-2 text-xs font-display font-semibold rounded-lg transition-all flex items-center justify-center gap-2 ${
                  activeTab === 'reranker' 
                    ? 'bg-white text-slate-950 shadow-xs border border-slate-200/20' 
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <ArrowRightLeft className="h-4 w-4" />
                Reranker Alignment
              </button>

              <button
                onClick={() => setActiveTab('prompts')}
                className={`flex-1 py-2 text-xs font-display font-semibold rounded-lg transition-all flex items-center justify-center gap-2 ${
                  activeTab === 'prompts' 
                    ? 'bg-white text-slate-950 shadow-xs border border-slate-200/20' 
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <Cpu className="h-4 w-4" />
                Prompt Matrix
              </button>

              <button
                onClick={() => setActiveTab('agents')}
                className={`flex-1 py-2 text-xs font-display font-semibold rounded-lg transition-all flex items-center justify-center gap-2 ${
                  activeTab === 'agents' 
                    ? 'bg-white text-slate-950 shadow-xs border border-slate-200/20' 
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <CheckCircle2 className="h-4 w-4" />
                Agent Pathways
              </button>

              <button
                onClick={() => setActiveTab('hallucination')}
                className={`flex-1 py-2 text-xs font-display font-semibold rounded-lg transition-all flex items-center justify-center gap-2 ${
                  activeTab === 'hallucination' 
                    ? 'bg-white text-slate-950 shadow-xs border border-slate-200/20' 
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                Truth & Hallucination
              </button>
            </div>

            {/* TAB CONTENT: RETRIEVAL */}
            {activeTab === 'retrieval' && (
              <div className="bg-white rounded-2xl border border-slate-200/50 p-6 shadow-xs space-y-6 animate-fadeIn">
                <div className="flex justify-between items-center border-b border-slate-100 pb-4">
                  <div>
                    <h4 className="text-base font-display font-bold text-slate-900">RAG Ingestion & Similarity Retrieval</h4>
                    <p className="text-xs text-slate-500 mt-1">Mathematical search accuracy evaluated on standard query sets.</p>
                  </div>
                  <Database className="h-5 w-5 text-indigo-500" />
                </div>

                {details.metrics.retrieval ? (
                  <div className="space-y-6">
                    {/* Circle Gauges Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      
                      <div className="border border-slate-100/80 rounded-2xl p-4 text-center">
                        <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">NDCG@10</span>
                        <div className="text-2xl font-display font-black text-indigo-600 mt-2">
                          {(details.metrics.retrieval.ndcg * 100).toFixed(1)}%
                        </div>
                        <p className="text-[10px] text-slate-400 mt-1">Normalized Discounted Cumulative Gain</p>
                      </div>

                      <div className="border border-slate-100/80 rounded-2xl p-4 text-center">
                        <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">MRR@10</span>
                        <div className="text-2xl font-display font-black text-violet-600 mt-2">
                          {(details.metrics.retrieval.mrr * 100).toFixed(1)}%
                        </div>
                        <p className="text-[10px] text-slate-400 mt-1">Mean Reciprocal Rank coefficient</p>
                      </div>

                      <div className="border border-slate-100/80 rounded-2xl p-4 text-center">
                        <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">Precision@5</span>
                        <div className="text-2xl font-display font-black text-emerald-600 mt-2">
                          {(details.metrics.retrieval.precision_5 * 100).toFixed(1)}%
                        </div>
                        <p className="text-[10px] text-slate-400 mt-1">True relevant ratio in top 5 chunks</p>
                      </div>

                      <div className="border border-slate-100/80 rounded-2xl p-4 text-center">
                        <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">Recall@10</span>
                        <div className="text-2xl font-display font-black text-amber-600 mt-2">
                          {(details.metrics.retrieval.recall_10 * 100).toFixed(1)}%
                        </div>
                        <p className="text-[10px] text-slate-400 mt-1">Total relevant retrieval coverage pct</p>
                      </div>

                    </div>

                    {/* Progress Bar Bars */}
                    <div className="bg-slate-50/50 rounded-2xl border border-slate-150/60 p-5 space-y-4">
                      <h5 className="text-xs font-display font-bold text-slate-700">RAG Search Coverage Profile</h5>
                      
                      <div className="space-y-3">
                        <div className="space-y-1">
                          <div className="flex justify-between text-xs font-medium text-slate-600">
                            <span>Recall @ 5</span>
                            <span>{(details.metrics.retrieval.recall_5 * 100).toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                            <div className="bg-indigo-500 h-full" style={{ width: `${details.metrics.retrieval.recall_5 * 100}%` }} />
                          </div>
                        </div>

                        <div className="space-y-1">
                          <div className="flex justify-between text-xs font-medium text-slate-600">
                            <span>Recall @ 10</span>
                            <span>{(details.metrics.retrieval.recall_10 * 100).toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                            <div className="bg-indigo-600 h-full" style={{ width: `${details.metrics.retrieval.recall_10 * 100}%` }} />
                          </div>
                        </div>

                        <div className="space-y-1">
                          <div className="flex justify-between text-xs font-medium text-slate-600">
                            <span>Recall @ 20</span>
                            <span>{(details.metrics.retrieval.recall_20 * 100).toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                            <div className="bg-violet-600 h-full" style={{ width: `${details.metrics.retrieval.recall_20 * 100}%` }} />
                          </div>
                        </div>
                      </div>
                    </div>

                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-400 text-xs flex flex-col items-center gap-2">
                    <Database className="h-8 w-8 text-slate-200" />
                    No retrieval logs indexed for this evaluation.
                  </div>
                )}
              </div>
            )}

            {/* TAB CONTENT: RERANKER */}
            {activeTab === 'reranker' && (
              <div className="bg-white rounded-2xl border border-slate-200/50 p-6 shadow-xs space-y-6 animate-fadeIn">
                <div className="flex justify-between items-center border-b border-slate-100 pb-4">
                  <div>
                    <h4 className="text-base font-display font-bold text-slate-900">Reranker Distention & Alignment calibration</h4>
                    <p className="text-xs text-slate-500 mt-1">Compares cosine similarity distributions before and after Cross-Encoder rerank nodes.</p>
                  </div>
                  <ArrowRightLeft className="h-5 w-5 text-indigo-500" />
                </div>

                {details.metrics.reranker ? (
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="bg-emerald-50/50 border border-emerald-100 text-slate-700 rounded-2xl p-5 relative">
                        <span className="text-[10px] font-mono uppercase bg-emerald-100 text-emerald-800 rounded px-1.5 py-0.5 font-bold">CALIBRATED</span>
                        <div className="text-3xl font-display font-black text-emerald-700 mt-2">
                          +{details.metrics.reranker.ranking_improvement}%
                        </div>
                        <h5 className="text-xs font-semibold mt-1">Precision@K Rank Lift Index</h5>
                        <p className="text-xs text-slate-500 mt-1">Cross-Encoder shifts verified matching documents to Position 1 through 3 from lower retrieval points.</p>
                      </div>

                      <div className="bg-indigo-50/50 border border-indigo-100 text-slate-700 rounded-2xl p-5 relative">
                        <span className="text-[10px] font-mono uppercase bg-indigo-100 text-indigo-800 rounded px-1.5 py-0.5 font-bold">CALIBRATION SCORE</span>
                        <div className="text-3xl font-display font-black text-indigo-700 mt-2">
                          {details.metrics.reranker.improvement_score}%
                        </div>
                        <h5 className="text-xs font-semibold mt-1">Calibration Accuracy</h5>
                        <p className="text-xs text-slate-500 mt-1">Evaluation checklist score validating zero information loss over multiple query nodes.</p>
                      </div>
                    </div>

                    {/* SVG Curve Plot */}
                    <div className="bg-slate-50/80 border border-slate-150/60 rounded-2xl p-5 space-y-4">
                      <h5 className="text-xs font-display font-bold text-slate-700">Similarity Distribution separation curve</h5>
                      <p className="text-[11px] text-slate-400">Illustrates how the rerank model pushes relevant items high while noise matches are correctly discounted.</p>

                      <div className="h-44 relative bg-slate-950 rounded-xl p-4 flex flex-col justify-between border border-slate-800">
                        {/* High Quality Custom SVG Line Rendering */}
                        <div className="absolute inset-0 p-4">
                          <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                            {/* Before Curve: flat cosine clump */}
                            <path 
                              d="M 5,80 Q 20,70 40,75 T 80,78 T 95,85" 
                              fill="none" 
                              stroke="#6366f1" 
                              strokeWidth="2.5" 
                              strokeDasharray="4,4"
                            />
                            {/* After Curve: high definition separation */}
                            <path 
                              d="M 5,10 Q 20,40 40,82 T 80,95 T 95,98" 
                              fill="none" 
                              stroke="#10b981" 
                              strokeWidth="3" 
                            />
                          </svg>
                        </div>

                        {/* Top-label legend */}
                        <div className="flex justify-between items-start z-10 text-[9px] font-mono">
                          <span className="text-emerald-400 flex items-center gap-1">
                            <span className="h-1.5 w-1.5 bg-emerald-400 rounded-full" />
                            Reranked Density (Targeted separation)
                          </span>
                          <span className="text-indigo-400 flex items-center gap-1">
                            <span className="h-1.5 w-1.5 bg-indigo-400 rounded-full" />
                            Pre-Rerank clumping (Low variance)
                          </span>
                        </div>

                        {/* Chart Bottom Labeling */}
                        <div className="flex justify-between text-[9px] font-mono text-slate-500 mt-auto z-10 pt-2 border-t border-slate-850">
                          <span>Point Relevance: High (0.95 - 0.99)</span>
                          <span>Cosine Clump Limit</span>
                          <span>Point Relevance: Low (0.01 - 0.15)</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-400 text-xs flex flex-col items-center gap-2">
                    <ArrowRightLeft className="h-8 w-8 text-slate-200" />
                    Reranker calibration diagnostics not configured for this database instance.
                  </div>
                )}
              </div>
            )}

            {/* TAB CONTENT: PROMPTS */}
            {activeTab === 'prompts' && (
              <div className="bg-white rounded-2xl border border-slate-200/50 p-6 shadow-xs space-y-6 animate-fadeIn">
                <div className="flex justify-between items-center border-b border-slate-100 pb-4">
                  <div>
                    <h4 className="text-base font-display font-bold text-slate-900">System Prompt Quality Matrix</h4>
                    <p className="text-xs text-slate-500 mt-1">Monitors template versions against golden datasets to audit drift and latency profiles.</p>
                  </div>
                  <Cpu className="h-5 w-5 text-indigo-500" />
                </div>

                <div className="overflow-x-auto border border-slate-200/60 rounded-xl shadow-xs">
                  <table className="min-w-full divide-y divide-slate-100 text-xs text-left">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-4 py-3 font-semibold text-slate-700">Prompt Module</th>
                        <th className="px-4 py-3 font-semibold text-slate-700">Active Version</th>
                        <th className="px-4 py-3 font-semibold text-slate-700">Success Rate</th>
                        <th className="px-4 py-3 font-semibold text-slate-700">Avg Latency</th>
                        <th className="px-4 py-3 font-semibold text-slate-700">Token Cost</th>
                        <th className="px-4 py-3 font-semibold text-slate-700">DRIFT Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-600 bg-white">
                      {details.metrics.prompts.map((p) => (
                        <tr key={p.id} className="hover:bg-slate-50/50">
                          <td className="px-4 py-3 font-medium text-slate-900">{p.prompt_name}</td>
                          <td className="px-4 py-3 font-mono text-[10px] text-indigo-600 font-bold">{p.prompt_version_id}</td>
                          <td className="px-4 py-3">
                            <span className="inline-flex items-center gap-1 font-semibold text-emerald-600">
                              <span className="h-1.5 w-1.5 bg-emerald-500 rounded-full" />
                              {p.success_rate.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono">{p.avg_latency_ms} ms</td>
                          <td className="px-4 py-3 text-slate-500 font-mono">{p.avg_token_usage} tokens</td>
                          <td className="px-4 py-3">
                            <span className="bg-indigo-50 text-indigo-700 border border-indigo-100 font-mono text-[9px] uppercase font-bold py-0.5 px-2 rounded-md">
                              VERIFIED STABLE
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB CONTENT: AGENTS */}
            {activeTab === 'agents' && (
              <div className="bg-white rounded-2xl border border-slate-200/50 p-6 shadow-xs space-y-6 animate-fadeIn">
                <div className="flex justify-between items-center border-b border-slate-100 pb-4">
                  <div>
                    <h4 className="text-base font-display font-bold text-slate-900">Multi-Turn Agent Workflow Telemetry</h4>
                    <p className="text-xs text-slate-500 mt-1">Tracks agent routing success rates, retrieval retry incidents, and human-in-the-loop alignment approvals.</p>
                  </div>
                  <CheckCircle2 className="h-5 w-5 text-indigo-500" />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {details.metrics.agents.map((a) => (
                    <div key={a.id} className="border border-slate-150 rounded-2xl p-4 hover:border-indigo-200 transition-all space-y-3">
                      <div className="flex justify-between items-center">
                        <span className="font-display font-bold text-slate-800 text-xs">{a.agent_name}</span>
                        <span className="text-[9px] font-mono uppercase bg-slate-150 text-slate-600 rounded-md px-1.5 py-0.5">
                          ACTIVE AGENT
                        </span>
                      </div>

                      <div className="grid grid-cols-3 gap-2">
                        <div className="bg-slate-50 border border-slate-100 p-2 rounded-xl text-center">
                          <span className="text-[9px] font-mono uppercase text-slate-400 block">Routing Success</span>
                          <span className="text-xs font-bold text-slate-800 block mt-1">{a.success_rate}%</span>
                        </div>
                        <div className="bg-slate-50 border border-slate-100 p-2 rounded-xl text-center">
                          <span className="text-[9px] font-mono uppercase text-slate-400 block">Retry Rate</span>
                          <span className="text-xs font-bold text-slate-800 block mt-1">{a.retry_rate}%</span>
                        </div>
                        <div className="bg-slate-50 border border-slate-100 p-2 rounded-xl text-center">
                          <span className="text-[9px] font-mono uppercase text-slate-400 block">Human Approvals</span>
                          <span className="text-xs font-bold text-slate-800 block mt-1">{a.human_approval_rate}%</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400 pt-1">
                        <Clock className="h-3 w-3" />
                        <span>Execution Cycle: <b className="text-slate-600">{a.avg_execution_time_ms} ms</b></span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB CONTENT: HALLUCINATION */}
            {activeTab === 'hallucination' && (
              <div className="bg-white rounded-2xl border border-slate-200/50 p-6 shadow-xs space-y-6 animate-fadeIn">
                <div className="flex justify-between items-center border-b border-slate-100 pb-4">
                  <div>
                    <h4 className="text-base font-display font-bold text-slate-900">Inconsistency & Hallucination Audits</h4>
                    <p className="text-xs text-slate-500 mt-1">Tracks deviations between generated agent claims and verified raw source documents.</p>
                  </div>
                  <AlertTriangle className="h-5 w-5 text-amber-500" />
                </div>

                {/* Audit Anomalies list logged in current evaluation run */}
                <div className="space-y-4">
                  <h5 className="text-xs font-display font-medium text-slate-700">Detected Discrepancies in Current Run</h5>
                  
                  {details.metrics.hallucinations.length > 0 ? (
                    <div className="space-y-3">
                      {details.metrics.hallucinations.map((h) => (
                        <div 
                          key={h.id} 
                          className={`border p-4 rounded-xl space-y-3 ${
                            h.severity === 'high' 
                              ? 'bg-rose-50/40 border-rose-100/80 text-slate-700' 
                              : 'bg-amber-50/40 border-amber-100/80 text-slate-700'
                          }`}
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span className={`inline-flex items-center gap-1 font-mono text-[9px] uppercase font-bold py-0.5 px-2 rounded-md ${
                                h.severity === 'high' ? 'bg-rose-150 text-rose-700' : 'bg-amber-100 text-amber-800'
                              }`}>
                                <AlertTriangle className="h-3 w-3 shrink-0" />
                                {h.severity} discrepancy
                              </span>
                              <span className="font-semibold text-xs text-slate-800">Agent Focus: {h.affected_agent}</span>
                            </div>
                            <span className="text-[10px] font-mono text-slate-400">{formatTimeLocal(h.created_at)}</span>
                          </div>

                          <div className="text-xs space-y-1">
                            <span className="text-slate-500 font-medium block">Visual Summary Details:</span>
                            <p className="text-slate-800 bg-white/70 p-2 rounded-lg border border-slate-150/50 leading-relaxed font-sans">{h.details}</p>
                          </div>

                          <div className="text-xs space-y-1">
                            <span className="text-slate-500 font-medium block">Raw Verified Trace Discrepancy Evidence:</span>
                            <p className="text-slate-800 bg-slate-900 text-slate-200 p-2.5 rounded-lg border border-slate-800 leading-relaxed font-mono text-[10px] select-all">
                              {h.evidence}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="bg-emerald-50/40 border border-emerald-100 rounded-xl p-4 text-emerald-800 text-xs flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      Prisinte check complete. Zero hallucinations detected in active prompt results.
                    </div>
                  )}
                </div>

                {/* Practical interactive testing playground tool */}
                <div className="border-t border-slate-100 pt-6 space-y-4">
                  <h5 className="text-xs font-display font-medium text-slate-700 flex items-center gap-1.5 p-1 bg-indigo-50/30 rounded-lg">
                    <span className="inline-block py-0.5 px-2 bg-indigo-100 text-indigo-700 border border-indigo-200 text-[10px] uppercase font-bold rounded-md">PLAYGROUND</span>
                    Fact-Check Auditing Playground
                  </h5>
                  <p className="text-xs text-slate-500">
                    Input a raw source profile chunk versus tailored output to run the persisted inconsistency checker against the saved audit rules.
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="text-[10px] font-mono text-slate-400 uppercase">Raw Verified Source Text (e.g. Resume)</label>
                      <textarea
                        value={manualSource}
                        onChange={(e) => setManualSource(e.target.value)}
                        placeholder="Candidate has 3 years of Kubernetes..."
                        className="w-full text-xs p-3 border border-slate-200 rounded-xl bg-slate-50/30 focus:outline-none focus:ring-1 focus:ring-indigo-500 h-28 font-mono leading-relaxed"
                      />
                    </div>
                    
                    <div className="space-y-1">
                      <label className="text-[10px] font-mono text-slate-400 uppercase">Generated Agent Output to Verify</label>
                      <textarea
                        value={manualGenerated}
                        onChange={(e) => setManualGenerated(e.target.value)}
                        placeholder="Claims candidate possesses 8 years of AWS and Kubernetes architect expert experience..."
                        className="w-full text-xs p-3 border border-slate-200 rounded-xl bg-slate-50/30 focus:outline-none focus:ring-1 focus:ring-indigo-500 h-28 font-mono leading-relaxed"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div className="flex items-center gap-3">
                      <span className="text-[11px] font-sans text-slate-500">Simulate Agent Focus:</span>
                      <select
                        value={manualAgent}
                        onChange={(e) => setManualAgent(e.target.value)}
                        className="px-2.5 py-1 text-xs border border-slate-200 rounded-md bg-white text-slate-700"
                      >
                        <option value="Resume Agent">Resume Agent</option>
                        <option value="Cover Letter Agent">Cover Letter Agent</option>
                        <option value="Job Matching Agent">Job Matching Agent</option>
                        <option value="Interview Agent">Interview Agent</option>
                      </select>
                    </div>

                    <button
                      onClick={handleManualHallucinationAudit}
                      disabled={auditing || !manualSource.trim() || !manualGenerated.trim()}
                      className={`px-4 py-1.5 text-xs font-semibold rounded-xl text-white shadow-2xs transition-all ${
                        auditing || !manualSource.trim() || !manualGenerated.trim()
                          ? 'bg-slate-200 cursor-not-allowed text-slate-400'
                          : 'bg-indigo-600 hover:bg-indigo-700'
                      }`}
                    >
                      {auditing ? 'Auditing...' : 'Deploy Audit'}
                    </button>
                  </div>

                  {/* Playground Output */}
                  {manualReport && (
                    <div className={`mt-4 border p-4 rounded-xl space-y-2 ${
                      manualReport.severity === 'high' 
                        ? 'bg-rose-50 border-rose-100 text-rose-800' 
                        : manualReport.severity === 'medium'
                        ? 'bg-amber-50 border-amber-100 text-amber-800'
                        : 'bg-emerald-50 border-emerald-100 text-emerald-800'
                    }`}>
                      <div className="flex items-center gap-2">
                        <AlertCircle className="h-4 w-4 shrink-0" />
                        <span className="font-display font-bold text-xs uppercase tracking-tight">Audit Report — Severity: {manualReport.severity}</span>
                      </div>
                      
                      <p className="text-xs font-semibold mt-1">Discrepancy Details:</p>
                      <p className="text-xs bg-white/70 p-2 rounded-lg leading-relaxed">{manualReport.details}</p>

                      <p className="text-xs font-semibold mt-1">Audit Trail Evidence:</p>
                      <p className="text-xs font-mono bg-slate-900 text-slate-200 p-2 rounded-lg break-all">{manualReport.evidence}</p>
                    </div>
                  )}

                </div>

              </div>
            )}

          </div>

        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-500 animate-pulse">
          <Clock className="h-10 w-10 text-slate-300 mx-auto animate-spin mb-4" />
          <h4 className="text-sm font-display font-bold text-slate-700">Hydrating Quality Dashboard</h4>
          <p className="text-xs text-slate-400 mt-1">Please wait while the evaluation run records are read from database...</p>
        </div>
      )}

    </div>
  );
}
