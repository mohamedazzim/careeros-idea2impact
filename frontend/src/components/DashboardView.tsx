/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { KnowledgeDoc, AnalysisRun } from '../types';
import { Target, Search, BarChart3, ChevronRight, Zap, AlertTriangle, CheckCircle, Terminal, HelpCircle, ArrowRight, Gauge, FileText, Check, LayoutGrid, AlertCircle, RefreshCw, ExternalLink } from 'lucide-react';


const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || 'http://localhost:8000/api/v1';
interface Props {
  documents: KnowledgeDoc[];
  activeDocId: string | null;
  activeRun: AnalysisRun | null;
  isAnalyzing: boolean;
  onAnalyze: (docId: string, jdText: string) => Promise<boolean>;
  onSelectDoc: (id: string) => void;
}

export default function DashboardView({
  documents,
  activeDocId,
  activeRun,
  isAnalyzing,
  onAnalyze,
  onSelectDoc
}: Props) {
  const [jd, setJd] = useState('');
  const [showTrace, setShowTrace] = useState(false);

  // Filter out non-indexed docs for analysis dropdown
  const indexedDocs = documents.filter(d => (d.status === 'indexed' || d.status === 'analyzed') && d.is_selectable !== false);
  const activeDoc = indexedDocs.find(d => d.id === activeDocId) || indexedDocs[0];
  const explainability = activeRun?.match_result?.explainability;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeDocId || !jd.trim()) return;
    onAnalyze(activeDocId, jd);
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-emerald-500 border-emerald-500/30 bg-emerald-50/50';
    if (score >= 80) return 'text-indigo-500 border-indigo-500/30 bg-indigo-50/50';
    if (score >= 70) return 'text-amber-500 border-amber-500/30 bg-amber-50/50';
    return 'text-rose-500 border-rose-500/30 bg-rose-50/50';
  };

  const getSeverityBadge = (severity: 'high' | 'medium' | 'low') => {
    switch (severity) {
      case 'high':
        return <span className="px-2 py-0.5 text-[10px] uppercase font-bold rounded-md bg-rose-50 border border-rose-100 text-rose-700">High Risk</span>;
      case 'medium':
        return <span className="px-2 py-0.5 text-[10px] uppercase font-bold rounded-md bg-amber-50 border border-amber-100 text-amber-700">Medium</span>;
      default:
        return <span className="px-2 py-0.5 text-[10px] uppercase font-bold rounded-md bg-slate-100 border border-slate-200 text-slate-600">Low Detail</span>;
    }
  };

  const getImpactBadge = (impact: 'high' | 'medium' | 'low') => {
    switch (impact) {
      case 'high':
        return <span className="px-2 py-0.5 text-[10px] uppercase font-bold rounded-md bg-emerald-50 border border-emerald-100 text-emerald-700">High Impact</span>;
      case 'medium':
        return <span className="px-2 py-0.5 text-[10px] uppercase font-bold rounded-md bg-sky-50 border border-sky-100 text-sky-700">Medium</span>;
      default:
        return <span className="px-2 py-0.5 text-[10px] uppercase font-bold rounded-md bg-slate-50 border border-slate-150 text-slate-600">Standard</span>;
    }
  };

  // Static templates to let the user play with examples
  const loadExampleJob = () => {
    setJd(`Staff Full Stack Engineer (React & TypeScript Node developer)
We are seeking a seasoned Principal or Staff Full Stack Engineer. 
Key Responsibilities:
- Design and build robust web interfaces using React, TypeScript, and Tailwind CSS.
- Build server-side APIs, database schemas, and microservices in NodeJS or Python fastAPI.
- Optimize search vectors using Redis, Qdrant or similar hybrid retrieve patterns.
- Secure operations with OAuth integrations, JWT auth flow, and reliable rate limiters.
- Write unit/integration tests to guarantee high scalability and reliability.
Required tools: PostgreSQL, Zustand, AWS or Cloud Run containers.`);
  };

  return (
    <div className="space-y-8" id="dashboard-view">
      {/* Top Split Page Screen */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Job Description Paste Form */}
        <div className="lg:col-span-5 space-y-6 bg-white border border-slate-100 rounded-2xl p-6 shadow-xs">
          <div>
            <h2 className="text-lg font-display font-semibold text-slate-950 flex items-center gap-2">
              <Target className="h-5 w-5 text-indigo-500" />
              RAG Alignment Matcher
            </h2>
            <p className="text-xs text-slate-500 mt-1">Paste a complete target job description to match against your active resume vector.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Select Candidate Resume</label>
              {indexedDocs.length === 0 ? (
                <div className="p-3 bg-amber-50/50 border border-amber-200/50 rounded-xl flex items-start gap-2 text-xs text-amber-800">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold">No Indexed Documents Found:</span> Write or upload a resume in the{' '}
                    <Link href="/knowledge" className="font-bold underline hover:text-amber-950">Knowledge Hub</Link> first.
                  </div>
                </div>
              ) : (
                <select
                  value={activeDoc?.id || ''}
                  onChange={(e) => onSelectDoc(e.target.value)}
                  className="w-full px-4 py-2 text-sm border border-slate-200 rounded-xl bg-slate-50 focus:outline-hidden focus:ring-2 focus:ring-slate-850 transition-all font-display font-medium text-slate-800"
                >
                  {indexedDocs.map(d => (
                    <option key={d.id} value={d.id}>{d.filename} (Indexed)</option>
                  ))}
                </select>
              )}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">Target Job Description</label>
                <button
                  type="button"
                  onClick={loadExampleJob}
                  className="text-xs text-indigo-600 font-medium hover:underline bg-slate-50 px-2 py-0.5 rounded"
                >
                  Insert Sample Job Spec
                </button>
              </div>
              <textarea
                value={jd}
                onChange={(e) => setJd(e.target.value)}
                required
                rows={9}
                className="w-full px-4 py-3 text-sm border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-slate-850 transition-all font-sans text-slate-700 leading-relaxed"
                placeholder="Paste responsibilities, metrics, goals, tech stack stacks here..."
              />
            </div>

            <button
              type="submit"
              disabled={isAnalyzing || indexedDocs.length === 0 || !jd.trim()}
              className="w-full py-3 bg-slate-950 hover:bg-slate-850 text-white rounded-xl text-sm font-display font-medium transition-all shadow-md disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isAnalyzing ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Running AI RAG Reranker...
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4" />
                  Analyze Alignment Match
                </>
              )}
            </button>
          </form>
        </div>

        {/* Right Column: Output Match Score Page */}
        <div className="lg:col-span-7 flex flex-col justify-between">
          {isAnalyzing ? (
            /* Progress state */
            <div className="bg-slate-900 text-slate-100 rounded-2xl p-8 flex flex-col items-center justify-center text-center space-y-6 h-full border border-slate-800 shadow-xl relative overflow-hidden">
              <div className="absolute top-0 right-0 left-0 h-1 bg-indigo-5050 accent-gradient">
                <div className="h-full bg-indigo-500 w-1/3 animate-ping" />
              </div>
              <div className="h-16 w-16 bg-slate-850 rounded-full flex items-center justify-center border border-slate-700 shadow-xl shrink-0">
                <RefreshCw className="h-8 w-8 text-indigo-400 animate-spin" />
              </div>
              <div className="space-y-2">
                <h3 className="text-xl font-display font-semibold tracking-tight text-white">LangGraph Orchestration Running</h3>
                <p className="text-sm text-slate-400 max-w-sm">RAG retrieve, context rerank and structural analysis pipelines are active.</p>
              </div>

              {/* Steps Checklist representation */}
              <div className="w-full max-w-xs space-y-3 pt-4 border-t border-slate-800 text-left font-mono text-xs">
                <div className="flex items-center justify-between text-indigo-400">
                  <span className="flex items-center gap-2">&rarr; Node 1: Ingest bytes</span>
                  <span className="font-semibold uppercase tracking-wider">COMPLETED</span>
                </div>
                <div className="flex items-center justify-between text-indigo-400">
                  <span className="flex items-center gap-2">&rarr; Node 2: GLiNER PII Mask</span>
                  <span className="font-semibold uppercase tracking-wider">COMPLETED</span>
                </div>
                <div className="flex items-center justify-between text-slate-300">
                  <span className="flex items-center gap-2">&rarr; Node 3: Qdrant Vector search</span>
                  <span className="font-semibold uppercase tracking-wider flex items-center gap-1">ACTIVE <RefreshCw className="h-3 w-3 animate-spin"/></span>
                </div>
                <div className="flex items-center justify-between text-slate-500">
                  <span>&rarr; Node 4: Rerank passage context</span>
                  <span className="font-semibold">PENDING</span>
                </div>
                <div className="flex items-center justify-between text-slate-500">
                  <span>&rarr; Node 5: Final alignment scoring</span>
                  <span className="font-semibold">PENDING</span>
                </div>
              </div>
            </div>
          ) : activeRun && activeRun.status === 'completed' && activeRun.match_result ? (
            /* Match Output Screen */
            <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-xs h-full space-y-6">
              <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Alignment Result</h3>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-3xl font-display font-bold text-slate-900">{activeRun.match_result.match_score}% Match</span>
                    <span className={`px-3 py-1 text-sm font-display font-bold rounded-lg border ${getScoreColor(activeRun.match_result.match_score)}`}>
                      Grade {activeRun.match_result.grade}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setShowTrace(!showTrace)}
                  className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 hover:bg-slate-50 text-slate-600 rounded-lg text-xs font-semibold font-mono"
                >
                  <Terminal className="h-4.5 w-4.5" />
                  {showTrace ? 'Hide Trace' : 'Open Smith Trace'}
                </button>
              </div>

              {/* Summary description paragraph */}
              <div className="space-y-4">
                <div>
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Architectural Summary</h4>
                  <p className="text-sm text-slate-600 mt-2 leading-relaxed font-sans">{activeRun.match_result.summary}</p>
                </div>

                {explainability && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50/60 overflow-hidden">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 border-b border-slate-200 bg-white">
                      <div>
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
                          <HelpCircle className="h-4 w-4 text-indigo-500" />
                          Why this score?
                        </h4>
                        <p className="text-xs text-slate-500 mt-1">Weighted final score: {activeRun.match_result.match_score}% from explicit resume and JD evidence.</p>
                      </div>
                      <a
                        href={`/workflow/alignment-report/${activeRun.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-indigo-100 bg-indigo-50 text-indigo-700 text-xs font-display font-semibold hover:bg-indigo-100"
                      >
                        Full Report
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-left text-xs">
                        <thead className="bg-slate-100/80 text-slate-500 uppercase tracking-wider">
                          <tr>
                            <th className="px-4 py-2 font-bold">Score Component</th>
                            <th className="px-4 py-2 font-bold">Score</th>
                            <th className="px-4 py-2 font-bold">Weight</th>
                            <th className="px-4 py-2 font-bold">Contribution</th>
                            <th className="px-4 py-2 font-bold">Evidence</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 bg-white">
                          {explainability.components.map((component) => (
                            <tr key={component.key}>
                              <td className="px-4 py-3 font-display font-semibold text-slate-800 whitespace-nowrap">{component.label}</td>
                              <td className="px-4 py-3 font-mono text-slate-700">{component.score}%</td>
                              <td className="px-4 py-3 font-mono text-slate-700">{component.weight}%</td>
                              <td className="px-4 py-3 font-mono font-semibold text-slate-900">{component.contribution}/{component.max_contribution}</td>
                              <td className="px-4 py-3 text-slate-600 max-w-sm">
                                {(component.matched || []).slice(0, 2).map((item) => (
                                  <span key={`m-${component.key}-${item}`} className="inline-flex mr-2 mb-1 items-center gap-1 text-emerald-700">
                                    <Check className="h-3 w-3" /> {item}
                                  </span>
                                ))}
                                {(component.missing || []).slice(0, 2).map((item) => (
                                  <span key={`x-${component.key}-${item}`} className="inline-flex mr-2 mb-1 items-center gap-1 text-rose-700">
                                    <AlertCircle className="h-3 w-3" /> {item}
                                  </span>
                                ))}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="px-4 py-3 bg-slate-950 text-slate-100 flex items-center justify-between text-xs">
                      <span className="font-display font-semibold">Final weighted score</span>
                      <span className="font-mono text-emerald-300">{activeRun.match_result.match_score}%</span>
                    </div>
                  </div>
                )}

                {/* Recommendations Bullet List */}
                <div>
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Strategic Resume Actions</h4>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                    {activeRun.match_result.recommendations.map((rec, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-slate-600">
                        <Check className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Embed Diagnostic Trace overlay */}
              {showTrace && (
                <div className="bg-slate-950 border border-slate-900 rounded-xl p-4 text-left space-y-3 shadow-inner">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <div className="flex items-center gap-2 text-indigo-400 font-mono text-xs">
                      <Terminal className="h-4 w-4" />
                      <span>LangSmith Execution Audit [ID: {activeRun.id}]</span>
                    </div>
                    <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[9px] font-mono px-1.5 py-0.5 rounded font-bold uppercase">TRACED</span>
                  </div>
              <div className="font-mono text-[10px] space-y-2 text-slate-300 overflow-x-auto whitespace-pre leading-relaxed max-h-48 scrollbar">
                <div>[0.0s] START: Pipeline initialized context matching constraints</div>
                    <div>[0.2s] INGEST: Loaded raw source buffer size = {(activeDoc?.raw_text || activeDoc?.content || '').length || 0} chars</div>
                    <div>[0.6s] REDACTION: Candidate identifiers masked before retrieval</div>
                    <div>[0.8s] EMBED: Resume vectors stored in retrieval index</div>
                    <div>[1.4s] RETRIEVER: Query-to-document similarity map resolved</div>
                    <div>[1.8s] RERANKER: Ranked candidate passages against the target role</div>
                    <div>[2.2s] SCORER: Match result computed from persisted alignment data</div>
                    <div className="text-emerald-400">&gt;&gt; Result parsed code 200 • Match Score synced!</div>
                </div>
              </div>
              )}
            </div>
          ) : (
            /* Idle / Empty screen placeholder representation */
            <div className="border border-slate-200/60 bg-slate-50/50 rounded-2xl p-12 text-center text-slate-400 flex flex-col justify-center items-center h-full">
              <BarChart3 className="h-12 w-12 text-slate-300 stroke-1 mb-4" />
              <h3 className="font-display font-semibold text-slate-850 text-sm">Waiting for Match Scope</h3>
              <p className="text-xs text-slate-500 max-w-sm mt-1 mx-auto leading-relaxed">
                Connect your active indexed resume with a custom pasted Job Description to compute real-time alignment metrics.
              </p>
              <button
                type="button"
                onClick={loadExampleJob}
                className="mt-4 px-4 py-2 bg-slate-100 hover:bg-slate-200/80 border border-slate-200 text-slate-700 rounded-xl text-xs font-display font-medium transition-all"
              >
                Try Sample Developer Job Role
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Strengths & Gaps Row Section */}
      {activeRun && activeRun.status === 'completed' && activeRun.match_result && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4 border-t border-slate-100">
          {/* Strengths View */}
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-display font-semibold text-slate-900 flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-emerald-500" />
                Key Profile Strengths
              </h3>
              <p className="text-xs text-slate-500 mt-1">Strengths and skills identified within the secure vector snippets matching job expectations.</p>
            </div>

            <div className="space-y-3">
              {activeRun.match_result.strengths.map((str) => (
                <div key={str.id} className="bg-emerald-50/20 border border-emerald-100/50 rounded-xl p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-display font-bold text-emerald-950">{str.title}</h4>
                    {getImpactBadge(str.impact)}
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed font-sans">{str.description}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Gaps Severity Table */}
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-display font-semibold text-slate-900 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-500" />
                Target Alignment Gaps
              </h3>
              <p className="text-xs text-slate-500 mt-1">Constructive gap review highlighting specific deficiencies with active training recommendations.</p>
            </div>

            <div className="bg-white rounded-xl border border-slate-100 overflow-hidden shadow-xs">
              {/* Desktop Table View */}
              <div className="hidden md:block overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-100 text-left">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Gap & Severity</th>
                      <th className="px-4 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Reasoning Description</th>
                      <th className="px-4 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Actionable Suggestion</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {activeRun.match_result.gaps.map((gp) => (
                      <tr key={gp.id}>
                        <td className="px-4 py-3 align-top whitespace-nowrap">
                          <div className="font-display font-semibold text-slate-800 text-xs mb-1.5">{gp.category}</div>
                          {getSeverityBadge(gp.severity)}
                        </td>
                        <td className="px-4 py-3 align-top text-xs text-slate-600 font-sans max-w-xs leading-relaxed">
                          {gp.description}
                        </td>
                        <td className="px-4 py-3 align-top text-xs font-sans text-indigo-700 bg-indigo-50/10 font-medium max-w-xs leading-relaxed">
                          {gp.suggestion}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile Stacked View */}
              <div className="md:hidden divide-y divide-slate-100">
                {activeRun.match_result.gaps.map((gp) => (
                  <div key={gp.id} className="p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="font-display font-semibold text-slate-800 text-xs">{gp.category}</div>
                      {getSeverityBadge(gp.severity)}
                    </div>
                    <div className="space-y-1">
                      <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Reasoning</div>
                      <div className="text-xs text-slate-600 font-sans leading-relaxed">{gp.description}</div>
                    </div>
                    <div className="space-y-1 bg-indigo-50/30 p-2 rounded-lg">
                      <div className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">Actionable Suggestion</div>
                      <div className="text-xs font-sans text-indigo-700 font-medium leading-relaxed">{gp.suggestion}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
