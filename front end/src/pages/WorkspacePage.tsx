import React, { useState, useRef, ChangeEvent, DragEvent } from 'react';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Layers,
  Sparkles,
  X,
  ChevronRight,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { api, ApiError } from '../lib/api';
import { Button } from '../components/ui/Button';
import { Card, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { formatFileSize } from '../lib/formatters';
import { AnalysisUploadResponse } from '../lib/types';

// Sample filings that exist in the repository backend for rapid testing
const SAMPLE_PRESETS = [
  {
    name: 'ABB Ltd. — FY 2025 Annual Report',
    company: 'ABB',
    year: '2025',
    type: 'Industrial Automation & Electrification',
    description: '$15.3B revenue, solid balance sheet, supply chain & currency risks.',
    textSample: `ABB Annual Report 2025\n\nABB Ltd.\nFor the year ended December 31, 2025\n\nManagement Discussion and Analysis\n\nRevenue increased 14% to $15.3 billion, driven by strong demand in electrification and automation. Operating income increased to $2.1 billion, supported by infrastructure investments and productivity measures.\n\nThe company continued to invest in research and development, with a focus on automation, robotics, and electrification. We also expanded manufacturing capacity in Europe and North America to support growth.\n\nBalance Sheet\n\nTotal assets were $22.6 billion and total liabilities were $9.8 billion. The company maintained a solid balance sheet with adequate liquidity. The debt ratio remained manageable during the year.\n\nRisk Factors\n\nThe business faces risks related to inflation, supply chain disruptions, and the pace of industrial investment. Currency volatility and delays in project execution could affect reported earnings. We also continue to monitor cybersecurity risks and the impacts of global trade tensions.\n\nGoing concern and liquidity remain stable, although macroeconomic volatility could pressure order intake and project conversion.`,
  },
  {
    name: 'Nimbus Cloud Tech — FY 2024 Filing',
    company: 'Nimbus Cloud Technologies',
    year: '2024',
    type: 'Enterprise SaaS & Cloud Infrastructure',
    description: '$145.6M revenue, $-38.2M operating loss, auditor going concern paragraph, CFO turnover.',
    textSample: `Nimbus Cloud Technologies Inc — Annual Report\n\nManagement Discussion and Analysis (MD&A)\nNimbus Cloud Technologies Inc provides workflow-automation software to mid-market enterprises. FY2024 revenue grew rapidly on strong new-customer bookings, though the company remains unprofitable as it invests heavily in sales and R&D.\n\nIncome Statement Highlights\nTotal Revenue: $145.6 million (FY2024), compared to Total Revenue: $96.3 million (FY2023)\nGross Profit: $102.0 million (FY2024)\nOperating Income: $-38.2 million (FY2024)\nNet Income: $-41.0 million (FY2024)\nEarnings Per Share (EPS): $-0.62 (FY2024)\nR&D Expense: $44.0 million (FY2024)\n\nBalance Sheet Highlights\nTotal Assets: $210.0 million (FY2024)\nTotal Liabilities: $150.0 million (FY2024)\nTotal Equity: $60.0 million (FY2024)\nTotal Debt: $95.0 million (FY2024)\nCash and Cash Equivalents: $28.4 million (FY2024)\n\nAuditor's Report\nThe auditors' report includes an explanatory paragraph expressing substantial doubt about the company's ability to continue as a going concern, citing recurring losses and negative operating cash flow.\n\nRisk Factors\nThe company disclosed a resignation of the CFO in the fourth quarter of FY2024. Nimbus Cloud Technologies Inc also disclosed related party transaction arrangements.`,
  },
];

type ProcessingStep = 'idle' | 'uploading' | 'chunking' | 'indexing' | 'complete';

export function WorkspacePage() {
  const { setActiveSession, setActiveView } = useApp();

  const [file, setFile] = useState<File | null>(null);
  const [companyName, setCompanyName] = useState('');
  const [reportYear, setReportYear] = useState('2025');
  const [initialQuestion, setInitialQuestion] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [processingStep, setProcessingStep] = useState<ProcessingStep>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<AnalysisUploadResponse | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (selectedFile: File) => {
    const ext = selectedFile.name.split('.').pop()?.toLowerCase();
    if (ext !== 'pdf' && ext !== 'txt') {
      setErrorMessage('Only PDF (.pdf) and Plain Text (.txt) financial filings are supported.');
      return;
    }
    setFile(selectedFile);
    setErrorMessage(null);

    // Auto-detect company name if filename has clues
    const nameClean = selectedFile.name.replace(/\.(pdf|txt)$/i, '').replace(/[-_]/g, ' ');
    if (!companyName) {
      if (/abb/i.test(nameClean)) setCompanyName('ABB');
      else if (/nimbus/i.test(nameClean)) setCompanyName('Nimbus Cloud Technologies');
      else if (/infosys/i.test(nameClean)) setCompanyName('Infosys');
      else setCompanyName(nameClean.split(' ')[0] || '');
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const loadPreset = (preset: (typeof SAMPLE_PRESETS)[0]) => {
    const blob = new Blob([preset.textSample], { type: 'text/plain' });
    const sampleFile = new File([blob], `${preset.company.toLowerCase()}_${preset.year}_report.txt`, {
      type: 'text/plain',
    });
    setFile(sampleFile);
    setCompanyName(preset.company);
    setReportYear(preset.year);
    setErrorMessage(null);
  };

  const handleStartAnalysis = async () => {
    if (!file) {
      setErrorMessage('Please select or drop a financial filing to begin.');
      return;
    }

    setErrorMessage(null);
    setProcessingStep('uploading');

    try {
      // Realistic stage updates for user feedback while backend executes
      const stepTimer1 = setTimeout(() => setProcessingStep('chunking'), 400);
      const stepTimer2 = setTimeout(() => setProcessingStep('indexing'), 900);

      const response = await api.uploadAnalysis(
        file,
        companyName || undefined,
        reportYear || undefined,
        initialQuestion || undefined
      );

      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);

      setUploadResult(response);
      setProcessingStep('complete');

      // Update global application session
      setActiveSession({
        analysisId: response.analysis_id,
        companyName: response.company_name || companyName || 'Company',
        reportYear: response.report_year || reportYear || '2025',
        documentName: response.document || file.name,
        totalChunks: response.total_chunks,
      });
    } catch (err) {
      setProcessingStep('idle');
      if (err instanceof ApiError) {
        setErrorMessage(err.detail || err.message);
      } else if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Failed to process and ingest document. Please verify the backend is running.');
      }
    }
  };

  const handleProceedToOverview = () => {
    setActiveView('overview');
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-12">
      {/* Header Banner */}
      <div className="space-y-2">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-xs font-semibold text-cyan-300">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Multi-Agent Document Ingestion Engine</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Ingest Financial Filing
        </h1>
        <p className="text-sm text-slate-400 max-w-2xl leading-relaxed">
          Upload an official Annual Report, 10-K, 10-Q, or earnings filing. The system performs structural chunking, vector embedding in ChromaDB, and prepares multi-agent agents for deep analysis.
        </p>
      </div>

      {/* Main Upload Card */}
      <Card className="border-slate-800 bg-slate-900/90 shadow-xl">
        <CardContent className="p-6 sm:p-8 space-y-6">
          {/* Dropzone */}
          {!uploadResult ? (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center transition-all cursor-pointer flex flex-col items-center justify-center ${
                isDragging
                  ? 'border-cyan-400 bg-cyan-950/30 scale-[0.99]'
                  : file
                  ? 'border-cyan-500/60 bg-slate-950/60'
                  : 'border-slate-800 hover:border-slate-700 bg-slate-950/40 hover:bg-slate-950/70'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt"
                onChange={handleInputChange}
                className="hidden"
              />

              {file ? (
                <div className="flex flex-col items-center space-y-3">
                  <div className="w-14 h-14 rounded-2xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-md">
                    <FileText className="w-7 h-7" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-100 text-sm">{file.name}</p>
                    <p className="text-xs text-slate-400 font-mono mt-0.5">{formatFileSize(file.size)}</p>
                  </div>
                  <Badge variant="primary" size="sm">
                    Ready to Process
                  </Badge>
                  <p className="text-[11px] text-slate-500 hover:text-slate-400 pt-1">
                    Click or drag another file to replace
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center space-y-3">
                  <div className="w-14 h-14 rounded-2xl bg-slate-800/80 border border-slate-700/60 flex items-center justify-center text-slate-400 shadow-inner">
                    <UploadCloud className="w-7 h-7 stroke-[1.5]" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-200 text-sm">
                      Upload a financial filing
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      Drag & drop your document here, or click to browse
                    </p>
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    <Badge variant="outline" size="sm">PDF Document (.pdf)</Badge>
                    <Badge variant="outline" size="sm">Plain Text (.txt)</Badge>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Success State Preview */
            <div className="rounded-2xl border border-emerald-800/60 bg-emerald-950/20 p-6 sm:p-8 space-y-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3.5">
                  <div className="w-12 h-12 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-slate-100">
                      Document Successfully Ingested
                    </h3>
                    <p className="text-xs text-emerald-300/90 font-mono mt-0.5">
                      Session ID: {uploadResult.analysis_id}
                    </p>
                  </div>
                </div>
                <Badge variant="success" size="md">
                  ChromaDB Ready
                </Badge>
              </div>

              {/* Ingestion Highlights */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Company</span>
                  <p className="font-bold text-slate-100 truncate text-sm">{uploadResult.company_name || companyName}</p>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Fiscal Year</span>
                  <p className="font-bold text-slate-100 font-mono text-sm">FY {uploadResult.report_year || reportYear}</p>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Vector Chunks</span>
                  <p className="font-bold text-cyan-400 font-mono text-sm">{uploadResult.total_chunks} chunks</p>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Collection</span>
                  <p className="font-bold text-slate-300 font-mono text-xs truncate">{uploadResult.collection || 'v1'}</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setUploadResult(null);
                    setFile(null);
                    setProcessingStep('idle');
                  }}
                >
                  Upload Another Document
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  onClick={handleProceedToOverview}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  Open Analysis Overview
                </Button>
              </div>
            </div>
          )}

          {/* Form Fields: Metadata & Optional Prompts */}
          {!uploadResult && (
            <div className="space-y-4 pt-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">
                    Company Name <span className="text-slate-400 font-normal">(Optional)</span>
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. ABB Ltd., Apple Inc."
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    disabled={processingStep !== 'idle'}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 font-medium disabled:opacity-50"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">
                    Report Year <span className="text-slate-400 font-normal">(Optional)</span>
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. 2025, 2024"
                    value={reportYear}
                    onChange={(e) => setReportYear(e.target.value)}
                    disabled={processingStep !== 'idle'}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 font-mono disabled:opacity-50"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">
                  Initial Focus Question <span className="text-slate-400 font-normal">(Optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. What were the key growth drivers and primary risk factors?"
                  value={initialQuestion}
                  onChange={(e) => setInitialQuestion(e.target.value)}
                  disabled={processingStep !== 'idle'}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 disabled:opacity-50"
                />
              </div>
            </div>
          )}

          {/* Processing Progress Feedback */}
          {processingStep !== 'idle' && processingStep !== 'complete' && (
            <div className="p-5 rounded-xl bg-slate-950 border border-cyan-500/40 space-y-4 animate-subtle-pulse">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-cyan-300 flex items-center gap-2">
                  <Layers className="w-4 h-4 animate-spin text-cyan-400" />
                  {processingStep === 'uploading' && 'Uploading document stream...'}
                  {processingStep === 'chunking' && 'Running Document Agent semantic chunking...'}
                  {processingStep === 'indexing' && 'Indexing embeddings in ChromaDB collection...'}
                </span>
                <span className="font-mono text-cyan-400 text-[11px]">Synchronous Pipeline</span>
              </div>

              {/* Stepper */}
              <div className="grid grid-cols-3 gap-2 text-[11px]">
                <div
                  className={`p-2 rounded-lg border flex items-center gap-1.5 ${
                    processingStep === 'uploading' || processingStep === 'chunking' || processingStep === 'indexing'
                      ? 'border-cyan-500/50 bg-cyan-950/40 text-cyan-200'
                      : 'border-slate-800 text-slate-500'
                  }`}
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  <span>1. Upload</span>
                </div>
                <div
                  className={`p-2 rounded-lg border flex items-center gap-1.5 ${
                    processingStep === 'chunking' || processingStep === 'indexing'
                      ? 'border-cyan-500/50 bg-cyan-950/40 text-cyan-200'
                      : 'border-slate-800 text-slate-500'
                  }`}
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  <span>2. Chunk Text</span>
                </div>
                <div
                  className={`p-2 rounded-lg border flex items-center gap-1.5 ${
                    processingStep === 'indexing'
                      ? 'border-cyan-500/50 bg-cyan-950/40 text-cyan-200'
                      : 'border-slate-800 text-slate-500'
                  }`}
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  <span>3. Vector Store</span>
                </div>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {errorMessage && (
            <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/80 text-rose-200 text-xs flex items-start gap-3">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div className="flex-1">
                <strong className="font-semibold block text-rose-300">Upload Issue</strong>
                <span>{errorMessage}</span>
              </div>
              <button
                onClick={() => setErrorMessage(null)}
                className="text-rose-400 hover:text-rose-200 p-1"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Action Bar */}
          {!uploadResult && (
            <div className="flex items-center justify-between pt-2">
              {file ? (
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  className="text-xs text-slate-400 hover:text-rose-400 transition-colors"
                >
                  Remove selected file
                </button>
              ) : (
                <span className="text-xs text-slate-500">No document selected</span>
              )}

              <Button
                variant="primary"
                size="lg"
                onClick={handleStartAnalysis}
                isLoading={processingStep !== 'idle' && processingStep !== 'complete'}
                disabled={!file}
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Run Ingestion & Analysis
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick Test Samples */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Quick-Load Verified Test Filings
          </h3>
          <span className="text-xs text-slate-500 font-mono">Real Benchmark Data</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {SAMPLE_PRESETS.map((preset, idx) => (
            <div
              key={idx}
              className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 hover:bg-slate-900 hover:border-slate-700 transition-all space-y-3 flex flex-col justify-between"
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 text-sm">{preset.company}</span>
                  <Badge variant="primary" size="sm" className="font-mono">
                    FY {preset.year}
                  </Badge>
                </div>
                <div className="text-[11px] text-cyan-400/90 font-medium">{preset.type}</div>
                <p className="text-xs text-slate-400 leading-relaxed">{preset.description}</p>
              </div>

              <Button
                size="sm"
                variant="secondary"
                onClick={() => loadPreset(preset)}
                className="w-full justify-between"
                rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
              >
                Load Filing
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
