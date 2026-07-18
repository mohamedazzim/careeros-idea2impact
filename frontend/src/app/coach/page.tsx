"use client";
import { useCareerOS } from '@/hooks/useCareerOS';
import InterviewCoachView from '@/components/InterviewCoachView';
import CareerCoachDashboard from '@/components/CareerCoachDashboard';

export default function CoachPage() {
  const { token, activeDocId } = useCareerOS();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <CareerCoachDashboard />
      <InterviewCoachView token={token} activeDocId={activeDocId} />
    </div>
  );
}
