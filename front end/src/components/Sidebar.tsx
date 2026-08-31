import React from 'react';
import {
  LayoutDashboard,
  UploadCloud,
  FileSpreadsheet,
  Search,
  AlertTriangle,
  GitCompare,
  FileText,
  History,
  Settings,
  X,
  Activity,
  Layers,
  Sparkles,
  ChevronRight,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { ActiveView } from '../lib/types';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface NavItem {
  id: ActiveView;
  label: string;
  icon: React.ElementType;
  badge?: string;
  requiresSession?: boolean;
}

export function Sidebar() {
  const {
    activeView,
    setActiveView,
    activeSessionId,
    activeCompany,
    activeYear,
    isBackendHealthy,
    mobileMenuOpen,
    setMobileMenuOpen,
  } = useApp();

  const primaryNav: NavItem[] = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard, requiresSession: true },
    { id: 'workspace', label: 'Workspace', icon: UploadCloud },
    { id: 'financials', label: 'Financials', icon: FileSpreadsheet, requiresSession: true },
    { id: 'research', label: 'Research', icon: Search, requiresSession: true },
    { id: 'risk', label: 'Risk & Red Flags', icon: AlertTriangle, requiresSession: true },
    { id: 'comparison', label: 'Peer Compare', icon: GitCompare, requiresSession: true },
    { id: 'report', label: 'Executive Report', icon: FileText, requiresSession: true },
  ];

  const secondaryNav: NavItem[] = [
    { id: 'history', label: 'Recent Analyses', icon: History },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  const handleNavClick = (viewId: ActiveView) => {
    setActiveView(viewId);
    setMobileMenuOpen(false);
  };

  const navContent = (
    <div className="flex flex-col h-full bg-slate-950/95 border-r border-slate-800/80 text-slate-300">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-slate-950 shadow-md shadow-cyan-500/20 font-extrabold">
            <Layers className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-extrabold text-base tracking-tight text-white">FinSight AI</span>
              <span className="text-[10px] uppercase font-bold tracking-widest px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                PRO
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">Multi-Agent Intelligence</p>
          </div>
        </div>

        {/* Mobile close button */}
        <button
          onClick={() => setMobileMenuOpen(false)}
          className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Active Session Context Widget */}
      {activeSessionId && (
        <div className="p-3 mx-3 my-3 rounded-xl bg-slate-900/90 border border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span className="uppercase font-semibold tracking-wider text-[10px] text-cyan-400 flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> Active Session
            </span>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          </div>
          <div className="font-bold text-sm text-slate-100 truncate">
            {activeCompany || 'Active Filing'}
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400 mt-1 font-mono">
            <span>FY {activeYear || '2025'}</span>
            <button
              onClick={() => handleNavClick('overview')}
              className="text-cyan-400 hover:text-cyan-300 flex items-center text-[11px] font-sans font-medium"
            >
              Inspect <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}

      {/* Primary Navigation */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 py-1.5">
          Analytical Modules
        </div>
        {primaryNav.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          const isEnabled = !item.requiresSession || !!activeSessionId;

          return (
            <button
              key={item.id}
              onClick={() => isEnabled && handleNavClick(item.id)}
              disabled={!isEnabled}
              className={twMerge(
                clsx(
                  'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all group cursor-pointer text-left',
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-300 font-semibold border border-cyan-500/30 shadow-sm'
                    : isEnabled
                    ? 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/80'
                    : 'text-slate-600 opacity-50 cursor-not-allowed'
                )
              )}
            >
              <div className="flex items-center gap-2.5">
                <Icon
                  className={twMerge(
                    clsx(
                      'w-4 h-4 shrink-0 transition-colors',
                      isActive
                        ? 'text-cyan-400'
                        : isEnabled
                        ? 'text-slate-400 group-hover:text-slate-200'
                        : 'text-slate-600'
                    )
                  )}
                />
                <span>{item.label}</span>
              </div>
              {item.requiresSession && !activeSessionId && (
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800">
                  Upload first
                </span>
              )}
            </button>
          );
        })}

        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 pt-5 pb-1.5">
          Workstation
        </div>
        {secondaryNav.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;

          return (
            <button
              key={item.id}
              onClick={() => handleNavClick(item.id)}
              className={twMerge(
                clsx(
                  'w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-all group cursor-pointer text-left',
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-300 font-semibold border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/80'
                )
              )}
            >
              <Icon
                className={twMerge(
                  clsx(
                    'w-4 h-4 shrink-0',
                    isActive ? 'text-cyan-400' : 'text-slate-400 group-hover:text-slate-200'
                  )
                )}
              />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Footer & Backend Health Status */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-950/60 shrink-0">
        <div className="flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <span
              className={twMerge(
                clsx(
                  'w-2 h-2 rounded-full',
                  isBackendHealthy === true
                    ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]'
                    : isBackendHealthy === false
                    ? 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]'
                    : 'bg-amber-500 animate-pulse'
                )
              )}
            />
            <span className="font-mono">
              {isBackendHealthy === true
                ? 'Backend: Online'
                : isBackendHealthy === false
                ? 'Backend: Offline'
                : 'Connecting...'}
            </span>
          </div>
          <span className="font-mono text-[10px] text-slate-500">v1.0.0</span>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside className="hidden lg:block w-64 h-screen sticky top-0 shrink-0 select-none z-30">
        {navContent}
      </aside>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 w-72 max-w-[85vw] shadow-2xl z-10">
            {navContent}
          </div>
        </div>
      )}
    </>
  );
}
