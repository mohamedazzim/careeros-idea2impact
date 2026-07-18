"use client";

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { clearAuthSession, getAuthSessionState } from '@/lib/auth-session';

const PUBLIC_ROUTES = new Set(['/login', '/register', '/forgot-password', '/reset-password']);

export default function SessionMonitor() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (PUBLIC_ROUTES.has(pathname)) return;

    let timer: ReturnType<typeof setTimeout> | null = null;
    let poller: ReturnType<typeof setInterval> | null = null;

    const redirectToLogin = () => {
      clearAuthSession();
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}&reason=session_expired`);
    };

    const scheduleLogout = () => {
      if (timer) clearTimeout(timer);
      const { token, expiresAt } = getAuthSessionState();
      if (!token) {
        redirectToLogin();
        return;
      }
      if (!expiresAt) return;

      const delay = expiresAt - Date.now();
      if (delay <= 0) {
        redirectToLogin();
        return;
      }

      timer = setTimeout(redirectToLogin, delay);
    };

    const verifySession = async () => {
      const { token } = getAuthSessionState();
      if (!token) {
        redirectToLogin();
        return;
      }
      try {
        const res = await fetch('/api/v1/auth/me', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (res.status === 401 || res.status === 403) {
          redirectToLogin();
        }
      } catch {
        // Keep the scheduled expiry path as the primary authority.
      }
    };

    const handleStorage = (event: StorageEvent) => {
      if (event.key && event.key !== 'careeros_token') return;
      scheduleLogout();
    };

    scheduleLogout();
    verifySession();
    poller = setInterval(verifySession, 60000);

    window.addEventListener('storage', handleStorage);
    window.addEventListener('focus', verifySession);
    window.addEventListener('visibilitychange', verifySession);

    return () => {
      if (timer) clearTimeout(timer);
      if (poller) clearInterval(poller);
      window.removeEventListener('storage', handleStorage);
      window.removeEventListener('focus', verifySession);
      window.removeEventListener('visibilitychange', verifySession);
    };
  }, [pathname, router]);

  return null;
}
