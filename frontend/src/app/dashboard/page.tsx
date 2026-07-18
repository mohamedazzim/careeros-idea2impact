"use client";
import { useCareerOS } from '@/hooks/useCareerOS';
import DashboardView from '@/components/DashboardView';

export default function DashboardPage() {
  const {
    documents,
    activeDocId,
    setActiveDocId,
    activeRun,
    isAnalyzing,
    triggerRAGAnalysis,
  } = useCareerOS();

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <DashboardView
        documents={documents}
        activeDocId={activeDocId}
        activeRun={activeRun}
        isAnalyzing={isAnalyzing}
        onAnalyze={triggerRAGAnalysis}
        onSelectDoc={setActiveDocId}
      />
    </div>
  );
}
