"use client";
import { useCareerOS } from '@/hooks/useCareerOS';
import LoginView from '@/components/LoginView';
import { useSearchParams } from 'next/navigation';

export default function LoginPage() {
  const { login, register, token } = useCareerOS();
  const searchParams = useSearchParams();
  const requestedRedirect = searchParams.get('redirect');
  const destination = requestedRedirect?.startsWith('/') && !requestedRedirect.startsWith('//')
    ? requestedRedirect
    : '/dashboard';

  const loginAndRedirect = async (email: string, password: string) => {
    const success = await login(email, password);
    if (success === true && typeof window !== 'undefined') window.location.replace(destination);
    return success;
  };

  const registerAndRedirect = async (email: string, password: string) => {
    const success = await register(email, password);
    if (success === true && typeof window !== 'undefined') window.location.replace('/knowledge');
    return success;
  };

  if (token) return <div className="min-h-screen bg-slate-950" aria-busy="true" />;

  return (
    <div className="min-h-screen bg-slate-950">
      <LoginView onLogin={loginAndRedirect} onRegister={registerAndRedirect} />
    </div>
  );
}
