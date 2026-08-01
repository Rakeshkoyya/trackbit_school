"use client";

// "X is away — here is what it breaks, and who can cover it" (DASH3 §4.3).
//
// The one screen where a staff absence becomes a decision instead of a fact. For
// each period the absent teacher was due to take, the candidates are ranked by
// who actually knows the subject — teaches it elsewhere > teaches this class >
// lightest load today — and **the reason is always shown**, because the rank is a
// suggestion and the admin is the one who knows that Priya is covering the trip.
//
// For an absent admin the blast radius is their work, not their periods, so their
// due/overdue tasks are listed with Reassign and Extend.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Check, RotateCcw, UserCheck } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import type { ImpactPeriod } from "@/lib/insights-types";

import { Empty } from "./shared";

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
            <li key={c.member_id} className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-sm">
                {c.name} <span className="text-xs text-muted-foreground">· {c.reason}</span>
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
  memberId, memberName, onClose,
}: {
  memberId: string | null;
  memberName?: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["insights", "impact", memberId],
    queryFn: () => insightsApi.staffImpact(memberId!),
    enabled: !!memberId,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["insights", "impact", memberId] });
    qc.invalidateQueries({ queryKey: ["insights", "staff"] });
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
              <Empty>No lessons on today’s timetable for them.</Empty>
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
