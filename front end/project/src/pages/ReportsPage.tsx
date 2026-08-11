import { useState } from 'react';
import { Card, Badge, PageHeader } from '@/components/ui';
import { Icon } from '@/components/Icon';

const REPORT_TYPES = [
  {
    id: 'executive',
    name: 'Executive Summary',
    icon: 'FileText',
    desc: 'High-level overview of key findings, financial highlights, and top recommendations. 2-3 pages.',
    pages: '2-3 pages',
    badge: 'Quick',
  },
  {
    id: 'detailed',
    name: 'Detailed Analysis',
    icon: 'FileBarChart',
    desc: 'Comprehensive breakdown of all financial metrics, ratios, trend analysis, and agent insights. 8-12 pages.',
    pages: '8-12 pages',
    badge: 'Comprehensive',
  },
  {
    id: 'investment',
    name: 'Investment Report',
    icon: 'FileCheck2',
    desc: 'Investment-focused report with risk assessment, valuation analysis, and buy/hold/sell recommendation. 5-7 pages.',
    pages: '5-7 pages',
    badge: 'Decision-grade',
  },
];

const REPORT_SECTIONS = [
  { label: 'Cover Page', icon: 'FileText' },
  { label: 'Executive Summary', icon: 'Sparkles' },
  { label: 'Financial Highlights', icon: 'DollarSign' },
  { label: 'Ratio Analysis', icon: 'Percent' },
  { label: 'Red Flag Assessment', icon: 'ShieldAlert' },
  { label: 'Comparison Benchmark', icon: 'GitCompare' },
  { label: 'Risk Summary', icon: 'AlertTriangle' },
  { label: 'Investment Recommendation', icon: 'TrendingUp' },
  { label: 'Source Citations', icon: 'FileSearch' },
];

export function ReportsPage() {
  const [selected, setSelected] = useState('detailed');
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [progress, setProgress] = useState(0);

  const generate = () => {
    setGenerating(true);
    setGenerated(false);
    setProgress(0);
    const interval = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) {
          clearInterval(interval);
          setGenerating(false);
          setGenerated(true);
          return 100;
        }
        return p + 5;
      });
    }, 100);
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Report Generation"
        subtitle="Synthesize findings from all agents into a downloadable PDF report"
        action={
          <button
            onClick={generate}
            disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl gradient-brand text-white text-sm font-medium shadow-card hover:shadow-elevated transition-all disabled:opacity-60"
          >
            <Icon name={generating ? 'Loader2' : 'Sparkles'} size={18} className={generating ? 'animate-spin' : ''} />
            {generating ? 'Generating…' : 'Generate Report'}
          </button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Report type selector */}
        <div className="lg:col-span-2">
          <h3 className="text-sm font-semibold text-secondary uppercase tracking-wider mb-3">Select Report Type</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {REPORT_TYPES.map((r) => {
              const active = selected === r.id;
              return (
                <button
                  key={r.id}
                  onClick={() => setSelected(r.id)}
                  className={`text-left p-5 rounded-2xl border-2 transition-all ${
                    active
                      ? 'border-brand-400 bg-brand-50 dark:bg-brand-500/10 shadow-card'
                      : 'border-base bg-surface hover:border-brand-200 hover:shadow-soft'
                  }`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${active ? 'gradient-brand' : 'bg-subtle'}`}>
                      <Icon name={r.icon} size={22} className={active ? 'text-white' : 'text-secondary'} />
                    </div>
                    {active && <Icon name="CheckCircle2" size={18} className="text-brand-500" />}
                  </div>
                  <h4 className="text-sm font-semibold text-primary">{r.name}</h4>
                  <p className="text-xs text-secondary mt-1.5 leading-relaxed">{r.desc}</p>
                  <div className="flex items-center gap-2 mt-3">
                    <Badge variant={active ? 'brand' : 'neutral'}>{r.badge}</Badge>
                    <span className="text-xs text-tertiary">{r.pages}</span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Report sections preview */}
          <Card className="p-6 mt-6">
            <h3 className="text-base font-semibold text-primary mb-4">Report Sections</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {REPORT_SECTIONS.map((s, i) => (
                <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-subtle transition-colors">
                  <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-500/10 flex items-center justify-center shrink-0">
                    <Icon name={s.icon} size={16} className="text-brand-600 dark:text-brand-400" />
                  </div>
                  <span className="text-sm text-secondary">{s.label}</span>
                  <Icon name="Check" size={14} className="text-emerald-500 ml-auto" />
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Generation panel */}
        <div>
          <Card className="p-6 sticky top-20">
            <h3 className="text-base font-semibold text-primary mb-4">Generation Status</h3>

            {/* Progress */}
            {generating && (
              <div className="mb-5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-secondary">Synthesizing report…</span>
                  <span className="text-sm font-semibold text-primary tabular-nums">{progress}%</span>
                </div>
                <div className="h-2.5 rounded-full bg-subtle overflow-hidden">
                  <div className="h-full rounded-full gradient-brand transition-all duration-200" style={{ width: `${progress}%` }} />
                </div>
                <div className="mt-3 space-y-1.5">
                  {['Parsing agent outputs', 'Compiling financial data', 'Generating charts', 'Formatting PDF'].map((step, i) => {
                    const stepProgress = (i + 1) / 4 * 100;
                    const done = progress >= stepProgress;
                    return (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <Icon name={done ? 'CheckCircle2' : 'Loader2'} size={14} className={done ? 'text-emerald-500' : 'text-brand-500 animate-spin'} />
                        <span className={done ? 'text-secondary' : 'text-tertiary'}>{step}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Ready state */}
            {generated && !generating && (
              <div className="mb-5 p-4 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 animate-fade-in">
                <div className="flex items-center gap-2 mb-2">
                  <Icon name="CheckCircle2" size={20} className="text-emerald-500" />
                  <span className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">Report Ready</span>
                </div>
                <p className="text-xs text-emerald-600 dark:text-emerald-500">Your {REPORT_TYPES.find((r) => r.id === selected)?.name} has been generated successfully.</p>
              </div>
            )}

            {/* Idle state */}
            {!generating && !generated && (
              <div className="mb-5 p-4 rounded-xl bg-subtle border border-base">
                <div className="flex items-center gap-2 mb-2">
                  <Icon name="FileBarChart" size={20} className="text-brand-500" />
                  <span className="text-sm font-semibold text-primary">Ready to Generate</span>
                </div>
                <p className="text-xs text-secondary">Click "Generate Report" to synthesize all agent findings into a PDF.</p>
              </div>
            )}

            {/* Report preview card */}
            <div className="p-4 rounded-xl border border-base">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-12 h-16 rounded-lg gradient-brand flex items-center justify-center shrink-0">
                  <Icon name="FileText" size={24} className="text-white" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-primary truncate">
                    {REPORT_TYPES.find((r) => r.id === selected)?.name}
                  </p>
                  <p className="text-xs text-tertiary">Big Tech Q4 Comparison</p>
                  <p className="text-xs text-tertiary mt-0.5">PDF · ~2.4 MB</p>
                </div>
              </div>
              <button
                disabled={!generated}
                onClick={() => setGenerated(false)}
                className={`w-full py-2.5 rounded-xl text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                  generated
                    ? 'bg-brand-600 text-white hover:bg-brand-700 shadow-card'
                    : 'bg-subtle text-tertiary cursor-not-allowed'
                }`}
              >
                <Icon name="Download" size={16} />
                Download PDF
              </button>
            </div>

            {/* Options */}
            <div className="mt-4 space-y-2">
              <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer">
                <input type="checkbox" defaultChecked className="rounded border-base text-brand-500 focus:ring-brand-500/20" />
                Include charts and visualizations
              </label>
              <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer">
                <input type="checkbox" defaultChecked className="rounded border-base text-brand-500 focus:ring-brand-500/20" />
                Include source citations
              </label>
              <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer">
                <input type="checkbox" className="rounded border-base text-brand-500 focus:ring-brand-500/20" />
                Email copy to stakeholders
              </label>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
