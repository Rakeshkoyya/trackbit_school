"use client";

// Exams — results, school → class → subject, across cycles (DASH3 §4.6).
//
// The type filter is what makes this one screen instead of several: a weekly CET
// and a term exam are the same shape of data, and `assessment_cycles.type`
// already separates them.
//
// Two honesty rules the UI holds:
//   * **participation sits next to every average.** An 88% from 9 of 42 students
//     is not an 88% class, and a roll-up that hides its denominator lets a
//     half-marked paper quietly lift the school figure.
//   * **no band tier appears anywhere** (P4). Band tests show as tests — real
//     marks — but never as a tier.

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ChartCard, ColumnChart, RowBars, StatTile, TrendLine, SERIES_COLORS, toneForPct, type ChartRow } from "@/components/charts";
import { BoardSkeleton, Empty, ScrollX, Section, StateChip, dayLabel } from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { insightsApi } from "@/lib/insights-api";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<string, string> = {
  chapter_test: "Chapter test",
  class_test: "Class test",
  slip_test: "Slip test",
  objective: "Objective",
  band_test: "Band test",
  term_exam: "Term exam",
  diagnostic: "Diagnostic",
};
const label = (t: string) => TYPE_LABEL[t] ?? t.replace(/_/g, " ");

function ExamsInner() {
  const { yearId } = useYear();
  const [type, setType] = useState<string>("");
  const { data, isLoading } = useQuery({
    queryKey: ["insights", "exams", yearId, type],
    queryFn: () => insightsApi.exams({ yearId: yearId ?? undefined, type: type || undefined }),
  });

  if (isLoading || !data) {
    return <><PageHeader title="Exams" subtitle="How the school is scoring, and where it is slipping." /><BoardSkeleton /></>;
  }

  const classRows: ChartRow[] = data.by_class.map((c) => ({ x: c.label, pct: c.avg_pct }));
  const subjectRows: ChartRow[] = data.by_subject.map((c) => ({ x: c.label, pct: c.avg_pct }));
  const distRows: ChartRow[] = data.distribution.map((b) => ({ x: b.label, students: b.count }));

  // Subject trajectories share one x-axis of test labels; each subject is a
  // series in fixed palette order, so a filter never repaints the survivors.
  const trendKeys = data.trends.slice(0, 6);
  const trendLabels = Array.from(
    new Set(trendKeys.flatMap((t) => t.points.map((p) => p.date))),
  ).sort();
  const trendRows: ChartRow[] = trendLabels.map((d) => {
    const row: ChartRow = { x: dayLabel(d) };
    for (const t of trendKeys) {
      const hit = t.points.find((p) => p.date === d);
      row[t.key] = hit ? hit.avg_pct : null;
    }
    return row;
  });

  const best = data.by_class[0];
  const worst = data.by_class[data.by_class.length - 1];

  return (
    <div>
      <PageHeader title="Exams" subtitle="How the school is scoring, and where it is slipping." />

      <div className="mb-5 flex flex-wrap items-center gap-1 rounded-lg border border-border p-0.5">
        <button type="button" onClick={() => setType("")}
          className={cn("rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            !type ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground")}>
          All tests
        </button>
        {data.types.map((t) => (
          <button key={t} type="button" onClick={() => setType(t)}
            className={cn("rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              type === t ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground")}>
            {label(t)}
          </button>
        ))}
      </div>

      {!data.exams ? (
        <Empty>No tests recorded{type ? ` of this type` : ""} in this academic year yet.</Empty>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="School average"
              value={data.avg_pct != null ? `${data.avg_pct}%` : "—"}
              sub={`${data.exams} test${data.exams === 1 ? "" : "s"} · ${data.scored} marks`}
              tone={data.avg_pct == null ? "neutral"
                : data.avg_pct >= 65 ? "green" : data.avg_pct >= 45 ? "amber" : "red"} />
            <StatTile label="Best class"
              value={best?.avg_pct != null ? `${best.avg_pct}%` : "—"}
              sub={best?.label ?? "not enough marks"} tone="green" />
            <StatTile label="Needs attention"
              value={worst?.avg_pct != null ? `${worst.avg_pct}%` : "—"}
              sub={worst && worst !== best ? worst.label : "only one class scored"}
              tone={worst?.avg_pct != null && worst.avg_pct < 45 ? "red" : "amber"} />
            <StatTile label="Subjects tracked" value={String(data.by_subject.length)}
              sub={`${data.trends.length} with a trajectory`} />
          </div>

          <div className="mb-6 grid gap-4 lg:grid-cols-2">
            <ChartCard title="Subject trajectories" className="lg:col-span-2"
              hint="Class average per test, over time. A subject with a single test has no trajectory and is left out.">
              {trendRows.length > 1 && trendKeys.length ? (
                <TrendLine rows={trendRows}
                  series={trendKeys.map((t, i) => ({
                    key: t.key, label: t.label, color: SERIES_COLORS[i % SERIES_COLORS.length],
                  }))}
                  yUnit="%" height={240} />
              ) : (
                <Empty>Not enough tests yet — a trajectory needs at least two per subject.</Empty>
              )}
            </ChartCard>

            <ChartCard title="Average by class" hint="Across every test in scope.">
              {classRows.length ? (
                <RowBars rows={classRows} dataKey="pct" unit="%" max={100}
                  height={Math.max(140, classRows.length * 26)}
                  colorFor={(r) => toneForPct(r.pct as number, { good: 65, fair: 45 })} />
              ) : <Empty>No class-scoped tests in scope.</Empty>}
            </ChartCard>

            <ChartCard title="Average by subject" hint="Across every class that sat it.">
              {subjectRows.length ? (
                <RowBars rows={subjectRows} dataKey="pct" unit="%" max={100}
                  height={Math.max(140, subjectRows.length * 26)}
                  colorFor={(r) => toneForPct(r.pct as number, { good: 65, fair: 45 })} />
              ) : <Empty>No subject-scoped tests in scope.</Empty>}
            </ChartCard>

            <ChartCard title="Score distribution" className="lg:col-span-2"
              hint="Every mark in scope. A long left tail is a different problem from a low average.">
              {distRows.some((r) => (r.students as number) > 0) ? (
                <ColumnChart rows={distRows} series={[{ key: "students", label: "Marks" }]} height={200} />
              ) : <Empty>No marks recorded yet.</Empty>}
            </ChartCard>
          </div>

          <Section title="Recent tests"
            hint="Participation is shown beside every average — an average over a third of the class is not a class average.">
            <ScrollX>
              <table className="w-full min-w-[680px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Test</th>
                    <th className="py-2 pr-3 font-medium">Type</th>
                    <th className="py-2 pr-3 font-medium">Class</th>
                    <th className="py-2 pr-3 font-medium">Subject</th>
                    <th className="py-2 pr-3 font-medium">Date</th>
                    <th className="py-2 pr-3 text-right font-medium">Average</th>
                    <th className="py-2 text-right font-medium">Sat it</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent.map((e) => (
                    <tr key={e.cycle_id} className="border-b border-border/60">
                      <td className="py-2 pr-3">
                        <a href={`/students/scores/exam/${e.cycle_id}`} className="hover:underline">{e.name}</a>
                      </td>
                      <td className="py-2 pr-3 text-muted-foreground">{label(e.type)}</td>
                      <td className="py-2 pr-3">{e.class_label ?? <StateChip>whole school</StateChip>}</td>
                      <td className="py-2 pr-3">{e.subject_name ?? "—"}</td>
                      <td className="py-2 pr-3 text-muted-foreground">{dayLabel(e.date)}</td>
                      <td className="py-2 pr-3 text-right">
                        {e.avg_pct != null
                          ? <Badge tone={e.avg_pct >= 65 ? "success" : e.avg_pct >= 45 ? "warning" : "danger"}>
                              {e.avg_pct}%
                            </Badge>
                          : <StateChip>not scored</StateChip>}
                      </td>
                      <td className="py-2 text-right tabular-nums text-muted-foreground">
                        {e.scored}/{e.roster}
                        {e.participation != null && e.participation < 0.8
                          ? <span className="ml-1 text-warning">·partial</span>
                          : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollX>
          </Section>
        </>
      )}
    </div>
  );
}

export default function DashboardExamsPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <ExamsInner />
    </AuthGuard>
  );
}
