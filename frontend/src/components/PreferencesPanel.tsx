/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { UserPreferences } from '../types';
import { Bell, KeyRound, EyeOff, ShieldAlert, CheckCircle2, AlertCircle } from 'lucide-react';


const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
interface Props {
  preferences: UserPreferences;
  onUpdate: (p: Partial<UserPreferences>) => Promise<boolean>;
}

export default function PreferencesPanel({ preferences, onUpdate }: Props) {
  const [threshold, setThreshold] = useState(preferences.alert_threshold);
  const [email, setEmail] = useState(preferences.notification_email);
  const [quietStart, setQuietStart] = useState(preferences.quiet_hours_start);
  const [quietEnd, setQuietEnd] = useState(preferences.quiet_hours_end);
  const [isSaving, setIsSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(false);
  const workspaceInitials = (preferences.notification_email || "CareerOS")
    .split("@")[0]
    .split(/[._-]+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSuccess(false);
    setError(false);
    const ok = await onUpdate({
      alert_threshold: threshold,
      notification_email: email,
      quiet_hours_start: quietStart,
      quiet_hours_end: quietEnd
    });
    setIsSaving(false);
    if (ok) {
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } else {
      setError(true);
      setTimeout(() => setError(false), 5000);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6" id="preferences-panel">
      {/* Back Header */}
      <div>
        <h2 className="text-2xl font-display font-semibold text-slate-950 tracking-tight">System Preferences</h2>
        <p className="text-sm text-slate-500 font-sans mt-1">Configure your personal thresholds, privacy rules, and integration defaults.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left pane: Profile Card */}
        <div className="bg-white rounded-2xl border border-slate-100 p-6 space-y-6 shadow-xs">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 bg-slate-100 rounded-full flex items-center justify-center font-display font-medium text-slate-800">
              {workspaceInitials}
            </div>
            <div>
              <h3 className="font-display font-semibold text-slate-800">Candidate Workspace</h3>
              <p className="text-xs text-slate-400 font-mono">{preferences.notification_email || "Notification email not configured"}</p>
            </div>
          </div>

          <div className="h-px bg-slate-100" />

          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <ShieldAlert className="h-5 w-5 text-indigo-500 mt-0.5 shrink-0" />
              <div>
                <h4 className="text-xs font-semibold text-slate-700">Security Guard (GLiNER)</h4>
                <p className="text-xs text-slate-500 mt-0.5">Automated PII sanitation strips telephone, exact address coordinates, and emails beforehand.</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Bell className="h-5 w-5 text-amber-500 mt-0.5 shrink-0" />
              <div>
                <h4 className="text-xs font-semibold text-slate-700">Match Notifications</h4>
                <p className="text-xs text-slate-500 mt-0.5">Receive structured job match digests straight to your notification email.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right pane: Form */}
        <form onSubmit={handleSave} className="md:col-span-2 bg-white rounded-2xl border border-slate-100 p-6 space-y-6 shadow-xs">
          {success && (
            <div className="bg-emerald-50 border border-emerald-100 text-emerald-800 p-4 rounded-xl flex items-center gap-3 text-sm">
              <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
              <span>Preferences saved and synced successfully to direct profile.</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-xl flex items-center gap-3 text-sm">
              <AlertCircle className="h-5 w-5 text-red-600 shrink-0" />
              <span>Failed to save preferences. Please try again.</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="pref-email-input" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Notification Email</label>
              <input
                id="pref-email-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2 text-sm border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-slate-800 focus:border-transparent transition-all"
                placeholder="email@example.com"
              />
            </div>

            <div>
              <label htmlFor="pref-threshold-input" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Alert Threshold Match Score</label>
              <div className="flex items-center gap-3">
                <input
                  id="pref-threshold-input"
                  type="range"
                  min="50"
                  max="100"
                  value={threshold}
                  onChange={(e) => setThreshold(parseInt(e.target.value))}
                  className="w-full h-1.5 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-slate-800 focus:outline-hidden"
                />
                <span className="text-sm font-semibold text-slate-800 font-mono w-10 text-right">{threshold}%</span>
              </div>
            </div>
          </div>

          <div className="h-px bg-slate-100" />

          {/* Quiet Hours */}
          <div>
            <h4 className="text-sm font-display font-semibold text-slate-800 mb-2">Focus & Quiet Hours</h4>
            <p className="text-xs text-slate-500 mb-4">Mute alerts and RAG alignment processing notifications during focus intervals.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="pref-quiet-start-input" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Quiet Hours Start</label>
                <input
                  id="pref-quiet-start-input"
                  type="time"
                  value={quietStart}
                  onChange={(e) => setQuietStart(e.target.value)}
                  className="w-full px-4 py-2 text-sm border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-slate-800 transition-all"
                />
              </div>

              <div>
                <label htmlFor="pref-quiet-end-input" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Quiet Hours End</label>
                <input
                  id="pref-quiet-end-input"
                  type="time"
                  value={quietEnd}
                  onChange={(e) => setQuietEnd(e.target.value)}
                  className="w-full px-4 py-2 text-sm border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-slate-800 transition-all"
                />
              </div>
            </div>
          </div>

          <div className="h-px bg-slate-100" />

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={isSaving}
              className="px-6 py-2.5 bg-slate-900 border border-slate-850 hover:bg-slate-850 text-white rounded-xl text-sm font-display font-medium transition-all disabled:opacity-50"
            >
              {isSaving ? 'Saving Changes...' : 'Save Configuration'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
