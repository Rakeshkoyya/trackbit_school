"use client";

// The register book — student × school day (founder, 2026-08-05).
//
// Built once, mounted twice: My Class gives its class teacher a register she can
// annotate (tap a red square to say why), and the every-teacher attendance
// screen shows the same book read-only. Both render `build_register`'s cells, so
// the two can never paint the same October differently.
//
// THE LAYOUT, and why it is not a `<table>`.
//
// The old grid was a table with `position: sticky` on the name cell. Sticky
// cells inside a scroller are fragile — they depend on the table's own layout
// algorithm, and at 360px the name column had to be `max-w-[11rem] truncate`,
// which ate most of the viewport and left three days visible. So this is **two
// panes**: a fixed name column, and a grid that scrolls sideways beside it.
// Nothing is sticky, nothing truncates to nothing, and the same code serves the
// phone and the desktop — the phone just scrolls further.
//
// `contain: layout inline-size` on the scroller is load-bearing (the V1-14 fix):
// `overflow-x: auto` alone does not stop a wide child's min-content
// contribution propagating up, so the grid would scroll AND drag the whole page
// sideways.
//
// Colour follows `D-86`: absent with a reason on record is amber (somebody dealt
// with it), absent with none is red. A day nobody marked is neutral with its own
// legend entry — a gap in the record is never evidence about a child (ux §5).

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { shiftMonth, todayKey } from "@/lib/format";
import type { ClassRegister, DayCellStatus, RegisterCell, RegisterRow } from "@/lib/school-types";
import { cn } from "@/lib/utils";

export const CELL: Record<DayCellStatus, { cls: string; label: string }> = {
  present: { cls: "bg-[color:var(--success,#234a37)]/25", label: "present" },
  partial: { cls: "bg-warning/40", label: "in for part of the day" },
  left_after_lunch: { cls: "bg-warning/60", label: "left after lunch" },
  absent: { cls: "bg-danger/70", label: "absent" },
  not_marked: { cls: "bg-muted", label: "not marked" },
  no_school: { cls: "bg-transparent border border-dashed border-border/70", label: "—" },
};

const MODE_LABEL: Record<string, string> = {
  every_period: "every period",
  first_period: "once a day",
  twice_daily: "twice a day",
};

const WEEKDAY = ["S", "M", "T", "W", "T", "F", "S"];

function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(undefined,
    { month: "long", year: "numeric" });
}

/** Row height, shared by both panes. They are separate scrollers, so the rows
 *  only line up because this number is used in both — it is not decoration. */
const ROW = "h-8";
const CELL_W = "w-7";

export function RegisterBook({
  data, month, onMonth, onCell, title,
}: {
  data: ClassRegister;
  month: string;
  onMonth: (next: string) => void;
  /** Omitted = read-only. My Class passes a handler to open the reason sheet. */
  onCell?: (row: RegisterRow, cell: RegisterCell) => void;
  title?: string;
}) {
  // `todayKey`, never `toISOString()` — the latter is UTC, so east of UTC the
  // "today" column would highlight yesterday for the whole morning.
  const today = todayKey();
  const unexplained = data.rows.reduce(
    (n, r) => n + r.cells.filter((c) => c.status === "absent" && !c.has_reason).length, 0);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Previous month"
            onClick={() => onMonth(shiftMonth(month, -1))}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-[9rem] text-center text-sm font-medium">
            {monthLabel(data.month)}
          </span>
          <Button variant="ghost" size="icon" aria-label="Next month"
            onClick={() => onMonth(shiftMonth(month, 1))}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <p className="font-mono text-[11px] text-muted-foreground">
          {title ? `${title} · ` : ""}
          {data.school_days} school day{data.school_days === 1 ? "" : "s"} ·
          register taken {MODE_LABEL[data.mode] ?? data.mode}
        </p>
      </div>

      {/* The sentence, and it names its own denominator: "present" is only ever
          out of the days this class actually marked (ux §4). */}
      <p className="mb-3 text-[13px] leading-snug">{data.headline}</p>

      {unexplained > 0 && onCell ? (
        <p className="mb-3 rounded-lg border border-border bg-danger/5 px-3 py-2 text-sm">
          <span className="font-medium">
            {unexplained} absence{unexplained === 1 ? "" : "s"}
          </span>{" "}
          with no reason on record — tap a red square to say why.
        </p>
      ) : null}

      <div className="flex overflow-hidden rounded-xl border border-border bg-card">
        {/* ── pane 1: the margin. Never scrolls, never truncates to nothing. */}
        <div className="shrink-0 border-r border-border">
          <div className={cn(ROW, "flex items-end border-b border-border px-2 pb-1",
            "font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground")}>
            Student
          </div>
          {data.rows.map((row) => (
            <div key={row.student_id}
              className={cn(ROW, "flex items-center gap-1.5 border-b border-border/50 px-2 last:border-b-0")}>
              <Link href={`/students/${row.student_id}`}
                className="w-[6.5rem] truncate text-[12px] hover:text-primary sm:w-[10rem]">
                {row.roll_no ? (
                  <span className="mr-1 font-mono text-[10px] text-muted-foreground">
                    {row.roll_no}
                  </span>
                ) : null}
                {row.full_name}
              </Link>
              <span className="ml-auto whitespace-nowrap font-mono text-[10px] tabular-nums text-muted-foreground">
                {row.marked_days > 0
                  ? `${row.present_days}/${row.marked_days}`
                  : "—"}
              </span>
            </div>
          ))}
          {/* The bottom margin: what the column totals row is labelled with. */}
          <div className={cn(ROW, "flex items-center border-t border-border px-2",
            "font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground")}>
            In that day
          </div>
        </div>

        {/* ── pane 2: the days. This is the pane that scrolls. */}
        <div className="min-w-0 flex-1 overflow-x-auto"
          style={{ contain: "layout inline-size" }}>
          <div className="w-max">
            <div className={cn(ROW, "flex border-b border-border")}>
              {data.days.map((d) => {
                const dow = new Date(`${d}T00:00:00`).getDay();
                return (
                  <span key={d}
                    className={cn(CELL_W, "flex shrink-0 flex-col items-center justify-end pb-0.5",
                      d === today && "bg-primary/5")}>
                    <span className="font-mono text-[8px] uppercase text-muted-foreground/70">
                      {WEEKDAY[dow]}
                    </span>
                    <span className={cn("font-mono text-[10px] tabular-nums",
                      d === today ? "font-semibold text-primary" : "text-muted-foreground")}>
                      {Number(d.slice(8, 10))}
                    </span>
                  </span>
                );
              })}
            </div>

            {data.rows.map((row) => (
              <div key={row.student_id}
                className={cn(ROW, "flex border-b border-border/50 last:border-b-0")}>
                {row.cells.map((c) => {
                  const meta = CELL[c.status];
                  // `D-86`: an absence somebody has explained reads amber, not
                  // red. Red is for what nobody has dealt with yet.
                  const amber = c.status === "absent" && c.has_reason;
                  const actionable = onCell
                    && (c.status === "absent" || c.status === "left_after_lunch");
                  return (
                    <span key={c.date}
                      className={cn(CELL_W, "flex shrink-0 items-center justify-center",
                        c.date === today && "bg-primary/5")}>
                      <button type="button" disabled={!actionable}
                        onClick={() => actionable && onCell?.(row, c)}
                        title={`${row.full_name} · ${new Date(`${c.date}T00:00:00`)
                          .toLocaleDateString()} — ${meta.label}${c.late ? " (late)" : ""}${
                          c.has_reason ? " · reason recorded" : ""}`}
                        aria-label={`${row.full_name} ${c.date} ${meta.label}`}
                        className={cn("block h-5 w-5 rounded-[3px]",
                          amber ? "bg-warning/70" : meta.cls,
                          c.late && "ring-1 ring-inset ring-warning",
                          actionable && "cursor-pointer hover:opacity-80")} />
                    </span>
                  );
                })}
              </div>
            ))}

            {/* Column totals — the figure a paper register carries at the foot
                of each column. A day nobody marked shows a dash, never a 0. */}
            <div className={cn(ROW, "flex border-t border-border")}>
              {data.day_totals.map((t) => (
                <span key={t.date}
                  className={cn(CELL_W, "flex shrink-0 items-center justify-center",
                    "font-mono text-[10px] tabular-nums",
                    t.date === today && "bg-primary/5",
                    t.marked ? "text-muted-foreground" : "text-muted-foreground/40")}
                  title={t.marked
                    ? `${t.present} of ${t.counted} in`
                    : "nobody marked this day"}>
                  {t.marked ? t.present : "—"}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        {(["present", "partial", "absent", "not_marked"] as DayCellStatus[]).map((s) => (
          <span key={s} className="inline-flex items-center gap-1.5">
            <span className={cn("h-3 w-3 rounded-[3px]", CELL[s].cls)} />
            {CELL[s].label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-warning/70" /> absent · reason recorded
        </span>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">
        &ldquo;Present&rdquo; counts the days this class actually marked — never the
        days nobody took. Scroll the grid sideways for the rest of the month.
      </p>
    </div>
  );
}
