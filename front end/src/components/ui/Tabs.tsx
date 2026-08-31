import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface TabItem<T extends string = string> {
  id: T;
  label: string;
  badge?: string | number;
  icon?: React.ReactNode;
}

export interface TabsProps<T extends string = string> {
  tabs: TabItem<T>[];
  activeTab: T;
  onChange: (tabId: T) => void;
  variant?: 'pills' | 'line';
  className?: string;
}

export function Tabs<T extends string = string>({
  tabs,
  activeTab,
  onChange,
  variant = 'line',
  className = '',
}: TabsProps<T>) {
  if (variant === 'pills') {
    return (
      <div className={twMerge(clsx('flex items-center p-1 bg-slate-900 border border-slate-800 rounded-xl gap-1', className))}>
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              className={twMerge(
                clsx(
                  'flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer',
                  isActive
                    ? 'bg-slate-800 text-cyan-300 font-semibold shadow-sm border border-slate-700/60'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850'
                )
              )}
            >
              {tab.icon && <span className="shrink-0">{tab.icon}</span>}
              <span>{tab.label}</span>
              {tab.badge !== undefined && (
                <span
                  className={twMerge(
                    clsx(
                      'text-[10px] px-1.5 py-0.2 rounded-full font-mono',
                      isActive ? 'bg-cyan-500/20 text-cyan-300' : 'bg-slate-800 text-slate-400'
                    )
                  )}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  // Line variant
  return (
    <div className={twMerge(clsx('flex items-center border-b border-slate-800 gap-6', className))}>
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={twMerge(
              clsx(
                'flex items-center gap-2 py-3 text-sm font-medium border-b-2 transition-all cursor-pointer -mb-px',
                isActive
                  ? 'border-cyan-500 text-cyan-400 font-semibold'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
              )
            )}
          >
            {tab.icon && <span className="shrink-0">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.badge !== undefined && (
              <span
                className={twMerge(
                  clsx(
                    'text-[11px] px-2 py-0.5 rounded-full font-mono',
                    isActive ? 'bg-cyan-500/15 text-cyan-300' : 'bg-slate-800 text-slate-400'
                  )
                )}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
