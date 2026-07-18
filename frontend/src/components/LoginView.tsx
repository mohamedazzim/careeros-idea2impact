/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { ShieldCheck, KeyRound, Mail, ArrowRight } from 'lucide-react';

interface Props {
  onLogin: (email: string, passwordString: string) => Promise<boolean | string>;
  onRegister: (email: string, passwordString: string) => Promise<boolean | string>;
}

export default function LoginView({ onLogin, onRegister }: Props) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setLocalError(null);
    if (!email || !password) {
      setLocalError('All fields are required.');
      setIsLoading(false);
      return;
    }

    let success: boolean | string = false;
    if (isRegister) {
      success = await onRegister(email, password);
    } else {
      success = await onLogin(email, password);
    }
    if (success !== true) {
      setLocalError(
        typeof success === 'string'
          ? success
          : isRegister
            ? 'Registration failed. Try a different email or retry in a moment.'
            : 'Login failed. Check your email and password and try again.'
      );
    }
    setIsLoading(false);
  };

  return (
    <div className="min-h-[85vh] flex flex-col items-center justify-center p-4" id="login-view">
      <div className="max-w-md w-full bg-white rounded-3xl border border-slate-100 shadow-xl overflow-hidden relative">
        {/* Ambient Top Glow Decorator */}
        <div className="absolute top-0 right-0 left-0 h-1.5 bg-indigo-650" />

        <div className="p-8 space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center h-12 w-12 bg-slate-900 text-white rounded-2xl mb-2">
              <ShieldCheck className="h-6 w-6 text-emerald-400" />
            </div>
            <h1 className="text-2xl font-display font-bold text-slate-950 tracking-tight">CareerOS AI Workspace</h1>
            <p className="text-xs text-slate-500 max-w-xs mx-auto">Sign in to continue your resume intelligence, opportunity tracking, and coaching workflow.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {localError && (
              <div className="p-3 bg-rose-50 border border-rose-100 rounded-xl text-rose-800 text-xs text-center font-medium">
                {localError}
              </div>
            )}

            <div>
              <label htmlFor="login-email-input" className="block text-xs font-semibold text-slate-700 uppercase tracking-widest mb-1.5">Email Address</label>
              <div className="relative">
                <input
                  id="login-email-input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-2xl focus:outline-hidden focus:ring-2 focus:ring-slate-850 focus:border-transparent transition-all"
                  placeholder="candidate@example.com"
                  required
                />
                <Mail className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400" />
              </div>
            </div>

            <div>
              <label htmlFor="login-password-input" className="block text-xs font-semibold text-slate-700 uppercase tracking-widest mb-1.5">Secure Password</label>
              <div className="relative">
                <input
                  id="login-password-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-2xl focus:outline-hidden focus:ring-2 focus:ring-slate-850 focus:border-transparent transition-all"
                  placeholder="••••••••"
                  required
                />
                <KeyRound className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400" />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 bg-slate-950 hover:bg-slate-850 text-white font-display font-semibold rounded-2xl shadow-md text-sm transition-all flex items-center justify-center gap-2"
            >
              {isLoading ? 'Verifying authentication...' : isRegister ? 'Register & Generate Account' : 'Authenticate Credentials'}
              <ArrowRight className="h-4 w-4 text-slate-300" />
            </button>
          </form>

          {/* View Toggler */}
          <div className="text-center">
            <button
              onClick={() => setIsRegister(!isRegister)}
              type="button"
              className="text-xs text-indigo-600 hover:text-indigo-800 transition-all font-medium font-sans hover:underline"
            >
              {isRegister ? 'Already registered? Sign in securely' : 'Need corporate access? Register a new workspace'}
            </button>
            <div className="mt-2">
              <Link href="/forgot-password" className="text-xs text-slate-400 hover:text-indigo-400 transition">
                Forgot your password?
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
