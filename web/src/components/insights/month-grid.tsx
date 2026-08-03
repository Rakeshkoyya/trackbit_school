"use client";

// V1-14 — the register: a month of attendance, class by class, day by day.
//
// **Why a grid and not a line.** Student attendance sits at ninety-something
// percent every day of the year, so a trend line is a flat line with noise on
// it: it cannot show a bad Tuesday, it cannot show which class is struggling,
// and it certainly cannot show the days nobody marked. The grid shows all three
// at once — a bad day is a vertical stripe, a struggling class a horizontal one,
// and a gap in the record is a gap you can see.
//
// **Why it looks like this.** It is the school's own artifact. Every teacher in
// the building keeps a register: names ruled down the margin, dates across the
// head, a mark in every box, a total in the last column. So this is set as that
// document — a ruled margin, mono figures with tabular numerals, day numbers as
// column heads with the weekday initial above them, and the month total where a
// register keeps it. Nothing here is decoration: the rules separate entries the
// way a ledger's do, and the mono is the face a register is written in.
//
// **The encoding** is sequential on absence — one hue, four monotonic steps,
// with an explicit zero: a class with nobody away gets a quiet filled cell
// rather than the lightest step of a "bad" ramp, so "nothing wrong" reads as
// nothing rather than as a little bit wrong. `unmarked` is a dashed outline —
// its own texture, not a step on the ramp, because a day nobody captured is not
// a day with low absence, and confusing the two is the single failure this whole
// grid exists to prevent.
//
// The class margin and the month total are **sticky** to the two edges: they are
// what the register is read BY, and letting them scroll away with the days left
// a wall of cells nobody could attribute to a class or a total.
//
// Plain CSS throughout. No charting library is loaded for this, so the register
// is on screen before the Recharts chunk arrives.

import Link from "next/link";
import { useMemo } from "react";

import type { ClassMonthCell, ClassMonthRow } from "@/lib/insights-types";
import { cn } from "@/lib/utils";

/** One hue, four steps, plus a zero that is not a step. Bands are on the SHARE
 *  of the class away, so a 12-child class and a 45-child class are comparable —
 *  a raw count would paint every big class dark. */
function cellClass(cell: ClassMonthCell): string {
  if (cell.state === "unmarked") {
    return "border border-dashed border-muted-foreground/40 bg-transparent";
  }
  if (!cell.absent) return "bg-muted-foreground/20";
  const share = cell.roster ? cell.absent / cell.roster : 0;
  if (share < 0.05) return "bg-[color:var(--chart-red)]/25";
  if (share < 0.1) return "bg-[color:var(--chart-red)]/45";
  if (share < 0.2) return "bg-[color:var(--chart-red)]/70";
  return "bg-[color:var(--chart-red)]";
}

function cellTitle(cell: ClassMonthCell, classLabel: string): string {
  const when = new Date(`${cell.date}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "short", day: "numeric", month: "short",
  });
  if (cell.state === "unmarked") {
    return `${classLabel} · ${when} — nothing marked. Not a full house; a gap in the record.`;
  }
  if (!cell.absent) return `${classLabel} · ${when} — everyone in (${cell.roster} on roll)`;
  return `${classLabel} · ${when} — ${cell.absent} of ${cell.roster} away (${cell.pct}% present)`;
}

const dayNo = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric" });
const weekdayInitial = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: "narrow" });
const monthOf = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "short" });

export function MonthGrid({
  rows, dates,
}: {
  rows: ClassMonthRow[];
  dates: string[];
}) {
  // A day number over every one of thirty columns is a smear, not an axis —
  // label roughly every fifth, plus every month boundary. The weekday initial
  // runs on every column, because a register's reader navigates by weekday and
  // a single letter never collides.
  const ticks = useMemo(() => {
    const out = new Set<number>();
    dates.forEach((d, i) => {
      if (i === 0 || i === dates.length - 1 || i % 5 === 0) out.add(i);
      if (i > 0 && monthOf(d) !== monthOf(dates[i - 1])) out.add(i);
    });
    return out;
  }, [dates]);

  if (!rows.length || !dates.length) {
    return (
      <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
        No class has captured attendance in this window yet — the register fills as
        soon as one period is marked.
      </p>
    );
  }

  return (
    <div className="-mx-1 overflow-x-auto px-1" style={{ contain: "layout inline-size" }}>
      <div className="min-w-[680px]">
        <table className="w-full border-separate border-spacing-0">
          <caption className="sr-only">
            Attendance by class and day. Darker means more of the class was away;
            a dashed cell means nothing was marked that day.
          </caption>
          <thead>
            <tr>
              <th scope="col"
                className="sticky left-0 z-10 w-[104px] bg-card pb-1.5 pr-3 text-left font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                Class
              </th>
              {dates.map((d, i) => (
                <th key={d} scope="col" className="px-[1px] pb-1.5 align-bottom">
                  <span className="block text-center font-mono text-[9px] leading-none text-muted-foreground/50">
                    {weekdayInitial(d)}
                  </span>
                  <span className="mt-0.5 block text-center font-mono text-[10px] leading-none tabular-nums text-muted-foreground">
                    {ticks.has(i) ? dayNo(d) : " "}
                  </span>
                </th>
              ))}
              <th scope="col"
                className="sticky right-0 z-10 w-16 bg-card pb-1.5 pl-3 text-right font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                Month
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const byDate = new Map(row.cells.map((c) => [c.date, c]));
              return (
                <tr key={row.class_id} className="group">
                  {/* The ruled margin. A register keys its rows at the left
                      edge, and the roll size belongs beside the name. */}
                  <th scope="row"
                    className="sticky left-0 z-10 border-r border-border/70 bg-card py-[3px] pr-3 text-left align-middle">
                    <Link href={`/students?class=${row.class_id}`}
                      className="flex items-baseline justify-end gap-2 hover:underline">
                      <span className="truncate text-[12px] font-medium">{row.class_label}</span>
                      <span className="shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground/60">
                        {row.roster}
                      </span>
                    </Link>
                  </th>
                  {dates.map((d) => {
                    const cell = byDate.get(d)
                      ?? { date: d, state: "unmarked" as const, absent: 0, roster: row.roster, pct: null };
                    return (
                      <td key={d} className="px-[1px] py-[3px]">
                        <div title={cellTitle(cell, row.class_label)}
                          className={cn(
                            "h-6 w-full rounded-[3px] transition-[transform,opacity]",
                            "hover:scale-[1.35] hover:opacity-100 group-hover:opacity-95",
                            cellClass(cell))} />
                      </td>
                    );
                  })}
                  <td className="sticky right-0 z-10 border-l border-border/70 bg-card py-[3px] pl-3 text-right">
                    {row.pct != null ? (
                      <span className={cn("font-mono text-[12px] tabular-nums",
                        row.tone === "red" ? "text-danger"
                          : row.tone === "amber" ? "text-warning" : "text-foreground/80")}>
                        {row.pct}
                        <span className="text-muted-foreground/50">%</span>
                      </span>
                    ) : (
                      <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground/60">
                        &mdash;
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* The key is not optional. Three of the states here are things a colour
            alone cannot say, and "nothing marked" is the one an admin most needs
            to not mistake for a good day. */}
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border/70 pt-3 font-mono text-[10px] tracking-wide text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-[3px] bg-muted-foreground/20" /> ALL IN
          </span>
          <span className="flex items-center gap-1.5">
            <span className="flex gap-[2px]">
              {[25, 45, 70, 100].map((o) => (
                <span key={o} className="h-3 w-3 rounded-[3px]"
                  style={{ background: `color-mix(in oklab, var(--chart-red) ${o}%, transparent)` }} />
              ))}
            </span>
            MORE AWAY
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-[3px] border border-dashed border-muted-foreground/40" />
            NOTHING MARKED &mdash; a gap in the record, not a full house
          </span>
        </div>
      </div>
    </div>
  );
}
