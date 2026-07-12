"use client";

// Lucy's chart widgets (Recharts) — loaded as ONE dynamic chunk from the
// widget renderer so the library never lands in the main bundle.
//
// Dataviz rules applied: one fixed categorical order (palette validated for
// light AND dark surfaces with the six-checks script — do not eyeball edits
// to it), single axis, thin rounded marks with surface gaps, recessive grid,
// hover tooltips everywhere, a legend only at ≥2 series (a single series is
// named by the widget title), text in text tokens — never in series color.

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChartData, DonutData } from "@/lib/lucy-types";

// Validated with dataviz six-checks for both #fcfcfb (light) and dark surfaces.
export const SERIES_COLORS = [
  "#5b74e8", "#1f9a5f", "#b0762a", "#c2447e", "#2b93b3", "#8a5fd4",
];

const AXIS_TICK = { fontSize: 11, fill: "var(--color-muted-foreground)" } as const;

const TOOLTIP_STYLE = {
  backgroundColor: "var(--color-card)",
  border: "1px solid var(--color-border)",
  borderRadius: "0.5rem",
  fontSize: "12px",
  color: "var(--color-foreground)",
} as const;

function SeriesLegend({ series }: { series: { key: string; label: string }[] }) {
  if (series.length < 2) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 px-1">
      {series.map((s, i) => (
        <span key={s.key} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="h-2.5 w-2.5 rounded-sm"
            style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }} />
          {s.label}
        </span>
      ))}
    </div>
  );
}

export function LucyBarChart({ data }: { data: ChartData }) {
  const { rows, series } = data;
  return (
    <div>
      <div className="h-56 w-full">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barGap={2}>
            <CartesianGrid vertical={false} stroke="var(--color-border)" strokeDasharray="0" />
            <XAxis dataKey="x" tick={AXIS_TICK} tickLine={false}
              axisLine={{ stroke: "var(--color-border)" }} interval="preserveStartEnd" />
            <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={40} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "var(--color-muted)", opacity: 0.4 }} />
            {series.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} name={s.label} maxBarSize={28}
                radius={[4, 4, 0, 0]} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <SeriesLegend series={series} />
    </div>
  );
}

export function LucyLineChart({ data }: { data: ChartData }) {
  const { rows, series } = data;
  return (
    <div>
      <div className="h-56 w-full">
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke="var(--color-border)" strokeDasharray="0" />
            <XAxis dataKey="x" tick={AXIS_TICK} tickLine={false}
              axisLine={{ stroke: "var(--color-border)" }} interval="preserveStartEnd" />
            <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={40} />
            <Tooltip contentStyle={TOOLTIP_STYLE}
              cursor={{ stroke: "var(--color-border)", strokeWidth: 1 }} />
            {series.map((s, i) => (
              <Line key={s.key} type="monotone" dataKey={s.key} name={s.label}
                stroke={SERIES_COLORS[i % SERIES_COLORS.length]} strokeWidth={2}
                dot={{ r: 3, strokeWidth: 0, fill: SERIES_COLORS[i % SERIES_COLORS.length] }}
                activeDot={{ r: 5 }} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <SeriesLegend series={series} />
    </div>
  );
}

export function LucyDonut({ data }: { data: DonutData }) {
  const slices = data.slices;
  const total = slices.reduce((sum, s) => sum + (s.value || 0), 0);
  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="h-44 w-44 shrink-0">
        <ResponsiveContainer>
          <PieChart>
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Pie data={slices} dataKey="value" nameKey="label" innerRadius="62%"
              outerRadius="95%" paddingAngle={1.5} stroke="var(--color-card)" strokeWidth={2}>
              {slices.map((s, i) => (
                <Cell key={s.label} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      {/* Direct labels with values — identity is never color-alone. */}
      <ul className="min-w-0 flex-1 space-y-1.5">
        {slices.map((s, i) => (
          <li key={s.label} className="flex items-center gap-2 text-sm">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }} />
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
