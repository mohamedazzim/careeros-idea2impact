"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, CheckCircle, FileText, Target, TrendingUp } from "lucide-react";
import type React from "react";
import type { AlignmentExplainability } from "@/types";

const apiBaseUrl =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) ||
  "http://localhost:8000/api/v1";

interface AlignmentReportPayload {
  runId: string;
  doc_id: string;
  filename: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  job_description: string;
  results: {
    overall_score?: number;
    resume_quality_score?: number;
    alignment_explainability?: AlignmentExplainability;
  };
}

export default function AlignmentReportPage() {
  const params = useParams<{ runId: string }>();
  const [report, setReport] = useState<AlignmentReportPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = window.localStorage.getItem("careeros_token");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    fetch(`${apiBaseUrl}/knowledge/alignment-report/${params.runId}`, { headers })
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || "Unable to load alignment report.");
        }
        return response.json();
      })
      .then(setReport)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [params.runId]);

  const explainability = report?.results?.alignment_explainability;
  const matchedProjects = useMemo(
    () => explainability?.components.find((component) => component.key === "projects")?.matched || [],
    [explainability],
  );
  const missingRequirements = useMemo(
    () => explainability?.missing_items || [],
    [explainability],
  );

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-50 p-6 text-slate-900">
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Loading alignment report...</div>
      </main>
    );
  }

  if (error || !report || !explainability) {
    return (
      <main className="min-h-screen bg-slate-50 p-6 text-slate-900">
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
          {error || "Alignment report was not found for this run."}
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 p-6 text-slate-900">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-indigo-500">Workflow Alignment Report</p>
            <h1 className="mt-2 text-3xl font-display font-black text-slate-950">{explainability.overall_score}% Match</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              Run {report.runId} for {report.filename}. Formula: {explainability.formula}.
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-right shadow-xs">
            <p className="text-xs uppercase tracking-wider text-slate-400">Final Recommendation</p>
            <p className="mt-1 max-w-xl text-sm font-semibold text-slate-800">{explainability.final_recommendation}</p>
          </div>
        </header>

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <SummaryPanel
            icon={<FileText className="h-5 w-5 text-indigo-500" />}
            title="Resume Overview"
            items={Object.values(explainability.resume_overview)}
          />
          <SummaryPanel
            icon={<Target className="h-5 w-5 text-indigo-500" />}
            title="JD Overview"
            items={Object.entries(explainability.jd_overview).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`)}
          />
          <SummaryPanel
            icon={<TrendingUp className="h-5 w-5 text-indigo-500" />}
            title="Score Scenarios"
            items={[
              `Add missing skills: ${explainability.score_scenarios?.if_missing_skills_added ?? "n/a"}%`,
              `Add relocation evidence: ${explainability.score_scenarios?.if_relocation_added ?? "n/a"}%`,
              `Add TensorFlow/PyTorch projects: ${explainability.score_scenarios?.if_tensorflow_pytorch_projects_added ?? "n/a"}%`,
            ]}
          />
        </section>

        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <EvidenceList title="Matched Skills" positive items={explainability.matched_skills} />
          <EvidenceList title="Missing Skills" items={explainability.missing_skills} />
          <EvidenceList title="Matched Projects" positive items={matchedProjects} />
          <EvidenceList title="Missing Requirements" items={missingRequirements} />
        </section>

        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="font-display text-lg font-bold text-slate-950">Scoring Breakdown</h2>
            <p className="mt-1 text-xs text-slate-500">Each contribution is `component score * weight / 100`.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3">Component</th>
                  <th className="px-5 py-3">Score</th>
                  <th className="px-5 py-3">Weight</th>
                  <th className="px-5 py-3">Contribution</th>
                  <th className="px-5 py-3">Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {explainability.components.map((component) => (
                  <tr key={component.key}>
                    <td className="px-5 py-4 font-semibold text-slate-900">{component.label}</td>
                    <td className="px-5 py-4 font-mono">{component.score}%</td>
                    <td className="px-5 py-4 font-mono">{component.weight}%</td>
                    <td className="px-5 py-4 font-mono font-bold">{component.contribution}/{component.max_contribution}</td>
                    <td className="px-5 py-4 text-xs text-slate-600">
                      {[...component.matched, ...component.missing].slice(0, 5).join("; ") || "No explicit evidence."}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <h2 className="font-display text-lg font-bold text-slate-950">Improvement Suggestions</h2>
          <ul className="mt-4 grid gap-3 text-sm text-slate-700 md:grid-cols-2">
            {explainability.improvement_suggestions.map((suggestion) => (
              <li key={suggestion} className="flex items-start gap-2 rounded-lg bg-slate-50 p-3">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                <span>{suggestion}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}

function SummaryPanel({ icon, title, items }: { icon: React.ReactNode; title: string; items: string[] }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="font-display text-sm font-bold text-slate-950">{title}</h2>
      </div>
      <ul className="mt-4 space-y-2 text-sm text-slate-600">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function EvidenceList({ title, items, positive = false }: { title: string; items: string[]; positive?: boolean }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
      <h2 className="font-display text-sm font-bold text-slate-950">{title}</h2>
      <div className="mt-4 flex flex-wrap gap-2">
        {items.length === 0 ? (
          <span className="text-sm text-slate-500">No items found.</span>
        ) : (
          items.map((item) => (
            <span
              key={item}
              className={`inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-semibold ${
                positive
                  ? "border-emerald-100 bg-emerald-50 text-emerald-700"
                  : "border-rose-100 bg-rose-50 text-rose-700"
              }`}
            >
              {positive ? <CheckCircle className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
              {item}
            </span>
          ))
        )}
      </div>
    </section>
  );
}
