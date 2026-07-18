"use client";
import { useCareerOS } from '@/hooks/useCareerOS';
import PreferencesPanel from '@/components/PreferencesPanel';

export default function PreferencesPage() {
  const { preferences, updatePreferences } = useCareerOS();

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <PreferencesPanel preferences={preferences} onUpdate={updatePreferences} />
    </div>
  );
}
