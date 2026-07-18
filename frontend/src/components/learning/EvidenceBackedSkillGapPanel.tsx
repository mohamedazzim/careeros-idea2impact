"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, BadgeCheck, Brain, RefreshCw, Sparkles } from "lucide-react";
import { readAuthToken } from "@/lib/auth-session";
import type { SkillGapAnalysisResponse, SkillGapFinding } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

type EvidenceBackedSkillGapPanelProps = {
  token?: string | null;
  jobId?: number | string | null;
  jobTitle?: string | null;
  company?: string | null;
  skillSlugs?: string[];
  compact?: boolean;
  emptyMessage?: string;
};

function normalizeSkills(skillSlugs: string[] | undefined): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  (skillSlugs || []).forEach((skill) => {
    const normalized = skill.trim();
    if (!normalized) return;
    const slug = normalized.toLowerCase();
    if (seen.has(slug)) return;
    seen.add(slug);
    result.push(normalized);
  });
  return result;
}

function titleCase(text: string): string {
  return text
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function statusTone(status: string): string {
  switch (status) {
    case "validated":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "evidenced":
      return "bg-cyan-50 text-cyan-700 border-cyan-200";
    case "learning":
      return "bg-indigo-50 text-indigo-700 border-indigo-200";
    case "missing":
      return "bg-amber-50 text-amber-700 border-amber-200";
    default:
      return "bg-slate-50 text-slate-600 border-slate-200";
  }
}

function confidenceTone(confidence: string): string {
  switch (confidence) {
    case "high":
      return "text-emerald-700";
    case "medium":
      return "text-amber-700";
    default:
      return "text-slate-500";
  }
}

function EvidenceList({ finding }: { finding: SkillGapFinding }) {
  if (!finding.evidence.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5 min-w-0">
      {finding.evidence.slice(0, 4).map((item) => (
        <span
          key={item.evidence_uid}
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] font-medium break-words max-w-full ${statusTone(item.supports_status)}`}
          title={item.quote_or_snippet || item.evidence_type}
        >
          {item.supports_status === "validated" ? <BadgeCheck className="h-3 w-3" /> : <Sparkles className="h-3 w-3" />}
          {item.evidence_type.replace(/_/g, " ")}
        </span>
      ))}
    </div>
  );
}

export default function EvidenceBackedSkillGapPanel({
  token,
  jobId,
  jobTitle,
  company,
  skillSlugs = [],
  compact = false,
  emptyMessage = "No evidence-backed skill gap analysis is available for this job yet.",
}: EvidenceBackedSkillGapPanelProps) {
  const authToken = token || readAuthToken();
  const normalizedSkills = useMemo(() => normalizeSkills(skillSlugs), [skillSlugs]);
  const resolvedJobId = useMemo(() => {
    if (jobId === null || jobId === undefined || jobId === "") {
      return null;
    }
    const numeric = typeof jobId === "string" ? Number(jobId) : jobId;
    return Number.isFinite(numeric) ? numeric : null;
  }, [jobId]);

  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<SkillGapAnalysisResponse | null>(null);

  const load = useCallback(async (forceRefresh = false) => {
    if (!authToken) {
      setPayload(null);
      setError("Sign in to review evidence-backed skill gaps.");
      return;
    }
    if (resolvedJobId === null) {
      setPayload(null);
      setError(emptyMessage);
      return;
    }

    forceRefresh ? setRefreshing(true) : setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/skill-gaps/analyze?limit=${Math.max(6, normalizedSkills.length || 6)}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          source_scope: "job",
          job_id: resolvedJobId,
        }),
      });
      const body: SkillGapAnalysisResponse | any = await response.json().catch(() => null);
      if (!response.ok || body?.status === "error") {
        const message = body?.detail?.message || body?.detail || body?.error?.message || body?.message || `HTTP ${response.status}`;
        throw new Error(message);
      }
      setPayload(body as SkillGapAnalysisResponse);
    } catch (err) {
      setPayload(null);
      setError(err instanceof Error ? err.message : "Evidence-backed skill gap analysis unavailable.");
    } finally {
      forceRefresh ? setRefreshing(false) : setLoading(false);
    }
  }, [authToken, emptyMessage, normalizedSkills.length, resolvedJobId]);

  useEffect(() => {
    void load(false);
  }, [load]);

  const findings = useMemo(() => {
    const items = payload?.findings || [];
    if (!normalizedSkills.length) return items;
    const wanted = new Set(normalizedSkills.map((skill) => skill.toLowerCase()));
    return items.filter((finding) => wanted.has(finding.skill_slug.toLowerCase()) || wanted.has(finding.skill_name.toLowerCase()));
  }, [normalizedSkills, payload?.findings]);

  const summary = payload?.summary;

  return (
    <div className={`space-y-4 ${compact ? "text-sm" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className={`${compact ? "text-sm" : "text-lg"} font-semibold text-slate-950 flex items-center gap-2`}>
            <Brain className="h-4.5 w-4.5 text-indigo-500" />
            Evidence-Backed Skill Gaps
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            Real stored evidence from resumes, learning sessions, outcomes, provenance, and the skill graph{jobTitle ? ` for ${jobTitle}` : ""}{company ? ` at ${company}` : ""}.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load(true)}
          disabled={loading || refreshing || !authToken}
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-700 transition hover:border-indigo-300 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading || refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing" : payload ? "Re-analyze" : "Analyze"}
        </button>
      </div>

      {summary && (
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-mono text-slate-600">
            {summary.required_skill_count} skills
          </span>
          <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[10px] font-mono text-amber-700">
            {summary.missing_skill_count} missing
          </span>
          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[10px] font-mono text-indigo-700">
            {summary.learning_skill_count} learning
          </span>
          <span className="rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-[10px] font-mono text-cyan-700">
            {summary.evidenced_skill_count} evidenced
          </span>
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[10px] font-mono text-emerald-700">
            {summary.validated_skill_count} validated
          </span>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-mono text-slate-600">
            {summary.insufficient_data_count} insufficient
          </span>
        </div>
      )}

      {loading && (
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500">
          Analyzing stored evidence...
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!loading && !error && findings.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-6 text-sm text-slate-500">
          {emptyMessage}
        </div>
      )}

      <div className="space-y-4">
        {findings.map((finding) => (
          <div key={finding.finding_uid} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm min-w-0 overflow-hidden">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="space-y-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-sm font-semibold text-slate-950 break-words">{finding.skill_name}</h4>
                  <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(finding.gap_status)}`}>
                    {finding.gap_status.replace(/_/g, " ")}
                  </span>
                  <span className="rounded-full bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                    {titleCase(finding.required_by_type)}
                  </span>
                </div>
                <p className="text-xs text-slate-600 break-words">{finding.reason_summary}</p>
                {finding.recommendation_summary && (
                  <p className="text-[11px] text-indigo-700 break-words">{finding.recommendation_summary}</p>
                )}
              </div>
              <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-right min-w-0">
                <p className="text-[10px] uppercase tracking-wider text-slate-400">Confidence</p>
                <p className={`text-sm font-semibold break-words ${confidenceTone(finding.confidence)}`}>{finding.confidence}</p>
                <p className="text-[10px] text-slate-500 break-words">{finding.evidence_count} evidence item{finding.evidence_count === 1 ? "" : "s"}</p>
              </div>
            </div>

            {finding.missing_evidence.length > 0 && (
              <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-[11px] text-amber-800 break-words">
                No strong evidence was stored for this skill yet. The engine keeps the gap honest instead of promoting a fake score.
              </div>
            )}

            <div className="mt-3">
              <EvidenceList finding={finding} />
            </div>

            {finding.calculation_metadata_json?.evidence_types && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {(finding.calculation_metadata_json.evidence_types as string[]).slice(0, 5).map((type) => (
                  <span key={`${finding.finding_uid}-${type}`} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-mono text-slate-600">
                    {type.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
