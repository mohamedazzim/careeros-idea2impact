"use client";
import { useCareerOS } from '@/hooks/useCareerOS';
import JobsIntelligenceView from '@/components/JobsIntelligenceView';

export default function JobsPage() {
  const { token, activeDocId, setActiveDocId, documents, refreshDocs, generatePackage, isGeneratingPackage } = useCareerOS();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <JobsIntelligenceView
        token={token}
        activeDocId={activeDocId}
        documents={documents}
        onRefreshDocs={refreshDocs}
        onGeneratePackage={generatePackage}
        isGenerating={isGeneratingPackage}
        onSelectDoc={setActiveDocId}
      />
    </div>
  );
}
