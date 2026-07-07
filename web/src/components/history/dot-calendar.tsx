"use client";

import type { DayDot } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATE_CLASS: Record<DayDot["state"], string> = {
  all: "bg-success",
  partial: "bg-success/35",
  none: "bg-muted",
};

/**
 * Dot calendar (plan §3.3) — a mosaic of effort, never a broken chain. Weeks
 * run in columns (Mon→Sun rows). Quiet days are muted, never red; there is no
 * "streak lost" framing.
 */
export function DotCalendar({ dots }: { dots: DayDot[] }) {
  if (dots.length === 0) return null;
  // Pad the first column so weekdays line up (Mon = row 0).
  const firstWeekday = (new Date(dots[0].date + "T00:00:00").getDay() + 6) % 7;

  return (
    <div className="overflow-x-auto">
      <div className="grid grid-flow-col grid-rows-7 gap-1">
        {Array.from({ length: firstWeekday }).map((_, i) => (
          <div key={`pad-${i}`} className="h-3 w-3" />
        ))}
        {dots.map((d) => (
          <div
            key={d.date}
            title={`${d.date} · ${d.state === "none" ? "nothing due" : `${d.done}/${d.total} done`}`}
            className={cn("h-3 w-3 rounded-sm", STATE_CLASS[d.state])}
          />
        ))}
      </div>
      <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="h-2.5 w-2.5 rounded-sm bg-success" /> all clear
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2.5 w-2.5 rounded-sm bg-success/35" /> partial
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2.5 w-2.5 rounded-sm bg-muted" /> nothing due
        </span>
      </div>
    </div>
  );
}
