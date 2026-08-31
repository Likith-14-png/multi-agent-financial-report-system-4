import React, { useEffect } from 'react';
import { X, FileText, Bookmark, Hash, Percent, Copy, Check } from 'lucide-react';
import { useApp } from '../lib/AppContext';

export function CitationDrawer() {
  const { isEvidenceDrawerOpen, selectedCitation, closeEvidenceDrawer } = useApp();
  const [copied, setCopied] = React.useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeEvidenceDrawer();
    };
    if (isEvidenceDrawerOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isEvidenceDrawerOpen, closeEvidenceDrawer]);

  if (!isEvidenceDrawerOpen || !selectedCitation) return null;

  const handleCopy = () => {
    if (selectedCitation.snippet) {
      navigator.clipboard.writeText(selectedCitation.snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm transition-opacity"
        onClick={closeEvidenceDrawer}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col">
          {/* Header */}
          <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/90 shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                <Bookmark className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-100">Document Evidence</h3>
                <p className="text-xs text-slate-400">Verified filing source citation</p>
              </div>
            </div>
            <button
              onClick={closeEvidenceDrawer}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-5 space-y-6">
            {/* Metadata Pills */}
            <div className="grid grid-cols-2 gap-2.5 text-xs">
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                <span className="text-[10px] text-slate-400 flex items-center gap-1 uppercase tracking-wider font-medium">
                  <FileText className="w-3 h-3 text-cyan-400" /> Source File
                </span>
                <p className="font-semibold text-slate-200 truncate font-mono text-[11px]" title={selectedCitation.source_file || 'Primary Filing'}>
                  {selectedCitation.source_file || 'Primary Document'}
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                <span className="text-[10px] text-slate-400 flex items-center gap-1 uppercase tracking-wider font-medium">
                  <Hash className="w-3 h-3 text-cyan-400" /> Page / Section
                </span>
                <p className="font-semibold text-slate-200 font-mono text-[11px]">
                  {selectedCitation.page ? `Page ${selectedCitation.page}` : selectedCitation.section || 'General'}
                </p>
              </div>

              {selectedCitation.chunk_id && (
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1 col-span-2">
                  <span className="text-[10px] text-slate-400 flex items-center gap-1 uppercase tracking-wider font-medium">
                    <Hash className="w-3 h-3 text-cyan-400" /> Chunk ID
                  </span>
                  <p className="font-mono text-[11px] text-cyan-300/90 break-all select-all">
                    {selectedCitation.chunk_id}
                  </p>
                </div>
              )}

              {selectedCitation.score !== undefined && selectedCitation.score !== null && (
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1 col-span-2">
                  <div className="flex justify-between items-center text-[10px] text-slate-400 uppercase tracking-wider font-medium">
                    <span className="flex items-center gap-1">
                      <Percent className="w-3 h-3 text-cyan-400" /> Grounding Relevance
                    </span>
                    <span className="font-mono text-cyan-300">
                      {Math.round(selectedCitation.score * 100)}%
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-cyan-500 rounded-full"
                      style={{ width: `${Math.min(selectedCitation.score * 100, 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Quote Snippet Box */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Extracted Quote
                </label>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 cursor-pointer font-medium"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy Text</span>
                    </>
                  )}
                </button>
              </div>

              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/90 text-xs text-slate-300 font-mono leading-relaxed select-text whitespace-pre-wrap">
                {selectedCitation.snippet || 'No text snippet available in this citation record.'}
              </div>
            </div>

            {/* Note on Provenance */}
            <div className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-800/30 text-[11px] text-cyan-300/80 leading-relaxed">
              <strong>Grounding Guarantee:</strong> This text snippet was retrieved directly from the ingested ChromaDB vector embeddings collection for the active financial filing.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
