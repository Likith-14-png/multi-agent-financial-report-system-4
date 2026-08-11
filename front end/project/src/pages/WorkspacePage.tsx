import { useState } from 'react';
import { useApp } from '@/lib/AppContext';
import { Card, Badge, ProgressBar, PageHeader, SectionHeader } from '@/components/ui';
import { Icon } from '@/components/Icon';
import { AGENTS, PIPELINE_STEPS, UPLOADED_DOCS } from '@/lib/mockData';
import type { AgentStatus, UploadedDoc } from '@/lib/types';

const statusConfig: Record<AgentStatus, { label: string; color: string; dot: string; badge: 'success' | 'warning' | 'neutral' }> = {
  completed: { label: 'Completed', color: 'text-emerald-600 dark:text-emerald-400', dot: 'bg-emerald-500', badge: 'success' },
  running: { label: 'Running', color: 'text-brand-600 dark:text-brand-400', dot: 'bg-brand-500', badge: 'warning' },
  waiting: { label: 'Waiting', color: 'text-tertiary', dot: 'bg-slate-400', badge: 'neutral' },
};

export function WorkspacePage() {
  const { setActiveSessionId, setPage } = useApp();
  const [dragging, setDragging] = useState(false);
  const [docs, setDocs] = useState<UploadedDoc[]>(UPLOADED_DOCS);
  const sessionId = 'WS-2026-0847';

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length) {
      const newDocs = files.map((f, i) => ({
        id: `d${Date.now()}-${i}`,
        name: f.name,
        size: `${(f.size / 1024 / 1024).toFixed(1)} MB`,
        company: f.name.split('_')[0] || 'Unknown',
        uploadedAt: 'just now',
        status: 'ready' as const,
      }));
      setDocs((d) => [...d, ...newDocs]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length) {
      const newDocs = files.map((f, i) => ({
        id: `d${Date.now()}-${i}`,
        name: f.name,
        size: `${(f.size / 1024 / 1024).toFixed(1)} MB`,
        company: f.name.split('_')[0] || 'Unknown',
        uploadedAt: 'just now',
        status: 'ready' as const,
      }));
      setDocs((d) => [...d, ...newDocs]);
    }
  };

  const startChat = () => {
    setActiveSessionId(sessionId);
    setPage('chat');
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Big Tech Q4 Comparison"
        subtitle={
          <span className="flex items-center gap-2">
            <span>Session ID: <span className="font-mono text-primary">{sessionId}</span></span>
            <Badge variant="warning"><Icon name="Activity" size={12} /> Analysis Running</Badge>
          </span>
        }
        action={
          <div className="flex items-center gap-2">
            <button className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl border border-base text-sm font-medium text-secondary hover:bg-subtle transition-colors">
              <Icon name="RefreshCw" size={16} /> Refresh
            </button>
            <button onClick={startChat} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl gradient-brand text-white text-sm font-medium shadow-card hover:shadow-elevated transition-all">
              <Icon name="MessageSquare" size={18} /> Open AI Chat
            </button>
          </div>
        }
      />

      {/* Upload + Pipeline */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-6">
        {/* Upload area */}
        <div className="lg:col-span-3">
          <Card className="p-6 h-full">
            <SectionHeader title="Upload Documents" subtitle="Drag and drop 10-K, 10-Q, or earnings PDFs" />
            <label
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              className={`block border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer ${
                dragging
                  ? 'border-brand-400 bg-brand-50 dark:bg-brand-500/10 scale-[1.01]'
                  : 'border-base hover:border-brand-300 hover:bg-subtle'
              }`}
            >
              <input type="file" multiple accept=".pdf,.doc,.docx,.txt" onChange={handleFileSelect} className="hidden" />
              <div className="w-14 h-14 rounded-2xl gradient-brand-soft flex items-center justify-center mx-auto mb-4">
                <Icon name="UploadCloud" size={28} className="text-brand-600 dark:text-brand-400" />
              </div>
              <p className="text-sm font-medium text-primary">
                {dragging ? 'Drop files here' : 'Drag & drop files or click to browse'}
              </p>
              <p className="text-xs text-tertiary mt-1">PDF, DOCX, TXT up to 50MB each</p>
            </label>

            {/* Uploaded docs list */}
            <div className="mt-5 space-y-2">
              {docs.map((d) => (
                <div key={d.id} className="flex items-center gap-3 p-3 rounded-xl border border-base hover:bg-subtle transition-colors group">
                  <div className="w-9 h-9 rounded-lg bg-red-50 dark:bg-red-500/10 flex items-center justify-center shrink-0">
                    <Icon name="FileText" size={18} className="text-red-500" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-primary truncate">{d.name}</p>
                    <p className="text-xs text-tertiary">{d.company} · {d.size} · {d.uploadedAt}</p>
                  </div>
                  <Badge variant="success">
                    <Icon name="CheckCircle2" size={12} /> Ready
                  </Badge>
                  <button className="p-1.5 rounded-lg text-tertiary hover:text-danger-500 hover:bg-red-50 dark:hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all">
                    <Icon name="X" size={16} />
                  </button>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Pipeline */}
        <div className="lg:col-span-2">
          <Card className="p-6 h-full">
            <SectionHeader title="Processing Pipeline" subtitle="Document Agent ingestion status" />
            <div className="space-y-1">
              {PIPELINE_STEPS.map((step, i) => {
                const done = i < 3;
                const active = i === 3;
                return (
                  <div key={step.key} className="flex items-center gap-3">
                    <div className="relative flex flex-col items-center">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-all ${
                        done
                          ? 'bg-emerald-500 text-white'
                          : active
                          ? 'bg-brand-500 text-white'
                          : 'bg-subtle text-tertiary border border-base'
                      }`}>
                        {done ? (
                          <Icon name="Check" size={16} />
                        ) : active ? (
                          <Icon name="Loader2" size={16} className="animate-spin" />
                        ) : (
                          <span className="text-xs font-semibold">{i + 1}</span>
                        )}
                      </div>
                      {i < PIPELINE_STEPS.length - 1 && (
                        <div className={`w-0.5 h-8 ${done ? 'bg-emerald-500' : 'bg-border-base'}`} />
                      )}
                    </div>
                    <div className="pb-8">
                      <p className={`text-sm font-medium ${done || active ? 'text-primary' : 'text-tertiary'}`}>
                        {step.label}
                      </p>
                      <p className="text-xs text-tertiary mt-0.5">
                        {done ? 'Completed' : active ? 'In progress…' : 'Queued'}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-2 p-3 rounded-xl bg-brand-50 dark:bg-brand-500/10 border border-brand-200 dark:border-brand-500/20">
              <div className="flex items-center gap-2">
                <Icon name="Database" size={16} className="text-brand-600 dark:text-brand-400" />
                <span className="text-xs font-medium text-brand-700 dark:text-brand-300">ChromaDB: 24 vectors indexed</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* AI Agent Status Panel */}
      <Card className="p-6">
        <SectionHeader
          title="AI Agent Status Panel"
          subtitle="Six specialized agents working in parallel"
          action={
            <Badge variant="brand">
              <span className="relative flex w-2 h-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500" />
              </span>
              2 Running · 2 Completed · 2 Waiting
            </Badge>
          }
        />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {AGENTS.map((agent, i) => {
            const sc = statusConfig[agent.status];
            return (
              <div
                key={agent.id}
                className="p-5 rounded-2xl border border-base hover:shadow-card transition-all animate-slide-up"
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-11 h-11 rounded-xl bg-brand-50 dark:bg-brand-500/10 flex items-center justify-center shrink-0">
                    <Icon name={agent.icon} size={22} className="text-brand-600 dark:text-brand-400" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-semibold text-primary">{agent.name}</h4>
                    </div>
                    <p className="text-xs text-secondary mt-0.5 leading-snug">{agent.description}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 mb-3">
                  <span className={`w-2 h-2 rounded-full ${sc.dot} ${agent.status === 'running' ? 'animate-pulse' : ''}`} />
                  <span className={`text-xs font-medium ${sc.color}`}>{sc.label}</span>
                  <span className="text-xs text-tertiary ml-auto font-mono">{agent.progress}%</span>
                </div>

                <ProgressBar value={agent.progress} showGlow={agent.status === 'running'} />

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {agent.responsibilities.map((r) => (
                    <span key={r} className="text-[11px] px-2 py-0.5 rounded-md bg-subtle text-secondary border border-base">
                      {r}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
