"use client";

// Students → Trends: one class, read as a moving picture rather than a list.
//
// The question a head of department actually asks is "which subject is pulling
// this class down, and since when?" — so the centrepiece is the subject
// trajectory chart (one line per subject across test cycles), with the latest
// test's distribution and the class's subject profile beside it. Every chart is
// backed by the same two reads the old list used; nothing new is captured.
//
// Bands stay staff-only (P4) and are shown as counts, never per-student here.

import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Minus, TrendingDown } from "lucide-react";

import {
  AbilityRadar, ChartCard, ColumnChart, Donut, RowBars, StatTile, TrendLine,
  SERIES_COLORS, STATUS_COLOR, toneForPct, type ChartRow, type Series,
} from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { schoolApi } from "@/lib/school-api";
import type { AnalysisMover } from "@/lib/school-types";

// Six is the palette's fixed length — a seventh subject would mean a generated
// hue, which is never allowed. Extras fall to the table, and we say so.
const MAX_LINES = 6;

function DeltaChip({ delta }: { delta: number }) {
  const Icon = delta > 0 ? ArrowUpRight : delta < 0 ? ArrowDownRight : Minus;
  const tone = delta > 0 ? "success" : delta < 0 ? "warning" : "neutral";
  return (
    <Badge tone={tone}>
      <Icon className="h-3 w-3" /> {delta > 0 ? "+" : ""}{delta} pts
    </Badge>
  );
}

function MoverList({ title, rows, tone }: { title: string; rows: AnalysisMover[]; tone: "up" | "down" }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-muted-foreground">{title}</p>
      <ul className="space-y-1.5">
        {rows.map((mv) => (
          <li key={mv.student_id} className="flex items-center justify-between gap-2 text-sm">
            <span className="min-w-0 truncate">{mv.full_name}</span>
            <span className="flex shrink-0 items-center gap-1.5">
              <span className="tabular-nums text-xs text-muted-foreground">
                {mv.prev_pct}% → {mv.latest_pct}%
              </span>
              <Badge tone={tone === "up" ? "success" : "warning"}>
                {tone === "up" ? "+" : ""}{mv.delta}
              </Badge>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ClassAnalytics({ classId }: { classId: string }) {
  const { data: trends = [] } = useQuery({ queryKey: ["trends", classId], queryFn: () => schoolApi.trends(classId) });
  const { data: analysis } = useQuery({ queryKey: ["class-analysis", classId], queryFn: () => schoolApi.classAnalysis(classId) });

  if (!trends.length && !analysis?.cycles.length) {
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
        No test cycles yet. Record an exam under Scores and this board fills itself.
      </p>
    );
  }

  const cycles = analysis?.cycles ?? [];
  const scored = cycles.filter((c) => c.avg_pct != null);
  const latest = scored[scored.length - 1];
  const prev = scored[scored.length - 2];
  const classDelta = latest?.avg_pct != null && prev?.avg_pct != null
    ? Math.round(latest.avg_pct - prev.avg_pct) : null;

  // ── class average over time (single series — the card title names it) ──
  const avgRows: ChartRow[] = scored.map((c) => ({ x: c.name, avg: c.avg_pct }));
  const firstAvg = scored[0]?.avg_pct ?? null;

  // ── subject trajectories (one line per subject, fixed hue order) ──
  const subjectOrder = trends.map((t) => ({ id: t.subject_id, name: t.subject_name }));
  const shown = subjectOrder.slice(0, MAX_LINES);
  const trajRows: ChartRow[] = scored.map((c) => {
    const row: ChartRow = { x: c.name };
    for (const s of shown) {
      row[s.id] = c.subjects.find((x) => x.subject_id === s.id)?.avg_pct ?? null;
    }
    return row;
  });
  const trajSeries: Series[] = shown.map((s, i) => ({
    key: s.id, label: s.name, color: SERIES_COLORS[i % SERIES_COLORS.length],
  }));

  // ── the class's subject profile, latest test (radar) ──
  const radarRows: ChartRow[] = trends
    .map((t) => ({ x: t.subject_name, avg: t.points.length ? t.points[t.points.length - 1].avg_pct : null }))
    .filter((r) => r.avg != null);

  // ── latest test distribution ──
  const histRows: ChartRow[] = (analysis?.histogram ?? []).map((h) => ({ x: h.bucket, count: h.count }));

  const bands = analysis?.band_counts ?? {};
  const bandSlices = (["A", "B", "C"] as const)
    .map((t, i) => ({ label: `Band ${t}`, value: bands[t] ?? 0, color: SERIES_COLORS[i] }))
    .filter((s) => s.value > 0);

  const drops = analysis?.movers.filter((m) => m.delta < -5).slice(0, 5) ?? [];
  const gains = analysis?.movers.filter((m) => m.delta > 5).slice(-5).reverse() ?? [];
  const weak = trends.filter((t) => t.weak);

  // Per-subject latest + change — the table view that sits beside the charts.
  const subjectRows = trends.map((t) => {
    const pts = t.points;
    const last = pts[pts.length - 1];
    const before = pts[pts.length - 2];
    return {
      id: t.subject_id, name: t.subject_name, weak: t.weak,
      latest: last?.avg_pct ?? null,
      delta: last && before ? Math.round(last.avg_pct - before.avg_pct) : null,
      points: pts,
    };
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Class average, latest test"
          value={latest?.avg_pct != null ? `${Math.round(latest.avg_pct)}%` : "—"}
          sub={latest ? latest.name : "no scored test yet"}
          tone={latest?.avg_pct == null ? "neutral" : latest.avg_pct >= 60 ? "green" : latest.avg_pct >= 40 ? "amber" : "red"}
          trend={scored.map((c) => c.avg_pct)}
        />
        <StatTile
          label="Change since previous test"
          value={classDelta == null ? "—" : `${classDelta > 0 ? "+" : ""}${classDelta} pts`}
          sub={prev ? `vs ${prev.name}` : "needs two tests"}
          tone={classDelta == null ? "neutral" : classDelta >= 0 ? "green" : "amber"}
        />
        <StatTile
          label="Tests recorded"
          value={String(cycles.length)}
          sub={scored.length === cycles.length ? "all scored" : `${cycles.length - scored.length} not scored yet`}
        />
        <StatTile
          label="Subjects needing attention"
          value={String(weak.length)}
          sub={weak.length ? weak.map((w) => w.subject_name).join(", ") : "none flagged"}
          tone={weak.length ? "amber" : "green"}
        />
      </div>

      <ChartCard
        title="Subject trajectories"
        hint={shown.length < subjectOrder.length
          ? `One line per subject across test cycles. Showing ${shown.length} of ${subjectOrder.length} — the rest are in the table below.`
          : "One line per subject across test cycles. Hover any point for the exact average."}>
        {trajRows.length > 1 && trajSeries.length ? (
          <TrendLine rows={trajRows} series={trajSeries} yUnit="%" yDomain={[0, 100]} height={260} />
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Two scored tests are needed before a trajectory means anything.
          </p>
        )}
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Class average over time"
          hint={firstAvg != null ? "Dashed line marks where this class started." : undefined}>
          {avgRows.length > 1 ? (
            <TrendLine rows={avgRows} series={[{ key: "avg", label: "Class average" }]}
              yUnit="%" yDomain={[0, 100]} height={200}
              reference={firstAvg != null ? { y: firstAvg, label: "first test" } : undefined} />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">One test so far — no line yet.</p>
          )}
        </ChartCard>

        <ChartCard title="Subject profile"
          hint={`Average per subject in the latest test${analysis?.latest_cycle_name ? ` · ${analysis.latest_cycle_name}` : ""}.`}>
          {radarRows.length >= 3 ? (
            <AbilityRadar rows={radarRows} series={[{ key: "avg", label: "Class average" }]} height={240} />
          ) : radarRows.length ? (
            <RowBars rows={radarRows} dataKey="avg" unit="%" max={100}
              height={Math.max(120, radarRows.length * 34)}
              colorFor={(r) => toneForPct(r.avg as number, { good: 60, fair: 40 })} />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">No subject averages yet.</p>
          )}
        </ChartCard>

        <ChartCard title={`Score distribution${analysis?.latest_cycle_name ? ` · ${analysis.latest_cycle_name}` : ""}`}
          hint="How many students landed in each band of marks.">
          {histRows.length ? (
            <ColumnChart rows={histRows} series={[{ key: "count", label: "Students" }]} height={200} />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">No scored test yet.</p>
          )}
        </ChartCard>

        <ChartCard title="Support tiers" hint="Staff-only intervention tiers — never shared with parents.">
          {bandSlices.length ? (
            <Donut slices={bandSlices} size={148}
              centerValue={String(bandSlices.reduce((s, x) => s + x.value, 0))} centerLabel="banded" />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">Nobody is banded in this class yet.</p>
          )}
          {bands.unset ? (
            <p className="mt-2 text-xs text-muted-foreground">{bands.unset} student(s) not banded.</p>
          ) : null}
        </ChartCard>
      </div>

      {drops.length || gains.length ? (
        <ChartCard title="Who moved" hint="Change of more than 5 points since the previous test.">
          <div className="grid gap-6 sm:grid-cols-2">
            {drops.length ? <MoverList title="Dropped" rows={drops} tone="down" /> : null}
            {gains.length ? <MoverList title="Improved" rows={gains} tone="up" /> : null}
          </div>
        </ChartCard>
      ) : null}

      {/* The table view — every subject, including any the chart had to fold away. */}
      <ChartCard title="Every subject" hint="The same numbers as the charts, in full.">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 pr-3 font-medium">Subject</th>
                <th className="py-2 pr-3 font-medium">Latest</th>
                <th className="py-2 pr-3 font-medium">Change</th>
                <th className="py-2 font-medium">History</th>
              </tr>
            </thead>
            <tbody>
              {subjectRows.map((s, i) => (
                <tr key={s.id} className="border-b border-border/60 last:border-0">
                  <td className="py-2 pr-3">
                    <span className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 shrink-0 rounded-sm"
                        style={{ background: i < MAX_LINES ? SERIES_COLORS[i % SERIES_COLORS.length] : STATUS_COLOR.neutral }} />
                      <span className="font-medium">{s.name}</span>
                      {s.weak ? <Badge tone="warning"><TrendingDown className="h-3 w-3" /> weak</Badge> : null}
                    </span>
                  </td>
                  <td className="py-2 pr-3 tabular-nums">{s.latest != null ? `${s.latest}%` : "—"}</td>
                  <td className="py-2 pr-3">{s.delta != null ? <DeltaChip delta={s.delta} /> : <span className="text-muted-foreground">—</span>}</td>
                  <td className="py-2 text-xs text-muted-foreground">
                    {s.points.map((p) => `${p.cycle_name} ${p.avg_pct}%`).join(" → ") || "no scores"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartCard>
    </div>
  );
}
