"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { schoolApi } from "@/lib/school-api";
import type { DaySlot } from "@/lib/school-types";
import { cn } from "@/lib/utils";

/**
 * The class's week the way a school reads it: days across, periods down, each
 * cell "subject + what gets taught". Everything is computed server-side — past
 * cells show the actual log, future cells the remaining syllabus laid onto the
 * timetable — so a teacher absence or a slow chapter shifts the projection
 * without anyone editing a plan (P2).
 */

const WEEKDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function toIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return toIso(d);
}

const fmt = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

function Cell({ slot }: { slot: DaySlot }) {
  const muted = slot.state === "blocked" || slot.state === "past";
  return (
    <div
      className={cn(
        "flex min-h-14 flex-col gap-0.5 rounded-md border px-2 py-1.5",
        slot.state === "actual" && "border-success/40 bg-success/5",
        slot.state === "planned" && "border-border bg-card",
        muted && "border-dashed border-border bg-muted/30",
      )}
    >
      <span className="flex items-center gap-1 text-[11px] font-medium">
        {slot.subject_name}
        {slot.state === "actual" ? <CheckCircle2 className="h-3 w-3 text-success" /> : null}
      </span>
      <span className={cn("text-[11px] leading-tight", muted ? "text-muted-foreground/70" : "text-muted-foreground")}>
        {slot.state === "blocked"
          ? "no class"
          : slot.state === "past" && !slot.topic_title
            ? "not logged"
            : slot.topic_title ?? "syllabus done"}
      </span>
    </div>
  );
}

export function ClassWeekGrid({ classId }: { classId: string }) {
  const [weekStart, setWeekStart] = useState<string | undefined>(undefined);
  const { data: week } = useQuery({
    queryKey: ["week-schedule", classId, weekStart ?? "current"],
    queryFn: () => schoolApi.weekSchedule(classId, weekStart),
    enabled: !!classId,
  });

  if (!week) return null;
  const periods = Array.from({ length: week.periods_per_day }, (_, i) => i + 1);
  const byDay = new Map(week.days.map((d) => [d.date, new Map(d.slots.map((s) => [s.period_no, s]))]));

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">
          Class week — {week.class_label} · {fmt(week.week_start)}
        </h2>
        <div className="flex items-center gap-1">
          <Button size="sm" variant="outline" className="h-7 px-2"
            onClick={() => setWeekStart(addDays(week.week_start, -7))} aria-label="Previous week">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button size="sm" variant="outline" className="h-7 px-2 text-xs"
            onClick={() => setWeekStart(undefined)}>
            This week
          </Button>
          <Button size="sm" variant="outline" className="h-7 px-2"
            onClick={() => setWeekStart(addDays(week.week_start, 7))} aria-label="Next week">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border bg-card p-2">
        <div
          className="grid min-w-[720px] gap-1"
          style={{ gridTemplateColumns: `2.5rem repeat(${week.days.length}, minmax(0, 1fr))` }}
        >
          <div />
          {week.days.map((d) => (
            <div key={d.date} className="px-1 pb-1 text-center text-xs font-medium">
              {WEEKDAY[d.weekday]}{" "}
              <span className={cn("text-muted-foreground", d.blocked && "line-through")}>{fmt(d.date)}</span>
            </div>
          ))}
          {periods.map((p) => (
            <div key={p} className="contents">
              <div className="flex items-center justify-center text-xs text-muted-foreground">P{p}</div>
              {week.days.map((d) => {
                const slot = byDay.get(d.date)?.get(p);
                return slot ? (
                  <Cell key={d.date + p} slot={slot} />
                ) : (
                  <div key={d.date + p} className="min-h-14 rounded-md border border-dashed border-border/50" />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">
        Green = actually taught (from the log). The rest is the remaining syllabus laid onto the
        timetable from today — it shifts by itself when a class runs behind.
      </p>
    </div>
  );
}
