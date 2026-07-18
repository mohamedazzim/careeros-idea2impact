/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useRef } from 'react';
import { KnowledgeDoc } from '../types';
import { UploadCloud, FileText, Trash2, ClipboardPaste, Eye, Lock, ShieldCheck, Cpu, AlertCircle, RefreshCw } from 'lucide-react';
import { formatDateOnly } from '@/lib/datetime';

interface Props {
  documents: KnowledgeDoc[];
  activeId: string | null;
  isUploading: boolean;
  onUpload: (filename: string, content: string, fileBase64?: string) => Promise<string | null>;
  onDelete: (id: string) => Promise<void>;
  onSelect: (id: string) => void;
  onPreviewDocument: (id: string) => Promise<KnowledgeDoc | null>;
  onAnalyzeTab: () => void;
}

export default function KnowledgeHub({
  documents,
  activeId,
  isUploading,
  onUpload,
  onDelete,
  onSelect,
  onPreviewDocument,
  onAnalyzeTab
}: Props) {
  const [pasteText, setPasteText] = useState('');
  const [pasteName, setPasteName] = useState('');
  const [isPasting, setIsPasting] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activeDocPreview, setActiveDocPreview] = useState<KnowledgeDoc | null>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const processFile = async (file: File) => {
    const reader = new FileReader();
    reader.onload = async () => {
      let base64 = '';
      let text = '';
      if (file.name.endsWith('.txt')) {
        text = reader.result as string;
        await onUpload(file.name, text);
      } else {
        // PDF or DOCX: parse as base64 for Claude Sonnet 4.6 OCR document processing on the server
        const base64String = (reader.result as string).split(',')[1];
        await onUpload(file.name, 'Extracting document binary securely...', base64String);
      }
    };

    if (file.name.endsWith('.txt')) {
      reader.readAsText(file);
    } else {
      reader.readAsDataURL(file);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const handlePasteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pasteText.trim()) return;
    const name = pasteName.trim() || 'My Pasted Resume';
    const filename = name.endsWith('.txt') ? name : `${name}.txt`;
    const docId = await onUpload(filename, pasteText);
    if (docId) {
      setPasteText('');
      setPasteName('');
      setIsPasting(false);
    }
  };

  const getStatusBadge = (status: KnowledgeDoc['status']) => {
    switch (status) {
      case 'uploaded':
      case 'processing':
        return <span className="px-2 py-0.5 text-xs font-mono rounded-full bg-slate-100 text-slate-800 flex items-center gap-1"><RefreshCw className="h-3 w-3 animate-spin"/> Uploaded</span>;
      case 'ingested':
        return <span className="px-2 py-0.5 text-xs font-mono rounded-full bg-cyan-50 text-cyan-800 flex items-center gap-1"><RefreshCw className="h-3 w-3 animate-spin"/> Ingesting</span>;
      case 'stripping_pii':
      case 'masking_pii':
        return <span className="px-2 py-0.5 text-xs font-mono rounded-full bg-indigo-50 text-indigo-800 flex items-center gap-1"><Lock className="h-3 w-3 animate-pulse"/> GLiNER Mask</span>;
      case 'embedding':
      case 'chunking_and_embedding':
      case 'persisting_chunks':
      case 'indexing':
      case 'evaluating':
        return <span className="px-2 py-0.5 text-xs font-mono rounded-full bg-purple-50 text-purple-800 flex items-center gap-1"><Cpu className="h-3 w-3 animate-pulse"/> Tensor Embed</span>;
      case 'indexed':
      case 'analyzed':
        return <span className="px-2 py-0.5 text-xs font-mono rounded-full bg-emerald-50 text-emerald-800 flex items-center gap-1"><ShieldCheck className="h-3 w-3"/> Indexed</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-mono rounded-full bg-rose-50 text-rose-800 flex items-center gap-1"><AlertCircle className="h-3 w-3"/> Ingestion Failed</span>;
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8" id="knowledge-hub">
      {/* Upload Column */}
      <div className="lg:col-span-1 space-y-6">
        <div>
          <h2 className="text-xl font-display font-semibold text-slate-950">Add Document</h2>
          <p className="text-xs text-slate-500 mt-1">Accepts Resume documents as TXT, PDF, Word, or raw copied blocks.</p>
        </div>

        {/* Toggle Option */}
        <div className="flex bg-slate-100 p-1 rounded-xl">
          <button
            onClick={() => setIsPasting(false)}
            className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${!isPasting ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'}`}
          >
            File Upload
          </button>
          <button
            onClick={() => setIsPasting(true)}
            className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${isPasting ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'}`}
          >
            Direct Copy-Paste
          </button>
        </div>

        {!isPasting ? (
          /* Drag & Drop Card */
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
              dragOver ? 'border-indigo-500 bg-indigo-50/20' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept=".pdf,.txt,.docx"
              className="hidden"
            />
            {isUploading ? (
              <div className="space-y-3 flex flex-col items-center">
                <RefreshCw className="h-10 w-10 text-indigo-500 animate-spin" />
                <p className="text-sm font-medium text-slate-800">Processing Document Pipeline...</p>
                <p className="text-xs text-slate-500">Extracting structure, masking PII & running vector embed workflows.</p>
              </div>
            ) : (
              <div className="space-y-3 flex flex-col items-center">
                <div className="h-12 w-12 rounded-xl bg-slate-100 flex items-center justify-center">
                  <UploadCloud className="h-6 w-6 text-slate-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-800">Drag & Drop Resume</p>
                  <p className="text-xs text-slate-500 mt-1">PDF, DOCX, or TXT (up to 10MB)</p>
                </div>
                <button
                  type="button"
                  className="px-4 py-1.5 bg-slate-950 text-white rounded-lg text-xs font-display font-medium shadow-sm hover:bg-slate-850"
                >
                  Browse Files
                </button>
              </div>
            )}
          </div>
        ) : (
          /* Copy Paste Text Card */
          <form onSubmit={handlePasteSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Document Label</label>
              <input
                type="text"
                value={pasteName}
                onChange={(e) => setPasteName(e.target.value)}
                required
                className="w-full px-4 py-2 text-sm border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-slate-800 transition-all"
                placeholder="e.g. Resume Senior Software Engineer"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Resume Text Content</label>
              <textarea
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                required
                rows={6}
                className="w-full px-4 py-3 text-sm border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-slate-800 transition-all font-mono text-xs"
                placeholder="Paste the raw text of the resume here..."
              />
            </div>
            <button
              type="submit"
              disabled={isUploading}
              className="w-full py-2.5 bg-slate-950 text-white font-display font-medium text-xs rounded-xl hover:bg-slate-850 transition-all shadow-sm"
            >
              {isUploading ? 'Securing & Vectorizing...' : 'Register Candidate Resume'}
            </button>
          </form>
        )}
      </div>

      {/* Docs Repository List Column */}
      <div className="lg:col-span-2 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-display font-semibold text-slate-950">Knowledge Base</h2>
            <p className="text-xs text-slate-500 mt-1">Currently loaded profiles sanitized for secure alignment analysis.</p>
          </div>
          <span className="text-xs font-semibold px-2 py-1 bg-slate-100 border border-slate-200 rounded-lg text-slate-700 font-mono">
            {documents.length} Records
          </span>
        </div>

        {documents.length === 0 ? (
          <div className="bg-slate-50 rounded-2xl border border-slate-200/60 p-12 text-center text-slate-400">
            <FileText className="h-10 w-10 mx-auto mb-3 stroke-1 text-slate-300" />
            <h3 className="font-display font-semibold text-slate-800 text-sm">No Resume Documents Indexed</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">Upload a PDF or paste file contents to register them in your secure workspace storage.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {documents.map((doc) => {
              const isActive = doc.id === activeId;
              return (
                <div
                  key={doc.id}
                  className={`bg-white rounded-2xl border p-4 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                    isActive ? 'border-slate-900 shadow-xs' : 'border-slate-100 hover:border-slate-200'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${isActive ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'}`}>
                      <FileText className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="font-display font-semibold text-sm text-slate-800 flex items-center gap-2">
                        {doc.filename}
                      </h4>
                      <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                        ID: {doc.id} • Registered {formatDateOnly(doc.created_at)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end md:self-center">
                    {getStatusBadge(doc.status)}

                    <div className="flex items-center border border-slate-150 rounded-lg overflow-hidden bg-slate-50">
                      <button
                        onClick={async () => {
                          onSelect(doc.id);
                          const fullDoc = await onPreviewDocument(doc.id);
                          setActiveDocPreview(fullDoc || doc);
                        }}
                        title="Preview Secure Content"
                        className="p-2 hover:bg-white text-slate-600 border-r border-slate-150 transition-all"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => onDelete(doc.id)}
                        title="Delete Document"
                        className="p-2 hover:bg-rose-50 text-rose-600 transition-all"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>

                    {(doc.status === 'indexed' || doc.status === 'analyzed') && (
                      <button
                        onClick={() => {
                          onSelect(doc.id);
                          onAnalyzeTab();
                        }}
                        className="px-3 py-1.5 bg-slate-900 hover:bg-slate-850 text-white text-xs font-display font-medium rounded-lg transition-all"
                      >
                        Analyze
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Modal/Preview Drawer for PII Check */}
        {activeDocPreview && (
          <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-2xl max-w-3xl w-full border border-slate-100 shadow-xl overflow-hidden flex flex-col max-h-[85vh]">
              <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-slate-50">
                <div>
                  <h3 className="text-base font-display font-semibold text-slate-800 flex items-center gap-2">
                    <ShieldCheck className="h-5 w-5 text-indigo-600" />
                    Security Preview: {activeDocPreview.filename}
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">Observe real-time PII stripping execution output.</p>
                </div>
                <button
                  onClick={() => setActiveDocPreview(null)}
                  className="p-1 px-3 hover:bg-slate-200 text-slate-700 bg-slate-100 rounded-lg text-xs font-semibold"
                >
                  Close
                </button>
              </div>

              <div className="p-6 overflow-y-auto space-y-6">
                {/* Entities Masked */}
                {activeDocPreview.pii_entities && activeDocPreview.pii_entities.length > 0 && (
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-150">
                    <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-widest mb-3">Stipped PII Register (Audit Log)</h4>
                    <div className="flex flex-wrap gap-2">
                      {activeDocPreview.pii_entities.map((ent, i) => (
                        <div key={i} className="flex items-center gap-1 bg-white border border-slate-200 px-2 py-1 rounded-md text-xs font-mono">
                          <span className="text-indigo-600 font-semibold text-[10px] uppercase bg-indigo-50 px-1 py-0.5 rounded mr-1">
                            {ent.entity_type}
                          </span>
                          <span className="text-slate-400 line-through mr-1 text-[11px]">
                            {ent.original_text}
                          </span>
                          <span className="text-slate-700 font-bold text-[11px]">&rarr; {ent.mask_token}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Cleared Text */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-widest">Sanitized Document Vector Context</h4>
                  <div className="bg-slate-950 text-slate-100 p-4 rounded-xl font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-60 border border-slate-900 leading-relaxed shadow-inner">
                    {activeDocPreview.status === 'indexed' || activeDocPreview.status === 'analyzed'
                      ? activeDocPreview.cleaned_text || activeDocPreview.content || 'No extracted content returned.'
                      : 'Indexing content in progress... Please refresh view in a moment.'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
