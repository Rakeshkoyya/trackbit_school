"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";

import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { TimetableClash } from "@/lib/school-types";

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const clashKey = (wd: number, p: number) => `${wd}:${p}`;
function clashSet(clashes: TimetableClash[]): Set<string> {
  return new Set(clashes.map((c) => clashKey(c.weekday, c.period_no)));
}

/** Editable (admin) / read-only class grid: weekday columns × period rows. */
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

  const inv = () => {
    qc.invalidateQueries({ queryKey: ["timetable", classId] });
    qc.invalidateQueries({ queryKey: ["timetable-clashes"] });
  };
  const setSlot = useMutation({
    mutationFn: (v: { weekday: number; period_no: number; class_subject_id: string }) =>
      schoolApi.setSlot({ class_id: classId, ...v }),
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

  return (
    <div>
      {grid.clashes.length > 0 ? (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-warning">
          <AlertTriangle className="h-3.5 w-3.5" /> {grid.clashes.length} teacher clash
          {grid.clashes.length > 1 ? "es" : ""} — a teacher is in two classes at once.
        </p>
      ) : null}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-muted/40 text-xs text-muted-foreground">
              <th className="w-16 px-2 py-2 text-left font-medium">Period</th>
              {grid.weekdays.map((wd) => (
                <th key={wd} className="px-2 py-2 text-left font-medium">{WEEKDAYS[wd]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map((p) => (
              <tr key={p} className="border-t border-border">
                <td className="px-2 py-1.5 text-xs font-medium text-muted-foreground">P{p}</td>
                {grid.weekdays.map((wd) => {
                  const slot = at(wd, p);
                  const isClash = clashes.has(clashKey(wd, p));
                  return (
                    <td key={wd} className="px-1 py-1">
                      {canEdit ? (
                        <select
                          value={slot?.class_subject_id ?? ""}
                          onChange={(e) => {
                            const v = e.target.value;
                            if (v) setSlot.mutate({ weekday: wd, period_no: p, class_subject_id: v });
                            else clearSlot.mutate({ weekday: wd, period_no: p });
                          }}
                          className={`w-full rounded border bg-card px-1.5 py-1 text-xs ${
                            isClash ? "border-warning ring-1 ring-warning" : "border-border"
                          }`}
                          title={isClash ? "Teacher clash at this period" : undefined}
                        >
                          <option value="">—</option>
                          {subjects.map((s) => (
                            <option key={s.id} value={s.id}>{s.subject_name}</option>
                          ))}
                        </select>
                      ) : (
                        <div
                          className={`min-h-7 rounded px-1.5 py-1 text-xs ${
                            isClash ? "bg-warning/10 text-warning" : slot ? "bg-muted/50" : ""
                          }`}
                          title={isClash ? "Teacher clash" : undefined}
                        >
                          {slot?.subject_name ?? ""}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** A teacher's own week (read-only), assembled from her slots across classes. */
export function TeacherWeekGrid() {
  const { data: week } = useQuery({ queryKey: ["my-week"], queryFn: schoolApi.myWeek });
  if (!week) return <div className="h-40 animate-pulse rounded-lg bg-muted" />;
  const at = (wd: number, p: number) => week.slots.find((s) => s.weekday === wd && s.period_no === p);
  const periods = Array.from({ length: week.periods_per_day }, (_, i) => i + 1);
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
              <th className="w-16 px-2 py-2 text-left font-medium">Period</th>
              {week.weekdays.map((wd) => (
                <th key={wd} className="px-2 py-2 text-left font-medium">{WEEKDAYS[wd]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map((p) => (
              <tr key={p} className="border-t border-border">
                <td className="px-2 py-1.5 text-xs font-medium text-muted-foreground">P{p}</td>
                {week.weekdays.map((wd) => {
                  const slot = at(wd, p);
                  return (
                    <td key={wd} className="px-1 py-1">
                      <div className={`min-h-7 rounded px-1.5 py-1 text-xs ${slot ? "bg-muted/50" : ""}`}>
                        {slot ? `${slot.class_label} · ${slot.subject_name ?? ""}` : ""}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
