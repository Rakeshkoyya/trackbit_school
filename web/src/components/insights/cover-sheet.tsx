"use client";

// "X is away — here is what it breaks, and who can cover it" (DASH3 §4.3).
//
// The one screen where a staff absence becomes a decision instead of a fact. For
// each period the absent teacher was due to take, the candidates are ranked by
// who actually knows the subject, and **the reason is always shown**, because the
// rank is a suggestion and the admin is the one who knows that Priya is covering
// the trip.
//
// V1-4 (`D-26`/`D-29`/`S-78`) made each row a comparison of two things the admin
// could not see before:
//   * **what the class gains** — the next planned topic, and whether this person
//     can actually teach it. That is the difference between a real lesson and a
//     supervised study period, and it is the strongest reason to prefer someone.
//   * **what she gives up** — the work she already recorded for that period
//     (`S-74`), and a warning if she is behind in her own subjects (`S-79b`).
// Both are shown on a still-assignable row. Neither is a block: covering a class
// beats checking notebooks on most mornings, and the admin knows which.
//
// `D-27`: it also opens for a FUTURE date, from an approved leave, so cover is
// arranged when the leave is approved rather than on the morning it starts.
//
// For an absent admin the blast radius is their work, not their periods, so their
// due/overdue tasks are listed with Reassign and Extend.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  AlertTriangle, BookOpen, CalendarClock, Check, RotateCcw, UserCheck,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import type { ImpactPeriod } from "@/lib/insights-types";

import { cn } from "@/lib/utils";

import { Empty } from "./shared";

/**
 * Every day of an absence, as ISO dates.
 *
 * A leave is a span; a marked absence is one day. Capped at two weeks so a long
 * medical leave does not render sixty buttons — cover past that is planned on
 * the leave screen, not from a sheet.
 */
function spanDays(start?: string, end?: string, fallback?: string): string[] {
  if (!start || !end) return fallback ? [fallback] : [];
  const out: string[] = [];
  const d = new Date(`${start}T00:00:00`);
  const last = new Date(`${end}T00:00:00`);
  while (d <= last && out.length < 14) {
    // Formatted from the LOCAL parts, never `toISOString()`. The Date is local
    // midnight, and in any timezone east of UTC that serialises to the previous
    // day — which silently opened cover on the wrong date for every school in
    // India.
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
      + `-${String(d.getDate()).padStart(2, "0")}`);
    d.setDate(d.getDate() + 1);
  }
  return out;
}

function PeriodBlock({
  period, memberId, date, onDone, busy,
}: {
  period: ImpactPeriod;
  memberId: string;
  date: string;
  onDone: () => void;
  busy: boolean;
}) {
  const assign = useMutation({
    mutationFn: (substituteId: string) =>
      insightsApi.action("substitute_assigned", {
        substitution: {
          date,
          class_id: period.class_id,
          period_no: period.period_no,
          class_subject_id: period.class_subject_id,
          substitute_member_id: substituteId,
          absent_member_id: memberId,
        },
      }),
    onSuccess: (res) => { toast.success(res.message); onDone(); },
    onError: (e) => showApiError(e, "Could not assign cover"),
  });
  const cancel = useMutation({
    mutationFn: (id: string) => insightsApi.cancelSubstitution(id),
    onSuccess: () => { toast.success("Cover cancelled"); onDone(); },
    onError: (e) => showApiError(e, "Could not cancel"),
  });

  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">
          Period {period.period_no}
          {period.start ? <span className="font-normal text-muted-foreground"> · {period.start}–{period.end}</span> : null}
        </span>
        <span className="text-sm text-muted-foreground">
          {period.class_label} {period.subject_name ?? ""}
        </span>
        {period.covered_by_name ? (
          <Badge tone="success" className="ml-auto">
            <Check className="h-3 w-3" /> {period.covered_by_name}
          </Badge>
        ) : (
          <Badge tone="danger" className="ml-auto">uncovered</Badge>
        )}
      </div>

      {/* D-29 — what the class gains. Without it every cover reads the same,
          and a study period looks as good as a lesson. */}
      {period.next_topic ? (
        <p className="mt-1 flex items-start gap-1.5 text-xs text-muted-foreground">
          <BookOpen className="mt-0.5 h-3 w-3 shrink-0" />
          <span>Next planned topic: <span className="text-foreground">{period.next_topic}</span></span>
        </p>
      ) : null}

      {period.substitution_id ? (
        <div className="mt-2">
          <Button size="sm" variant="ghost" disabled={cancel.isPending}
            onClick={() => cancel.mutate(period.substitution_id!)}>
            <RotateCcw className="h-3.5 w-3.5" /> Cancel cover
          </Button>
        </div>
      ) : period.candidates.length ? (
        <ul className="mt-2 space-y-1.5">
          {period.candidates.map((c) => (
            <li key={c.member_id} className="flex items-start gap-2">
              <span className="min-w-0 flex-1 text-sm">
                <span className="flex flex-wrap items-center gap-1.5">
                  {c.name}
                  {c.can_teach_next_topic ? (
                    <Badge tone="success">can teach it</Badge>
                  ) : null}
                </span>
                <span className="block text-xs text-muted-foreground">{c.reason}</span>
                {/* S-79(b) — don't rob Peter to pay Paul. A warning, never a block. */}
                {c.behind_note ? (
                  <span className="mt-0.5 flex items-center gap-1 text-xs text-warning">
                    <AlertTriangle className="h-3 w-3 shrink-0" /> {c.behind_note}
                  </span>
                ) : null}
              </span>
              <Button size="sm" variant="outline" disabled={busy || assign.isPending}
                onClick={() => assign.mutate(c.member_id)}>
                <UserCheck className="h-3.5 w-3.5" /> Assign
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">
          Nobody is free this period. The class will need merging or a study period.
        </p>
      )}
    </div>
  );
}

export function CoverSheet({
  memberId, memberName, onDate, leaveStart, leaveEnd, onClose,
}: {
  memberId: string | null;
  memberName?: string;
  /** D-27 — a future day from an approved leave. Omitted = today. */
  onDate?: string;
  /** V1-14: the whole span an approved leave covers. Cover is arranged for the
   *  absence, not for one day of it — a teacher away Mon–Wed leaves three days
   *  of periods, and a sheet pinned to "today" showed *"no lessons today"* for
   *  a person with nine periods to hand out. */
  leaveStart?: string;
  leaveEnd?: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const days = useMemo(
    () => spanDays(leaveStart, leaveEnd, onDate),
    [leaveStart, leaveEnd, onDate]);
  const [day, setDay] = useState<string | undefined>(onDate);

  // The picked day resets whenever the sheet opens on a different person, so it
  // can never show one teacher's Tuesday under another's name.
  const active = day && days.includes(day) ? day : days[0] ?? onDate;

  const { data, isLoading } = useQuery({
    queryKey: ["insights", "impact", memberId, active ?? "today"],
    queryFn: () => insightsApi.staffImpact(memberId!, active),
    enabled: !!memberId,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["insights", "impact", memberId] });
    qc.invalidateQueries({ queryKey: ["insights", "staff"] });
    qc.invalidateQueries({ queryKey: ["leave"] });
  };

  const taskAction = useMutation({
    mutationFn: ({ kind, taskId }: { kind: "task_extended"; taskId: string }) =>
      insightsApi.action(kind, { task_id: taskId }),
    onSuccess: (res) => { toast.success(res.message); refresh(); },
    onError: (e) => showApiError(e, "Could not update the task"),
  });

  return (
    <Sheet open={!!memberId} onOpenChange={(v) => { if (!v) onClose(); }}
      title={memberName ? `${memberName} is away` : "Away today"}>
      {isLoading || !data ? (
        <div className="h-40 animate-pulse rounded-lg bg-muted/60" />
      ) : (
        <div className="space-y-4">
          {/* Every day of the absence, so the periods on Tuesday are one tap
              away from the periods on Monday. One day = just the date. */}
          {days.length > 1 ? (
            <div className="flex flex-wrap gap-1.5">
              {days.map((d) => (
                <button key={d} type="button" onClick={() => setDay(d)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 font-mono text-[11px] tabular-nums",
                    d === active
                      ? "border-primary bg-primary/10 font-medium text-foreground"
                      : "border-border text-muted-foreground hover:bg-muted")}>
                  {new Date(`${d}T00:00:00`).toLocaleDateString(undefined, {
                    weekday: "short", day: "numeric", month: "short" })}
                </button>
              ))}
            </div>
          ) : (
            <p className="font-mono text-[11px] text-muted-foreground">
              {new Date(`${data.date}T00:00:00`).toLocaleDateString(undefined, {
                weekday: "long", day: "numeric", month: "long" })}
            </p>
          )}
          {data.reason ? (
            <p className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
              {data.on_leave ? "On approved leave — " : ""}{data.reason}
            </p>
          ) : null}

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Periods to cover
            </p>
            {data.periods.length ? (
              <div className="space-y-2">
                {data.periods.map((p) => (
                  <PeriodBlock key={`${p.class_id}-${p.period_no}`} period={p}
                    memberId={data.member_id} date={data.date}
                    onDone={refresh} busy={taskAction.isPending} />
                ))}
              </div>
            ) : (
              <Empty>
                Nothing on their timetable for{" "}
                {new Date(`${data.date}T00:00:00`).toLocaleDateString(undefined, {
                  weekday: "long", day: "numeric", month: "short" })}
                {days.length > 1 ? " — try another day of the leave." : "."}
              </Empty>
            )}
          </div>

          {data.tasks.length ? (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Work due today
              </p>
              <div className="space-y-2">
                {data.tasks.map((t) => (
                  <div key={t.task_id} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm">{t.title}</span>
                      <span className="block text-xs text-muted-foreground">
                        {t.board_name}
                        {t.days_overdue ? ` · ${t.days_overdue}d overdue` : " · due today"}
                      </span>
                    </span>
                    {t.is_critical ? <Badge tone="danger">critical</Badge> : null}
                    <Button size="sm" variant="outline" disabled={taskAction.isPending}
                      onClick={() => taskAction.mutate({ kind: "task_extended", taskId: t.task_id })}>
                      <CalendarClock className="h-3.5 w-3.5" /> Extend
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </Sheet>
  );
}
