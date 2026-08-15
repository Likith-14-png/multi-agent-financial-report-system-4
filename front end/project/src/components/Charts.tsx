import { useId } from 'react';

/* ---------- Line Chart ---------- */
export function LineChart({
  series,
  labels,
  height = 200,
  formatY = (v: number) => `${v}`,
}: {
  series: { name: string; data: number[]; color: string }[];
  labels: string[];
  height?: number;
  formatY?: (v: number) => string;
}) {
  const gradId = useId();
  const W = 600;
  const H = height;
  const pad = { top: 20, right: 16, bottom: 28, left: 44 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  const allVals = series.flatMap((s) => s.data);
  const min = Math.min(...allVals, 0);
  const max = Math.max(...allVals) * 1.1;
  const range = max - min || 1;

  const x = (i: number) => pad.left + (i / (labels.length - 1)) * innerW;
  const y = (v: number) => pad.top + innerH - ((v - min) / range) * innerH;

  const gridLines = 4;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} preserveAspectRatio="xMidYMid meet">
      <defs>
        {series.map((s, i) => (
          <linearGradient key={i} id={`${gradId}-${i}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={s.color} stopOpacity="0.18" />
            <stop offset="100%" stopColor={s.color} stopOpacity="0" />
          </linearGradient>
        ))}
      </defs>
      {/* grid */}
      {Array.from({ length: gridLines + 1 }).map((_, i) => {
        const gy = pad.top + (i / gridLines) * innerH;
        const val = max - (i / gridLines) * range;
        return (
          <g key={i}>
            <line x1={pad.left} y1={gy} x2={W - pad.right} y2={gy} stroke="currentColor" strokeOpacity="0.08" strokeWidth="1" />
            <text x={pad.left - 8} y={gy + 3} textAnchor="end" className="fill-current text-[10px]" fillOpacity="0.45">
              {formatY(val)}
            </text>
          </g>
        );
      })}
      {/* x labels */}
      {labels.map((l, i) => (
        <text key={i} x={x(i)} y={H - 8} textAnchor="middle" className="fill-current text-[10px]" fillOpacity="0.5">
          {l}
        </text>
      ))}
      {/* series */}
      {series.map((s, si) => {
        const path = s.data.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(v)}`).join(' ');
        const area = `${path} L ${x(s.data.length - 1)} ${pad.top + innerH} L ${x(0)} ${pad.top + innerH} Z`;
        return (
          <g key={si}>
            <path d={area} fill={`url(#${gradId}-${si})`} />
            <path d={path} fill="none" stroke={s.color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            {s.data.map((v, i) => (
              <circle key={i} cx={x(i)} cy={y(v)} r="3.5" fill="var(--bg-surface)" stroke={s.color} strokeWidth="2" />
            ))}
          </g>
        );
      })}
    </svg>
  );
}

/* ---------- Bar Chart ---------- */
export function BarChart({
  data,
  labels,
  height = 200,
  formatY = (v: number) => `${v}`,
  color = '#2563eb',
}: {
  data: number[];
  labels: string[];
  height?: number;
  formatY?: (v: number) => string;
  color?: string;
}) {
  const W = 600;
  const H = height;
  const pad = { top: 20, right: 16, bottom: 28, left: 44 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;
  const max = Math.max(...data) * 1.15 || 1;
  const slot = innerW / data.length;
  const barW = Math.min(slot * 0.55, 48);
  const gridLines = 4;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} preserveAspectRatio="xMidYMid meet">
      {Array.from({ length: gridLines + 1 }).map((_, i) => {
        const gy = pad.top + (i / gridLines) * innerH;
        const val = max - (i / gridLines) * max;
        return (
          <g key={i}>
            <line x1={pad.left} y1={gy} x2={W - pad.right} y2={gy} stroke="currentColor" strokeOpacity="0.08" strokeWidth="1" />
            <text x={pad.left - 8} y={gy + 3} textAnchor="end" className="fill-current text-[10px]" fillOpacity="0.45">
              {formatY(val)}
            </text>
          </g>
        );
      })}
      {data.map((v, i) => {
        const bh = (v / max) * innerH;
        const bx = pad.left + i * slot + (slot - barW) / 2;
        const by = pad.top + innerH - bh;
        return (
          <g key={i}>
            <rect x={bx} y={by} width={barW} height={bh} rx="5" fill={color} fillOpacity="0.85" />
            <text x={bx + barW / 2} y={H - 8} textAnchor="middle" className="fill-current text-[10px]" fillOpacity="0.5">
              {labels[i]}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ---------- Grouped Bar Chart (comparison) ---------- */
export function GroupedBarChart({
  groups,
  series,
  height = 260,
  formatY = (v: number) => `${v}`,
}: {
  groups: string[];
  series: { name: string; data: number[]; color: string }[];
  height?: number;
  formatY?: (v: number) => string;
}) {
  const W = 600;
  const H = height;
  const pad = { top: 24, right: 16, bottom: 36, left: 48 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;
  const allVals = series.flatMap((s) => s.data);
  const max = Math.max(...allVals) * 1.15 || 1;
  const slot = innerW / groups.length;
  const barW = Math.min((slot * 0.8) / series.length, 28);
  const gridLines = 4;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} preserveAspectRatio="xMidYMid meet">
        {Array.from({ length: gridLines + 1 }).map((_, i) => {
          const gy = pad.top + (i / gridLines) * innerH;
          const val = max - (i / gridLines) * max;
          return (
            <g key={i}>
              <line x1={pad.left} y1={gy} x2={W - pad.right} y2={gy} stroke="currentColor" strokeOpacity="0.08" strokeWidth="1" />
              <text x={pad.left - 8} y={gy + 3} textAnchor="end" className="fill-current text-[10px]" fillOpacity="0.45">
                {formatY(val)}
              </text>
            </g>
          );
        })}
        {groups.map((g, gi) => {
          return (
            <g key={gi}>
              {series.map((s, si) => {
                const v = s.data[gi];
                const bh = (v / max) * innerH;
                const groupStart = pad.left + gi * slot + (slot - barW * series.length) / 2;
                const bx = groupStart + si * barW;
                const by = pad.top + innerH - bh;
                return <rect key={si} x={bx} y={by} width={barW - 2} height={bh} rx="4" fill={s.color} fillOpacity="0.85" />;
              })}
              <text x={pad.left + gi * slot + slot / 2} y={H - 14} textAnchor="middle" className="fill-current text-[10px]" fillOpacity="0.55">
                {g}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="flex items-center justify-center gap-4 mt-1">
        {series.map((s, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ background: s.color }} />
            <span className="text-xs text-secondary">{s.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------- Donut Chart ---------- */
export function DonutChart({
  segments,
  size = 160,
}: {
  segments: { label: string; value: number; color: string }[];
  size?: number;
}) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  const r = size / 2 - 12;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {segments.map((s, i) => {
          const frac = s.value / total;
          const dash = frac * circumference;
          const el = (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth="14"
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${cx} ${cy})`}
              strokeLinecap="round"
            />
          );
          offset += dash;
          return el;
        })}
        <text x={cx} y={cy - 4} textAnchor="middle" className="fill-current text-2xl font-bold" fillOpacity="0.9">
          {total}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" className="fill-current text-[10px]" fillOpacity="0.5">
          Total
        </text>
      </svg>
      <div className="space-y-1.5">
        {segments.map((s, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: s.color }} />
            <span className="text-secondary">{s.label}</span>
            <span className="text-primary font-medium ml-auto">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
