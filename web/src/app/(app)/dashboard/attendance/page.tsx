"use client";

// Attendance — students (DASH3 §4.1).
//
// Three layers, and the middle one is why the tab exists:
//   1. the shape — 14-day pulse, per-class today, and the period capture grid
//   2. the red list — students absent for every marked period of 3+ school days
//   3. the rail — remind the guardian, or put a follow-up on the class teacher
//
// The capture grid is the finding the percentages cannot give: it separates
// "attendance is bad" from "attendance was never taken". Staff live on their own
// tab (revision 2) — this page carries only a strip that links across.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, MessageSquare, UserPlus, Users } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  ChartCard, PulseArea, RowBars, StatTile, toneForPct, type ChartRow,
} from "@/components/charts";
import { PeriodHeatmap } from "@/components/insights/period-heatmap";
import {
  BoardSkeleton, Empty, RailButton, RedRow, Section, dayLabel,
} from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import type { AbsenceStreak } from "@/lib/insights-types";

function StreakList({ yearId }: { yearId: string | null }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["insights", "streaks", yearId],
    queryFn: () => insightsApi.streaks({ yearId: yearId ?? undefined }),
  });

  const run = useMutation({
    mutationFn: ({ kind, row }: { kind: "guardian_reminded" | "followup_assigned"; row: AbsenceStreak }) =>
      insightsApi.action(kind, {
        student_id: row.student_id,
        title: kind === "followup_assigned"
          ? `Call ${row.full_name}'s parent — absent ${row.streak} days`
          : undefined,
      }),
    onSuccess: (res) => {
      // `already_done` is the rail refusing to fire twice today, not a failure.
      if (res.already_done) toast.info(res.message);
      else toast.success(res.message);
      qc.invalidateQueries({ queryKey: ["insights", "streaks"] });
    },
    onError: (e) => showApiError(e, "Could not complete that"),
  });

  if (isLoading) return <div className="h-32 animate-pulse rounded-xl border border-border bg-card" />;
  if (!data?.rows.length) {
    return (
      <Empty>
        Nobody has missed {data?.min_days ?? 3} school days in a row — the list fills only when a
        student is absent for every marked period of consecutive school days.
      </Empty>
    );
  }

  return (
    <div className="space-y-2">
      {data.rows.map((r) => (
        <RedRow
          key={r.student_id}
          href={`/students/${r.student_id}`}
          title={<>{r.full_name} <span className="font-normal text-muted-foreground">· {r.class_label ?? "—"}</span></>}
          subtitle={
            <>
              {r.streak} school days absent
              {r.last_present ? ` · last seen ${dayLabel(r.last_present)}` : ""}
              {r.class_teacher_name ? ` · class teacher ${r.class_teacher_name}` : ""}
              {r.guardian_count === 0 ? " · no guardian on file" : ""}
            </>
          }
          meta={<Badge tone="danger">{r.streak}d</Badge>}
          actions={
            <>
              <RailButton
                label="Remind guardian" doneLabel="Reminded"
                done={r.reminded_today} pending={run.isPending}
                icon={r.reminded_today
                  ? <CheckCircle2 className="h-3.5 w-3.5" />
                  : <MessageSquare className="h-3.5 w-3.5" />}
                onClick={() => run.mutate({ kind: "guardian_reminded", row: r })}
              />
              <RailButton
                label="Assign follow-up" doneLabel="Assigned"
                done={r.followup_assigned_today} pending={run.isPending}
                icon={r.followup_assigned_today
                  ? <CheckCircle2 className="h-3.5 w-3.5" />
                  : <UserPlus className="h-3.5 w-3.5" />}
                onClick={() => run.mutate({ kind: "followup_assigned", row: r })}
              />
            </>
          }
        />
      ))}
    </div>
  );
}

function AttendanceInner() {
  const { yearId } = useYear();
  const { data, isLoading } = useQuery({
    queryKey: ["insights", "attendance", yearId],
    queryFn: () => insightsApi.attendance(yearId ?? undefined),
  });

  if (isLoading || !data) return <><PageHeader title="Attendance" subtitle="Who is here, and was it even taken?" /><BoardSkeleton /></>;

  const today = data.students.today;
  const trend = data.students.days.map((d) => d.present_pct);
  const pulseRows: ChartRow[] = data.students.days.map((d) => ({ x: dayLabel(d.date), pct: d.present_pct }));
  const classRows: ChartRow[] = data.students.classes_today
    .filter((c) => c.present_pct != null)
    .map((c) => ({ x: c.class_label, pct: c.present_pct }));
  const capturePct = data.capture.expected
    ? Math.round((data.capture.marked / data.capture.expected) * 100)
    : null;
  const staff = data.staff;

  return (
    <div>
      <PageHeader title="Attendance" subtitle="Who is here, and was it even taken?" />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Present today"
          value={today?.present_pct != null ? `${today.present_pct}%` : "—"}
          sub={today ? `${today.absent} absent · ${today.late} late` : "nothing marked yet"}
          tone={today?.present_pct == null ? "neutral"
            : today.present_pct >= 90 ? "green" : today.present_pct >= 80 ? "amber" : "red"}
          trend={trend}
        />
        <StatTile
          label="Periods captured"
          value={data.capture.expected ? `${data.capture.marked}/${data.capture.expected}` : "—"}
          sub={capturePct != null ? `${capturePct}% of today's timetable` : "no timetable for today"}
          tone={capturePct == null ? "neutral" : capturePct >= 90 ? "green" : capturePct >= 50 ? "amber" : "red"}
        />
        <StatTile
          label="Absent 3+ days"
          value={String(data.streak_count)}
          sub={data.streak_count ? "each needs a phone call" : "nobody on the red list"}
          tone={data.streak_count ? "red" : "green"}
        />
        {/* "Not marked" is information, never a failure — an admin who marks
            staff at 10am must not see a red tile every morning. */}
        <StatTile
          label="Staff in today"
          value={staff.marked ? `${staff.present}/${staff.total}` : "not marked"}
          sub={staff.marked
            ? `${staff.absent} away${staff.on_leave ? ` · ${staff.on_leave} on leave` : ""}`
            : "nobody has taken staff attendance"}
          tone={!staff.marked ? "neutral" : staff.absent > 2 ? "red" : staff.absent ? "amber" : "green"}
          href="/dashboard/staff"
        />
      </div>

      <Section
        title="Period capture, today"
        hint="Which periods were actually marked. An empty cell in a scheduled period is a gap in the record, not a class with nobody in it."
      >
        <div className="rounded-xl border border-border bg-card p-4">
          <PeriodHeatmap grid={data.capture} />
        </div>
      </Section>

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <ChartCard
          title={`Present, last ${data.students.window_days} days`}
          hint="Share of student-periods present. Only days with marked periods appear."
          className="lg:col-span-2"
        >
          {pulseRows.length > 1 ? (
            <PulseArea rows={pulseRows} dataKey="pct" label="Present" yUnit="%" yDomain={[0, 100]} height={170} />
          ) : (
            <Empty>Not enough marked days yet — the line starts once two days are captured.</Empty>
          )}
        </ChartCard>

        <ChartCard title="By class, today" hint="Present share from today's marked periods.">
          {classRows.length ? (
            <RowBars rows={classRows} dataKey="pct" unit="%" max={100}
              height={Math.max(140, classRows.length * 30)}
              colorFor={(r) => toneForPct(r.pct as number, { good: 90, fair: 80 })} />
          ) : (
            <Empty>No attendance marked today yet.</Empty>
          )}
        </ChartCard>

        <ChartCard title="Staff today" hint="Marked by the admin on the Staff screen.">
          {staff.marked ? (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-4 text-sm">
                <span><span className="text-lg font-semibold tabular-nums">{staff.present}</span> <span className="text-muted-foreground">in</span></span>
                <span><span className="text-lg font-semibold tabular-nums text-danger">{staff.absent}</span> <span className="text-muted-foreground">away</span></span>
                <span><span className="text-lg font-semibold tabular-nums text-warning">{staff.on_leave}</span> <span className="text-muted-foreground">on leave</span></span>
              </div>
              {staff.absentees.length ? (
                <ul className="space-y-1 text-sm">
                  {staff.absentees.slice(0, 5).map((a) => (
                    <li key={a.member_id} className="flex items-center justify-between gap-2">
                      <span className="truncate">{a.name}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {a.periods_due
                          ? `${a.periods_due - a.periods_covered} of ${a.periods_due} periods uncovered`
                          : a.reason ?? "no periods today"}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
              <Link href="/dashboard/staff" className="inline-flex items-center gap-1 text-xs text-muted-foreground underline">
                <Users className="h-3.5 w-3.5" /> Open the staff board
              </Link>
            </div>
          ) : (
            <Empty>Staff attendance has not been taken today — that is a gap in the record, not a full house.</Empty>
          )}
        </ChartCard>
      </div>

      <Section
        title="Absent 3+ school days"
        hint="Absent in EVERY marked period of consecutive school days. Days the class marked nothing are skipped, not counted as present."
      >
        <StreakList yearId={yearId} />
      </Section>
    </div>
  );
}

export default function DashboardAttendancePage() {
  return (
    <AuthGuard allow={["admin"]}>
      <AttendanceInner />
    </AuthGuard>
  );
}
