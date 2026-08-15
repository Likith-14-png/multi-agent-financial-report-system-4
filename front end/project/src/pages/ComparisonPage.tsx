import { useState } from 'react';
import { Card, Badge, PageHeader } from '@/components/ui';
import { Icon } from '@/components/Icon';
import { GroupedBarChart } from '@/components/Charts';
import { COMPANIES } from '@/lib/mockData';

const METRICS = [
  { key: 'revenue', label: 'Revenue', icon: 'DollarSign', format: (v: number) => `$${v}B` },
  { key: 'netIncome', label: 'Net Income', icon: 'Wallet', format: (v: number) => `$${v}B` },
  { key: 'assets', label: 'Assets', icon: 'Building2', format: (v: number) => `$${v}B` },
  { key: 'debt', label: 'Debt', icon: 'Banknote', format: (v: number) => `$${v}B` },
  { key: 'operatingMargin', label: 'Operating Margin', icon: 'Percent', format: (v: number) => `${v}%` },
  { key: 'cashFlow', label: 'Cash Flow', icon: 'Activity', format: (v: number) => `$${v}B` },
  { key: 'eps', label: 'EPS', icon: 'TrendingUp', format: (v: number) => `$${v}` },
] as const;

const CHART_METRICS = [
  { key: 'revenue', label: 'Revenue', color: '#2563eb' },
  { key: 'netIncome', label: 'Net Income', color: '#06b6d4' },
  { key: 'cashFlow', label: 'Cash Flow', color: '#10b981' },
  { key: 'operatingMargin', label: 'Operating Margin', color: '#f59e0b' },
] as const;

const COLORS = ['#2563eb', '#06b6d4', '#10b981', '#f59e0b'];

export function ComparisonPage() {
  const [selectedMetric, setSelectedMetric] = useState<(typeof CHART_METRICS)[number]>(CHART_METRICS[0]);
  const [selectedCompanies, setSelectedCompanies] = useState<string[]>(COMPANIES.map((c) => c.ticker));

  const toggleCompany = (ticker: string) => {
    setSelectedCompanies((prev) =>
      prev.includes(ticker) ? prev.filter((t) => t !== ticker) : [...prev, ticker]
    );
  };

  const visibleCompanies = COMPANIES.filter((c) => selectedCompanies.includes(c.ticker));

  const chartSeries = CHART_METRICS.filter((m) => m.key === selectedMetric.key).map((m) => ({
    name: m.label,
    data: visibleCompanies.map((c) => (c as unknown as Record<string, number>)[m.key]),
    color: m.color,
  }));

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Company Comparison"
        subtitle="Side-by-side financial metrics across analyzed companies"
        action={
          <div className="flex items-center gap-2">
            <button className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl border border-base text-sm font-medium text-secondary hover:bg-subtle transition-colors">
              <Icon name="Download" size={16} /> Export
            </button>
            <button className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl gradient-brand text-white text-sm font-medium shadow-card hover:shadow-elevated transition-all">
              <Icon name="Filter" size={16} /> Filter
            </button>
          </div>
        }
      />

      {/* Company selector chips */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <span className="text-xs font-medium text-tertiary mr-1">Companies:</span>
        {COMPANIES.map((c, i) => {
          const active = selectedCompanies.includes(c.ticker);
          return (
            <button
              key={c.ticker}
              onClick={() => toggleCompany(c.ticker)}
              className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium border transition-all ${
                active
                  ? 'bg-surface border-base text-primary shadow-soft'
                  : 'bg-subtle border-base text-tertiary hover:text-secondary'
              }`}
            >
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: active ? COLORS[i % COLORS.length] : '#cbd5e1' }} />
              {c.name}
              {active && <Icon name="X" size={13} className="text-tertiary" />}
            </button>
          );
        })}
      </div>

      {/* Comparison table */}
      <Card className="mb-6 overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full">
            <thead>
              <tr className="border-b border-base bg-subtle">
                <th className="text-left px-5 py-3.5 text-xs font-semibold text-secondary uppercase tracking-wider">Company</th>
                {METRICS.map((m) => (
                  <th key={m.key} className="text-right px-5 py-3.5 text-xs font-semibold text-secondary uppercase tracking-wider whitespace-nowrap">
                    {m.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleCompanies.map((c, i) => (
                <tr key={c.ticker} className="border-b border-base last:border-0 hover:bg-subtle transition-colors group">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 text-white text-sm font-bold" style={{ background: COLORS[i % COLORS.length] }}>
                        {c.name.charAt(0)}
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-primary">{c.name}</p>
                        <p className="text-xs text-tertiary">{c.ticker} · {c.sector}</p>
                      </div>
                    </div>
                  </td>
                  {METRICS.map((m) => {
                    const value = (c as unknown as Record<string, number>)[m.key];
                    return (
                      <td key={m.key} className="text-right px-5 py-4 text-sm font-medium text-primary tabular-nums whitespace-nowrap">
                        {m.format(value)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Grouped bar */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-primary">Metric Comparison</h3>
            <div className="flex items-center gap-1 p-1 rounded-xl bg-subtle">
              {CHART_METRICS.map((m) => (
                <button
                  key={m.key}
                  onClick={() => setSelectedMetric(m)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    selectedMetric.key === m.key ? 'bg-surface text-primary shadow-soft' : 'text-secondary hover:text-primary'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>
          <GroupedBarChart
            groups={visibleCompanies.map((c) => c.ticker)}
            series={chartSeries}
            height={280}
            formatY={(v) => (selectedMetric.key === 'operatingMargin' ? `${Math.round(v)}%` : `$${Math.round(v)}B`)}
          />
        </Card>

        {/* Revenue trend comparison */}
        <Card className="p-6">
          <h3 className="text-base font-semibold text-primary mb-1">Revenue Trend (4-Year)</h3>
          <p className="text-xs text-secondary mb-4">Trailing fiscal years · $B</p>
          <div className="space-y-4">
            {visibleCompanies.map((c, i) => {
              const max = Math.max(...c.revenueHistory);
              return (
                <div key={c.ticker}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                      <span className="text-sm font-medium text-primary">{c.name}</span>
                    </div>
                    <span className="text-xs text-secondary tabular-nums">
                      {c.revenueHistory[0]} → {c.revenueHistory[c.revenueHistory.length - 1]}B
                    </span>
                  </div>
                  <div className="flex items-end gap-1.5 h-16">
                    {c.revenueHistory.map((v, j) => (
                      <div key={j} className="flex-1 flex flex-col items-center gap-1">
                        <div
                          className="w-full rounded-t-md transition-all duration-700 hover:opacity-80"
                          style={{
                            height: `${(v / max) * 100}%`,
                            background: COLORS[i % COLORS.length],
                            opacity: 0.4 + (j / (c.revenueHistory.length - 1)) * 0.6,
                          }}
                        />
                        <span className="text-[10px] text-tertiary">FY{22 + j}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Key insights */}
      <Card className="p-6 mt-6">
        <div className="flex items-center gap-2 mb-4">
          <Icon name="Sparkles" size={18} className="text-brand-600 dark:text-brand-400" />
          <h3 className="text-base font-semibold text-primary">AI-Generated Insights</h3>
          <Badge variant="brand">Comparison Agent</Badge>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { icon: 'TrendingUp', color: 'text-emerald-500', title: 'Microsoft leads margin', desc: '44.7% operating margin — highest in the cohort, driven by Azure software economics.' },
            { icon: 'DollarSign', color: 'text-brand-500', title: 'Amazon tops revenue', desc: '$574.8B in revenue, 2.3x larger than Microsoft, but with thinner 8.1% margins.' },
            { icon: 'TrendingDown', color: 'text-danger-500', title: 'Apple revenue declining', desc: 'Only company with negative revenue growth (-2.8%), signaling iPhone cycle pressure.' },
          ].map((insight, i) => (
            <div key={i} className="p-4 rounded-xl border border-base hover:shadow-card transition-all">
              <Icon name={insight.icon} size={20} className={insight.color + ' mb-2'} />
              <p className="text-sm font-semibold text-primary">{insight.title}</p>
              <p className="text-xs text-secondary mt-1 leading-relaxed">{insight.desc}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
