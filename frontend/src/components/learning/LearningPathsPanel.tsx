"use client";

import { useEffect, useMemo, useState } from "react";
import { BookOpen, Clock3, ExternalLink, AlertCircle } from "lucide-react";
import { readAuthToken } from "@/lib/auth-session";
import LearningOutcomeControls from "@/components/learning/LearningOutcomeControls";
import type { LearningPath, LearningPathsResponse, LearningProviderHealth, ResourceProvenanceSummary } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

type LearningPathsPanelProps = {
  title?: string;
  subtitle?: string;
  skillSlugs?: string[];
  limit?: number;
  compact?: boolean;
  emptyMessage?: string;
};

function formatHours(hours: number): string {
  if (!Number.isFinite(hours)) return "n/a";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  return `${hours.toFixed(hours >= 10 ? 0 : 1)} hrs`;
}

function formatDate(value?: string | null): string {
  if (!value) return "n/a";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "n/a" : date.toLocaleDateString();
}

function providerStatusClass(status?: string): string {
  switch ((status || "").toLowerCase()) {
    case "success":
    case "configured":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "quota_exceeded":
    case "missing_api_key":
      return "border-amber-200 bg-amber-50 text-amber-700";
    case "seeded_fallback":
    case "skipped":
      return "border-slate-200 bg-slate-50 text-slate-500";
    default:
      return "border-slate-200 bg-slate-50 text-slate-600";
  }
}

function ProvenanceDetails({ summary }: { summary?: ResourceProvenanceSummary | null }) {
  if (!summary) return null;
  return (
    <details className="mt-3 rounded-lg border border-slate-200 bg-white/80 px-3 py-2 text-[11px] text-slate-600">
      <summary className="cursor-pointer list-none font-medium text-slate-700">
        Why this result?
      </summary>
      <div className="mt-2 space-y-1 break-words">
        <p><span className="font-semibold text-slate-900">Reason:</span> {summary.explanation || "Provenance recorded."}</p>
        <p><span className="font-semibold text-slate-900">Score:</span> {Math.round(summary.score_total)} / 100 from {summary.score_formula}</p>
        <p><span className="font-semibold text-slate-900">Confidence:</span> {summary.confidence} | <span className="font-semibold text-slate-900">Status:</span> {summary.status}</p>
        <p><span className="font-semibold text-slate-900">Recorded:</span> {summary.recorded_at ? new Date(summary.recorded_at).toLocaleString() : "n/a"}</p>
        <p><span className="font-semibold text-slate-900">Evidence:</span> {summary.evidence_count} item{summary.evidence_count === 1 ? "" : "s"}</p>
      </div>
    </details>
  );
}

export default function LearningPathsPanel({
  title = "Verified Learning Paths",
  subtitle = "Real free learning resources mapped to current skill gaps.",
  skillSlugs = [],
  limit = 8,
  compact = false,
  emptyMessage = "No verified learning resources are available for the current gaps yet.",
}: LearningPathsPanelProps) {
  const [loading, setLoading] = useState(false);
  const [paths, setPaths] = useState<LearningPath[]>([]);
  const [providerHealth, setProviderHealth] = useState<LearningProviderHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      const token = readAuthToken();
      if (!token) {
        if (mounted) {
          setPaths([]);
          setProviderHealth(null);
          setError("Sign in to view your personalized learning paths.");
        }
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const query = new URLSearchParams();
        query.set("limit", String(limit));
        if (skillSlugs.length > 0) {
          query.set("skills", skillSlugs.map((skill) => skill.trim()).filter(Boolean).join(","));
        }

        const response = await fetch(`${API_BASE}/learning/paths?${query.toString()}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        const payload: LearningPathsResponse | any = await response.json().catch(() => null);
        if (!response.ok) {
          const message = payload?.detail || payload?.error?.message || `HTTP ${response.status}`;
          throw new Error(message);
        }
        if (!mounted) return;
        setPaths(Array.isArray(payload?.paths) ? payload.paths : []);
        setProviderHealth(payload?.provider_health || null);
      } catch (err) {
        if (!mounted) return;
        setPaths([]);
        setError(err instanceof Error ? err.message : "Learning path service unavailable.");
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void load();
    return () => {
      mounted = false;
    };
  }, [limit, skillSlugs]);
  const requestedSkillCount = skillSlugs.length;
  const availableSkillCount = useMemo(
    () => paths.filter((path) => path.resource_status === "available").length,
    [paths],
  );
  const emptyStateMessage =
    requestedSkillCount > 0 && paths.length === 0
      ? "No verified learning resources match the selected skill gaps yet."
      : emptyMessage;
  const providerEntries = Array.isArray(providerHealth?.providers) ? providerHealth.providers : [];
  const providerMessage = providerHealth?.message || null;

  return (
    <div className={`space-y-4 ${compact ? "text-sm" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className={`${compact ? "text-sm" : "text-lg"} font-semibold text-slate-950 flex items-center gap-2`}>
            <BookOpen className="h-4.5 w-4.5 text-indigo-500" />
            {title}
          </h3>
          <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
        </div>
        {providerHealth && (
          <div className="flex flex-wrap items-center justify-end gap-2">
            <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-mono text-slate-600">
              {String(providerHealth.provider_mode || providerHealth.provider || "seeded").replace(/\+/g, " + ")}
            </div>
            <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-mono text-slate-600">
              {providerHealth.trusted_sources} trusted sources
            </div>
            <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-mono text-slate-600">
              {providerHealth.status || "seeded_fallback"}
            </div>
            {providerEntries.slice(0, 4).map((provider) => (
              <div
                key={provider.name}
                className={`rounded-full border px-3 py-1 text-[10px] font-mono ${providerStatusClass(provider.status)}`}
                title={provider.message || provider.last_error || provider.display_name || provider.name}
              >
                {provider.display_name || provider.name} - {provider.status}
              </div>
            ))}
            {requestedSkillCount > 0 && (
              <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-mono text-slate-600">
                {availableSkillCount} / {requestedSkillCount} skill gaps covered
              </div>
            )}
          </div>
        )}
      </div>

      {loading && (
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500">
          Loading verified learning paths...
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800 flex items-start gap-2">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!error && providerMessage && (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
          {providerMessage}
        </div>
      )}

      {!loading && !error && paths.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-6 text-sm text-slate-500">
          {emptyStateMessage}
        </div>
      )}

      <div className="space-y-4">
        {paths.map((path) => (
          <div key={path.skill_slug} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm min-w-0 overflow-hidden">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="space-y-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-sm font-semibold text-slate-950 break-words">{path.skill_name}</h4>
                  <span className="rounded-full bg-indigo-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-indigo-700">
                    {path.priority}
                  </span>
                  <span
                    className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${
                      path.resource_status === "available"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-amber-50 text-amber-700"
                    }`}
                  >
                    {path.resource_status.replace(/_/g, " ")}
                  </span>
                </div>
                <p className="text-xs text-slate-600">{path.reason}</p>
                <p className="text-[11px] text-slate-500">
                  {formatHours(path.estimated_hours)} learning path - Updated {formatDate(path.refreshed_at)}
                  {path.discovery_status ? ` - ${path.discovery_status}` : ""}
                </p>
              </div>
              <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-right min-w-0">
                <p className="text-[10px] uppercase tracking-wider text-slate-400">Gaps matched</p>
                <p className="text-sm font-semibold text-slate-900 break-words">{path.source_job_titles.length} jobs</p>
                <p className="text-[10px] text-slate-500 break-words">{path.resource_count || 0} resources</p>
              </div>
            </div>

            {path.message && (
              <div className="mt-4 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800 break-words">
                {path.message}
              </div>
            )}

            <ProvenanceDetails summary={path.provenance_summary as ResourceProvenanceSummary | null | undefined} />

            <div className="mt-4 grid gap-3">
              {path.steps.map((step) => (
                <div key={`${path.skill_slug}-${step.order_index}`} className="rounded-xl border border-slate-100 bg-slate-50/70 p-3 min-w-0 overflow-hidden">
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between min-w-0">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                          {step.step_type}
                        </span>
                        <p className="text-sm font-semibold text-slate-900 break-words">{step.title}</p>
                      </div>
                      {step.reason && <p className="mt-1 text-xs text-slate-600 break-words">{step.reason}</p>}
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-slate-500">
                      <Clock3 className="h-3.5 w-3.5" />
                      {step.estimated_minutes ? `${step.estimated_minutes} min` : "n/a"}
                    </div>
                  </div>

                  {step.practice_project && (
                    <div className="mt-2 rounded-lg border border-indigo-100 bg-indigo-50/70 px-3 py-2 text-xs text-indigo-900">
                      <span className="font-semibold">Practice project:</span> {step.practice_project}
                    </div>
                  )}

                  <div className="mt-3 space-y-2">
                    {step.resources.length > 0 ? (
                      step.resources.map((resource) => (
                        <div
                          key={resource.id}
                          className="rounded-lg border border-slate-200 bg-white px-3 py-2 transition hover:border-indigo-300 hover:bg-indigo-50/50"
                        >
                          <a href={resource.source_url} target="_blank" rel="noreferrer" className="block">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-slate-950 break-words">{resource.title}</p>
                                <p className="text-[11px] text-slate-500 break-words">
                                  {resource.provider} - {resource.source_type.replace(/_/g, " ")}
                                  {resource.channel_name ? ` - ${resource.channel_name}` : ""}
                                </p>
                              </div>
                              <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                            </div>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wider text-slate-400">
                              <span>{resource.price_status || (resource.is_free ? "free" : "paid_or_unknown")}</span>
                              <span>Verified {formatDate(resource.last_verified_at)}</span>
                              <span>Trust {Math.round((resource.trust_score || 0) * 100)}%</span>
                              {resource.source_domain && <span>{resource.source_domain}</span>}
                            </div>
                          </a>
                          <ProvenanceDetails summary={resource.provenance_summary as ResourceProvenanceSummary | null | undefined} />
                          <LearningOutcomeControls resource={resource} sourceUi="learning_paths_panel" compact={compact} />
                        </div>
                      ))
                    ) : (
                      <div className="rounded-lg border border-dashed border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
                        No verified resource was attached to this step yet.
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {providerEntries.length > 0 && (
              <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50/70 px-3 py-3">
                <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wider text-slate-400">
                  <span>Discovery providers</span>
                  <span>{providerEntries.length} sources</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {providerEntries.map((provider) => (
                    <span
                      key={`${path.skill_slug}-${provider.name}`}
                      className={`rounded-full border px-3 py-1 text-[11px] ${providerStatusClass(provider.status)}`}
                      title={provider.message || provider.last_error || provider.allowed_domains?.join(", ") || provider.display_name || provider.name}
                    >
                      {provider.display_name || provider.name}
                      {provider.last_result_count !== undefined && provider.last_result_count !== null
                        ? ` - ${provider.last_result_count}`
                        : ""}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {path.source_domains?.length ? (
              <div className="mt-4 flex flex-wrap gap-2 text-[10px] uppercase tracking-wider text-slate-400">
                {path.source_domains.map((domain) => (
                  <span key={`${path.skill_slug}-${domain}`} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1">
                    {domain}
                  </span>
                ))}
              </div>
            ) : null}

            <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-slate-500">
              {path.source_job_titles.slice(0, 4).map((title) => (
                <span key={title} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1">
                  {title}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
