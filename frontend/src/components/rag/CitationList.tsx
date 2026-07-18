"use client";

import type { DemoRagCitation } from "@/types/demo-rag";

interface CitationListProps {
  citations: DemoRagCitation[];
}

export default function CitationList({ citations }: CitationListProps) {
  if (!citations.length) {
    return (
      <p className="text-xs text-slate-500">
        No citations returned.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {citations.map((citation, index) => (
        <div
          key={`${citation.source_path}-${citation.section_title}-${index}`}
          className="rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-cyan-300">
                {citation.doc_name}
              </p>
              <p className="mt-1 text-sm text-slate-200">
                {citation.section_title}
              </p>
            </div>
            <span className="rounded-full border border-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-300">
              {(citation.score || 0).toFixed(2)}
            </span>
          </div>
          <p className="mt-2 break-all text-xs uppercase tracking-[0.18em] text-slate-500">
            {citation.source_path}
          </p>
        </div>
      ))}
    </div>
  );
}

