import "@testing-library/jest-dom/vitest";
import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import LoginView from "@/components/LoginView";
import KnowledgeHub from "@/components/KnowledgeHub";
import ChatMessageList from "@/components/rag/ChatMessageList";
import LearningPathsPanel from "@/components/learning/LearningPathsPanel";
import { canAccess, getNavSections } from "@/lib/rbac";
import type { KnowledgeDoc } from "@/types";
import type { RagChatMessage } from "@/types/demo-rag";

const renderEndRef = React.createRef<HTMLDivElement>();

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CareerOS authentication UX", () => {
  it("requires login credentials before calling the API boundary", () => {
    const onLogin = vi.fn();
    const onRegister = vi.fn();
    render(<LoginView onLogin={onLogin} onRegister={onRegister} />);

    expect(screen.getByLabelText(/email address/i)).toBeRequired();
    expect(screen.getByLabelText(/secure password/i)).toBeRequired();
    fireEvent.click(screen.getByRole("button", { name: /authenticate credentials/i }));

    expect(onLogin).not.toHaveBeenCalled();
    expect(onRegister).not.toHaveBeenCalled();
  });

  it("shows a safe authentication failure without leaking stack traces", async () => {
    const onLogin = vi.fn().mockResolvedValue("Invalid credentials.");
    render(<LoginView onLogin={onLogin} onRegister={vi.fn()} />);

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: "candidate@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/secure password/i), {
      target: { value: "wrong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /authenticate credentials/i }));

    expect(await screen.findByText("Invalid credentials.")).toBeInTheDocument();
    expect(screen.queryByText(/traceback|stack|exception/i)).not.toBeInTheDocument();
  });
});

describe("CareerOS resume upload and analysis states", () => {
  const baseProps = {
    activeId: null,
    onUpload: vi.fn().mockResolvedValue("doc-1"),
    onDelete: vi.fn(),
    onSelect: vi.fn(),
    onPreviewDocument: vi.fn().mockResolvedValue(null),
    onAnalyzeTab: vi.fn(),
  };

  it("shows the resume-upload loading state during ingestion", () => {
    render(<KnowledgeHub {...baseProps} documents={[]} isUploading />);

    expect(screen.getByText("Processing Document Pipeline...")).toBeInTheDocument();
    expect(screen.getByText(/masking PII & running vector embed workflows/i)).toBeInTheDocument();
  });

  it("shows resume-analysis summary data for an indexed document", () => {
    const documents: KnowledgeDoc[] = [
      {
        id: "doc-1",
        filename: "synthetic-resume.txt",
        doc_type: "resume",
        status: "analyzed",
        chunk_count: 7,
        embedding_status: "indexed",
        vector_count: 7,
        created_at: "2026-06-13T10:00:00Z",
      },
    ];

    render(<KnowledgeHub {...baseProps} documents={documents} isUploading={false} />);

    expect(screen.getByText("synthetic-resume.txt")).toBeInTheDocument();
    expect(screen.getByText("Indexed")).toBeInTheDocument();
    expect(screen.getByText("1 Records")).toBeInTheDocument();
  });

  it("keeps upload failures visible as failed ingestion status", () => {
    const documents: KnowledgeDoc[] = [
      {
        id: "doc-failed",
        filename: "bad-upload.pdf",
        doc_type: "resume",
        status: "failed",
        created_at: "2026-06-13T10:00:00Z",
      },
    ];

    render(<KnowledgeHub {...baseProps} documents={documents} isUploading={false} />);

    expect(screen.getByText("bad-upload.pdf")).toBeInTheDocument();
    expect(screen.getByText("Ingestion Failed")).toBeInTheDocument();
  });
});

describe("CareerOS RAG and opportunity evidence UX", () => {
  it("renders opportunity-match evidence, missing skills, preparation actions, and citations", () => {
    const messages: RagChatMessage[] = [
      {
        id: "answer-1",
        role: "assistant",
        createdAt: Date.now(),
        confidence: 0.91,
        content:
          "Opportunity-match evidence: Python and FastAPI are matched. Missing skills: Kubernetes. Preparation action: build a deployment project.",
        citations: [
          {
            doc_name: "FEATURE_STATUS.md",
            section_title: "Job Matching",
            source_path: "docs/rag/FEATURE_STATUS.md",
            score: 0.88,
          },
        ],
        followUpQuestions: ["Which agents are implemented?"],
      },
    ];
    const onFollowUpClick = vi.fn();

    render(
      <ChatMessageList
        messages={messages}
        loading={false}
        onFollowUpClick={onFollowUpClick}
        endRef={renderEndRef}
      />,
    );

    expect(screen.getByText(/Opportunity-match evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Missing skills: Kubernetes/i)).toBeInTheDocument();
    expect(screen.getByText(/Preparation action/i)).toBeInTheDocument();
    expect(screen.getByText("FEATURE_STATUS.md")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /which agents are implemented/i }));
    expect(onFollowUpClick).toHaveBeenCalledWith("Which agents are implemented?");
  });

  it("shows safe service-unavailable states for Deepgram and external dry-run actions", () => {
    const messages: RagChatMessage[] = [
      {
        id: "answer-2",
        role: "assistant",
        createdAt: Date.now(),
        content: "Deepgram is unavailable in this demo. External calls are dry-run only.",
        error: { code: "PROVIDER_UNAVAILABLE", message: "Provider unavailable for this demo." },
      },
    ];

    render(
      <ChatMessageList
        messages={messages}
        loading={false}
        onFollowUpClick={vi.fn()}
        endRef={renderEndRef}
      />,
    );

    expect(screen.getByText(/Deepgram is unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/dry-run only/i)).toBeInTheDocument();
    expect(screen.getByText("PROVIDER_UNAVAILABLE")).toBeInTheDocument();
    expect(screen.queryByText(/traceback|stack|api key|secret/i)).not.toBeInTheDocument();
  });

  it("does not render secret-like response fields unless they are part of the visible answer", () => {
    const message = {
      id: "answer-3",
      role: "assistant" as const,
      createdAt: Date.now(),
      content: "The demo uses environment variables and does not expose server credentials.",
      internal_secret: "NVIDIA_API_KEY=not-for-ui",
      raw_provider_payload: { GEMINI_API_KEY: "not-for-ui" },
    } as RagChatMessage & Record<string, unknown>;

    render(
      <ChatMessageList
        messages={[message]}
        loading={false}
        onFollowUpClick={vi.fn()}
        endRef={renderEndRef}
      />,
    );

    expect(screen.getByText(/does not expose server credentials/i)).toBeInTheDocument();
    expect(screen.queryByText(/NVIDIA_API_KEY=not-for-ui/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/GEMINI_API_KEY/i)).not.toBeInTheDocument();
  });
});

describe("CareerOS learning paths and demo-user restrictions", () => {
  it("blocks non-admin demo users from admin-only routes and navigation", () => {
    expect(canAccess("/skill-graph", "User")).toBe(false);
    expect(canAccess("/ops", "User")).toBe(false);
    expect(canAccess("/dashboard", "User")).toBe(true);

    const labels = getNavSections("User").flatMap((section) => section.items.map((item) => item.label));
    expect(labels).toContain("Demo RAG");
    expect(labels).not.toContain("Ops Center");
    expect(labels).not.toContain("Skill Graph");
  });

  it("displays authenticated learning resources with missing-skill and preparation context", async () => {
    localStorage.setItem("careeros_token", "demo-token");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          provider_health: {
            provider_mode: "seeded",
            trusted_sources: 1,
            status: "configured",
            message: "Synthetic demo resources loaded.",
            providers: [],
          },
          paths: [
            {
              skill_slug: "kubernetes",
              skill_name: "Kubernetes",
              priority: "high",
              resource_status: "available",
              reason: "Missing skill from opportunity match evidence.",
              estimated_hours: 3,
              refreshed_at: "2026-06-13T10:00:00Z",
              discovery_status: "verified",
              source_job_titles: ["Platform Engineer"],
              source_domains: ["kubernetes.io"],
              resource_count: 1,
              steps: [
                {
                  order_index: 1,
                  step_type: "learn",
                  title: "Kubernetes basics",
                  reason: "Preparation action for deployment gaps.",
                  estimated_minutes: 45,
                  practice_project: "Deploy the CareerOS API locally.",
                  resources: [
                    {
                      id: 1,
                      skill_slug: "kubernetes",
                      title: "Kubernetes Documentation",
                      provider: "Official Docs",
                      source_type: "documentation",
                      source_url: "https://kubernetes.io/docs/",
                      channel_name: "Kubernetes",
                      is_free: true,
                      price_status: "free",
                      last_verified_at: "2026-06-13T10:00:00Z",
                      trust_score: 0.95,
                      source_domain: "kubernetes.io",
                    },
                  ],
                },
              ],
            },
          ],
        }),
      }),
    );

    render(<LearningPathsPanel skillSlugs={["kubernetes"]} limit={1} />);

    expect(await screen.findByText("Kubernetes")).toBeInTheDocument();
    expect(screen.getByText(/Missing skill from opportunity match evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Preparation action for deployment gaps/i)).toBeInTheDocument();
    expect(screen.getByText("Kubernetes Documentation")).toBeInTheDocument();
  });
});
