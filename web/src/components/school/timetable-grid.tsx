"use client";

import { Fragment } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Home } from "lucide-react";

import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { TimetableBlock, TimetableClash, TimetableSlot } from "@/lib/school-types";

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const clashKey = (wd: number, p: number) => `${wd}:${p}`;
function clashSet(clashes: TimetableClash[]): Set<string> {
  return new Set(clashes.map((c) => clashKey(c.weekday, c.period_no)));
}

/** The value a cell's <select> carries: a class-subject id or `block:<id>`. */
const BLOCK_PREFIX = "block:";
function cellValue(slot: TimetableSlot | undefined): string {
  if (!slot) return "";
  return slot.slot_type === "block"
    ? `${BLOCK_PREFIX}${slot.session_id ?? ""}`
    : slot.class_subject_id ?? "";
}

function cellText(slot: TimetableSlot | undefined): string {
  if (!slot) return "";
  return slot.slot_type === "block" ? slot.block_name ?? "—" : slot.subject_name ?? "";
}

/**
 * Editable (admin) / read-only class grid: weekday columns × period rows.
 *
 * TT-2 changed two things. A cell may now hold a **block** — homework class,
 * games, an extra course, assembly — not just a subject, so the picker is
 * grouped and blocks are tinted to be distinguishable at a glance. And the day's
 * real clock runs down the left edge, with breaks drawn where they fall: once
 * the day runs to 19:00, "P9" on its own stops meaning anything to the person
 * building the grid.
 */
export function TimetableGrid({ classId, canEdit }: { classId: string; canEdit: boolean }) {
  const qc = useQueryClient();
  const { data: grid } = useQuery({
    queryKey: ["timetable", classId],
    queryFn: () => schoolApi.timetableGrid(classId),
    enabled: !!classId,
  });
  const { data: subjects = [] } = useQuery({
    queryKey: ["class-subjects", classId],
    queryFn: () => schoolApi.classSubjects(classId),
    enabled: !!classId && canEdit,
  });
  const { data: blocks = [] } = useQuery({
    queryKey: ["timetable-blocks"],
    queryFn: schoolApi.blocks,
    enabled: canEdit,
  });

  const inv = () => {
    qc.invalidateQueries({ queryKey: ["timetable", classId] });
    qc.invalidateQueries({ queryKey: ["timetable-clashes"] });
    qc.invalidateQueries({ queryKey: ["timetable-blocks"] });
  };
  const setSlot = useMutation({
    mutationFn: (v: {
      weekday: number; period_no: number;
      slot_type: "subject" | "block";
      class_subject_id?: string | null; session_id?: string | null;
    }) => schoolApi.setSlot({ class_id: classId, ...v }),
    onSuccess: () => inv(),
    onError: (e) => showApiError(e, "Could not set period"),
  });
  const clearSlot = useMutation({
    mutationFn: (v: { weekday: number; period_no: number }) =>
      schoolApi.clearSlot({ class_id: classId, ...v }),
    onSuccess: () => inv(),
    onError: (e) => showApiError(e, "Could not clear period"),
  });

  if (!grid) return <div className="h-40 animate-pulse rounded-lg bg-muted" />;

  const clashes = clashSet(grid.clashes);
  const at = (wd: number, p: number) =>
    grid.slots.find((s) => s.weekday === wd && s.period_no === p);
  const periods = Array.from({ length: grid.periods_per_day }, (_, i) => i + 1);
  const clockOf = new Map(grid.periods.map((p) => [p.period_no, p]));
  // Breaks are keyed by the period they follow, so they slot into the rows.
  const breaksAfter = new Map<number, typeof grid.breaks>();
  for (const b of grid.breaks) {
    breaksAfter.set(b.after_period_no, [...(breaksAfter.get(b.after_period_no) ?? []), b]);
  }
  const live = (b: TimetableBlock) => b.active;
  const colSpan = grid.weekdays.length + 1;

  const onPick = (wd: number, p: number, raw: string) => {
    if (!raw) { clearSlot.mutate({ weekday: wd, period_no: p }); return; }
    if (raw.startsWith(BLOCK_PREFIX)) {
      setSlot.mutate({
        weekday: wd, period_no: p, slot_type: "block",
        session_id: raw.slice(BLOCK_PREFIX.length), class_subject_id: null,
      });
      return;
    }
    setSlot.mutate({
      weekday: wd, period_no: p, slot_type: "subject",
      class_subject_id: raw, session_id: null,
    });
  };

  return (
    <div>
      {grid.clashes.length > 0 ? (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-warning">
          <AlertTriangle className="h-3.5 w-3.5" /> {grid.clashes.length} teacher clash
          {grid.clashes.length > 1 ? "es" : ""} — a teacher is in two places at once.
        </p>
      ) : null}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-muted/40 text-xs text-muted-foreground">
              <th className="w-28 px-2 py-2 text-left font-medium">Period</th>
              {grid.weekdays.map((wd) => (
                <th key={wd} className="px-2 py-2 text-left font-medium">{WEEKDAYS[wd]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {/* A break before period 1 (morning assembly time) still belongs here. */}
            {(breaksAfter.get(0) ?? []).map((b, i) => (
              <tr key={`b0-${i}`} className="border-t border-border bg-muted/20">
                <td colSpan={colSpan} className="px-2 py-1 text-xs text-muted-foreground">
                  {b.label}{b.start ? ` · ${b.start}–${b.end}` : ""}
                </td>
              </tr>
            ))}
            {periods.map((p) => {
              const clock = clockOf.get(p);
              return (
                <Fragment key={p}>
                  <tr className="border-t border-border">
                    <td className="px-2 py-1.5 align-top">
                      <div className="text-xs font-medium text-muted-foreground">P{p}</div>
                      {clock?.start ? (
                        <div className="text-[11px] text-muted-foreground/70">
                          {clock.start}–{clock.end}
                        </div>
                      ) : null}
                    </td>
                    {grid.weekdays.map((wd) => {
                      const slot = at(wd, p);
                      const isClash = clashes.has(clashKey(wd, p));
                      const isBlock = slot?.slot_type === "block";
                      return (
                        <td key={wd} className="px-1 py-1">
                          {canEdit ? (
                            <select
                              value={cellValue(slot)}
                              onChange={(e) => onPick(wd, p, e.target.value)}
                              className={`w-full rounded border px-1.5 py-1 text-xs ${
                                isClash ? "border-warning ring-1 ring-warning" : "border-border"
                              } ${isBlock ? "bg-primary/5 font-medium" : "bg-card"}`}
                              title={isClash ? "Teacher clash at this period" : undefined}
                            >
                              <option value="">—</option>
                              <optgroup label="Subjects">
                                {subjects.map((s) => (
                                  <option key={s.id} value={s.id}>{s.subject_name}</option>
                                ))}
                              </optgroup>
                              {blocks.filter(live).length ? (
                                <optgroup label="Blocks">
                                  {blocks.filter(live).map((b) => (
                                    <option key={b.id} value={`${BLOCK_PREFIX}${b.id}`}>
                                      {b.name} · {b.kind_label}
                                      {b.hostellers_only ? " · hostellers" : ""}
                                    </option>
                                  ))}
                                </optgroup>
                              ) : null}
                            </select>
                          ) : (
                            <div
                              className={`min-h-7 rounded px-1.5 py-1 text-xs ${
                                isClash ? "bg-warning/10 text-warning"
                                  : isBlock ? "bg-primary/10 font-medium"
                                    : slot ? "bg-muted/50" : ""
                              }`}
                              title={isClash ? "Teacher clash" : undefined}
                            >
                              <span className="inline-flex items-center gap-1">
                                {cellText(slot)}
                                {slot?.hostellers_only ? (
                                  <Home className="h-3 w-3 opacity-60" aria-label="Hostellers only" />
                                ) : null}
                              </span>
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                  {(breaksAfter.get(p) ?? []).map((b, i) => (
                    <tr key={`b${p}-${i}`} className="border-t border-border bg-muted/20">
                      <td colSpan={colSpan} className="px-2 py-1 text-xs text-muted-foreground">
                        {b.label}{b.start ? ` · ${b.start}–${b.end}` : ""}
                      </td>
                    </tr>
                  ))}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {canEdit && !grid.has_timings ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Set the school timings above to put real times against these periods.
        </p>
      ) : null}
    </div>
  );
}

/** A teacher's own week (read-only), assembled from her slots across classes. */
export function TeacherWeekGrid() {
  const { data: week } = useQuery({ queryKey: ["my-week"], queryFn: schoolApi.myWeek });
  if (!week) return <div className="h-40 animate-pulse rounded-lg bg-muted" />;
  const at = (wd: number, p: number) => week.slots.find((s) => s.weekday === wd && s.period_no === p);
  const periods = Array.from({ length: week.periods_per_day }, (_, i) => i + 1);
  const clockOf = new Map(week.periods.map((p) => [p.period_no, p]));
  const empty = week.slots.length === 0;

  return (
    <div>
      {empty ? (
        <p className="mb-3 text-sm text-muted-foreground">
          No timetable set for your classes yet — your admin builds it under Plan → Timetable.
        </p>
      ) : null}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-muted/40 text-xs text-muted-foreground">
              <th className="w-28 px-2 py-2 text-left font-medium">Period</th>
              {week.weekdays.map((wd) => (
                <th key={wd} className="px-2 py-2 text-left font-medium">{WEEKDAYS[wd]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map((p) => {
              const clock = clockOf.get(p);
              return (
                <tr key={p} className="border-t border-border">
                  <td className="px-2 py-1.5 align-top">
                    <div className="text-xs font-medium text-muted-foreground">P{p}</div>
                    {clock?.start ? (
                      <div className="text-[11px] text-muted-foreground/70">
                        {clock.start}–{clock.end}
                      </div>
                    ) : null}
                  </td>
                  {week.weekdays.map((wd) => {
                    const slot = at(wd, p);
                    const isBlock = slot?.slot_type === "block";
                    return (
                      <td key={wd} className="px-1 py-1">
                        <div className={`min-h-7 rounded px-1.5 py-1 text-xs ${
                          isBlock ? "bg-primary/10 font-medium" : slot ? "bg-muted/50" : ""
                        }`}>
                          {slot
                            ? isBlock
                              ? `${slot.block_name ?? ""} · ${slot.class_label}`
                              : `${slot.class_label} · ${slot.subject_name ?? ""}`
                            : ""}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
