"use client";

// TrackBit's chart kit — every chart in the product is one of these, so the
// dashboard, the class trends and a student's report card read as one system.
// Loaded as a SINGLE next/dynamic chunk (see ./index.tsx) so Recharts never
// lands in the nav bundle.
//
// Dataviz rules applied throughout:
//   * one axis, never two y-scales;
//   * categorical hues assigned in fixed order and never cycled — identity
//     follows the entity, so filtering a series never repaints the survivors;
//   * status colours (green/amber/red) are RESERVED for RAG/attendance state and
//     always ship with their label — state is never colour-alone;
//   * thin marks, 4px rounded data-ends, 2px lines, a 2px surface gap between
//     adjacent fills, recessive grid;
//   * a hover tooltip on every plot, a legend at >= 2 series (one series is
//     named by the card title), direct labels on donut slices;
//   * text wears text tokens — never the series colour.

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  RadialBar,
  RadialBarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChartRow, Series, Slice } from "@/components/charts/palette";
import { SERIES_COLORS } from "@/components/charts/palette";

const AXIS_TICK = { fontSize: 11, fill: "var(--color-muted-foreground)" } as const;

const TOOLTIP_STYLE = {
  backgroundColor: "var(--color-card)",
  border: "1px solid var(--color-border)",
  borderRadius: "0.5rem",
  fontSize: "12px",
  color: "var(--color-foreground)",
} as const;

function colorAt(s: Series, i: number) {
  return s.color ?? SERIES_COLORS[i % SERIES_COLORS.length];
}

/** Identity is never colour-alone: every multi-series chart carries this. */
export function ChartLegend({ series }: { series: Series[] }) {
  if (series.length < 2) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
      {series.map((s, i) => (
        <span key={s.key} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: colorAt(s, i) }} />
          {s.label}
        </span>
      ))}
    </div>
  );
}

// ── lines ────────────────────────────────────────────────────────────────────

export function TrendLine({
  rows, series, height = 220, yDomain, yUnit = "", reference,
}: {
  rows: ChartRow[];
  series: Series[];
  height?: number;
  yDomain?: [number, number];
  yUnit?: string;
  reference?: { y: number; label: string };
}) {
  return (
    <div>
      <div style={{ height }} className="w-full">
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
            <CartesianGrid vertical={false} stroke="var(--color-border)" />
            <XAxis dataKey="x" tick={AXIS_TICK} tickLine={false}
              axisLine={{ stroke: "var(--color-border)" }} interval="preserveStartEnd" minTickGap={12} />
            <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={44}
              domain={yDomain ?? ["auto", "auto"]} unit={yUnit} />
            <Tooltip contentStyle={TOOLTIP_STYLE}
              cursor={{ stroke: "var(--color-border)", strokeWidth: 1 }}
              formatter={(v: unknown) => `${v}${yUnit}`} />
            {reference ? (
              <ReferenceLine y={reference.y} stroke="var(--color-muted-foreground)"
                strokeDasharray="4 4" strokeOpacity={0.6}
                label={{ value: reference.label, position: "insideTopRight",
                  fill: "var(--color-muted-foreground)", fontSize: 10 }} />
            ) : null}
            {series.map((s, i) => (
              <Line key={s.key} type="monotone" dataKey={s.key} name={s.label}
                stroke={colorAt(s, i)} strokeWidth={2}
                dot={{ r: 3, strokeWidth: 0, fill: colorAt(s, i) }}
                activeDot={{ r: 5, stroke: "var(--color-card)", strokeWidth: 2 }}
                connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ChartLegend series={series} />
    </div>
  );
}

/** One measure over time, filled — used where the shape matters more than the
 * exact value (the attendance pulse). Single series by design. */
export function PulseArea({
  rows, dataKey, label, height = 150, yDomain, yUnit = "", color,
}: {
  rows: ChartRow[];
  dataKey: string;
  label: string;
  height?: number;
  yDomain?: [number, number];
  yUnit?: string;
  color?: string;
}) {
  const stroke = color ?? SERIES_COLORS[1];
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <AreaChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id={`pulse-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--color-border)" />
          <XAxis dataKey="x" tick={AXIS_TICK} tickLine={false}
            axisLine={{ stroke: "var(--color-border)" }} interval="preserveStartEnd" minTickGap={16} />
          <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={44}
            domain={yDomain ?? ["auto", "auto"]} unit={yUnit} />
          <Tooltip contentStyle={TOOLTIP_STYLE}
            cursor={{ stroke: "var(--color-border)", strokeWidth: 1 }}
            formatter={(v: unknown) => [`${v}${yUnit}`, label]} />
          <Area type="monotone" dataKey={dataKey} name={label} stroke={stroke} strokeWidth={2}
            fill={`url(#pulse-${dataKey})`}
            dot={{ r: 2.5, strokeWidth: 0, fill: stroke }}
            activeDot={{ r: 5, stroke: "var(--color-card)", strokeWidth: 2 }} connectNulls />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── bars ─────────────────────────────────────────────────────────────────────

export function ColumnChart({
  rows, series, height = 220, yUnit = "", yDomain, stacked = false,
}: {
  rows: ChartRow[];
  series: Series[];
  height?: number;
  yUnit?: string;
  yDomain?: [number, number];
  stacked?: boolean;
}) {
  return (
    <div>
      <div style={{ height }} className="w-full">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -18 }} barGap={2}>
            <CartesianGrid vertical={false} stroke="var(--color-border)" />
            <XAxis dataKey="x" tick={AXIS_TICK} tickLine={false}
              axisLine={{ stroke: "var(--color-border)" }} interval={0} />
            <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={44}
              unit={yUnit} domain={yDomain ?? [0, "auto"]} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "var(--color-muted)", opacity: 0.4 }}
              formatter={(v: unknown) => `${v}${yUnit}`} />
            {series.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} name={s.label} maxBarSize={30}
                stackId={stacked ? "a" : undefined}
                radius={stacked && i < series.length - 1 ? [0, 0, 0, 0] : [4, 4, 0, 0]}
                fill={colorAt(s, i)}
                stroke="var(--color-card)" strokeWidth={stacked ? 2 : 0} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartLegend series={series} />
    </div>
  );
}

/** Horizontal bars — the right form when the category labels are long (class
 * names, subject names) and the measure is a simple magnitude. */
export function RowBars({
  rows, dataKey, height = 220, unit = "", colorFor, max, labelWidth = 92,
}: {
  rows: ChartRow[];
  dataKey: string;
  height?: number;
  unit?: string;
  colorFor?: (row: ChartRow) => string;
  max?: number;
  labelWidth?: number;
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 4 }}>
          <CartesianGrid horizontal={false} stroke="var(--color-border)" />
          <XAxis type="number" tick={AXIS_TICK} tickLine={false} axisLine={false}
            domain={[0, max ?? "auto"]} unit={unit} />
          <YAxis type="category" dataKey="x" tick={AXIS_TICK} tickLine={false}
            axisLine={{ stroke: "var(--color-border)" }} width={labelWidth} interval={0} />
          <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "var(--color-muted)", opacity: 0.4 }}
            formatter={(v: unknown) => `${v}${unit}`} />
          <Bar dataKey={dataKey} maxBarSize={18} radius={[0, 4, 4, 0]}>
            {rows.map((r, i) => (
              <Cell key={i} fill={colorFor ? colorFor(r) : SERIES_COLORS[0]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── parts of a whole ─────────────────────────────────────────────────────────

export function Donut({
  slices, centerValue, centerLabel, size = 168,
}: {
  slices: Slice[];
  centerValue?: string;
  centerLabel?: string;
  size?: number;
}) {
  const total = slices.reduce((sum, s) => sum + (s.value || 0), 0);
  return (
    <div className="flex flex-wrap items-center gap-5">
      <div className="relative shrink-0" style={{ height: size, width: size }}>
        <ResponsiveContainer>
          <PieChart>
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Pie data={slices} dataKey="value" nameKey="label" innerRadius="64%" outerRadius="96%"
              paddingAngle={1.5} stroke="var(--color-card)" strokeWidth={2}>
              {slices.map((s, i) => (
                <Cell key={s.label} fill={s.color ?? SERIES_COLORS[i % SERIES_COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {centerValue ? (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-semibold tabular-nums">{centerValue}</span>
            {centerLabel ? (
              <span className="text-[11px] text-muted-foreground">{centerLabel}</span>
            ) : null}
          </div>
        ) : null}
      </div>
      {/* Direct labels with values — never colour-alone, never a number on the arc. */}
      <ul className="min-w-0 flex-1 space-y-1.5">
        {slices.map((s, i) => (
          <li key={s.label} className="flex items-center gap-2 text-sm">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ background: s.color ?? SERIES_COLORS[i % SERIES_COLORS.length] }} />
            <span className="min-w-0 flex-1 truncate">{s.label}</span>
            <span className="tabular-nums text-muted-foreground">
              {s.value}{total > 0 ? ` · ${Math.round((s.value / total) * 100)}%` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A single percentage as a ring. One number, so no axis and no legend — the
 * label beside it names what it measures. */
export function Gauge({
  value, label, sub, size = 116, color,
}: {
  value: number | null;
  label: string;
  sub?: string;
  size?: number;
  color?: string;
}) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  const fill = color ?? SERIES_COLORS[1];
  const data = [{ name: label, value: pct, fill }];
  return (
    <div className="flex items-center gap-3">
      <div className="relative shrink-0" style={{ height: size, width: size }}>
        <ResponsiveContainer>
          <RadialBarChart data={data} innerRadius="74%" outerRadius="100%"
            startAngle={90} endAngle={-270}>
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar background={{ fill: "var(--color-muted)" }} dataKey="value" cornerRadius={8} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-semibold tabular-nums">
            {value == null ? "—" : `${Math.round(value)}%`}
          </span>
        </div>
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium">{label}</p>
        {sub ? <p className="text-xs text-muted-foreground">{sub}</p> : null}
      </div>
    </div>
  );
}

// ── profile shape ────────────────────────────────────────────────────────────

/** The ability radar: one axis per skill area, 0-100. Two series at most (the
 * student and the class average) — beyond that a radar becomes a scribble. */
export function AbilityRadar({
  rows, series, height = 260,
}: {
  rows: ChartRow[];          // [{ x: "Reasoning", student: 72, class: 61 }, …]
  series: Series[];
  height?: number;
}) {
  return (
    <div>
      <div style={{ height }} className="w-full">
        <ResponsiveContainer>
          <RadarChart data={rows} outerRadius="70%">
            <PolarGrid stroke="var(--color-border)" />
            <PolarAngleAxis dataKey="x"
              tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} />
            <PolarRadiusAxis domain={[0, 100]} angle={90} tickCount={3} axisLine={false}
              tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: unknown) => `${v}%`} />
            {series.map((s, i) => (
              <Radar key={s.key} dataKey={s.key} name={s.label}
                stroke={colorAt(s, i)} strokeWidth={2}
                fill={colorAt(s, i)} fillOpacity={i === 0 ? 0.22 : 0.08}
                dot={{ r: 3, strokeWidth: 0, fill: colorAt(s, i) }} />
            ))}
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <ChartLegend series={series} />
    </div>
  );
}

/** A sparkline for a stat tile: shape only, no axes, no tooltip — the tile's
 * number carries the value. */
export function Sparkline({
  values, color, height = 34,
}: {
  values: (number | null)[];
  color?: string;
  height?: number;
}) {
  const rows = values.map((v, i) => ({ x: i, v }));
  const stroke = color ?? SERIES_COLORS[0];
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 4, right: 2, bottom: 2, left: 2 }}>
          <Line type="monotone" dataKey="v" stroke={stroke} strokeWidth={2} dot={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
