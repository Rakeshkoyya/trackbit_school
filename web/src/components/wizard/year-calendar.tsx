"use client";

/**
 * The wizard's live year artifact (V2-P7).
 *
 * Two jobs, one component:
 *   1. Preview — as the admin drags the year's end date, months mount and unmount
 *      with a spring, so the shape of the year is something they *see*.
 *   2. Paint — select a range of days the way you pick seats: press a cell, drag,
 *      release. Used for exams, holidays and celebrations.
 *
 * Motion is opt-out: `useReducedMotion` collapses every transition to an instant
 * swap. An admin doing a heavy one-time setup on a school laptop must be able to
 * turn the movement off, and the component must still be fully usable.
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export type PaintKind = "holiday" | "exam_block" | "event" | "celebration";

export interface PaintedRange {
  start: string; // yyyy-mm-dd
  end: string;
  kind: PaintKind;
  title: string;
}

const KIND_STYLE: Record<PaintKind, string> = {
  holiday: "bg-warning-soft text-warning",
  exam_block: "bg-danger/12 text-danger",
  event: "bg-accent text-accent-foreground",
  celebration: "bg-[#e7efe9] text-[#234a37]",
};

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
// Monday-first, matching the school week (working_weekdays uses Mon=0).
const DOW = ["M", "T", "W", "T", "F", "S", "S"];

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

function parse(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** Every month touched by [start, end], as a first-of-month date. */
function monthsBetween(start: Date, end: Date): Date[] {
  const out: Date[] = [];
  const cur = new Date(start.getFullYear(), start.getMonth(), 1);
  const last = new Date(end.getFullYear(), end.getMonth(), 1);
  let guard = 0;
  while (cur <= last && guard < 36) {
    out.push(new Date(cur));
    cur.setMonth(cur.getMonth() + 1);
    guard += 1;
  }
  return out;
}

/** Leading blanks so the 1st lands under the right weekday (Monday-first). */
function leadingBlanks(monthStart: Date): number {
  return (monthStart.getDay() + 6) % 7;
}

function daysInMonth(monthStart: Date): number {
  return new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0).getDate();
}

function within(day: string, start: string, end: string): boolean {
  return day >= start && day <= end;
}

export function YearCalendar({
  startDate,
  endDate,
  ranges = [],
  paintable = false,
  onPaint,
  workingWeekdays = [0, 1, 2, 3, 4, 5],
  className,
}: {
  startDate: string;
  endDate: string;
  ranges?: PaintedRange[];
  paintable?: boolean;
  onPaint?: (start: string, end: string) => void;
  workingWeekdays?: number[];
  className?: string;
}) {
  const reduce = useReducedMotion();
  const [anchor, setAnchor] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const painting = useRef(false);

  const months = useMemo(() => {
    if (!startDate || !endDate) return [];
    const s = parse(startDate);
    const e = parse(endDate);
    if (e < s) return [];
    return monthsBetween(s, e);
  }, [startDate, endDate]);

  // A drag can end anywhere on the page (or outside it), so commit on a window
  // pointerup rather than on the cell's — otherwise releasing off-grid leaves the
  // selection stuck mid-drag.
  const commit = useCallback(() => {
    if (!painting.current || !anchor) return;
    painting.current = false;
    const other = hover ?? anchor;
    const [a, b] = anchor <= other ? [anchor, other] : [other, anchor];
    onPaint?.(a, b);
    setAnchor(null);
    setHover(null);
  }, [anchor, hover, onPaint]);

  useEffect(() => {
    if (!paintable) return;
    window.addEventListener("pointerup", commit);
    return () => window.removeEventListener("pointerup", commit);
  }, [paintable, commit]);

  const pending = useMemo(() => {
    if (!anchor) return null;
    const other = hover ?? anchor;
    return anchor <= other ? { start: anchor, end: other } : { start: other, end: anchor };
  }, [anchor, hover]);

  const rangeFor = useCallback(
    (day: string) => ranges.find((r) => within(day, r.start, r.end)),
    [ranges],
  );

  if (!months.length) {
    return (
      <div
        className={cn(
          "flex h-full min-h-64 items-center justify-center rounded-2xl border border-dashed border-border text-sm text-muted-foreground",
          className,
        )}
      >
        Pick a start and end date to see the year.
      </div>
    );
  }

  return (
    <div className={cn("grid grid-cols-2 gap-4 sm:grid-cols-3", className)}>
      <AnimatePresence mode="popLayout" initial={false}>
        {months.map((month) => {
          const key = `${month.getFullYear()}-${month.getMonth()}`;
          const blanks = leadingBlanks(month);
          const total = daysInMonth(month);
          return (
            <motion.div
              key={key}
              layout={!reduce}
              initial={reduce ? false : { opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={reduce ? undefined : { opacity: 0, scale: 0.9 }}
              transition={
                reduce
                  ? { duration: 0 }
                  : { type: "spring", stiffness: 320, damping: 30, mass: 0.6 }
              }
              className="rounded-xl border border-border bg-card p-2.5"
            >
              <div className="mb-1.5 flex items-baseline justify-between">
                <span className="text-xs font-semibold">{MONTHS[month.getMonth()]}</span>
                <span className="text-[10px] text-muted-foreground">{month.getFullYear()}</span>
              </div>
              <div className="grid grid-cols-7 gap-px text-center">
                {DOW.map((d, i) => (
                  <span key={i} className="text-[9px] font-medium text-muted-foreground">
                    {d}
                  </span>
                ))}
                {Array.from({ length: blanks }).map((_, i) => (
                  <span key={`b${i}`} />
                ))}
                {Array.from({ length: total }).map((_, i) => {
                  const date = new Date(month.getFullYear(), month.getMonth(), i + 1);
                  const day = iso(date);
                  const inYear = day >= startDate && day <= endDate;
                  const weekday = (date.getDay() + 6) % 7;
                  const working = workingWeekdays.includes(weekday);
                  const hit = rangeFor(day);
                  const selecting = pending && within(day, pending.start, pending.end);

                  return (
                    <button
                      key={day}
                      type="button"
                      disabled={!paintable || !inYear}
                      aria-label={day}
                      title={hit ? `${hit.title} · ${hit.kind.replace("_", " ")}` : day}
                      onPointerDown={() => {
                        if (!paintable || !inYear) return;
                        painting.current = true;
                        setAnchor(day);
                        setHover(day);
                      }}
                      onPointerEnter={() => {
                        if (painting.current) setHover(day);
                      }}
                      className={cn(
                        "aspect-square rounded-[3px] text-[10px] leading-none transition-colors",
                        "flex items-center justify-center",
                        !inYear && "opacity-25",
                        inYear && !working && "text-muted-foreground/60",
                        inYear && working && !hit && "bg-muted/60",
                        hit && KIND_STYLE[hit.kind],
                        selecting && "ring-2 ring-ring ring-offset-1",
                        paintable && inYear && "cursor-pointer hover:brightness-95",
                      )}
                    >
                      {i + 1}
                    </button>
                  );
                })}
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

export function CalendarLegend() {
  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
      {(
        [
          ["holiday", "Holiday"],
          ["exam_block", "Exam"],
          ["event", "Event"],
          ["celebration", "Celebration"],
        ] as [PaintKind, string][]
      ).map(([kind, label]) => (
        <span key={kind} className="inline-flex items-center gap-1.5">
          <span className={cn("h-3 w-3 rounded-[3px]", KIND_STYLE[kind])} />
          {label}
        </span>
      ))}
    </div>
  );
}
