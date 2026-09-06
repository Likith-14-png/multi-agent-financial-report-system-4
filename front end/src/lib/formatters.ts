/**
 * FinSight AI — Financial Formatters & Metric Utilities
 */

import { RiskSeverity } from './types';

/**
 * Format currency or number with human-friendly suffixes
 */
export function formatFinancialValue(
  value: unknown,
  currency: string = '$',
  unit?: string | null
): string {
  if (value === null || value === undefined || value === '') {
    return 'Not available';
  }

  // If value is an object (e.g. { value: 123, currency: '$', unit: 'billion' })
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    const target =
      obj.display_value ??
      obj.formatted ??
      obj.value ??
      obj.comparison_value ??
      obj.numeric_value ??
      obj.raw_value;
    if (target !== undefined && target !== null && target !== value) {
      const objUnit = (obj.unit as string) || (obj.unit_scale as string) || unit;
      const objCurr = (obj.currency as string) || currency;
      return formatFinancialValue(target, objCurr, objUnit);
    }
    return 'Not available';
  }

  // If it's already a formatted string like "$15.3 billion" or "70.1 %", return cleaned
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (/^(na|n\/a|null|undefined|none|not found|nan)$/i.test(trimmed)) {
      return 'Not available';
    }
    return trimmed;
  }

  if (typeof value !== 'number' || isNaN(value)) {
    return 'Not available';
  }

  const absVal = Math.abs(value);
  const isNegative = value < 0;
  const prefix = isNegative ? `-${currency}` : currency;

  if (unit?.toLowerCase() === 'billion' || absVal >= 1_000_000_000) {
    const num = unit?.toLowerCase() === 'billion' ? absVal : absVal / 1_000_000_000;
    return `${prefix}${num.toFixed(2)}B`;
  }
  if (unit?.toLowerCase() === 'million' || absVal >= 1_000_000) {
    const num = unit?.toLowerCase() === 'million' ? absVal : absVal / 1_000_000;
    return `${prefix}${num.toFixed(2)}M`;
  }
  if (unit?.toLowerCase() === 'thousand' || absVal >= 1_000) {
    const num = unit?.toLowerCase() === 'thousand' ? absVal : absVal / 1_000;
    return `${prefix}${num.toFixed(1)}K`;
  }

  return `${prefix}${absVal.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

/**
 * Format percentage
 */
export function formatPercent(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    const target = obj.percentage_difference ?? obj.difference_pct ?? obj.value;
    if (target !== undefined && target !== null && target !== value) {
      return formatPercent(target);
    }
    return '—';
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (/^(na|n\/a|null|undefined|none|nan)$/i.test(trimmed)) return '—';
    if (trimmed.endsWith('%')) return trimmed;
    const num = parseFloat(trimmed.replace('%', ''));
    if (!isNaN(num)) return `${num >= 0 ? '+' : ''}${num.toFixed(1)}%`;
    return trimmed;
  }
  if (typeof value === 'number') {
    if (isNaN(value)) return '—';
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  }
  return '—';
}

/**
 * Return styling classes according to risk severity
 */
export function getRiskColorClass(severity: RiskSeverity | string | null | undefined): {
  bg: string;
  text: string;
  border: string;
  badge: string;
  dot: string;
} {
  const norm = (severity || '').toLowerCase();
  if (norm === 'critical') {
    return {
      bg: 'bg-rose-950/40 dark:bg-rose-950/50',
      text: 'text-rose-400 dark:text-rose-300',
      border: 'border-rose-800/60 dark:border-rose-800/80',
      badge: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
      dot: 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]',
    };
  }
  if (norm === 'high') {
    return {
      bg: 'bg-amber-950/40 dark:bg-amber-950/50',
      text: 'text-amber-400 dark:text-amber-300',
      border: 'border-amber-800/60 dark:border-amber-800/80',
      badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
      dot: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]',
    };
  }
  if (norm === 'medium') {
    return {
      bg: 'bg-yellow-950/30 dark:bg-yellow-950/40',
      text: 'text-yellow-400 dark:text-yellow-300',
      border: 'border-yellow-800/60 dark:border-yellow-800/70',
      badge: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
      dot: 'bg-yellow-500',
    };
  }
  // Low or default
  return {
    bg: 'bg-emerald-950/30 dark:bg-emerald-950/40',
    text: 'text-emerald-400 dark:text-emerald-300',
    border: 'border-emerald-800/50 dark:border-emerald-800/60',
    badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    dot: 'bg-emerald-500',
  };
}

/**
 * Format bytes to readable size
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Extract numbers for chart plotting from diverse backend string/number representations
 */
export function parseNumericValue(val: unknown): number | null {
  if (typeof val === 'number') return isNaN(val) ? null : val;
  if (!val) return null;
  if (typeof val === 'object' && val !== null) {
    const obj = val as Record<string, unknown>;
    const candidate =
      obj.numeric_value ??
      obj.comparison_value ??
      obj.value ??
      obj.display_value ??
      obj.raw_value;
    if (candidate !== undefined && candidate !== null && candidate !== val) {
      return parseNumericValue(candidate);
    }
    return null;
  }
  if (typeof val !== 'string') return null;
  const clean = val.replace(/[$€£,]/g, '').trim();
  const match = clean.match(/[-+]?\d*\.?\d+/);
  if (!match) return null;
  const num = parseFloat(match[0]);
  if (clean.toLowerCase().includes('billion') || clean.toLowerCase().includes('b')) return num * 1_000_000_000;
  if (clean.toLowerCase().includes('million') || clean.toLowerCase().includes('m')) return num * 1_000_000;
  if (clean.toLowerCase().includes('thousand') || clean.toLowerCase().includes('k')) return num * 1_000;
  return num;
}
