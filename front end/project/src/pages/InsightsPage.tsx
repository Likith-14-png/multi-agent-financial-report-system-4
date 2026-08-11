import { useState } from 'react';
import { Card, Badge, PageHeader } from '@/components/ui';
import { Icon } from '@/components/Icon';
import { LineChart, BarChart } from '@/components/Charts';
import { COMPANIES } from '@/lib/mockData';

const INSIGHT_CARDS = [
  { key: 'revenue', label: 'Revenue', icon: 'DollarSign', color: 'brand', value: '$245.1B', change: '+16.2%', trend: 'up' },
  { key: 'netIncome', label: 'Net Profit', icon: 'Wallet', color: 'accent', value: '$88.1B', change: '+22.1%', trend: 'up' },
  { key: 'operatingMargin', label: 'Operating Margin', icon: 'Percent', color: 'brand', value: '44.7%', change: '+2.3pp', trend: 'up' },
  { key: 'assets', label: 'Total Assets', icon: 'Building2', color: 'accent', value: '$512.2B', change: '+8.4%', trend: 'up' },
  { key: 'liabilities', label: 'Liabilities', icon: 'Banknote', color: 'brand', value: '$286.8B', change: '+5.1%', trend: 'up' },
  { key: 'debt', label: 'Total Debt', icon: 'PiggyBank', color: 'accent', value: '$97.4B', change: '+3.2%', trend: 'up' },
  { key: 'cashFlow', label: 'Cash Flow', icon: 'Activity', color: 'brand', value: '$118.5B', change: '+14.8%', trend: 'up' },
] as const;

const colorMap: Record<string, { bg: string; text: string }> = {
  brand: { bg: 'bg-brand-50 dark:bg-brand-500/10', text: 'text-brand-600 dark:text-brand-400' },
  accent: { bg: 'bg-cyan-50 dark:bg-cyan-500/10', text: 'text-cyan-600 dark:text-cyan-400' },
};

export function InsightsPage() {
  const [company, setCompany] = useState(COMPANIES[0]);

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Financial Insights Dashboard"
        subtitle="Deep-dive metrics, trends, and visual analysis"
        action={
          <div className="flex items-center gap-1 p-1 rounded-xl bg-subtle">
            {COMPANIES.slice(0, 4).map((c) => (
              <button
                key={c.ticker}
                onClick={() => setCompany(c)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  company.ticker === c.ticker ? 'bg-surface text-primary shadow-soft' : 'text-secondary hover:text-primary'
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>
        }
      />

      {/* Insight cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4 mb-6">
        {INSIGHT_CARDS.map((card, i) => {
          const c = colorMap[card.color];
          return (
            <Card key={card.key} hover className="p-5 animate-slide-up">
              <div style={{ animationDelay: `${i * 40}ms` }} className="flex items-start justify-between">
                <div className={`w-10 h-10 rounded-xl ${c.bg} flex items-center justify-center`}>
                  <Icon name={card.icon} size={20} className={c.text} />
                </div>
                <Badge variant={card.trend === 'up' ? 'success' : 'danger'}>
                  <Icon name={card.trend === 'up' ? 'ArrowUpRight' : 'ArrowDownRight'} size={12} />
                  {card.change}
                </Badge>
              </div>
              <p className="text-2xl font-bold text-primary mt-3 tracking-tight">{card.value}</p>
              <p className="text-xs text-secondary mt-0.5">{card.label}</p>
            </Card>
          );
        })}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Revenue & profit trend */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-semibold text-primary">Revenue & Profit Trend</h3>
              <p className="text-xs text-secondary mt-0.5">{company.name} · 4 fiscal years · $B</p>
            </div>
            <Badge variant="success"><Icon name="TrendingUp" size={12} /> Growing</Badge>
          </div>
          <LineChart
            labels={['FY22', 'FY23', 'FY24', 'FY25']}
            series={[
              { name: 'Revenue', data: company.revenueHistory, color: '#2563eb' },
              { name: 'Net Income', data: company.profitHistory, color: '#06b6d4' },
            ]}
            height={240}
            formatY={(v) => `$${Math.round(v)}B`}
          />
          <div className="flex items-center justify-center gap-4 mt-2">
            {[
              { name: 'Revenue', color: '#2563eb' },
              { name: 'Net Income', color: '#06b6d4' },
            ].map((l) => (
              <div key={l.name} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full" style={{ background: l.color }} />
                <span className="text-xs text-secondary">{l.name}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Quarterly revenue bars */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-semibold text-primary">Annual Revenue Breakdown</h3>
              <p className="text-xs text-secondary mt-0.5">{company.name} · $B per fiscal year</p>
            </div>
          </div>
          <BarChart
            data={company.revenueHistory}
            labels={['FY22', 'FY23', 'FY24', 'FY25']}
            height={240}
            color="#2563eb"
            formatY={(v) => `$${Math.round(v)}B`}
          />
        </Card>
      </div>

      {/* Financial ratios + balance sheet */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Key ratios */}
        <Card className="p-6">
          <h3 className="text-base font-semibold text-primary mb-4">Key Financial Ratios</h3>
          <div className="space-y-3">
            {[
              { label: 'Debt-to-Equity', value: (company.debt / (company.assets - company.liabilities)).toFixed(2), benchmark: '< 1.5', status: 'ok' },
              { label: 'Current Ratio', value: '2.41', benchmark: '> 1.0', status: 'ok' },
              { label: 'Return on Equity', value: `${((company.netIncome / (company.assets - company.liabilities)) * 100).toFixed(1)}%`, benchmark: '> 15%', status: 'ok' },
              { label: 'Net Profit Margin', value: `${((company.netIncome / company.revenue) * 100).toFixed(1)}%`, benchmark: '> 20%', status: 'ok' },
              { label: 'Asset Turnover', value: `${(company.revenue / company.assets).toFixed(2)}x`, benchmark: '> 0.5x', status: 'ok' },
            ].map((r, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-base last:border-0">
                <div>
                  <p className="text-sm font-medium text-primary">{r.label}</p>
                  <p className="text-xs text-tertiary">Benchmark: {r.benchmark}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-primary tabular-nums">{r.value}</p>
                  <Badge variant="success" className="mt-0.5">Healthy</Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Balance sheet visual */}
        <Card className="p-6 lg:col-span-2">
          <h3 className="text-base font-semibold text-primary mb-4">Balance Sheet Overview</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Assets breakdown */}
            <div>
              <p className="text-sm font-medium text-secondary mb-3">Assets · ${company.assets}B</p>
              <div className="space-y-2">
                {[
                  { label: 'Current Assets', pct: 35, color: '#2563eb' },
                  { label: 'PP&E', pct: 28, color: '#06b6d4' },
                  { label: 'Intangibles', pct: 22, color: '#10b981' },
                  { label: 'Other', pct: 15, color: '#f59e0b' },
                ].map((a, i) => (
                  <div key={i}>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-secondary">{a.label}</span>
                      <span className="text-primary font-medium tabular-nums">${((company.assets * a.pct) / 100).toFixed(1)}B · {a.pct}%</span>
                    </div>
                    <div className="h-2.5 rounded-full bg-subtle overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${a.pct}%`, background: a.color }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
            {/* Liabilities breakdown */}
            <div>
              <p className="text-sm font-medium text-secondary mb-3">Liabilities & Equity · ${company.assets}B</p>
              <div className="space-y-2">
                {[
                  { label: 'Current Liabilities', pct: 30, color: '#ef4444' },
                  { label: 'Long-term Debt', pct: 19, color: '#f59e0b' },
                  { label: 'Other Liabilities', pct: 7, color: '#8b5cf6' },
                  { label: "Shareholders' Equity", pct: 44, color: '#10b981' },
                ].map((a, i) => (
                  <div key={i}>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-secondary">{a.label}</span>
                      <span className="text-primary font-medium tabular-nums">${((company.assets * a.pct) / 100).toFixed(1)}B · {a.pct}%</span>
                    </div>
                    <div className="h-2.5 rounded-full bg-subtle overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${a.pct}%`, background: a.color }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
