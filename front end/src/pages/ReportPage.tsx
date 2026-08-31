import React, { useEffect, useState } from 'react';
import {
  FileText,
  Download,
  CheckCircle2,
  AlertTriangle,
  Bookmark,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { api, ApiError } from '../lib/api';
import { ReportResponse } from '../lib/types';
import { formatFinancialValue } from '../lib/formatters';
import { AnalysisHeader } from '../components/AnalysisHeader';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { CardSkeleton } from '../components/ui/Skeleton';
import { MarkdownRenderer } from '../components/ui/MarkdownRenderer';

export function ReportPage() {
  const { activeSessionId, activeCompany, activeYear, setActiveView } = useApp();

  const [report, setReport] = useState<ReportResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchReport = async () => {
    if (!activeSessionId) return;
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await api.getReport(activeSessionId);
      setReport(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.detail || err.message);
      } else {
        setErrorMessage('Failed to synthesize executive report from agents.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [activeSessionId]);

  if (!activeSessionId) {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <EmptyState
          icon={FileText}
          title="No Active Filing for Report Generation"
          description="Upload a filing in the Workspace to synthesize a comprehensive publication-quality Executive Financial Report."
          actionLabel="Go to Workspace"
          onAction={() => setActiveView('workspace')}
        />
      </div>
    );
  }

  const handleDownloadPdf = async () => {
    if (!activeSessionId) return;
    setIsDownloading(true);
    try {
      await api.downloadReportPdf(activeSessionId, activeCompany || undefined, activeYear || undefined);
    } catch (err) {
      console.error('PDF download error:', err);
      setErrorMessage('Failed to download report PDF. Verify backend ReportLab service.');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <AnalysisHeader
        onAskQuestion={() => setActiveView('research')}
        onCompare={() => setActiveView('comparison')}
      />

      {errorMessage && (
        <ErrorBanner
          title="Executive Report Synthesis Notice"
          message={errorMessage}
          onRetry={fetchReport}
        />
      )}

      {/* Report Publication Header */}
      <Card className="border-slate-800 bg-slate-900/90 p-6 sm:p-8 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-xs font-semibold text-cyan-300">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Formal Executive Synthesis</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Financial Research & Audit Report
          </h2>
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 font-mono">
            <span className="text-slate-200 font-semibold">{report?.company_name || activeCompany}</span>
            <span>·</span>
            <span>Fiscal Year {report?.report_year || activeYear}</span>
            <span>·</span>
            <Badge variant="success" size="sm">
              Status: {report?.report_status || 'Complete'}
            </Badge>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button
            variant="primary"
            size="lg"
            onClick={handleDownloadPdf}
            isLoading={isDownloading}
            leftIcon={<Download className="w-4 h-4" />}
            className="shadow-lg shadow-cyan-900/30"
          >
            Download Formal PDF
          </Button>
        </div>
      </Card>

      {/* Main Report Body Canvas */}
      {isLoading ? (
        <div className="space-y-6">
          <CardSkeleton lines={6} />
          <CardSkeleton lines={4} />
          <CardSkeleton lines={5} />
        </div>
      ) : report ? (
        <div className="space-y-6">
          {/* Section 1: Executive Summary */}
          <Card className="border-slate-800 bg-slate-900/80 p-6 sm:p-8 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <FileText className="w-4 h-4 text-cyan-400" />
                1. Executive Summary
              </h3>
              <span className="text-[11px] text-slate-500 font-mono">Synthesis</span>
            </div>
            <div className="text-sm text-slate-200 leading-relaxed font-sans">
              {report.executive_summary ? (
                <MarkdownRenderer content={report.executive_summary} />
              ) : (
                <p className="italic text-slate-400">Executive summary synthesis generated from multi-agent agents.</p>
              )}
            </div>
          </Card>

          {/* Section 2: Core Financial Metrics Summary */}
          {report.financial_metrics && report.financial_metrics.length > 0 && (
            <Card className="border-slate-800 bg-slate-900/80 p-6 sm:p-8 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-cyan-400" />
                  2. Key Financial Line Items
                </h3>
                <span className="text-[11px] text-slate-500 font-mono">Audited Statements</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse font-mono">
                  <thead className="bg-slate-950/60 text-slate-400 font-semibold border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-4">Line Item</th>
                      <th className="py-2.5 px-4 text-right">Reported Figure</th>
                      <th className="py-2.5 px-4">Period</th>
                      <th className="py-2.5 px-4">Classification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-[11px]">
                    {report.financial_metrics.map((m, idx) => (
                      <tr key={idx} className="hover:bg-slate-950/40">
                        <td className="py-2.5 px-4 font-sans font-medium text-slate-200">
                          {String(m.metric || m.canonical_label || m.metric_name || `Metric #${idx + 1}`)}
                        </td>
                        <td className="py-2.5 px-4 text-right font-bold text-cyan-300">
                          {formatFinancialValue(m.value as string | number)}
                        </td>
                        <td className="py-2.5 px-4 text-slate-400">
                          FY {String(m.period || m.year || activeYear)}
                        </td>
                        <td className="py-2.5 px-4 text-slate-400 font-sans">
                          {String(m.unit || m.category || 'Audited')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Section 3: Grounded Research Findings */}
          {report.research_findings && report.research_findings.length > 0 && (
            <Card className="border-slate-800 bg-slate-900/80 p-6 sm:p-8 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <Bookmark className="w-4 h-4 text-cyan-400" />
                  3. Strategic MD&A & Research Findings
                </h3>
                <span className="text-[11px] text-slate-500 font-mono">Research Retrieval</span>
              </div>

              <div className="space-y-3">
                {report.research_findings.map((f, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300 space-y-1">
                    <MarkdownRenderer content={typeof f === 'string' ? f : JSON.stringify(f)} />
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Section 4: Risk & Red Flag Assessment */}
          {report.risk_assessment && (
            <Card className="border-slate-800 bg-slate-900/80 p-6 sm:p-8 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  4. Risk Assessment & Footnote Analysis
                </h3>
                <Badge
                  variant="risk"
                  riskSeverity={String(report.risk_assessment.overall_risk || 'Low')}
                  size="sm"
                >
                  {String(report.risk_assessment.overall_risk || 'Low')} Risk
                </Badge>
              </div>

              <div className="text-xs text-slate-300 leading-relaxed">
                {typeof report.risk_assessment === 'string' ? (
                  <MarkdownRenderer content={report.risk_assessment} />
                ) : (
                  <div className="space-y-3">
                    <p>
                      Identified {String(report.risk_assessment.total_flags ?? '0')} audit disclosure and liquidity points.
                    </p>
                    {Array.isArray(report.risk_assessment.flags) && (
                      <div className="space-y-2">
                        {report.risk_assessment.flags.slice(0, 5).map((fl: any, fIdx: number) => (
                          <div key={fIdx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] space-y-1">
                            <span className="font-bold text-slate-200">{fl.title || fl.description}</span>
                            {fl.evidence && <p className="font-mono text-slate-400 italic">"{fl.evidence}"</p>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Section 5: Strategic Analyst Recommendations */}
          {report.recommendations && report.recommendations.length > 0 && (
            <Card className="border-slate-800 bg-slate-900/80 p-6 sm:p-8 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  5. Strategic Recommendations
                </h3>
                <span className="text-[11px] text-slate-500 font-mono">Action Items</span>
              </div>

              <ul className="space-y-2.5">
                {report.recommendations.map((rec, idx) => (
                  <li key={idx} className="flex items-start gap-3 text-xs text-slate-200">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span className="leading-relaxed">{rec}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Bottom Download CTA Bar */}
          <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-cyan-950/40 to-slate-900 border border-cyan-500/30 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-white">Generate Hardcopy PDF Report</h4>
              <p className="text-xs text-slate-400">
                Complete with charts, tabular line items, audit disclosures, and full source citations.
              </p>
            </div>
            <Button
              variant="primary"
              size="md"
              onClick={handleDownloadPdf}
              isLoading={isDownloading}
              leftIcon={<Download className="w-4 h-4" />}
            >
              Export PDF Now
            </Button>
          </div>
        </div>
      ) : (
        <EmptyState
          icon={FileText}
          title="Report Not Ready"
          description="Could not generate synthesized report. Please verify that the filing has completed ingestion."
          actionLabel="Retry Synthesis"
          onAction={fetchReport}
        />
      )}
    </div>
  );
}
