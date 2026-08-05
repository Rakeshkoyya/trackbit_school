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

/** A catalogue date this school has not decided on yet (V1-20). */
export interface SuggestedDay {
  id: string;
  date: string; // yyyy-mm-dd
  name: string;
  kind: string;
  tier: string;
}

/**
 * Two levels of certainty, and the calendar's whole job is to keep them apart.
 *
 *   **Decided** — a row in `calendar_events`. It IS the year: it has already
 *   changed every plan's capacity. Solid fill, weighted numeral.
 *
 *   **Proposed** — a catalogue suggestion nobody has approved. It has changed
 *   nothing. Dashed outline, faint tint, normal weight.
 *
 * Outline-versus-fill rather than two greens, because the difference is
 * categorical (is this real yet?) not one of degree, and because texture
 * survives greyscale, a projector and colour blindness where a second tint of
 * the same hue does not. The dashed outline is the same device the roll
 * medallion, the day-book's away cell and the homework funnel already use for
 * "no record here" — one visual habit for one idea.
 */
const KIND_STYLE: Record<PaintKind, string> = {
  holiday: "bg-warning/25 text-warning font-semibold",
  exam_block: "bg-danger/18 text-danger font-semibold",
  event: "bg-accent text-accent-foreground font-semibold",
  celebration: "bg-primary/18 text-primary font-semibold",
};

const SUGGESTED_STYLE =
  "border border-dashed border-primary/45 bg-primary/[0.06] text-primary/85";

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
  suggestions = [],
  paintable = false,
  onPaint,
  onSuggestion,
  // SY-1 (founder): the calendar is a VIEW by default and only paints when the
  // admin says so. Tapping a date used to add an event on the spot, which on a
  // year grid is a fat-fingered holiday nobody meant to declare. Reviewing a
  // suggested date stays available in view mode, because that opens an approval
  // sheet and commits nothing.
  workingWeekdays = [0, 1, 2, 3, 4, 5],
  className,
}: {
  startDate: string;
  endDate: string;
  ranges?: PaintedRange[];
  suggestions?: SuggestedDay[];
  /** Drag across days to create an event. Off = read-only calendar. */
  paintable?: boolean;
  onPaint?: (start: string, end: string) => void;
  onSuggestion?: (s: SuggestedDay) => void;
  workingWeekdays?: number[];
  className?: string;
}) {
  const reduce = useReducedMotion();
  const [anchor, setAnchor] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const painting = useRef(false);
  // The anchor is mirrored in refs because `commit` runs on a window pointerup
  // that can arrive in the SAME tick as the pointerdown that set it. React
  // state is async, so a fast tap left `commit` reading a stale `null` anchor
  // and bailing out — the drag never resolved, the cell stayed stuck in its
  // selected ring, and nothing was painted or opened. Rare with a slow human
  // press, reliable with a quick one, and now on the critical path because
  // tapping a single suggested date is a primary action.
  const anchorRef = useRef<string | null>(null);
  const hoverRef = useRef<string | null>(null);

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
  const suggestionFor = useCallback(
    (day: string) => suggestions.find((s) => s.date === day),
    [suggestions],
  );

  const commit = useCallback(() => {
    const start = anchorRef.current;
    if (!painting.current || !start) return;
    painting.current = false;
    const other = hoverRef.current ?? start;
    const [a, b] = start <= other ? [start, other] : [other, start];
    anchorRef.current = null;
    hoverRef.current = null;
    setAnchor(null);
    setHover(null);
    // A TAP on a suggested day opens that suggestion; a DRAG always paints.
    // Without this split the two gestures collide on exactly the days the
    // admin most wants to act on — and painting a fresh "Holiday" over Diwali
    // would throw away the name, the source and the note the catalogue carries.
    if (a === b) {
      const hit = suggestionFor(a);
      if (hit && onSuggestion) {
        onSuggestion(hit);
        return;
      }
    }
    // In view mode a drag selects nothing and paints nothing. Only the
    // suggestion tap above survives, and that opens a sheet rather than
    // writing anything.
    if (!paintable) return;
    onPaint?.(a, b);
  }, [onPaint, onSuggestion, paintable, suggestionFor]);

  const interactive = paintable || !!onSuggestion;

  useEffect(() => {
    if (!interactive) return;
    window.addEventListener("pointerup", commit);
    return () => window.removeEventListener("pointerup", commit);
  }, [interactive, commit]);

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
                  // A decided event always wins the cell: it is what the year
                  // actually is. The suggestion underneath it has been answered.
                  const suggested = hit ? undefined : suggestionFor(day);
                  const selecting = pending && within(day, pending.start, pending.end);
                  const label = hit
                    ? `${hit.title} · ${hit.kind.replace("_", " ")}`
                    : suggested
                      ? `${suggested.name} — suggested, not on your calendar yet`
                      : day;

                  return (
                    <button
                      key={day}
                      type="button"
                      disabled={!interactive || !inYear}
                      aria-label={suggested ? `${day}: ${suggested.name}, suggested` : day}
                      title={label}
                      onPointerDown={() => {
                        if (!interactive || !inYear) return;
                        painting.current = true;
                        anchorRef.current = day;
                        hoverRef.current = day;
                        setAnchor(day);
                        setHover(day);
                      }}
                      onPointerEnter={() => {
                        // No hover-extend in view mode: there is no range to
                        // build, so the ring would promise a paint that never
                        // happens.
                        if (!painting.current || !paintable) return;
                        hoverRef.current = day;
                        setHover(day);
                      }}
                      className={cn(
                        "aspect-square rounded-[3px] text-[10px] leading-none transition-colors",
                        "flex items-center justify-center",
                        !inYear && "opacity-25",
                        inYear && !working && "text-muted-foreground/60",
                        inYear && working && !hit && !suggested && "bg-muted/60",
                        suggested && SUGGESTED_STYLE,
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

export function CalendarLegend({ showSuggested = false }: { showSuggested?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
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
      {showSuggested ? (
        <span className="inline-flex items-center gap-1.5">
          <span className={cn("h-3 w-3 rounded-[3px]", SUGGESTED_STYLE)} />
          {/* Named for what the admin has to DO, not for where it came from.
              "Observance" is our word; "tap to decide" is their next move. */}
          Suggested — tap to decide
        </span>
      ) : null}
    </div>
  );
}
