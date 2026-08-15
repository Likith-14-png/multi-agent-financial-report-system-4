import { useApp } from '@/lib/AppContext';
import { Card, Badge, ProgressBar, PageHeader } from '@/components/ui';
import { Icon } from '@/components/Icon';
import { STATS, RECENT_COMPANIES, RESEARCH_SESSIONS } from '@/lib/mockData';
import { LineChart } from '@/components/Charts';

const STAT_CARDS = [
  { key: 'documentsUploaded', label: 'Documents Uploaded', icon: 'FileText', color: 'brand', change: '+12%' },
  { key: 'activeSessions', label: 'Active Analysis Sessions', icon: 'Activity', color: 'accent', change: '+2' },
  { key: 'reportsGenerated', label: 'Reports Generated', icon: 'FileBarChart', color: 'brand', change: '+3' },
  { key: 'questionsAnswered', label: 'Questions Answered', icon: 'MessageSquare', color: 'accent', change: '+24%' },
];

const colorMap: Record<string, { bg: string; text: string; bar: string }> = {
  brand: { bg: 'bg-brand-50 dark:bg-brand-500/10', text: 'text-brand-600 dark:text-brand-400', bar: 'bg-brand-500' },
  accent: { bg: 'bg-cyan-50 dark:bg-cyan-500/10', text: 'text-cyan-600 dark:text-cyan-400', bar: 'bg-cyan-500' },
};

export function DashboardPage() {
  const { user, setPage } = useApp();

  return (
    <div className="animate-fade-in">
      <PageHeader
        title={`Welcome back, ${user?.name?.split(' ')[0] ?? 'Analyst'}`}
        subtitle="Here's what's happening across your research workspaces."
        action={
          <button
            onClick={() => setPage('workspace')}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl gradient-brand text-white text-sm font-medium shadow-card hover:shadow-elevated transition-all"
          >
            <Icon name="Plus" size={18} />
            New Research Workspace
          </button>
        }
      />

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {STAT_CARDS.map((s, i) => {
          const c = colorMap[s.color];
          return (
            <Card key={s.key} hover className="p-5 animate-slide-up" >
              <div style={{ animationDelay: `${i * 60}ms` }} className="flex items-start justify-between">
                <div className={`w-11 h-11 rounded-xl ${c.bg} flex items-center justify-center`}>
                  <Icon name={s.icon} size={22} className={c.text} />
                </div>
                <Badge variant="success">
                  <Icon name="ArrowUpRight" size={12} />
                  {s.change}
                </Badge>
              </div>
              <p className="text-3xl font-bold text-primary mt-4 tracking-tight">
                {(STATS as Record<string, number>)[s.key]}
              </p>
              <p className="text-sm text-secondary mt-1">{s.label}</p>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Revenue overview chart */}
        <Card className="lg:col-span-2 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-semibold text-primary">Revenue Overview</h3>
              <p className="text-xs text-secondary mt-0.5">Trailing 4 fiscal years · $B</p>
            </div>
            <Badge variant="brand">
              <Icon name="TrendingUp" size={12} /> +14.2% YoY
            </Badge>
          </div>
          <LineChart
            labels={['FY22', 'FY23', 'FY24', 'FY25']}
            series={[
              { name: 'Microsoft', data: [168, 203, 211, 245], color: '#2563eb' },
              { name: 'Apple', data: [365, 394, 383, 383], color: '#06b6d4' },
            ]}
            height={220}
            formatY={(v) => `$${Math.round(v)}B`}
          />
          <div className="flex items-center justify-center gap-4 mt-2">
            {[
              { name: 'Microsoft', color: '#2563eb' },
              { name: 'Apple', color: '#06b6d4' },
            ].map((l) => (
              <div key={l.name} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full" style={{ background: l.color }} />
                <span className="text-xs text-secondary">{l.name}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Recent companies */}
        <Card className="p-6">
          <h3 className="text-base font-semibold text-primary mb-4">Recently Analyzed</h3>
          <div className="space-y-3">
            {RECENT_COMPANIES.map((c, i) => {
              const col = colorMap[c.color];
              return (
                <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-subtle transition-colors cursor-pointer group">
                  <div className={`w-10 h-10 rounded-xl ${col.bg} flex items-center justify-center shrink-0`}>
                    <Icon name="Building2" size={18} className={col.text} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-primary truncate">{c.name}</p>
                    <p className="text-xs text-tertiary">{c.ticker} · {c.filings} filings</p>
                  </div>
                  <Icon name="ChevronRight" size={16} className="text-tertiary opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              );
            })}
          </div>
          <button onClick={() => setPage('comparison')} className="w-full mt-4 py-2 text-sm text-brand-600 hover:text-brand-700 font-medium border border-base rounded-xl hover:bg-brand-50 dark:hover:bg-brand-500/10 transition-colors">
            View all companies
          </button>
        </Card>
      </div>

      {/* Previous sessions */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-primary">Previous Research Sessions</h3>
          <button onClick={() => setPage('history')} className="text-sm text-brand-600 hover:text-brand-700 font-medium">
            View all
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {RESEARCH_SESSIONS.slice(0, 6).map((s) => (
            <div key={s.id} className="p-4 rounded-xl border border-base hover:shadow-card transition-all cursor-pointer group" onClick={() => setPage('history')}>
              <div className="flex items-start justify-between mb-3">
                <div className="w-9 h-9 rounded-lg bg-brand-50 dark:bg-brand-500/10 flex items-center justify-center">
                  <Icon name="FolderPlus" size={18} className="text-brand-600 dark:text-brand-400" />
                </div>
                <Badge
                  variant={s.status === 'completed' ? 'success' : s.status === 'in-progress' ? 'warning' : 'neutral'}
                >
                  {s.status === 'in-progress' ? 'In Progress' : s.status === 'completed' ? 'Completed' : 'Queued'}
                </Badge>
              </div>
              <p className="text-sm font-semibold text-primary truncate">{s.name}</p>
              <p className="text-xs text-secondary mt-1 truncate">{s.companies.join(', ')}</p>
              <div className="flex items-center gap-3 mt-3 text-xs text-tertiary">
                <span className="flex items-center gap-1"><Icon name="FileText" size={13} /> {s.documents}</span>
                <span className="flex items-center gap-1"><Icon name="Clock" size={13} /> {s.uploadDate}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
