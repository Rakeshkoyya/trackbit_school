"use client";

import { CheckSquare, ListChecks, UserCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** ONE roll-call component, ONE default (V1-3, S-12).
 *
 *  The school sheet and the session sheet had opposite habits for the same act:
 *  one started every box unticked ("tick who answers"), the other started
 *  everyone present. Same teacher, same minute of the day, inverted muscle
 *  memory — and neither matched SPRD2 §5.4's "All present ✓, one tap".
 *
 *  The default is now capture-by-exception everywhere: **everyone present, tap
 *  the exceptions** (present → absent → late → present). The name-by-name flow
 *  survives as an explicit **Call the roll** toggle for teachers who prefer it —
 *  same storage, same payload, just a different starting point.
 */
export type RollStatus = "present" | "absent" | "late";

export type RollRow = {
  student_id: string;
  full_name: string;
  roll_no?: string | null;
  /** TT-4: which class the child is in. Null on an ordinary sheet; set on a
   *  combined period's, where the sheet groups by it — a teacher scanning
   *  eighty names for one child needs the room split the way the room is. */
  class_label?: string | null;
};

export type RollMark = { status: RollStatus; late_minutes: number | null };
export type RollMarks = Record<string, RollMark>;

const NEXT: Record<RollStatus, RollStatus> = {
  present: "absent", absent: "late", late: "present",
};
const TONE: Record<RollStatus, "success" | "danger" | "warning"> = {
  present: "success", absent: "danger", late: "warning",
};

export function emptyMarks(rows: RollRow[]): RollMarks {
  return Object.fromEntries(rows.map((r) => [
    r.student_id, { status: "present" as RollStatus, late_minutes: null },
  ]));
}

export function marksFrom(
  rows: RollRow[],
  statusOf: (r: RollRow) => { status?: string | null; late_minutes?: number | null },
): RollMarks {
  return Object.fromEntries(rows.map((r) => {
    const s = statusOf(r);
    const status = (s.status === "absent" || s.status === "late")
      ? (s.status as RollStatus) : "present";
    return [r.student_id, { status, late_minutes: s.late_minutes ?? null }];
  }));
}

export function rollCounts(marks: RollMarks) {
  const values = Object.values(marks);
  const absent = values.filter((m) => m.status === "absent").length;
  const late = values.filter((m) => m.status === "late").length;
  return { total: values.length, absent, late, present: values.length - absent };
}

export function RollCall({
  rows,
  marks,
  onChange,
  showLateMinutes = false,
  rollMode = false,
  onRollMode,
}: {
  rows: RollRow[];
  marks: RollMarks;
  onChange: (next: RollMarks) => void;
  /** Sessions capture how many minutes late; the period sheet doesn't ask. */
  showLateMinutes?: boolean;
  /** "Call the roll": start from nobody ticked and tick who answers. */
  rollMode?: boolean;
  onRollMode?: (on: boolean) => void;
}) {
  const set = (id: string, patch: Partial<RollMark>) =>
    onChange({ ...marks, [id]: { ...marks[id], ...patch } });

  const cycle = (id: string) => {
    const cur = marks[id]?.status ?? "present";
    const next = NEXT[cur];
    set(id, { status: next, late_minutes: next === "late" ? marks[id]?.late_minutes ?? null : null });
  };

  const allPresent = () => onChange(emptyMarks(rows));
  const noneMarked = () => onChange(Object.fromEntries(rows.map((r) => [
    r.student_id, { status: "absent" as RollStatus, late_minutes: null },
  ])));

  if (rows.length === 0) {
    return (
      <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
        No students on this class’s roster yet.
      </p>
    );
  }

  // TT-4 — one sheet, grouped by class when the room holds more than one. The
  // groups keep their server order so the sheet reads the same on every visit.
  const groups: { label: string | null; rows: RollRow[] }[] = [];
  for (const r of rows) {
    const label = r.class_label ?? null;
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.rows.push(r);
    else groups.push({ label, rows: [r] });
  }
  const grouped = groups.length > 1;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {rollMode
            ? "Call out each name and tap who answers."
            : "Everyone is present — tap only the exceptions."}
        </p>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={rollMode ? noneMarked : allPresent}>
            {rollMode ? <ListChecks className="h-4 w-4" /> : <CheckSquare className="h-4 w-4" />}
            {rollMode ? "Clear all" : "All present"}
          </Button>
          {onRollMode ? (
            <Button size="sm" variant="ghost"
              onClick={() => { onRollMode(!rollMode); if (!rollMode) noneMarked(); else allPresent(); }}>
              {rollMode ? "Back to exceptions" : "Call the roll"}
            </Button>
          ) : null}
        </div>
      </div>

      {groups.map((g, gi) => (
        <div key={g.label ?? gi}>
          {grouped ? (
            <p className="mb-1 mt-3 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground first:mt-0">
              {g.label ?? "Class"}
              <span className="ml-1.5 normal-case tracking-normal opacity-70">
                {g.rows.length} student{g.rows.length === 1 ? "" : "s"}
              </span>
            </p>
          ) : null}
      <div className="grid gap-1 sm:grid-cols-2">
        {g.rows.map((r) => {
          const m = marks[r.student_id] ?? { status: "present" as RollStatus, late_minutes: null };
          const present = m.status !== "absent";
          return (
            <div key={r.student_id} className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => cycle(r.student_id)}
                className={cn(
                  "flex min-w-0 flex-1 items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-sm active:scale-[0.99]",
                  m.status === "absent" ? "border-danger/40 bg-danger/5"
                    : m.status === "late" ? "border-warning/50 bg-warning-soft"
                      : "border-border bg-card",
                )}
              >
                <span className={cn(
                  "grid h-5 w-5 shrink-0 place-items-center rounded border",
                  present
                    ? "border-[color:var(--success,#234a37)] bg-[color:var(--success,#234a37)] text-white"
                    : "border-border bg-background",
                )}>
                  {present ? <UserCheck className="h-3.5 w-3.5" /> : null}
                </span>
                <span className="min-w-0 flex-1 truncate">
                  {r.roll_no ? `${r.roll_no}. ` : ""}{r.full_name}
                </span>
                {m.status !== "present" ? <Badge tone={TONE[m.status]}>{m.status}</Badge> : null}
              </button>
              {showLateMinutes && m.status === "late" ? (
                <Input className="h-9 w-16 shrink-0" type="number" min={0} placeholder="min"
                  aria-label={`Minutes late for ${r.full_name}`}
                  value={m.late_minutes ?? ""}
                  onChange={(e) => set(r.student_id, {
                    late_minutes: e.target.value ? Number(e.target.value) : null,
                  })} />
              ) : null}
            </div>
          );
        })}
      </div>
        </div>
      ))}
    </div>
  );
}
