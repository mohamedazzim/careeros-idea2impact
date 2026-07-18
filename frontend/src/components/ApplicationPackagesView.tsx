"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { formatDateOnly, formatDateTimeLocal } from "@/lib/datetime";
import {
  Package, FileText, Mail, BookOpen, MessageSquare, Download,
  RefreshCw, Trash2, Plus, ChevronRight, CheckCircle2, Clock,
  AlertCircle, Sparkles, Briefcase, History, Copy, BadgeCheck,
  Brain, Target, ShieldAlert, Loader2, Check, X
} from "lucide-react";

interface PackageItem {
  id: string;
  job_id: number | null;
  title: string;
  status: string;
  resume_tailored: string;
  cover_letter: string;
  outreach_message: string;
  interview_guide: string;
  readiness_summary: string;
  metadata: any;
  created_at: string;
  updated_at: string;
}

interface ResumeSection {
  header: { name: string; role_target: string; location: string; email: string; phone: string; linkedin: string; github: string; portfolio: string };
  summary: string[];
  skills: Record<string, string[]>;
  experience: { title: string; company: string; dates: string; bullets: string[] }[];
  projects: { name: string; tech_stack: string[]; description: string; impact: string }[];
  education: { degree: string; institution: string; year: string }[];
  certifications: { name: string; issuer: string; year: string }[];
  achievements: string[];
  ats_keywords: string[];
  quality_notes: string[];
}

interface CoverLetterSection { subject: string; body: string; }
interface OutreachSection { linkedin_message: string; email_message: string; }
interface InterviewGuideSection {
  likely_questions: string[];
  talking_points: string[];
  weaknesses_to_prepare: string[];
  questions_to_ask: string[];
}
interface PkgMetadata { job_id: string; target_role: string; target_company: string; match_score: number; generation_mode: string; warnings: string[]; }

interface StructuredContent {
  resume: ResumeSection;
  cover_letter: CoverLetterSection;
  outreach: OutreachSection;
  interview_guide: InterviewGuideSection;
  metadata: PkgMetadata;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getToken(): string {
  try { return localStorage.getItem("careeros_token") || ""; } catch { return ""; }
}

function tryParseContent(pkg: PackageItem): StructuredContent | null {
  try {
    const parseOne = (raw: string): any => {
      if (!raw) return {};
      try { return JSON.parse(raw); } catch { return { body: raw }; }
    };
    const resume = parseOne(pkg.resume_tailored);
    const cover = parseOne(pkg.cover_letter);
    const outreach = parseOne(pkg.outreach_message);
    const interview = parseOne(pkg.interview_guide);
    const meta = pkg.metadata || {};

    const structured: StructuredContent = {
      resume: {
        header: resume.header || {},
        summary: resume.summary || (typeof resume === "string" ? [resume] : []),
        skills: resume.skills || {},
        experience: resume.experience || [],
        projects: resume.projects || [],
        education: resume.education || [],
        certifications: resume.certifications || [],
        achievements: resume.achievements || [],
        ats_keywords: resume.ats_keywords || [],
        quality_notes: resume.quality_notes || [],
      },
      cover_letter: { subject: cover.subject || "", body: cover.body || "" },
      outreach: { linkedin_message: outreach.linkedin_message || "", email_message: outreach.email_message || "" },
      interview_guide: {
        likely_questions: interview.likely_questions || [],
        talking_points: interview.talking_points || [],
        weaknesses_to_prepare: interview.weaknesses_to_prepare || [],
        questions_to_ask: interview.questions_to_ask || [],
      },
      metadata: {
        job_id: meta.job_id || "",
        target_role: meta.target_role || resume.header?.role_target || "",
        target_company: meta.target_company || "",
        match_score: meta.match_score || 0,
        generation_mode: meta.generation_mode || "unknown",
        warnings: meta.warnings || [],
      },
    };

    if (!hasRenderableStructuredContent(structured)) {
      const targetRole = structured.metadata.target_role || pkg.title || "this role";
      const targetCompany = structured.metadata.target_company || "the company";
      return {
        resume: {
          ...structured.resume,
          summary: [
            pkg.readiness_summary || `No structured resume content was stored for ${targetRole} at ${targetCompany}.`,
          ],
          quality_notes: [
            ...(structured.resume.quality_notes || []),
            "This package was saved without meaningful structured content. Regenerate it to rebuild the tailored sections.",
          ],
        },
        cover_letter: {
          subject: structured.cover_letter.subject || `Application for ${targetRole}`,
          body: structured.cover_letter.body || "No cover letter content was stored for this package.",
        },
        outreach: {
          linkedin_message: structured.outreach.linkedin_message || "No LinkedIn outreach message was stored for this package.",
          email_message: structured.outreach.email_message || "No email outreach message was stored for this package.",
        },
        interview_guide: {
          likely_questions: structured.interview_guide.likely_questions.length > 0
            ? structured.interview_guide.likely_questions
            : ["No interview guide content was stored for this package."],
          talking_points: structured.interview_guide.talking_points,
          weaknesses_to_prepare: structured.interview_guide.weaknesses_to_prepare,
          questions_to_ask: structured.interview_guide.questions_to_ask,
        },
        metadata: structured.metadata,
      };
    }
    return structured;
  } catch {
    return null;
  }
}

function hasRenderableStructuredContent(content: StructuredContent | null): boolean {
  if (!content) return false;
  const resume = content.resume || ({} as ResumeSection);
  const cover = content.cover_letter || ({} as CoverLetterSection);
  const outreach = content.outreach || ({} as OutreachSection);
  const interview = content.interview_guide || ({} as InterviewGuideSection);
  return Boolean(
    (resume.summary && resume.summary.length > 0) ||
    (resume.skills && Object.keys(resume.skills).length > 0) ||
    (resume.experience && resume.experience.length > 0) ||
    (resume.projects && resume.projects.length > 0) ||
    (resume.education && resume.education.length > 0) ||
    (resume.certifications && resume.certifications.length > 0) ||
    (resume.achievements && resume.achievements.length > 0) ||
    (resume.ats_keywords && resume.ats_keywords.length > 0) ||
    (cover.subject || cover.body || outreach.linkedin_message || outreach.email_message ||
      interview.likely_questions?.length || interview.talking_points?.length ||
      interview.weaknesses_to_prepare?.length || interview.questions_to_ask?.length)
  );
}

function pickBestPackage(packages: PackageItem[], preferredId?: string | null): PackageItem | null {
  const preferred = preferredId ? packages.find((pkg) => pkg.id === preferredId) : null;
  if (preferred) {
    const preferredContent = tryParseContent(preferred);
    if (hasRenderableStructuredContent(preferredContent) || preferred.readiness_summary || preferred.status !== "ready") {
      return preferred;
    }
  }

  for (const pkg of packages) {
    const content = tryParseContent(pkg);
    if (hasRenderableStructuredContent(content) || pkg.readiness_summary) {
      return pkg;
    }
  }

  return packages[0] || null;
}

function copyToClipboard(text: string, setMsg: (m: string | null) => void) {
  navigator.clipboard.writeText(text).then(() => {
    setMsg("Copied!");
    setTimeout(() => setMsg(null), 1500);
  }).catch(() => setMsg("Copy failed"));
}

function QualityBadge({ mode, warnings }: { mode: string; warnings: string[] }) {
  if (mode === "llm") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border border-emerald-500/30 bg-emerald-950/30 text-emerald-300">
        <BadgeCheck className="h-3 w-3" /> AI Generated
      </span>
    );
  }
  if (mode === "deterministic_fallback") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border border-amber-500/30 bg-amber-950/30 text-amber-300">
        <ShieldAlert className="h-3 w-3" /> Deterministic Fallback
      </span>
    );
  }
  if (warnings.length > 0) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border border-amber-500/30 bg-amber-950/30 text-amber-300">
        <AlertCircle className="h-3 w-3" /> See Notes
      </span>
    );
  }
  return null;
}

export default function ApplicationPackagesView() {
  const mountedRef = useRef(true);
  const pollAbortRef = useRef<AbortController | null>(null);
  const [packages, setPackages] = useState<PackageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [copyMsg, setCopyMsg] = useState<string | null>(null);
  const [selectedPkg, setSelectedPkg] = useState<PackageItem | null>(null);
  const [structured, setStructured] = useState<StructuredContent | null>(null);
  const [activeTab, setActiveTab] = useState<"resume" | "cover" | "outreach" | "interview" | "versions">("resume");
  const [generating, setGenerating] = useState(false);
  const [jobIdInput, setJobIdInput] = useState("");
  const [stage, setStage] = useState<string>("");

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      pollAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (selectedPkg) {
      const s = tryParseContent(selectedPkg);
      setStructured(s);
    } else {
      setStructured(null);
    }
  }, [selectedPkg]);

  const loadPackages = useCallback(async (signal?: AbortSignal) => {
    if (!mountedRef.current) return;
    setLoading(true);
    setError(null);
    const token = getToken();
    try {
      const res = await fetch(`${API_BASE}/packages`, {
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!mountedRef.current || signal?.aborted) return;
      const nextPackages = data.packages || [];
      setPackages(nextPackages);
      setSelectedPkg((current) => {
        const candidate = current
          ? (nextPackages.find((p: PackageItem) => p.id === current.id) ?? current)
          : null;
        const chosen = pickBestPackage(nextPackages, candidate?.id);
        return chosen ?? null;
      });
    } catch (e: any) {
      if (signal?.aborted || e?.name === "AbortError") return;
      if (!mountedRef.current) return;
      setError(e.message);
    } finally {
      if (!mountedRef.current || signal?.aborted) return;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadPackages(controller.signal);
    return () => controller.abort();
  }, [loadPackages]);

  useEffect(() => {
    if (!success) return;
    const timer = setTimeout(() => { if (mountedRef.current) setSuccess(null); }, 3500);
    return () => clearTimeout(timer);
  }, [success]);

  const pollUntilSettled = useCallback(async (targetId?: string) => {
    pollAbortRef.current?.abort();
    const controller = new AbortController();
    pollAbortRef.current = controller;
    for (let attempt = 0; attempt < 50; attempt++) {
      if (controller.signal.aborted || !mountedRef.current) return;
      const mockStages = ["Reading candidate profile...", "Reading job details...", "Generating resume...", "Validating output...", "Saving package..."];
      setStage(mockStages[Math.min(attempt, mockStages.length - 1)]);
      await new Promise<void>((resolve) => {
        const timer = setTimeout(resolve, 1500);
        controller.signal.addEventListener("abort", () => { clearTimeout(timer); resolve(); }, { once: true });
      });
      if (controller.signal.aborted || !mountedRef.current) return;
      const token = getToken();
      try {
        const res = await fetch(`${API_BASE}/packages`, {
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        if (!res.ok) continue;
        const data = await res.json();
        if (controller.signal.aborted || !mountedRef.current) return;
        const nextPackages = data.packages || [];
        setPackages(nextPackages);
        setSelectedPkg((current) => {
          const preferredId = targetId || current?.id;
          return pickBestPackage(nextPackages, preferredId) ?? null;
        });
        const target = targetId ? nextPackages.find((p: PackageItem) => p.id === targetId) : pickBestPackage(nextPackages);
        if (!target) continue;
        if (target.status !== "generating" && target.status !== "regenerating") {
          setStage("");
          if (target.status === "ready") setSuccess("Package ready!");
          else if (target.status === "failed") setError(target.readiness_summary || "Generation failed");
          return;
        }
      } catch (e: any) {
        if (controller.signal.aborted || e?.name === "AbortError") return;
      }
    }
    setStage("");
    if (!mountedRef.current || controller.signal.aborted) return;
    setError("Package generation timed out. Try regenerating.");
  }, []);

  const handleGenerate = async () => {
    if (!jobIdInput.trim()) return;
    setGenerating(true);
    setError(null);
    setSuccess(null);
    setStage("Starting generation...");
    const token = getToken();
    try {
      const res = await fetch(`${API_BASE}/packages/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ job_id: jobIdInput.trim() }),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (!mountedRef.current) return;
      setJobIdInput("");
      await pollUntilSettled(data.package_id);
    } catch (e: any) {
      if (!mountedRef.current) return;
      setError(e.message);
      setStage("");
    } finally {
      if (!mountedRef.current) return;
      setGenerating(false);
    }
  };

  const handleDelete = async (id: string) => {
    const token = getToken();
    setError(null);
    const res = await fetch(`${API_BASE}/packages/${id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) { setError(`Delete failed: HTTP ${res.status}`); return; }
    setPackages((prev) => prev.filter((p) => p.id !== id));
    if (selectedPkg?.id === id) setSelectedPkg(null);
    setSuccess("Package deleted.");
  };

  const handleRegenerate = async (id: string) => {
    setGenerating(true);
    setError(null);
    setStage("Regenerating...");
    const token = getToken();
    const res = await fetch(`${API_BASE}/packages/${id}/regenerate`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) { setGenerating(false); setError(`HTTP ${res.status}`); return; }
    await pollUntilSettled(id);
    if (!mountedRef.current) return;
    setGenerating(false);
  };

  const handleDownload = async (id: string, asset: string) => {
    const token = getToken();
    const res = await fetch(`${API_BASE}/packages/${id}/download?asset=${asset}&format=markdown`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) { setError(`Download failed: HTTP ${res.status}`); return; }
    const data = await res.json();
    const blob = new Blob([data.content || ""], { type: "text/markdown;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = data.filename || `${asset}.md`;
    document.body.appendChild(link); link.click(); link.remove();
    window.URL.revokeObjectURL(url);
    setSuccess("Download started.");
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case "ready": return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />;
      case "generating": case "regenerating": return <RefreshCw className="h-3.5 w-3.5 animate-spin text-amber-400" />;
      case "failed": return <AlertCircle className="h-3.5 w-3.5 text-red-400" />;
      default: return <Clock className="h-3.5 w-3.5 text-slate-400" />;
    }
  };

  const tabs = [
    { key: "resume", label: "Resume", icon: FileText },
    { key: "cover", label: "Cover Letter", icon: Mail },
    { key: "outreach", label: "Outreach", icon: MessageSquare },
    { key: "interview", label: "Interview", icon: BookOpen },
    { key: "versions", label: "Info", icon: History },
  ] as const;
  const packageHasContent = hasRenderableStructuredContent(structured);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-4 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Package className="h-7 w-7 text-violet-400" />
              Application Packages
            </h1>
            <p className="text-sm text-slate-400 mt-1">ATS-optimized resumes, cover letters, outreach &amp; interview prep</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text" value={jobIdInput}
              onChange={(e) => setJobIdInput(e.target.value)}
              placeholder="Enter job ID..."
              onKeyDown={(e) => { if (e.key === "Enter") handleGenerate(); }}
              className="px-3 py-2 rounded-xl border border-slate-700 bg-slate-900 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500/50 w-40 lg:w-48"
            />
            <button
              onClick={handleGenerate}
              disabled={generating || !jobIdInput.trim()}
              className="flex items-center gap-2 px-4 py-2 rounded-xl border border-violet-500/30 bg-violet-950/30 hover:bg-violet-950/50 text-violet-300 text-sm font-medium transition-colors disabled:opacity-50"
            >
              <Sparkles className={`h-4 w-4 ${generating ? "animate-pulse" : ""}`} />
              Generate
            </button>
          </div>
        </div>

        {/* Stage indicator during generation */}
        {stage && (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-300 flex items-center gap-3">
            <Loader2 className="h-4 w-4 animate-spin" />
            {stage}
          </div>
        )}

        {error && (<div className="rounded-2xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-300">{error}</div>)}
        {success && (<div className="rounded-2xl border border-emerald-500/30 bg-emerald-950/20 p-4 text-sm text-emerald-300">{success}</div>)}

        <div className="grid gap-4 lg:grid-cols-3">
          {/* Sidebar */}
          <div className="lg:col-span-1 space-y-2 max-h-[70vh] overflow-y-auto pr-1">
            {loading && packages.length === 0 && (<div className="text-slate-500 text-sm p-4">Loading...</div>)}
            {!loading && packages.length === 0 && (
              <div className="rounded-2xl border border-slate-700 bg-slate-900/40 p-6 text-center">
                <Package className="h-8 w-8 text-slate-600 mx-auto mb-2" />
                <p className="text-sm text-slate-500">No packages yet. Enter a job ID and click Generate.</p>
              </div>
            )}
            {packages.map((pkg) => (
              <button
                key={pkg.id}
                onClick={() => { setSelectedPkg(pkg); setActiveTab("resume"); }}
                className={`w-full text-left rounded-xl border p-4 transition-all ${
                  selectedPkg?.id === pkg.id ? "border-violet-500/50 bg-violet-950/20" : "border-slate-700 bg-slate-900/60 hover:border-slate-600"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{pkg.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{formatDateOnly(pkg.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">{statusIcon(pkg.status)}<ChevronRight className="h-4 w-4 text-slate-600" /></div>
                </div>
              </button>
            ))}
          </div>

          {/* Main content */}
          <div className="lg:col-span-2">
            {selectedPkg && structured ? (
              <div className="rounded-2xl border border-slate-700 bg-slate-900/60 overflow-hidden">
                {!packageHasContent && (
                  <div className="m-4 rounded-2xl border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-200">
                    This package saved successfully, but the stored structured content is empty. Regenerate it to rebuild the tailored resume, cover letter, outreach, and interview prep from the latest job and resume data.
                  </div>
                )}
                {/* Tabs */}
                <div className="flex items-center border-b border-slate-700 overflow-x-auto">
                  {tabs.map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={`flex items-center gap-2 px-4 py-3 text-xs font-medium transition-colors whitespace-nowrap ${
                        activeTab === tab.key ? "text-violet-300 border-b-2 border-violet-500 bg-slate-800/40" : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <tab.icon className="h-3.5 w-3.5" /> {tab.label}
                    </button>
                  ))}
                </div>

                {/* Toolbar */}
                <div className="flex items-center justify-between p-3 border-b border-slate-800">
                  <div className="flex items-center gap-3">
                    {statusIcon(selectedPkg.status)}
                    <span className="text-xs text-slate-400">{selectedPkg.status}</span>
                    {copyMsg && <span className="text-xs text-emerald-400">{copyMsg}</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <QualityBadge mode={structured.metadata.generation_mode} warnings={structured.metadata.warnings} />
                    {structured.metadata.match_score > 0 && (
                      <span className="text-[10px] font-mono text-slate-500">{Math.round(structured.metadata.match_score)}% match</span>
                    )}
                    {activeTab !== "versions" && (
                      <button onClick={() => handleDownload(selectedPkg.id, activeTab === "outreach" ? "outreach" : activeTab === "interview" ? "interview_guide" : activeTab === "cover" ? "cover_letter" : "resume")}
                        className="flex items-center gap-1 px-2 py-1 rounded-lg border border-slate-700 text-xs text-slate-400 hover:text-slate-200 transition-colors">
                        <Download className="h-3 w-3" /> Download
                      </button>
                    )}
                    <button onClick={() => handleRegenerate(selectedPkg.id)} disabled={generating}
                      className="flex items-center gap-1 px-2 py-1 rounded-lg border border-amber-500/30 text-xs text-amber-400 hover:text-amber-300 transition-colors disabled:opacity-50">
                      <RefreshCw className={`h-3 w-3 ${generating ? "animate-spin" : ""}`} /> Regenerate
                    </button>
                    <button onClick={() => handleDelete(selectedPkg.id)}
                      className="flex items-center gap-1 px-2 py-1 rounded-lg border border-red-500/30 text-xs text-red-400 hover:text-red-300 transition-colors">
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>

                {/* Content */}
                <div className="p-4 max-h-[60vh] overflow-y-auto">
                  {/* === RESUME TAB === */}
                  {activeTab === "resume" && (
                    <div className="space-y-6 text-sm">
                      {/* Header */}
                      <div className="text-center pb-4 border-b border-slate-800">
                        <h2 className="text-lg font-bold text-white">{structured.resume.header?.name || "[Your Name]"}</h2>
                        <p className="text-violet-300 font-medium">{structured.resume.header?.role_target || ""}</p>
                        <p className="text-xs text-slate-500">{structured.resume.header?.location || ""}</p>
                      </div>

                      {/* Summary */}
                      {structured.resume.summary.length > 0 && (
                        <SectionCard title="Professional Summary" icon={Target} onCopy={() => copyToClipboard(structured.resume.summary.join("\n"), setCopyMsg)}>
                          {structured.resume.summary.map((line, i) => (
                            <p key={i} className="text-slate-300 leading-relaxed mb-1">{line}</p>
                          ))}
                        </SectionCard>
                      )}

                      {/* Skills */}
                      {Object.keys(structured.resume.skills).length > 0 && (
                        <SectionCard title="Core Skills" icon={Brain} onCopy={() => {
                          const text = Object.entries(structured.resume.skills).map(([cat, skills]) => `**${cat}**: ${skills.join(", ")}`).join("\n");
                          copyToClipboard(text, setCopyMsg);
                        }}>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            {Object.entries(structured.resume.skills).map(([category, skills]) => (
                              <div key={category}>
                                <p className="text-[10px] uppercase font-mono font-bold text-slate-500 mb-1">{category}</p>
                                <div className="flex flex-wrap gap-1">
                                  {skills.map((s) => (
                                    <span key={s} className="px-2 py-0.5 rounded-md bg-slate-800 text-xs text-slate-300 border border-slate-700">{s}</span>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        </SectionCard>
                      )}

                      {/* Experience */}
                      {structured.resume.experience.length > 0 && (
                        <SectionCard title="Experience" icon={Briefcase}>
                          {structured.resume.experience.map((exp, i) => (
                            <div key={i} className="mb-4 last:mb-0">
                              <div className="flex justify-between items-start">
                                <div>
                                  <p className="font-semibold text-white">{exp.title}</p>
                                  <p className="text-slate-400 text-xs">{exp.company}</p>
                                </div>
                                {exp.dates && <p className="text-xs text-slate-500">{exp.dates}</p>}
                              </div>
                              {exp.bullets.length > 0 && (
                                <ul className="mt-2 space-y-1 list-disc list-inside text-slate-300">
                                  {exp.bullets.map((b, j) => <li key={j} className="text-xs">{b}</li>)}
                                </ul>
                              )}
                            </div>
                          ))}
                        </SectionCard>
                      )}

                      {/* Projects */}
                      {structured.resume.projects.length > 0 && (
                        <SectionCard title="Projects">
                          {structured.resume.projects.map((proj, i) => (
                            <div key={i} className="mb-3 last:mb-0 p-3 rounded-xl border border-slate-800 bg-slate-900/50">
                              <p className="font-semibold text-white">{proj.name}</p>
                              {proj.tech_stack.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {proj.tech_stack.map((t) => <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-violet-950/50 text-violet-300 border border-violet-500/20">{t}</span>)}
                                </div>
                              )}
                              <p className="text-xs text-slate-400 mt-1">{proj.description}</p>
                              {proj.impact && <p className="text-xs text-emerald-400 mt-1">Impact: {proj.impact}</p>}
                            </div>
                          ))}
                        </SectionCard>
                      )}

                      {/* Education */}
                      {structured.resume.education.length > 0 && (
                        <SectionCard title="Education">
                          {structured.resume.education.map((edu, i) => (
                            <p key={i} className="text-slate-300 text-xs mb-1">{edu.degree} — {edu.institution} ({edu.year})</p>
                          ))}
                        </SectionCard>
                      )}

                      {/* ATS Keywords */}
                      {structured.resume.ats_keywords.length > 0 && (
                        <SectionCard title="ATS Keywords">
                          <div className="flex flex-wrap gap-1">
                            {structured.resume.ats_keywords.map((kw) => (
                              <span key={kw} className="px-2 py-0.5 rounded-md bg-emerald-950/30 text-[10px] text-emerald-300 border border-emerald-500/20">{kw}</span>
                            ))}
                          </div>
                        </SectionCard>
                      )}

                      {/* Quality Notes / Warnings */}
                      {(structured.resume.quality_notes.length > 0 || structured.metadata.warnings.length > 0) && (
                        <SectionCard title="Notes & Warnings" icon={ShieldAlert}>
                          {structured.resume.quality_notes.map((n, i) => (
                            <p key={`qn-${i}`} className="text-amber-300 text-xs mb-1 flex items-start gap-2">
                              <AlertCircle className="h-3 w-3 mt-0.5 shrink-0" /> {n}
                            </p>
                          ))}
                          {structured.metadata.warnings.map((w, i) => (
                            <p key={`mw-${i}`} className="text-amber-300 text-xs mb-1 flex items-start gap-2">
                              <AlertCircle className="h-3 w-3 mt-0.5 shrink-0" /> {w}
                            </p>
                          ))}
                        </SectionCard>
                      )}
                    </div>
                  )}

                  {/* === COVER LETTER TAB === */}
                  {activeTab === "cover" && (
                    <div className="space-y-4">
                      {structured.cover_letter.subject && (
                        <p className="text-xs font-mono text-slate-500">Subject: {structured.cover_letter.subject}</p>
                      )}
                      {structured.cover_letter.body ? (
                        <div className="bg-slate-950 rounded-xl p-4 border border-slate-800 text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">
                          {structured.cover_letter.body}
                        </div>
                      ) : (
                        <div className="text-center py-12 text-slate-500">
                          <Mail className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          <p className="text-sm">{selectedPkg.status === "generating" ? "Generating..." : "No cover letter generated"}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* === OUTREACH TAB === */}
                  {activeTab === "outreach" && (
                    <div className="space-y-4">
                      <SectionCard title="LinkedIn Message" onCopy={() => copyToClipboard(structured.outreach.linkedin_message, setCopyMsg)}>
                        <p className="text-slate-300 text-sm whitespace-pre-wrap leading-relaxed">
                          {structured.outreach.linkedin_message || "No LinkedIn outreach generated."}
                        </p>
                      </SectionCard>
                      <SectionCard title="Email Message" onCopy={() => copyToClipboard(structured.outreach.email_message, setCopyMsg)}>
                        <p className="text-slate-300 text-sm whitespace-pre-wrap leading-relaxed">
                          {structured.outreach.email_message || "No email outreach generated."}
                        </p>
                      </SectionCard>
                    </div>
                  )}

                  {/* === INTERVIEW TAB === */}
                  {activeTab === "interview" && (
                    <div className="space-y-4">
                      {structured.interview_guide.likely_questions.length > 0 && (
                        <SectionCard title="Likely Questions">
                          <ul className="space-y-1 list-disc list-inside">
                            {structured.interview_guide.likely_questions.map((q, i) => <li key={i} className="text-slate-300 text-xs">{q}</li>)}
                          </ul>
                        </SectionCard>
                      )}
                      {structured.interview_guide.talking_points.length > 0 && (
                        <SectionCard title="Key Talking Points">
                          <ul className="space-y-1 list-disc list-inside">
                            {structured.interview_guide.talking_points.map((t, i) => <li key={i} className="text-slate-300 text-xs">{t}</li>)}
                          </ul>
                        </SectionCard>
                      )}
                      {structured.interview_guide.weaknesses_to_prepare.length > 0 && (
                        <SectionCard title="Prepare For">
                          <ul className="space-y-1 list-disc list-inside">
                            {structured.interview_guide.weaknesses_to_prepare.map((w, i) => <li key={i} className="text-amber-300 text-xs">{w}</li>)}
                          </ul>
                        </SectionCard>
                      )}
                      {structured.interview_guide.questions_to_ask.length > 0 && (
                        <SectionCard title="Questions to Ask">
                          <ul className="space-y-1 list-disc list-inside">
                            {structured.interview_guide.questions_to_ask.map((q, i) => <li key={i} className="text-slate-300 text-xs">{q}</li>)}
                          </ul>
                        </SectionCard>
                      )}
                      {structured.interview_guide.likely_questions.length === 0 && (
                        <div className="text-center py-12 text-slate-500">
                          <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          <p className="text-sm">No interview guide generated yet.</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* === VERSIONS / INFO TAB === */}
                  {activeTab === "versions" && (
                    <div className="space-y-3 text-sm">
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <InfoRow label="Package ID" value={selectedPkg.id} />
                        <InfoRow label="Status" value={selectedPkg.status} />
                        <InfoRow label="Target Role" value={structured.metadata.target_role} />
                        <InfoRow label="Company" value={structured.metadata.target_company} />
                        <InfoRow label="Generation" value={structured.metadata.generation_mode} />
                        <InfoRow label="Match Score" value={`${Math.round(structured.metadata.match_score)}%`} />
                        <InfoRow label="Created" value={formatDateTimeLocal(selectedPkg.created_at)} />
                        <InfoRow label="Updated" value={formatDateTimeLocal(selectedPkg.updated_at, "—")} />
                      </div>
                      {structured.metadata.warnings.length > 0 && (
                        <div className="p-3 rounded-xl border border-amber-500/20 bg-amber-950/10">
                          <p className="text-[10px] uppercase font-mono font-bold text-amber-400 mb-2">Warnings</p>
                          {structured.metadata.warnings.map((w, i) => <p key={i} className="text-xs text-amber-300">{w}</p>)}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-slate-700 bg-slate-900/40 p-12 text-center">
                <Briefcase className="h-10 w-10 text-slate-600 mx-auto mb-3" />
                <p className="text-sm text-slate-500">{selectedPkg ? "This package uses the old format. Regenerate it to see the new structured view." : "Select a package to view"}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SectionCard({ title, icon: Icon, children, onCopy }: { title: string; icon?: any; children: React.ReactNode; onCopy?: () => void }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="h-4 w-4 text-violet-400" />}
          <h3 className="text-xs font-mono uppercase font-bold text-slate-400 tracking-wider">{title}</h3>
        </div>
        {onCopy && (
          <button onClick={onCopy} className="text-slate-600 hover:text-slate-300 transition-colors" title="Copy section">
            <Copy className="h-3 w-3" />
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-2 rounded-lg bg-slate-900/50 border border-slate-800">
      <p className="text-[10px] uppercase font-mono text-slate-500">{label}</p>
      <p className="text-slate-300 text-xs truncate">{value || "—"}</p>
    </div>
  );
}
