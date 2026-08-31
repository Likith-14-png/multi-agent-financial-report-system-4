import React, { useEffect, useState, useMemo } from 'react';
import {
  FileSpreadsheet,
  TrendingUp,
  Search,
  Bookmark,
  ExternalLink,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { api, ApiError } from '../lib/api';
import { ExtractionResponse, ObservationItem, CitationSource } from '../lib/types';
import { formatFinancialValue } from '../lib/formatters';
import { AnalysisHeader } from '../components/AnalysisHeader';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Tabs } from '../components/ui/Tabs';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { TableRowSkeleton } from '../components/ui/Skeleton';
import { TrendLineChart } from '../components/Charts';

type StatementTab = 'all' | 'income' | 'balance' | 'cashflow' | 'observations';

export function FinancialsPage() {
  const { activeSessionId, activeYear, setActiveView, openEvidenceDrawer } = useApp();

  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<StatementTab>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const fetchExtraction = async () => {
    if (!activeSessionId) return;
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await api.getExtraction(activeSessionId);
      setExtraction(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.detail || err.message);
      } else {
        setErrorMessage('Failed to retrieve structured financial statements.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchExtraction();
  }, [activeSessionId]);

  if (!activeSessionId) {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <EmptyState
          icon={FileSpreadsheet}
          title="No Active Financial Statement Data"
          description="Upload a filing in the Workspace to parse Income Statements, Balance Sheets, Cash Flows, and line-item provenance."
          actionLabel="Go to Workspace"
          onAction={() => setActiveView('workspace')}
        />
      </div>
    );
  }

  // Core statement structures built from extraction data
  const incomeMetrics = useMemo(() => [
    { label: 'Total Revenue', value: extraction?.revenue, unit: 'Top Line' },
    { label: 'Gross Profit', value: extraction?.gross_profit, unit: 'Gross Profit' },
    { label: 'Operating Income (EBIT)', value: extraction?.operating_income, unit: 'Operating' },
    { label: 'Pre-tax Income', value: extraction?.pretax_income, unit: 'EBT' },
    { label: 'Net Income', value: extraction?.net_income, unit: 'Bottom Line' },
    { label: 'Earnings Per Share (EPS)', value: extraction?.eps || extraction?.basic_eps, unit: 'Per Share' },
    { label: 'R&D Expense', value: extraction?.rd_expense, unit: 'Innovation' },
  ], [extraction]);

  const balanceMetrics = useMemo(() => [
    { label: 'Total Assets', value: extraction?.total_assets, unit: 'Asset Base' },
    { label: 'Total Liabilities', value: extraction?.total_liabilities, unit: 'Obligations' },
    { label: 'Total Equity', value: extraction?.total_equity, unit: 'Book Value' },
    { label: 'Operating Cash Flow', value: extraction?.operating_cash_flow, unit: 'Operating' },
  ], [extraction]);

  const cashFlowMetrics = useMemo(() => [
    { label: 'Operating Cash Flow', value: extraction?.operating_cash_flow || extraction?.cash_flow, unit: 'Operating' },
    { label: 'Free Cash Flow (FCF)', value: extraction?.free_cash_flow, unit: 'Free Cash' },
  ], [extraction]);

  // Combine metrics or observations
  const observationsList: ObservationItem[] = useMemo(() => {
    if (extraction?.observations && extraction.observations.length > 0) {
      return extraction.observations;
    }
    if (extraction?.detailed_metrics && extraction.detailed_metrics.length > 0) {
      return extraction.detailed_metrics;
    }
    if (extraction?.metrics && extraction.metrics.length > 0) {
      return extraction.metrics.map((m) => ({
        canonical_label: m.metric,
        value: m.value,
        period: m.period || activeYear,
        source_file: m.source,
        page: m.page,
        chunk_id: m.chunk_id,
        evidence: m.evidence,
        provenance: m.provenance,
      }));
    }
    return [];
  }, [extraction, activeYear]);

  // Filter observations by search query
  const filteredObservations = useMemo(() => {
    if (!searchQuery.trim()) return observationsList;
    const q = searchQuery.toLowerCase();
    return observationsList.filter((obs) => {
      const name = (obs.canonical_label || obs.metric || obs.metric_name || '').toLowerCase();
      const val = String(obs.value || obs.raw_value || '').toLowerCase();
      const src = (obs.source_file || '').toLowerCase();
      return name.includes(q) || val.includes(q) || src.includes(q);
    });
  }, [observationsList, searchQuery]);

  const handleOpenCitation = (obs: ObservationItem) => {
    const citation: CitationSource = {
      source_file: obs.source_file || obs.provenance?.source_file || 'Primary Filing',
      page: obs.page || obs.provenance?.page,
      chunk_id: obs.chunk_id || obs.provenance?.chunk_id,
      section: obs.section || obs.provenance?.section || obs.canonical_label || 'Financial Statement',
      snippet: obs.evidence || `Extracted metric "${obs.canonical_label || obs.metric}" valued at ${obs.value || obs.raw_value} from audited statements.`,
    };
    openEvidenceDrawer(citation);
  };

  // Build trend chart from yearly_metrics
  const yearlyMetrics = extraction?.yearly_metrics;
  const trendSeries = [];
  if (yearlyMetrics) {
    for (const [key, pts] of Object.entries(yearlyMetrics)) {
      if (Array.isArray(pts) && pts.length > 0) {
        trendSeries.push({
          name: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
          color: key.includes('revenue') ? '#06b6d4' : key.includes('income') ? '#10b981' : '#a855f7',
          points: pts.map((p) => ({
            label: p.year || p.period || 'Year',
            value: typeof p.value === 'number' ? p.value : parseFloat(String(p.value).replace(/[^0-9.-]/g, '')) || 0,
            displayValue: typeof p.value === 'string' ? p.value : undefined,
          })),
        });
      }
    }
  }

  const statementTabs = [
    { id: 'all' as StatementTab, label: 'All Statements' },
    { id: 'income' as StatementTab, label: 'Income Statement' },
    { id: 'balance' as StatementTab, label: 'Balance Sheet' },
    { id: 'cashflow' as StatementTab, label: 'Cash Flow' },
    { id: 'observations' as StatementTab, label: 'Provenance Table', badge: observationsList.length },
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      <AnalysisHeader
        onAskQuestion={() => setActiveView('research')}
        onCompare={() => setActiveView('comparison')}
      />

      {errorMessage && (
        <ErrorBanner
          title="Financial Statement Notice"
          message={errorMessage}
          onRetry={fetchExtraction}
        />
      )}

      {/* Navigation Tabs & Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <Tabs
          tabs={statementTabs}
          activeTab={activeTab}
          onChange={(tab) => setActiveTab(tab as StatementTab)}
          variant="pills"
        />

        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search metric name or value..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-medium"
          />
        </div>
      </div>

      {/* Historical Trend Chart (if multiple years exist) */}
      {trendSeries.length > 0 && (
        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400" />
              Multi-Year Metric Series Trajectory
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5 pt-0">
            <TrendLineChart series={trendSeries} height={200} />
          </CardContent>
        </Card>
      )}

      {/* Statements Grid */}
      {(activeTab === 'all' || activeTab === 'income') && (
        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader className="border-b border-slate-800/60 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Income Statement Summary</CardTitle>
                <p className="text-xs text-slate-400 mt-0.5">Operating performance, margins, and net earnings</p>
              </div>
              <Badge variant="primary" size="sm">FY {activeYear}</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-xs text-left border-collapse">
              <thead className="bg-slate-950/60 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="py-3 px-5">Metric Name</th>
                  <th className="py-3 px-5">Classification</th>
                  <th className="py-3 px-5 text-right">Reported Value</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {isLoading ? (
                  <>
                    <TableRowSkeleton cols={3} />
                    <TableRowSkeleton cols={3} />
                    <TableRowSkeleton cols={3} />
                  </>
                ) : (
                  incomeMetrics.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/40 transition-colors">
                      <td className="py-3.5 px-5 font-sans font-medium text-slate-200">{item.label}</td>
                      <td className="py-3.5 px-5 text-slate-400 text-[11px] font-sans">{item.unit}</td>
                      <td className="py-3.5 px-5 text-right font-bold text-slate-100 text-sm">
                        {formatFinancialValue(item.value)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {(activeTab === 'all' || activeTab === 'balance') && (
        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader className="border-b border-slate-800/60 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Balance Sheet Summary</CardTitle>
                <p className="text-xs text-slate-400 mt-0.5">Asset base, liabilities, equity, and liquidity</p>
              </div>
              <Badge variant="outline" size="sm">Position</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-xs text-left border-collapse">
              <thead className="bg-slate-950/60 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="py-3 px-5">Metric Name</th>
                  <th className="py-3 px-5">Classification</th>
                  <th className="py-3 px-5 text-right">Reported Value</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {isLoading ? (
                  <>
                    <TableRowSkeleton cols={3} />
                    <TableRowSkeleton cols={3} />
                  </>
                ) : (
                  balanceMetrics.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/40 transition-colors">
                      <td className="py-3.5 px-5 font-sans font-medium text-slate-200">{item.label}</td>
                      <td className="py-3.5 px-5 text-slate-400 text-[11px] font-sans">{item.unit}</td>
                      <td className="py-3.5 px-5 text-right font-bold text-slate-100 text-sm">
                        {formatFinancialValue(item.value)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {(activeTab === 'all' || activeTab === 'cashflow') && (
        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader className="border-b border-slate-800/60 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Cash Flow Statement</CardTitle>
                <p className="text-xs text-slate-400 mt-0.5">Cash generation and capital reinvestment</p>
              </div>
              <Badge variant="outline" size="sm">Cash Flow</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-xs text-left border-collapse">
              <thead className="bg-slate-950/60 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="py-3 px-5">Metric Name</th>
                  <th className="py-3 px-5">Classification</th>
                  <th className="py-3 px-5 text-right">Reported Value</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {isLoading ? (
                  <TableRowSkeleton cols={3} />
                ) : (
                  cashFlowMetrics.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/40 transition-colors">
                      <td className="py-3.5 px-5 font-sans font-medium text-slate-200">{item.label}</td>
                      <td className="py-3.5 px-5 text-slate-400 text-[11px] font-sans">{item.unit}</td>
                      <td className="py-3.5 px-5 text-right font-bold text-slate-100 text-sm">
                        {formatFinancialValue(item.value)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Observations & Traceability Provenance Table */}
      {(activeTab === 'all' || activeTab === 'observations') && (
        <Card className="border-slate-800 bg-slate-900/80">
          <CardHeader className="border-b border-slate-800/60 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Bookmark className="w-4 h-4 text-cyan-400" />
                  Line-Item Provenance & Vector Evidence Trace
                </CardTitle>
                <p className="text-xs text-slate-400 mt-0.5">
                  Click any observation to inspect original filing pages, chunk IDs, and grounding snippets
                </p>
              </div>
              <Badge variant="primary" size="sm">
                {filteredObservations.length} Line Items
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse min-w-[640px]">
              <thead className="bg-slate-950/60 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="py-3 px-5">Canonical Metric</th>
                  <th className="py-3 px-5">Period</th>
                  <th className="py-3 px-5">Extracted Value</th>
                  <th className="py-3 px-5">Source File & Page</th>
                  <th className="py-3 px-5 text-right">Evidence Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {isLoading ? (
                  <>
                    <TableRowSkeleton cols={5} />
                    <TableRowSkeleton cols={5} />
                    <TableRowSkeleton cols={5} />
                  </>
                ) : filteredObservations.length > 0 ? (
                  filteredObservations.map((obs, idx) => (
                    <tr
                      key={idx}
                      onClick={() => handleOpenCitation(obs)}
                      className="hover:bg-slate-900/70 transition-colors cursor-pointer group"
                    >
                      <td className="py-3.5 px-5 font-sans font-medium text-slate-200">
                        {obs.canonical_label || obs.metric || obs.metric_name || 'Financial Item'}
                      </td>
                      <td className="py-3.5 px-5 text-slate-400">
                        FY {obs.period || obs.year || activeYear}
                      </td>
                      <td className="py-3.5 px-5 font-bold text-cyan-300">
                        {formatFinancialValue(obs.value || obs.raw_value)}
                      </td>
                      <td className="py-3.5 px-5 text-slate-400">
                        <span className="truncate max-w-[160px] inline-block font-mono">
                          {obs.source_file || obs.provenance?.source_file || 'Report'}
                          {obs.page ? ` (p.${obs.page})` : ''}
                        </span>
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-slate-800 text-slate-300 group-hover:bg-cyan-500/20 group-hover:text-cyan-300 transition-colors">
                          <span>Inspect</span>
                          <ExternalLink className="w-2.5 h-2.5" />
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-500 font-sans text-xs">
                      No extracted metrics matched your query.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
