import {
  History,
  Building2,
  Calendar,
  FileText,
  Trash2,
  ExternalLink,
  Plus,
  Clock,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';

export function HistoryPage() {
  const {
    recentAnalyses,
    activeSessionId,
    setActiveSession,
    removeRecentAnalysis,
    clearRecentAnalyses,
    setActiveView,
  } = useApp();

  const handleOpenSession = (item: (typeof recentAnalyses)[0]) => {
    setActiveSession({
      analysisId: item.analysis_id,
      companyName: item.company_name,
      reportYear: item.report_year,
      documentName: item.document_name,
      totalChunks: item.total_chunks,
      overallRisk: item.overall_risk,
    });
    setActiveView('overview');
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-xs font-semibold text-cyan-300 mb-2">
            <History className="w-3.5 h-3.5" />
            <span>Local Session Archive</span>
          </div>
          <h1 className="text-2xl font-extrabold text-white">Recent Financial Analyses</h1>
          <p className="text-xs text-slate-400 mt-1">
            Reopen previously ingested sessions or manage your analyst workspace history.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {recentAnalyses.length > 0 && (
            <Button
              size="sm"
              variant="outline"
              onClick={clearRecentAnalyses}
              leftIcon={<Trash2 className="w-3.5 h-3.5" />}
              className="text-rose-400 border-rose-800/80 hover:bg-rose-950/40"
            >
              Clear Archive
            </Button>
          )}
          <Button
            size="sm"
            variant="primary"
            onClick={() => setActiveView('workspace')}
            leftIcon={<Plus className="w-3.5 h-3.5" />}
          >
            New Ingestion
          </Button>
        </div>
      </div>

      {/* Sessions List */}
      {recentAnalyses.length > 0 ? (
        <div className="grid grid-cols-1 gap-3.5">
          {recentAnalyses.map((item) => {
            const isActive = activeSessionId === item.analysis_id;
            const dateFormatted = new Date(item.created_at).toLocaleString([], {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });

            return (
              <Card
                key={item.analysis_id}
                className={`border transition-all p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                  isActive
                    ? 'border-cyan-500/60 bg-cyan-950/20 shadow-md'
                    : 'border-slate-800 bg-slate-900/70 hover:bg-slate-900 hover:border-slate-700'
                }`}
              >
                <div className="space-y-1.5 min-w-0">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shrink-0">
                      <Building2 className="w-4 h-4" />
                    </div>
                    <h3 className="text-base font-bold text-slate-100 truncate">
                      {item.company_name || 'Analyzed Company'}
                    </h3>
                    <Badge variant="primary" size="sm" className="font-mono">
                      <Calendar className="w-3 h-3 mr-1" />
                      FY {item.report_year || '2025'}
                    </Badge>
                    {isActive && (
                      <Badge variant="success" size="sm">
                        Currently Active
                      </Badge>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 font-mono pt-1">
                    {item.document_name && (
                      <span className="flex items-center gap-1">
                        <FileText className="w-3 h-3 text-slate-500" />
                        {item.document_name}
                      </span>
                    )}
                    {item.total_chunks && (
                      <span>{item.total_chunks} vector chunks</span>
                    )}
                    <span className="text-slate-500 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {dateFormatted}
                    </span>
                    <span className="text-[11px] text-slate-600">ID: {item.analysis_id.slice(0, 8)}...</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    size="sm"
                    variant={isActive ? 'secondary' : 'primary'}
                    onClick={() => handleOpenSession(item)}
                    rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
                  >
                    {isActive ? 'Inspect' : 'Load Session'}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => removeRecentAnalysis(item.analysis_id)}
                    className="text-slate-500 hover:text-rose-400 p-2"
                    title="Remove from history"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={History}
          title="No Saved Recent Analyses"
          description="Uploaded documents and completed analyses will automatically be preserved in your local session archive."
          actionLabel="Start New Analysis"
          onAction={() => setActiveView('workspace')}
        />
      )}
    </div>
  );
}
