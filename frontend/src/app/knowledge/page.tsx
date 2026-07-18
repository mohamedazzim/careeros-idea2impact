"use client";
import { useCareerOS } from '@/hooks/useCareerOS';
import KnowledgeHub from '@/components/KnowledgeHub';
import { useRouter } from 'next/navigation';

export default function KnowledgePage() {
  const router = useRouter();
  const {
    documents,
    activeDocId,
    setActiveDocId,
    isUploading,
    uploadResume,
    deleteDoc,
    setActiveTab,
    fetchDocumentById,
  } = useCareerOS();

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <KnowledgeHub
        documents={documents}
        activeId={activeDocId}
        isUploading={isUploading}
        onUpload={uploadResume}
        onDelete={deleteDoc}
        onSelect={setActiveDocId}
        onPreviewDocument={fetchDocumentById}
        onAnalyzeTab={() => {
          setActiveTab('dashboard');
          router.push('/dashboard');
        }}
      />
    </div>
  );
}
