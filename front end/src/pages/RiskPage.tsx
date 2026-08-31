import React, { useEffect, useState, useMemo } from 'react';
import {
  AlertTriangle,
  ShieldAlert,
  ShieldCheck,
  Search,
  Send,
  FileText,
  Bookmark,
  CheckCircle2,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { api, ApiError } from '../lib/api';
import { RedFlagsResponse, RedFlagItem, RedFlagsQueryResponse, CitationSource } from '../lib/types';
import { getRiskColorClass } from '../lib/formatters';
import { AnalysisHeader } from '../components/AnalysisHeader';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { CardSkeleton } from '../components/ui/Skeleton';
import { RiskDistributionBar } from '../components/Charts';
import { MarkdownRenderer } from '../components/ui/MarkdownRenderer';

type SeverityFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';

export function RiskPage() {
  const { activeSessionId, activeCompany, setActiveView, openEvidenceDrawer } = useApp();

  const [redFlags, setRedFlags] = useState<RedFlagsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [riskQuery, setRiskQuery] = useState('');
  const [queryResult, setQueryResult] = useState<RedFlagsQueryResponse | null>(null);
  const [isQueryLoading, setIsQueryLoading] = useState(false);

  const fetchRedFlags = async () => {
    if (!activeSessionId) return;
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await api.getRedFlags(activeSessionId);
      setRedFlags(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.detail || err.message);
      } else {
        setErrorMessage('Failed to retrieve risk flags. Verify backend connection.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRedFlags();
  }, [activeSessionId]);

  if (!activeSessionId) {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <EmptyState
          icon={AlertTriangle}
          title="No Active Filing for Risk Assessment"
          description="Upload a filing in the Workspace to evaluate going concern uncertainties, debt covenants, auditor notes, and management risks."
          actionLabel="Go to Workspace"
          onAction={() => setActiveView('workspace')}
        />
      </div>
    );
  }

  const flags: RedFlagItem[] = redFlags?.flags || [];

  const countCritical = flags.filter((f) => String(f.severity || f.risk_level).toLowerCase() === 'critical').length;
  const countHigh = flags.filter((f) => String(f.severity || f.risk_level).toLowerCase() === 'high').length;
  const countMedium = flags.filter((f) => String(f.severity || f.risk_level).toLowerCase() === 'medium').length;
  const countLow = flags.filter((f) => String(f.severity || f.risk_level).toLowerCase() === 'low').length;

  const filteredFlags = useMemo(() => {
    if (severityFilter === 'all') return flags;
    return flags.filter((f) => String(f.severity || f.risk_level).toLowerCase() === severityFilter);
  }, [flags, severityFilter]);

  const handleRiskQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!riskQuery.trim() || !activeSessionId || isQueryLoading) return;

    setIsQueryLoading(true);
    try {
      const res = await api.queryRedFlags(activeSessionId, riskQuery);
      setQueryResult(res);
    } catch (err) {
      console.error('Risk query failed:', err);
    } finally {
      setIsQueryLoading(false);
    }
  };

  const handleOpenCitation = (flag: RedFlagItem) => {
    const citation: CitationSource = {
      source_file: activeCompany ? `${activeCompany} Filing` : 'Primary Filing',
      page: flag.page,
      section: flag.category || flag.title || 'Risk Factor Note',
      snippet: flag.evidence || flag.reason || flag.description || 'Audit risk flagged by Red Flag Agent.',
    };
    openEvidenceDrawer(citation);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      <AnalysisHeader
        onAskQuestion={() => setActiveView('research')}
        onCompare={() => setActiveView('comparison')}
      />

      {errorMessage && (
        <ErrorBanner
          title="Risk Intelligence Notice"
          message={errorMessage}
          onRetry={fetchRedFlags}
        />
      )}

      {/* Top Banner: Overall Risk Level Card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left: Overall Risk Badge Card */}
        <Card className="border-slate-800 bg-slate-900/90 p-6 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Audited Risk Classification
              </span>
              <ShieldAlert className="w-4 h-4 text-cyan-400" />
            </div>

            <div className="flex items-center gap-3 pt-1">
              <Badge
                variant="risk"
                riskSeverity={redFlags?.overall_risk || 'Low'}
                size="md"
                className="text-sm px-3 py-1 font-bold"
              >
                {redFlags?.overall_risk || 'Low'} Overall Risk
              </Badge>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed pt-1">
              Synthesized by Red Flag Agent across disclosures, liquidity ratios, and footnote disclosures.
            </p>
          </div>

          <div className="pt-4 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400 font-mono">
            <span>Model: {redFlags?.model_used || 'Standard Offline / Gemini'}</span>
            {redFlags?.execution_time && (
              <span>{redFlags.execution_time.toFixed(2)}s scan</span>
            )}
          </div>
        </Card>

        {/* Center & Right: Severity Distribution Breakdown */}
        <Card className="md:col-span-2 border-slate-800 bg-slate-900/90 p-6 flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-100">
                  Risk Item Breakdown
                </h3>
                <p className="text-xs text-slate-400">
                  Total of {flags.length} audit concerns identified in active filing
                </p>
              </div>
              <span className="text-2xl font-extrabold text-white font-mono">{flags.length}</span>
            </div>

            <RiskDistributionBar
              critical={countCritical}
              high={countHigh}
              medium={countMedium}
              low={countLow}
            />
          </div>

          {/* Quick Filter Buttons */}
          <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800/60">
            <button
              onClick={() => setSeverityFilter('all')}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                severityFilter === 'all'
                  ? 'bg-slate-800 text-white border border-slate-700'
                  : 'bg-slate-950/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              All ({flags.length})
            </button>
            <button
              onClick={() => setSeverityFilter('critical')}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                severityFilter === 'critical'
                  ? 'bg-rose-950 text-rose-300 border border-rose-800'
                  : 'bg-slate-950/60 text-slate-400 hover:text-rose-300'
              }`}
            >
              Critical ({countCritical})
            </button>
            <button
              onClick={() => setSeverityFilter('high')}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                severityFilter === 'high'
                  ? 'bg-amber-950 text-amber-300 border border-amber-800'
                  : 'bg-slate-950/60 text-slate-400 hover:text-amber-300'
              }`}
            >
              High ({countHigh})
            </button>
            <button
              onClick={() => setSeverityFilter('medium')}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                severityFilter === 'medium'
                  ? 'bg-yellow-950 text-yellow-300 border border-yellow-800'
                  : 'bg-slate-950/60 text-slate-400 hover:text-yellow-300'
              }`}
            >
              Medium ({countMedium})
            </button>
            <button
              onClick={() => setSeverityFilter('low')}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                severityFilter === 'low'
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                  : 'bg-slate-950/60 text-slate-400 hover:text-emerald-300'
              }`}
            >
              Low ({countLow})
            </button>
          </div>
        </Card>
      </div>

      {/* Grounded Risk Query Console */}
      <Card className="border-slate-800 bg-slate-900/80">
        <CardHeader className="pb-3 border-b border-slate-800/60">
          <CardTitle className="text-sm flex items-center gap-2">
            <Search className="w-4 h-4 text-cyan-400" />
            Query Risk & Footnote Database
          </CardTitle>
          <p className="text-xs text-slate-400 mt-0.5">
            Ask targeted questions focused specifically on debt covenants, supplier concentration, legal liabilities, or going concern disclosures.
          </p>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          <form onSubmit={handleRiskQuery} className="flex items-center gap-2">
            <input
              type="text"
              placeholder="e.g. What are the debt covenants and going concern details?"
              value={riskQuery}
              onChange={(e) => setRiskQuery(e.target.value)}
              disabled={isQueryLoading}
              className="flex-1 px-4 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-medium"
            />
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isQueryLoading}
              disabled={!riskQuery.trim() || isQueryLoading}
              leftIcon={<Send className="w-3.5 h-3.5" />}
            >
              Evaluate Risk
            </Button>
          </form>

          {/* Render Query Result */}
          {queryResult && (
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-semibold text-cyan-300">
                  Risk Evaluation: "{queryResult.question}"
                </span>
                <button
                  onClick={() => setQueryResult(null)}
                  className="text-slate-500 hover:text-slate-300 text-[11px]"
                >
                  Clear
                </button>
              </div>

              <div className="text-xs text-slate-200 leading-relaxed font-sans">
                <MarkdownRenderer
                  content={queryResult.answer}
                  sources={queryResult.sources || []}
                  onCitationClick={openEvidenceDrawer}
                />
              </div>

              {queryResult.sources && queryResult.sources.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800/60">
                  {queryResult.sources.map((s, idx) => (
                    <button
                      key={idx}
                      onClick={() => openEvidenceDrawer(s)}
                      className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-slate-300 hover:border-cyan-500/50 flex items-center gap-1 font-mono cursor-pointer"
                    >
                      <FileText className="w-3 h-3 text-cyan-400" />
                      <span>{s.source_file || 'Filing'}</span>
                      {s.page && <span>p.{s.page}</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Filtered Risk Cards Stream */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Detected Audit & Disclosure Items ({filteredFlags.length})
          </h3>
          <span className="text-xs text-slate-500 font-mono">
            Filtered by: {severityFilter.toUpperCase()}
          </span>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            <CardSkeleton lines={3} />
            <CardSkeleton lines={3} />
          </div>
        ) : filteredFlags.length > 0 ? (
          <div className="grid grid-cols-1 gap-4">
            {filteredFlags.map((flag, idx) => {
              const sev = flag.severity || flag.risk_level || 'Medium';
              const colorClass = getRiskColorClass(sev);

              return (
                <Card
                  key={idx}
                  className={`border ${colorClass.border} bg-slate-900/90 hover:bg-slate-900 transition-all p-5 space-y-4`}
                >
                  {/* Card Top */}
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="risk" riskSeverity={sev} size="sm">
                          {sev}
                        </Badge>
                        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                          {flag.category || 'General Financial Risk'}
                        </span>
                        {flag.page && (
                          <Badge variant="outline" size="sm" className="font-mono">
                            Page {flag.page}
                          </Badge>
                        )}
                      </div>
                      <h4 className="text-base font-bold text-slate-100">
                        {flag.title || flag.description?.slice(0, 80) || `Risk Item #${idx + 1}`}
                      </h4>
                    </div>

                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleOpenCitation(flag)}
                      leftIcon={<Bookmark className="w-3 h-3 text-cyan-400" />}
                      className="text-xs"
                    >
                      View Source Quote
                    </Button>
                  </div>

                  {/* Description & Root Cause */}
                  <div className="space-y-2 text-xs text-slate-300 leading-relaxed">
                    <p>{flag.description}</p>
                    {flag.reason && (
                      <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                          Analytical Root Cause:
                        </span>
                        <p className="text-slate-300">{flag.reason}</p>
                      </div>
                    )}
                  </div>

                  {/* Quote Evidence Block */}
                  {flag.evidence && (
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/90 text-xs font-mono text-slate-400 space-y-1">
                      <span className="text-[10px] uppercase font-bold tracking-wider text-cyan-400 block">
                        Direct Evidence Excerpt:
                      </span>
                      <p className="italic text-slate-300 whitespace-pre-wrap">{flag.evidence}</p>
                    </div>
                  )}

                  {/* Recommendation / Mitigation */}
                  {flag.recommendation && (
                    <div className="flex items-start gap-2 pt-2 border-t border-slate-800/60 text-xs text-emerald-300/90">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                      <div>
                        <strong className="font-semibold text-emerald-300">Analyst Recommendation: </strong>
                        <span>{flag.recommendation}</span>
                      </div>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        ) : (
          <div className="p-12 text-center rounded-2xl border border-dashed border-slate-800 bg-slate-900/30">
            <ShieldCheck className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
            <h4 className="text-sm font-semibold text-slate-200">No flags in this category</h4>
            <p className="text-xs text-slate-400 mt-1">
              No financial risk items met the selected severity filter.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
