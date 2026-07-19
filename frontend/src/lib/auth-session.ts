export type AuthSessionState = {
  token: string | null;
  expiresAt: number | null;
};

export function readAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem('careeros_token');
  } catch {
    return null;
  }
}

export function decodeTokenExpiry(token: string | null): number | null {
  if (!token) return null;
  try {
    const payload = decodeAuthTokenPayload(token);
    if (!payload || typeof payload.exp !== 'number') return null;
    return payload.exp * 1000;
  } catch {
    return null;
  }
}

export function decodeAuthTokenPayload(token: string | null): Record<string, unknown> | null {
  if (!token) return null;
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=');
    return JSON.parse(atob(padded)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function readAuthUserStorageScope(token: string | null = readAuthToken()): string {
  const payload = decodeAuthTokenPayload(token);
  const subject = typeof payload?.sub === 'string' ? payload.sub.trim() : '';
  return subject ? `user_${subject}` : 'unknown_user';
}

export function clearAuthSession(): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem('careeros_token');
    sessionStorage.clear();
  } catch {
    // Ignore storage failures during logout cleanup.
  }
  document.cookie = 'careeros_token=; path=/; max-age=0; SameSite=Lax';
}

export function getAuthSessionState(): AuthSessionState {
  const token = readAuthToken();
  return {
    token,
    expiresAt: decodeTokenExpiry(token),
  };
}
