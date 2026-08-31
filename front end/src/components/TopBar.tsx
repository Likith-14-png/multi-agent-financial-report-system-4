import React from 'react';
import {
  Menu,
  Sun,
  Moon,
  UploadCloud,
  Building2,
  Calendar,
  Activity,
  PlusCircle,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { Button } from './ui/Button';

export function TopBar() {
  const {
    activeView,
    setActiveView,
    activeCompany,
    activeYear,
    activeSessionId,
    theme,
    toggleTheme,
    isBackendHealthy,
    setMobileMenuOpen,
  } = useApp();

  const viewTitles: Record<string, { title: string; category: string }> = {
    workspace: { title: 'Document Ingestion & Workspace', category: 'Workflow' },
    overview: { title: 'Executive Overview', category: 'Intelligence' },
    financials: { title: 'Financial Statement Analysis', category: 'Extraction' },
    research: { title: 'Grounded Research Console', category: 'Retrieval' },
    risk: { title: 'Risk Intelligence & Red Flags', category: 'Auditing' },
    comparison: { title: 'Peer Benchmark Comparison', category: 'Benchmarking' },
    report: { title: 'Synthesized Executive Report', category: 'Deliverables' },
    history: { title: 'Recent Analyses Archive', category: 'Workstation' },
    settings: { title: 'Workstation Preferences', category: 'Configuration' },
  };

  const currentMeta = viewTitles[activeView] || { title: 'Financial Analyst Workstation', category: 'Dashboard' };

  return (
    <header className="h-16 px-4 sm:px-6 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md sticky top-0 z-20 flex items-center justify-between gap-4">
      {/* Left: Hamburger (mobile) + View title */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={() => setMobileMenuOpen(true)}
          className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 focus:outline-none"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold tracking-widest text-slate-400">
            <span>FinSight</span>
            <span>/</span>
            <span className="text-cyan-400">{currentMeta.category}</span>
          </div>
          <h1 className="text-sm sm:text-base font-bold text-slate-100 truncate tracking-tight">
            {currentMeta.title}
          </h1>
        </div>
      </div>

      {/* Right: Active context & Action buttons */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Active Company Pill (if session active) */}
        {activeSessionId && activeCompany && (
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200">
            <Building2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <span className="font-semibold truncate max-w-[140px]">{activeCompany}</span>
            <span className="text-slate-500 font-mono">|</span>
            <Calendar className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span className="font-mono text-slate-300 text-[11px]">{activeYear || '2025'}</span>
          </div>
        )}

        {/* Backend health status badge */}
        <div
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-mono border border-slate-800 bg-slate-900/60"
          title={isBackendHealthy ? 'FastAPI Backend Healthy' : 'Backend Unreachable'}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isBackendHealthy === true
                ? 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.7)]'
                : isBackendHealthy === false
                ? 'bg-rose-500'
                : 'bg-amber-500 animate-pulse'
            }`}
          />
          <span className="text-slate-400">
            {isBackendHealthy === true ? 'API Live' : isBackendHealthy === false ? 'API Error' : 'Connecting'}
          </span>
        </div>

        {/* Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-xl border border-slate-800 bg-slate-900 hover:bg-slate-850 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          aria-label="Toggle theme"
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-cyan-400" />}
        </button>

        {/* New Filing Upload Button */}
        <Button
          size="sm"
          variant="primary"
          onClick={() => setActiveView('workspace')}
          leftIcon={<PlusCircle className="w-4 h-4" />}
          className="hidden xs:inline-flex"
        >
          New Analysis
        </Button>
      </div>
    </header>
  );
}
