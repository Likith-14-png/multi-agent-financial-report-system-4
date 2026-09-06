import React, { useEffect, useState, useRef } from 'react';
import {
  GitCompare,
  UploadCloud,
  FileText,
  TrendingUp,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { api, ApiError } from '../lib/api';
import { ComparisonResponse, ComparisonRecord } from '../lib/types';
import { formatFinancialValue, formatPercent, formatFileSize, parseNumericValue } from '../lib/formatters';
import { AnalysisHeader } from '../components/AnalysisHeader';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { BarComparisonChart, ComparisonBarItem } from '../components/Charts';
import { MarkdownRenderer } from '../components/ui/MarkdownRenderer';

const PEER_SAMPLES = [
  {
    name: 'Infosys Ltd. — FY 2025 Report',
    company: 'Infosys',
    year: '2025',
    type: 'IT Services & Digital Consulting',
    description: '$18.5B revenue, $3.8B operating income, $16.2B total assets.',
    textSample: `Infosys Financial Report 2025\nRevenue increased to $18.5 billion in fiscal year 2025.\nOperating income was $3.8 billion.\nNet income reached $3.1 billion.\nTotal assets stood at $16.2 billion with total liabilities of $4.5 billion.\nOperating cash flow remained robust at $3.2 billion.\nEPS increased to $0.75 per share.\nRisk factors include currency volatility and tech spending moderation.`,
  },
  {
    name: 'Orion Steelworks — FY 2024 Report',
    company: 'Orion Steelworks',
    year: '2024',
    type: 'Heavy Industrial Manufacturing',
    description: '$8.4B revenue, $920M operating income, higher debt leverage.',
    textSample: `Orion Steelworks Annual Report 2024\nRevenue for the fiscal year 2024 was $8.4 billion.\nOperating income stood at $920 million.\nNet income was $640 million.\nTotal assets were $14.8 billion and total liabilities were $8.2 billion.\nOperating cash flow was $1.1 billion.\nCapital expenditures were $750 million to expand blast furnace operations.`,
  },
];

export function ComparisonPage() {
  const { activeSessionId, activeCompany, setActiveView } = useApp();

  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Peer upload states
  const [peerFile, setPeerFile] = useState<File | null>(null);
  const [peerCompany, setPeerCompany] = useState('');
  const [peerYear, setPeerYear] = useState('2025');
  const [isUploadingPeer, setIsUploadingPeer] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchComparison = async () => {
    if (!activeSessionId) return;
    setErrorMessage(null);
    try {
      const data = await api.getComparison(activeSessionId);
      setComparison(data);
    } catch (err) {
      if (err instanceof ApiError) {
        // 404 is expected before Company B is uploaded
        if (err.status !== 404) {
          setErrorMessage(err.detail || err.message);
        }
      } else {
        setErrorMessage('Failed to load peer comparison results.');
      }
    }
  };

  useEffect(() => {
    fetchComparison();
  }, [activeSessionId]);

  if (!activeSessionId) {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <EmptyState
          icon={GitCompare}
          title="No Active Session for Peer Benchmarking"
          description="Upload a base financial filing in the Workspace first to enable multi-company benchmarking."
          actionLabel="Go to Workspace"
          onAction={() => setActiveView('workspace')}
        />
      </div>
    );
  }

  const handleFileSelect = (selectedFile: File) => {
    const ext = selectedFile.name.split('.').pop()?.toLowerCase();
    if (ext !== 'pdf' && ext !== 'txt') {
      setErrorMessage('Only PDF (.pdf) and Plain Text (.txt) filings are supported for peer comparison.');
      return;
    }
    setPeerFile(selectedFile);
    setErrorMessage(null);
    const cleanName = selectedFile.name.replace(/\.(pdf|txt)$/i, '').replace(/[-_]/g, ' ');
    if (!peerCompany) {
      setPeerCompany(cleanName.split(' ')[0] || '');
    }
  };

  const handleUploadPeer = async () => {
    if (!peerFile || !activeSessionId || isUploadingPeer) return;
    setIsUploadingPeer(true);
    setErrorMessage(null);
    try {
      const result = await api.uploadComparison(
        activeSessionId,
        peerFile,
        peerCompany || undefined,
        peerYear || undefined
      );
      setComparison(result);
      setPeerFile(null);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.detail || err.message);
      } else {
        setErrorMessage('Failed to ingest second company filing.');
      }
    } finally {
      setIsUploadingPeer(false);
    }
  };

  const loadPeerPreset = (preset: (typeof PEER_SAMPLES)[0]) => {
    const blob = new Blob([preset.textSample], { type: 'text/plain' });
    const sampleFile = new File([blob], `${preset.company.toLowerCase()}_${preset.year}_report.txt`, {
      type: 'text/plain',
    });
    setPeerFile(sampleFile);
    setPeerCompany(preset.company);
    setPeerYear(preset.year);
    setErrorMessage(null);
  };

  const cleanCompName = (name?: string | null) => {
    if (!name) return '';
    return name.replace(/^(name|company(?:\s+name)?)\s*[:\-]\s*/i, '').trim();
  };
  const compA = cleanCompName(comparison?.companies?.[0]) || cleanCompName(activeCompany) || 'Company A';
  const compB = cleanCompName(comparison?.companies?.[1]) || 'Company B';

  const records: ComparisonRecord[] = comparison?.records || [];

  const getCompanyVal = (val: unknown) => {
    if (val === null || val === undefined) return null;
    if (typeof val === 'object') {
      const obj = val as Record<string, unknown>;
      return obj.display_value ?? obj.value ?? obj.comparison_value ?? obj.numeric_value ?? obj.raw_value ?? null;
    }
    return val;
  };

  // Build bar comparison items
  const barChartData: ComparisonBarItem[] = records.map((r) => {
    const rawA = r.company_a_value ?? getCompanyVal(r.company_a);
    const rawB = r.company_b_value ?? getCompanyVal(r.company_b);
    const numA = parseNumericValue(rawA);
    const numB = parseNumericValue(rawB);
    return {
      metric: r.metric,
      companyA: numA,
      companyB: numB,
      displayA: rawA !== null && rawA !== undefined ? formatFinancialValue(rawA) : '—',
      displayB: rawB !== null && rawB !== undefined ? formatFinancialValue(rawB) : '—',
    };
  });

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      <AnalysisHeader
        onAskQuestion={() => setActiveView('research')}
        onCompare={() => {}}
      />

      {errorMessage && (
        <ErrorBanner
          title="Peer Comparison Notice"
          message={errorMessage}
          onRetry={fetchComparison}
        />
      )}

      {/* When Company B is NOT uploaded yet: Upload Peer Dropzone */}
      {!comparison ? (
        <div className="space-y-6">
          <Card className="border-slate-800 bg-slate-900/90 p-6 sm:p-8 space-y-6">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-xs font-semibold text-cyan-300">
                <GitCompare className="w-3.5 h-3.5" />
                <span>Cross-Company Benchmark Workflow</span>
              </div>
              <h2 className="text-xl sm:text-2xl font-extrabold text-white">
                Benchmark {activeCompany || 'Active Company'} with a Peer
              </h2>
              <p className="text-xs sm:text-sm text-slate-400 max-w-2xl leading-relaxed">
                Upload a second company's financial report to generate structured side-by-side metric comparisons, percentage variances, and comparative reasoning.
              </p>
            </div>

            {/* Dropzone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                if (e.dataTransfer.files?.[0]) handleFileSelect(e.dataTransfer.files[0]);
              }}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer flex flex-col items-center justify-center ${
                isDragging
                  ? 'border-indigo-400 bg-indigo-950/30'
                  : peerFile
                  ? 'border-indigo-500/60 bg-slate-950/60'
                  : 'border-slate-800 hover:border-slate-700 bg-slate-950/40 hover:bg-slate-950/70'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt"
                onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
                className="hidden"
              />

              {peerFile ? (
                <div className="flex flex-col items-center space-y-2">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
                    <FileText className="w-6 h-6" />
                  </div>
                  <p className="font-semibold text-slate-100 text-sm">{peerFile.name}</p>
                  <p className="text-xs text-slate-400 font-mono">{formatFileSize(peerFile.size)}</p>
                  <Badge variant="primary" size="sm">Peer Document Loaded</Badge>
                </div>
              ) : (
                <div className="flex flex-col items-center space-y-2">
                  <div className="w-12 h-12 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400">
                    <UploadCloud className="w-6 h-6" />
                  </div>
                  <p className="font-semibold text-slate-200 text-sm">Upload Company B Financial Report</p>
                  <p className="text-xs text-slate-400">PDF or TXT filing</p>
                </div>
              )}
            </div>

            {/* Inputs */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">
                  Company B Name <span className="text-slate-400 font-normal">(Optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Infosys, Orion Steelworks"
                  value={peerCompany}
                  onChange={(e) => setPeerCompany(e.target.value)}
                  disabled={isUploadingPeer}
                  className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">
                  Report Year <span className="text-slate-400 font-normal">(Optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. 2025"
                  value={peerYear}
                  onChange={(e) => setPeerYear(e.target.value)}
                  disabled={isUploadingPeer}
                  className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button
                variant="primary"
                size="md"
                onClick={handleUploadPeer}
                disabled={!peerFile || isUploadingPeer}
                isLoading={isUploadingPeer}
                rightIcon={<ArrowRight className="w-4 h-4" />}
                className="bg-indigo-600 hover:bg-indigo-500 text-white"
              >
                Run Peer Comparison
              </Button>
            </div>
          </Card>

          {/* Quick-Load Verified Peer Presets */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Quick Peer Presets
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {PEER_SAMPLES.map((sample, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-900 transition-all flex items-center justify-between gap-4"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-200 text-sm">{sample.company}</span>
                      <Badge variant="outline" size="sm">FY {sample.year}</Badge>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{sample.description}</p>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => loadPeerPreset(sample)}
                    className="shrink-0"
                  >
                    Select Peer
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* Render Comparative Results */
        <div className="space-y-6">
          {/* Header Banner */}
          <Card className="border-slate-800 bg-slate-900/90 p-5 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 font-bold text-lg text-white">
                <span className="text-cyan-400">{compA}</span>
                <span className="text-slate-500 font-mono text-sm">vs</span>
                <span className="text-indigo-400">{compB}</span>
              </div>
              <Badge variant="primary" size="sm">
                Peer Benchmarking Complete
              </Badge>
            </div>

            <Button
              size="sm"
              variant="outline"
              onClick={() => setComparison(null)}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Benchmark Different Peer
            </Button>
          </Card>

          {/* Visual Bar Comparison Chart */}
          {barChartData.length > 0 && (
            <Card className="border-slate-800 bg-slate-900/80 p-5">
              <CardHeader className="p-0 pb-4">
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-cyan-400" />
                  Comparative Scale Overview
                </CardTitle>
                <p className="text-xs text-slate-400 mt-0.5">
                  Visualized magnitude comparison across primary financial line items
                </p>
              </CardHeader>
              <CardContent className="p-0">
                <BarComparisonChart
                  data={barChartData}
                  companyAName={compA}
                  companyBName={compB}
                />
              </CardContent>
            </Card>
          )}

          {/* Comparative Metrics Table */}
          <Card className="border-slate-800 bg-slate-900/80">
            <CardHeader className="border-b border-slate-800/60 pb-3">
              <CardTitle className="text-base">Side-by-Side Line Item Variance</CardTitle>
              <p className="text-xs text-slate-400 mt-0.5">
                Exact reported metrics and calculated variance
              </p>
            </CardHeader>
            <CardContent className="p-0 overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse min-w-[700px]">
                <thead className="bg-slate-950/70 text-slate-300 font-semibold border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-5">Financial Metric</th>
                    <th className="py-3 px-5 text-cyan-400">{compA}</th>
                    <th className="py-3 px-5 text-indigo-400">{compB}</th>
                    <th className="py-3 px-5 text-right">Variance ($)</th>
                    <th className="py-3 px-5 text-right">Variance (%)</th>
                    <th className="py-3 px-5">Analyst Interpretation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                  {records.length > 0 ? (
                    records.map((rec, idx) => {
                      const valA = rec.company_a_value ?? getCompanyVal(rec.company_a);
                      const valB = rec.company_b_value ?? getCompanyVal(rec.company_b);
                      const diffPct = rec.difference_pct ?? rec.diff_percent ?? rec.percentage_difference;
                      return (
                        <tr key={idx} className="hover:bg-slate-900/40 transition-colors">
                          <td className="py-3.5 px-5 font-sans font-medium text-slate-200">
                            {rec.metric}
                          </td>
                          <td className="py-3.5 px-5 font-bold text-cyan-300">
                            {formatFinancialValue(valA)}
                          </td>
                          <td className="py-3.5 px-5 font-bold text-indigo-300">
                            {formatFinancialValue(valB)}
                          </td>
                          <td className="py-3.5 px-5 text-right text-slate-300">
                            {rec.difference !== undefined && rec.difference !== null
                              ? formatFinancialValue(rec.difference)
                              : '—'}
                          </td>
                          <td className="py-3.5 px-5 text-right font-bold text-slate-200">
                            {diffPct !== undefined && diffPct !== null ? formatPercent(diffPct) : '—'}
                          </td>
                          <td className="py-3.5 px-5 font-sans text-slate-400 text-xs max-w-xs truncate">
                            {rec.interpretation || rec.direction || '—'}
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-slate-500 font-sans text-xs">
                        No metric variance records returned from comparison agent.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {/* Comparison Summary Section */}
          {comparison.summary && (
            <Card className="border-slate-800 bg-slate-900/80 p-5 space-y-3">
              <CardTitle className="text-base flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-cyan-400" />
                Executive Comparison Summary
              </CardTitle>
              <div className="text-xs text-slate-300 leading-relaxed font-sans">
                {typeof comparison.summary === 'string' ? (
                  <MarkdownRenderer content={comparison.summary} />
                ) : (
                  <div className="space-y-1.5">
                    <p className="font-semibold text-slate-200">
                      Benchmark Analysis: {compA} vs. {compB}
                    </p>
                    <ul className="list-disc list-inside space-y-1 text-slate-300">
                      {records
                        .filter((r) => r.interpretation && !r.interpretation.includes('cannot be performed'))
                        .map((r, i) => (
                          <li key={i}>
                            <span className="font-medium text-cyan-300">{r.metric}:</span> {r.interpretation}
                          </li>
                        ))}
                    </ul>
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
