/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import {
  Job,
  JobSkill,
  JobSource,
  JobIngestionRun,
  JobMatch,
  Strength,
  Gap,
  KnowledgeDoc,
  JobRefreshDiagnostics,
  JobSortOption,
} from '../types';
import { formatDateOnly, formatDateTimeLocal, formatTimeLocal } from '@/lib/datetime';
import LearningPathsPanel from './learning/LearningPathsPanel';
import EvidenceBackedSkillGapPanel from './learning/EvidenceBackedSkillGapPanel';
import GapActionsPanel from './learning/GapActionsPanel';
import GitHubProjectsPanel from './learning/GitHubProjectsPanel';
import { 
  Building2, 
  MapPin, 
  Sparkles, 
  Search, 
  Maximize2, 
  RefreshCw, 
  Layers, 
  Briefcase, 
  ExternalLink, 
  CheckCircle, 
  XCircle, 
  Network, 
  ArrowRight, 
  BarChart3, 
  Gauge, 
  Clock, 
  Code 
} from 'lucide-react';

function flattenSkillValues(...values: unknown[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];

  const visit = (item: unknown) => {
    if (item == null) {
      return;
    }
    if (Array.isArray(item)) {
      item.forEach(visit);
      return;
    }
    if (typeof item === 'string') {
      const normalized = item.trim();
      if (normalized && !seen.has(normalized)) {
        seen.add(normalized);
        result.push(normalized);
      }
      return;
    }
    if (typeof item === 'object') {
      const record = item as Record<string, unknown>;
      const candidate =
        record.skill ??
        record.name ??
        record.slug ??
        record.title ??
        record.category ??
        record.label ??
        record.id;
      if (candidate !== undefined && candidate !== null) {
        visit(candidate);
      }
    }
  };

  values.forEach(visit);
  return result;
}

function normalizeRefreshDiagnostics(payload: any, fallbackStatus: string = 'queued'): JobRefreshDiagnostics | null {
  if (!payload) {
    return null;
  }
  const diagnostics = payload.diagnostics || {};
  const summary = payload.refresh_summary || diagnostics.summary || {
    found: 0,
    added: 0,
    updated: 0,
    duplicates_removed: 0,
    expired_removed: 0,
    errors: 0,
    embedded: 0,
  };
  const providerResults = payload.provider_results || diagnostics.provider_results || [];
  const visibilityReason = payload.visibility_reason || diagnostics.visibility_reason || null;
  const reasonCode = diagnostics.reason_code || visibilityReason?.code || payload.reason_code || fallbackStatus || 'unknown';
  const reason = diagnostics.reason || visibilityReason?.message || payload.reason || payload.message || 'Refresh diagnostics are not available yet.';
  const totals = payload.totals || diagnostics.totals || {
    fetched: summary.found,
    new_unique: summary.added,
    updated_existing: summary.updated,
    duplicate_results: summary.duplicates_removed,
    visible_new_jobs: summary.added,
  };
  const dedupe = payload.dedupe || diagnostics.dedupe || {
    strategy: 'provider_external_id_then_canonical_fingerprint',
    new_insert_count: summary.added,
    existing_match_count: summary.updated,
    duplicate_result_count: summary.duplicates_removed,
    possible_over_dedupe_count: 0,
  };
  const visibility = payload.visibility || diagnostics.visibility || {
    visible_list_changed: summary.added > 0,
    reason_if_unchanged: summary.added > 0 ? null : reasonCode,
    message: reason,
  };
  const sampleUpdatedJobs = payload.sample_updated_jobs || diagnostics.sample_updated_jobs || [];
  const providerQueryContexts = payload.provider_query_contexts || diagnostics.provider_query_contexts || [];
  return {
    status: diagnostics.status || payload.status || fallbackStatus,
    reason_code: reasonCode,
    reason,
    summary,
    provider_results: providerResults,
    visibility_reason: visibilityReason || undefined,
    totals,
    dedupe,
    visibility,
    sample_updated_jobs: sampleUpdatedJobs,
    provider_query_contexts: providerQueryContexts,
  };
}

function getRefreshStatusTone(status?: string | null): string {
  const normalized = (status || '').toLowerCase();
  if (normalized === 'completed' || normalized === 'tracked') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (normalized === 'running' || normalized === 'queued') return 'bg-amber-50 text-amber-700 border-amber-200';
  if (normalized === 'blocked' || normalized === 'failed' || normalized === 'error') return 'bg-rose-50 text-rose-700 border-rose-200';
  if (normalized === 'skipped' || normalized === 'not_tracked') return 'bg-slate-50 text-slate-500 border-slate-200';
  return 'bg-indigo-50 text-indigo-700 border-indigo-200';
}

function getRefreshOutcomeSummary(refreshDiagnostics: JobRefreshDiagnostics) {
  const totals = refreshDiagnostics.totals || {
    fetched: refreshDiagnostics.summary.found,
    new_unique: refreshDiagnostics.summary.added,
    updated_existing: refreshDiagnostics.summary.updated,
    duplicate_results: refreshDiagnostics.summary.duplicates_removed,
    visible_new_jobs: refreshDiagnostics.summary.added,
  };
  const visibility = refreshDiagnostics.visibility || {
    visible_list_changed: refreshDiagnostics.summary.added > 0,
    reason_if_unchanged: refreshDiagnostics.summary.added > 0 ? null : refreshDiagnostics.reason_code,
    message: refreshDiagnostics.reason,
  };
  const reasonCode = (visibility.reason_if_unchanged || refreshDiagnostics.reason_code || '').toLowerCase();
  const providerNames = (refreshDiagnostics.provider_results || [])
    .filter((provider) => (provider.added ?? 0) === 0 && (provider.found ?? 0) > 0)
    .map((provider) => provider.display_name || provider.provider)
    .filter(Boolean);
  const firstProviderName = providerNames[0] || 'the providers';

  if (totals.new_unique > 0) {
    return {
      title: 'New jobs were added',
      detail: `CareerOS added ${totals.new_unique} new job card${totals.new_unique === 1 ? '' : 's'} and refreshed ${totals.updated_existing} existing record${totals.updated_existing === 1 ? '' : 's'}.`,
      chips: [
        `Fetched ${totals.fetched}`,
        `New ${totals.new_unique}`,
        `Updated ${totals.updated_existing}`,
        `Duplicates ${totals.duplicate_results}`,
      ],
      actionText: 'The ranked feed should grow if providers keep returning fresh postings.',
    };
  }

  if (reasonCode.includes('billing')) {
    return {
      title: 'No new jobs were added because a provider was billing-blocked',
      detail: visibility.message || refreshDiagnostics.reason || 'One provider was blocked by billing, so its new jobs were not available for the run.',
      chips: [
        `Fetched ${totals.fetched}`,
        `Updated ${totals.updated_existing}`,
        `Duplicates ${totals.duplicate_results}`,
      ],
      actionText: 'Fix provider billing or switch to a source that is currently enabled.',
    };
  }

  if (reasonCode === 'providers_returned_only_existing_jobs') {
    return {
      title: 'No new jobs were added because providers returned jobs already in CareerOS',
      detail: visibility.message || `${firstProviderName} returned jobs that matched records already stored in CareerOS.`,
      chips: [
        `Fetched ${totals.fetched}`,
        `Updated ${totals.updated_existing}`,
        `Duplicates ${totals.duplicate_results}`,
      ],
      actionText: 'Broaden the query, wait for fresher provider inventory, or review unscored jobs.',
    };
  }

  if (reasonCode === 'duplicate_only') {
    return {
      title: 'No new jobs were added because the refresh returned duplicates',
      detail: visibility.message || 'The provider results matched jobs already stored in CareerOS.',
      chips: [
        `Fetched ${totals.fetched}`,
        `Duplicates ${totals.duplicate_results}`,
        `Updated ${totals.updated_existing}`,
      ],
      actionText: 'This usually means the same inventory was fetched again.',
    };
  }

  if (reasonCode === 'all_results_expired') {
    return {
      title: 'No new jobs were added because the results were stale or expired',
      detail: visibility.message || 'The refresh found jobs, but they were already stale or expired.',
      chips: [
        `Fetched ${totals.fetched}`,
        `Expired ${refreshDiagnostics.summary.expired_removed}`,
        `Updated ${totals.updated_existing}`,
      ],
      actionText: 'Try again later or widen the provider filters to surface newer postings.',
    };
  }

  if (totals.fetched > 0 && totals.new_unique === 0 && totals.updated_existing > 0) {
    return {
      title: 'No new jobs were added because the run only refreshed existing records',
      detail: visibility.message || `Providers returned ${totals.fetched} jobs, but they matched existing records already in CareerOS.`,
      chips: [
        `Fetched ${totals.fetched}`,
        `Updated ${totals.updated_existing}`,
        `Duplicates ${totals.duplicate_results}`,
      ],
      actionText: 'This is healthy if the providers are re-serving the same inventory.',
    };
  }

  return {
    title: 'No new jobs were added',
    detail: visibility.message || refreshDiagnostics.reason || 'The refresh completed, but no new or updated jobs were available for the feed.',
    chips: [
      `Fetched ${totals.fetched}`,
      `Updated ${totals.updated_existing}`,
      `Duplicates ${totals.duplicate_results}`,
    ],
    actionText: 'Use the provider notes below to see whether the run was blocked, stale, or duplicate-heavy.',
  };
}

interface JobsIntelligenceViewProps {
  token: string | null;
  activeDocId: string | null;
  documents: KnowledgeDoc[];
  onRefreshDocs: () => void;
  onGeneratePackage?: (jobId: string | number) => void;
  isGenerating?: boolean;
  onSelectDoc?: (docId: string) => void;
}

export default function JobsIntelligenceView({ token, activeDocId, documents, onRefreshDocs, onGeneratePackage, isGenerating, onSelectDoc }: JobsIntelligenceViewProps) {
  const [jobs, setJobs] = useState<any[]>([]);
  const [stats, setStats] = useState<any>({
    total_jobs: 0,
    raw_total_jobs: 0,
    india_eligible_jobs: 0,
    excluded_non_india: 0,
    filtered_out_jobs: 0,
    non_india_filtered_jobs: 0,
    non_tech_filtered_jobs: 0,
    stale_or_closed_jobs: 0,
    total_matches: 0,
    active_sources: 0,
  });
  const [alignmentSummary, setAlignmentSummary] = useState<any>(null);
  const [providerCatalog, setProviderCatalog] = useState<any[]>([]);
  const [syncLogs, setSyncLogs] = useState<JobIngestionRun[]>([]);
  const [refreshDiagnostics, setRefreshDiagnostics] = useState<JobRefreshDiagnostics | null>(null);
  const [stageHistory, setStageHistory] = useState<{ node: string; label: string; at: string }[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedJob, setSelectedJob] = useState<any | null>(null);
  const [selectedPhase2, setSelectedPhase2] = useState<any | null>(null);
  const [rc3Intel, setRc3Intel] = useState<any | null>(null);

  // Search and Filter State
  const [searchQuery, setSearchQuery] = useState('');
  const [minScore, setMinScore] = useState<number>(0);
  const [selectedSource, setSelectedSource] = useState<string>('');
  const [selectedPlace, setSelectedPlace] = useState<string>('');
  const [sortBy, setSortBy] = useState<JobSortOption>('best_match');

  // LangGraph Live Node Status Visualization
  const [syncStatus, setSyncStatus] = useState<'idle' | 'fetching' | 'normalizing' | 'deduping' | 'enriching' | 'matching' | 'ranking' | 'completed'>('idle');
  const [currentStepDetail, setCurrentStepDetail] = useState('');

  const mapBackendNodeToSyncStatus = useCallback((node?: string | null, fallback?: string | null) => {
    const normalized = (node || '').toLowerCase();
    if (normalized === 'fetch_jobs') return 'fetching';
    if (normalized === 'normalize') return 'normalizing';
    if (normalized === 'deduplicate') return 'deduping';
    if (normalized === 'enrich') return 'enriching';
    if (normalized === 'get_profile' || normalized === 'match_jobs') return 'matching';
    if (normalized === 'rank_jobs') return 'ranking';
    if (normalized === 'completed') return 'completed';
    if (fallback === 'completed') return 'completed';
    if (fallback === 'failed') return 'idle';
    return 'fetching';
  }, []);

  const describeBackendNode = useCallback((node?: string | null) => {
    switch ((node || '').toLowerCase()) {
      case 'fetch_jobs':
        return 'fetch_jobs: fetching fresh direct postings from real provider APIs...';
      case 'normalize':
        return 'normalize: shaping raw provider results into CareerOS job records...';
      case 'deduplicate':
        return 'deduplicate: removing repeated postings and duplicate source IDs...';
      case 'enrich':
        return 'enrich: classifying location, tech role, and experience fit...';
      case 'get_profile':
        return 'get_profile: loading the active resume and candidate profile...';
      case 'match_jobs':
        return 'match_jobs: scoring jobs against the active resume...';
      case 'rank_jobs':
        return 'rank_jobs: ranking scored jobs and preparing top opportunities...';
      case 'completed':
        return 'completed: pipeline finished and results are ready.';
      default:
        return 'processing: waiting for the next pipeline update...';
    }
  }, []);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  }), [token]);
  const selectableDocuments = useMemo(
    () => documents.filter((doc) => (doc.status === 'indexed' || doc.status === 'analyzed') && doc.is_selectable !== false),
    [documents]
  );
  const activeResume = useMemo(
    () => selectableDocuments.find((doc) => doc.id === activeDocId) || selectableDocuments[0] || null,
    [selectableDocuments, activeDocId]
  );
  const effectiveResumeId = activeDocId || activeResume?.id || null;

  const fetchJobsAndStats = useCallback(async () => {
    setIsLoading(true);
    try {
      // Build filter queries
      const queryParams = new URLSearchParams();
      queryParams.append('limit', '200');
      queryParams.append('include_unmatched', 'true');
      queryParams.append('sort', sortBy);
      if (minScore > 0) queryParams.append('score', minScore.toString());
      if (selectedSource) queryParams.append('source', selectedSource);
      if (effectiveResumeId) queryParams.append('resume_id', effectiveResumeId);

      const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
      let jobsPayload: any = null;
      const [jobsRes, statsRes] = await Promise.all([
        fetch(`${baseUrl}/jobs?${queryParams.toString()}`, { headers }),
        fetch(`${baseUrl}/jobs/stats?${queryParams.toString()}`, { headers })
      ]);

      if (jobsRes.ok) {
        jobsPayload = await jobsRes.json();
        setJobs(jobsPayload.jobs || []);
        setAlignmentSummary(jobsPayload.alignment_summary || null);
        setProviderCatalog(jobsPayload.provider_catalog || []);
      }
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        const normalizedStats = statsData.stats || {
          total_jobs: statsData.total_jobs ?? statsData.active_jobs ?? 0,
          raw_total_jobs: statsData.raw_total_jobs ?? statsData.total_jobs ?? statsData.active_jobs ?? 0,
          india_eligible_jobs: statsData.india_eligible_jobs ?? statsData.total_jobs ?? 0,
          excluded_non_india: statsData.excluded_non_india ?? 0,
          filtered_out_jobs: statsData.filtered_out_jobs ?? 0,
          non_india_filtered_jobs: statsData.non_india_filtered_jobs ?? 0,
          non_tech_filtered_jobs: statsData.non_tech_filtered_jobs ?? 0,
          stale_or_closed_jobs: statsData.stale_or_closed_jobs ?? 0,
          total_matches: statsData.total_matches ?? jobsPayload?.matched_count ?? jobsPayload?.jobs?.length ?? 0,
          active_sources: statsData.active_sources ?? Object.keys(statsData.by_source || {}).length,
          avg_match_score: statsData.avg_match_score ?? 0,
          by_source: statsData.by_source || {},
          india_by_source: statsData.india_by_source || {},
          last_ingested: statsData.last_ingested ?? null,
          last_sync_runs: statsData.last_sync_runs || [],
        };
        setStats(normalizedStats);
        setAlignmentSummary((prev: any) => statsData.alignment_summary || prev);
        setProviderCatalog((prev) => statsData.provider_catalog || prev);
        const latestTheirstack = statsData.provider_health?.theirstack;
        if (latestTheirstack?.latest_provider_results || latestTheirstack?.latest_refresh_reason || latestTheirstack?.latest_refresh_summary) {
          const latestDiagnostics = normalizeRefreshDiagnostics({
            status: latestTheirstack?.status || 'completed',
            reason_code: latestTheirstack?.latest_refresh_reason?.code,
            reason: latestTheirstack?.latest_refresh_reason?.message,
            refresh_summary: latestTheirstack?.latest_refresh_summary || {},
            provider_results: latestTheirstack?.latest_provider_results || [],
            visibility_reason: latestTheirstack?.latest_refresh_reason || null,
          }, 'completed');
          if (latestDiagnostics) {
            setRefreshDiagnostics(latestDiagnostics);
          }
        }
        if (normalizedStats.last_sync_runs) {
          setSyncLogs(normalizedStats.last_sync_runs);
        }
      }
      const rc3Res = await fetch(`${baseUrl}/opportunities/rc3/intelligence`, { headers });
      if (rc3Res.ok) {
        setRc3Intel(await rc3Res.json());
      }
    } catch (err) {
      console.error('Failed to load CareerOS Jobs feed', err);
    } finally {
      setIsLoading(false);
    }
  }, [minScore, selectedSource, effectiveResumeId, headers, sortBy]);

  useEffect(() => {
    fetchJobsAndStats();
  }, [fetchJobsAndStats]);

  // Handle detailed job fetch
  const selectJob = async (id: string) => {
    try {
      const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
      const detailParams = new URLSearchParams();
      if (effectiveResumeId) detailParams.append('resume_id', effectiveResumeId);
      const res = await fetch(`${baseUrl}/jobs/${id}?${detailParams.toString()}`, { headers });
      if (res.ok) {
        const fullJob = await res.json();
        setSelectedJob(fullJob);
        setSelectedPhase2(null);
      }
    } catch (e) {
      console.error('Error fetching job details', e);
    }
  };

  // Trigger background job matching pipeline
  const handleSyncScrape = async () => {
    setSyncStatus('fetching');
    setCurrentStepDetail('fetch_jobs: Fetching fresh direct postings from real provider APIs...');

    try {
      const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
      const res = await fetch(`${baseUrl}/jobs/refresh`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ resume_id: effectiveResumeId }),
      });
      const body = await res.json().catch(() => null);
      const startDiagnostics = normalizeRefreshDiagnostics(body, body?.status || 'queued');
      if (startDiagnostics) {
        setRefreshDiagnostics(startDiagnostics);
      }

      if (!res.ok || !body?.session_id) {
        const msg = body?.message || body?.detail || `HTTP ${res.status}`;
        setSyncStatus('idle');
        setCurrentStepDetail(`Pipeline start failed: ${msg}`);
        return;
      }

      if (body.status === 'setup_required') {
        setSyncStatus('idle');
        setCurrentStepDetail('Upload or select an analyzed resume before matching jobs.');
        return;
      }

      const sessionId = body.session_id;
      setSyncStatus('fetching');
      setCurrentStepDetail('refresh queued: the background worker is starting the job pipeline...');
      setStageHistory([]);

      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${baseUrl}/jobs/refresh/${sessionId}`, { headers });
          if (!statusRes.ok) {
            clearInterval(pollInterval);
            setSyncStatus('idle');
            setCurrentStepDetail(`Status check failed: HTTP ${statusRes.status}`);
            return;
          }
          const statusBody = await statusRes.json();
          const liveDiagnostics = normalizeRefreshDiagnostics(statusBody, statusBody?.status || 'running');
          if (liveDiagnostics) {
            setRefreshDiagnostics(liveDiagnostics);
          }
          const state = statusBody.status;
          const node = statusBody.current_node || '';
          const mappedStatus = mapBackendNodeToSyncStatus(node, state);
          setSyncStatus(mappedStatus);
          setStageHistory(Array.isArray(statusBody.stage_history) ? statusBody.stage_history : []);
          setCurrentStepDetail(describeBackendNode(node));

          if (state === 'completed') {
            clearInterval(pollInterval);
            setSyncStatus('completed');
            setCurrentStepDetail('All opportunities indexed!');
            fetchJobsAndStats();
            fetch(`${baseUrl}/jobs/phase2/run`, {
              method: 'POST',
              headers,
              body: JSON.stringify({ resume_id: effectiveResumeId, limit: 120 })
            }).catch(() => undefined);
            onRefreshDocs();
            setTimeout(() => setSyncStatus('idle'), 4000);
          } else if (state === 'failed') {
            clearInterval(pollInterval);
            setSyncStatus('idle');
            setCurrentStepDetail(statusBody.error || 'Background matching failed.');
          } else if (state === 'setup_required') {
            clearInterval(pollInterval);
            setSyncStatus('idle');
            setCurrentStepDetail('Upload or select an analyzed resume before matching jobs.');
          } else {
            setCurrentStepDetail(`${describeBackendNode(node)} (${Math.round(statusBody.completion_pct || 0)}%)`);
          }
        } catch {
          // keep polling on transient network errors
        }
      }, 1500);

      // Safety: stop polling after 10 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (syncStatus !== 'idle') {
          setSyncStatus('idle');
          setCurrentStepDetail('Matching pipeline timed out — results may be incomplete.');
        }
      }, 600000);
    } catch (e: any) {
      setSyncStatus('idle');
      setCurrentStepDetail(`Ingestion run failed: ${e?.message || e}`);
    }
  };

  // Compute stats and lists
  const NON_INDIA_LOCATIONS = /united states|united kingdom|germany|canada|london|san francisco|ontario|berlin|new york|seattle|europe|amsterdam|paris|tokyo|singapore|australia/i;

  const isIndiaVisibleJob = (job: any): boolean => {
    if (job.is_india_eligible === false || job.status === "excluded") return false;
    if (job.is_tech_role === false) return false;
    const loc = job.location || '';
    if (NON_INDIA_LOCATIONS.test(loc)) return false;
    return true;
  };

  const filteredJobs = jobs.filter(j => {
    if (!isIndiaVisibleJob(j)) return false;
    const textSearch = `${j.title} ${j.company} ${j.location}`.toLowerCase();
    const matchesSearch = textSearch.includes(searchQuery.toLowerCase());
    const matchesPlace = selectedPlace ? j.location.toLowerCase().includes(selectedPlace.toLowerCase()) : true;
    return matchesSearch && matchesPlace;
  });

  const matchedJobs = filteredJobs.filter(j => j.match?.score_source === "job_match" && j.match?.match_score != null);
  const unscoredJobs = filteredJobs.filter(j => j.match?.score_source !== "job_match" || j.match?.match_score == null);
  const [showUnscored, setShowUnscored] = useState(false);

  const topMatches = [...matchedJobs]
    .sort((a, b) => (b.match?.match_score || 0) - (a.match?.match_score || 0))
    .slice(0, 5);

  const displayJobs = showUnscored ? [...matchedJobs, ...unscoredJobs] : matchedJobs;

  // Quick stats extraction
  const formatPostedDate = useCallback((job: any) => {
    const raw = job?.posted_date || job?.posted_at || null;
    return raw ? formatDateOnly(raw, 'Unknown') : 'Unknown';
  }, []);

  const formatJobClock = useCallback((raw?: string | null) => {
    return formatTimeLocal(raw, 'Unknown');
  }, []);

  const formatTimestamp = useCallback((raw?: string | null) => {
    return formatDateTimeLocal(raw, 'Unknown');
  }, []);

  const formatFetchedTimestamp = useCallback((job: any) => {
    return formatTimestamp(job?.fetched_at);
  }, [formatTimestamp]);

  const formatLastSeenTimestamp = useCallback((job: any) => {
    return formatTimestamp(job?.fetched_at || job?.ingested_at);
  }, [formatTimestamp]);

  const selectedJobMissingSkills = useMemo(() => {
    return flattenSkillValues(
      selectedJob?.match?.missing_skills,
      selectedJob?.match_details?.missing_skills,
    );
  }, [selectedJob]);

  return (
    <div className="space-y-8 animate-fade-in">
      
      {/* Platform Title Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-6 sm:p-8 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-[400px] h-[450px] bg-indigo-505/20 blur-3xl rounded-full" />
        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2">
            <span className="text-[10px] font-mono tracking-widest uppercase bg-indigo-500/30 text-indigo-300 border border-indigo-400/20 px-2.5 py-1 rounded-full font-semibold">
              Pipeline &amp; Matching
            </span>
            <h2 className="text-2xl sm:text-3xl font-display font-black tracking-tight">Ranked Job Matches</h2>
            <p className="text-slate-300 text-sm max-w-xl font-sans font-light">
              Your resume scored against real provider postings. Jobs ranked by match score — apply to the best fits first.
            </p>
          </div>
          <button
            onClick={handleSyncScrape}
            disabled={syncStatus !== 'idle'}
            className="px-6 py-3 bg-white text-indigo-950 hover:bg-slate-50 transition-all font-display font-semibold rounded-2xl flex items-center gap-2 shadow-lg disabled:opacity-50 text-sm w-full md:w-auto justify-center cursor-pointer hover:scale-101 border border-indigo-200/20"
          >
            <RefreshCw className={`h-4.5 w-4.5 ${syncStatus !== 'idle' ? 'animate-spin' : ''}`} />
              {syncStatus !== 'idle' ? 'Pipeline Active' : 'Refresh Pipeline'}
          </button>
        </div>
      </div>

      {refreshDiagnostics && (
        <div className="bg-white border border-slate-200/60 rounded-2xl p-5 shadow-2xs space-y-4 overflow-hidden">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-1 min-w-0">
              <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-bold">Refresh Diagnostics</p>
              <h3 className="font-display font-black text-slate-900 text-lg">Provider Results Panel</h3>
              <p className="text-sm text-slate-600 max-w-3xl break-words">
                This shows what each provider returned, which records were refreshed, and why no new job cards may have appeared after the run.
              </p>
            </div>
            <span className={`inline-flex w-fit items-center rounded-full border px-3 py-1 text-[10px] font-mono font-bold uppercase tracking-widest ${getRefreshStatusTone(refreshDiagnostics.status)}`}>
              {refreshDiagnostics.status}
            </span>
          </div>

          {(() => {
            const totals = refreshDiagnostics.totals || {
              fetched: refreshDiagnostics.summary.found,
              new_unique: refreshDiagnostics.summary.added,
              updated_existing: refreshDiagnostics.summary.updated,
              duplicate_results: refreshDiagnostics.summary.duplicates_removed,
              visible_new_jobs: refreshDiagnostics.summary.added,
            };
            const dedupe = refreshDiagnostics.dedupe || {
              strategy: 'provider_external_id_then_canonical_fingerprint',
              new_insert_count: refreshDiagnostics.summary.added,
              existing_match_count: refreshDiagnostics.summary.updated,
              duplicate_result_count: refreshDiagnostics.summary.duplicates_removed,
              possible_over_dedupe_count: 0,
            };
            const visibility = refreshDiagnostics.visibility || {
              visible_list_changed: refreshDiagnostics.summary.added > 0,
              reason_if_unchanged: refreshDiagnostics.summary.added > 0 ? null : refreshDiagnostics.reason_code,
              message: refreshDiagnostics.reason,
            };
            const outcome = getRefreshOutcomeSummary(refreshDiagnostics);
            const sampleUpdatedJobs = refreshDiagnostics.sample_updated_jobs || [];
            return (
              <>
                <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4 space-y-3 overflow-hidden">
                  <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-bold">Why no new jobs were added</p>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-slate-900 break-words">{outcome.title}</p>
                    <p className="text-sm text-slate-700 leading-relaxed break-words">{outcome.detail}</p>
                  </div>
                  <div className="flex flex-wrap gap-2 text-[10px] font-mono text-slate-500 min-w-0">
                    {outcome.chips.map((chip) => (
                      <span key={chip} className="rounded-lg bg-white border border-slate-200 px-2 py-1 break-words max-w-full">{chip}</span>
                    ))}
                    <span className="rounded-lg bg-white border border-slate-200 px-2 py-1 break-words max-w-full">Code: {refreshDiagnostics.reason_code}</span>
                    <span className="rounded-lg bg-white border border-slate-200 px-2 py-1 break-words max-w-full">Dedupe: {dedupe.strategy}</span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed break-words">{outcome.actionText}</p>
                </div>

                {!visibility.visible_list_changed && (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4 text-sm text-amber-900 space-y-2 overflow-hidden">
                    <p className="font-display font-bold">No new jobs were added because successful providers returned existing jobs only.</p>
                    <p className="text-xs leading-relaxed">
                      Providers returned {totals.fetched} jobs, CareerOS refreshed {totals.updated_existing} existing job records, detected {totals.duplicate_results} duplicate provider results, and inserted {totals.new_unique} new unique jobs.
                    </p>
                    <div className="flex flex-wrap gap-2 text-[10px] font-mono text-amber-900/80">
                      <span className="rounded-lg bg-white/70 border border-amber-200 px-2 py-1">Increase search breadth</span>
                      <span className="rounded-lg bg-white/70 border border-amber-200 px-2 py-1">Fix TheirStack billing</span>
                      <span className="rounded-lg bg-white/70 border border-amber-200 px-2 py-1">Refresh later</span>
                      <span className="rounded-lg bg-white/70 border border-amber-200 px-2 py-1">Review unscored jobs</span>
                    </div>
                  </div>
                )}

                {sampleUpdatedJobs.length > 0 && (
                  <div className="rounded-2xl border border-slate-100 bg-white p-4 min-w-0 overflow-hidden">
                    <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-bold">Updated existing jobs</p>
                    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                      {sampleUpdatedJobs.slice(0, 3).map((job: any) => (
                        <div key={`${job.provider}-${job.external_job_id || job.title}`} className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-xs text-slate-700 space-y-1 min-w-0 overflow-hidden">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-display font-bold text-slate-900 break-words">{job.title || 'Untitled job'}</span>
                            <span className="text-[10px] font-mono font-bold uppercase text-indigo-700 break-words">{job.provider || 'unknown'}</span>
                          </div>
                          <p className="text-[10px] text-slate-500 break-words">{job.company || 'Unknown company'}{job.external_job_id ? ` · ${job.external_job_id}` : ''}</p>
                          <p className="text-[10px] font-mono text-slate-500 break-words">Last seen: {job.last_seen_at || 'unknown'}</p>
                          <div className="flex flex-wrap gap-1 min-w-0">
                            {(job.updated_fields || []).slice(0, 4).map((field: string) => (
                              <span key={field} className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-mono uppercase tracking-wide text-slate-500 break-words max-w-full">
                                {field}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            );
          })()}

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {(refreshDiagnostics.provider_results || []).length > 0 ? (
              refreshDiagnostics.provider_results.map((provider) => (
                <div key={provider.provider} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs space-y-3 min-w-0 overflow-hidden">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold">{provider.display_name || provider.provider}</p>
                      <h4 className="font-display font-bold text-slate-900 break-words">{provider.provider}</h4>
                    </div>
                    <span className={`rounded-full border px-2.5 py-1 text-[10px] font-mono font-bold uppercase tracking-widest ${getRefreshStatusTone(provider.status)}`}>
                      {provider.status}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2 text-[10px] font-mono text-slate-500 min-w-0">
                    <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1 break-words max-w-full">Fetched: {provider.found ?? 0}</span>
                    <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1 break-words max-w-full">New jobs added: {provider.added ?? 0}</span>
                    <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1 break-words max-w-full">Existing jobs refreshed: {provider.updated ?? 0}</span>
                    <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1 break-words max-w-full">Duplicate results: {provider.duplicates_removed ?? 0}</span>
                    <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1 break-words max-w-full">Expired: {provider.expired_removed ?? 0}</span>
                    {provider.provider_status_code ? (
                      <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1 break-words max-w-full">Status: {provider.provider_status_code}</span>
                    ) : null}
                  </div>
                  {provider.query_context ? (
                    <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-[10px] font-mono text-slate-500 space-y-1 min-w-0 overflow-hidden">
                      <p className="font-bold uppercase tracking-wider text-slate-400">Query context</p>
                      <p className="break-words">Query: {provider.query_context.query || 'direct provider feed'}</p>
                      <p className="break-words">Location: {provider.query_context.location || 'India/Remote filters'}</p>
                      <p className="break-words">Limit: {provider.query_context.limit ?? 0} · Since: {provider.query_context.since || 'not used'} · Configured: {provider.query_context.configured ? 'yes' : 'no'}</p>
                    </div>
                  ) : null}
                  {provider.message ? (
                    <p className="text-xs text-slate-600 leading-relaxed break-words">{provider.message}</p>
                  ) : null}
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-500 md:col-span-2 xl:col-span-3">
                Provider diagnostics will appear here after the next refresh run.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Observability Box (LangGraph Live Pipeline Audit Logs) */}
      {syncStatus !== 'idle' && (
        <div className="bg-slate-900 border border-slate-700/50 text-slate-100 p-6 rounded-2xl shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Network className="h-5 w-5 text-indigo-400" />
              <span className="font-mono text-sm uppercase tracking-wide text-indigo-300 font-bold">
                LangGraph: JobMatchingGraph
              </span>
            </div>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 rounded-md">
              Executing Trace
            </span>
          </div>

          {/* Graphical Node Connectors representing StateGraph execution */}
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-3 text-center py-2 font-mono text-xs">
            
            <div className={`p-2 border rounded-xl transition-all ${syncStatus === 'fetching' ? 'border-amber-400 bg-amber-400/10 text-amber-200 shadow-sm' : 'border-slate-800 bg-slate-950 text-slate-500'}`}>
              <div className="text-[10px] text-slate-400 uppercase">Node 1</div>
              <div className="font-bold truncate mt-0.5">fetch_jobs</div>
            </div>

            <div className={`p-2 border rounded-xl transition-all ${syncStatus === 'normalizing' ? 'border-amber-400 bg-amber-400/10 text-amber-200 shadow-sm' : 'border-slate-800 bg-slate-950 text-slate-500'}`}>
              <div className="text-[10px] text-slate-400 uppercase">Node 2</div>
              <div className="font-bold truncate mt-0.5">normalize</div>
            </div>

            <div className={`p-2 border rounded-xl transition-all ${syncStatus === 'deduping' ? 'border-amber-400 bg-amber-400/10 text-amber-200 shadow-sm' : 'border-slate-800 bg-slate-950 text-slate-500'}`}>
              <div className="text-[10px] text-slate-400 uppercase">Node 3</div>
              <div className="font-bold truncate mt-0.5">deduplicate</div>
            </div>

            <div className={`p-2 border rounded-xl transition-all ${syncStatus === 'enriching' ? 'border-amber-400 bg-amber-400/10 text-amber-200 shadow-sm' : 'border-slate-800 bg-slate-950 text-slate-500'}`}>
              <div className="text-[10px] text-slate-400 uppercase">Node 4</div>
              <div className="font-bold truncate mt-0.5">enrich</div>
            </div>

            <div className={`p-2 border rounded-xl transition-all ${syncStatus === 'matching' ? 'border-amber-400 bg-amber-400/10 text-amber-200 shadow-sm' : 'border-slate-800 bg-slate-950 text-slate-500'}`}>
              <div className="text-[10px] text-slate-400 uppercase">Node 5</div>
              <div className="font-bold truncate mt-0.5">get_profile</div>
            </div>

            <div className={`p-2 border rounded-xl transition-all ${syncStatus === 'matching' ? 'border-amber-400 bg-amber-400/10 text-amber-200 shadow-sm' : 'border-slate-800 bg-slate-950 text-slate-500'}`}>
              <div className="text-[10px] text-slate-400 uppercase">Node 6</div>
              <div className="font-bold mt-0.5">match_jobs</div>
            </div>

            <div className={`p-2 border rounded-xl transition-all ${syncStatus === 'ranking' ? 'border-amber-400 bg-amber-400/10 text-amber-200 shadow-sm' : 'border-slate-800 bg-slate-950 text-slate-500'}`}>
              <div className="text-[10px] text-slate-400 uppercase">Node 7</div>
              <div className="font-bold mt-0.5">rank_jobs</div>
            </div>
          </div>

          <div className="flex items-center gap-3 bg-slate-950 rounded-xl p-3 border border-slate-800 font-mono text-xs">
            <span className="h-2 w-2 bg-emerald-500 rounded-full animate-ping" />
            <span className="text-emerald-400 font-semibold uppercase shrink-0">Status Detail:</span>
            <span className="text-slate-300 truncate">{currentStepDetail}</span>
          </div>

          {stageHistory.length > 0 && (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {stageHistory.slice(-6).map((stage, index) => (
                <div key={`${stage.node}-${stage.at}-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/80 p-3 text-left">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-mono uppercase tracking-wide text-indigo-300">{stage.label}</span>
                    <span className="text-[9px] font-mono text-slate-500">{formatJobClock(stage.at)}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-300 break-all">{stage.node}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Active Resume Indicator */}
      <div className="bg-white border border-slate-200/50 rounded-2xl p-5 shadow-2xs text-slate-900">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-bold">Resume Selector</p>
          {onSelectDoc && (
            <select
              value={activeResume?.id || ''}
              onChange={(e) => {
                onSelectDoc(e.target.value);
                setSelectedJob(null);
                setSelectedPhase2(null);
              }}
              className="px-3 py-1.5 text-xs border border-slate-200 rounded-xl bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all font-medium text-slate-700 max-w-xs"
            >
              <option value="" disabled>Select a resume...</option>
              {selectableDocuments
                .map(d => (
                  <option key={d.id} value={d.id}>{d.filename}</option>
                ))
              }
            </select>
          )}
        </div>
        {activeResume ? (
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4 items-center">
            <div className="md:col-span-2">
              <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-bold">Active Resume</p>
              <h3 className="font-display font-black text-slate-900 mt-1">{activeResume.filename}</h3>
              <p className="text-xs text-slate-500 mt-1">Upload Date: {formatDateTimeLocal(activeResume.created_at)}</p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:col-span-4">
              <ResumeStat label="Index Status" value={activeResume.status} />
              <ResumeStat label="Chunk Count" value={String(activeResume.chunk_count ?? alignmentSummary?.active_resume?.chunk_count ?? 0)} />
              <ResumeStat label="Embedding" value={activeResume.embedding_status || alignmentSummary?.active_resume?.embedding_status || activeResume.status} />
              <ResumeStat label="Vector Count" value={String(activeResume.vector_count ?? alignmentSummary?.active_resume?.vector_count ?? 0)} />
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3 text-amber-700">
            <XCircle className="h-5 w-5" />
            <div>
              <h3 className="font-display font-bold">No valid resume selected.</h3>
              <p className="text-xs text-slate-500">Upload and index a resume with extractable content before refreshing the feed.</p>
            </div>
          </div>
        )}
      </div>

      {/* Statistics Panels Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        
        <div className="bg-white border border-slate-200/50 rounded-2xl p-5 shadow-2xs flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 mt-0.5">Current Ranked Feed</p>
            <h4 className="text-2xl font-display font-black text-slate-900">{stats.total_jobs ?? 0} Jobs</h4>
            <p className="text-[10px] text-slate-400 font-mono">Active + India + tech + direct apply URL.</p>
          </div>
          <div className="h-10 w-10 bg-slate-100 rounded-xl flex items-center justify-center text-slate-600">
            <Briefcase className="h-5 w-5" />
          </div>
        </div>

        <div className="bg-white border border-slate-200/50 rounded-2xl p-5 shadow-2xs flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 mt-0.5">Provider Inventory</p>
            <h4 className="text-2xl font-display font-black text-slate-900">{stats.raw_total_jobs ?? stats.total_jobs ?? 0} Jobs</h4>
            <p className="text-[10px] text-slate-400 font-mono">{stats.filtered_out_jobs ?? 0} currently filtered out before ranking.</p>
          </div>
          <div className="h-10 w-10 bg-slate-100 rounded-xl flex items-center justify-center text-slate-600">
            <Layers className="h-5 w-5" />
          </div>
        </div>

        <div className="bg-white border border-slate-200/50 rounded-2xl p-5 shadow-2xs flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 mt-0.5">Real Providers</p>
            <h4 className="text-2xl font-display font-black text-slate-800">{providerCatalog.length || stats.active_sources} Sources</h4>
          </div>
          <div className="h-10 w-10 bg-slate-100 rounded-xl flex items-center justify-center text-slate-600">
            <Layers className="h-5 w-5" />
          </div>
        </div>
      </div>

      {(stats.raw_total_jobs ?? 0) > (stats.total_jobs ?? 0) && (
        <div className="bg-white border border-slate-200/50 rounded-2xl p-4 shadow-2xs">
          <p className="text-xs font-display font-bold text-slate-900">Why the inventory count is bigger than the ranked count</p>
          <p className="mt-1 text-xs text-slate-600 leading-relaxed">
            CareerOS stores the full provider inventory, then narrows it to the jobs that are currently worth ranking for your active feed.
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-mono text-slate-500">
            <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1">Inventory: {stats.raw_total_jobs ?? 0}</span>
            <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1">Ranked now: {stats.total_jobs ?? 0}</span>
            <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1">Filtered non-India: {stats.non_india_filtered_jobs ?? 0}</span>
            <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1">Filtered non-tech: {stats.non_tech_filtered_jobs ?? 0}</span>
            <span className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-1">Filtered stale/closed: {stats.stale_or_closed_jobs ?? 0}</span>
          </div>
        </div>
      )}

      {/* Main Split Layout Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 min-w-0">
        
        {/* Left column - Filter Panel, Ingestion Runs & List (Grid 2/3) */}
        <div className="lg:col-span-2 space-y-6 min-w-0">
          
          {/* Controls Bar */}
          <div className="bg-white p-4 border border-slate-200/60 rounded-2xl space-y-3.5 shadow-2xs">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-grow">
                <Search className="absolute left-3.5 top-3.5 h-4.5 w-4.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Query company, job titles, or role skills..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-slate-400 transition-all font-sans"
                />
              </div>

              <div className="flex flex-wrap gap-2">
                <select
                  value={selectedSource || ''}
                  onChange={(e) => setSelectedSource(e.target.value)}
                  className="px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none font-medium text-slate-600"
                >
                  <option value="">All Providers</option>
                  {(providerCatalog.length ? providerCatalog : [
                    { name: 'theirstack', display_name: 'TheirStack' },
                    { name: 'remoteok', display_name: 'RemoteOK' },
                    { name: 'arbeitnow', display_name: 'Arbeitnow' },
                    { name: 'adzuna', display_name: 'Adzuna' },
                    { name: 'usajobs', display_name: 'USAJobs' },
                    { name: 'greenhouse', display_name: 'Greenhouse' },
                    { name: 'lever', display_name: 'Lever' },
                  ]).map((provider) => (
                    <option key={provider.name} value={provider.name}>
                      {provider.display_name || provider.name}
                    </option>
                  ))}
                </select>

                <select
                  value={selectedPlace || ''}
                  onChange={(e) => setSelectedPlace(e.target.value)}
                  className="px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none font-medium text-slate-600"
                  >
                    <option value="">All India</option>
                    <option value="bengaluru">Bengaluru</option>
                    <option value="chennai">Chennai</option>
                    <option value="hyderabad">Hyderabad</option>
                  <option value="pune">Pune</option>
                  <option value="mumbai">Mumbai</option>
                  <option value="delhi">Delhi NCR</option>
                  <option value="kolkata">Kolkata</option>
                  <option value="remote india">Remote India</option>
                  <option value="coimbatore">Coimbatore</option>
                    <option value="kochi">Kochi</option>
                    <option value="ahmedabad">Ahmedabad</option>
                  </select>

                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold px-0.5">Sort by</span>
                    <select
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value as JobSortOption)}
                      className="px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none font-medium text-slate-600 min-w-[170px]"
                    >
                      <option value="best_match">Best match</option>
                      <option value="posted_at_desc">Latest posted</option>
                      <option value="fetched_at_desc">Recently fetched</option>
                      <option value="freshness_desc">Highest freshness</option>
                      <option value="company_asc">Company A-Z</option>
                    </select>
                  </div>
                </div>
              </div>

            {/* Match Rating sliders wrapper */}
            <div className="flex items-center gap-3 pt-1 border-t border-slate-100 text-xs">
              <span className="font-mono text-slate-400 uppercase tracking-wide">Filter Minimal Alignment:</span>
              <div className="flex gap-2.5">
                {[0, 60, 75, 85].map((scVal) => (
                  <button
                    key={scVal}
                    onClick={() => setMinScore(scVal)}
                    className={`px-3 py-1 font-mono hover:bg-slate-50 border rounded-lg transition-all ${minScore === scVal ? 'bg-indigo-650 font-bold border-indigo-600 text-indigo-700 bg-indigo-50/50' : 'text-slate-500 border-slate-200'}`}
                  >
                    {scVal === 0 ? 'Off' : `>= ${scVal}%`}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Top Matches */}
          {topMatches.length > 0 && (
            <div className="bg-white p-4 border border-emerald-100 rounded-2xl space-y-3 shadow-2xs">
              <h3 className="font-display font-bold text-sm text-slate-900 flex items-center gap-2">
                <Sparkles className="h-4.5 w-4.5 text-emerald-600" />
                Top Matches
              </h3>
              <div className="grid grid-cols-1 gap-2">
                {topMatches.map((job) => (
                  <button
                    key={`top-${job.id}`}
                    onClick={() => selectJob(job.id)}
                    className="text-left p-3 rounded-xl border border-slate-100 hover:border-slate-300 bg-slate-50/60 transition-all"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-xs font-display font-bold text-slate-900">{job.company}</div>
                        <div className="text-xs text-slate-600">{job.title} · {job.location}</div>
                      </div>
                      <div className="text-lg font-display font-black text-emerald-600">{job.match.match_score}%</div>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1 truncate">{job.match.summary}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Job Postings Results List */}
          <div className="space-y-4">
            <h3 className="font-display font-medium text-base text-slate-900 tracking-tight flex items-center justify-between">
              <span>
                Ranked Job Matches ({matchedJobs.length} scored)
                <span className="ml-2 text-xs font-mono text-slate-400">
                  Showing {displayJobs.length} of {stats.total_jobs ?? matchedJobs.length}
                </span>
              </span>
              <span className="flex items-center gap-3">
                {unscoredJobs.length > 0 && (
                  <button
                    onClick={() => setShowUnscored(!showUnscored)}
                    className="text-xs font-mono text-indigo-600 hover:text-indigo-800 underline ml-3"
                  >
                    {showUnscored ? 'Hide' : 'Show'} {unscoredJobs.length} unscored jobs
                  </button>
                )}
                {isLoading && <span className="text-xs font-mono text-slate-400 animate-pulse ml-3">Running fetch query...</span>}
              </span>
            </h3>

            {displayJobs.length === 0 ? (
              <div className="bg-white border border-slate-200/50 rounded-2xl p-12 text-center shadow-2xs">
                <div className="h-12 w-12 bg-slate-50 border border-slate-200/40 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-400 shadow-2xs animate-pulse">
                  <Briefcase className="h-6 w-6" />
                </div>
                <h4 className="font-display font-bold text-slate-800 text-sm">No scored matches yet</h4>
                <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                  Run Refresh Pipeline or wait for the next matching cycle. Fresh jobs are available under &quot;Unscored jobs&quot; toggle.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4.5">
                {displayJobs.map((job) => {
                  const hasMatch = job.match?.score_source === "job_match" && job.match?.match_score != null;
                  const matchScore = job.match?.match_score ?? null;

                  return (
                    <div 
                      key={job.id} 
                      onClick={() => selectJob(job.id)}
                      className={`group bg-white hover:bg-slate-50 border transition-all rounded-2xl p-5 shadow-2xs flex flex-col sm:flex-row justify-between items-start gap-4 cursor-pointer relative ${selectedJob?.id === job.id ? 'border-slate-800 ring-1 ring-slate-800' : 'border-slate-200/60'}`}
                    >
                      {/* Left Block details */}
                      <div className="space-y-2 flex-grow">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[10px] font-mono tracking-widest uppercase bg-slate-100 text-slate-500 font-bold border border-slate-200 rounded px-1.5 py-0.5">
                            Source: {job.source || 'unknown'}
                          </span>
                          <span className="text-[10px] font-mono tracking-widest uppercase bg-indigo-50 text-indigo-700 font-bold border border-indigo-200 rounded px-1.5 py-0.5">
                            Provider: {job.source_provider || job.source || 'unknown'}
                          </span>
                          <span className="text-xs text-slate-400 flex items-center gap-1 font-mono">
                            <Clock className="h-3.5 w-3.5" />
                            Posted: {formatPostedDate(job)}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-2 text-[10px] text-slate-400 font-mono">
                          <span>Fetched: {formatFetchedTimestamp(job)}</span>
                          <span>Last seen: {formatLastSeenTimestamp(job)}</span>
                          <span>Posted: {formatPostedDate(job)}</span>
                          {job.freshness_bucket && <span>Freshness: {job.freshness_bucket} ({Math.round(job.freshness_score || 0)})</span>}
                          {job.opportunity_priority_score != null && <span>Priority: {Math.round(job.opportunity_priority_score)}</span>}
                          {job.match?.deadline_status && (
                            <span className={`${
                              job.match.deadline_status === 'CLOSING_SOON' ? 'text-amber-600 font-bold' :
                              job.match.deadline_status === 'CLOSED' ? 'text-red-600' :
                              'text-slate-400'
                            }`}>
                              Deadline: {job.match.deadline_display || job.match.deadline_status}
                            </span>
                          )}
                          {job.match?.career_family && job.match.career_family !== 'unknown' && (
                            <span className="bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded">
                              {job.match.career_family}
                            </span>
                          )}
                        </div>
                        
                        <div>
                          <h4 className="font-display font-bold text-slate-800 text-sm group-hover:text-indigo-950 transition-colors">
                            {job.title}
                          </h4>
                          <div className="flex items-center gap-3.5 text-xs text-slate-500 mt-1">
                            <span className="flex items-center gap-1">
                              <Building2 className="h-3.5 w-3.5 text-slate-300" />
                              {job.company}
                            </span>
                            <span className="flex items-center gap-1">
                              <MapPin className="h-3.5 w-3.5 text-slate-300" />
                              {job.location}
                            </span>
                          </div>
                        </div>

                        {/* Top 3 Skill tags */}
                          {(job.extracted_skills || job.skills || job.skills_required) && (job.extracted_skills || job.skills || job.skills_required).length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {(job.extracted_skills || job.skills || job.skills_required).slice(0, 3).map((sk: any, idx: number) => (
                              <span 
                                key={sk.id || `${job.id}-${sk}-${idx}`} 
                                className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border bg-slate-50 border-slate-100 text-slate-500"
                              >
                                {sk.skill || sk}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Score Indicator Badge */}
                      <div className="sm:text-right shrink-0 flex sm:flex-col justify-between items-center sm:items-end w-full sm:w-auto border-t border-slate-100 sm:border-t-0 pt-3 sm:pt-0">
                        {hasMatch ? (
                          <div className="text-center sm:text-right">
                            <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-0.5">Match Index</span>
                            {job.seniority_level && (
                              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-200">{job.seniority_level}</span>
                            )}
                            {job.tech_role_category && (
                              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600 border border-emerald-200">{job.tech_role_category}</span>
                            )}
                            <div className="flex items-center gap-1.5 justify-end">
                              <span className={`text-xl font-display font-black ${matchScore >= 80 ? 'text-emerald-600' : matchScore >= 65 ? 'text-indigo-650' : 'text-slate-600'}`}>
                                {matchScore}%
                              </span>
                            </div>
                          </div>
                        ) : (
                          <div className="text-left sm:text-right text-slate-400 text-xs py-2 font-mono flex items-center gap-1.5">
                            <XCircle className="h-4.5 w-4.5" />
                            Unscored
                          </div>
                        )}

                        <div className="mt-3 text-slate-300 group-hover:text-slate-600 hidden sm:flex items-center gap-2">
                          {hasMatch && (
                            <span className="text-[10px] font-mono text-slate-400">
                              View details →
                            </span>
                          )}
                          {job.apply_url && (
                            <a
                              href={job.apply_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[10px] font-mono text-indigo-500 hover:text-indigo-700 transition-colors"
                              onClick={(e) => e.stopPropagation()}
                            >
                              Apply
                            </a>
                          )}
                          <Maximize2 className="h-4.5 w-4.5" />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right column - Ingested Runs feed & Detail Views (Grid 1/3) */}
        <div className="space-y-6 min-w-0">

          {/* Active Job Detail Display Sheet */}
          <div className="bg-white border border-slate-200/60 rounded-2xl p-6 shadow-xs relative overflow-hidden min-w-0">
            {selectedJob ? (
              <div className="space-y-6 animate-fade-in">
                
                {/* Header detail */}
                <div className="border-b border-slate-100 pb-4.5 space-y-3 min-w-0">
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-[10px] font-mono uppercase font-black px-2 py-0.5 bg-slate-100 text-slate-500 rounded border border-slate-200">
                      {selectedJob.source_provider || selectedJob.source} Pipeline
                    </span>
                    {selectedJob.apply_url ? (
                      <a
                      href={selectedJob.apply_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={() => {
                        const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
                        fetch(`${baseUrl}/jobs/${selectedJob.id}/application`, {
                          method: 'POST',
                          headers,
                          body: JSON.stringify({ status: 'APPLIED', notes: 'User clicked Apply to Job from CareerOS.' })
                        }).catch(() => undefined);
                      }}
                      className="px-3 py-1 rounded-lg transition-colors font-semibold text-[11px] flex items-center gap-1 bg-slate-900 text-white hover:bg-indigo-950 disabled:opacity-50"
                    >
                      <ExternalLink className="h-3 w-3" />
                      Apply to Job
                    </a>
                    ) : (
                      <span className="px-3 py-1 rounded-lg font-semibold text-[11px] flex items-center gap-1 bg-slate-100 text-slate-400">
                        Direct application unavailable
                      </span>
                    )}
                  </div>

                  <div>
                    <h3 className="font-display font-black text-slate-900 tracking-tight text-base sm:text-lg break-words">
                      {selectedJob.title}
                    </h3>
                    <p className="text-xs text-slate-500 mt-1 flex items-center gap-1.5 font-medium flex-wrap break-words">
                      <Building2 className="h-4 w-4 text-slate-300" />
                      {selectedJob.company}
                      <span className="text-slate-300">•</span>
                      <MapPin className="h-4 w-4 text-slate-300" />
                      {selectedJob.location}
                    </p>
                    <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] font-mono text-slate-500 min-w-0">
                      <span className="rounded-lg bg-slate-50 border border-slate-100 px-2 py-1 break-words">Provider: {selectedJob.source_provider || selectedJob.source || 'Unknown'}</span>
                      <span className="rounded-lg bg-slate-50 border border-slate-100 px-2 py-1 break-words">Posted: {formatPostedDate(selectedJob)}</span>
                      <span className="rounded-lg bg-slate-50 border border-slate-100 px-2 py-1 break-words">Fetched: {formatFetchedTimestamp(selectedJob)}</span>
                      <span className="rounded-lg bg-slate-50 border border-slate-100 px-2 py-1 break-words">Last seen: {formatLastSeenTimestamp(selectedJob)}</span>
                      <span className="rounded-lg bg-slate-50 border border-slate-100 px-2 py-1 break-words">Freshness: {selectedJob.freshness_bucket || 'unknown'} ({Math.round(selectedJob.freshness_score || 0)})</span>
                      <span className="rounded-lg bg-slate-50 border border-slate-100 px-2 py-1 break-words">Priority: {Math.round(selectedJob.opportunity_priority_score || 0)}</span>
                      <span className="rounded-lg bg-slate-50 border border-slate-100 px-2 py-1 break-words">Lifecycle: {selectedJob.lifecycle_state || 'NEW'}</span>
                    </div>
                  </div>
                </div>

                {/* AI Assets Tailoring Generator Block */}
                <div className="bg-gradient-to-br from-indigo-950 via-slate-900 to-indigo-950 border border-slate-800 p-4 rounded-2xl text-white space-y-3 shadow-md overflow-hidden">
                  <div className="flex items-center gap-1.5">
                    <Sparkles className="h-4.5 w-4.5 text-indigo-400 animate-pulse" />
                    <span className="text-[10px] font-mono tracking-wider uppercase text-indigo-200 font-bold">App Package Generator</span>
                  </div>
                  <p className="text-[11px] text-slate-350 font-light leading-snug break-words">
                    Instantly craft an ATS-tailored Resume, custom Cover Letter, LinkedIn outreaches, and an expert Interview Prep Sheet using RAG matching.
                  </p>
                  <button
                    onClick={() => {
                      if (selectedJob?.id != null) {
                        onGeneratePackage?.(String(selectedJob.id));
                      }
                    }}
                    disabled={isGenerating || selectedJob?.id == null}
                    className="w-full py-2.5 bg-indigo-550 hover:bg-indigo-650 active:scale-98 text-white text-xs font-semibold rounded-xl shadow-md transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
                    {isGenerating ? 'Drafting Assets (under 60s)...' : 'Generate Application Package'}
                  </button>
                </div>

                {/* Score Widget Card */}
                {selectedJob.match ? (
                  <div className="bg-slate-50 border border-slate-200/30 p-4 rounded-xl space-y-3 overflow-hidden">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-bold block">
                        RAG Alignment Score
                      </span>
                      <span className="text-xs font-mono uppercase text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-100 font-bold">
                        Conf: {(selectedJob.match.confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div className="flex items-end gap-3 justify-between">
                      <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden self-center">
                        <div 
                          className={`h-full rounded-full transition-all duration-500 ${selectedJob.match.match_score >= 80 ? 'bg-emerald-500' : selectedJob.match.match_score >= 65 ? 'bg-indigo-500' : 'bg-slate-400'}`}
                          style={{ width: `${selectedJob.match.match_score}%` }}
                        />
                      </div>
                      <span className={`text-2xl font-display font-black leading-none ${selectedJob.match.match_score >= 80 ? 'text-emerald-600' : 'text-slate-800'}`}>
                        {selectedJob.match.match_score}%
                      </span>
                    </div>

                    <p className="text-xs font-sans text-slate-600 italic bg-white/60 p-2.5 rounded-lg border border-slate-200/20 break-words">
                      &quot;{selectedJob.match.summary}&quot;
                    </p>
                    <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-600 min-w-0">
                      <span className="bg-white/70 border border-slate-200/40 rounded-lg px-2 py-1 break-words">
                        Freshness {Math.round(selectedJob.match.freshness_score || selectedJob.freshness_score || 0)}
                      </span>
                      <span className="bg-white/70 border border-slate-200/40 rounded-lg px-2 py-1 break-words">
                        Priority {Math.round(selectedJob.match.opportunity_priority_score || selectedJob.opportunity_priority_score || 0)}
                      </span>
                      <span className="bg-white/70 border border-slate-200/40 rounded-lg px-2 py-1 break-words">
                        Provider Quality {Math.round(selectedJob.match.provider_quality_score || selectedJob.provider_quality_score || 0)}
                      </span>
                      <span className="bg-white/70 border border-slate-200/40 rounded-lg px-2 py-1 break-words">
                        Learning Time {selectedJob.match.estimated_learning_time || 'n/a'}
                      </span>
                    </div>
                    {selectedJob.match.below_40_explanation && (
                      <p className="text-[11px] text-rose-700 bg-rose-50 border border-rose-100 rounded-lg p-2">
                        Below 40% explanation: {selectedJob.match.below_40_explanation}
                      </p>
                    )}
                    {selectedJob.match.estimated_score_improvement && (
                      <p className="text-[11px] text-indigo-700 bg-indigo-50 border border-indigo-100 rounded-lg p-2">
                        Estimated improvement after closing top gaps: +{selectedJob.match.estimated_score_improvement.points} pts to about {selectedJob.match.estimated_score_improvement.projected_score}%.
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="bg-slate-50 border border-slate-200/40 p-4 rounded-xl text-center text-slate-400 text-xs py-5">
                    No alignment calculations complete yet. Complete resume uploading to run RAG vector spaces.
                  </div>
                )}

                {/* Why This Match */}
                {selectedJob.match?.components && (
                  <div className="bg-white border border-slate-200 rounded-xl overflow-hidden min-w-0">
                    <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
                      <h4 className="text-xs font-mono uppercase tracking-wider font-black text-slate-700">Why this match?</h4>
                      <p className="text-[11px] text-slate-500 mt-1 break-words">Scores are calculated against {selectedJob.match.active_resume?.name || activeResume?.filename || 'the active resume'}.</p>
                    </div>
                    <div className="divide-y divide-slate-100">
                      {selectedJob.match.components.map((component: any) => (
                        <div key={component.key} className="p-3 space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-display font-bold text-slate-900 break-words">{component.label}</span>
                            <span className="text-xs font-mono font-bold text-indigo-700 break-words">{component.score}% · {(component.weight * 100).toFixed(0)}% weight</span>
                          </div>
                          <div className="flex flex-wrap gap-1.5 min-w-0">
                            {(component.evidence || []).slice(0, 3).map((item: string) => (
                              <span key={`${component.key}-e-${item}`} className="inline-flex items-center gap-1 text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-100 rounded px-1.5 py-0.5 break-words max-w-full">
                                <CheckCircle className="h-3 w-3" /> {item}
                              </span>
                            ))}
                            {(component.missing || []).slice(0, 3).map((item: string) => (
                              <span key={`${component.key}-m-${item}`} className="inline-flex items-center gap-1 text-[10px] bg-rose-50 text-rose-700 border border-rose-100 rounded px-1.5 py-0.5 break-words max-w-full">
                                <XCircle className="h-3 w-3" /> {item}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="px-4 py-3 bg-slate-950 text-white flex items-center justify-between">
                      <span className="text-xs font-display font-bold">Final Score</span>
                      <span className="text-lg font-display font-black">{selectedJob.match.match_score}%</span>
                    </div>
                  </div>
                )}

                {selectedJob.match && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <SkillEvidenceList title="Matched Skills" items={selectedJob.match.matched_skills || []} tone="match" />
                    <SkillEvidenceList title="Missing Skills" items={selectedJobMissingSkills} tone="gap" />
                  </div>
                )}

                {selectedJobMissingSkills.length > 0 && (
                  <div className="space-y-3 border-t border-slate-100 pt-4">
                    <LearningPathsPanel
                      title="Verified Learning Paths for Top Gaps"
                      subtitle="Free resources mapped to the exact missing skills in this job match."
                      skillSlugs={selectedJobMissingSkills}
                      limit={Math.min(selectedJobMissingSkills.length, 25) || 1}
                      compact
                      emptyMessage="No verified free resource is available yet for these gaps. Add curated resources or enable YouTube discovery."
                    />
                    <EvidenceBackedSkillGapPanel
                      token={token}
                      jobId={selectedJob?.id}
                      jobTitle={selectedJob?.title}
                      company={selectedJob?.company}
                      skillSlugs={selectedJobMissingSkills}
                      compact
                      emptyMessage="No evidence-backed skill gap analysis is available for the current job yet."
                    />
                    <GapActionsPanel
                      token={token}
                      jobId={selectedJob?.id}
                      jobTitle={selectedJob?.title}
                      company={selectedJob?.company}
                      skillSlugs={selectedJobMissingSkills}
                      compact
                      emptyMessage="No proof actions are available yet for the current gaps."
                    />
                    <GitHubProjectsPanel
                      token={token}
                      jobId={selectedJob?.id}
                      jobTitle={selectedJob?.title}
                      company={selectedJob?.company}
                      skillSlugs={selectedJobMissingSkills}
                      compact
                      emptyMessage="No GitHub project recommendations are available yet for the current gaps."
                    />
                  </div>
                )}

                {/* Enriched Attribute Fields */}
                <div className="space-y-4">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block font-black">
                    Required Competencies
                  </span>

                  {(selectedJob.extracted_skills || selectedJob.skills || selectedJob.skills_required) && (selectedJob.extracted_skills || selectedJob.skills || selectedJob.skills_required).length > 0 ? (
                    <div className="grid grid-cols-2 gap-2">
                      {(selectedJob.extracted_skills || selectedJob.skills || selectedJob.skills_required).map((s: any, idx: number) => (
                        <div key={s.id || `${selectedJob.id}-skill-${idx}`} className="p-2 border border-slate-100 rounded-xl bg-slate-50/50 text-[11px] font-sans">
                          <span className="font-semibold block text-slate-700">{s.skill || s}</span>
                          <span className="text-[9px] font-mono font-bold uppercase text-slate-400">
                            Required
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 border border-slate-100 rounded-xl text-xs text-slate-400 italic">
                      Compiling extracted tags via Claude Sonnet 4.6 engine...
                    </div>
                  )}
                </div>

                {/* Match Strengths and Gaps Analysis */}
                {selectedJob.match && (
                  <div className="space-y-5.5 pt-2 border-t border-slate-100">
                    
                    {/* Strengths */}
                    <div className="space-y-2">
                      <h5 className="text-[10px] font-mono uppercase font-black tracking-wider text-emerald-600 flex items-center gap-1">
                        <CheckCircle className="h-4 w-4" />
                        Aesthetic Alignments / Strengths
                      </h5>
                      <div className="space-y-2">
                        {selectedJob.match.strengths?.map((str: Strength) => (
                          <div key={str.id} className="p-2.5 bg-emerald-50/30 border border-emerald-100/40 rounded-xl space-y-1">
                            <span className="text-[11px] font-bold text-slate-800 block leading-tight">{str.title}</span>
                            <p className="text-[10px] text-slate-600 leading-normal">{str.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Gaps */}
                    <div className="space-y-2">
                      <h5 className="text-[10px] font-mono uppercase font-black tracking-wider text-amber-600 flex items-center gap-1">
                        <XCircle className="h-4 w-4" />
                        Skill Deficiencies / Resume Gaps
                      </h5>
                      <div className="space-y-2">
                        {selectedJob.match.gaps?.map((gap: Gap) => (
                          <div key={gap.id} className="p-2.5 bg-amber-50/30 border border-amber-100/40 rounded-xl space-y-1">
                            <span className="text-[11px] font-bold text-slate-800 block leading-tight">{gap.category}</span>
                            <p className="text-[10px] text-slate-600 leading-normal">{gap.description}</p>
                            <div className="text-[9px] font-mono text-slate-500 bg-slate-100 px-1 py-0.5 rounded mt-1 font-semibold leading-normal">
                              Suggestion: {gap.suggestion}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {selectedPhase2 && (
                  <div className="space-y-3 border-t border-slate-100 pt-4">
                    <h4 className="text-[10px] font-mono uppercase tracking-wider font-black text-indigo-600">
                      Opportunity Intelligence
                    </h4>
                    {selectedPhase2.report ? (
                      <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-3 space-y-2">
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-xs font-display font-bold text-slate-900">
                            {selectedPhase2.report.recommended_priority}
                          </span>
                          <span className="text-xs font-mono font-black text-indigo-700">
                            Rank {Math.round(selectedPhase2.report.opportunity_rank_score || 0)}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600">{selectedPhase2.report.report?.why_this_job_matters}</p>
                        <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-600">
                          <span>Gap {Math.round(selectedPhase2.report.skill_gap_score || 0)}</span>
                          <span>Urgency {Math.round(selectedPhase2.report.application_urgency || 0)}</span>
                          <span>Growth {Math.round(selectedPhase2.report.career_growth_potential || 0)}</span>
                          <span>Competition {Math.round(selectedPhase2.report.competition_risk || 0)}</span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-[11px] text-slate-400">No intelligence report has been generated for this job yet.</p>
                    )}
                    {selectedPhase2.salary && (
                      <div className="rounded-xl border border-slate-200 bg-white p-3 overflow-hidden min-w-0">
                        <h5 className="text-[10px] font-mono uppercase font-black text-slate-500 mb-2">Salary Intelligence</h5>
                        <p className="text-xs font-display font-bold text-slate-900">
                          {selectedPhase2.salary.salary_currency} {Math.round(selectedPhase2.salary.monthly_min || 0)} - {Math.round(selectedPhase2.salary.monthly_max || 0)} monthly
                        </p>
                        <p className="text-[10px] text-slate-500 font-mono break-words">
                          Yearly: {Math.round(selectedPhase2.salary.yearly_min || 0)} - {Math.round(selectedPhase2.salary.yearly_max || 0)} · confidence {(selectedPhase2.salary.salary_confidence * 100).toFixed(0)}%
                        </p>
                      </div>
                    )}
                    {selectedPhase2.interview_prep && (
                      <div className="rounded-xl border border-slate-200 bg-white p-3 overflow-hidden min-w-0">
                        <h5 className="text-[10px] font-mono uppercase font-black text-slate-500 mb-2">Interview Prep Agent</h5>
                        <ul className="space-y-1 text-[11px] text-slate-600 list-disc pl-4">
                          {(selectedPhase2.interview_prep.technical_questions || []).slice(0, 3).map((q: string) => (
                            <li key={q}>{q}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {(selectedPhase2.alert_decisions || []).length > 0 && (
                      <Phase2List
                        title="Recent Alert Decisions"
                        items={(selectedPhase2.alert_decisions || []).slice(0, 3).map((d: any) => `${d.decision}: ${d.reason}`)}
                      />
                    )}
                    {(selectedPhase2.application_timeline || []).length > 0 && (
                      <Phase2List
                        title="Application Timeline"
                        items={(selectedPhase2.application_timeline || []).map((e: any) => `${e.status}: ${formatDateTimeLocal(e.created_at)}`)}
                      />
                    )}
                  </div>
                )}

                {/* Full Description text snippet */}
                <div className="space-y-2 border-t border-slate-100 pt-4.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block font-black">
                    Raw Job Description
                  </span>
                  <p className="text-xs text-slate-600 leading-relaxed font-sans max-h-48 overflow-y-auto bg-slate-50/50 p-3 rounded-xl border border-dotted border-slate-200 break-words">
                    {selectedJob.full_description || selectedJob.description}
                  </p>
                </div>

              </div>
            ) : (
              <div className="text-center py-20 text-slate-400 font-sans space-y-3">
                <div className="h-10 w-10 bg-slate-50 rounded-full flex items-center justify-center mx-auto text-slate-350">
                  <Layers className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="font-display font-medium text-xs text-slate-800">No Job Selected</h4>
                  <p className="text-[11px] max-w-xs mx-auto text-slate-400 mt-1">
                    Select any opportunity from the database to view deep credentials assessment, match indexes, and gaps suggestions.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Job Ingestion Runs Widget */}
          <div className="bg-white border border-slate-200/50 rounded-2xl p-5 shadow-2xs space-y-4">
            <h4 className="font-display font-medium text-xs text-slate-900 tracking-tight flex items-center gap-2">
              <Code className="h-4.5 w-4.5 text-slate-400" />
              Recent Ingestion Audits
            </h4>

            {syncLogs.length === 0 ? (
              <p className="text-[11px] text-slate-400 font-mono italic">No ingestion reports available.</p>
            ) : (
              <div className="space-y-3">
                {syncLogs.slice(-3).map((log) => (
                  <div key={log.id} className="p-3 bg-slate-50 border border-slate-200/40 rounded-xl space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono font-bold text-slate-800 uppercase">
                        {log.source === 'greenhouse' ? 'Greenhouse App' : 'Lever App'}
                      </span>
                      <span className={`text-[9px] font-mono px-1 rounded ${log.status === 'completed' ? 'bg-emerald-50 text-emerald-700 font-bold' : 'bg-rose-50 text-rose-700'}`}>
                        {log.status}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                      <span>Found: {log.jobs_found} | Added: {log.jobs_added}</span>
                      <span>{formatJobClock(log.started_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>

      </div>

    </div>
  );
}

function ResumeStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
      <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-bold">{label}</p>
      <p className="mt-1 text-xs font-display font-bold text-slate-900 truncate">{value || 'Unknown'}</p>
    </div>
  );
}

function Phase2Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
      <p className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-bold">{label}</p>
      <p className="mt-1 text-lg font-display font-black text-slate-900">{value}</p>
    </div>
  );
}

function Phase2List({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 min-w-0 overflow-hidden">
      <h4 className="text-[10px] font-mono uppercase tracking-wider font-black text-slate-600 mb-2">{title}</h4>
      {items.length > 0 ? (
        <div className="space-y-1">
          {items.slice(0, 6).map((item) => (
            <div key={`${title}-${item}`} className="text-[11px] text-slate-600 rounded-lg bg-slate-50 border border-slate-100 px-2 py-1 break-words">
              {item}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-slate-400">No evidence captured yet.</p>
      )}
    </div>
  );
}

function SkillEvidenceList({ title, items, tone }: { title: string; items: string[]; tone: 'match' | 'gap' }) {
  const Icon = tone === 'match' ? CheckCircle : XCircle;
  const colors = tone === 'match'
    ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
    : 'bg-rose-50 text-rose-700 border-rose-100';
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 min-w-0 overflow-hidden">
      <h4 className="text-[10px] font-mono uppercase tracking-wider font-black text-slate-600 mb-2">{title}</h4>
      {items.length > 0 ? (
        <div className="flex flex-wrap gap-1.5 min-w-0">
          {items.slice(0, 10).map((item) => (
            <span key={`${title}-${item}`} className={`inline-flex items-center gap-1 text-[10px] rounded px-1.5 py-0.5 border ${colors} break-words max-w-full`}>
              <Icon className="h-3 w-3" /> {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-slate-400">No evidence captured yet.</p>
      )}
    </div>
  );
}

function AlertDecisionsPanel({ alertStats, phase2Decisions }: { alertStats: any; phase2Decisions?: any }) {
  const decisions = alertStats?.decisions || phase2Decisions || {};
  const dashboardItems = alertStats?.dashboard_items || [];

  const DECISION_META: Record<string, { label: string; color: string; desc: string }> = {
    CALL: { label: 'CALL', color: 'text-amber-700 bg-amber-50 border-amber-200', desc: 'Direct voice workflow decision' },
    EMAIL: { label: 'EMAIL', color: 'text-blue-700 bg-blue-50 border-blue-200', desc: 'Direct email outreach decision' },
    WHATSAPP: { label: 'WHATSAPP', color: 'text-emerald-700 bg-emerald-50 border-emerald-200', desc: 'Direct WhatsApp outreach decision' },
    DASHBOARD_ONLY: { label: 'DASHBOARD', color: 'text-indigo-700 bg-indigo-50 border-indigo-200', desc: 'Visible in dashboard, no outbound action' },
    IGNORE: { label: 'IGNORE', color: 'text-slate-500 bg-slate-50 border-slate-200', desc: 'Suppressed — below action threshold' },
    NONE: { label: 'NONE', color: 'text-slate-400 bg-slate-50 border-slate-100', desc: 'No action required' },
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[10px] font-mono uppercase tracking-wider font-black text-slate-600">Alert Decisions</h4>
      </div>
      <div className="space-y-1">
        {Object.entries(decisions).length === 0 ? (
          <p className="text-[11px] text-slate-400">No alert decisions yet.</p>
        ) : (
          Object.entries(decisions).map(([key, count]) => {
            const meta = DECISION_META[key] || { label: key, color: 'text-slate-500 bg-slate-50 border-slate-200', desc: '' };
            return (
              <div key={key} className="flex items-center justify-between text-[11px] rounded-lg bg-slate-50 border border-slate-100 px-2 py-1">
                <span className={`font-mono font-bold px-1.5 py-0.5 rounded border text-[10px] ${meta.color}`}>
                  {meta.label}
                </span>
                <span className="font-mono font-bold text-slate-800">{String(count)}</span>
              </div>
            );
          })
        )}
      </div>
      {Object.keys(decisions).length > 0 && (
        <p className="text-[9px] text-slate-400 font-mono mt-2 leading-relaxed">
          CALL/EMAIL/WHATSAPP are delivered directly when enabled. DASHBOARD items are visible in-app only.
        </p>
      )}
      {dashboardItems.length > 0 && (
        <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[10px] font-mono uppercase tracking-wider font-black text-slate-500">Latest Dashboard Jobs</p>
            <Link href="/jobs/alerts" className="text-[10px] font-mono rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-slate-600 hover:bg-slate-100">
              Browse All
            </Link>
          </div>
          {dashboardItems.slice(0, 4).map((item: any) => (
            <button
              key={`${item.job_id}-${item.created_at}`}
              type="button"
              className="w-full text-left rounded-lg border border-indigo-100 bg-indigo-50/50 px-2 py-1.5 hover:bg-indigo-50 transition-colors"
              title={item.reason || ''}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-semibold text-slate-800 truncate">{item.title}</span>
                <span className="text-[10px] font-mono font-bold text-indigo-700">{Number(item.match_score || 0).toFixed(1)}%</span>
              </div>
              <div className="text-[10px] text-slate-500 font-mono truncate">
                {item.company}{item.location ? ` · ${item.location}` : ''}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

