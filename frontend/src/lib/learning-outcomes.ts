import { readAuthToken } from "@/lib/auth-session";
import type {
  LearningAbandonRequest,
  LearningActivityListResponse,
  LearningCompletionRequest,
  LearningFeedbackRequest,
  LearningOutcomeListResponse,
  LearningProgressRequest,
  LearningResourceOutcomeResponse,
  LearningResourceTrackingRequest,
  LearningTrackingActionResponse,
} from "@/types";

const API_BASE = (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) || "/api/v1";

function ensureTrailingSlash(base: string): string {
  return base.endsWith("/") ? base.slice(0, -1) : base;
}

async function parseJsonResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const record = payload as Record<string, unknown>;
  if (typeof record.message === "string" && record.message.trim()) return record.message.trim();
  if (typeof record.detail === "string" && record.detail.trim()) return record.detail.trim();
  return fallback;
}

export class LearningOutcomeApiError extends Error {
  status: number;
  code?: string;
  loginRequired: boolean;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "LearningOutcomeApiError";
    this.status = status;
    this.code = code;
    this.loginRequired = status === 401 || status === 403;
  }
}

function requireAuthToken(): string {
  const token = readAuthToken();
  if (!token) {
    throw new LearningOutcomeApiError("Sign in to track learning outcomes.", 401, "AUTH_REQUIRED");
  }
  return token;
}

async function postLearningAction<T>(path: string, body: unknown): Promise<T> {
  const token = requireAuthToken();
  const response = await fetch(`${ensureTrailingSlash(API_BASE)}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body ?? {}),
  });
  const payload = await parseJsonResponse(response);
  if (!response.ok) {
    throw new LearningOutcomeApiError(
      extractErrorMessage(payload, "The learning outcome service is temporarily unavailable."),
      response.status,
      payload && typeof payload === "object" && "code" in payload ? String((payload as Record<string, unknown>).code ?? "") : undefined,
    );
  }
  return payload as T;
}

async function getLearningAction<T>(path: string): Promise<T> {
  const token = requireAuthToken();
  const response = await fetch(`${ensureTrailingSlash(API_BASE)}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  const payload = await parseJsonResponse(response);
  if (!response.ok) {
    throw new LearningOutcomeApiError(
      extractErrorMessage(payload, "The learning outcome service is temporarily unavailable."),
      response.status,
      payload && typeof payload === "object" && "code" in payload ? String((payload as Record<string, unknown>).code ?? "") : undefined,
    );
  }
  return payload as T;
}

export async function openLearningResource(resourceId: number, request: LearningResourceTrackingRequest = {}): Promise<LearningTrackingActionResponse> {
  return postLearningAction<LearningTrackingActionResponse>(`/learning/resources/${resourceId}/open`, request);
}

export async function startLearningResource(resourceId: number, request: LearningResourceTrackingRequest = {}): Promise<LearningTrackingActionResponse> {
  return postLearningAction<LearningTrackingActionResponse>(`/learning/resources/${resourceId}/start`, request);
}

export async function updateLearningProgress(sessionUid: string, request: LearningProgressRequest): Promise<LearningTrackingActionResponse> {
  return postLearningAction<LearningTrackingActionResponse>(`/learning/sessions/${sessionUid}/progress`, request);
}

export async function completeLearningResource(sessionUid: string, request: LearningCompletionRequest = {}): Promise<LearningTrackingActionResponse> {
  return postLearningAction<LearningTrackingActionResponse>(`/learning/sessions/${sessionUid}/complete`, request);
}

export async function abandonLearningResource(sessionUid: string, request: LearningAbandonRequest = {}): Promise<LearningTrackingActionResponse> {
  return postLearningAction<LearningTrackingActionResponse>(`/learning/sessions/${sessionUid}/abandon`, request);
}

export async function submitLearningFeedback(resourceId: number, request: LearningFeedbackRequest = {}): Promise<LearningTrackingActionResponse> {
  return postLearningAction<LearningTrackingActionResponse>(`/learning/resources/${resourceId}/feedback`, request);
}

export async function getLearningResourceOutcome(resourceId: number): Promise<LearningResourceOutcomeResponse> {
  return getLearningAction<LearningResourceOutcomeResponse>(`/learning/resources/${resourceId}/outcome`);
}

export async function listLearningOutcomes(query?: Record<string, string | number | undefined | null>): Promise<LearningOutcomeListResponse> {
  const params = new URLSearchParams();
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    params.set(key, String(value));
  });
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return getLearningAction<LearningOutcomeListResponse>(`/learning/outcomes${suffix}`);
}

export async function listLearningActivity(query?: Record<string, string | number | undefined | null>): Promise<LearningActivityListResponse> {
  const params = new URLSearchParams();
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    params.set(key, String(value));
  });
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return getLearningAction<LearningActivityListResponse>(`/learning/activity${suffix}`);
}
