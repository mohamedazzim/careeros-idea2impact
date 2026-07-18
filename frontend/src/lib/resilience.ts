/**
 * Frontend API Resilience Layer for CareerOS.
 *
 * Provides:
 * - Auto-retry with exponential backoff
 * - Loading state tracking
 * - Error state management
 * - Graceful degradation patterns
 *
 * Usage:
 *   import { resilientFetch, useResilientQuery } from '@/lib/resilience';
 *   const data = await resilientFetch('/api/v1/auth/login', { method: 'POST', body });
 */
const RETRY_MAX = 3;
const RETRY_BASE_DELAY_MS = 1000;
const RETRY_STATUS_CODES = [408, 429, 500, 502, 503, 504];

export interface ResilienceResult<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  retryCount: number;
  succeeded: boolean;
}

export interface ResilientFetchOptions extends RequestInit {
  maxRetries?: number;
  baseDelayMs?: number;
  onRetry?: (attempt: number, error: Error) => void;
}

// ── Stateful loading / error tracker per request key ────────────────
const pendingMap = new Map<string, Promise<Response>>();
const errorStateMap = new Map<string, { error: string; timestamp: number }>();

// Clear stale errors after 30 seconds
setInterval(() => {
  const now = Date.now();
  const keys = Array.from(errorStateMap.keys());
  for (const key of keys) {
    const val = errorStateMap.get(key);
    if (val && now - val.timestamp > 30_000) errorStateMap.delete(key);
  }
}, 10_000);

export function getRequestError(key: string): string | null {
  return errorStateMap.get(key)?.error ?? null;
}

export function getRequestLoading(key: string): boolean {
  return pendingMap.has(key);
}

export function clearRequestState(key: string): void {
  pendingMap.delete(key);
  errorStateMap.delete(key);
}

// ── Resilient fetch with retry ──────────────────────────────────────
export async function resilientFetch<T = unknown>(
  url: string,
  options: ResilientFetchOptions = {},
): Promise<ResilienceResult<T>> {
  const {
    maxRetries = RETRY_MAX,
    baseDelayMs = RETRY_BASE_DELAY_MS,
    onRetry,
    ...fetchOptions
  } = options;

  const requestKey = `${fetchOptions.method ?? 'GET'}:${url}`;
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers: {
          'Content-Type': 'application/json',
          ...fetchOptions.headers,
        },
      });

      if (response.ok) {
        pendingMap.delete(requestKey);
        errorStateMap.delete(requestKey);
        const data = response.status === 204 ? null : await response.json();
        return {
          data: data as T,
          error: null,
          loading: false,
          retryCount: attempt,
          succeeded: true,
        };
      }

      // Server errors — retryable
      if (RETRY_STATUS_CODES.includes(response.status) && attempt < maxRetries) {
        const delay = baseDelayMs * Math.pow(2, attempt);
        if (onRetry) onRetry(attempt + 1, new Error(`HTTP ${response.status}`));
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }

      // Client errors — don't retry
      const errorBody = await response.json().catch(() => ({ message: response.statusText }));
      const error = new Error(errorBody.message || `HTTP ${response.status}`);
      errorStateMap.set(requestKey, { error: error.message, timestamp: Date.now() });
      pendingMap.delete(requestKey);
      return {
        data: null,
        error,
        loading: false,
        retryCount: attempt,
        succeeded: false,
      };
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt < maxRetries) {
        const delay = baseDelayMs * Math.pow(2, attempt);
        if (onRetry) onRetry(attempt + 1, lastError);
        await new Promise((r) => setTimeout(r, delay));
      }
    }
  }

  const finalError = lastError ?? new Error('Request failed');
  errorStateMap.set(requestKey, { error: finalError.message, timestamp: Date.now() });
  pendingMap.delete(requestKey);
  return {
    data: null,
    error: finalError,
    loading: false,
    retryCount: maxRetries,
    succeeded: false,
  };
}

// ── Type-safe API client (wraps resilientFetch) ─────────────────────
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface ApiClientOptions {
  token?: string;
  maxRetries?: number;
}

export function createApiClient(
  defaultOptions: ApiClientOptions = {},
) {
  const { token } = defaultOptions;

  function authHeaders(): Record<string, string> {
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
  }

  return {
    get<T = unknown>(path: string, opts?: ResilientFetchOptions): Promise<ResilienceResult<T>> {
      return resilientFetch<T>(`${BASE_URL}${path}`, {
        ...opts,
        method: 'GET',
        headers: { ...authHeaders(), ...(opts?.headers as Record<string, string> | undefined) },
        maxRetries: opts?.maxRetries ?? defaultOptions.maxRetries,
      });
    },

    post<T = unknown>(path: string, body?: unknown, opts?: ResilientFetchOptions): Promise<ResilienceResult<T>> {
      return resilientFetch<T>(`${BASE_URL}${path}`, {
        ...opts,
        method: 'POST',
        body: body ? JSON.stringify(body) : undefined,
        headers: { ...authHeaders(), ...(opts?.headers as Record<string, string> | undefined) },
        maxRetries: opts?.maxRetries ?? defaultOptions.maxRetries,
      });
    },

    put<T = unknown>(path: string, body?: unknown, opts?: ResilientFetchOptions): Promise<ResilienceResult<T>> {
      return resilientFetch<T>(`${BASE_URL}${path}`, {
        ...opts,
        method: 'PUT',
        body: body ? JSON.stringify(body) : undefined,
        headers: { ...authHeaders(), ...(opts?.headers as Record<string, string> | undefined) },
        maxRetries: opts?.maxRetries ?? defaultOptions.maxRetries,
      });
    },

    delete<T = unknown>(path: string, opts?: ResilientFetchOptions): Promise<ResilienceResult<T>> {
      return resilientFetch<T>(`${BASE_URL}${path}`, {
        ...opts,
        method: 'DELETE',
        headers: { ...authHeaders(), ...(opts?.headers as Record<string, string> | undefined) },
        maxRetries: opts?.maxRetries ?? defaultOptions.maxRetries,
      });
    },

    get baseUrl() { return BASE_URL; },
    get token() { return token; },
  };
}

// Singleton API client — update token via setAuthToken when user logs in
let _apiClient = createApiClient();

export function getApiClient() {
  return _apiClient;
}

export function setAuthToken(token: string | null) {
  _apiClient = createApiClient({ token: token ?? undefined });
}

// ── React hook for resilient queries ────────────────────────────────
export function useResilientQuery<T>(url: string, token?: string) {
  const client = createApiClient({ token });
  return {
    get: () => client.get<T>(url),
    post: (body?: unknown) => client.post<T>(url, body),
  };
}
