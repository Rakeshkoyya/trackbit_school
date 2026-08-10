"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, GripVertical, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { showApiError } from "@/lib/errors";
import { todayKey } from "@/lib/format";
import { schoolApi } from "@/lib/school-api";
import type { PeriodTime } from "@/lib/school-types";

/**
 * The school day, editable (TT-2).
 *
 * Before this there was no screen anywhere in the app that could set a period's
 * start and end — the admin could change `periods_per_day` and nothing else, so
 * "8:00–2:00, then a break, then homework class at 3:30" was unsayable.
 *
 * Two things it is careful about:
 *
 *  * **A row is a period or a break, and only periods are numbered.** The number
 *    is derived and shown, never typed: adding a break between P4 and P5 must
 *    not renumber anything, and the only way to guarantee that is to compute the
 *    numbers from the list.
 *  * **Saving is effective-dated.** The default is today, and the field is right
 *    there, because the founder's case is reshaping the day after Term 1 exams —
 *    at which point last term's timesheets must keep last term's clock.
 */

const PERIOD = "period";

/** Common break names. Free text is still allowed — this is a shortcut, not a list. */
const BREAK_KINDS = ["break", "lunch", "assembly", "games", "prayer"];

type Row = PeriodTime;

function isPeriod(r: Row): boolean {
  return (r.kind || PERIOD) === PERIOD;
}

/** Period numbers, derived exactly the way `school_clock` derives them. */
function numbering(rows: Row[]): (number | null)[] {
  let n = 0;
  return rows.map((r) => (isPeriod(r) ? ++n : null));
}

function toMinutes(s: string): number | null {
  const [h, m] = s.split(":").map(Number);
  return Number.isNaN(h) || Number.isNaN(m) ? null : h * 60 + m;
}

function addMinutes(hhmm: string, mins: number): string {
  const base = toMinutes(hhmm);
  if (base === null) return hhmm;
  const t = (base + mins + 24 * 60) % (24 * 60);
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}

/** The same three rules `services/bell.validate_entries` enforces, said sooner. */
function problems(rows: Row[]): string | null {
  let lastEnd: number | null = null;
  for (let i = 0; i < rows.length; i++) {
    const start = toMinutes(rows[i].start);
    const end = toMinutes(rows[i].end);
    if (start === null || end === null) return `Row ${i + 1}: give both a start and an end time.`;
    if (end <= start) return `Row ${i + 1} ends at or before it starts.`;
    if (lastEnd !== null && start < lastEnd) {
      return `Row ${i + 1} starts before the row above it ends — put the day in order.`;
    }
    lastEnd = end;
  }
  if (!rows.some(isPeriod)) return "A school day needs at least one period.";
  return null;
}

export function BellEditor({ yearId }: { yearId: string }) {
  const qc = useQueryClient();
  const { data: bell } = useQuery({
    queryKey: ["bell", yearId],
    queryFn: () => schoolApi.bellSchedule(yearId),
    enabled: !!yearId,
  });
  const { data: history } = useQuery({
    queryKey: ["bell-history", yearId],
    queryFn: () => schoolApi.bellHistory(yearId),
    enabled: !!yearId,
  });

  const [rows, setRows] = useState<Row[]>([]);
  const [from, setFrom] = useState<string>(todayKey());
  const [note, setNote] = useState("");
  const [dirty, setDirty] = useState(false);
  const [syncedFrom, setSyncedFrom] = useState<string | null>(null);

  // Seed the editor from the server's copy — adjusted during render rather than
  // in an effect, which is React's own answer for "reset state when the props
  // change" and avoids the cascading re-render an effect would cause. Once she
  // has touched a row (`dirty`) the server no longer overwrites her work.
  const serverKey = bell ? `${bell.id ?? "none"}:${bell.effective_from ?? ""}` : null;
  if (bell && !dirty && serverKey !== syncedFrom) {
    setSyncedFrom(serverKey);
    setRows(bell.entries.map((e) => ({ ...e })));
  }

  const nums = useMemo(() => numbering(rows), [rows]);
  const periodCount = nums.filter((n) => n !== null).length;
  const issue = rows.length ? problems(rows) : null;

  const save = useMutation({
    mutationFn: () => schoolApi.setBellSchedule({
      academic_year_id: yearId,
      entries: rows,
      effective_from: from,
      note: note.trim() || null,
    }),
    onSuccess: () => {
      setDirty(false);
      setSyncedFrom(null);  // re-seed from whatever the server now says
      setNote("");
      qc.invalidateQueries({ queryKey: ["bell", yearId] });
      qc.invalidateQueries({ queryKey: ["bell-history", yearId] });
      qc.invalidateQueries({ queryKey: ["timetable"] });
      qc.invalidateQueries({ queryKey: ["period-config", yearId] });
      toast.success("School timings saved");
    },
    onError: (e) => showApiError(e, "Could not save the timings"),
  });

  const edit = (i: number, patch: Partial<Row>) => {
    setDirty(true);
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  };

  const addRow = (kind: string) => {
    setDirty(true);
    setRows((prev) => {
      const last = prev[prev.length - 1];
      const start = last ? last.end : "08:00";
      const mins = kind === PERIOD ? 40 : 15;
      return [...prev, { start, end: addMinutes(start, mins), kind, label: null }];
    });
  };

  const removeRow = (i: number) => {
    setDirty(true);
    setRows((prev) => prev.filter((_, j) => j !== i));
  };

  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= rows.length) return;
    setDirty(true);
    setRows((prev) => {
      const next = [...prev];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  };

  if (!bell) return <div className="h-40 animate-pulse rounded-lg bg-muted" />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-1.5 text-sm font-semibold">
            <Clock className="h-4 w-4" /> School timings
          </h3>
          <p className="text-xs text-muted-foreground">
            {periodCount} period{periodCount === 1 ? "" : "s"} a day
            {bell.effective_from ? ` · in force since ${bell.effective_from}` : ""}
          </p>
        </div>
        {!bell.has_timings ? (
          <p className="text-xs text-warning">
            No clock set yet — periods are numbered but have no times.
          </p>
        ) : null}
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-muted/40 text-xs text-muted-foreground">
              <th className="w-20 px-2 py-2 text-left font-medium">#</th>
              <th className="w-28 px-2 py-2 text-left font-medium">Start</th>
              <th className="w-28 px-2 py-2 text-left font-medium">End</th>
              <th className="px-2 py-2 text-left font-medium">What it is</th>
              <th className="w-24 px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const n = nums[i];
              return (
                <tr key={i} className="border-t border-border">
                  <td className="px-2 py-1.5">
                    {n !== null ? (
                      <span className="inline-flex h-6 min-w-6 items-center justify-center rounded bg-primary/10 px-1.5 text-xs font-semibold text-primary">
                        P{n}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">break</span>
                    )}
                  </td>
                  <td className="px-2 py-1.5">
                    <Input type="time" value={r.start} className="h-8 text-xs"
                           onChange={(e) => edit(i, { start: e.target.value })} />
                  </td>
                  <td className="px-2 py-1.5">
                    <Input type="time" value={r.end} className="h-8 text-xs"
                           onChange={(e) => edit(i, { end: e.target.value })} />
                  </td>
                  <td className="px-2 py-1.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <select
                        value={isPeriod(r) ? PERIOD : "break-kind"}
                        onChange={(e) => edit(i, {
                          kind: e.target.value === PERIOD ? PERIOD : "break",
                        })}
                        className="h-8 rounded border border-border bg-card px-1.5 text-xs"
                      >
                        <option value={PERIOD}>Teaching period</option>
                        <option value="break-kind">Break</option>
                      </select>
                      {!isPeriod(r) ? (
                        <>
                          <select
                            value={BREAK_KINDS.includes(r.kind) ? r.kind : "break"}
                            onChange={(e) => edit(i, { kind: e.target.value })}
                            className="h-8 rounded border border-border bg-card px-1.5 text-xs"
                          >
                            {BREAK_KINDS.map((k) => (
                              <option key={k} value={k}>{k}</option>
                            ))}
                          </select>
                          <Input
                            value={r.label ?? ""} placeholder="Name it (optional)"
                            className="h-8 w-40 text-xs"
                            onChange={(e) => edit(i, { label: e.target.value })}
                          />
                        </>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-2 py-1.5">
                    <div className="flex items-center justify-end gap-0.5">
                      <button type="button" onClick={() => move(i, -1)} disabled={i === 0}
                              aria-label="Move up"
                              className="rounded p-1 text-muted-foreground hover:bg-muted disabled:opacity-30">
                        <GripVertical className="h-3.5 w-3.5 rotate-180" />
                      </button>
                      <button type="button" onClick={() => move(i, 1)}
                              disabled={i === rows.length - 1} aria-label="Move down"
                              className="rounded p-1 text-muted-foreground hover:bg-muted disabled:opacity-30">
                        <GripVertical className="h-3.5 w-3.5" />
                      </button>
                      <button type="button" onClick={() => removeRow(i)} aria-label="Remove row"
                              className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 ? (
              <tr className="border-t border-border">
                <td colSpan={5} className="px-3 py-6 text-center text-sm text-muted-foreground">
                  No timings yet — add the first period to start the day.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => addRow(PERIOD)}>
          <Plus className="mr-1 h-3.5 w-3.5" /> Add period
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={() => addRow("break")}>
          <Plus className="mr-1 h-3.5 w-3.5" /> Add break
        </Button>
      </div>

      {issue ? <p className="text-xs text-destructive">{issue}</p> : null}

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-muted/20 p-3">
        <label className="text-xs">
          <span className="mb-1 block text-muted-foreground">In force from</span>
          <Input type="date" value={from} className="h-8 w-40 text-xs"
                 onChange={(e) => { setDirty(true); setFrom(e.target.value); }} />
        </label>
        <label className="min-w-48 flex-1 text-xs">
          <span className="mb-1 block text-muted-foreground">Why (optional)</span>
          <Input value={note} placeholder="e.g. after Term 1 exams" className="h-8 text-xs"
                 onChange={(e) => setNote(e.target.value)} />
        </label>
        <Button type="button" size="sm" disabled={!!issue || !rows.length || save.isPending}
                onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save timings"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Changing the day is an addition, never an overwrite: everything already
        recorded keeps the clock it was recorded against.
      </p>

      {history && history.schedules.length > 1 ? (
        <details className="rounded-lg border border-border">
          <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-muted-foreground">
            Earlier shapes of the day ({history.schedules.length - 1})
          </summary>
          <ul className="divide-y divide-border">
            {history.schedules.slice(1).map((s) => (
              <li key={s.id ?? s.effective_from} className="px-3 py-2 text-xs">
                <span className="font-medium">
                  {s.effective_from} → {s.effective_to ?? "now"}
                </span>
                <span className="text-muted-foreground">
                  {" "}· {s.periods_per_day} periods{s.note ? ` · ${s.note}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
