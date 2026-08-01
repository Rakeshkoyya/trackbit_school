"use client";

// Staff — presence · leave · load · cover (DASH3 §4.3, revision 2).
//
// This tab is the one that changed most once SF-1 shipped. It is the *analytical
// and decision* surface: who is free right now, who is away and what that breaks,
// what is waiting for approval, and whether the teaching load is balanced. The
// operational screens stay where they are — `/staff` marks attendance,
// `/staff/leave` decides leave, `/staff/today` is the period grid — and this
// links to them rather than re-rendering them.
//
// One rule the copy holds throughout: **"not marked yet" is information, not a
// failure.** An admin who takes staff attendance at 10am must not open a red
// board every morning.

import { useQuery } from "@tanstack/react-query";
import { CalendarCheck2, ExternalLink, UserX } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ChartCard, RowBars, StatTile, STATUS_COLOR, type ChartRow } from "@/components/charts";
import { CoverSheet } from "@/components/insights/cover-sheet";
import { NowBoard } from "@/components/insights/now-board";
import {
  BoardSkeleton, Empty, RedRow, ScrollX, Section, StateChip, dayLabel,
} from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { insightsApi } from "@/lib/insights-api";
import type { LoadStripCell } from "@/lib/insights-types";
import { cn } from "@/lib/utils";

const STRIP: Record<LoadStripCell["kind"], string> = {
  class: "bg-[color:var(--chart-green)]/70",
  substituting: "bg-[color:var(--chart-amber)]/70",
  work: "bg-muted-foreground/30",
  free: "bg-muted",
  absent: "bg-danger/25",
};

function DayStrip({ cells }: { cells: LoadStripCell[] }) {
  return (
    <span className="flex gap-0.5">
      {cells.map((c) => (
        <span key={c.period_no} title={`Period ${c.period_no}: ${c.label ?? c.kind}`}
          className={cn("h-3.5 w-3.5 rounded-[2px]", STRIP[c.kind])} />
      ))}
    </span>
  );
}

function StaffInner() {
  const [coverFor, setCoverFor] = useState<{ id: string; name: string } | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["insights", "staff"],
    queryFn: () => insightsApi.staff(),
    // The live board moves with the bell; a stale "period 4" is worse than a
    // spinner, so this refetches while the tab is open.
    refetchInterval: 120_000,
  });

  if (isLoading || !data) {
    return <><PageHeader title="Staff" subtitle="Who is in, who is free, and what an absence breaks." /><BoardSkeleton /></>;
  }

  const { presence, leave, week } = data;
  const loadRows: ChartRow[] = week.teachers
    .filter((t) => t.teaching_periods > 0)
    .slice(0, 14)
    .map((t) => ({ x: t.name, periods: t.teaching_periods }));
  const bucketRows: ChartRow[] = week.buckets.map((b) => ({ x: b.label, periods: b.periods }));

  return (
    <div>
      <PageHeader title="Staff" subtitle="Who is in, who is free, and what an absence breaks." />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="In today"
          value={presence.marked ? `${presence.present}/${presence.total}` : "not marked"}
          sub={presence.marked
            ? `${presence.absent} away${presence.on_leave ? ` · ${presence.on_leave} on leave` : ""}`
            : "nobody has taken staff attendance"}
          tone={!presence.marked ? "neutral" : presence.absent > 2 ? "red" : presence.absent ? "amber" : "green"}
          href="/staff"
        />
        <StatTile
          label="Periods uncovered"
          value={String(data.uncovered_periods)}
          sub={data.uncovered_periods ? "an absent teacher's classes" : "every absence is covered"}
          tone={data.uncovered_periods ? "red" : "green"}
        />
        <StatTile
          label="Leave waiting"
          value={String(leave.pending)}
          sub={leave.pending ? "needs a decision" : `${leave.on_leave_today} on leave today`}
          tone={leave.pending ? "amber" : "green"}
          href="/staff/leave"
        />
        {/* StatTile truncates its sub to one line — keep it short enough to read. */}
        <StatTile
          label="Free periods unlogged"
          value={String(week.unfilled_free_periods)}
          sub="today, no timesheet entry"
          tone={week.unfilled_free_periods > 8 ? "amber" : "neutral"}
          href="/staff/today"
        />
      </div>

      <Section title="Right now"
        hint="The timetable says who is teaching; the timesheet says what the rest are doing.">
        <NowBoard board={data.now} />
      </Section>

      {presence.absentees.length ? (
        <Section title="Away today"
          hint="Open one to see the periods it breaks and who is genuinely free to cover them.">
          <div className="space-y-2">
            {presence.absentees.map((a) => {
              const uncovered = Math.max(0, a.periods_due - a.periods_covered);
              return (
                <RedRow
                  key={a.member_id}
                  tone={uncovered ? "red" : "amber"}
                  title={<>{a.name} <span className="font-normal text-muted-foreground">· {a.role}</span></>}
                  subtitle={
                    <>
                      {a.on_leave ? "On approved leave" : "Marked away"}
                      {a.reason ? ` · ${a.reason}` : ""}
                      {a.periods_due
                        ? ` · ${a.periods_due} period${a.periods_due === 1 ? "" : "s"} today`
                        : " · no lessons today"}
                    </>
                  }
                  meta={a.periods_due
                    ? <Badge tone={uncovered ? "danger" : "success"}>
                        {uncovered ? `${uncovered} uncovered` : "all covered"}
                      </Badge>
                    : null}
                  actions={
                    <Button size="sm" variant="outline"
                      onClick={() => setCoverFor({ id: a.member_id, name: a.name })}>
                      <UserX className="h-3.5 w-3.5" /> Arrange cover
                    </Button>
                  }
                />
              );
            })}
          </div>
        </Section>
      ) : null}

      <Section
        title="Leave"
        hint={`School allowance: ${leave.allowed_per_year} days a year, ${leave.allowed_per_month} a month. Over-policy applications are flagged, never blocked.`}
        action={
          <Link href="/staff/leave" className={buttonVariants({ variant: "outline", size: "sm" })}>
            <ExternalLink className="h-3.5 w-3.5" /> Decide on /staff/leave
          </Link>
        }
      >
        {leave.queue.length ? (
          <div className="space-y-2">
            {leave.queue.map((r) => (
              <RedRow
                key={r.request_id}
                tone={r.warnings.length ? "amber" : "neutral"}
                href="/staff/leave"
                title={<>{r.member_name} <span className="font-normal text-muted-foreground">· {r.days} day{r.days === 1 ? "" : "s"}</span></>}
                subtitle={
                  <>
                    {dayLabel(r.start_date)}
                    {r.start_date !== r.end_date ? ` – ${dayLabel(r.end_date)}` : ""} · {r.reason}
                  </>
                }
                meta={r.warnings.length
                  ? <span className="text-warning">{r.warnings[0]}</span>
                  : <CalendarCheck2 className="h-4 w-4 text-muted-foreground" />}
              />
            ))}
          </div>
        ) : (
          <Empty>
            Nothing waiting. {leave.on_leave_today} on leave today · {leave.approved_days_this_month} day
            {leave.approved_days_this_month === 1 ? "" : "s"} approved this month.
          </Empty>
        )}
      </Section>

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Teaching periods this week"
          hint={`Against an org mean of ${week.mean_teaching}, computed over people who teach at all.`}
        >
          {loadRows.length ? (
            <RowBars rows={loadRows} dataKey="periods" max={undefined}
              height={Math.max(140, loadRows.length * 26)}
              colorFor={(r) => {
                const t = week.teachers.find((x) => x.name === r.x);
                return t?.load_flag === "over" ? STATUS_COLOR.red
                  : t?.load_flag === "under" ? STATUS_COLOR.amber : STATUS_COLOR.green;
              }} />
          ) : (
            <Empty>No timetable slots this week — the grid has not been set.</Empty>
          )}
        </ChartCard>

        <ChartCard title="What non-teaching periods went on"
          hint="From the timesheet, this week. A school with nothing here has not adopted it yet.">
          {bucketRows.length ? (
            <RowBars rows={bucketRows} dataKey="periods"
              height={Math.max(140, bucketRows.length * 26)} />
          ) : (
            <Empty>No timesheet entries this week.</Empty>
          )}
        </ChartCard>
      </div>

      <Section title="The day, teacher by teacher"
        hint="Each cell is one period: teaching · covering · other work · free · away.">
        <ScrollX>
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Teacher</th>
                <th className="py-2 pr-3 font-medium">Today</th>
                <th className="py-2 pr-3 text-right font-medium">Teaching</th>
                <th className="py-2 pr-3 text-right font-medium">Other work</th>
                <th className="py-2 text-right font-medium">Load</th>
              </tr>
            </thead>
            <tbody>
              {week.teachers.map((t) => (
                <tr key={t.member_id} className="border-b border-border/60">
                  <td className="py-2 pr-3">
                    <span className="block truncate">{t.name}</span>
                    <span className="block text-xs text-muted-foreground">{t.role}</span>
                  </td>
                  <td className="py-2 pr-3"><DayStrip cells={t.today} /></td>
                  <td className="py-2 pr-3 text-right tabular-nums">{t.teaching_periods}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{t.work_periods}</td>
                  <td className="py-2 text-right">
                    {t.teaching_periods === 0 ? (
                      <StateChip>no classes</StateChip>
                    ) : t.load_flag === "over" ? (
                      <Badge tone="danger">+{t.delta_vs_mean}</Badge>
                    ) : t.load_flag === "under" ? (
                      <Badge tone="warning">{t.delta_vs_mean}</Badge>
                    ) : (
                      <Badge tone="success">balanced</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollX>
      </Section>

      <CoverSheet memberId={coverFor?.id ?? null} memberName={coverFor?.name}
        onClose={() => setCoverFor(null)} />
    </div>
  );
}

export default function DashboardStaffPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <StaffInner />
    </AuthGuard>
  );
}
