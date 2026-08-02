"use client";

// Tasks — assigned work, and the duties period capture implies (DASH3 §4.5).
//
// Two halves that look alike and are not.
//
// The top half is the task module rolled up, with a rail on every overdue row:
// extend the date, or nudge whoever it is waiting on.
//
// The bottom half is the observation that My Day *is* a task list. Attendance
// marked · lesson logged · homework set · checks confirmed, against the periods
// each teacher was **actually due to teach** — a teacher whose classes were all
// cancelled cannot read as 0%, and a period covered by a substitute counts toward
// the substitute. It is deliberately read-only: the fix for an unlogged period is
// the teacher opening My Day, not the admin filing a task about it.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlarmClock, CalendarClock } from "lucide-react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ChartCard, RowBars, StatTile, STATUS_COLOR, type ChartRow } from "@/components/charts";
import { BoardSkeleton, Empty, RedRow, ScrollX, Section, StateChip, dayLabel } from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import type { ActionKind } from "@/lib/insights-types";

function DutyBar({ label, done, total }: { label: string; done: number; total: number }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <span className="inline-flex items-center gap-1.5" title={`${label}: ${done}/${total}`}>
      <span className="h-1.5 w-10 overflow-hidden rounded-full bg-muted">
        <span className="block h-full rounded-full"
          style={{
            width: `${pct}%`,
            background: pct >= 80 ? STATUS_COLOR.green : pct >= 50 ? STATUS_COLOR.amber : STATUS_COLOR.red,
          }} />
      </span>
      <span className="text-xs tabular-nums text-muted-foreground">{done}/{total}</span>
    </span>
  );
}

function TasksInner() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["insights", "tasks"],
    queryFn: () => insightsApi.tasks(),
  });

  const run = useMutation({
    mutationFn: ({ kind, taskId, userId }: { kind: ActionKind; taskId?: string; userId?: string }) =>
      insightsApi.action(kind, { task_id: taskId, user_id: userId }),
    onSuccess: (res) => {
      if (res.already_done) toast.info(res.message);
      else toast.success(res.message);
      qc.invalidateQueries({ queryKey: ["insights", "tasks"] });
    },
    onError: (e) => showApiError(e, "Could not complete that"),
  });

  if (isLoading || !data) {
    return <><PageHeader title="Tasks" subtitle="What is waiting, and who it is waiting on." /><BoardSkeleton /></>;
  }

  const boardRows: ChartRow[] = data.by_board.slice(0, 12).map((b) => ({ x: b.label, open: b.open }));
  const assigneeRows: ChartRow[] = data.by_assignee.slice(0, 12).map((a) => ({ x: a.label, open: a.open }));

  return (
    <div>
      <PageHeader title="Tasks" subtitle="What is waiting, and who it is waiting on." />

      {/* §7: nine overdue across nine people is a busy week; nine with one
          person is a conversation. The sentence names which. */}
      {data.headline ? <p className="mb-5 text-base">{data.headline}</p> : null}

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Open" value={String(data.open)}
          sub={data.unassigned ? `${data.unassigned} unassigned` : "all assigned"}
          tone={data.unassigned ? "amber" : "neutral"} />
        <StatTile label="Overdue" value={String(data.overdue)}
          sub={data.critical_overdue ? `${data.critical_overdue} critical` : "nothing critical"}
          tone={data.critical_overdue ? "red" : data.overdue ? "amber" : "green"} />
        <StatTile label={`Completed (${data.window_days}d)`} value={String(data.completed_window)}
          sub="closed in the window" tone="green"
          trend={data.daily.map((d) => d.completed)} />
        <StatTile label="Daily duties"
          value={data.duty_completion != null ? `${Math.round(data.duty_completion * 100)}%` : "—"}
          sub="attendance · log · homework · checks"
          tone={data.duty_completion == null ? "neutral"
            : data.duty_completion >= 0.8 ? "green" : data.duty_completion >= 0.5 ? "amber" : "red"} />
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <ChartCard title="Open work by board" hint="Where the backlog is sitting.">
          {boardRows.length ? (
            <RowBars rows={boardRows} dataKey="open" height={Math.max(140, boardRows.length * 26)} />
          ) : <Empty>No open tasks.</Empty>}
        </ChartCard>
        <ChartCard title="Open work by person" hint="Who is carrying it.">
          {assigneeRows.length ? (
            <RowBars rows={assigneeRows} dataKey="open" height={Math.max(140, assigneeRows.length * 26)} />
          ) : <Empty>No open tasks.</Empty>}
        </ChartCard>
      </div>

      <Section title="Overdue" hint="Criticals first. Extend the date, or nudge the person it is waiting on.">
        {data.red_rows.length ? (
          <div className="space-y-2">
            {data.red_rows.map((t) => (
              <RedRow
                key={t.task_id}
                href={`/task/${t.task_id}`}
                tone={t.is_critical ? "red" : "amber"}
                title={t.title}
                subtitle={
                  <>
                    {t.board_name} · {t.assignee_name ?? "unassigned"}
                    {t.due_at ? ` · due ${dayLabel(t.due_at.slice(0, 10))}` : ""}
                  </>
                }
                meta={<Badge tone={t.is_critical ? "danger" : "warning"}>{t.days_overdue}d late</Badge>}
                actions={
                  <>
                    <Button size="sm" variant="outline" disabled={run.isPending}
                      onClick={() => run.mutate({ kind: "task_extended", taskId: t.task_id })}>
                      <CalendarClock className="h-3.5 w-3.5" /> Extend
                    </Button>
                    {t.assignee_user_id ? (
                      <Button size="sm" variant="outline" disabled={run.isPending}
                        onClick={() => run.mutate({ kind: "nudged", userId: t.assignee_user_id! })}>
                        <AlarmClock className="h-3.5 w-3.5" /> Nudge
                      </Button>
                    ) : null}
                  </>
                }
              />
            ))}
          </div>
        ) : (
          <Empty>Nothing is overdue.</Empty>
        )}
      </Section>

      <Section title="Today's classroom duties"
        hint="Against the periods each teacher was actually due to teach. Read-only — the fix is the teacher opening My Day.">
        {data.duties.length ? (
          <ScrollX>
            <table className="w-full min-w-[620px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Teacher</th>
                  <th className="py-2 pr-3 font-medium">Attendance</th>
                  <th className="py-2 pr-3 font-medium">Lesson log</th>
                  <th className="py-2 pr-3 font-medium">Homework</th>
                  <th className="py-2 pr-3 font-medium">Checks</th>
                  <th className="py-2 text-right font-medium">Overall</th>
                </tr>
              </thead>
              <tbody>
                {data.duties.map((d) => (
                  <tr key={d.member_id} className="border-b border-border/60">
                    <td className="py-2 pr-3">
                      <span className="block truncate">{d.name}</span>
                      <span className="block text-xs text-muted-foreground">
                        {d.due_periods} period{d.due_periods === 1 ? "" : "s"} due
                      </span>
                    </td>
                    <td className="py-2 pr-3"><DutyBar label="Attendance" done={d.attendance_marked} total={d.due_periods} /></td>
                    <td className="py-2 pr-3"><DutyBar label="Logged" done={d.logged} total={d.due_periods} /></td>
                    <td className="py-2 pr-3 tabular-nums text-muted-foreground">{d.homework_set}</td>
                    <td className="py-2 pr-3 tabular-nums text-muted-foreground">{d.checks_confirmed}</td>
                    <td className="py-2 text-right">
                      {d.completion == null ? <StateChip>nothing due</StateChip>
                        : <Badge tone={d.completion >= 0.8 ? "success" : d.completion >= 0.5 ? "warning" : "danger"}>
                            {Math.round(d.completion * 100)}%
                          </Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollX>
        ) : (
          <Empty>No lessons scheduled today — nothing was due, so there is nothing to score.</Empty>
        )}
      </Section>
    </div>
  );
}

export default function DashboardTasksPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <TasksInner />
    </AuthGuard>
  );
}
