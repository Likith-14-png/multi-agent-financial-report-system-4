import React from 'react';
import { Building2, Calendar, FileText, Download, MessageSquare, GitCompare, Plus, ShieldCheck } from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { api } from '../lib/api';

export interface AnalysisHeaderProps {
  onAskQuestion?: () => void;
  onCompare?: () => void;
}

export function AnalysisHeader({ onAskQuestion, onCompare }: AnalysisHeaderProps) {
  const { activeSessionId, activeCompany, activeYear, activeDocumentName, activeTotalChunks, setActiveView } = useApp();
  const [isDownloading, setIsDownloading] = React.useState(false);

  if (!activeSessionId) return null;

  const handleDownloadPdf = async () => {
    if (!activeSessionId) return;
    setIsDownloading(true);
    try {
      await api.downloadReportPdf(activeSessionId, activeCompany || undefined, activeYear || undefined);
    } catch (err) {
      console.error('Failed to download PDF:', err);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="p-4 sm:p-5 rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur-md shadow-sm mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="space-y-1.5 min-w-0">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shrink-0">
            <Building2 className="w-4 h-4" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight truncate">
            {activeCompany || 'Active Filing Analysis'}
          </h2>
          <Badge variant="primary" size="sm" className="font-mono">
            <Calendar className="w-3 h-3 mr-1" />
            FY {activeYear || '2025'}
          </Badge>
          <Badge variant="success" size="sm">
            <ShieldCheck className="w-3 h-3 mr-1" />
            Ready
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 pt-0.5">
          {activeDocumentName && (
            <span className="flex items-center gap-1 font-mono truncate max-w-xs" title={activeDocumentName}>
              <FileText className="w-3 h-3 text-slate-500" />
              {activeDocumentName}
            </span>
          )}
          {activeTotalChunks && (
            <span className="font-mono text-slate-400">
              {activeTotalChunks} vector chunks indexed
            </span>
          )}
          <span className="font-mono text-slate-500 text-[11px]">
            ID: {activeSessionId.slice(0, 8)}...
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 shrink-0">
        {onAskQuestion ? (
          <Button size="sm" variant="outline" onClick={onAskQuestion} leftIcon={<MessageSquare className="w-3.5 h-3.5" />}>
            Ask Research
          </Button>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setActiveView('research')} leftIcon={<MessageSquare className="w-3.5 h-3.5" />}>
            Research
          </Button>
        )}

        {onCompare ? (
          <Button size="sm" variant="outline" onClick={onCompare} leftIcon={<GitCompare className="w-3.5 h-3.5" />}>
            Compare Peer
          </Button>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setActiveView('comparison')} leftIcon={<GitCompare className="w-3.5 h-3.5" />}>
            Compare
          </Button>
        )}

        <Button
          size="sm"
          variant="primary"
          onClick={handleDownloadPdf}
          isLoading={isDownloading}
          leftIcon={<Download className="w-3.5 h-3.5" />}
        >
          Export PDF
        </Button>

        <Button
          size="sm"
          variant="ghost"
          onClick={() => setActiveView('workspace')}
          leftIcon={<Plus className="w-3.5 h-3.5" />}
          title="Start new analysis"
        >
          New
        </Button>
      </div>
    </div>
  );
}
