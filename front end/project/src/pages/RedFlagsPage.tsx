import { useState } from 'react';
import { Card, Badge, PageHeader } from '@/components/ui';
import { Icon } from '@/components/Icon';
import { RED_FLAGS } from '@/lib/mockData';

const severityConfig = {
  critical: { label: 'Critical', variant: 'danger' as const, bg: 'bg-red-50 dark:bg-red-500/10', border: 'border-red-200 dark:border-red-500/20', icon: 'AlertTriangle', iconColor: 'text-red-500', ring: 'ring-red-500/20' },
  high: { label: 'High', variant: 'warning' as const, bg: 'bg-amber-50 dark:bg-amber-500/10', border: 'border-amber-200 dark:border-amber-500/20', icon: 'ShieldAlert', iconColor: 'text-amber-500', ring: 'ring-amber-500/20' },
  medium: { label: 'Medium', variant: 'warning' as const, bg: 'bg-yellow-50 dark:bg-yellow-500/10', border: 'border-yellow-200 dark:border-yellow-500/20', icon: 'Flag', iconColor: 'text-yellow-500', ring: 'ring-yellow-500/20' },
};

const FILTERS = ['All', 'Critical', 'High', 'Medium'] as const;

export function RedFlagsPage() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('All');

  const filtered = filter === 'All'
    ? RED_FLAGS
    : RED_FLAGS.filter((f) => f.severity === filter.toLowerCase());

  const counts = {
    critical: RED_FLAGS.filter((f) => f.severity === 'critical').length,
    high: RED_FLAGS.filter((f) => f.severity === 'high').length,
    medium: RED_FLAGS.filter((f) => f.severity === 'medium').length,
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Red Flag Dashboard"
        subtitle="Financial anomalies and risk indicators detected across analyzed companies"
        action={
          <button className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-base text-sm font-medium text-secondary hover:bg-subtle transition-colors">
            <Icon name="RefreshCw" size={16} /> Re-run Analysis
          </button>
        }
      />

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card className="p-5 border-red-200 dark:border-red-500/20">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-red-50 dark:bg-red-500/10 flex items-center justify-center">
              <Icon name="AlertTriangle" size={22} className="text-red-500" />
            </div>
            <div>
              <p className="text-2xl font-bold text-primary">{RED_FLAGS.length}</p>
              <p className="text-xs text-secondary">Total Flags</p>
            </div>
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-red-50 dark:bg-red-500/10 flex items-center justify-center">
              <Icon name="ShieldAlert" size={22} className="text-red-500" />
            </div>
            <div>
              <p className="text-2xl font-bold text-primary">{counts.critical}</p>
              <p className="text-xs text-secondary">Critical</p>
            </div>
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-amber-50 dark:bg-amber-500/10 flex items-center justify-center">
              <Icon name="Flag" size={22} className="text-amber-500" />
            </div>
            <div>
              <p className="text-2xl font-bold text-primary">{counts.high}</p>
              <p className="text-xs text-secondary">High Priority</p>
            </div>
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center">
              <Icon name="ShieldCheck" size={22} className="text-emerald-500" />
            </div>
            <div>
              <p className="text-2xl font-bold text-primary">2</p>
              <p className="text-xs text-secondary">Companies Clean</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-2 mb-6">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              filter === f
                ? 'bg-surface text-primary shadow-soft border border-base'
                : 'text-secondary hover:bg-subtle'
            }`}
          >
            {f}
            {f !== 'All' && (
              <span className="ml-1.5 text-xs text-tertiary">
                ({f === 'Critical' ? counts.critical : f === 'High' ? counts.high : counts.medium})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Flag cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((flag, i) => {
          const sc = severityConfig[flag.severity];
          return (
            <Card key={flag.id} hover className={`p-5 border ${sc.border} animate-slide-up`}>
              <div style={{ animationDelay: `${i * 50}ms` }} className="flex items-start justify-between mb-3">
                <div className={`w-11 h-11 rounded-xl ${sc.bg} flex items-center justify-center ring-4 ${sc.ring}`}>
                  <Icon name={sc.icon} size={22} className={sc.iconColor} />
                </div>
                <Badge variant={sc.variant}>{sc.label}</Badge>
              </div>
              <h3 className="text-base font-semibold text-primary">{flag.title}</h3>
              <p className="text-xs text-secondary mt-1.5 leading-relaxed">{flag.description}</p>
              <div className="mt-4 pt-3 border-t border-base flex items-center justify-between">
                <div>
                  <p className="text-xs text-tertiary">{flag.company}</p>
                  <p className="text-sm font-semibold text-primary mt-0.5">{flag.metric}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-tertiary">Value</p>
                  <p className={`text-sm font-semibold mt-0.5 flex items-center gap-1 justify-end ${flag.trend === 'up' ? 'text-danger-600' : 'text-amber-600'}`}>
                    <Icon name={flag.trend === 'up' ? 'ArrowUpRight' : 'ArrowDownRight'} size={14} />
                    {flag.value}
                  </p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Risk assessment summary */}
      <Card className="p-6 mt-6">
        <div className="flex items-center gap-2 mb-4">
          <Icon name="ShieldCheck" size={18} className="text-brand-600 dark:text-brand-400" />
          <h3 className="text-base font-semibold text-primary">Risk Assessment Summary</h3>
          <Badge variant="brand">Red Flag Agent</Badge>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { company: 'Microsoft', risk: 'Low', color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-500/10', score: 18 },
            { company: 'Apple', risk: 'Medium', color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-500/10', score: 42 },
            { company: 'Alphabet', risk: 'Medium', color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-500/10', score: 38 },
            { company: 'Amazon', risk: 'High', color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-500/10', score: 67 },
          ].map((r, i) => (
            <div key={i} className="p-4 rounded-xl border border-base">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-semibold text-primary">{r.company}</p>
                <span className={`text-xs font-medium ${r.color}`}>{r.risk} Risk</span>
              </div>
              <div className="h-2 rounded-full bg-subtle overflow-hidden mb-2">
                <div className={`h-full rounded-full ${r.bg}`} style={{ width: `${r.score}%`, background: r.score > 60 ? '#ef4444' : r.score > 35 ? '#f59e0b' : '#10b981' }} />
              </div>
              <p className="text-xs text-tertiary">Risk Score: {r.score}/100</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
