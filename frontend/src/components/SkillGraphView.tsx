"use client";

import { useCallback, useEffect, useMemo, useState, type ElementType, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BrainCircuit,
  Database,
  GitBranch,
  Layers,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { formatDateTimeLocal } from "@/lib/datetime";
import { useCareerOS } from "@/hooks/useCareerOS";
import type {
  SkillGraphDetailResponse,
  SkillGraphHealthResponse,
  SkillGraphImportResponse,
  SkillGraphImportRun,
  SkillGraphNode,
  SkillGraphNodeListResponse,
  SkillGraphStateListResponse,
  SkillGraphSummaryResponse,
  SkillGraphUserState,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function authHeaders(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function scoreTone(status: string): string {
  switch (status) {
    case "validated":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
    case "growing":
      return "border-cyan-500/30 bg-cyan-500/10 text-cyan-200";
    case "observed":
      return "border-amber-500/30 bg-amber-500/10 text-amber-200";
    default:
      return "border-slate-700 bg-slate-900 text-slate-300";
  }
}

function miniPercent(score: number): string {
  return `${Math.round((Number.isFinite(score) ? score : 0) * 100)}%`;
}

export default function SkillGraphView() {
  const router = useRouter();
  const { token, userRole } = useCareerOS();
  const isAdmin = userRole === "Admin";

  const [mounted, setMounted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedSlug, setSelectedSlug] = useState<string>("");

  const [health, setHealth] = useState<SkillGraphHealthResponse | null>(null);
  const [summary, setSummary] = useState<SkillGraphSummaryResponse | null>(null);
  const [nodes, setNodes] = useState<SkillGraphNode[]>([]);
  const [states, setStates] = useState<SkillGraphUserState[]>([]);
  const [runs, setRuns] = useState<SkillGraphImportRun[]>([]);
  const [detail, setDetail] = useState<SkillGraphDetailResponse | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const signedIn = Boolean(token);
  const selectedNode = useMemo(
    () => nodes.find((node) => node.skill_slug === selectedSlug) || detail?.node || null,
    [detail?.node, nodes, selectedSlug],
  );

  const loadDetail = useCallback(async (slug: string) => {
    if (!token || !slug) return;
    const response = await fetch(`${API_BASE}/skill-graph/nodes/${encodeURIComponent(slug)}`, {
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(token),
      },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `Failed to load ${slug}.`);
    }
    const payload = (await response.json()) as SkillGraphDetailResponse;
    setDetail(payload);
  }, [token]);

  const loadOverview = useCallback(async (skillSearch = "") => {
    if (!token) return;
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (skillSearch.trim()) {
        params.set("search", skillSearch.trim());
      }

      const [healthRes, summaryRes, nodesRes, statesRes, runsRes] = await Promise.all([
        fetch(`${API_BASE}/skill-graph/health`, {
          headers: { "Content-Type": "application/json", ...authHeaders(token) },
        }),
        fetch(`${API_BASE}/skill-graph/summary?limit=12`, {
          headers: { "Content-Type": "application/json", ...authHeaders(token) },
        }),
        fetch(`${API_BASE}/skill-graph/nodes?limit=30${params.toString() ? `&${params.toString()}` : ""}`, {
          headers: { "Content-Type": "application/json", ...authHeaders(token) },
        }),
        fetch(`${API_BASE}/skill-graph/states?limit=20`, {
          headers: { "Content-Type": "application/json", ...authHeaders(token) },
        }),
        fetch(`${API_BASE}/skill-graph/import-runs?limit=10`, {
          headers: { "Content-Type": "application/json", ...authHeaders(token) },
        }),
      ]);

      if (!healthRes.ok) throw new Error((await healthRes.json().catch(() => null))?.detail || "Skill graph health check failed.");
      if (!summaryRes.ok) throw new Error((await summaryRes.json().catch(() => null))?.detail || "Skill graph summary failed.");
      if (!nodesRes.ok) throw new Error((await nodesRes.json().catch(() => null))?.detail || "Skill graph node listing failed.");
      if (!statesRes.ok) throw new Error((await statesRes.json().catch(() => null))?.detail || "Skill graph state listing failed.");
      if (!runsRes.ok) throw new Error((await runsRes.json().catch(() => null))?.detail || "Skill graph import history failed.");

      const healthPayload = (await healthRes.json()) as SkillGraphHealthResponse;
      const summaryPayload = (await summaryRes.json()) as SkillGraphSummaryResponse;
      const nodesPayload = (await nodesRes.json()) as SkillGraphNodeListResponse;
      const statesPayload = (await statesRes.json()) as SkillGraphStateListResponse;
      const runsPayload = (await runsRes.json().catch(() => ({ total: 0, runs: [] }))) as { total: number; runs: SkillGraphImportRun[] };

      setHealth(healthPayload);
      setSummary(summaryPayload);
      setNodes(nodesPayload.nodes || []);
      setStates(statesPayload.states || []);
      setRuns(runsPayload.runs || []);

      setSelectedSlug((current) => {
        if (current && (nodesPayload.nodes || []).some((node) => node.skill_slug === current)) {
          return current;
        }
        return nodesPayload.nodes?.[0]?.skill_slug || summaryPayload.top_nodes?.[0]?.skill_slug || "";
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load skill graph.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!mounted || !signedIn) return;
    void loadOverview(query);
  }, [loadOverview, mounted, signedIn]);

  useEffect(() => {
    if (!mounted || !signedIn || !selectedSlug) return;
    void loadDetail(selectedSlug).catch((err) => setError(err instanceof Error ? err.message : "Failed to load node detail."));
  }, [loadDetail, mounted, selectedSlug, signedIn]);

  const handleSearchSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void loadOverview(query);
  };

  const handleImport = async () => {
    if (!token || !isAdmin) return;
    setImporting(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`${API_BASE}/skill-graph/import`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(token),
        },
        body: JSON.stringify({
          include_user_states: true,
          include_edges: true,
          include_evidence: true,
          notes: "Manual import from Skill Graph dashboard",
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail || "Skill graph import failed.");
      }
      const data = payload as SkillGraphImportResponse;
      setNotice(`Imported ${data.node_count} nodes, ${data.edge_count} edges, and ${data.evidence_count} evidence rows.`);
      await loadOverview(query);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Skill graph import failed.");
    } finally {
      setImporting(false);
    }
  };

  const selectedAliasPreview = detail?.aliases?.slice(0, 4) || [];
  const selectedEvidencePreview = detail?.evidence?.slice(0, 4) || [];
  const selectedEdgesPreview = detail?.edges?.slice(0, 4) || [];
  const selectedUserStatesPreview = detail?.user_states?.slice(0, 4) || [];

  if (!mounted) {
    return <div className="min-h-screen bg-slate-950" aria-busy="true" />;
  }

  if (!signedIn) {
    return (
      <div className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100">
        <div className="mx-auto flex max-w-3xl flex-col items-start gap-5 rounded-3xl border border-slate-800 bg-slate-900 p-8 shadow-2xl shadow-indigo-950/20">
          <p className="text-xs uppercase tracking-[0.3em] text-cyan-300">Skill Graph</p>
          <h1 className="text-3xl font-semibold text-white">Sign in to inspect the skill graph</h1>
          <p className="max-w-2xl text-sm leading-7 text-slate-400">
            The skill graph is an authenticated workspace that aggregates real CareerOS evidence into canonical skill nodes, aliases, edges, user states, and import runs.
          </p>
          <button
            type="button"
            onClick={() => router.push("/login?redirect=/skill-graph")}
            className="rounded-2xl bg-cyan-500 px-5 py-3 text-sm font-medium text-slate-950 transition hover:bg-cyan-400"
          >
            Go to login
          </button>
        </div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100">
        <div className="mx-auto flex max-w-3xl flex-col items-start gap-5 rounded-3xl border border-slate-800 bg-slate-900 p-8 shadow-2xl shadow-indigo-950/20">
          <p className="text-xs uppercase tracking-[0.3em] text-cyan-300">Skill Graph</p>
          <h1 className="text-3xl font-semibold text-white">Admin access required</h1>
          <p className="max-w-2xl text-sm leading-7 text-slate-400">
            The skill graph import ledger is an internal workspace for Admin reviewers. The authenticated account you are using can sign in, but it does not have permission to open this dashboard.
          </p>
          <button
            type="button"
            onClick={() => router.push("/dashboard")}
            className="rounded-2xl border border-slate-700 bg-slate-950 px-5 py-3 text-sm font-medium text-slate-100 transition hover:border-slate-500"
          >
            Back to dashboard
          </button>
        </div>
      </div>
    );
  }

  const totalNodes = summary?.total_nodes ?? nodes.length;
  const totalEdges = summary?.total_edges ?? 0;
  const totalEvidence = summary?.total_evidence ?? 0;
  const totalUserStates = summary?.total_user_states ?? states.length;

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-cyan-950/30 p-6 shadow-2xl shadow-cyan-950/20">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 space-y-3">
              <p className="text-xs uppercase tracking-[0.35em] text-cyan-300">M4 Skill Graph</p>
              <h1 className="flex items-center gap-3 text-3xl font-semibold text-white">
                <GitBranch className="h-7 w-7 text-cyan-300" />
                Skill Graph Schema and Import Ledger
              </h1>
              <p className="max-w-3xl text-sm leading-7 text-slate-300">
                Review the real-data skill graph, imported from CareerOS jobs, learning, roadmap, and resume evidence. The graph stays evidence-backed and can be refreshed from this panel.
              </p>
              {notice && (
                <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                  {notice}
                </div>
              )}
              {error && (
                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                  {error}
                </div>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:w-[28rem]">
              <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-4">
                <p className="text-[10px] uppercase tracking-[0.25em] text-slate-500">Health</p>
                <p className={`mt-2 inline-flex rounded-full border px-3 py-1 text-xs font-medium ${health?.ready ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" : "border-amber-500/30 bg-amber-500/10 text-amber-200"}`}>
                  {health?.ready ? "ready" : health?.status || "checking"}
                </p>
                <p className="mt-3 text-xs leading-6 text-slate-400 break-words">
                  {health?.message || "Import availability is derived from live CareerOS data sources."}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-4">
                <p className="text-[10px] uppercase tracking-[0.25em] text-slate-500">Collection</p>
                <p className="mt-2 text-lg font-semibold text-white">{health?.collection || "skill_graph"}</p>
                <p className="mt-2 text-xs text-slate-400">Tables: {health?.tables?.length || 0}</p>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[
            { label: "Nodes", value: totalNodes, icon: BrainCircuit, tone: "text-cyan-300" },
            { label: "Edges", value: totalEdges, icon: Layers, tone: "text-violet-300" },
            { label: "Evidence", value: totalEvidence, icon: Database, tone: "text-emerald-300" },
            { label: "User states", value: totalUserStates, icon: ShieldCheck, tone: "text-amber-300" },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.label} className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{item.label}</p>
                    <p className="mt-2 text-3xl font-semibold text-white">{item.value}</p>
                  </div>
                  <span className={`rounded-2xl border border-slate-700 bg-slate-950 p-3 ${item.tone}`}>
                    <Icon className="h-5 w-5" />
                  </span>
                </div>
              </div>
            );
          })}
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-6">
            <form
              onSubmit={handleSearchSubmit}
              className="flex flex-col gap-3 rounded-3xl border border-slate-800 bg-slate-900/90 p-4 sm:flex-row sm:items-center"
            >
              <label className="flex min-w-0 flex-1 items-center gap-3 rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3">
                <Search className="h-4 w-4 shrink-0 text-slate-400" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search by skill slug, name, or category"
                  className="w-full bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
                />
              </label>
              <div className="flex flex-wrap gap-3">
                <button
                  type="submit"
                  className="rounded-2xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-3 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20"
                >
                  Filter graph
                </button>
                <button
                  type="button"
                  onClick={() => void loadOverview(query)}
                  className="inline-flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm font-medium text-slate-200 transition hover:border-slate-500"
                >
                  <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                  Refresh
                </button>
                <button
                  type="button"
                  onClick={() => void handleImport()}
                  disabled={!isAdmin || importing}
                  className="inline-flex items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Sparkles className="h-4 w-4" />
                  {importing ? "Importing..." : isAdmin ? "Run import" : "Admin only"}
                </button>
              </div>
            </form>

            <div className="rounded-3xl border border-slate-800 bg-slate-900/90 p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Canonical nodes</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Evidence-backed skills</h2>
                </div>
                <p className="text-xs text-slate-500">
                  Showing {nodes.length} result{nodes.length === 1 ? "" : "s"}
                </p>
              </div>

              <div className="mt-5 space-y-3">
                {nodes.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 p-8 text-sm text-slate-400">
                    {loading ? "Loading skill graph nodes..." : "No nodes matched the current filter."}
                  </div>
                ) : (
                  nodes.map((node) => {
                    const active = node.skill_slug === selectedSlug;
                    return (
                      <button
                        key={node.skill_slug}
                        type="button"
                        onClick={() => setSelectedSlug(node.skill_slug)}
                        className={`w-full rounded-2xl border p-4 text-left transition ${
                          active
                            ? "border-cyan-500/40 bg-cyan-500/10"
                            : "border-slate-800 bg-slate-950/80 hover:border-slate-700 hover:bg-slate-950"
                        }`}
                      >
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="break-words text-base font-semibold text-white">{node.skill_name}</p>
                              <span className={`rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.2em] ${scoreTone(node.status)}`}>
                                {node.status}
                              </span>
                            </div>
                            <p className="mt-1 break-words text-sm text-slate-400">
                              <span className="font-mono text-cyan-300">{node.skill_slug}</span> · category {node.category} · {node.evidence_count} evidence rows
                            </p>
                          </div>

                          <div className="grid shrink-0 grid-cols-2 gap-2 text-xs text-slate-400 sm:grid-cols-4 lg:min-w-[19rem]">
                            <Metric label="Trust" value={miniPercent(node.trust_score)} />
                            <Metric label="Rel" value={miniPercent(node.relevance_score)} />
                            <Metric label="Fresh" value={miniPercent(node.freshness_score)} />
                            <Metric label="Conf" value={miniPercent(node.confidence_score)} />
                          </div>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-3xl border border-slate-800 bg-slate-900/90 p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Selected skill</p>
                  <h2 className="mt-1 text-2xl font-semibold text-white break-words">
                    {selectedNode?.skill_name || "Choose a node"}
                  </h2>
                  <p className="mt-2 break-words text-sm text-slate-400">
                    {selectedNode
                      ? `${selectedNode.skill_slug} · ${selectedNode.category} · ${selectedNode.status}`
                      : "Select a node to inspect aliases, evidence, edges, and user state."}
                  </p>
                </div>
                {selectedNode && (
                  <div className="rounded-2xl border border-slate-700 bg-slate-950 px-3 py-2 text-right">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Last import</p>
                    <p className="mt-1 text-xs text-slate-200 break-words">{selectedNode.last_import_run_uid || "n/a"}</p>
                  </div>
                )}
              </div>

              {!selectedNode ? (
                <div className="mt-6 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 p-6 text-sm text-slate-400">
                  Pick a skill node to inspect the import evidence.
                </div>
              ) : (
                <div className="mt-6 space-y-5">
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <SmallStat label="Evidence" value={String(selectedNode.evidence_count)} />
                    <SmallStat label="Sources" value={String(selectedNode.source_count)} />
                    <SmallStat label="Users" value={String(selectedNode.user_count)} />
                    <SmallStat label="Demand / Supply" value={`${selectedNode.demand_count} / ${selectedNode.supply_count}`} />
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <InfoPanel title="Aliases" icon={GitBranch}>
                      {selectedAliasPreview.length ? (
                        <div className="space-y-2">
                          {selectedAliasPreview.map((alias) => (
                            <div key={`${alias.raw_value}-${alias.source_entity_id}`} className="rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm">
                              <p className="break-words font-medium text-white">{alias.raw_value}</p>
                              <p className="mt-1 break-words text-xs text-slate-400">
                                {alias.source_entity_type} · {alias.source_field} · {alias.provider || "provider n/a"}
                              </p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyState text="No aliases captured for this skill." />
                      )}
                    </InfoPanel>

                    <InfoPanel title="User states" icon={ShieldCheck}>
                      {selectedUserStatesPreview.length ? (
                        <div className="space-y-2">
                          {selectedUserStatesPreview.map((state) => (
                            <div key={state.state_uid} className="rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm">
                              <div className="flex items-center justify-between gap-3">
                                <p className="break-words font-medium text-white">{state.user_id}</p>
                                <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] ${scoreTone(state.status)}`}>
                                  {state.status}
                                </span>
                              </div>
                              <p className="mt-1 text-xs text-slate-400">
                                confidence {miniPercent(state.confidence_score)} · evidence {state.evidence_count} · completion {state.completion_count}
                              </p>
                              <p className="mt-1 break-words text-xs text-slate-500">
                                {state.recommended_action || "No recommended action yet."}
                              </p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyState text="No user skill states captured for this node." />
                      )}
                    </InfoPanel>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <InfoPanel title="Edges" icon={ArrowRight}>
                      {selectedEdgesPreview.length ? (
                        <div className="space-y-2">
                          {selectedEdgesPreview.map((edge) => (
                            <div key={edge.edge_uid} className="rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm">
                              <p className="break-words font-medium text-white">
                                {edge.source_skill_name} → {edge.target_skill_name}
                              </p>
                              <p className="mt-1 break-words text-xs text-slate-400">
                                {edge.edge_type} · {edge.source_entity_type} · {edge.source_title || "No source title"}
                              </p>
                              <p className="mt-1 text-xs text-slate-500">
                                weight {edge.weight.toFixed(2)} · evidence {edge.evidence_count} · confidence {miniPercent(edge.confidence_score)}
                              </p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyState text="No edges linked to this node yet." />
                      )}
                    </InfoPanel>

                    <InfoPanel title="Evidence" icon={Database}>
                      {selectedEvidencePreview.length ? (
                        <div className="space-y-2">
                          {selectedEvidencePreview.map((evidence) => (
                            <div key={evidence.evidence_uid} className="rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm">
                              <p className="break-words font-medium text-white">
                                {evidence.evidence_kind}
                              </p>
                              <p className="mt-1 break-words text-xs text-slate-400">
                                {evidence.source_entity_type} · {evidence.source_field} · {evidence.provider || "provider n/a"}
                              </p>
                              <p className="mt-1 break-words text-xs text-slate-500">
                                {evidence.raw_value.length > 220 ? `${evidence.raw_value.slice(0, 220)}…` : evidence.raw_value}
                              </p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyState text="No evidence rows captured for this node." />
                      )}
                    </InfoPanel>
                  </div>
                </div>
              )}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <InfoPanel title="Recent import runs" icon={Sparkles}>
                {runs.length ? (
                  <div className="space-y-2">
                    {runs.map((run) => (
                      <div key={run.run_uid} className="rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm">
                        <div className="flex items-start justify-between gap-3">
                          <p className="break-words font-medium text-white">{run.strategy}</p>
                          <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] ${run.status === "completed" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" : scoreTone(run.status)}`}>
                            {run.status}
                          </span>
                        </div>
                        <p className="mt-1 break-words text-xs text-slate-400">
                          {run.node_count} nodes · {run.edge_count} edges · {run.evidence_count} evidence
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {run.completed_at ? `Completed ${formatDateTimeLocal(run.completed_at)}` : "Still running or awaiting refresh."}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState text="No import runs recorded yet." />
                )}
              </InfoPanel>

              <InfoPanel title="My skill states" icon={ShieldCheck}>
                {states.length ? (
                  <div className="space-y-2">
                    {states.slice(0, 4).map((state) => (
                      <div key={state.state_uid} className="rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <p className="break-words font-medium text-white">{state.skill_name}</p>
                          <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] ${scoreTone(state.status)}`}>
                            {state.status}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-400">
                          confidence {miniPercent(state.confidence_score)} · last activity {formatDateTimeLocal(state.last_activity_at || null)}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState text="No user states found for the current account." />
                )}
              </InfoPanel>
            </div>
          </div>
        </section>

        {loading && (
          <div className="flex items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/80 px-4 py-3 text-sm text-slate-300">
            <RefreshCw className="h-4 w-4 animate-spin text-cyan-300" />
            Refreshing skill graph data...
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950 px-3 py-2 text-left">
      <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-medium text-white">{value}</p>
    </div>
  );
}

function SmallStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3">
      <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-1 break-words text-sm font-medium text-white">{value}</p>
    </div>
  );
}

function InfoPanel({ title, icon: Icon, children }: { title: string; icon: ElementType; children: ReactNode }) {
  return (
    <div className="rounded-3xl border border-slate-800 bg-slate-900/90 p-5">
      <div className="flex items-center gap-2">
        <span className="rounded-xl border border-slate-700 bg-slate-950 p-2 text-cyan-300">
          <Icon className="h-4 w-4" />
        </span>
        <h3 className="text-sm font-semibold text-white">{title}</h3>
      </div>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 p-4 text-sm text-slate-400">{text}</div>;
}
