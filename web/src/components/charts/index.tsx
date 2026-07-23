"use client";

// The public face of the chart kit. Every Recharts component arrives through
// next/dynamic, so the library is ONE lazily-loaded chunk shared by the
// dashboard, the class trends board and the student report card — it never
// lands in the nav bundle. The non-chart primitives below are plain CSS and
// render immediately, so a page's numbers are readable before the plots paint.

import dynamic from "next/dynamic";
import Link from "next/link";

import { SERIES_COLORS, STATUS_COLOR } from "@/components/charts/palette";

export { SERIES_COLORS, STATUS_COLOR, toneForPct } from "@/components/charts/palette";
export type { ChartRow, Series, Slice } from "@/components/charts/palette";

function skeleton(height: number) {
  const Loading = () => (
    <div className="w-full animate-pulse rounded-lg bg-muted/60" style={{ height }} />
  );
  Loading.displayName = "ChartSkeleton";
  return Loading;
}

export const TrendLine = dynamic(
  () => import("@/components/charts/school-charts").then((m) => m.TrendLine),
  { ssr: false, loading: skeleton(220) });
export const PulseArea = dynamic(
  () => import("@/components/charts/school-charts").then((m) => m.PulseArea),
  { ssr: false, loading: skeleton(150) });
export const ColumnChart = dynamic(
  () => import("@/components/charts/school-charts").then((m) => m.ColumnChart),
  { ssr: false, loading: skeleton(220) });
export const RowBars = dynamic(
  () => import("@/components/charts/school-charts").then((m) => m.RowBars),
  { ssr: false, loading: skeleton(220) });
export const Donut = dynamic(
  () => import("@/components/charts/school-charts").then((m) => m.Donut),
  { ssr: false, loading: skeleton(168) });
export const Gauge = dynamic(
  () => import("@/components/charts/school-charts").then((m) => m.Gauge),
  { ssr: false, loading: skeleton(116) });
export const AbilityRadar = dynamic(
  () => import("@/components/charts/school-charts").then((m) => m.AbilityRadar),
  { ssr: false, loading: skeleton(260) });
export const Sparkline = dynamic(
  () => import("@/components/charts/school-charts").then((m) => m.Sparkline),
  { ssr: false, loading: skeleton(34) });

// ── frames & non-chart primitives ────────────────────────────────────────────

/** The frame every chart sits in. The title names the single series, which is
 * why single-series charts carry no legend. */
export function ChartCard({
  title, hint, action, children, className = "",
}: {
  title: string;
  hint?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-border bg-card p-4 ${className}`}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">{title}</h3>
          {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

/** A headline number. `trend` is the shape behind it, never a second axis. */
export function StatTile({
  label, value, sub, tone = "neutral", trend, href,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "green" | "amber" | "red";
  trend?: (number | null)[];
  href?: string;
}) {
  const toneClass = {
    neutral: "", green: "text-success", amber: "text-warning", red: "text-danger",
  }[tone];
  const body = (
    <>
      <p className="truncate text-xs text-muted-foreground">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${toneClass}`}>{value}</p>
      {sub ? <p className="mt-0.5 truncate text-xs text-muted-foreground">{sub}</p> : null}
      {trend && trend.filter((v) => v != null).length > 1 ? (
        <div className="mt-2 -mx-1">
          <Sparkline values={trend} color={tone === "neutral" ? SERIES_COLORS[0] : STATUS_COLOR[tone]} />
        </div>
      ) : null}
    </>
  );
  const cls = "block rounded-xl border border-border bg-card p-4";
  if (href) {
    return <Link href={href} className={`${cls} transition-colors hover:border-primary/40`}>{body}</Link>;
  }
  return <div className={cls}>{body}</div>;
}

/** A segmented meter — two known parts of a known whole (topics taught vs
 * missed, fees collected vs due). A 2px surface gap separates the fills. */
export function MeterBar({
  parts, height = 6,
}: {
  parts: { value: number; color: string; label: string }[];
  height?: number;
}) {
  const total = parts.reduce((sum, p) => sum + Math.max(0, p.value), 0) || 1;
  return (
    <div className="flex w-full overflow-hidden rounded-full bg-muted" style={{ height }}>
      {parts.map((p, i) => (
        <div key={i} title={`${p.label}: ${p.value}`}
          style={{
            width: `${(Math.max(0, p.value) / total) * 100}%`,
            background: p.color,
            marginRight: i < parts.length - 1 ? 2 : 0,
          }} />
      ))}
    </div>
  );
}
