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

/**
 * Arc length for a ring gauge, and the cap that goes with it.
 *
 * A round cap extends the stroke by `stroke/2` at EACH end, so a 99.2% arc drawn
 * naively is visually 100% — the two caps meet and the gap that carries the
 * whole meaning of the figure disappears. 238 of 240 then looks exactly like
 * 240 of 240, which is the one thing a presence ring must never do.
 *
 * So: subtract the cap overhang from the drawn length, and keep a floor of one
 * stroke width so a tiny-but-real percentage is still a visible mark. A genuine
 * 100% draws the closed circle with a butt cap — no overhang to hide.
 */
function arcGeometry(pct: number | null, circumference: number, stroke: number) {
  if (pct == null) return { length: 0, cap: "butt" as const };
  const clamped = Math.max(0, Math.min(100, pct));
  // A true zero draws NOTHING. The floor below exists so a tiny-but-real share
  // is still a visible mark, and applying it to 0 put a coloured nub on a ring
  // that means "none of this has happened" — the mirror of the closed-circle
  // bug at the other end, and just as much a lie.
  if (clamped === 0) return { length: 0, cap: "butt" as const };
  if (clamped >= 100) return { length: circumference, cap: "butt" as const };
  const ideal = (circumference * clamped) / 100;
  return {
    length: Math.max(Math.min(ideal, circumference - stroke * 1.6) - stroke, stroke * 0.5),
    cap: "round" as const,
  };
}

/**
 * The roll medallion — concentric arcs, one per cohort, composed as ONE object.
 *
 * Three loose donuts sat on the page as three unrelated widgets. A school's roll
 * is one fact with three parts, and this says so: outermost is the largest
 * cohort, each arc keeps its own denominator (so nothing is being compared by
 * arc length — they are three completions, not three magnitudes), and the exact
 * figures live in the legend beside it, in tabular mono, where they are actually
 * legible. The centre carries the only number with no denominator problem: how
 * many people are in the building.
 *
 * A cohort nobody has marked gets a dashed track and no arc — visibly a ring
 * waiting to be filled in, never an empty one that reads as zero.
 */
export function RollMedallion({
  arcs, size = 168, stroke = 12, gap = 7, children,
}: {
  arcs: { key: string; pct: number | null; color: string; label: string }[];
  size?: number;
  stroke?: number;
  gap?: number;
  children?: React.ReactNode;
}) {
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90"
        role="img"
        aria-label={arcs.map((a) => `${a.label}: ${a.pct == null ? "not marked" : `${a.pct}%`}`)
          .join(", ")}>
        {arcs.map((a, i) => {
          const r = (size - stroke) / 2 - i * (stroke + gap);
          if (r <= stroke) return null;
          const c = 2 * Math.PI * r;
          const { length, cap } = arcGeometry(a.pct, c, stroke);
          return (
            <g key={a.key}>
              <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke}
                className="stroke-muted" strokeLinecap="round"
                strokeDasharray={a.pct == null ? "2 6" : undefined} />
              {a.pct != null ? (
                <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={a.color}
                  strokeWidth={stroke} strokeLinecap={cap}
                  strokeDasharray={`${length} ${c}`}>
                  <title>{`${a.label}: ${a.pct}%`}</title>
                </circle>
              ) : null}
            </g>
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        {children}
      </div>
    </div>
  );
}

/**
 * A ring gauge — one part of one whole, read at a glance (V1-14).
 *
 * Deliberately radial, and deliberately NOT used to compare categories: each
 * ring is its own question with its own denominator (students, teachers, admin
 * staff), so there is no arc-length comparison for the eye to get wrong. The
 * magnitude is carried by the text in the middle; the arc is the shape.
 *
 * Three rules it must keep:
 *   * `pct === null` is **not captured** — a dashed neutral track and the word,
 *     never a 0% ring and never red. An admin who marks staff at 10am must not
 *     open a red board every morning.
 *   * the colour is a status (good / watch / serious), so it always ships with
 *     its label underneath — never colour alone.
 *   * the accessible name is the whole sentence, denominator included, because
 *     a screen reader gets no help at all from an arc.
 */
export function ActivityRing({
  pct, label, caption, tone = "neutral", size = 96, stroke = 9, color: colorOverride,
  children,
}: {
  pct: number | null;
  label: string;
  caption?: string;
  tone?: "neutral" | "green" | "amber" | "red";
  size?: number;
  stroke?: number;
  /** Paint the arc by ENTITY instead of status — used where several rings sit
   *  side by side and the reader has to tell which is which. The status then
   *  has to be carried in text, which the caller is responsible for. */
  color?: string;
  children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const { length, cap } = arcGeometry(pct, circumference, stroke);
  const color = pct == null ? "var(--color-muted-foreground)"
    : colorOverride ?? STATUS_COLOR[tone];

  return (
    <div className="flex min-w-0 flex-col items-center gap-1.5 text-center">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
          aria-label={`${label}: ${caption ?? (pct == null ? "not captured" : `${pct}%`)}`}
          className="-rotate-90">
          {/* The track. Dashed when nothing has been captured, so "no record" is
              legible as a texture and not only as a missing colour. */}
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke}
            className="stroke-muted"
            strokeDasharray={pct == null ? "3 5" : undefined} strokeLinecap="round" />
          {pct != null ? (
            <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color}
              strokeWidth={stroke} strokeLinecap={cap}
              strokeDasharray={`${length} ${circumference}`} />
          ) : null}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
          {children}
        </div>
      </div>
      <p className="text-xs font-medium">{label}</p>
      {caption ? (
        <p className="text-[11px] leading-snug text-muted-foreground">{caption}</p>
      ) : null}
    </div>
  );
}

/**
 * The pace device (V1-15) — a completion arc with the PLAN'S OWN MARKER on it.
 *
 * A syllabus percentage on its own is unreadable: 47% is excellent in July and
 * alarming in February, and no reader carries the school calendar in their head.
 * So the track carries a tick at the share the approved plan had scheduled by
 * today, and the whole verdict becomes a distance you can see — arc past the
 * tick is ahead, arc short of it is behind, and the size of the gap is the size
 * of the problem. The number in the middle is then a detail, not a riddle.
 *
 * The same device repeats at two smaller scales (`PaceBar`, and the cells of the
 * teacher matrix) so one visual habit reads the whole module. Deliberately not
 * a second chart type per scope — "one computation, many renderings" applies to
 * the drawing as much as to the arithmetic.
 *
 * Both figures are divided server-side (`S-51`). This component never computes
 * a percentage; it only places one.
 */
export function PaceRing({
  pct, expectedPct, tone = "neutral", size = 148, stroke = 14, children,
  label,
}: {
  pct: number | null;
  /** Where the plan said this would be by today, on the SAME denominator. */
  expectedPct?: number | null;
  tone?: "neutral" | "green" | "amber" | "red";
  size?: number;
  stroke?: number;
  label?: string;
  children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const { length, cap } = arcGeometry(pct, circumference, stroke);
  const centre = size / 2;

  // The marker, in the SVG's own frame; the -90° rotation on the <svg> takes it
  // to the top with the arc, so the two can never drift apart.
  const marker = expectedPct == null ? null : (() => {
    const theta = (Math.max(0, Math.min(100, expectedPct)) / 100) * 2 * Math.PI;
    const inner = r - stroke / 2 - 3;
    const outer = r + stroke / 2 + 3;
    return {
      x1: centre + inner * Math.cos(theta), y1: centre + inner * Math.sin(theta),
      x2: centre + outer * Math.cos(theta), y2: centre + outer * Math.sin(theta),
    };
  })();

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90"
        role="img"
        aria-label={[
          label,
          pct == null ? "nothing recorded yet" : `${pct}% covered`,
          expectedPct != null ? `plan expected ${expectedPct}% by today` : null,
        ].filter(Boolean).join(", ")}>
        <circle cx={centre} cy={centre} r={r} fill="none" strokeWidth={stroke}
          className="stroke-muted" strokeLinecap="round"
          strokeDasharray={pct == null ? "3 6" : undefined} />
        {pct != null ? (
          <circle cx={centre} cy={centre} r={r} fill="none" stroke={STATUS_COLOR[tone]}
            strokeWidth={stroke} strokeLinecap={cap}
            strokeDasharray={`${length} ${circumference}`} />
        ) : null}
        {/* Drawn twice: a surface-coloured line first, so the tick stays legible
            whether it lands on the filled arc or on the bare track. */}
        {marker ? (
          <>
            <line {...marker} strokeWidth={5} className="stroke-card" strokeLinecap="round" />
            <line {...marker} strokeWidth={2} className="stroke-foreground" strokeLinecap="round">
              <title>{`The plan expected ${expectedPct}% by today`}</title>
            </line>
          </>
        ) : null}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        {children}
      </div>
    </div>
  );
}

/**
 * The same device, flattened — a completion bar with the plan's marker on it.
 *
 * Used wherever the ring would be too big to repeat: every row of the scope
 * ledger, every cell of the teacher matrix, every class and subject on the
 * overview block. The tick means exactly what it means on the ring.
 */
export function PaceBar({
  pct, expectedPct, tone = "neutral", height = 8, className = "",
}: {
  pct: number | null;
  expectedPct?: number | null;
  tone?: "neutral" | "green" | "amber" | "red";
  height?: number;
  className?: string;
}) {
  const width = pct == null ? 0 : Math.max(0, Math.min(100, pct));
  return (
    <div className={`relative w-full overflow-hidden rounded-full ${className}`}
      style={{ height }}>
      {/* Nothing recorded reads as a texture, never as an empty bar at zero —
          "not captured" and "none of it taught" are opposite findings. */}
      <div className={`absolute inset-0 rounded-full ${pct == null
        ? "border border-dashed border-muted-foreground/40" : "bg-muted"}`} />
      {pct != null ? (
        <div className="absolute inset-y-0 left-0 rounded-full transition-[width]"
          style={{ width: `${width}%`, background: STATUS_COLOR[tone] }} />
      ) : null}
      {expectedPct != null ? (
        <span title={`The plan expected ${expectedPct}% by today`}
          className="absolute inset-y-0 w-[2px] rounded-full bg-foreground"
          style={{
            left: `${Math.max(0, Math.min(100, expectedPct))}%`,
            // Half a hair back, so the tick straddles the position rather than
            // starting at it — at 100% it would otherwise sit outside the bar.
            transform: "translateX(-1px)",
            boxShadow: "0 0 0 1.5px var(--color-card)",
          }} />
      ) : null}
    </div>
  );
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
