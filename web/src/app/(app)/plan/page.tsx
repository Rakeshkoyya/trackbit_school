"use client";

/**
 * Plan → Year (V2-P10).
 *
 * The wizard drew the year on a calendar; the moment setup ended the admin lost it
 * and got a text list back. This is the same artifact, permanently: drag across days
 * to add a holiday or an exam, watch teaching days recompute, and tie each exam to
 * the chapters it examines.
 *
 * That last control is what lets the planner say the sentence it exists for —
 * "Chapter 5 lands after the exam that examines it" — so it belongs on the screen
 * where exams live, not only inside a one-time wizard.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { CalendarDays, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { YearSwitcher } from "@/components/school/year-switcher";
import { ExamPortions } from "@/components/wizard/exam-portions";
import {
  CalendarLegend,
  YearCalendar,
  type PaintKind,
  type PaintedRange,
} from "@/components/wizard/year-calendar";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { CalendarEventType } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const KINDS: { kind: PaintKind; label: string }[] = [
  { kind: "exam_block", label: "Exam" },
  { kind: "holiday", label: "Holiday" },
  { kind: "celebration", label: "Celebration" },
  { kind: "event", label: "Event" },
];

const fmt = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

function PlanYearInner() {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin";
  const { yearId } = useYear();
  const qc = useQueryClient();

  const [kind, setKind] = useState<PaintKind>("holiday");
  const [title, setTitle] = useState("Holiday");

  const { data: summary } = useQuery({
    queryKey: ["calendar", yearId],
    queryFn: () => schoolApi.calendarSummary(yearId!),
    enabled: !!yearId,
  });
  const { data: classes } = useQuery({
    queryKey: ["classes", yearId],
    queryFn: () => schoolApi.classes(yearId!),
    enabled: !!yearId,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["calendar", yearId] });
    qc.invalidateQueries({ queryKey: ["school-overview"] });
  };

  const create = useMutation({
    mutationFn: (r: { start: string; end: string }) =>
      schoolApi.createEvents([
        {
          academic_year_id: yearId!,
          type: kind as CalendarEventType,
          title: title.trim() || KINDS.find((k) => k.kind === kind)!.label,
          start_date: r.start,
          end_date: r.end,
        },
      ]),
    onSuccess: () => {
      invalidate();
      toast.success("Added to the calendar");
    },
    onError: (e) => showApiError(e, "Could not add that"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteEvent(id),
    onSuccess: () => {
      invalidate();
      toast.success("Removed");
    },
    onError: (e) => showApiError(e, "Could not remove that"),
  });

  if (!yearId || !summary) {
    return <PageHeader title="Academic year" subtitle="Create a year in Setup to begin." />;
  }

  const ranges: PaintedRange[] = summary.events.map((e) => ({
    start: e.start_date,
    end: e.end_date,
    kind: e.type as PaintKind,
    title: e.title,
  }));
  const exams = summary.events.filter((e) => e.type === "exam_block");

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <PageHeader
          title="Academic year"
          subtitle={`${fmt(summary.start_date)} → ${fmt(summary.end_date)}`}
        />
        <div className="flex items-center gap-2">
          <Badge tone="primary">
            <CalendarDays className="h-3 w-3" /> {summary.teaching_days} teaching days
          </Badge>
          <YearSwitcher />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
        <div className="space-y-4">
          {canEdit ? (
            <div className="space-y-3 rounded-xl border border-border bg-card p-4">
              <div>
                <Label>What are you marking?</Label>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {KINDS.map((k) => (
                    <button
                      key={k.kind}
                      type="button"
                      onClick={() => {
                        setKind(k.kind);
                        setTitle(k.label);
                      }}
                      className={cn(
                        "rounded-full border px-3 py-1.5 text-xs transition-colors",
                        kind === k.kind
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-card hover:bg-muted",
                      )}
                    >
                      {k.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <Label htmlFor="etitle">Call it</Label>
                <Input id="etitle" value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <p className="text-xs text-muted-foreground">
                Drag across the calendar to mark it. Teaching days recompute as you go, and every
                plan re-forecasts against them.
              </p>
            </div>
          ) : null}

          {canEdit ? <ExamPortions exams={exams} classes={classes ?? []} /> : null}

          <div>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {summary.events.length} entries
            </h2>
            <div className="max-h-96 space-y-1.5 overflow-auto pr-1">
              <AnimatePresence initial={false}>
                {summary.events.map((e) => (
                  <motion.div
                    key={e.id}
                    layout
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 6 }}
                    className="group flex items-center justify-between rounded-lg border border-border bg-card px-3 py-1.5 text-sm"
                  >
                    <span className="min-w-0 truncate">
                      <span className="font-medium">{e.title}</span>{" "}
                      <span className="text-xs text-muted-foreground">
                        {e.start_date === e.end_date
                          ? fmt(e.start_date)
                          : `${fmt(e.start_date)} → ${fmt(e.end_date)}`}
                        {e.blocks_periods?.length
                          ? ` · periods ${e.blocks_periods.join(", ")}`
                          : ""}
                      </span>
                    </span>
                    {canEdit ? (
                      <button
                        type="button"
                        aria-label={`Remove ${e.title}`}
                        onClick={() => remove.mutate(e.id)}
                        className="text-muted-foreground opacity-0 group-hover:opacity-100"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    ) : null}
                  </motion.div>
                ))}
              </AnimatePresence>
              {!summary.events.length ? (
                <p className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                  Nothing marked yet.
                </p>
              ) : null}
            </div>
          </div>
        </div>

        <div className="min-w-0">
          <div className="mb-3">
            <CalendarLegend />
          </div>
          <YearCalendar
            startDate={summary.start_date}
            endDate={summary.end_date}
            ranges={ranges}
            paintable={canEdit}
            workingWeekdays={summary.working_weekdays}
            onPaint={(start, end) => create.mutate({ start, end })}
          />
        </div>
      </div>
    </div>
  );
}

export default function PlanYearPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <PlanYearInner />
    </AuthGuard>
  );
}
