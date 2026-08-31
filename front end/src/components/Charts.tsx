import React, { useState } from 'react';
import { formatFinancialValue, parseNumericValue } from '../lib/formatters';

// -------------------------------------------------------------
// 1. MiniSparkline for Metric Cards
// -------------------------------------------------------------
export interface MiniSparklineProps {
  data: number[];
  color?: string;
  height?: number;
  width?: number;
}

export function MiniSparkline({
  data,
  color = '#06b6d4',
  height = 32,
  width = 90,
}: MiniSparklineProps) {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min === 0 ? 1 : max - min;
  const padding = 2;

  const points = data
    .map((val, idx) => {
      const x = padding + (idx / (data.length - 1)) * (width - padding * 2);
      const y = height - padding - ((val - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
      {data.length > 0 && (
        <circle
          cx={width - padding}
          cy={height - padding - ((data[data.length - 1] - min) / range) * (height - padding * 2)}
          r="3"
          fill={color}
        />
      )}
    </svg>
  );
}

// -------------------------------------------------------------
// 2. TrendLineChart for Historical Financial Metrics
// -------------------------------------------------------------
export interface TrendPoint {
  label: string | number;
  value: number;
  displayValue?: string;
}

export interface TrendSeries {
  name: string;
  color: string;
  points: TrendPoint[];
}

export interface TrendLineChartProps {
  series: TrendSeries[];
  height?: number;
  title?: string;
  subtitle?: string;
}

export function TrendLineChart({
  series,
  height = 240,
  title,
  subtitle,
}: TrendLineChartProps) {
  const [hoveredPoint, setHoveredPoint] = useState<{
    seriesName: string;
    label: string | number;
    value: number;
    displayValue?: string;
    x: number;
    y: number;
  } | null>(null);

  if (!series || series.length === 0 || !series[0].points || series[0].points.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-xs text-slate-500">
        No historical trend data available
      </div>
    );
  }

  // Collect all values to find global min/max
  const allValues = series.flatMap((s) => s.points.map((p) => p.value));
  const rawMin = Math.min(...allValues, 0);
  const rawMax = Math.max(...allValues);
  const paddingX = 40;
  const paddingY = 30;
  const chartWidth = 540;
  const chartHeight = height;

  const minVal = rawMin < 0 ? rawMin * 1.1 : 0;
  const maxVal = rawMax === minVal ? rawMax + 10 : rawMax * 1.15;
  const range = maxVal - minVal;

  const labels = series[0].points.map((p) => p.label);

  const getX = (index: number) => {
    if (labels.length === 1) return chartWidth / 2;
    return paddingX + (index / (labels.length - 1)) * (chartWidth - paddingX * 2);
  };

  const getY = (value: number) => {
    return chartHeight - paddingY - ((value - minVal) / range) * (chartHeight - paddingY * 2);
  };

  return (
    <div className="w-full flex flex-col">
      {(title || subtitle) && (
        <div className="flex justify-between items-baseline mb-3">
          {title && <h4 className="text-sm font-semibold text-slate-200">{title}</h4>}
          {subtitle && <span className="text-xs text-slate-400">{subtitle}</span>}
        </div>
      )}

      <div className="relative w-full overflow-x-auto">
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          className="w-full h-auto min-w-[320px] select-none"
        >
          {/* Horizontal grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
            const y = chartHeight - paddingY - pct * (chartHeight - paddingY * 2);
            const val = minVal + pct * range;
            return (
              <g key={idx} className="text-slate-700/60">
                <line
                  x1={paddingX}
                  y1={y}
                  x2={chartWidth - paddingX}
                  y2={y}
                  stroke="currentColor"
                  strokeDasharray="4 4"
                  strokeWidth="1"
                />
                <text
                  x={paddingX - 8}
                  y={y + 3}
                  textAnchor="end"
                  className="text-[9px] fill-slate-500 font-mono"
                >
                  {formatFinancialValue(val)}
                </text>
              </g>
            );
          })}

          {/* X Axis Labels */}
          {labels.map((label, idx) => {
            const x = getX(idx);
            return (
              <text
                key={idx}
                x={x}
                y={chartHeight - 8}
                textAnchor="middle"
                className="text-[10px] fill-slate-400 font-mono font-medium"
              >
                {label}
              </text>
            );
          })}

          {/* Series Lines & Circles */}
          {series.map((s, sIdx) => {
            const pathPoints = s.points
              .map((p, pIdx) => `${getX(pIdx)},${getY(p.value)}`)
              .join(' ');

            return (
              <g key={sIdx}>
                <polyline
                  fill="none"
                  stroke={s.color}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  points={pathPoints}
                />
                {s.points.map((p, pIdx) => {
                  const cx = getX(pIdx);
                  const cy = getY(p.value);
                  return (
                    <circle
                      key={pIdx}
                      cx={cx}
                      cy={cy}
                      r="4"
                      fill={s.color}
                      className="cursor-pointer hover:r-6 transition-all"
                      onMouseEnter={() =>
                        setHoveredPoint({
                          seriesName: s.name,
                          label: p.label,
                          value: p.value,
                          displayValue: p.displayValue,
                          x: cx,
                          y: cy,
                        })
                      }
                      onMouseLeave={() => setHoveredPoint(null)}
                    />
                  );
                })}
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip */}
        {hoveredPoint && (
          <div
            className="absolute z-20 px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs shadow-xl pointer-events-none -translate-x-1/2 -translate-y-full"
            style={{
              left: `${(hoveredPoint.x / chartWidth) * 100}%`,
              top: `${(hoveredPoint.y / chartHeight) * 100}%`,
            }}
          >
            <div className="text-[10px] text-slate-400 font-mono">
              {hoveredPoint.seriesName} · {hoveredPoint.label}
            </div>
            <div className="font-semibold text-cyan-300 font-mono">
              {hoveredPoint.displayValue || formatFinancialValue(hoveredPoint.value)}
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 mt-3 pt-2 border-t border-slate-800/60 justify-center">
        {series.map((s, idx) => (
          <div key={idx} className="flex items-center gap-1.5 text-xs text-slate-300">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
            <span>{s.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// 3. BarComparisonChart (Company A vs Company B)
// -------------------------------------------------------------
export interface ComparisonBarItem {
  metric: string;
  companyA: number | null;
  companyB: number | null;
  displayA?: string;
  displayB?: string;
}

export interface BarComparisonChartProps {
  data: ComparisonBarItem[];
  companyAName?: string;
  companyBName?: string;
}

export function BarComparisonChart({
  data,
  companyAName = 'Company A',
  companyBName = 'Company B',
}: BarComparisonChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-40 flex items-center justify-center text-xs text-slate-500">
        No comparative metric data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end gap-6 text-xs mb-2">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded bg-cyan-500 shrink-0" />
          <span className="text-slate-200 font-medium">{companyAName}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded bg-indigo-500 shrink-0" />
          <span className="text-slate-200 font-medium">{companyBName}</span>
        </div>
      </div>

      <div className="space-y-3">
        {data.map((item, idx) => {
          const valA = item.companyA ?? parseNumericValue(item.displayA) ?? 0;
          const valB = item.companyB ?? parseNumericValue(item.displayB) ?? 0;
          const max = Math.max(Math.abs(valA), Math.abs(valB), 1);
          const pctA = Math.min((Math.abs(valA) / max) * 100, 100);
          const pctB = Math.min((Math.abs(valB) / max) * 100, 100);

          return (
            <div key={idx} className="p-3 rounded-xl bg-slate-900/50 border border-slate-800/80 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="font-semibold text-slate-200">{item.metric}</span>
                <div className="flex gap-4 font-mono text-[11px]">
                  <span className="text-cyan-400">
                    {item.displayA || (item.companyA !== null ? formatFinancialValue(item.companyA) : '—')}
                  </span>
                  <span className="text-indigo-400">
                    {item.displayB || (item.companyB !== null ? formatFinancialValue(item.companyB) : '—')}
                  </span>
                </div>
              </div>

              {/* Company A Bar */}
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden flex">
                <div
                  className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400 rounded-full transition-all duration-500"
                  style={{ width: `${pctA}%` }}
                />
              </div>

              {/* Company B Bar */}
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden flex">
                <div
                  className="h-full bg-gradient-to-r from-indigo-600 to-indigo-400 rounded-full transition-all duration-500"
                  style={{ width: `${pctB}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// 4. RiskDistributionBar (Critical / High / Medium / Low)
// -------------------------------------------------------------
export interface RiskDistributionBarProps {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export function RiskDistributionBar({
  critical,
  high,
  medium,
  low,
}: RiskDistributionBarProps) {
  const total = critical + high + medium + low;
  if (total === 0) {
    return (
      <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden flex">
        <div className="h-full bg-emerald-500/50 w-full" />
      </div>
    );
  }

  const pCrit = (critical / total) * 100;
  const pHigh = (high / total) * 100;
  const pMed = (medium / total) * 100;
  const pLow = (low / total) * 100;

  return (
    <div className="space-y-2">
      <div className="h-2.5 w-full bg-slate-800 rounded-full overflow-hidden flex gap-0.5">
        {critical > 0 && <div style={{ width: `${pCrit}%` }} className="h-full bg-rose-500" title={`Critical: ${critical}`} />}
        {high > 0 && <div style={{ width: `${pHigh}%` }} className="h-full bg-amber-500" title={`High: ${high}`} />}
        {medium > 0 && <div style={{ width: `${pMed}%` }} className="h-full bg-yellow-500" title={`Medium: ${medium}`} />}
        {low > 0 && <div style={{ width: `${pLow}%` }} className="h-full bg-emerald-500" title={`Low: ${low}`} />}
      </div>
      <div className="flex justify-between text-[11px] text-slate-400 font-mono">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-500" /> {critical} Critical</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> {high} High</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-500" /> {medium} Med</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> {low} Low</span>
      </div>
    </div>
  );
}
