"use client";

import type { MemberBar, TrendPoint } from "@/lib/types";
import { cn } from "@/lib/utils";

export function RangeToggle({
  value,
  onChange,
}: {
  value: "today" | "week";
  onChange: (v: "today" | "week") => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-border bg-card p-0.5 text-sm">
      {(["today", "week"] as const).map((r) => (
        <button
          key={r}
          onClick={() => onChange(r)}
          className={cn(
            "rounded-md px-3 py-1 font-medium capitalize transition-colors",
            value === r ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {r === "week" ? "7 days" : "Today"}
        </button>
      ))}
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: "success" | "warning" | "default";
}) {
  const valueTone =
    tone === "success" ? "text-success" : tone === "warning" ? "text-warning" : "text-foreground";
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-2xl font-semibold tabular-nums", valueTone)}>{value}</p>
      {sub ? <p className="text-xs text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

export function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div
        className="h-full rounded-full bg-success transition-all duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

/** Per-member completion bars. `action` renders trailing controls (e.g. nudge). */
export function MemberBars({
  members,
  action,
}: {
  members: MemberBar[];
  action?: (m: MemberBar) => React.ReactNode;
}) {
  if (members.length === 0) {
    return <p className="text-sm text-muted-foreground">No assigned work in this window.</p>;
  }
  return (
    <ul className="space-y-3">
      {members.map((m) => (
        <li key={m.user_id} className="flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-sm font-medium">{m.name}</span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {m.done}/{m.total}
                {m.done > 0 ? ` · ${m.on_time} on time` : ""}
              </span>
            </div>
            <div className="mt-1.5">
              <ProgressBar done={m.done} total={m.total} />
            </div>
          </div>
          {action ? <div className="shrink-0">{action(m)}</div> : null}
        </li>
      ))}
    </ul>
  );
}

/** Lightweight inline SVG sparkline — no chart lib (plan P3-FE-01). */
export function TrendSparkline({ trend }: { trend: TrendPoint[] }) {
  if (trend.length === 0) return null;
  const w = 280;
  const h = 48;
  const max = Math.max(1, ...trend.map((p) => p.done));
  const step = trend.length > 1 ? w / (trend.length - 1) : w;
  const pts = trend.map((p, i) => {
    const x = i * step;
    const y = h - (p.done / max) * (h - 6) - 3;
    return [x, y] as const;
  });
  const line = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${w},${h} L0,${h} Z`;
  const total = trend.reduce((s, p) => s + p.done, 0);

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          14-day trend
        </p>
        <span className="text-xs text-muted-foreground">{total} completed</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="h-12 w-full" preserveAspectRatio="none" aria-hidden>
        <path d={area} fill="var(--color-success)" opacity={0.12} />
        <path
          d={line}
          fill="none"
          stroke="var(--color-success)"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}
