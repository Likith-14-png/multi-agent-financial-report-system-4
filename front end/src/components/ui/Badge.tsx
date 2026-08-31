import React, { HTMLAttributes } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { RiskSeverity } from '../../lib/types';
import { getRiskColorClass } from '../../lib/formatters';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'primary' | 'secondary' | 'outline' | 'success' | 'warning' | 'danger' | 'risk';
  riskSeverity?: RiskSeverity | string | null;
  size?: 'sm' | 'md';
}

export function Badge({
  className,
  variant = 'default',
  riskSeverity,
  size = 'md',
  children,
  ...props
}: BadgeProps) {
  const baseStyles = 'inline-flex items-center font-medium rounded-full transition-colors';

  const sizes = {
    sm: 'text-[10px] px-2 py-0.5 font-medium tracking-wide',
    md: 'text-xs px-2.5 py-1 font-medium',
  };

  const variants = {
    default: 'bg-slate-800 text-slate-300 border border-slate-700/60',
    primary: 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30',
    secondary: 'bg-slate-700/40 text-slate-300 border border-slate-600/40',
    outline: 'bg-transparent text-slate-400 border border-slate-700',
    success: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
    warning: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
    danger: 'bg-rose-500/15 text-rose-300 border border-rose-500/30',
    risk: riskSeverity ? getRiskColorClass(riskSeverity).badge : 'bg-slate-800 text-slate-300',
  };

  return (
    <span
      className={twMerge(clsx(baseStyles, sizes[size], variants[variant], className))}
      {...props}
    >
      {variant === 'risk' && riskSeverity && (
        <span
          className={twMerge(
            clsx(
              'w-1.5 h-1.5 rounded-full mr-1.5 shrink-0 inline-block',
              getRiskColorClass(riskSeverity).dot
            )
          )}
        />
      )}
      {children}
    </span>
  );
}
