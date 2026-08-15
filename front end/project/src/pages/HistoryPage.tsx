import { useState } from 'react';
import { useApp } from '@/lib/AppContext';
import { Card, Badge, PageHeader } from '@/components/ui';
import { Icon } from '@/components/Icon';
import { RESEARCH_SESSIONS } from '@/lib/mockData';

const STATUS_CONFIG = {
  completed: { variant: 'success' as const, label: 'Completed', icon: 'CheckCircle2' },
  'in-progress': { variant: 'warning' as const, label: 'In Progress', icon: 'Loader2' },
  queued: { variant: 'neutral' as const, label: 'Queued', icon: 'Clock' },
};

export function HistoryPage() {
  const { setPage, setActiveSessionId } = useApp();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'completed' | 'in-progress' | 'queued'>('all');

  const filtered = RESEARCH_SESSIONS.filter((s) => {
    const matchesSearch = s.name.toLowerCase().includes(search.toLowerCase()) || s.companies.some((c) => c.toLowerCase().includes(search.toLowerCase()));
    const matchesFilter = filter === 'all' || s.status === filter;
    return matchesSearch && matchesFilter;
  });

  const openSession = (id: string) => {
    setActiveSessionId(id);
    setPage('workspace');
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Previous Research Sessions"
        subtitle="Browse and reopen past research workspaces"
        action={
          <button
            onClick={() => setPage('workspace')}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl gradient-brand text-white text-sm font-medium shadow-card hover:shadow-elevated transition-all"
          >
            <Icon name="Plus" size={18} /> New Session
          </button>
        }
      />

      {/* Search + filter */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Icon name="Search" size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-tertiary" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by session name or company…"
            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-base bg-surface text-sm text-primary outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-500/10 placeholder:text-tertiary"
          />
        </div>
        <div className="flex items-center gap-1 p-1 rounded-xl bg-subtle">
          {(['all', 'completed', 'in-progress', 'queued'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3.5 py-2 rounded-lg text-sm font-medium transition-all capitalize ${
                filter === f ? 'bg-surface text-primary shadow-soft' : 'text-secondary hover:text-primary'
              }`}
            >
              {f === 'in-progress' ? 'In Progress' : f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Session cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((s, i) => {
          const sc = STATUS_CONFIG[s.status];
          return (
            <Card key={s.id} hover className="p-5 animate-slide-up" onClick={() => openSession(s.id)}>
              <div style={{ animationDelay: `${i * 40}ms` }} className="flex items-start justify-between mb-3">
                <div className="w-11 h-11 rounded-xl bg-brand-50 dark:bg-brand-500/10 flex items-center justify-center">
                  <Icon name="FolderPlus" size={22} className="text-brand-600 dark:text-brand-400" />
                </div>
                <Badge variant={sc.variant}>
                  <Icon name={sc.icon} size={12} className={s.status === 'in-progress' ? 'animate-spin' : ''} />
                  {sc.label}
                </Badge>
              </div>
              <h3 className="text-base font-semibold text-primary truncate">{s.name}</h3>
              <p className="text-xs text-secondary mt-1 truncate">{s.companies.join(' · ')}</p>

              {/* Company avatars */}
              <div className="flex items-center gap-1.5 mt-3">
                {s.companies.slice(0, 4).map((c, j) => (
                  <div key={j} className="w-7 h-7 rounded-lg bg-subtle border border-base flex items-center justify-center text-[10px] font-bold text-secondary">
                    {c.charAt(0)}
                  </div>
                ))}
                {s.companies.length > 4 && (
                  <span className="text-xs text-tertiary ml-1">+{s.companies.length - 4}</span>
                )}
              </div>

              <div className="flex items-center justify-between mt-4 pt-3 border-t border-base">
                <div className="flex items-center gap-3 text-xs text-tertiary">
                  <span className="flex items-center gap-1"><Icon name="FileText" size={13} /> {s.documents} docs</span>
                  <span className="flex items-center gap-1"><Icon name="Clock" size={13} /> {s.uploadDate}</span>
                </div>
                <span className="flex items-center gap-1 text-xs text-brand-600 dark:text-brand-400 font-medium group-hover:gap-2 transition-all">
                  Open <Icon name="ChevronRight" size={14} />
                </span>
              </div>
            </Card>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <Card className="p-12 text-center">
          <Icon name="Search" size={40} className="text-tertiary mx-auto mb-3" />
          <p className="text-sm font-medium text-primary">No sessions found</p>
          <p className="text-xs text-secondary mt-1">Try adjusting your search or filter.</p>
        </Card>
      )}
    </div>
  );
}
