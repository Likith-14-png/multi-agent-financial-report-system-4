import React, { useEffect, useState } from 'react';
import {
  TrendingUp,
  AlertTriangle,
  Search,
  ArrowRight,
  ShieldCheck,
  Building2,
  FileText,
  Layers,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { api, ApiError } from '../lib/api';
import { ExtractionResponse, ResearchResponse, RedFlagsResponse } from '../lib/types';
import { formatFinancialValue } from '../lib/formatters';
import { AnalysisHeader } from '../components/AnalysisHeader';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { MetricCardSkeleton, CardSkeleton } from '../components/ui/Skeleton';
import { TrendLineChart, RiskDistributionBar } from '../components/Charts';
import { MarkdownRenderer } from '../components/ui/MarkdownRenderer';

export function OverviewPage() {
  const { activeSessionId, activeYear, setActiveView, openEvidenceDrawer } = useApp();

  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null);
  const [research, setResearch] = useState<ResearchResponse | null>(null);
  const [redFlags, setRedFlags] = useState<RedFlagsResponse | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchOverviewData = async () => {
    if (!activeSessionId) return;

    setIsLoading(true);
    setErrorMessage(null);

    try {
      // Execute parallel calls to retrieve extraction, research, and red flags
      const [extData, resData, rfData] = await Promise.allSettled([
        api.getExtraction(activeSessionId),
        api.getResearch(activeSessionId),
        api.getRedFlags(activeSessionId),
      ]);

      if (extData.status === 'fulfilled') setExtraction(extData.value);
      if (resData.status === 'fulfilled') setResearch(resData.value);
      if (rfData.status === 'fulfilled') setRedFlags(rfData.value);

      if (extData.status === 'rejected' && resData.status === 'rejected' && rfData.status === 'rejected') {
        const reason = extData.reason;
        if (reason instanceof ApiError) {
          setErrorMessage(reason.detail || reason.message);
        } else {
          setErrorMessage('Could not load analysis data. The session may have expired.');
        }
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to retrieve analysis overview.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchOverviewData();
  }, [activeSessionId]);

  if (!activeSessionId) {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <EmptyState
          icon={Building2}
          title="No Active Financial Analysis"
          description="Upload an annual report or financial filing in the Workspace to generate executive metrics, grounded research, risk evaluations, and peer benchmarks."
          actionLabel="Go to Ingestion Workspace"
          onAction={() => setActiveView('workspace')}
        />
      </div>
    );
  }

  // Build historical trend chart data from yearly_metrics if available
  const yearlyMetrics = extraction?.yearly_metrics;
  const trendSeries = [];

  if (yearlyMetrics && yearlyMetrics.revenue && yearlyMetrics.revenue.length > 0) {
    trendSeries.push({
      name: 'Revenue',
      color: '#06b6d4', // cyan
      points: yearlyMetrics.revenue.map((pt) => ({
        label: pt.year || pt.period || 'Period',
        value: typeof pt.value === 'number' ? pt.value : parseFloat(String(pt.value).replace(/[^0-9.-]/g, '')) || 0,
        displayValue: typeof pt.value === 'string' ? pt.value : undefined,
      })),
    });
  }

  if (yearlyMetrics && yearlyMetrics.net_income && yearlyMetrics.net_income.length > 0) {
    trendSeries.push({
      name: 'Net Income',
      color: '#10b981', // emerald
      points: yearlyMetrics.net_income.map((pt) => ({
        label: pt.year || pt.period || 'Period',
        value: typeof pt.value === 'number' ? pt.value : parseFloat(String(pt.value).replace(/[^0-9.-]/g, '')) || 0,
        displayValue: typeof pt.value === 'string' ? pt.value : undefined,
      })),
    });
  }

  // Risk counts
  const flags = redFlags?.flags || [];
  const countCritical = flags.filter((f) => String(f.severity || f.risk_level).toLowerCase() === 'critical').length;
  const countHigh = flags.filter((f) => String(f.severity || f.risk_level).toLowerCase() === 'high').length;
  const countMedium = flags.filter((f) => String(f.severity || f.risk_level).toLowerCase() === 'medium').length;
  const countLow = flags.filter((f) => String(f.severity || f.risk_level).toLowerCase() === 'low').length;

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      {/* Active Session Context Bar */}
      <AnalysisHeader
        onAskQuestion={() => setActiveView('research')}
        onCompare={() => setActiveView('comparison')}
      />

      {errorMessage && (
        <ErrorBanner
          title="Analysis Overview Notice"
          message={errorMessage}
          onRetry={fetchOverviewData}
        />
      )}

      {/* KPI Highlights Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Core Financial Metrics
          </h3>
          <button
            onClick={() => setActiveView('financials')}
            className="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1 cursor-pointer"
          >
            Detailed Statements <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Revenue */}
            <Card className="border-slate-800 bg-slate-900/70 hover:border-slate-700 transition-all">
              <CardContent className="p-5 space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="font-semibold uppercase tracking-wider text-[11px]">Total Revenue</span>
                  <Badge variant="primary" size="sm">FY {activeYear}</Badge>
                </div>
                <div className="text-2xl font-extrabold text-white font-mono tracking-tight">
                  {formatFinancialValue(extraction?.revenue)}
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                  <span>Top-Line Scale</span>
                  <span className="text-cyan-400 font-mono text-[11px]">Primary Ingestion</span>
                </div>
              </CardContent>
            </Card>

            {/* Operating Income */}
            <Card className="border-slate-800 bg-slate-900/70 hover:border-slate-700 transition-all">
              <CardContent className="p-5 space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="font-semibold uppercase tracking-wider text-[11px]">Operating Income</span>
                  <Badge variant="outline" size="sm">EBIT</Badge>
                </div>
                <div className="text-2xl font-extrabold text-white font-mono tracking-tight">
                  {formatFinancialValue(extraction?.operating_income)}
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                  <span>Core Operations</span>
                  <span className="text-slate-400 font-mono text-[11px]">Operating Profit</span>
                </div>
              </CardContent>
            </Card>

            {/* Net Income */}
            <Card className="border-slate-800 bg-slate-900/70 hover:border-slate-700 transition-all">
              <CardContent className="p-5 space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="font-semibold uppercase tracking-wider text-[11px]">Net Income</span>
                  <Badge variant="outline" size="sm">GAAP</Badge>
                </div>
                <div className="text-2xl font-extrabold text-white font-mono tracking-tight">
                  {formatFinancialValue(extraction?.net_income)}
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                  <span>Bottom-Line Earnings</span>
                  <span className="text-emerald-400 font-mono text-[11px]">Profitability</span>
                </div>
              </CardContent>
            </Card>

            {/* Total Assets */}
            <Card className="border-slate-800 bg-slate-900/70 hover:border-slate-700 transition-all">
              <CardContent className="p-5 space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="font-semibold uppercase tracking-wider text-[11px]">Total Assets</span>
                  <Badge variant="outline" size="sm">Balance Sheet</Badge>
                </div>
                <div className="text-2xl font-extrabold text-white font-mono tracking-tight">
                  {formatFinancialValue(extraction?.total_assets)}
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                  <span>Capital Base</span>
                  <span className="text-slate-400 font-mono text-[11px]">Asset Base</span>
                </div>
              </CardContent>
            </Card>

            {/* Total Liabilities */}
            <Card className="border-slate-800 bg-slate-900/70 hover:border-slate-700 transition-all">
              <CardContent className="p-5 space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="font-semibold uppercase tracking-wider text-[11px]">Total Liabilities</span>
                  <Badge variant="outline" size="sm">Obligations</Badge>
                </div>
                <div className="text-2xl font-extrabold text-white font-mono tracking-tight">
                  {formatFinancialValue(extraction?.total_liabilities)}
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                  <span>Leverage / Debt</span>
                  <span className="text-slate-400 font-mono text-[11px]">Obligations</span>
                </div>
              </CardContent>
            </Card>

            {/* Free Cash Flow / EPS */}
            <Card className="border-slate-800 bg-slate-900/70 hover:border-slate-700 transition-all">
              <CardContent className="p-5 space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="font-semibold uppercase tracking-wider text-[11px]">
                    {extraction?.free_cash_flow ? 'Free Cash Flow' : 'Earnings Per Share'}
                  </span>
                  <Badge variant="outline" size="sm">
                    {extraction?.free_cash_flow ? 'Cash Flow' : 'Per Share'}
                  </Badge>
                </div>
                <div className="text-2xl font-extrabold text-white font-mono tracking-tight">
                  {extraction?.free_cash_flow
                    ? formatFinancialValue(extraction.free_cash_flow)
                    : extraction?.eps
                    ? String(extraction.eps)
                    : 'Not available'}
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                  <span>Liquidity & Yield</span>
                  <span className="text-cyan-400 font-mono text-[11px]">Audited</span>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Grid: Trends Chart & Risk Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Historical Trends */}
        <Card className="lg:col-span-2 border-slate-800 bg-slate-900/80">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-cyan-400" />
                Financial Trajectory & Trends
              </CardTitle>
              <p className="text-xs text-slate-400 mt-0.5">
                Extracted historical metrics across reported filing periods
              </p>
            </div>
            <Badge variant="primary" size="sm">
              Vector Ingested
            </Badge>
          </CardHeader>
          <CardContent className="p-5 pt-2">
            {isLoading ? (
              <div className="h-56 flex items-center justify-center">
                <Layers className="w-6 h-6 animate-spin text-slate-600" />
              </div>
            ) : trendSeries.length > 0 ? (
              <TrendLineChart series={trendSeries} height={210} />
            ) : (
              <div className="h-52 flex flex-col items-center justify-center p-6 text-center rounded-xl bg-slate-950/40 border border-slate-800/80">
                <TrendingUp className="w-8 h-8 text-slate-600 mb-2" />
                <p className="text-xs font-medium text-slate-300">Single Period Report Analyzed</p>
                <p className="text-[11px] text-slate-500 max-w-sm mt-1">
                  This filing focuses on FY {activeYear}. Multi-year comparisons are available in the Financials or Peer Benchmark views.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-3 text-xs"
                  onClick={() => setActiveView('comparison')}
                >
                  Benchmark with Peer Company
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Risk Profile Card */}
        <Card className="border-slate-800 bg-slate-900/80 flex flex-col justify-between">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                Audit Risk Assessment
              </CardTitle>
              <Badge
                variant="risk"
                riskSeverity={redFlags?.overall_risk || 'Low'}
                size="sm"
              >
                {redFlags?.overall_risk || 'Low'} Risk
              </Badge>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Red flag items identified by Red Flag Agent
            </p>
          </CardHeader>
          <CardContent className="p-5 pt-2 space-y-4 flex-1 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80">
                <div className="flex justify-between items-baseline mb-1.5">
                  <span className="text-xs font-semibold text-slate-300">Total Flagged Items</span>
                  <span className="text-xl font-extrabold text-white font-mono">
                    {redFlags?.total_flags ?? flags.length}
                  </span>
                </div>
                <RiskDistributionBar
                  critical={countCritical}
                  high={countHigh}
                  medium={countMedium}
                  low={countLow}
                />
              </div>

              {flags.length > 0 ? (
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-200 truncate">
                      {flags[0].title || flags[0].category || 'Primary Risk Note'}
                    </span>
                    <Badge variant="risk" riskSeverity={flags[0].severity || flags[0].risk_level} size="sm">
                      {flags[0].severity || flags[0].risk_level || 'Risk'}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                    {flags[0].description || flags[0].reason || 'Footnote risk analysis details available.'}
                  </p>
                </div>
              ) : (
                <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-800/40 text-xs text-emerald-300 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 shrink-0 text-emerald-400" />
                  <span>No critical auditor red flags or going concern alerts detected.</span>
                </div>
              )}
            </div>

            <Button
              size="sm"
              variant="secondary"
              onClick={() => setActiveView('risk')}
              className="w-full justify-between mt-2"
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            >
              Examine All Risk Items
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Research Findings & Citations Preview */}
      <Card className="border-slate-800 bg-slate-900/80">
        <CardHeader className="flex flex-row items-center justify-between pb-2 border-b border-slate-800/60">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Search className="w-4 h-4 text-cyan-400" />
              Executive Research Synthesis
            </CardTitle>
            <p className="text-xs text-slate-400 mt-0.5">
              Grounded AI research analysis extracted from filing MD&A and footnotes
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setActiveView('research')}
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
          >
            Open Analyst Console
          </Button>
        </CardHeader>
        <CardContent className="p-6 space-y-4">
          {isLoading ? (
            <CardSkeleton lines={4} />
          ) : research?.answer || research?.summary ? (
            <div className="space-y-4">
              <div className="text-sm text-slate-200 leading-relaxed max-w-4xl">
                <MarkdownRenderer
                  content={research.summary || research.answer || ''}
                  sources={research.sources || []}
                  onCitationClick={openEvidenceDrawer}
                />
              </div>

              {/* Source Evidence Pills */}
              {research.sources && research.sources.length > 0 && (
                <div className="pt-3 border-t border-slate-800/60 space-y-2">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Verified Citations & Grounding Sources:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {research.sources.slice(0, 5).map((src, sIdx) => (
                      <button
                        key={sIdx}
                        onClick={() => openEvidenceDrawer(src)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-cyan-500/60 hover:bg-slate-900 text-xs text-slate-300 transition-colors cursor-pointer group"
                      >
                        <FileText className="w-3 h-3 text-cyan-400 shrink-0" />
                        <span className="font-mono text-[11px]">{src.source_file || 'Filing'}</span>
                        {src.page && <span className="text-slate-500 font-mono">p.{src.page}</span>}
                        {src.section && (
                          <span className="text-slate-400 max-w-[120px] truncate">· {src.section}</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-slate-400 py-6 text-center">
              Research synthesis will automatically compile from the uploaded filing.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
