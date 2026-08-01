"use client";

// The period capture heatmap — class × period for one day (DASH3 §4.1).
//
// The single most useful thing on the attendance tab, because it answers a
// question no percentage can: **was attendance bad, or was it never taken?**
// Four states, and keeping them apart is the entire point of the grid:
//
//   free      nothing scheduled — the class has no lesson that period
//   pending   scheduled and NOT marked — the gap the admin is looking for
//   marked    captured
//   not_held  the teacher said the class did not happen — captured, not missing
//
// Not a sequential heatmap: these are states, not magnitudes, so the cells use
// the reserved status colours and every cell carries a title + the legend below
// names each state. Colour is never the only channel (dataviz: status colours
// ship with a label).

import type { CaptureCell, CaptureState, PeriodCaptureGrid } from "@/lib/insights-types";
import { cn } from "@/lib/utils";

import { Empty, ScrollX } from "./shared";

const CELL: Record<CaptureState, { cls: string; label: string }> = {
  // Marked reads solid; pending reads as an outlined hole, which is what draws
  // the eye down a column of unmarked periods.
  marked: { cls: "bg-[color:var(--chart-green)]/70 text-transparent", label: "Marked" },
  pending: { cls: "border border-dashed border-danger/60 bg-danger/8", label: "Not marked" },
  not_held: { cls: "bg-muted-foreground/25", label: "Not held" },
  free: { cls: "bg-transparent", label: "No lesson" },
};

function cellTitle(classLabel: string, c: CaptureCell): string {
  const where = `${classLabel} · period ${c.period_no}${c.subject_name ? ` · ${c.subject_name}` : ""}`;
  if (c.state === "marked") {
    const detail = c.absent || c.late
      ? `${c.absent} absent${c.late ? `, ${c.late} late` : ""}`
      : "all present";
    return `${where} — marked (${detail})`;
  }
  if (c.state === "pending") return `${where} — scheduled, not marked yet`;
  if (c.state === "not_held") return `${where} — class not held`;
  return `${where} — no lesson scheduled`;
}

export function PeriodHeatmap({ grid }: { grid: PeriodCaptureGrid }) {
  if (!grid.rows.length) {
    return <Empty>No classes in this academic year yet — the grid fills once the timetable is set.</Empty>;
  }
  const periods = Array.from({ length: grid.periods_per_day }, (_, i) => i + 1);
  const times = new Map(grid.period_times.map((p) => [p.period_no, p]));

  return (
    <div>
      <ScrollX>
        <table className="w-full min-w-[520px] border-separate border-spacing-0.5 text-xs">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-card px-2 py-1 text-left font-medium text-muted-foreground">
                Class
              </th>
              {periods.map((p) => (
                <th key={p} className="px-1 py-1 text-center font-medium text-muted-foreground"
                  title={times.get(p) ? `${times.get(p)!.start}–${times.get(p)!.end}` : undefined}>
                  {p}
                </th>
              ))}
              <th className="px-2 py-1 text-right font-medium text-muted-foreground">Done</th>
            </tr>
          </thead>
          <tbody>
            {grid.rows.map((row) => (
              <tr key={row.class_id}>
                <th scope="row" className="sticky left-0 z-10 whitespace-nowrap bg-card px-2 py-1 text-left font-medium">
                  {row.class_label}
                </th>
                {periods.map((p) => {
                  const cell = row.cells.find((c) => c.period_no === p)
                    ?? { period_no: p, state: "free" as CaptureState, class_subject_id: null, subject_name: null, absent: 0, late: 0 };
                  return (
                    <td key={p} className="p-0">
                      <div
                        title={cellTitle(row.class_label, cell)}
                        className={cn("h-6 w-full min-w-6 rounded-sm", CELL[cell.state].cls)}
                      >
                        <span className="sr-only">{CELL[cell.state].label}</span>
                      </div>
                    </td>
                  );
                })}
                <td className="whitespace-nowrap px-2 py-1 text-right tabular-nums text-muted-foreground">
                  {row.expected ? `${row.marked}/${row.expected}` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollX>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        {(Object.keys(CELL) as CaptureState[]).map((state) => (
          <span key={state} className="inline-flex items-center gap-1.5">
            <span className={cn("h-3 w-3 rounded-sm", CELL[state].cls,
              state === "free" ? "border border-border" : "")} />
            {CELL[state].label}
          </span>
        ))}
      </div>
    </div>
  );
}
