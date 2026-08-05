"use client";

/**
 * Adjusting the plan (SY-1) — the founder's ask, and the one genuinely new
 * artifact in this packet.
 *
 * *"When she wants to change the date of chapter 3 and extend it, show a visual
 * representation of chapters and the timeline up to the next exam, so she can
 * adjust the nodes and see the gaps."*
 *
 * The design follows from that sentence. Time runs left to right across a
 * single ribbon. Everything she can MOVE is a bar; everything she cannot is a
 * **rule drawn through every lane** — the exam she is planning towards, the term
 * that ends, today. She is not reading a chart, she is pushing chapters around
 * against fixed walls, and the walls have to look like walls.
 *
 * The gaps are drawn, not implied. A hatched span between two chapters carries
 * its own count of teaching days, because "there is a free fortnight in
 * November" is the thing she opened this dialog to find out and a blank stretch
 * of background does not say it.
 *
 * Dragging is the fast path, never the only one: every bar has date inputs in
 * the ledger below, which is what a keyboard and a screen reader use. The two
 * edit one piece of state.
 *
 * Nothing is written until she saves. On save the server reports a range too
 * small for its chapters and **still saves it** (V2-P5) — she is the one who
 * knows whether she can go faster.
 */

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, GripVertical, Lock } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { showApiError } from "@/lib/errors";
import { shiftDay, todayKey } from "@/lib/format";
import { schoolApi } from "@/lib/school-api";
import type { RescheduleViolation } from "@/lib/syllabus-types";
import { cn } from "@/lib/utils";

const DAY_MS = 86_400_000;

/** Whole days between two `YYYY-MM-DD` keys, in local time throughout —
 *  never via `toISOString`, which returns yesterday east of UTC (V1-14). */
const daysBetween = (a: string, b: string) =>
  Math.round((new Date(`${b}T00:00:00`).getTime()
    - new Date(`${a}T00:00:00`).getTime()) / DAY_MS);

const fmtDay = (iso: string, withYear = false) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN",
    withYear ? { day: "numeric", month: "short", year: "2-digit" }
      : { day: "numeric", month: "short" });

type Draft = Record<string, { start: string; end: string }>;

const LANE_H = 34;

export function PlanTimelineDialog({ csId, termId, open, onOpenChange, onSaved }: {
  csId: string | null;
  termId?: string | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSaved: () => void;
}) {
  return (
    <Modal open={open} onOpenChange={onOpenChange} size="xl"
      title="Adjust the plan"
      description="Move a chapter and watch what it does to the days before the exam.">
      {/* Keyed and mounted only while open, so every draft edit is discarded
          when she closes it — no effect resetting state after the fact. */}
      {open && csId ? (
        <TimelineBody key={`${csId}:${termId ?? ""}`} csId={csId} termId={termId}
          onClose={() => onOpenChange(false)} onSaved={onSaved} />
      ) : null}
    </Modal>
  );
}

function TimelineBody({ csId, termId, onClose, onSaved }: {
  csId: string;
  termId?: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  // The server's copy is react-query's; the only local state is what she has
  // MOVED. Deriving the draft from the two means a refetch after saving cannot
  // leave a stale set of dates on screen.
  const { data, isLoading } = useQuery({
    queryKey: ["plan-timeline", csId, termId ?? ""],
    queryFn: () => schoolApi.planTimeline(csId, termId ?? undefined),
  });
  const [moved, setMoved] = useState<Draft>({});
  const [violations, setViolations] = useState<RescheduleViolation[]>([]);
  const [saving, setSaving] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  // Mirrored in a ref: a fast pointerup can land in the same tick as the
  // pointerdown that set the drag, and React state is async — the V1-20 bug.
  const dragRef = useRef<{
    unit: string; mode: "move" | "start" | "end"; originX: number;
    from: { start: string; end: string };
    // The scale is frozen at pointerdown. The axis widens to follow a bar
    // dragged past its edge, so reading the live span mid-drag would change
    // pixels-per-day underneath the pointer and the bar would accelerate away
    // from it.
    span: number;
  } | null>(null);

  // The dates on screen: the server's, overridden by anything she has dragged.
  const draft: Draft = useMemo(() => {
    const base: Draft = {};
    for (const c of data?.chapters ?? []) {
      if (c.planned_start && c.planned_end) {
        base[c.unit_id] = moved[c.unit_id]
          ?? { start: c.planned_start, end: c.planned_end };
      }
    }
    return base;
  }, [data, moved]);

  /**
   * The axis — **the stretch she is actually planning, not the whole year.**
   *
   * Drawn across the full planning window, a fortnight-long chapter is 3% of
   * the ribbon: a 40px pill with no room for its own name, which is the one
   * thing the picture exists to show. So the axis runs from the earliest thing
   * on screen to **the next exam after her chapters**, padded a week each side
   * and clamped to the window — the founder's "up to the next exam", made
   * literal. Anything dragged past the edge widens it, so nothing can be
   * dragged out of sight.
   */
  const axis = useMemo(() => {
    if (!data) return null;
    const drafted = Object.values(draft).flatMap((d) => [d.start, d.end]);
    const min = (xs: string[]) => xs.reduce((a, b) => (a < b ? a : b));
    const max = (xs: string[]) => xs.reduce((a, b) => (a > b ? a : b));

    const anchors = drafted.length ? drafted : [todayKey()];
    let from = min(anchors);
    let to = max(anchors);
    // The next exam that ends after the chapters do — the deadline she is
    // planning against. Without one, a month of headroom is enough to work in.
    const exam = data.markers
      .filter((mk) => mk.kind === "exam" && (mk.end_date ?? mk.date) >= to)
      .sort((a, b) => a.date.localeCompare(b.date))[0];
    to = exam ? max([to, exam.end_date ?? exam.date]) : shiftDay(to, 30);
    from = min([from, todayKey()]);

    // Clamped to the window, EXCEPT where a chapter already sits outside it: a
    // plan week is a Monday, and the Monday of the year's first week routinely
    // falls a few days before the year starts. Clamping there pinned that
    // chapter's bar to 0% and drew it starting later than it does.
    from = min([max([shiftDay(from, -7), data.window_start]), ...anchors]);
    to = max([min([shiftDay(to, 7), data.window_end]), ...anchors]);
    // A window that collapsed (everything sits outside the term) still needs a
    // positive span, or every bar divides by zero and lands at 0%.
    if (to <= from) to = shiftDay(from, 30);
    const span = Math.max(1, daysBetween(from, to));
    return { start: from, end: to, span };
  }, [data, draft]);

  const pctOf = (iso: string) =>
    axis ? Math.max(0, Math.min(100, (daysBetween(axis.start, iso) / axis.span) * 100)) : 0;

  // ── dragging ───────────────────────────────────────────────────────────────
  const beginDrag = (e: React.PointerEvent, unit: string,
                     mode: "move" | "start" | "end") => {
    const current = draft[unit];
    if (!current || !axis) return;
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    dragRef.current = {
      unit, mode, originX: e.clientX, from: { ...current }, span: axis.span,
    };
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    const track = trackRef.current;
    if (!drag || !track || !axis) return;
    const width = track.getBoundingClientRect().width || 1;
    // Snap to whole days: a plan is made of days, and a half-day drag that
    // rounds silently is a date she did not choose.
    const shifted = Math.round(((e.clientX - drag.originX) / width) * drag.span);
    if (!Number.isFinite(shifted)) return;

    setMoved((d) => {
      const from = drag.from;
      let start = from.start;
      let end = from.end;
      if (drag.mode === "move") {
        start = shiftDay(from.start, shifted);
        end = shiftDay(from.end, shifted);
      } else if (drag.mode === "start") {
        start = shiftDay(from.start, shifted);
        if (start > end) start = end;
      } else {
        end = shiftDay(from.end, shifted);
        if (end < start) end = start;
      }
      return { ...d, [drag.unit]: { start, end } };
    });
  };

  const endDrag = () => { dragRef.current = null; };

  const setDate = (unit: string, which: "start" | "end", value: string) => {
    if (!value) return;
    setMoved((d) => {
      const row = d[unit] ?? draft[unit];
      if (!row) return d;
      const next = { ...row, [which]: value };
      // Keep the pair ordered rather than refusing the keystroke — she is
      // mid-edit, and a rejected input reads as a broken field.
      if (next.start > next.end) {
        if (which === "start") next.end = next.start; else next.start = next.end;
      }
      return { ...d, [unit]: next };
    });
  };

  const changed = useMemo(() => {
    if (!data) return [];
    return data.chapters.filter((c) => {
      const d = draft[c.unit_id];
      return d && (d.start !== c.planned_start || d.end !== c.planned_end);
    });
  }, [data, draft]);

  const save = async () => {
    if (!csId || !changed.length) return;
    setSaving(true);
    try {
      const out = await schoolApi.reschedulePlan(csId, changed.map((c) => ({
        unit_id: c.unit_id,
        start_date: draft[c.unit_id].start,
        end_date: draft[c.unit_id].end,
      })));
      setViolations(out.violations);
      onSaved();
      if (out.fits) {
        toast.success(`${changed.length} chapter${changed.length === 1 ? "" : "s"} moved`);
        onClose();
      } else {
        // Saved, but it does not fit. Keep her here with the reason on screen
        // rather than closing on a success toast that would be a lie.
        toast.warning("Saved — but the dates are tight. See what's flagged below.");
      }
    } catch (e) {
      showApiError(e, "Could not move those chapters");
    } finally {
      setSaving(false);
    }
  };

  const ordered = useMemo(() => {
    if (!data) return [];
    return [...data.chapters].sort((a, b) => {
      const da = draft[a.unit_id]?.start ?? "";
      const db = draft[b.unit_id]?.start ?? "";
      if (da && db && da !== db) return da.localeCompare(db);
      return a.position - b.position;
    });
  }, [data, draft]);

  // The gaps between consecutive scheduled chapters — the thing she opened this
  // to see, counted rather than left as empty background.
  const gaps = useMemo(() => {
    const scheduled = ordered
      .map((c) => ({ c, d: draft[c.unit_id] }))
      .filter((r) => r.d) as { c: (typeof ordered)[number]; d: { start: string; end: string } }[];
    const out: { after: string; before: string; from: string; to: string; days: number }[] = [];
    for (let i = 0; i < scheduled.length - 1; i++) {
      const from = shiftDay(scheduled[i].d.end, 1);
      const to = shiftDay(scheduled[i + 1].d.start, -1);
      const days = daysBetween(from, to) + 1;
      if (days > 0) {
        out.push({ after: scheduled[i].c.title, before: scheduled[i + 1].c.title,
          from, to, days });
      }
    }
    return out;
  }, [ordered, draft]);

  const today = todayKey();

  if (isLoading || !data || !axis) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">
        Loading the plan…
      </p>
    );
  }

  return (
        <div className="space-y-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
            {data.class_label} {data.subject_name}
            <span className="px-1.5 text-muted-foreground/50">·</span>
            {fmtDay(data.window_start)} → {fmtDay(data.window_end)}
            <span className="px-1.5 text-muted-foreground/50">·</span>
            {data.periods_per_week} periods a week
          </p>
          {data.lock_reason ? (
            <p className={cn(
              "flex items-start gap-2 rounded-lg border px-3 py-2 text-xs",
              data.locked ? "border-border bg-muted text-muted-foreground"
                : "border-border bg-card text-muted-foreground")}>
              <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{data.lock_reason}</span>
            </p>
          ) : null}

          {/* ── the ribbon ─────────────────────────────────────────────── */}
          <div className="rounded-xl border border-border bg-card p-3">
            {/* The year rides on the ends whenever the span crosses one: an
                Indian academic year runs Apr → Mar, so "1 Apr → 31 Mar" reads
                as a range that ends before it starts. */}
            <div className="mb-2 flex items-center justify-between gap-2 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
              <span>{fmtDay(axis.start, axis.start.slice(0, 4) !== axis.end.slice(0, 4))}</span>
              <span className="hidden sm:inline">
                Drag a bar to move it · drag an edge to stretch it
              </span>
              <span>{fmtDay(axis.end, axis.start.slice(0, 4) !== axis.end.slice(0, 4))}</span>
            </div>

            <div ref={trackRef}
              onPointerMove={onPointerMove}
              onPointerUp={endDrag}
              onPointerCancel={endDrag}
              className="relative select-none rounded-lg bg-muted/30"
              style={{ height: Math.max(LANE_H * ordered.length + 12, 60) }}>

              {/* The walls: exams, term ends and today, drawn through every
                  lane so a bar's collision with one is visible at a glance. */}
              {data.markers.map((mk, i) => {
                const left = pctOf(mk.date);
                const isExam = mk.kind === "exam";
                const width = isExam && mk.end_date
                  ? Math.max(0.6, pctOf(mk.end_date) - left) : 0;
                return (
                  <div key={`${mk.kind}-${i}`} className="pointer-events-none absolute inset-y-0"
                    style={{ left: `${left}%`, width: width ? `${width}%` : undefined }}>
                    {isExam ? (
                      <div className="h-full rounded-sm bg-danger/12 ring-1 ring-inset ring-danger/30" />
                    ) : (
                      <div className={cn("h-full w-px",
                        mk.kind === "today" ? "bg-foreground/60"
                          : "bg-border")} />
                    )}
                    {/* Exams label at the top, term ends and today at the
                        bottom. An exam block and the term end it sits inside are
                        days apart, so one shared row of labels overprinted them
                        into an unreadable smear. Two families, two rows.
                        Near the right edge the label flips to the other side of
                        its own marker rather than running off the ribbon. */}
                    <span className={cn(
                      "absolute max-w-[9rem] truncate font-mono text-[9px] uppercase tracking-wide",
                      isExam ? "top-0 text-danger" : "text-muted-foreground",
                      // Two term ends a fortnight apart printed over each other
                      // as "TERM 1TERM 2". Alternating rows costs nothing and
                      // survives any number of them.
                      !isExam ? (i % 2 ? "bottom-3" : "bottom-0") : "",
                      left > 68 ? "right-full mr-1 text-right" : "left-1")}>
                      {mk.label}
                    </span>
                  </div>
                );
              })}

              {/* The gaps, hatched and counted. */}
              {gaps.map((g) => (
                <div key={`${g.after}-${g.from}`}
                  className="pointer-events-none absolute inset-y-2 rounded-sm border border-dashed border-border/70"
                  style={{
                    left: `${pctOf(g.from)}%`,
                    width: `${Math.max(0.4, pctOf(g.to) - pctOf(g.from))}%`,
                  }} />
              ))}

              {/* The chapters. */}
              {ordered.map((c, i) => {
                const d = draft[c.unit_id];
                const top = 6 + i * LANE_H;
                if (!d) {
                  return (
                    <div key={c.unit_id}
                      className="absolute left-2 flex items-center gap-2 text-[11px] text-muted-foreground"
                      style={{ top, height: LANE_H - 8 }}>
                      <span className="rounded border border-dashed border-border px-1.5 py-0.5">
                        {c.title} · not scheduled
                      </span>
                    </div>
                  );
                }
                const left = pctOf(d.start);
                const width = Math.max(1.2, pctOf(shiftDay(d.end, 1)) - left);
                const moved = d.start !== c.planned_start || d.end !== c.planned_end;
                const done = c.status === "completed";
                // Under about a tenth of the ribbon there is no room for a name
                // inside the bar, so it sits beside it. A bar you cannot name is
                // a bar you cannot decide anything about.
                const outside = width < 11;
                return (
                  <div key={c.unit_id}
                    className={cn(
                      "absolute flex items-center rounded-md border text-[11px] shadow-sm",
                      done
                        // Already taught: history, and history does not move.
                        ? "cursor-not-allowed border-success/40 bg-success/15 text-foreground/70"
                        : moved
                          ? "cursor-grab border-primary bg-primary/20 ring-1 ring-primary"
                          : "cursor-grab border-border bg-card hover:border-primary/60",
                      c.locked ? "cursor-not-allowed" : "")}
                    style={{ left: `${left}%`, width: `${width}%`, top,
                      height: LANE_H - 10 }}
                    onPointerDown={(e) => {
                      if (!c.locked) beginDrag(e, c.unit_id, "move");
                    }}>
                    {!c.locked ? (
                      <span onPointerDown={(e) => {
                        e.stopPropagation(); beginDrag(e, c.unit_id, "start");
                      }}
                        className="h-full w-2 shrink-0 cursor-ew-resize rounded-l-md bg-foreground/10 hover:bg-foreground/25" />
                    ) : null}
                    <span className="flex min-w-0 flex-1 items-center gap-1 truncate px-1.5">
                      {c.locked ? <Lock className="h-3 w-3 shrink-0" />
                        : <GripVertical className="h-3 w-3 shrink-0 opacity-40" />}
                      {!outside ? <span className="truncate">{c.title}</span> : null}
                    </span>
                    {!c.locked ? (
                      <span onPointerDown={(e) => {
                        e.stopPropagation(); beginDrag(e, c.unit_id, "end");
                      }}
                        className="h-full w-2 shrink-0 cursor-ew-resize rounded-r-md bg-foreground/10 hover:bg-foreground/25" />
                    ) : null}
                    {outside ? (
                      <span className="pointer-events-none absolute left-[calc(100%+6px)] whitespace-nowrap text-[11px] text-muted-foreground">
                        {c.title}
                      </span>
                    ) : null}
                  </div>
                );
              })}
            </div>

            {gaps.length ? (
              <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                {gaps.map((g) => `${g.days}d free after ${g.after}`).join(" · ")}
              </p>
            ) : null}
          </div>

          {/* ── the ledger ────────────────────────────────────────────── */}
          <div className="overflow-hidden rounded-xl border border-border">
            <div className="grid gap-2 border-b border-border bg-muted/30 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground"
              style={{ gridTemplateColumns: "1.6fr 4rem 9rem 9rem 5rem" }}>
              <span>Chapter</span><span>Periods</span><span>Starts</span>
              <span>Ends</span><span>Days</span>
            </div>
            {!ordered.length ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                This subject has no chapters yet. Add them on the syllabus board,
                size them, then come back and lay them out.
              </p>
            ) : null}
            {ordered.map((c) => {
              const d = draft[c.unit_id];
              return (
                <div key={c.unit_id}
                  className="grid items-center gap-2 border-b border-border px-3 py-1.5 last:border-b-0"
                  style={{ gridTemplateColumns: "1.6fr 4rem 9rem 9rem 5rem" }}>
                  <span className="truncate text-sm">
                    {c.title}
                    {c.locked ? (
                      <span className="ml-1.5 text-[11px] text-muted-foreground">
                        · already taught
                      </span>
                    ) : null}
                  </span>
                  <span className="font-mono text-xs tabular-nums text-muted-foreground">
                    {c.est_periods ?? "—"}
                  </span>
                  {d ? (
                    <>
                      <input type="date" value={d.start} disabled={c.locked}
                        aria-label={`${c.title} starts`}
                        max={d.end}
                        onChange={(e) => setDate(c.unit_id, "start", e.target.value)}
                        className="h-7 rounded-md border border-border bg-card px-2 font-mono text-xs disabled:opacity-50" />
                      <input type="date" value={d.end} disabled={c.locked}
                        aria-label={`${c.title} ends`}
                        min={d.start}
                        onChange={(e) => setDate(c.unit_id, "end", e.target.value)}
                        className="h-7 rounded-md border border-border bg-card px-2 font-mono text-xs disabled:opacity-50" />
                      <span className="font-mono text-xs tabular-nums text-muted-foreground">
                        {daysBetween(d.start, d.end) + 1}d
                      </span>
                    </>
                  ) : (
                    <span className="col-span-3 text-xs text-muted-foreground">
                      Not scheduled — size its topics on the syllabus board first.
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {violations.length ? (
            <ul className="space-y-1.5">
              {violations.map((v, i) => (
                <li key={i}
                  className="flex items-start gap-2 rounded-lg border border-border bg-warning-soft/40 px-3 py-2 text-xs text-warning">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{v.message}</span>
                </li>
              ))}
            </ul>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">
              {changed.length
                ? `${changed.length} chapter${changed.length === 1 ? "" : "s"} moved · nothing is saved yet`
                : `Nothing moved yet. Today is ${fmtDay(today)}.`}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={onClose}>
                Cancel
              </Button>
              <Button size="sm" onClick={save} disabled={!changed.length || saving}>
                {saving ? "Saving…" : "Save the plan"}
              </Button>
            </div>
          </div>
        </div>
  );
}
