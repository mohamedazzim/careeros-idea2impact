"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, BookOpen, ExternalLink, RefreshCw, Wrench, BadgeCheck, MessageSquareText } from "lucide-react";
import { readAuthToken } from "@/lib/auth-session";
import LearningOutcomeControls from "@/components/learning/LearningOutcomeControls";
import type { LearningGapActionsResponse, LearningResource, ResourceProvenanceSummary } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

type GapActionsPanelProps = {
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

function renderResourceLabel(resource: LearningResource): string {
  const parts = [resource.provider, resource.source_type.replace(/_/g, " ")];
  if (resource.channel_name) {
    parts.push(resource.channel_name);
  }
  return parts.filter(Boolean).join(" | ");
}

function ProvenanceDetails({ summary }: { summary?: ResourceProvenanceSummary | null }) {
  if (!summary) return null;
  return (
    <details className="mt-2 rounded-lg border border-slate-200 bg-white/80 px-3 py-2 text-[11px] text-slate-600">
      <summary className="cursor-pointer list-none font-medium text-slate-700">
        Why this result?
      </summary>
      <div className="mt-2 space-y-1 break-words">
        <p><span className="font-semibold text-slate-900">Reason:</span> {summary.explanation || "Provenance recorded."}</p>
        <p><span className="font-semibold text-slate-900">Score:</span> {Math.round(summary.score_total)} / 100 from {summary.score_formula}</p>
        <p><span className="font-semibold text-slate-900">Confidence:</span> {summary.confidence} | <span className="font-semibold text-slate-900">Status:</span> {summary.status}</p>
        <p><span className="font-semibold text-slate-900">Recorded:</span> {summary.recorded_at ? new Date(summary.recorded_at).toLocaleString() : "n/a"}</p>
      </div>
    </details>
  );
}

export default function GapActionsPanel({
  token,
  jobId,
  jobTitle,
  company,
  skillSlugs = [],
  compact = false,
  emptyMessage = "No proof actions are available for the current gaps yet.",
}: GapActionsPanelProps) {
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
  const [payload, setPayload] = useState<LearningGapActionsResponse | null>(null);

  const load = useCallback(async (forceRefresh = false) => {
    if (!authToken) {
      setPayload(null);
      setError("Sign in to view proof actions for your skill gaps.");
      return;
    }
    if (!normalizedSkills.length && resolvedJobId === null) {
      setPayload(null);
      setError(emptyMessage);
      return;
    }

    forceRefresh ? setRefreshing(true) : setLoading(true);
    setError(null);
    try {
      const commonBody = {
        skills: normalizedSkills,
        job_id: resolvedJobId,
      };
      const response = forceRefresh
        ? await fetch(`${API_BASE}/learning/gap-actions/refresh`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${authToken}`,
            },
            body: JSON.stringify(commonBody),
          })
        : await fetch(
            `${API_BASE}/learning/gap-actions?${new URLSearchParams({
              skills: normalizedSkills.join(","),
              ...(resolvedJobId !== null ? { job_id: String(resolvedJobId) } : {}),
            }).toString()}`,
            {
              headers: {
                Authorization: `Bearer ${authToken}`,
              },
            },
          );

      const body: LearningGapActionsResponse | any = await response.json().catch(() => null);
      if (!response.ok || body?.status === "error") {
        const message = body?.detail || body?.error?.message || body?.message || `HTTP ${response.status}`;
        throw new Error(message);
      }
      setPayload(body as LearningGapActionsResponse);
    } catch (err) {
      setPayload(null);
      setError(err instanceof Error ? err.message : "Gap-action service unavailable.");
    } finally {
      forceRefresh ? setRefreshing(false) : setLoading(false);
    }
  }, [authToken, emptyMessage, normalizedSkills, resolvedJobId]);

  useEffect(() => {
    void load(false);
  }, [load]);

  const actions = payload?.actions || [];
  const hasActions = actions.length > 0;

  return (
    <div className={`space-y-4 ${compact ? "text-sm" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className={`${compact ? "text-sm" : "text-lg"} font-semibold text-slate-950 flex items-center gap-2`}>
            <Wrench className="h-4.5 w-4.5 text-indigo-500" />
            Close These Gaps With Proof
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            Learn from verified resources, build a proof project, and turn the result into resume and interview evidence{jobTitle ? ` for ${jobTitle}` : ""}{company ? ` at ${company}` : ""}.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load(true)}
          disabled={loading || refreshing || !authToken}
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-700 transition hover:border-indigo-300 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading || refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing" : payload?.cached ? "Refresh ideas" : "Reload"}
        </button>
      </div>

      {payload?.provider_health && (
        <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-mono text-slate-600">
          {payload.provider_health.provider || "seeded"} | {payload.source_status.replace(/_/g, " ")}
        </div>
      )}

      {loading && (
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500">
          Loading proof actions...
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!loading && !error && !hasActions && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-6 text-sm text-slate-500">
          {emptyMessage}
        </div>
      )}

      <div className="space-y-4">
        {actions.map((action) => (
          <div key={action.skill_slug} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm min-w-0 overflow-hidden">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="space-y-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-sm font-semibold text-slate-950 break-words">{action.skill_name}</h4>
                  <span className="rounded-full bg-indigo-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-indigo-700">
                    {titleCase(action.priority)}
                  </span>
                  <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${
                    action.resource_status === "available"
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-amber-50 text-amber-700"
                  }`}>
                    {action.resource_status.replace(/_/g, " ")}
                  </span>
                  <span className="rounded-full bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                    {action.source_status.replace(/_/g, " ")}
                  </span>
                </div>
                <p className="text-xs text-slate-600">{action.reason}</p>
                <p className="text-[11px] text-slate-500">
                  {action.estimated_hours} hrs estimated | {action.count} gap signal{action.count === 1 ? "" : "s"}
                </p>
              </div>
              <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-right min-w-0">
                <p className="text-[10px] uppercase tracking-wider text-slate-400">Learning resources</p>
                <p className="text-sm font-semibold text-slate-900 break-words">{action.resource_count} verified</p>
              </div>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-3 min-w-0 overflow-hidden">
                <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-700 flex items-center gap-1.5">
                  <BookOpen className="h-3.5 w-3.5" />
                  Learn
                </p>
                <div className="mt-2 space-y-2">
                  {action.source_resources.length > 0 ? (
                    action.source_resources.map((resource) => (
                      <div
                        key={resource.id}
                        className="rounded-lg border border-emerald-100 bg-white px-3 py-2 transition hover:border-emerald-300 hover:bg-emerald-50/70"
                      >
                        <a href={resource.source_url} target="_blank" rel="noreferrer" className="block">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-slate-950 break-words">{resource.title}</p>
                              <p className="text-[11px] text-slate-500 break-words">{renderResourceLabel(resource)}</p>
                            </div>
                            <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                          </div>
                        </a>
                        <ProvenanceDetails summary={resource.provenance_summary as ResourceProvenanceSummary | null | undefined} />
                        <LearningOutcomeControls resource={resource} jobId={resolvedJobId} sourceUi="gap_actions_panel" compact={compact} />
                      </div>
                    ))
                  ) : (
                    <p className="rounded-lg border border-dashed border-emerald-200 bg-white px-3 py-2 text-xs text-emerald-800">
                      No verified learning resource is available yet. Use the official docs for this skill and keep the project small.
                    </p>
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3">
                <p className="text-[10px] font-bold uppercase tracking-widest text-indigo-700 flex items-center gap-1.5">
                  <Wrench className="h-3.5 w-3.5" />
                  Build
                </p>
                {action.project_ideas.map((idea) => (
                  <div key={`${action.skill_slug}-${idea.title}`} className="mt-2 rounded-lg border border-indigo-100 bg-white p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-slate-950">{idea.title}</p>
                      <span className="rounded-full bg-slate-900 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-white">
                        {idea.difficulty}
                      </span>
                      <span className="rounded-full bg-indigo-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-indigo-700">
                        {idea.proof_type.replace(/_/g, " ")}
                      </span>
                      <span className="rounded-full bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                        {idea.estimated_hours} hrs
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-slate-600">
                      {idea.source_status.replace(/_/g, " ")}
                    </p>
                    <ol className="mt-2 space-y-1.5 pl-4 text-xs text-slate-700 list-decimal">
                      {idea.steps.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                    <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50/70 p-2">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">README outline</p>
                      <ul className="mt-1 space-y-1 text-xs text-slate-600">
                        {idea.github_readme_outline.map((item) => (
                          <li key={item}>- {item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
                <ProvenanceDetails summary={action.provenance_summary as ResourceProvenanceSummary | null | undefined} />
              </div>

              <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3">
                <p className="text-[10px] font-bold uppercase tracking-widest text-amber-700 flex items-center gap-1.5">
                  <BadgeCheck className="h-3.5 w-3.5" />
                  Prove
                </p>
                <div className="mt-2 space-y-2">
                  <p className="rounded-lg border border-amber-100 bg-white px-3 py-2 text-xs text-amber-900">
                    {action.resume_proof.before_gap}
                  </p>
                  <div className="rounded-lg border border-amber-100 bg-white px-3 py-2">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Resume bullets</p>
                    <ul className="mt-1 space-y-1 text-xs text-slate-700">
                      {action.resume_proof.suggested_bullets.map((bullet) => (
                        <li key={bullet}>- {bullet}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-lg border border-amber-100 bg-white px-3 py-2">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">LinkedIn bullets</p>
                    <ul className="mt-1 space-y-1 text-xs text-slate-700">
                      {action.resume_proof.linkedin_bullets.map((bullet) => (
                        <li key={bullet}>- {bullet}</li>
                      ))}
                    </ul>
                  </div>
                  <p className="rounded-lg border border-amber-100 bg-white px-3 py-2 text-xs text-slate-700">
                    {action.resume_proof.portfolio_description}
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-sky-100 bg-sky-50/50 p-3">
                <p className="text-[10px] font-bold uppercase tracking-widest text-sky-700 flex items-center gap-1.5">
                  <MessageSquareText className="h-3.5 w-3.5" />
                  Interview
                </p>
                <div className="mt-2 space-y-2">
                  <div className="rounded-lg border border-sky-100 bg-white px-3 py-2">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Talking points</p>
                    <ul className="mt-1 space-y-1 text-xs text-slate-700">
                      {action.interview_proof.talking_points.map((point) => (
                        <li key={point}>- {point}</li>
                      ))}
                    </ul>
                  </div>
                  <p className="rounded-lg border border-sky-100 bg-white px-3 py-2 text-xs text-slate-700">
                    {action.interview_proof.sample_answer}
                  </p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

