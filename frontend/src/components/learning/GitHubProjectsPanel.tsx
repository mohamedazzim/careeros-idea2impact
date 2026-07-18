"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, ExternalLink, Github, RefreshCw, Sparkles, GitPullRequest } from "lucide-react";
import { readAuthToken } from "@/lib/auth-session";
import type { GitHubProjectsResponse } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

type GitHubProjectsPanelProps = {
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

function renderRepoMeta(repo: GitHubProjectsResponse["skills"][number]["repositories"][number]): string {
  const parts = [];
  if (repo.language) parts.push(repo.language);
  parts.push(`${repo.stargazers_count} stars`);
  if (repo.is_template) parts.push("template");
  if (repo.archived) parts.push("archived");
  return parts.join(" | ");
}

function ProvenanceDetails({ summary }: { summary?: Record<string, any> | null }) {
  if (!summary) return null;
  return (
    <details className="mt-3 rounded-lg border border-slate-200 bg-white/80 px-3 py-2 text-[11px] text-slate-600">
      <summary className="cursor-pointer list-none font-medium text-slate-700">
        Why this result?
      </summary>
      <div className="mt-2 space-y-1 break-words">
        <p><span className="font-semibold text-slate-900">Reason:</span> {String(summary.explanation || "Provenance recorded.")}</p>
        {"score_total" in summary ? <p><span className="font-semibold text-slate-900">Score:</span> {Math.round(Number(summary.score_total || 0))} / 100</p> : null}
        {"confidence" in summary ? <p><span className="font-semibold text-slate-900">Confidence:</span> {String(summary.confidence || "n/a")}</p> : null}
        {"recorded_at" in summary ? <p><span className="font-semibold text-slate-900">Recorded:</span> {summary.recorded_at ? new Date(String(summary.recorded_at)).toLocaleString() : "n/a"}</p> : null}
      </div>
    </details>
  );
}

export default function GitHubProjectsPanel({
  token,
  jobId,
  jobTitle,
  company,
  skillSlugs = [],
  compact = false,
  emptyMessage = "No GitHub project recommendations are available for the current gaps yet.",
}: GitHubProjectsPanelProps) {
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
  const [payload, setPayload] = useState<GitHubProjectsResponse | null>(null);

  const load = useCallback(async (forceRefresh = false) => {
    if (!authToken) {
      setPayload(null);
      setError("Sign in to view GitHub projects for your skill gaps.");
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
        ? await fetch(`${API_BASE}/learning/github-projects/refresh`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${authToken}`,
            },
            body: JSON.stringify(commonBody),
          })
        : await fetch(
            `${API_BASE}/learning/github-projects?${new URLSearchParams({
              skills: normalizedSkills.join(","),
              ...(resolvedJobId !== null ? { job_id: String(resolvedJobId) } : {}),
            }).toString()}`,
            {
              headers: {
                Authorization: `Bearer ${authToken}`,
              },
            },
          );

      const body: GitHubProjectsResponse | any = await response.json().catch(() => null);
      if (!response.ok || body?.status === "error") {
        const message = body?.detail || body?.error?.message || body?.message || `HTTP ${response.status}`;
        throw new Error(message);
      }
      setPayload(body as GitHubProjectsResponse);
    } catch (err) {
      setPayload(null);
      setError(err instanceof Error ? err.message : "GitHub project discovery unavailable.");
    } finally {
      forceRefresh ? setRefreshing(false) : setLoading(false);
    }
  }, [authToken, emptyMessage, normalizedSkills, resolvedJobId]);

  useEffect(() => {
    void load(false);
  }, [load]);

  const skills = payload?.skills || [];
  const hasSkills = skills.length > 0;

  return (
    <div className={`space-y-4 ${compact ? "text-sm" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className={`${compact ? "text-sm" : "text-lg"} font-semibold text-slate-950 flex items-center gap-2`}>
            <Github className="h-4.5 w-4.5 text-slate-900" />
            GitHub Projects for Practice
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            Real GitHub repositories, templates, and beginner-friendly issues mapped to the current gaps{jobTitle ? ` for ${jobTitle}` : ""}{company ? ` at ${company}` : ""}.
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
          {payload.provider_health.provider || "github"} | {payload.source_status.replace(/_/g, " ")}
        </div>
      )}

      {loading && (
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500">
          Loading GitHub repositories and issues...
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!loading && !error && !hasSkills && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-6 text-sm text-slate-500">
          {emptyMessage}
        </div>
      )}

      <div className="space-y-4">
        {skills.map((skill) => (
          <div key={skill.skill_slug} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm min-w-0 overflow-hidden">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="space-y-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-sm font-semibold text-slate-950 break-words">{skill.skill_name}</h4>
                  <span className="rounded-full bg-indigo-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-indigo-700">
                    {titleCase(skill.priority)}
                  </span>
                  <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${
                    skill.source_status === "available"
                      ? "bg-emerald-50 text-emerald-700"
                      : skill.source_status === "rate_limited"
                        ? "bg-rose-50 text-rose-700"
                        : "bg-amber-50 text-amber-700"
                  }`}>
                    {skill.source_status.replace(/_/g, " ")}
                  </span>
                </div>
                <p className="text-xs text-slate-600">{skill.reason}</p>
                <p className="text-[11px] text-slate-500">
                  {skill.estimated_hours} hrs estimated | {skill.count} gap signal{skill.count === 1 ? "" : "s"}
                </p>
              </div>
              <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-right min-w-0">
                <p className="text-[10px] uppercase tracking-wider text-slate-400">GitHub results</p>
                <p className="text-sm font-semibold text-slate-900">{skill.repository_count} repos · {skill.issue_count} issues</p>
              </div>
            </div>
            <ProvenanceDetails summary={skill.provenance_summary} />

            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3 min-w-0 overflow-hidden">
                <p className="text-[10px] font-bold uppercase tracking-widest text-indigo-700 flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5" />
                  Build
                </p>
                <div className="mt-2 space-y-2">
                  {skill.templates.length > 0 || skill.repositories.length > 0 ? (
                    <>
                      {skill.templates.map((repo) => (
                        <div
                          key={`${skill.skill_slug}-template-${repo.full_name}`}
                          className="block rounded-lg border border-indigo-100 bg-white px-3 py-2 transition hover:border-indigo-300 hover:bg-indigo-50/70 min-w-0 overflow-hidden"
                        >
                          <a href={repo.html_url} target="_blank" rel="noreferrer" className="block">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-slate-950 break-words">{repo.full_name}</p>
                                <p className="text-[11px] text-slate-500 break-words">{renderRepoMeta(repo)}</p>
                                {repo.description ? <p className="mt-1 text-[11px] text-slate-600 break-words">{repo.description}</p> : null}
                              </div>
                              <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                            </div>
                          </a>
                        </div>
                      ))}
                      {skill.repositories
                        .filter((repo) => !skill.templates.some((templateRepo) => templateRepo.full_name === repo.full_name))
                        .map((repo) => (
                          <div
                            key={`${skill.skill_slug}-repo-${repo.full_name}`}
                            className="block rounded-lg border border-indigo-100 bg-white px-3 py-2 transition hover:border-indigo-300 hover:bg-indigo-50/70 min-w-0 overflow-hidden"
                          >
                            <a href={repo.html_url} target="_blank" rel="noreferrer" className="block">
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <p className="text-sm font-medium text-slate-950 break-words">{repo.full_name}</p>
                                  <p className="text-[11px] text-slate-500 break-words">{renderRepoMeta(repo)}</p>
                                  {repo.description ? <p className="mt-1 text-[11px] text-slate-600 break-words">{repo.description}</p> : null}
                                </div>
                                <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                              </div>
                            </a>
                          </div>
                        ))}
                    </>
                  ) : (
                    <p className="rounded-lg border border-dashed border-indigo-200 bg-white px-3 py-2 text-xs text-indigo-800">
                      No GitHub repository was found yet for this skill. Try a refresh or add a token for better coverage.
                    </p>
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-3 min-w-0 overflow-hidden">
                <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-700 flex items-center gap-1.5">
                  <GitPullRequest className="h-3.5 w-3.5" />
                  Contribute
                </p>
                <div className="mt-2 space-y-2">
                  {skill.good_first_issues.length > 0 ? (
                    skill.good_first_issues.map((issue) => (
                      <a
                        key={`${skill.skill_slug}-issue-${issue.html_url}`}
                        href={issue.html_url}
                        target="_blank"
                        rel="noreferrer"
                        className="block rounded-lg border border-emerald-100 bg-white px-3 py-2 transition hover:border-emerald-300 hover:bg-emerald-50/70"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-slate-950 break-words">{issue.title}</p>
                            <p className="text-[11px] text-slate-500 break-words">{issue.repository_full_name} | {issue.label_names.join(", ") || "good first issue"}</p>
                            <p className="mt-1 text-[11px] text-slate-600 break-words">Score {issue.score.toFixed(1)}</p>
                          </div>
                          <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                        </div>
                      </a>
                    ))
                  ) : (
                    <p className="rounded-lg border border-dashed border-emerald-200 bg-white px-3 py-2 text-xs text-emerald-800">
                      No beginner-friendly issues were found for this skill yet.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
