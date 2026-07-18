"use client";

import { useEffect, useMemo, useState } from "react";
import { Ban, CheckCircle2, Clock3, MessageSquareText, Play, PlusCircle, RefreshCw, Rocket, Star } from "lucide-react";
import {
  abandonLearningResource,
  completeLearningResource,
  openLearningResource,
  startLearningResource,
  submitLearningFeedback,
  updateLearningProgress,
} from "@/lib/learning-outcomes";
import type { LearningResource, LearningTrackingActionResponse } from "@/types";

type LearningOutcomeControlsProps = {
  resource: LearningResource;
  jobId?: number | null;
  sourceUi?: string;
  compact?: boolean;
};

const SESSION_KEY_PREFIX = "careeros_learning_session_";

function sessionStorageKey(resourceId: number): string {
  return `${SESSION_KEY_PREFIX}${resourceId}`;
}

function formatDate(value?: string | null): string {
  if (!value) return "n/a";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "n/a" : date.toLocaleString();
}

function truncateSession(sessionUid?: string | null): string {
  if (!sessionUid) return "n/a";
  return sessionUid.length > 12 ? `${sessionUid.slice(0, 6)}...${sessionUid.slice(-4)}` : sessionUid;
}

function isOutcomeTracked(status?: string | null): boolean {
  return status === "sufficient_data" || status === "tracked";
}

export default function LearningOutcomeControls({
  resource,
  jobId = null,
  sourceUi = "learning_panel",
  compact = false,
}: LearningOutcomeControlsProps) {
  const storageKey = useMemo(() => sessionStorageKey(resource.id), [resource.id]);
  const [sessionUid, setSessionUid] = useState<string | null>(null);
  const [completionPercentage, setCompletionPercentage] = useState<number>(
    Number(resource.outcome_summary?.average_completion_percentage ?? 0),
  );
  const [feedbackVisible, setFeedbackVisible] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState<string>("5");
  const [feedbackHelpful, setFeedbackHelpful] = useState<string>("4");
  const [feedbackRecommend, setFeedbackRecommend] = useState<boolean>(true);
  const [feedbackComment, setFeedbackComment] = useState("");
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [latestOutcome, setLatestOutcome] = useState(resource.outcome_summary ?? null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(resource.outcome_summary?.last_calculated_at ?? null);

  useEffect(() => {
    setLatestOutcome(resource.outcome_summary ?? null);
    setLastUpdatedAt(resource.outcome_summary?.last_calculated_at ?? null);
    setCompletionPercentage(Number(resource.outcome_summary?.average_completion_percentage ?? 0));
  }, [resource.outcome_summary]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = window.localStorage.getItem(storageKey);
      if (saved) {
        setSessionUid(saved);
      }
    } catch {
      // Ignore storage failures.
    }
  }, [storageKey]);

  const persistSession = (nextSessionUid?: string | null) => {
    if (!nextSessionUid) return;
    setSessionUid(nextSessionUid);
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(storageKey, nextSessionUid);
    } catch {
      // Ignore storage failures.
    }
  };

  const syncFromResponse = (response: LearningTrackingActionResponse) => {
    if (response.session?.session_uid) {
      persistSession(response.session.session_uid);
    }
    if (typeof response.session?.completion_percentage === "number") {
      setCompletionPercentage(response.session.completion_percentage);
    }
    if (response.outcome) {
      setLatestOutcome(response.outcome);
      setLastUpdatedAt(response.outcome.last_calculated_at ?? null);
    }
    if (response.message) {
      setMessage(response.message);
    }
    if (response.insufficient_data && !response.outcome) {
      setMessage("Outcome tracking is still building evidence for this resource.");
    }
  };

  const withAction = async (label: string, handler: () => Promise<LearningTrackingActionResponse>) => {
    setLoadingAction(label);
    setError(null);
    setMessage(null);
    try {
      const response = await handler();
      syncFromResponse(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update learning progress right now.");
    } finally {
      setLoadingAction(null);
    }
  };

  const buildRequest = () => ({
    job_id: jobId ?? undefined,
    skill_slug: resource.skill_slug,
    source_ui: sourceUi,
    external_resource_url: resource.source_url,
    metadata: {
      source_domain: resource.source_domain,
      verification_status: resource.verification_status,
      price_status: resource.price_status,
    },
  });

  const ensureSession = async (): Promise<string | null> => {
    if (sessionUid) {
      return sessionUid;
    }
    const started = await startLearningResource(resource.id, buildRequest());
    syncFromResponse(started);
    return started.session?.session_uid ?? null;
  };

  const handleOpen = () => withAction("open", async () => openLearningResource(resource.id, buildRequest()));

  const handleStart = () => withAction("start", async () => startLearningResource(resource.id, buildRequest()));

  const handleProgress = () =>
    withAction("progress", async () => {
      const activeSession = await ensureSession();
      if (!activeSession) {
        throw new Error("A session could not be created for this resource.");
      }
      const nextPercentage = Math.min(100, Math.max(0, completionPercentage + 10));
      setCompletionPercentage(nextPercentage);
      return updateLearningProgress(activeSession, {
        completion_percentage: nextPercentage,
        notes: `Updated from ${sourceUi}`,
        metadata: {
          source_ui: sourceUi,
          resource_title: resource.title,
        },
      });
    });

  const handleComplete = () =>
    withAction("complete", async () => {
      const activeSession = await ensureSession();
      if (!activeSession) {
        throw new Error("A session could not be created for this resource.");
      }
      return completeLearningResource(activeSession, {
        notes: `Completed from ${sourceUi}`,
        metadata: {
          source_ui: sourceUi,
          resource_title: resource.title,
        },
      });
    });

  const handleAbandon = () =>
    withAction("abandon", async () => {
      const activeSession = await ensureSession();
      if (!activeSession) {
        throw new Error("A session could not be created for this resource.");
      }
      return abandonLearningResource(activeSession, {
        reason: "User stopped the resource from the panel.",
        notes: `Marked abandoned from ${sourceUi}`,
        metadata: {
          source_ui: sourceUi,
          resource_title: resource.title,
        },
      });
    });

  const handleFeedback = () =>
    withAction("feedback", async () => {
      const activeSession = await ensureSession();
      return submitLearningFeedback(resource.id, {
        session_uid: activeSession ?? undefined,
        rating: Number(feedbackRating),
        difficulty: resource.difficulty || undefined,
        would_recommend: feedbackRecommend,
        comment: feedbackComment.trim() || undefined,
        helpfulness_score: Number(feedbackHelpful),
        outcome_tag: latestOutcome?.status || undefined,
        metadata: {
          source_ui: sourceUi,
          resource_title: resource.title,
          session_uid: activeSession ?? null,
        },
      });
    });

  const tracked = isOutcomeTracked(latestOutcome?.status);
  const actionButtonClass = compact
    ? "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium transition"
    : "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-medium transition";

  return (
    <div className={`mt-3 rounded-xl border border-slate-200 bg-slate-50/70 ${compact ? "p-2 text-[11px]" : "p-3 text-xs"} text-slate-600 min-w-0 overflow-hidden`}>
      <div className="flex flex-col gap-3 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
            <Clock3 className="h-3 w-3" />
            {sessionUid ? `Session ${truncateSession(sessionUid)}` : "No session yet"}
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${
              tracked ? "border border-emerald-200 bg-emerald-50 text-emerald-700" : "border border-amber-200 bg-amber-50 text-amber-800"
            }`}
          >
            <CheckCircle2 className="h-3 w-3" />
            {tracked ? "Outcome tracked" : "Outcome not tracked"}
          </span>
          {latestOutcome?.status && (
            <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              {latestOutcome.status.replace(/_/g, " ")}
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void handleOpen()}
            disabled={loadingAction !== null}
            className={`${actionButtonClass} border-slate-200 bg-white text-slate-700 hover:border-indigo-300 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-50`}
          >
            <Play className="h-3.5 w-3.5" />
            Open
          </button>
          <button
            type="button"
            onClick={() => void handleStart()}
            disabled={loadingAction !== null}
            className={`${actionButtonClass} border-indigo-200 bg-indigo-50 text-indigo-700 hover:border-indigo-300 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-50`}
          >
            <Rocket className="h-3.5 w-3.5" />
            Start
          </button>
          <button
            type="button"
            onClick={() => void handleProgress()}
            disabled={loadingAction !== null}
            className={`${actionButtonClass} border-sky-200 bg-sky-50 text-sky-700 hover:border-sky-300 hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-50`}
          >
            <PlusCircle className="h-3.5 w-3.5" />
            +10%
          </button>
          <button
            type="button"
            onClick={() => void handleComplete()}
            disabled={loadingAction !== null}
            className={`${actionButtonClass} border-emerald-200 bg-emerald-50 text-emerald-700 hover:border-emerald-300 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50`}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            Complete
          </button>
          <button
            type="button"
            onClick={() => void handleAbandon()}
            disabled={loadingAction !== null}
            className={`${actionButtonClass} border-rose-200 bg-rose-50 text-rose-700 hover:border-rose-300 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50`}
          >
            <Ban className="h-3.5 w-3.5" />
            Abandon
          </button>
          <button
            type="button"
            onClick={() => setFeedbackVisible((current) => !current)}
            className={`${actionButtonClass} border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:text-slate-900`}
          >
            <MessageSquareText className="h-3.5 w-3.5" />
            Feedback
          </button>
        </div>

        <div className="grid gap-2 text-[11px] text-slate-600 sm:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 min-w-0 overflow-hidden">
            <p className="text-[10px] uppercase tracking-wider text-slate-400">Completion</p>
            <p className="font-semibold text-slate-900">{Math.round(completionPercentage)}%</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 min-w-0 overflow-hidden">
            <p className="text-[10px] uppercase tracking-wider text-slate-400">Outcome updated</p>
            <p className="font-semibold text-slate-900">{formatDate(lastUpdatedAt)}</p>
          </div>
        </div>

        {latestOutcome?.explanation && (
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-600 break-words">
            <p className="font-semibold text-slate-900">Why this matters</p>
            <p className="mt-1">{latestOutcome.explanation}</p>
            <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-wider text-slate-400">
              <span>{latestOutcome.started_count} started</span>
              <span>{latestOutcome.completion_count} completed</span>
              <span>{latestOutcome.feedback_count} feedback</span>
              <span>{latestOutcome.average_rating ? `Avg ${latestOutcome.average_rating.toFixed(1)}/5` : "No rating yet"}</span>
            </div>
          </div>
        )}

        {feedbackVisible && (
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="space-y-1">
                <span className="text-[10px] uppercase tracking-wider text-slate-400">Rating</span>
                <select
                  value={feedbackRating}
                  onChange={(event) => setFeedbackRating(event.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900"
                >
                  {["1", "2", "3", "4", "5"].map((value) => (
                    <option key={value} value={value}>
                      {value} / 5
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-[10px] uppercase tracking-wider text-slate-400">Helpfulness</span>
                <select
                  value={feedbackHelpful}
                  onChange={(event) => setFeedbackHelpful(event.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900"
                >
                  {["1", "2", "3", "4", "5"].map((value) => (
                    <option key={value} value={value}>
                      {value} / 5
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2">
                <input
                  type="checkbox"
                  checked={feedbackRecommend}
                  onChange={(event) => setFeedbackRecommend(event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                />
                <span className="text-[11px] text-slate-700">Would recommend</span>
              </label>
            </div>

            <label className="mt-3 block space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-slate-400">Comment</span>
              <textarea
                value={feedbackComment}
                onChange={(event) => setFeedbackComment(event.target.value)}
                rows={3}
                placeholder="What was useful, confusing, or missing?"
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-indigo-300"
              />
            </label>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => void handleFeedback()}
                disabled={loadingAction !== null}
                className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-[11px] font-medium text-indigo-700 transition hover:border-indigo-300 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loadingAction === "feedback" ? (
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Star className="h-3.5 w-3.5" />
                )}
                Submit feedback
              </button>
              <span className="text-[10px] uppercase tracking-wider text-slate-400">
                Feedback is stored against the current resource session where available.
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800 break-words">
            {error}
          </div>
        )}

        {message && !error && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[11px] text-emerald-800 break-words">
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
